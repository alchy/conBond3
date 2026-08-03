"""Klient logovátka — to, co si ostatní moduly importují.

`import cb_logger` dá volajícímu `LogClient` a ten už REST volání obsahuje.
Kdo logovátko používá, nepíše žádný HTTP kód, nesestavuje URL a nerozbaluje
JSON — zavolá metodu (README-MODULES.md § 1).

Dvě věci odlišují tenhle klient od klientů ostatních modulů:

* **Nikdy nikoho neshodí.** Logovátko je nepovinná závislost. Když neběží,
  klient to ohlásí na chybový výstup, přepne se do spool režimu a pokračuje.
  Kdyby padlé logovátko shodilo systém, byla by nejméně důležitá součást
  zároveň nejkřehčí (README-MODULES.md § 9).
* **Neloguje svá vlastní volání.** Zacyklil by se. Je to jediná výjimka
  z pravidla, že wrapper loguje sám za sebe.

Zápis je asynchronní schválně. Debug úroveň vyrobí na plném korpusu statisíce
záznamů; synchronní HTTP volání na každý z nich by udělalo z nejcennější
úrovně logu nepoužitelnou a někdo by ji vypnul.
"""

from __future__ import annotations

import atexit
import json
import queue
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from cb_logger.record import Level, Result
from cb_logger.service import now_iso

#: Strop fronty v paměti. Při přetečení se zahazují **nejstarší** záznamy
#: a zapíše se o tom jeden záznam s počtem zahozených. Tiché přetečení by
#: udělalo z logu nespolehlivý zdroj, aniž by to bylo vidět.
QUEUE_LIMIT = 20_000

#: Poslední záchrana, když se nedá přečíst ani konfigurace logovátka. Odpovídá
#: základnímu portu rozsahu cb-logger (README-MODULES.md § 5).
FALLBACK_ENDPOINT = "http://127.0.0.1:42100"


