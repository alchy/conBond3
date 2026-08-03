"""Doménová logika logovátka: kam záznam patří, jak se zapíše a co se z něj počítá.

Tenhle soubor nezná HTTP, nezná sokety a nečte konfiguraci ze souboru — dostane
hotové hodnoty a pracuje nad nimi (README-MODULES.md § 1). Díky tomu se dá celý
otestovat bez spuštěné služby a používat i v procesu.

Skládá se ze čtyř věcí, které spolu souvisejí, ale každá jde vyzkoušet zvlášť:

    route()     čistá funkce záznam → cesta; dělení proudu bez zásahu do kódu
    Writer      zápis JSONL, rotace podle velikosti, mazání podle stáří
    Summary     počty podle komponenta × metoda × result, přežívají restart
    LoggerService  spojení výše dohromady plus kruhový buffer pro sledování
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from cb_logger import objects as objects_mod
from cb_logger.record import LogRecord, Result, from_wire

#: Verze tvaru souboru se souhrnem. Čtečka umí předchozí verzi, nebo řekne,
#: že neumí — nikdy nehádá (README-MODULES.md § 14).
SUMMARY_FORMAT_VERSION = 1

#: Jak se jmenují otočené soubory. Vzor slouží i ke zpětnému hledání při mazání
#: podle stáří, proto je zapsaný jednou a použitý dvakrát.
_ROTATED_SUFFIX = "%Y%m%dT%H%M%S"
_ROTATED_PATTERN = re.compile(r"\.(\d{8}T\d{6})\.jsonl$")


def now_iso() -> str:
    """Vrátí aktuální čas v ISO 8601 s milisekundami, v UTC.

    Proč UTC a ne místní čas: log ze dvou dnů kolem přechodu na letní čas by
    v místním čase obsahoval hodinu, která se opakuje, a hodinu, která
    neexistuje. Řadit takový log podle času nejde.

    Proč to není metoda služby: čas se do funkcí předává parametrem
    (README-MODULES.md § 3). Tahle funkce je jediné místo, které na hodiny sahá,
    a volá se z okraje systému, ne z logiky.

    Výstup:
        Řetězec jako `2026-08-03T14:22:41.183Z`. Milisekundy jsou tam proto,
        že v jednom průchodu vznikne během jedné sekundy klidně sto záznamů
        a bez nich by se nedaly seřadit.
    """
    t = datetime.now(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def route(record: LogRecord, routing: dict[str, Any]) -> str:
    """Vybere podle pravidel soubor, do kterého záznam patří.

    Proč je to čistá funkce a ne `if` v zapisovači: dělení proudu se dodatečně
    zavádí špatně. Kdyby se zapisovalo rovnou do jednoho souboru, přibyl by
    později `if` pro komponentu, pak druhý pro úroveň, pak třetí pro velikost —
    a z toho vzniká kód, který se nedá vyměnit. Tady je jediné místo, kde se
    rozhoduje kam, a testuje se bez zapisování.

    Vstup:
        record: ověřený záznam.
        routing: blok `module.routing` z konfigurace — klíč `default` s cestou
            a `rules` se seznamem pravidel. Pravidla se procházejí shora dolů,
            **první shoda vyhrává**. Pravidlo musí mít vedle `to` aspoň jednu
            podmínku; schéma to vynucuje, protože pravidlo bez podmínky by
            chytilo všechno a zastínilo výchozí proud.

    Výstup:
        Cesta k souboru jako řetězec. Když nesedlo žádné pravidlo, vrací
        `routing["default"]`.

    Při chybě:
        Nevyhazuje. Neznámý klíč v pravidle by neprošel validací konfigurace,
        takže sem se nedostane.
    """
    for pravidlo in routing.get("rules", ()):
        if _rule_matches(record, pravidlo):
            return pravidlo["to"]
    return routing["default"]


def _rule_matches(record: LogRecord, rule: dict[str, Any]) -> bool:
    """Řekne, jestli záznam odpovídá pravidlu směrování.

    Podmínky v pravidle platí **současně** (logické A). Dvě podmínky vedle sebe
    znamenají „obojí", ne „kterákoli" — kdyby platilo NEBO, nešlo by zúžit
    pravidlo na debug záznamy jedné komponenty, což je nejčastější potřeba.

    Vstup:
        record: ověřený záznam.
        rule: jedno pravidlo z konfigurace, včetně klíče `to`, který se
            při porovnávání přeskakuje.

    Výstup:
        `True`, když záznam vyhovuje všem podmínkám pravidla.

    Při chybě:
        Nevyhazuje.
    """
    for klic, ocekavano in rule.items():
        if klic == "to":
            continue
        if klic == "malformed":
            if record.malformed is not ocekavano:
                return False
        elif klic == "level":
            if record.level.value != ocekavano:
                return False
        elif klic == "result":
            if record.result.value != ocekavano:
                return False
        elif klic == "component":
            if record.component != ocekavano:
                return False
    return True


class Writer:
    """Zapisuje záznamy do JSONL souborů, otáčí je a maže staré.

    Proč JSONL a ne jeden velký JSON: jde připisovat na konec a číst po částech,
    aniž se načte celý soubor. Je to pořád JSON, takže platí, že do dat jde
    vidět bez nástroje.

    Proč drží otevřené popisovače: zápis do logu je krátké a časté volání.
    Otevřít a zavřít soubor u každého záznamu by z logování udělalo to nejdražší
    v systému a někdo by ho vypnul.
    """

    def __init__(self, *, rotate_max_bytes: int, retention_days: int):
        """Vstup:
            rotate_max_bytes: velikost, při které se soubor otočí.
            retention_days: kolik dní se otočené soubory drží; nula znamená
                bez mazání.
        """
        self._rotate_max_bytes = rotate_max_bytes
        self._retention_days = retention_days
        self._handles: dict[str, Any] = {}
        self._lock = threading.Lock()

    def write(self, records: Iterable[tuple[str, LogRecord]]) -> int:
        """Zapíše dvojice (cesta, záznam) a vrátí počet zapsaných.

        Proč bere dávku a ne jeden záznam: klient posílá po dávkách a zápis
        celé dávky pod jedním zámkem je řádově levnější než zamykat u každého
        řádku.

        Vstup:
            records: dvojice (cesta k souboru, záznam). Cestu vybral směrovač.

        Výstup:
            Počet skutečně zapsaných záznamů.

        Při chybě:
            `OSError`, když se nedá zapisovat na disk. Vyšší vrstva to přeloží
            na typovanou chybu; tady se nemlčí, protože ztráta zápisu je
            přesně to, co se nesmí stát tiše.
        """
        zapsano = 0
        with self._lock:
            for cesta, zaznam in records:
                popisovac = self._handle_for(cesta)
                radek = json.dumps(
                    zaznam.to_json_object(), ensure_ascii=False, sort_keys=False
                )
                popisovac.write(radek + "\n")
                zapsano += 1
            for popisovac in self._handles.values():
                # Vyprázdnit hned po dávce: nedopsaný řádek v systémové
                # vyrovnávací paměti je při pádu procesu ztracený, a to zrovna
                # ten poslední, který obvykle říká, co se stalo.
                popisovac.flush()
            self._rotate_if_needed()
        return zapsano

    def write_objects(self, records: Iterable[tuple[str, Any]]) -> int:
        """Zapíše objektové záznamy. Stejná mechanika jako `write`, jiný typ.

        Proč vlastní metoda a ne společná se `write`: obojí zapisuje JSONL, ale
        objektový záznam má jiný typ a společná metoda by musela mít parametr
        „co to je". `if` podle druhu dat je diagnostika chybějícího švu — tady
        je levnější mít dvě metody než jednu s odbočkou.

        Vstup:
            records: dvojice (cesta k souboru, objektový záznam).

        Výstup:
            Počet zapsaných záznamů.

        Při chybě:
            `OSError`, když se nedá zapisovat na disk.
        """
        zapsano = 0
        with self._lock:
            for cesta, zaznam in records:
                popisovac = self._handle_for(cesta)
                popisovac.write(
                    json.dumps(zaznam.to_json_object(), ensure_ascii=False) + "\n"
                )
                zapsano += 1
            for popisovac in self._handles.values():
                popisovac.flush()
            self._rotate_if_needed()
        return zapsano

    def _handle_for(self, cesta: str):
        """Vrátí otevřený popisovač pro cestu; při prvním použití ho založí.

        Vstup:
            cesta: absolutní cesta k souboru.

        Výstup:
            Otevřený soubor v režimu připisování.

        Při chybě:
            `OSError`, když adresář nejde vytvořit nebo soubor otevřít.
        """
        popisovac = self._handles.get(cesta)
        if popisovac is None:
            Path(cesta).parent.mkdir(parents=True, exist_ok=True)
            popisovac = open(cesta, "a", encoding="utf-8")
            self._handles[cesta] = popisovac
        return popisovac

    def _rotate_if_needed(self) -> None:
        """Otočí soubory, které přerostly strop, a smaže staré otočené.

        Volá se po každé dávce, ne na časovač: rotace podle velikosti musí
        nastat, když velikost naroste, a to se pozná jedině po zápisu.

        Při chybě:
            Nevyhazuje. Selhání rotace nesmí shodit zápis — plný soubor je
            horší než otočený, ale pořád lepší než ztracený záznam.
        """
        for cesta, popisovac in list(self._handles.items()):
            try:
                if popisovac.tell() < self._rotate_max_bytes:
                    continue
                popisovac.close()
                del self._handles[cesta]
                razitko = datetime.now(timezone.utc).strftime(_ROTATED_SUFFIX)
                otoceny = Path(cesta).with_suffix(f".{razitko}.jsonl")
                Path(cesta).rename(otoceny)
                self._delete_expired(Path(cesta).parent)
            except OSError:
                # Popisovač je zavřený a z mapy pryč; další zápis ho založí
                # znovu. Horší než neotočit je spadnout uprostřed zápisu.
                self._handles.pop(cesta, None)

    def _delete_expired(self, adresar: Path) -> None:
        """Smaže otočené soubory starší než `retention_days`.

        Proč se stáří čte z názvu a ne z času úpravy souboru: čas úpravy se
        mění kopírováním a zálohováním, takže by se retence chovala jinak po
        každém přesunu dat. Název je fakt o tom, kdy soubor vznikl.

        Vstup:
            adresar: kde otočené soubory leží.

        Při chybě:
            Nevyhazuje. Neuklizený soubor je drobnost; spadlý zápis není.
        """
        if self._retention_days <= 0:
            return
        hranice = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        for soubor in adresar.glob("*.jsonl"):
            shoda = _ROTATED_PATTERN.search(soubor.name)
            if not shoda:
                continue
            try:
                vznik = datetime.strptime(shoda.group(1), _ROTATED_SUFFIX).replace(
                    tzinfo=timezone.utc
                )
                if vznik < hranice:
                    soubor.unlink()
            except (ValueError, OSError):
                continue

    def close(self) -> None:
        """Zavře všechny otevřené popisovače. Volá se explicitně při ukončení."""
        with self._lock:
            for popisovac in self._handles.values():
                try:
                    popisovac.flush()
                    popisovac.close()
                except OSError:
                    pass
            self._handles.clear()


class Summary:
    """Počty podle komponenta × metoda × result. Přežívají restart.

    Proč přežívají: čísla, která mizí při každém restartu, se nedají použít
    k hodnocení systému, a „měření je základ hodnocení úspěšnosti" je zásada,
    ne přání (README-MODULES.md § 11).

    Proč zvlášť počítá `malformed`: špatně tvarovaný záznam se přijímá, aby se
    neztratila stopa — ale rostoucí počet je chyba ve volajícím a musí být
    poznat bez čtení logu.
    """

    def __init__(self, *, path: str, started_at: str):
        """Vstup:
            path: kam se souhrn ukládá.
            started_at: od kdy se počítá, ISO 8601. Předává se zvenčí, aby
                šlo souhrn deterministicky otestovat.
        """
        self._path = Path(path)
        self._lock = threading.Lock()
        self._counts: dict[str, dict[str, int]] = {}
        self._malformed = 0
        self._no_trace = 0
        self._total = 0
        self._since = started_at
        self._load()

    def add(self, record: LogRecord) -> None:
        """Připočte záznam do souhrnu.

        Vstup:
            record: ověřený záznam.

        Při chybě:
            Nevyhazuje.
        """
        klic = f"{record.component}.{record.method}"
        with self._lock:
            radek = self._counts.setdefault(
                klic, {r.value: 0 for r in Result}
            )
            radek[record.result.value] += 1
            self._total += 1
            if record.malformed:
                self._malformed += 1
            if record.trace is None:
                # Rostoucí podíl znamená, že někde v systému někdo přestal
                # předávat parametr — je to měřitelná díra v řetězu doložení.
                self._no_trace += 1

    def snapshot(self) -> dict[str, Any]:
        """Vrátí souhrn jako JSON objekt.

        Výstup:
            Objekt s počty, od kdy se počítá a kolik záznamů nemá stopu.
            Klíč `by_method` je slovník `komponenta.metoda` → počty po výsledcích.
        """
        with self._lock:
            return {
                "format_version": SUMMARY_FORMAT_VERSION,
                "since": self._since,
                "total": self._total,
                "malformed": self._malformed,
                "without_trace": self._no_trace,
                "by_method": {k: dict(v) for k, v in sorted(self._counts.items())},
            }

    def flush(self) -> None:
        """Uloží souhrn na disk atomicky.

        Proč atomicky: přímý zápis do cílového souboru po pádu procesu zanechá
        poloviční JSON, který už nikdo nepřečte — a přišlo by se tím o celé
        měření, ne o poslední vteřinu.

        Při chybě:
            Nevyhazuje. Neuložený souhrn je ztráta čísel, ne důvod shodit
            službu, která jinak zapisuje.
        """
        data = self.snapshot()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            docasny = self._path.with_suffix(".json.tmp")
            docasny.write_text(
                json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            os.replace(docasny, self._path)
        except OSError:
            pass

    def reset(self, *, started_at: str) -> None:
        """Vynuluje souhrn. Volá se jen explicitně — samo se nevynuluje nikdy."""
        with self._lock:
            self._counts.clear()
            self._malformed = 0
            self._no_trace = 0
            self._total = 0
            self._since = started_at
        self.flush()

    def _load(self) -> None:
        """Načte uložený souhrn, pokud existuje a je čitelný.

        Při chybě:
            Nevyhazuje — začne od nuly. Ale u nesouhlasné verze formátu se
            **nezačíná od nuly tiše**: to by vypadalo jako čerstvý start,
            zatímco data existují. Proto se soubor odsune stranou.
        """
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        if data.get("format_version") != SUMMARY_FORMAT_VERSION:
            try:
                self._path.rename(
                    self._path.with_suffix(f".v{data.get('format_version')}.json")
                )
            except OSError:
                pass
            return
        self._counts = {
            k: {r.value: int(v.get(r.value, 0)) for r in Result}
            for k, v in data.get("by_method", {}).items()
            if isinstance(v, dict)
        }
        self._total = int(data.get("total", 0))
        self._malformed = int(data.get("malformed", 0))
        self._no_trace = int(data.get("without_trace", 0))
        self._since = data.get("since", self._since)


class LoggerService:
    """Přijme dávku záznamů, uloží je, započítá a nabídne posledních N k sledování.

    Tohle je celá doménová logika logovátka. Nezná HTTP; `api.py` ji jen
    obaluje a `control.py` ji spouští.
    """

    def __init__(self, config: dict[str, Any], *, started_at: str | None = None):
        """Vstup:
            config: ověřená konfigurace z `config.load()`.
            started_at: čas startu v ISO 8601. `None` znamená teď — používá se
                v provozu; testy si ho předávají, aby byly deterministické.
        """
        self._config = config
        self._started_at = started_at or now_iso()
        modul = config["module"]

        self._routing = modul["routing"]
        self._writer = Writer(
            rotate_max_bytes=modul["storage"]["rotate_max_bytes"],
            retention_days=modul["storage"]["retention_days"],
        )
        self._summary = Summary(
            path=modul["summary"]["path"], started_at=self._started_at
        )
        # Kruhový buffer pro nově připojený prohlížeč, aby okno nebylo prázdné,
        # dokud něco nepřiteče. Server ho drží jednou za celý systém.
        self._recent: deque[dict[str, Any]] = deque(
            maxlen=modul["watch"]["buffer_records"]
        )
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._subscribers_lock = threading.Lock()
        self._last_error: str | None = None

        # Objektový proud je vedený zvlášť od textového. Objekt je jiný druh
        # záznamu: čte se jiným kukátkem, roste jinou rychlostí a mísit obojí
        # v jednom souboru znamená, že se ani jedno nedá číst.
        self._objects_cfg = modul["objects"]
        self._objects_recent: deque[dict[str, Any]] = deque(
            maxlen=modul["watch"]["buffer_records"]
        )
        self._objects_subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._objects_total = 0
        self._objects_truncated = 0

    def accept(self, records: Any, *, received_ts: str) -> dict[str, Any]:
        """Přijme dávku záznamů z drátu, uloží je a započítá.

        Proč nikdy neodmítne kvůli obsahu: záznam se posílá právě tehdy, když
        se něco děje. Špatně tvarovaný se uloží označený (`malformed`), ne
        zahodí — chybějící záznam není nic, kdežto označený je informace.

        Vstup:
            records: seznam záznamů z drátu. Cokoli, co není seznam, se počítá
                jako chyba tvaru požadavku a ohlásí se návratovou hodnotou.
            received_ts: čas přijetí v ISO 8601. Předává se zvenčí, aby šla
                funkce deterministicky otestovat.

        Výstup:
            Objekt s počty: `accepted` kolik se uložilo, `malformed` kolik
            z toho bylo označených. Klíč `error` je tam jen tehdy, když byl
            špatně tvar celé dávky.

        Při chybě:
            `OSError` propustí dál, když se nedá zapisovat na disk. Ztráta
            zápisu se nesmí stát tiše.
        """
        if not isinstance(records, list):
            return {
                "accepted": 0,
                "malformed": 0,
                "error": "records musí být pole",
            }

        zaznamy = [from_wire(r, received_ts=received_ts) for r in records]
        k_zapisu = [(route(z, self._routing), z) for z in zaznamy]

        self._writer.write(k_zapisu)

        spatnych = 0
        for zaznam in zaznamy:
            self._summary.add(zaznam)
            if zaznam.malformed:
                spatnych += 1
            self._publish(zaznam.to_json_object())

        return {"accepted": len(zaznamy), "malformed": spatnych}

    def accept_objects(self, records: Any, *, received_ts: str) -> dict[str, Any]:
        """Přijme dávku JSON objektů k zalogování.

        Druhý druh logu vedle textového (viz `objects.py`). Textový záznam
        odpovídá na otázku *co se stalo*, objektový na otázku *jak vypadala
        data* — pole po sítku, koš atomů, matice šablon. Zploštit takovou
        strukturu do řetězce znamená přijít o to, kvůli čemu se na ni člověk
        dívá.

        Objekt přes strop velikosti nebo hloubky se uloží **oříznutý
        a označený, ne zahozený** — chybějící záznam není nic.

        Vstup:
            records: seznam objektových záznamů z drátu.
            received_ts: čas přijetí v ISO 8601, předaný zvenčí.

        Výstup:
            Objekt s počty: `accepted`, `malformed` a `truncated`. Klíč `error`
            je tam jen tehdy, když byl špatně tvar celé dávky.

        Při chybě:
            `OSError` propustí dál, když se nedá zapisovat na disk.
        """
        if not isinstance(records, list):
            return {"accepted": 0, "malformed": 0, "truncated": 0,
                    "error": "objects musí být pole"}

        zaznamy = [
            objects_mod.from_wire(
                r,
                received_ts=received_ts,
                max_object_bytes=self._objects_cfg["max_object_bytes"],
                max_depth=self._objects_cfg["max_depth"],
            )
            for r in records
        ]

        proud = self._objects_cfg["stream"]
        self._writer.write_objects([(proud, z) for z in zaznamy])

        spatnych = zkracenych = 0
        for zaznam in zaznamy:
            self._objects_total += 1
            if zaznam.malformed:
                spatnych += 1
            if zaznam.truncated or zaznam.depth_limited:
                zkracenych += 1
                self._objects_truncated += 1
            self._publish_object(zaznam.to_json_object())

        return {"accepted": len(zaznamy), "malformed": spatnych,
                "truncated": zkracenych}

    def _publish_object(self, objekt: dict[str, Any]) -> None:
        """Uloží objekt do kruhového bufferu a rozešle ho kukátku na objekty."""
        self._objects_recent.append(objekt)
        with self._subscribers_lock:
            odberatele = list(self._objects_subscribers)
        for poslat in odberatele:
            try:
                poslat(objekt)
            except Exception:
                self.unsubscribe_objects(poslat)

    def subscribe_objects(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Přihlásí odběratele objektového proudu (okno kukátka na objekty)."""
        with self._subscribers_lock:
            self._objects_subscribers.append(callback)

    def unsubscribe_objects(
        self, callback: Callable[[dict[str, Any]], None]
    ) -> None:
        """Odhlásí odběratele objektového proudu."""
        with self._subscribers_lock:
            if callback in self._objects_subscribers:
                self._objects_subscribers.remove(callback)

    def recent_objects(self) -> list[dict[str, Any]]:
        """Vrátí poslední objekty pro nově připojené kukátko."""
        return list(self._objects_recent)

    def _publish(self, objekt: dict[str, Any]) -> None:
        """Uloží záznam do kruhového bufferu a rozešle ho odběratelům.

        Odběratelé jsou otevřené prohlížeče na sledovací stránce. Selhání
        jednoho z nich (zavřená záložka) nesmí ovlivnit zápis ani ostatní.

        Při chybě:
            Nevyhazuje. Odběratel, který spadne, se odhlásí.
        """
        self._recent.append(objekt)
        with self._subscribers_lock:
            odberatele = list(self._subscribers)
        for poslat in odberatele:
            try:
                poslat(objekt)
            except Exception:
                self.unsubscribe(poslat)

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Přihlásí odběratele živého proudu (jedno okno prohlížeče)."""
        with self._subscribers_lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Odhlásí odběratele. Volá se při zavření okna i po jeho selhání."""
        with self._subscribers_lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def recent(self) -> list[dict[str, Any]]:
        """Vrátí posledních N záznamů pro nově připojený prohlížeč."""
        return list(self._recent)

    def summary(self) -> dict[str, Any]:
        """Vrátí souhrn počtů — základ měření modulu."""
        return self._summary.snapshot()

    def reset_summary(self) -> dict[str, Any]:
        """Vynuluje souhrn a vrátí nový stav."""
        self._summary.reset(started_at=now_iso())
        return self._summary.snapshot()

    def health(self) -> dict[str, Any]:
        """Vrátí stav služby pro `GET /v1/health` a pro `status`.

        Výstup:
            Objekt se stavem, dobou běhu, poslední chybou a s tím, které části
            jsou zapnuté. Vypnutá funkcionalita je vidět schválně — systém
            s vypnutou částí není tentýž systém a měření to musí vědět.
        """
        souhrn = self._summary.snapshot()
        return {
            "status": "ok",
            "started_at": self._started_at,
            "last_error": self._last_error,
            "records_total": souhrn["total"],
            "records_malformed": souhrn["malformed"],
            "objects_total": self._objects_total,
            "objects_truncated": self._objects_truncated,
            "enabled": {
                "watch": self._config["module"]["watch"]["enabled"],
                "routing_rules": len(self._routing.get("rules", [])),
            },
            "storage": {
                "default_stream": self._routing["default"],
                "retention_days": self._config["module"]["storage"][
                    "retention_days"
                ],
            },
        }

    def note_error(self, message: str) -> None:
        """Zapamatuje si poslední chybu, aby ji `health()` uměl ohlásit."""
        self._last_error = message

    def flush(self) -> None:
        """Uloží souhrn a vyprázdní zápisy. Volá se pravidelně i při ukončení."""
        self._summary.flush()

    def close(self) -> None:
        """Uklidí popisovače a uloží souhrn. Volá se explicitně při ukončení."""
        self._summary.flush()
        self._writer.close()
