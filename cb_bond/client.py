"""`BondClient` — rozhraní cb-bondu pro ostatní moduly.

Jediná cesta, kterou smí cizí modul cb-bond volat (§ 4). Import čehokoli
z vnitřku obchází šev, a ten pak přestane být švem: nejde vyměnit
implementace za ním, protože někdo spoléhá na to, co je uvnitř.

Klient se vytváří **jednou při startu**, ne v každé funkci — klient
v cyklu znamená kontrolu služby v cyklu. Dál se předává parametrem tomu,
kdo ho volá (§ 3).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

#: Ovládací program, kterým se služba spouští. Patří do hlášky o
#: nedostupné službě: bez něj si každý musí pamatovat jméno programu,
#: a to je přesně ta drobnost, kvůli které se místo spuštění služby
#: hodinu hledá chyba v kódu.
CONTROL = "./cb-bond.py start"


class ServiceUnavailable(Exception):
    """Služba cb-bond neodpovídá.

    Typovaná chyba, ne prázdný výsledek: prázdný by se slil s platným
    „nevím" a volající by hledal chybu v datech místo ve spojení (§ 9).
    """


class IncompatibleApi(Exception):
    """Služba běží, ale neumí verzi rozhraní, kterou klient chce."""


def default_endpoint() -> tuple[str, str]:
    """Adresa služby z její vlastní konfigurace a `run/service.port`.

    Adresu své služby deklaruje sama služba; opisovat ji do konfigurace
    každého volajícího by znamenalo tolik míst k opravě, kolik je
    volajících. Skutečný port z `run/` má přednost — v konfiguraci může
    být nula, kterou přiděluje systém.
    """
    from cb_bond.config import load
    config = load()
    host = config["service"]["host"]
    port = config["service"]["port"]
    try:
        skutecny = int(
            Path(config["runtime"]["port_file"]).read_text().strip())
        if skutecny > 0:
            port, zdroj = skutecny, "run/service.port"
        else:
            zdroj = "konfigurace"
    except (OSError, ValueError):
        zdroj = "konfigurace"
    return f"http://{host}:{port}", zdroj


class BondClient:
    """Otázky a stav systému přes síť.

    Vstup:
        endpoint: adresa služby. **Nepovinná** — bez ní se zjistí
            z konfigurace modulu (viz `default_endpoint`).
        timeout: strop na jedno volání. Odpověď na otázku je řádově
            desítky milisekund, ale stavba při prvním dotazu po startu
            může trvat déle.
        api: verze rozhraní, kterou klient umí.
    """

    def __init__(self, *, endpoint: str | None = None,
                 timeout: float = 60.0, api: str = "v1") -> None:
        if endpoint is None:
            self.endpoint, self.endpoint_source = default_endpoint()
        else:
            self.endpoint = endpoint.rstrip("/")
            self.endpoint_source = "předáno"
        self.timeout = timeout
        self.api = api

    def ask(self, text: str, *, top: int | None = None) -> dict[str, Any]:
        """Otázka → odpověď, rozklad skóre a kandidátní věty.

        Při chybě:
            `ServiceUnavailable`, když služba neodpovídá nebo nemá
            postavený systém. Pro volajícího je obojí totéž: odpověď
            nedostane.
        """
        telo: dict[str, Any] = {"text": text}
        if top is not None:
            telo["top"] = top
        return self._post("/v1/ask", telo)

    def context(self, text: str) -> dict[str, Any]:
        """Přidá větu do korpusu i grafu; vrátí nový stav.

        Dialogové doplnění: když systém neví, člověk mu fakt dopoví
        a další otázka už s ním počítá.
        """
        return self._post("/v1/context", {"text": text})

    def teach_pattern(self, lemma: str, operation: str) -> dict[str, Any]:
        """Naučí jazykový vzor operátoru (LANGUAGE_LEARNING.md)."""
        return self._post("/v1/logic/pattern",
                          {"lemma": lemma, "operation": operation,
                           "learned_from": "konzole"})

    def forget_word(self, lemma: str) -> dict[str, Any]:
        """Odvolá jazykový vzor slova; formální operace zůstává."""
        return self._post("/v1/logic/forget", {"lemma": lemma})

    def resolve_reference(self, choice: str) -> dict[str, Any]:
        """Dokončí doptání na referenci volbou instance|class (§ 5)."""
        return self._post("/v1/logic/resolve", {"choice": choice})

    def state(self) -> dict[str, Any]:
        """Statistiky obsahu — vět, hran, lemmat, os, vazeb."""
        return self._get("/v1/state")

    def health(self) -> dict[str, Any]:
        """Stav služby. `degraded` znamená běží, ale neumí odpovídat."""
        return self._get("/v1/health")

    def version(self) -> dict[str, Any]:
        """Verze modulu a rozhraní; odpovídá i nezdravé službě."""
        return self._get("/version")

    # --- vnitřek --------------------------------------------------------

    def _get(self, cesta: str) -> dict[str, Any]:
        return self._posli(urllib.request.Request(self.endpoint + cesta))

    def _post(self, cesta: str, telo: dict[str, Any]) -> dict[str, Any]:
        return self._posli(urllib.request.Request(
            self.endpoint + cesta,
            data=json.dumps(telo, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"}))

    def _posli(self, pozadavek) -> dict[str, Any]:
        """Odešle požadavek a přeloží chyby na typy, kterým se dá věřit."""
        try:
            with urllib.request.urlopen(pozadavek,
                                        timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise self._z_odpovedi(e) from None
        except (urllib.error.URLError, OSError) as e:
            raise ServiceUnavailable(self._hlaska(e)) from None

    def _z_odpovedi(self, e: urllib.error.HTTPError) -> Exception:
        """Typovaná chyba z těla odpovědi.

        Služba posílá `{"error": {"type", "message"}}`; typ je to, podle
        čeho se volající rozhoduje, text je pro člověka.
        """
        try:
            chyba = json.loads(e.read().decode("utf-8"))["error"]
            typ, zprava = chyba.get("type", "unknown"), chyba.get("message")
        except Exception:                        # noqa: BLE001
            typ, zprava = "unknown", str(e)

        if typ == "not_built":
            # Služba běží, ale systém nemá postavený. Pro volajícího je to
            # totéž jako nedostupná služba: odpověď nedostane.
            return ServiceUnavailable(
                f"modul cb-bond na {self.endpoint} běží, ale nemá "
                f"postavený systém:\n{zprava}")
        return RuntimeError(f"cb-bond {self.endpoint}: [{typ}] {zprava}")

    def _hlaska(self, duvod: Exception) -> str:
        """Hláška o nedostupné službě.

        Povinně tři věci: který modul, na jaké adrese ho klient hledal
        a čím ho spustit.
        """
        return (f"modul cb-bond neodpovídá na {self.endpoint} "
                f"(adresa z: {self.endpoint_source})\n"
                f"  důvod: {duvod}\n"
                f"  spustíš ho: {CONTROL}")
