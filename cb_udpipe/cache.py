"""Trvalá cache rozborů: JSONL na disku, index klíč → offset v paměti.

Cache není jen zrychlení. Je to **rostoucí sbírka rozebraných českých vět se
svým zdrojem** — tedy to, z čeho se dá jednou trénovat vlastní model. Ten druhý
odběratel rozhoduje o tvaru: ukládá se všech deset sloupců a klíč nese model
i verzi tokenizéru, aby šlo poznat, čím rozbor vznikl (koncepce, § 1 a § 4).

Proč JSONL a ne jeden JSON objekt: jde připisovat na konec. Jeden velký objekt
by se musel při každé nové větě přepsat celý; conBond2 měl obdobu
(`data/raw/_tokeny.json`) a při 70 MB to už bolelo.

Proč index a ne celá cache v paměti: 26 tisíc vět rozboru je desítky megabajtů.
V paměti jsou jen klíče, tokeny se čtou `seek`em až při zásahu.
"""

from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path
from typing import Any

from cb_udpipe.conllu import Multiword, Sentence, Token

#: Verze tvaru záznamu. Čtečka umí předchozí verzi, nebo řekne, že neumí —
#: nikdy nehádá (README-MODULES.md § 14).
CACHE_FORMAT_VERSION = 1

#: Klíče, bez kterých je záznam nečitelný. Chybějící klíč znamená poškozený
#: řádek, ne prázdný rozbor — a to se musí rozlišit, jinak by se ztráta dat
#: počítala jako platná věta bez tokenů.
REQUIRED_FIELDS = ("source", "model", "tokenizer", "tokens")


