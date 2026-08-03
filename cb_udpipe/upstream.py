"""Klient UDPipe 2 serveru — jediné místo v modulu, které s ním mluví.

Vrací **syrový CoNLL-U**; rozbor na tokeny dělá `conllu.parse`. Rozdělení je
záměrné: tenhle modul se stará o síť a o tvar požadavku, a právě na tvaru
požadavku stojí rozdíl mezi levným a drahým voláním.

`udpipe2_server.py` má v `predict()` podmínku:

    if tag or parse:
        self._network.load()
        …compute_embeddings…

Požadavek jen s `tokenizer` a **bez** `tagger`/`parser` tedy síť vůbec nenačte
a embeddingy nepočítá — je to čistý C++ tokenizér z UDPipe 1. Naopak požadavek
**bez** `tokenizer` čte vstup jako CoNLL-U, takže segmentace i tokenizace jsou
dané vstupem a server je nemůže změnit (koncepce, § 2).
"""

from __future__ import annotations

import json
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

#: Cesta, na kterou UDPipe 2 přijímá rozbor. Neverzovaná — je to cizí
#: rozhraní, ne naše.
PROCESS_PATH = "/process"

#: Cesta, na které server hlásí načtené modely. Používá ji `control.py`
#: k čekání na start a `service.health()` ke zjištění dostupnosti.
MODELS_PATH = "/models"

#: Text, kterým server hlásí větu delší než jeho mez. Rozlišuje se, protože
#: volající na to reaguje jinak než na obecnou chybu: větu přeskočí s důvodem
#: a zbytek dávky pošle dál.
TOO_LONG_MARKER = "longer than 1000 words"


class UpstreamUnavailable(Exception):
    """UDPipe neodpovídá.

    Je to **povinná** závislost, takže se vyhazuje (README-MODULES.md § 9).
    Nikdy se nevrací prázdný výsledek — ten by se slil s platným prázdným
    rozborem a měření by odměnilo právě tu chybu, kterou má chytat.
    """


class UpstreamError(Exception):
    """UDPipe odpověděl, ale ne tak, jak se čeká."""


class SentenceTooLong(UpstreamError):
    """Věta přesáhla mez serveru (1000 slov).

    Vlastní typ, aby ji volající mohl přeskočit s důvodem místo toho, aby
    kvůli jedné větě zahodil celou dávku.
    """