def default_endpoint() -> tuple[str, str]:
    """Zjistí, kde logovátko běží, a řekne, odkud to ví.

    Proč to není magie, ale čtení: adresu služby **deklaruje sama služba** ve
    své konfiguraci, a když běží, zapisuje si skutečně přidělený port do
    `run/service.port`. Tahle funkce jen přečte totéž, co čte `status`. Není
    to hledání služby po síti ani hádání — je to dotaz na jediné místo, které
    odpověď zná.

    Explicitně předaný `endpoint` má vždycky přednost. Tohle je jen výchozí
    hodnota pro případ, kdy volající žádnou nemá — typicky konzole nebo modul,
    který mluví s logovátkem u sebe doma. Modul, který má v konfiguraci vlastní
    `logging.endpoint`, si ho předá a sem se nedostane.

    Pořadí je od nejjistějšího k nejobecnějšímu:

    1. `run/service.port` — skutečný port běžící služby. Podstatné, když je
       v konfiguraci nula a port přidělil systém.
    2. `service.port` z konfigurace — zamýšlený port.
    3. `FALLBACK_ENDPOINT` — když se nedá přečíst ani konfigurace.

    Výstup:
        Dvojice (adresa, odkud se vzala). Druhá položka se ukládá do
        `stats()`, aby šlo poznat, se kterou službou klient vlastně mluví —
        bez toho by se ladila jedna instance a běžela druhá.

    Při chybě:
        Nevyhazuje. Nečitelná konfigurace není důvod, aby program nemohl
        logovat; skončí to na `FALLBACK_ENDPOINT`.
    """
    from cb_logger.config import DEFAULT_CONFIG_PATH

    host, port = "127.0.0.1", None
    try:
        syrova = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        host = syrova["service"]["host"]
        port = syrova["service"]["port"]
        port_file = DEFAULT_CONFIG_PATH.parent / syrova["runtime"]["port_file"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return FALLBACK_ENDPOINT, "zabudovaná výchozí hodnota"

    try:
        skutecny = int(port_file.read_text().strip())
        if skutecny > 0:
            return f"http://{host}:{skutecny}", "run/service.port (běžící služba)"
    except (OSError, ValueError):
        pass

    if isinstance(port, int) and port > 0:
        return f"http://{host}:{port}", "cb-logger-config.json"
    return FALLBACK_ENDPOINT, "zabudovaná výchozí hodnota"


class ServiceUnavailable(Exception):
    """Služba neodpovídá.

    U logovátka se **nevyhazuje** — je to nepovinná závislost a její výpadek
    znamená degradaci. Typ je tady proto, že ho potřebují klienti ostatních
    modulů, kde povinná závislost typovanou chybu vyhodit musí.
    """


class IncompatibleApi(Exception):
    """Služba běží, ale neumí verzi rozhraní, kterou klient chce."""


def _hlaska_nedostupna(endpoint: str, duvod: str) -> str:
    """Sestaví hlášku o nedostupné službě.

    Hláška má povinně tři věci: **který modul**, **na jaké adrese** ho klient
    hledal a **čím ho spustit**. Bez toho třetího si každý musí pamatovat jméno
    ovládacího programu, a to je přesně ta drobnost, kvůli které se místo
    spuštění služby hodinu hledá chyba v kódu.
    """
    return (
        f"modul cb-logger neodpovídá na {endpoint}/version ({duvod}).\n"
        f"Spusť ho: ./cb-logger.py start"
    )


class LogClient:
    """Zapisuje záznamy do logovátka. Dávkuje, nezdržuje, přežije výpadek.

    Vytváří se **jednou při startu**, ne v každé funkci — klient v cyklu
    znamená kontrolu služby v cyklu. Předává se pak parametrem tomu, kdo
    loguje (README-MODULES.md § 3).
    """

    def __init__(self, *, component: str, endpoint: str | None = None,
                 level: str | None = None, methods: tuple[str, ...] = (),
                 payload: str = "summary",
                 batch_size: int = 200, flush_interval_ms: int = 500,
                 spool_dir: str | Path | None = None,
                 timeout_s: float = 2.0,
                 stderr: Any = None):
        """Vstup:
            component: jméno komponenty, pod kterým se záznamy objeví.
                Klient se představí jednou a dál se neopakuje.
            endpoint: adresa logovátka, například `http://127.0.0.1:42100`.
                **Nepovinná.** Když chybí, zjistí se z konfigurace logovátka
                a z `run/service.port` (viz `default_endpoint`) — adresu své
                služby deklaruje sama služba a nemá smysl ji opisovat.
                Modul, který mluví s jinou instancí, si ji předá a přebije tím
                výchozí hodnotu. Kde se vzala, je vidět ve `stats()`.
            level: **Nepovinná, a výchozí je posílat všechno.** Kdo ji
                nenastaví, o nic nepřijde — filtruje se až při výpisu
                v kukátku a v souhrnu, tedy na straně logovátka.
                Hodnota `"info"` je vědomé rozhodnutí ušetřit síť a disk:
                debug se pak zahodí už u volajícího a **nikdy nikam nedorazí**.
                Kolik se ho zahodilo, je vidět ve `stats()` jako
                `filtered_by_level`.
            methods: zúžení podrobné stopy na vyjmenované metody. Prázdné
                znamená celý modul. Tohle je jediný režim ladění, který jde
                nechat zapnutý na velkém provozu.
            payload: `summary` nebo `full`. Odděleně od `level` schválně —
                často je potřeba vidět víc záznamů, ne delší záznamy.
            batch_size, flush_interval_ms: kdy odejde dávka.
            spool_dir: kam se ukládají neodeslané záznamy. `None` je vypne,
                což se hodí testům; v provozu tím systém přijde o stopu.
            timeout_s: strop na jedno volání. Volání bez stropu není pomalé,
                je zamrzlé.
            stderr: kam jdou hlášky o nedostupnosti. `None` znamená
                `sys.stderr`; testy si sem podstrčí vlastní.
        """
        self.component = component
        if endpoint is None:
            self.endpoint, self.endpoint_source = default_endpoint()
        else:
            self.endpoint, self.endpoint_source = endpoint.rstrip("/"), "předáno"
        # `None` znamená posílat všechno. Zahodit záznam u zdroje je
        # nevratné — a vývojář, který zapomněl nastavit úroveň, by o data
        # přišel, aniž by se to kdekoli dozvěděl. Je to stejná úvaha jako
        # u špatně tvarovaných záznamů: chybějící záznam není nic.
        self.level = Level(level) if level is not None else None
        self.methods = frozenset(methods)
        self.payload = payload
        self._batch_size = batch_size
        self._flush_interval_s = flush_interval_ms / 1000.0
        self._timeout_s = timeout_s
        self._stderr = stderr if stderr is not None else sys.stderr

        self._spool = (Path(spool_dir) / f"{component}.jsonl"
                       if spool_dir else None)
        self._queue: queue.Queue = queue.Queue(maxsize=QUEUE_LIMIT)
        # Záznamy, které už nejsou ve frontě, ale ještě neodešly — odesílací
        # vlákno je drží v rozpracované dávce. Bez tohohle počitadla vypadá
        # fronta prázdně ve chvíli, kdy se ještě nic neodeslalo.
        self._inflight = 0
        self._inflight_lock = threading.Lock()
        self._dropped = 0
        # Záznamy zahozené kvůli úrovni, ještě u volajícího. Počítají se
        # schválně: zahodit potichu a nikde to neukázat je totéž jako lhát —
        # vývojář pak hledá chybu v logovátku, zatímco ji má v konfiguraci.
        self._filtered = 0
        self._undelivered = 0
        self._stop = threading.Event()
        self._lock = threading.Lock()

        self.available = False
        self.server_version: dict[str, Any] | None = None
        self._check_service()

        self._worker = threading.Thread(
            target=self._loop, name=f"cb-logger-{component}", daemon=True
        )
        self._worker.start()

        # Pojistka pro konec procesu. Odesílací vlákno je démon a odesílá po
        # dávkách; kdo skončí dřív než za `flush_interval_ms`, přišel by
        # o všechno, co zapsal.
        #
        # Naměřeno při stavbě: `log.info(...)` a konec skriptu = nula záznamů.
        # Bylo to sice popsané v příručce, ale past, kterou musí obcházet
        # každý volající, je chyba návrhu, ne vlastnost — a v modulu, který
        # spadne, by se ztratily právě ty poslední záznamy před pádem, tedy ty
        # nejcennější.
        #
        # `close()` zůstává jediná **řízená** cesta; tohle je záchranná síť pro
        # normální konec procesu. Při `kill -9` ani `os._exit()` se `atexit`
        # nespustí — proti tomu je spool a nic víc udělat nejde.
        self._atexit_hook = self._flush_at_exit
        atexit.register(self._atexit_hook)

    # ------------------------------------------------------------- zápis

    def info(self, *, method: str, result: Result | str,
             message: str | None = None,
             trace: str | None = None,
             input: dict[str, Any] | None = None,
             output: dict[str, Any] | None = None,
             duration_ms: int | None = None,
             version: dict[str, Any] | None = None) -> None:
        """Zapíše záznam úrovně `info` — hranici komponenty.

        Co z něj musí být jasné: která komponenta se volala, s jakým vstupem
        a s jakým výsledkem.

        **Všechny parametry se pojmenovávají**, `method` nevyjímaje. Je to
        kázeň zapsaná po chybě: dokud byl `method` poziční, skončila v něm
        hláška — `log.info(method="debug hlaska !", …)`. Takový zápis projde, ale
        rozbije měření: souhrn se počítá podle komponenta × metoda × result,
        takže každá hláška by byla vlastní řádek a čísla by ztratila smysl.
        S pojmenovaným parametrem to nejde napsat omylem.
        """
        self._enqueue(Level.INFO, method, result, message, trace, input,
                      output, duration_ms, version)

    def debug(self, *, method: str, result: Result | str,
              message: str | None = None,
              trace: str | None = None,
              input: dict[str, Any] | None = None,
              output: dict[str, Any] | None = None,
              duration_ms: int | None = None,
              version: dict[str, Any] | None = None) -> None:
        """Zapíše záznam úrovně `debug` — vnitřek funkce.

        Zahodí se hned tady, když je klient na úrovni `info` a metoda není
        ve výčtu `methods`. Neposlaný záznam nestojí nic; poslaný a zahozený
        na druhé straně stojí síť i disk.
        """
        self._enqueue(Level.DEBUG, method, result, message, trace, input,
                      output, duration_ms, version)

    def json(self, *, method: str, obj: Any, label: str | None = None,
             kind: str | None = None, trace: str | None = None) -> None:
        """Zaloguje celý JSON objekt — druhý druh logu.

        Textový záznam odpovídá na otázku *co se stalo*, tenhle na otázku
        *jak vypadala data*: pole po sítku, koš atomů, matice šablon.
        V kukátku se objekt vykresluje jako rozbalitelný strom.

        Vstup:
            method: metoda, ve které objekt vznikl.
            obj: cokoli serializovatelného do JSON.
            label: jméno, pod kterým se objekt v kukátku ukáže —
                „pole po sítku", „koš věty 4". Bez něj by šlo poznat jen
                komponentu a metodu, a to u modulu, který loguje tři různé
                struktury, nestačí.
            kind: volitelné zařazení pro filtrování; když chybí, použije se
                `label`.
            trace: stopa průchodu. Předává se, nikdy nevyrábí.

        Při chybě:
            Nevyhazuje. Objekt přes strop velikosti nebo hloubky ořízne až
            služba, a to označeně — sem se ořezávat nemá, protože klient neví,
            jaké stropy služba má.
        """
        zaznam = {
            "kind": "__object__",
            "payload": {
                "ts": now_iso(),
                "component": self.component,
                "method": method,
                "label": label or method,
                "object": obj,
                "trace": trace,
            },
        }
        if kind is not None:
            zaznam["payload"]["kind"] = kind
        self._put(zaznam)

    # ----------------------------------------------------------- ukončení

    def _pending(self) -> int:
        """Kolik záznamů ještě neodešlo — ve frontě i v rozpracované dávce.

        Proč nestačí `queue.qsize()`: odesílací vlákno si záznam vyzvedne
        během mikrosekund a drží ho v lokální dávce, dokud neproběhne HTTP.
        V tu chvíli je fronta prázdná, ale odesláno není nic — a kdo se řídí
        jen frontou, ukončí proces uprostřed odesílání.

        *(Naměřeno při stavbě: `log.info(...)` a konec skriptu ztrácely záznam
        nahodile, podle toho, jestli vlákno stihlo HTTP dokončit dřív, než
        interpret zmrazil vlákna.)*
        """
        with self._inflight_lock:
            return self._queue.qsize() + self._inflight

    def flush(self, timeout_s: float = 5.0) -> int:
        """Dopraví frontu do logovátka; vrátí počet neodeslaných záznamů.

        Proč vrací počet místo výjimky: volá se při ukončení procesu, kdy už
        výjimka nemá kam bublat. Neodeslané záznamy skončí ve spool souboru
        a odešlou se při dalším startu — ztratit se nesmí, protože debug stopa
        je jediný způsob, jak zpětně vysvětlit, jak artefakt vznikl.

        Vstup:
            timeout_s: kolik sekund čekat. Výchozích 5 s je stonásobná rezerva
                proti naměřené době odeslání dávky na místní smyčce a zároveň
                strop, který nezdrží ukončení procesu natolik, aby to někdo
                obešel `kill -9`.

        Výstup:
            Počet záznamů, které se nepodařilo odeslat. Nula znamená, že je
            fronta prázdná.

        Při chybě:
            Nevyhazuje.
        """
        konec = time.monotonic() + timeout_s
        while time.monotonic() < konec and self._pending() > 0:
            time.sleep(0.005)
        return self._pending() + self._undelivered

    def close(self, timeout_s: float = 5.0) -> int:
        """Dopraví zbytek fronty a zastaví vlákno. Volá se explicitně."""
        zbylo = self.flush(timeout_s)
        self._stop.set()
        self._worker.join(timeout=1.0)
        # Po řízeném ukončení už není co zachraňovat; registrovaná pojistka by
        # jen zdržela konec procesu o marné čekání na prázdnou frontu.
        try:
            atexit.unregister(self._atexit_hook)
        except Exception:
            pass
        return zbylo

    def _flush_at_exit(self) -> None:
        """Pojistka volaná při normálním konci procesu.

        Proč je oddělená od `close()`: `close()` je řízené ukončení, které
        volající udělá vědomě a chce znát počet neodeslaných. Tohle je záchranná
        síť pro toho, kdo na `close()` zapomněl — nesmí nic vyhodit ani vypsat,
        protože běží ve chvíli, kdy už proces končí a nikdo se nedívá.

        **Odesílá sám, nespoléhá na odesílací vlákno.** Při ukončování
        interpretu se nová vlákna spolehlivě nerozeběhnou a to stávající může
        být kdykoli zmrazeno — spoléhat se na ně by znamenalo pojistku, která
        drží jen někdy. *(Naměřeno: první pokus o tuhle pojistku volal
        `flush()`, ten si zakládal pomocné vlákno, a záznam se pořád ztrácel.)*

        Při chybě:
            Nevyhazuje nikdy. Co se nepodaří odeslat, `_send` uloží do spoolu.
        """
        try:
            # Nejdřív dát odesílacímu vláknu šanci dokončit, co má rozdělané.
            # Během `atexit` ještě běží; interpret ho zmrazí až potom.
            konec = time.monotonic() + 2.0
            while time.monotonic() < konec and self._pending() > 0:
                time.sleep(0.005)

            # Co i tak zbylo ve frontě, odešli sám — na vlákno už se spolehnout
            # nedá a druhá šance nebude.
            zbytek: list[dict[str, Any]] = []
            while True:
                try:
                    zbytek.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if zbytek:
                self._send(zbytek)
            self._stop.set()
        except Exception:
            pass

    def stats(self) -> dict[str, Any]:
        """Vrátí stav klienta pro `GET /v1/health` volajícího modulu."""
        return {
            "component": self.component,
            "endpoint": self.endpoint,
            # Odkud se adresa vzala. Bez toho se ladí jedna instance
            # a běží druhá.
            "endpoint_source": self.endpoint_source,
            "available": self.available,
            "level": self.level.value if self.level else "vše",
            "queued": self._pending(),
            # Zahozeno kvůli úrovni. Nenulové číslo u klienta, kterému nic
            # nechodí, je odpověď: debug se zahazuje, protože level je "info".
            "filtered_by_level": self._filtered,
            "dropped": self._dropped,
            "undelivered": self._undelivered,
            "spool": str(self._spool) if self._spool else None,
        }

    # ------------------------------------------------------------ vnitřek

    def _check_service(self) -> None:
        """Zeptá se služby na `/version` a podle výsledku nastaví dostupnost.

        Ptá se na `/version`, ne na `/v1/health`: je to bod bez závislostí,
        který odpoví, i když je služba jinak nezdravá — rozliší tedy „neběží"
        od „běží, ale něco jí chybí".

        Při chybě:
            Nevyhazuje. Napíše hlášku na chybový výstup a nechá `available`
            na `False`; zápis pak jde do spoolu.
        """
        try:
            with urllib.request.urlopen(
                f"{self.endpoint}/version", timeout=self._timeout_s
            ) as odpoved:
                self.server_version = json.loads(odpoved.read() or b"{}")
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            print(_hlaska_nedostupna(self.endpoint, str(e)), file=self._stderr)
            return

        umi = (self.server_version or {}).get("api", [])
        if "v1" not in umi:
            print(
                f"modul cb-logger na {self.endpoint} obsluhuje {umi}, "
                f"klient potřebuje v1.",
                file=self._stderr,
            )
            return
        self.available = True

    def _enqueue(self, level: Level, method: str, result: Result | str,
                 message: str | None, trace: str | None, input: dict | None,
                 output: dict | None, duration_ms: int | None,
                 version: dict | None) -> None:
        """Sestaví textový záznam a vloží ho do fronty."""
        if level is Level.DEBUG and self.level is Level.INFO \
                and method not in self.methods:
            # Sem se dojde jen tehdy, když si volající úroveň `info` vědomě
            # nastavil. Bez nastavení se posílá všechno.
            self._filtered += 1
            return

        zaznam: dict[str, Any] = {
            "ts": now_iso(),
            "level": level.value,
            "component": self.component,
            "method": method,
            "result": result.value if isinstance(result, Result) else result,
        }
        if message is not None:
            zaznam["message"] = message
        if trace is not None:
            zaznam["trace"] = trace
        if input is not None:
            zaznam["input"] = input
        if output is not None:
            zaznam["output"] = output
        if duration_ms is not None:
            zaznam["duration_ms"] = duration_ms
        if version is not None:
            zaznam["version"] = version

        self._put({"kind": "__record__", "payload": zaznam})

    def _put(self, polozka: dict[str, Any]) -> None:
        """Vloží položku do fronty; při přetečení zahodí nejstarší.

        Tiché přetečení by udělalo z logu nespolehlivý zdroj, aniž by to bylo
        vidět — proto se počítá a počet se objeví ve `stats()`.
        """
        try:
            self._queue.put_nowait(polozka)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._dropped += 1
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(polozka)
            except queue.Full:
                self._dropped += 1

    def _loop(self) -> None:
        """Vlákno na pozadí: sbírá dávku a odesílá ji.

        Nikdy nevyhazuje ven — výjimka ve vlákně by ho tiše ukončila a záznamy
        by se přestaly odesílat, aniž by si toho kdokoli všiml.
        """
        while not self._stop.is_set():
            davka = self._collect()
            if not davka:
                continue
            try:
                self._send(davka)
            except Exception:  # noqa: BLE001 — vlákno nesmí zemřít
                self._spool_write(davka)
            finally:
                with self._inflight_lock:
                    self._inflight -= len(davka)

    def _collect(self) -> list[dict[str, Any]]:
        """Posbírá dávku z fronty, nejdéle po `flush_interval_s`."""
        davka: list[dict[str, Any]] = []
        try:
            davka.append(self._queue.get(timeout=self._flush_interval_s))
        except queue.Empty:
            return davka
        while len(davka) < self._batch_size:
            try:
                davka.append(self._queue.get_nowait())
            except queue.Empty:
                break
        # Zvednout hned po vyzvednutí z fronty: mezi `get` a tímhle řádkem
        # nesmí být okno, ve kterém záznam není ani ve frontě, ani započítaný.
        with self._inflight_lock:
            self._inflight += len(davka)
        return davka

    def _send(self, davka: list[dict[str, Any]]) -> None:
        """Odešle dávku; textové a objektové záznamy jdou na vlastní cesty."""
        zaznamy = [p["payload"] for p in davka if p["kind"] == "__record__"]
        objekty = [p["payload"] for p in davka if p["kind"] == "__object__"]

        podarilo_se = True
        if zaznamy:
            podarilo_se &= self._post("/v1/records", {"records": zaznamy})
        if objekty:
            podarilo_se &= self._post("/v1/objects", {"objects": objekty})

        if podarilo_se:
            if not self.available:
                # Služba se vrátila. Doposlat, co leží ve spoolu — neodeslané
                # záznamy se nezahazují.
                self.available = True
                self._spool_resend()
        else:
            self.available = False
            self._spool_write(davka)

    def _post(self, cesta: str, telo: dict[str, Any]) -> bool:
        """Pošle objekt na cestu; vrátí `True`, když se to povedlo."""
        data = json.dumps(telo, ensure_ascii=False).encode("utf-8")
        pozadavek = urllib.request.Request(
            self.endpoint + cesta, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(pozadavek, timeout=self._timeout_s) as o:
                o.read()
            return True
        except (urllib.error.URLError, OSError):
            return False

    def _spool_write(self, davka: list[dict[str, Any]]) -> None:
        """Uloží neodeslanou dávku na disk.

        Při chybě:
            Nevyhazuje. Když nejde zapsat ani spool, záznamy se ztratí — ale
            spočítají se v `undelivered`, takže o tom je vidět.
        """
        if self._spool is None:
            self._undelivered += len(davka)
            return
        try:
            with self._lock:
                self._spool.parent.mkdir(parents=True, exist_ok=True)
                with open(self._spool, "a", encoding="utf-8") as f:
                    for polozka in davka:
                        f.write(json.dumps(polozka, ensure_ascii=False) + "\n")
        except OSError:
            self._undelivered += len(davka)

    def _spool_resend(self) -> None:
        """Odešle, co leží ve spoolu, a soubor uklidí.

        Při chybě:
            Nevyhazuje. Když odeslání znovu selže, soubor zůstane a zkusí se
            při příští příležitosti — ztratit se nesmí.
        """
        if self._spool is None or not self._spool.exists():
            return
        try:
            with self._lock:
                radky = self._spool.read_text(encoding="utf-8").splitlines()
        except OSError:
            return

        davka: list[dict[str, Any]] = []
        for radek in radky:
            try:
                davka.append(json.loads(radek))
            except json.JSONDecodeError:
                continue
        if not davka:
            return

        zaznamy = [p["payload"] for p in davka if p.get("kind") == "__record__"]
        objekty = [p["payload"] for p in davka if p.get("kind") == "__object__"]
        ok = True
        if zaznamy:
            ok &= self._post("/v1/records", {"records": zaznamy})
        if objekty:
            ok &= self._post("/v1/objects", {"objects": objekty})
        if ok:
            try:
                with self._lock:
                    self._spool.unlink()
            except OSError:
                pass


def from_config(config: dict[str, Any], *, component: str) -> LogClient:
    """Postaví klienta z bloku `logging` konfigurace volajícího modulu.

    Proč to existuje: každý modul by jinak opisoval těch osm parametrů a při
    první změně by se opisy rozešly.

    Vstup:
        config: ověřená konfigurace volajícího modulu; čte se z ní `logging`.
        component: jméno komponenty.

    Výstup:
        Připravený `LogClient`.
    """
    log = config.get("logging", {})
    return LogClient(
        component=component,
        # Chybějící endpoint se nedoplňuje konstantou, ale zjistí se
        # z konfigurace logovátka (viz `default_endpoint`).
        endpoint=log.get("endpoint"),
        # Chybějící úroveň znamená posílat všechno, ne `info` — kdo ji
        # nenastavil, si nevybral, a nevybráním se nemá přicházet o data.
        level=log.get("level"),
        methods=tuple(log.get("methods", ())),
        payload=log.get("payload", "summary"),
        batch_size=log.get("batch_size", 200),
        flush_interval_ms=log.get("flush_interval_ms", 500),
        spool_dir=log.get("spool_dir"),
    )