class Cache:
    """Cache rozborů jednoho modelu.

    Jeden soubor na model; verze tokenizéru je v záznamu. Obojí je součástí
    klíče, protože **rozbor bez nich není určený** — vrátit rozbor jiné
    tokenizace by byla tichá záměna dat (INV-9).

    Instance drží otevřený soubor pro zápis. Dvě instance nad týmž souborem
    znamenají ztrátu dat; brání tomu PID soubor služby jako zámek
    (README-MODULES.md § 8).
    """

    def __init__(self, *, directory: Path | str, model: str, tokenizer: str):
        """Vstup:
            directory: adresář cache. Založí se, když neexistuje — studený
                start není chyba.
            model: jméno modelu UDPipe. Určuje jméno souboru.
            tokenizer: otisk pravidel tokenizace (`tokenize.fingerprint`).
                Záznam s jiným otiskem se do indexu nezaloží.
        """
        self.model = model
        self.tokenizer = tokenizer
        self.path = Path(directory) / f"{model}.jsonl"
        self._index: dict[str, int] = {}
        self._corrupt = 0
        self._handle = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._build_index()

    def get(self, source: str) -> Sentence | None:
        """Vrátí rozbor věty z cache, nebo `None`.

        Proč `None` a ne výjimka: nezásah je nejčastější případ při prvním
        průchodu korpusem a výjimka by z něj udělala nejdražší cestu. Volající
        pak větu pošle k rozboru — je to normální stav, ne chyba.

        Vstup:
            source: text věty. Normalizuje se na NFC, totéž co dělá sám
                server, takže rozložené `ě` trefí tutéž větu jako složené.

        Výstup:
            `Sentence`, nebo `None`, když v cache není.

        Při chybě:
            Nevyhazuje. Poškozený řádek se počítá do `stats()["corrupt"]`
            a vrátí se `None` — ztráta jednoho rozboru nesmí shodit dávku.
        """
        offset = self._index.get(_klic(source))
        if offset is None:
            return None
        try:
            with self.path.open("r", encoding="utf-8") as f:
                f.seek(offset)
                radek = f.readline()
        except OSError:
            return None
        veta = _ze_zaznamu(radek, model=self.model, tokenizer=self.tokenizer)
        if veta is None:
            self._corrupt += 1
        return veta

    def put(self, sentence: Sentence, *, ts: str) -> None:
        """Zapíše rozbor do cache.

        Zápis je **připsání na konec** plus `fsync`. Atomický zápis přes
        dočasný soubor a `os.replace` (README-MODULES.md § 8) tu použít nejde —
        to je celý soubor, ne řádek. Pojistka je jinde: po pádu procesu je
        rozbitý nejvýš poslední řádek a ten se při startu přeskočí.

        Vstup:
            sentence: rozebraná věta.
            ts: čas v ISO 8601. Předává se zvenčí, aby šla funkce
                deterministicky otestovat (README-MODULES.md § 3).

        Výstup:
            Nic.

        Při chybě:
            `OSError`, když se nedá zapsat. Nepolyká se: cache, která tiše
            nezapisuje, vypadá jako cache, která nemá zásahy — a to je přesně
            ta tichá vada, kterou má měření chytat.
        """
        zaznam = {
            "source": sentence.source,
            "model": self.model,
            "tokenizer": self.tokenizer,
            "sent_id": sentence.sent_id,
            "tokens": [_token_na_json(t) for t in sentence.tokens],
            "multiword": [_multiword_na_json(m) for m in sentence.multiword],
            "ts": ts,
            "format_version": CACHE_FORMAT_VERSION,
        }
        radek = json.dumps(zaznam, ensure_ascii=False) + "\n"

        f = self._open()
        offset = f.tell()
        f.write(radek)
        f.flush()
        os.fsync(f.fileno())
        self._index[_klic(sentence.source)] = offset

    def stats(self) -> dict[str, Any]:
        """Vrátí počty pro `GET /v1/cache/stats` a pro měření.

        Výstup:
            Slovník s počtem vět v indexu, počtem poškozených řádků,
            velikostí souboru a s tím, kterého modelu a tokenizéru se cache
            týká. `corrupt` roste tiše jen v tom smyslu, že nevyhazuje —
            v souhrnu je vidět.

        Při chybě:
            Nevyhazuje. Chybějící soubor znamená nulovou velikost.
        """
        try:
            velikost = self.path.stat().st_size
        except OSError:
            velikost = 0
        return {
            "sentences": len(self._index),
            "corrupt": self._corrupt,
            "bytes": velikost,
            "model": self.model,
            "tokenizer": self.tokenizer,
            "format_version": CACHE_FORMAT_VERSION,
            "path": str(self.path),
        }

    def close(self) -> None:
        """Zavře soubor. Volá se explicitně při ukončení služby."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def _open(self):
        """Vrátí otevřený soubor pro připisování; otevře ho při první potřebě.

        Proč líně: služba, která jen čte, nemá důvod držet soubor otevřený pro
        zápis — a při studeném startu by ho tím založila prázdný.
        """
        if self._handle is None:
            self._handle = self.path.open("a", encoding="utf-8")
        return self._handle

    def _build_index(self) -> None:
        """Postaví index klíč → offset přečtením souboru.

        Proč se čte celý soubor při startu: bez indexu je cache po restartu
        prázdná, i když data má. Čtou se jen klíče, ne rozbory — v paměti tak
        zůstanou desítky bajtů na větu místo desítek kilobajtů.

        Záznam s **jiným otiskem tokenizéru** se do indexu nezaloží. Zůstane
        ale v souboru: změna pravidel cache neznehodnotí, staré záznamy jsou
        platné pro svou verzi (koncepce, § 4).

        Při chybě:
            Nevyhazuje. Chybějící soubor je prázdná cache, poškozený řádek se
            přeskočí a započítá.
        """
        if not self.path.exists():
            return
        try:
            with self.path.open("rb") as f:
                offset = 0
                for syrovy in f:
                    delka = len(syrovy)
                    self._zaznamenej(syrovy, offset)
                    offset += delka
        except OSError:
            # Nečitelný soubor znamená prázdnou cache, ne pád služby. Že se
            # nečte, je vidět v `stats()` jako nulový počet vět.
            return

    def _zaznamenej(self, syrovy: bytes, offset: int) -> None:
        """Zapíše jeden řádek do indexu, nebo ho započítá jako poškozený."""
        try:
            zaznam = json.loads(syrovy.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._corrupt += 1
            return
        if not isinstance(zaznam, dict):
            self._corrupt += 1
            return
        if any(k not in zaznam for k in REQUIRED_FIELDS):
            self._corrupt += 1
            return
        if zaznam.get("tokenizer") != self.tokenizer:
            return          # jiná verze pravidel — platný záznam, jiný klíč
        if zaznam.get("format_version") != CACHE_FORMAT_VERSION:
            self._corrupt += 1
            return
        self._index[_klic(zaznam["source"])] = offset


def _klic(source: str) -> str:
    """Normalizuje text věty na klíč cache.

    Jen NFC, totéž co dělá sám server (`unicodedata.normalize("NFC", …)`).
    Nic víc: srovnávat velikost písmen nebo mezery by znamenalo vracet rozbor
    jiné věty, než o kterou se volající ptal (koncepce, § 4).
    """
    return unicodedata.normalize("NFC", source)


def _ze_zaznamu(radek: str, *, model: str, tokenizer: str) -> Sentence | None:
    """Přečte větu z jednoho řádku cache.

    Vstup:
        radek: řádek JSONL.
        model: očekávaný model.
        tokenizer: očekávaný otisk pravidel.

    Výstup:
        `Sentence`, nebo `None` u poškozeného či neodpovídajícího záznamu.

    Při chybě:
        Nevyhazuje.
    """
    try:
        zaznam = json.loads(radek)
    except json.JSONDecodeError:
        return None
    if not isinstance(zaznam, dict):
        return None
    if any(k not in zaznam for k in REQUIRED_FIELDS):
        return None
    if zaznam["model"] != model or zaznam["tokenizer"] != tokenizer:
        return None
    try:
        return Sentence(
            source=zaznam["source"],
            tokens=tuple(_token_z_json(t) for t in zaznam["tokens"]),
            multiword=tuple(_multiword_z_json(m)
                            for m in zaznam.get("multiword", [])),
            sent_id=zaznam.get("sent_id"),
        )
    except (TypeError, KeyError, ValueError):
        return None


def _token_na_json(t: Token) -> dict[str, Any]:
    """Převede token na JSON objekt. Prázdné sloupce se vynechávají — v logu
    i v cache jsou prázdné klíče šum, který zakrývá to podstatné."""
    o: dict[str, Any] = {"id": t.id, "form": t.form}
    for jmeno in ("lemma", "upos", "xpos", "head", "deprel", "deps"):
        hodnota = getattr(t, jmeno)
        if hodnota is not None:
            o[jmeno] = hodnota
    if t.feats:
        o["feats"] = t.feats
    if t.misc:
        o["misc"] = t.misc
    return o


def _token_z_json(o: dict[str, Any]) -> Token:
    """Postaví token z JSON objektu; chybějící sloupce jsou `None`."""
    return Token(
        id=o["id"], form=o["form"], lemma=o.get("lemma"), upos=o.get("upos"),
        xpos=o.get("xpos"), feats=o.get("feats"), head=o.get("head"),
        deprel=o.get("deprel"), deps=o.get("deps"), misc=o.get("misc"),
    )


def _multiword_na_json(m: Multiword) -> dict[str, Any]:
    """Převede víceslovný tvar na JSON objekt."""
    o: dict[str, Any] = {"id": list(m.id), "form": m.form}
    if m.misc:
        o["misc"] = m.misc
    return o


def _multiword_z_json(o: dict[str, Any]) -> Multiword:
    """Postaví víceslovný tvar z JSON objektu."""
    return Multiword(id=(o["id"][0], o["id"][1]), form=o["form"],
                     misc=o.get("misc"))