class Upstream:
    """Klient vlastní instance UDPipe 2.

    Vytváří se **jednou při startu** a předává parametrem tomu, kdo ho volá
    (README-MODULES.md § 3). Klient v cyklu znamená navazování spojení v cyklu.
    """

    def __init__(self, *, endpoint: str, timeout_s: float, log: Any = None,
                 launcher: str = "./cb-udpipe.py start"):
        """Vstup:
            endpoint: adresa serveru, například `http://127.0.0.1:42201`.
                Předává se z konfigurace; modul se nikoho neptá, kde služba
                běží (README-MODULES.md § 4).
            timeout_s: strop na jedno volání. Volání bez stropu není pomalé,
                je zamrzlé — a zamrzlá služba se hledá hůř než spadlá.
            log: `LogClient`, nebo `None`. Logovátko je nepovinná závislost,
                takže `None` je platný stav, ne chyba.
            launcher: příkaz, kterým se služba spouští. Je součástí chybové
                hlášky; bez něj si musí každý pamatovat jméno ovládacího
                programu, a to je přesně ta drobnost, kvůli které se místo
                spuštění služby hodinu hledá chyba v kódu.
        """
        self.endpoint = endpoint.rstrip("/")
        self.timeout_s = timeout_s
        self.log = log
        self.launcher = launcher

    def tokenize(self, text: str, *, trace: str | None = None) -> str:
        """Fáze 1: segmentace a hrubá tokenizace, bez tagů.

        Posílá **jen** `tokenizer`. Bez `tagger` a `parser` server nenačte síť
        ani nespočítá embeddingy, takže je to volání řádově levnější než plný
        rozbor (viz docstring modulu).

        Vstup:
            text: syrový text, jedna nebo víc vět. Normalizuje se na NFC —
                totéž dělá sám server, a klíč cache se tak shoduje s tím,
                co se poslalo.
            trace: identifikátor průchodu. Přebírá se, nikdy nerazí.

        Výstup:
            CoNLL-U se segmentací a tokenizací; sloupce s tagy jsou prázdné.
            Každá věta nese `# text`, ze kterého vzejde klíč cache.

        Při chybě:
            `UpstreamUnavailable`, když server neodpovídá; `SentenceTooLong`
            u věty nad mez serveru; `UpstreamError` u ostatních chyb.
        """
        return self._process(
            {"tokenizer": "", "data": _nfc(text)},
            method="tokenize", trace=trace,
            vstup={"chars": len(text)},
        )

    def tag_and_parse(self, conllu_text: str, *,
                      trace: str | None = None) -> str:
        """Fáze 4: dorozbor hotového CoNLL-U.

        **Neposílá `tokenizer`**, takže server čte vstup jako CoNLL-U a
        segmentaci ani tokenizaci nemění. Bez toho by se naše oprava zahodila
        a věty by se navíc mohly slepit — conBond2 to má zapsané:
        „dávkou je tokenizér občas slepí a čísla vět by přestala odpovídat
        označení."

        Vstup:
            conllu_text: hotové CoNLL-U z `conllu.write`.
            trace: identifikátor průchodu.

        Výstup:
            Totéž CoNLL-U s doplněnými tagy a závislostmi. Věty se vracejí
            1:1 a párují se podle `sent_id`.

        Při chybě:
            Stejné výjimky jako `tokenize`.
        """
        return self._process(
            {"tagger": "", "parser": "", "data": conllu_text},
            method="tag_and_parse", trace=trace,
            vstup={"bytes": len(conllu_text)},
        )

    def models(self) -> dict[str, Any]:
        """Vrátí seznam modelů, které server obsluhuje.

        Používá se ke zjištění, jestli server žije: je to nejlevnější dotaz,
        který nesahá na data ani nenačítá síť.

        Výstup:
            Odpověď serveru jako slovník.

        Při chybě:
            `UpstreamUnavailable` nebo `UpstreamError`.
        """
        adresa = self.endpoint + MODELS_PATH
        try:
            with urllib.request.urlopen(adresa, timeout=self.timeout_s) as r:
                telo = r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise UpstreamError(
                f"UDPipe na {adresa} odpověděl {e.code}"
            ) from None
        except (urllib.error.URLError, OSError) as e:
            raise UpstreamUnavailable(self._hlaska(e)) from None
        try:
            return json.loads(telo)
        except json.JSONDecodeError:
            raise UpstreamError(
                f"UDPipe na {adresa} nevrátil JSON"
            ) from None

    def _process(self, parametry: dict[str, str], *, method: str,
                 trace: str | None, vstup: dict[str, Any]) -> str:
        """Pošle požadavek na `/process` a vrátí obsah klíče `result`.

        Vstup:
            parametry: tělo požadavku. Přítomnost klíče rozhoduje, ne hodnota —
                server testuje `"tagger" in params`.
            method: jméno metody do logu.
            trace: identifikátor průchodu.
            vstup: shrnutí vstupu do logu. Nikdy celý text — log s celými
                korpusovými daty naroste tak, že se v něm nedá hledat.

        Výstup:
            Obsah klíče `result`, tedy syrový CoNLL-U.

        Při chybě:
            Vyhazuje a **zároveň o tom zapíše záznam** — tichá chyba je
            nejhorší druh chyby, protože měření ji ukáže jako úspěch.
        """
        adresa = self.endpoint + PROCESS_PATH
        telo = urllib.parse.urlencode(parametry).encode("utf-8")
        try:
            with urllib.request.urlopen(adresa, telo,
                                        timeout=self.timeout_s) as r:
                odpoved = r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            self._zaloguj(method, trace, vstup, result="error",
                          message=f"HTTP {e.code}")
            raise self._z_http_chyby(e) from None
        except (urllib.error.URLError, OSError) as e:
            self._zaloguj(method, trace, vstup, result="error",
                          message=str(e))
            raise UpstreamUnavailable(self._hlaska(e)) from None

        vysledek = self._vytahni_result(odpoved, adresa, method, trace, vstup)
        self._zaloguj(method, trace, vstup, result="ok",
                      vystup={"bytes": len(vysledek)})
        return vysledek

    def _vytahni_result(self, odpoved: str, adresa: str, method: str,
                        trace: str | None, vstup: dict[str, Any]) -> str:
        """Přečte klíč `result` z odpovědi serveru.

        Chybějící `result` **není prázdný rozbor**. Je to jiný protokol, než
        jaký čekáme, a slít to s prázdnem by byla tichá chyba: měření by
        ukázalo větu bez tokenů místo nefunkčního spojení.
        """
        try:
            data = json.loads(odpoved)
        except json.JSONDecodeError:
            self._zaloguj(method, trace, vstup, result="error",
                          message="odpověď není JSON")
            raise UpstreamError(
                f"UDPipe na {adresa} nevrátil JSON"
            ) from None
        if not isinstance(data, dict) or "result" not in data:
            self._zaloguj(method, trace, vstup, result="error",
                          message="odpověď nemá klíč result")
            raise UpstreamError(
                f"UDPipe na {adresa} vrátil odpověď bez klíče 'result'. "
                f"Prázdný rozbor to není — je to jiný protokol."
            )
        return data["result"]

    def _z_http_chyby(self, e: urllib.error.HTTPError) -> UpstreamError:
        """Přeloží chybu serveru na náš typ.

        Věta nad mez dostane vlastní typ, aby ji volající mohl přeskočit
        s důvodem místo zahození celé dávky.
        """
        try:
            telo = e.read().decode("utf-8", errors="replace")
        except Exception:            # noqa: BLE001 — tělo chyby je nepovinné
            telo = ""
        if TOO_LONG_MARKER in telo:
            return SentenceTooLong(telo.strip())
        return UpstreamError(
            f"UDPipe odpověděl {e.code}: {telo.strip() or e.reason}"
        )

    def _hlaska(self, duvod: Exception) -> str:
        """Sestaví hlášku o nedostupném serveru.

        Povinně tři věci: který modul, na jaké adrese ho klient hledal a čím
        ho spustit (README-MODULES.md § 1).
        """
        return (
            f"modul cb-udpipe: vlastní instance UDPipe neodpovídá na "
            f"{self.endpoint}{MODELS_PATH} ({duvod}).\n"
            f"Spusť ji: {self.launcher}"
        )

    def _zaloguj(self, method: str, trace: str | None,
                 vstup: dict[str, Any], *, result: str,
                 vystup: dict[str, Any] | None = None,
                 message: str | None = None) -> None:
        """Zapíše záznam o volání ven, pokud je logovátko k dispozici.

        Klient loguje sám za sebe: je to jediné místo, kde je vidět obě strany
        hranice. Když se rozejdou, je chyba mezi nimi — v síti, v serializaci,
        v timeoutu — a bez záznamu z obou stran ji nikdo nenajde
        (README-MODULES.md § 1).
        """
        if self.log is None:
            return
        udaje: dict[str, Any] = {
            "method": method, "trace": trace, "result": result, "input": vstup,
        }
        if vystup is not None:
            udaje["output"] = vystup
        if message is not None:
            udaje["message"] = message
        self.log.info(**udaje)


def _nfc(text: str) -> str:
    """Normalizuje text na NFC.

    Server dělá totéž (`unicodedata.normalize("NFC", params["data"])`), takže
    bez toho by se klíč cache lišil od textu, se kterým server pracoval.
    """
    return unicodedata.normalize("NFC", text)
