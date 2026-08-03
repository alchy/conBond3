"""Klient, který si naimportují ostatní moduly.

`import cb_udpipe` dá volajícímu `UdpipeClient` a ten už REST volání obsahuje.
Kdo modul používá, nepíše žádný HTTP kód, nesestavuje URL a nerozbaluje JSON —
zavolá metodu. **REST se napíše jednou v modulu a nikdo další ho nepíše**
(README-MODULES.md § 1); kdyby si každý klient skládal požadavky sám, změna
kontraktu by se musela opravit na deseti místech a devět by se našlo za
provozu.

Dvě vlastnosti, které to musí mít, aby se dal takhle používat:

* **Podepisuje se stejně jako `service.py`.** Táž jména metod, tytéž
  parametry, týž návratový typ. Rozdíl je jen v konstruktoru, kde se předá
  `endpoint`. Že to platí, hlídá zkouška shody tváří (`T-K3`).
* **Selže při vytvoření, ne při prvním volání.** Klient nad neběžící službou
  je tikající chyba: ukázala by se uprostřed dávky, po hodině počítání
  a s polovinou zapsaných výsledků.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from cb_udpipe import __api__
from cb_udpipe.conllu import Multiword, Sentence, Token
from cb_udpipe.service import ParsedSentence, ParseResult

#: Strop na ověřovací dotaz v konstruktoru. Krátký schválně: `GET /version`
#: nemá závislosti a nesahá na data, takže na místní smyčce odchází
#: v jednotkách milisekund. Kdo čeká dýl, obvykle čeká marně.
CHECK_TIMEOUT_S = 2.0

#: Příkaz, kterým se služba spouští. Je součástí chybové hlášky.
LAUNCHER = "./cb-udpipe.py start"


class ServiceUnavailable(Exception):
    """Služba cb-udpipe neodpovídá.

    Vyhazuje se **při vytvoření klienta**. Pro volající je cb-udpipe povinná
    závislost: bez rozboru nemá co zpracovávat, takže degradace nedává smysl
    (README-MODULES.md § 9).
    """


class IncompatibleApi(Exception):
    """Služba běží, ale neumí verzi rozhraní, kterou klient chce."""


class UdpipeClient:
    """Rozbor vět přes síť. Rozhraní modulu pro ostatní moduly.

    Vytváří se **jednou při startu**, ne v každé funkci — klient v cyklu
    znamená kontrolu služby v cyklu. Dál se předává parametrem tomu, kdo ho
    volá (README-MODULES.md § 3).
    """

    def __init__(self, *, endpoint: str, log: Any = None,
                 timeout_s: float = 600.0, api: str = "v1"):
        """Vstup:
            endpoint: adresa služby, například `http://127.0.0.1:42200`.
                Předává se z konfigurace volajícího; modul se nikoho neptá,
                kde služba běží (README-MODULES.md § 4).
            log: `LogClient`, nebo `None`. Klient loguje sám za sebe — je to
                jediné místo, kde je vidět obě strany hranice.
            timeout_s: strop na jedno volání rozboru.
            api: verze rozhraní, kterou klient umí.

        Při chybě:
            `ServiceUnavailable`, když služba neodpovídá — hláška uvádí modul,
            adresu a příkaz ke spuštění. `IncompatibleApi`, když služba
            neobsluhuje požadovanou verzi rozhraní.
        """
        self.endpoint = endpoint.rstrip("/")
        self.log = log
        self.timeout_s = timeout_s
        self.api = api
        self.server_version: dict[str, Any] | None = None
        self._zkontroluj_sluzbu()

    def parse(self, *, text: str, trace: str | None = None) -> ParseResult:
        """Rozebere text. Táž signatura jako `UdpipeService.parse`.

        Vstup:
            text: jedna nebo víc vět.
            trace: identifikátor průchodu. Posílá se v těle požadavku, ne
                v hlavičce — hlavička se po cestě ztratí a řetěz by se přerušil
                na každé hranici služby (README-MODULES.md § 7).

        Výstup:
            `ParseResult` — **týž typ**, jaký vrací služba v procesu. To je
            podmínka zkoušky shody tváří (`T-K3`).

        Při chybě:
            `ServiceUnavailable`, když služba přestala odpovídat.
            `RuntimeError` s typem chyby, kterou vrátila služba.
        """
        telo = self._posli("/v1/parse", {"text": text, "trace": trace},
                           method="parse", trace=trace)
        return _parse_result_z_json(telo)

    def tokenize_only(self, *, text: str,
                      trace: str | None = None) -> list[Sentence]:
        """Jen segmentace a tokenizace, bez tagů.

        Výstup:
            Věty s opravenou tokenizací a prázdnými sloupci tagů — týž typ,
            jaký vrací služba v procesu.

        Při chybě:
            Stejné výjimky jako `parse`.
        """
        telo = self._posli("/v1/tokenize", {"text": text, "trace": trace},
                           method="tokenize_only", trace=trace)
        return [_veta_z_json(v) for v in telo["sentences"]]

    def health(self) -> dict[str, Any]:
        """Stav služby, tak jak ho hlásí `GET /v1/health`."""
        return self._get("/v1/health")

    def summary(self) -> dict[str, Any]:
        """Počty podle metody a výsledku."""
        return self._get("/v1/summary")

    # ------------------------------------------------------------ vnitřek

    def _zkontroluj_sluzbu(self) -> None:
        """Ověří při vytvoření, že služba běží a umí naši verzi rozhraní.

        Proč to stojí za jedno volání navíc: klient vytvořený nad neběžící
        službou je tikající chyba. Kdyby se výpadek ukázal až u prvního
        `parse()`, spadlo by to uprostřed dávky, po hodině počítání
        a s polovinou zapsaných výsledků (README-MODULES.md § 1).
        """
        try:
            verze = self._get("/version", timeout_s=CHECK_TIMEOUT_S)
        except ServiceUnavailable as e:
            self._zaloguj("__init__", None, result="error", message=str(e))
            raise
        self.server_version = verze

        umi = verze.get("api") or []
        if self.api not in umi:
            zprava = (
                f"modul cb-udpipe na {self.endpoint} obsluhuje rozhraní "
                f"{umi}, klient chce {self.api!r}."
            )
            self._zaloguj("__init__", None, result="error", message=zprava)
            raise IncompatibleApi(zprava)

        self._zaloguj("__init__", None, result="ok",
                      vystup={"version": verze.get("version"),
                              "tokenizer": verze.get("tokenizer")})

    def _get(self, cesta: str, *,
             timeout_s: float | None = None) -> dict[str, Any]:
        """Zavolá GET a vrátí JSON objekt."""
        return self._zavolej(cesta, None,
                             timeout_s if timeout_s is not None
                             else self.timeout_s)

    def _posli(self, cesta: str, telo: dict[str, Any], *, method: str,
               trace: str | None) -> dict[str, Any]:
        """Zavolá POST, zaloguje obě strany a vrátí JSON objekt."""
        zacatek = time.monotonic()
        try:
            odpoved = self._zavolej(cesta, telo, self.timeout_s)
        except Exception as e:
            self._zaloguj(method, trace, result="error", message=str(e),
                          vstup={"chars": len(telo.get("text") or "")})
            raise
        self._zaloguj(
            method, trace,
            result="ok" if odpoved.get("sentences") else "empty",
            vstup={"chars": len(telo.get("text") or "")},
            vystup={"sentences": len(odpoved.get("sentences") or []),
                    "cached": odpoved.get("cached"),
                    "parsed": odpoved.get("parsed")},
            duration_ms=int((time.monotonic() - zacatek) * 1000),
        )
        return odpoved

    def _zavolej(self, cesta: str, telo: dict[str, Any] | None,
                 timeout_s: float) -> dict[str, Any]:
        """Provede HTTP volání a přeloží chyby na výjimky.

        Chyba služby se **nevrací jako slovník s klíčem `error`**, ale jako
        výjimka: kdyby se vracela, musel by si každý volající pamatovat, že ji
        má kontrolovat, a jednou by na to zapomněl (README-MODULES.md § 1).

        Prázdný výsledek naopak výjimka **není** — je to normální návratová
        hodnota. Kdyby bylo obojí stejné, přenese se `INV-9` do každého
        volajícího.
        """
        adresa = self.endpoint + cesta
        data = (json.dumps(telo, ensure_ascii=False).encode("utf-8")
                if telo is not None else None)
        req = urllib.request.Request(
            adresa, data=data, method="POST" if data else "GET",
            headers={"Content-Type": "application/json"} if data else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise self._z_chyby(e, adresa) from None
        except (urllib.error.URLError, OSError) as e:
            raise ServiceUnavailable(self._hlaska(e)) from None
        except json.JSONDecodeError:
            raise RuntimeError(
                f"modul cb-udpipe na {adresa} nevrátil JSON"
            ) from None

    def _z_chyby(self, e: urllib.error.HTTPError, adresa: str) -> Exception:
        """Přeloží typovanou chybu služby na výjimku."""
        try:
            telo = json.loads(e.read().decode("utf-8"))
            chyba = telo.get("error", {})
            typ = chyba.get("type", "unknown")
            zprava = chyba.get("message", "")
        except Exception:                        # noqa: BLE001
            typ, zprava = "unknown", e.reason

        if typ == "upstream_unavailable":
            # Služba běží, ale UDPipe pod ní ne. Pro volajícího je to totéž
            # jako nedostupná služba: rozbor nedostane.
            return ServiceUnavailable(
                f"modul cb-udpipe na {self.endpoint} běží, ale jeho UDPipe "
                f"ne:\n{zprava}"
            )
        return RuntimeError(f"cb-udpipe {adresa}: [{typ}] {zprava}")

    def _hlaska(self, duvod: Exception) -> str:
        """Hláška o nedostupné službě.

        Povinně tři věci: který modul, na jaké adrese ho klient hledal a čím
        ho spustit. Bez toho třetího si každý musí pamatovat jméno ovládacího
        programu, a to je přesně ta drobnost, kvůli které se místo spuštění
        služby hodinu hledá chyba v kódu (README-MODULES.md § 1).
        """
        return (
            f"modul cb-udpipe neodpovídá na {self.endpoint}/version "
            f"({duvod}).\nSpusť ho: {LAUNCHER}"
        )

    def _zaloguj(self, method: str, trace: str | None, *, result: str,
                 vstup: dict[str, Any] | None = None,
                 vystup: dict[str, Any] | None = None,
                 message: str | None = None,
                 duration_ms: int | None = None) -> None:
        """Zapíše záznam o volání ven.

        Klient loguje sám za sebe: služba zaznamená, že ji někdo volal, klient
        zaznamená, že volal a co se vrátilo. Když se ty dva pohledy rozejdou,
        je chyba mezi nimi — a bez záznamu z obou stran ji nikdo nenajde.
        """
        if self.log is None:
            return
        udaje: dict[str, Any] = {"method": method, "trace": trace,
                                 "result": result}
        for jmeno, hodnota in (("input", vstup), ("output", vystup),
                               ("message", message),
                               ("duration_ms", duration_ms)):
            if hodnota is not None:
                udaje[jmeno] = hodnota
        try:
            self.log.info(**udaje)
        except Exception:
            # Logovátko je nepovinná závislost; jeho výpadek nesmí shodit
            # volajícího (README-MODULES.md § 9).
            pass


def from_config(config: dict[str, Any], *, log: Any = None) -> UdpipeClient:
    """Postaví klienta z konfigurace volajícího modulu.

    Vstup:
        config: konfigurace, ve které je pod `module.udpipe_endpoint` adresa
            služby. Adresa cizí služby patří do konfigurace **volajícího**,
            ne volaného (README-MODULES.md § 4).
        log: `LogClient`, nebo `None`.

    Výstup:
        Připravený `UdpipeClient`.

    Při chybě:
        `KeyError`, když adresa v konfiguraci chybí; `ServiceUnavailable`,
        když služba neběží.
    """
    return UdpipeClient(endpoint=config["module"]["udpipe_endpoint"], log=log)


# --------------------------------------------------------- z JSON na typy


def _parse_result_z_json(telo: dict[str, Any]) -> ParseResult:
    """Postaví `ParseResult` z odpovědi služby.

    Převod je zvlášť, ne metodou na typu: doménový typ nemá znát tvar drátu.
    Zároveň je to jediné místo, které musí zůstat v souladu
    s `api._parse_result_na_json` — a `T-K3` hlídá, že zůstává.
    """
    return ParseResult(
        sentences=tuple(_parsed_z_json(v) for v in telo.get("sentences", [])),
        cached=telo.get("cached", 0),
        parsed=telo.get("parsed", 0),
        skipped=tuple(telo.get("skipped", [])),
    )


def _parsed_z_json(o: dict[str, Any]) -> ParsedSentence:
    """Postaví rozebranou větu z JSON objektu."""
    return ParsedSentence(
        source=o["source"],
        tokens=tuple(_token_z_json(t) for t in o.get("tokens", [])),
        multiword=tuple(_multiword_z_json(m)
                        for m in o.get("multiword", [])),
        from_cache=o.get("from_cache", False),
        retokenized=o.get("retokenized", 0),
    )


def _veta_z_json(o: dict[str, Any]) -> Sentence:
    """Postaví větu z `tokenize_only` z JSON objektu."""
    return Sentence(
        source=o["source"],
        tokens=tuple(_token_z_json(t) for t in o.get("tokens", [])),
        multiword=tuple(_multiword_z_json(m)
                        for m in o.get("multiword", [])),
        sent_id=o.get("sent_id"),
    )


def _token_z_json(o: dict[str, Any]) -> Token:
    """Postaví token z JSON objektu."""
    return Token(
        id=o["id"], form=o["form"], lemma=o.get("lemma"), upos=o.get("upos"),
        xpos=o.get("xpos"), feats=o.get("feats"), head=o.get("head"),
        deprel=o.get("deprel"), deps=o.get("deps"), misc=o.get("misc"),
    )


def _multiword_z_json(o: dict[str, Any]) -> Multiword:
    """Postaví víceslovný tvar z JSON objektu."""
    return Multiword(id=(o["id"][0], o["id"][1]), form=o["form"],
                     misc=o.get("misc"))
