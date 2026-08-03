"""REST vrstva nad `service.py`.

Rozbalí požadavek, zavolá službu, zabalí odpověď. **Žádné rozhodnutí o doméně**
tady být nesmí — když se objeví `if` nad obsahem dat, patří do `service.py`
(README-MODULES.md § 1). Díky tomu jde týž modul použít v procesu i přes síť a obě
cesty vrátí totéž (`T-K3`).

Staví se na standardní knihovně. Provozní backend nesmí potřebovat nic mimo ni;
těžké knihovny patří k přípravě dat, ne k běhu služby.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from cb_logger import __api__, __version__
from cb_logger.service import LoggerService, now_iso

#: Návratové kódy. Vyjmenované schválně na jednom místě, aby se význam
#: nerozešel mezi obsluhami (README-MODULES.md § 7).
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_PAYLOAD_TOO_LARGE = 413
HTTP_SERVER_ERROR = 500


class ApiServer(ThreadingHTTPServer):
    """HTTP server, který si nese službu a konfiguraci.

    Proč se předává přes server a ne globálem: obsluha požadavku si musí umět
    sáhnout na službu, ale `BaseHTTPRequestHandler` se instancuje sám a nejde
    mu nic předat konstruktorem. Server je jediné místo, kde to jde udělat
    explicitně — modulová proměnná by znemožnila mít dvě služby v jednom
    procesu, což potřebují testy.
    """

    daemon_threads = True
    # Nechává znovu obsadit port hned po ukončení. Bez toho by restart služby
    # musel čekat na uvolnění soketu a `restart` by občas selhal.
    allow_reuse_address = True

    def __init__(self, address, handler_class, *, service: LoggerService,
                 config: dict[str, Any]):
        super().__init__(address, handler_class)
        self.service = service
        self.config = config


class ApiHandler(BaseHTTPRequestHandler):
    """Obsluha jednoho požadavku.

    Cesty jsou verzované (`/v1/…`) s jedinou výjimkou: `/version` stojí mimo
    verzování, protože kdo se ptá na verzi, ještě neví, kterou verzi rozhraní
    má volat.
    """

    # Vlastní jméno serveru místo výchozího "BaseHTTP/0.6 Python/3.11".
    # Verze interpretu v hlavičce je zbytečná informace pro kohokoli, kdo
    # se na port připojí.
    server_version = "cb-logger"
    sys_version = ""

    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ GET

    def do_GET(self) -> None:
        """Obslouží čtecí body rozhraní."""
        cesta = urlparse(self.path).path.rstrip("/") or "/"
        sluzba: LoggerService = self.server.service

        try:
            if cesta == "/version":
                self._send_json(HTTP_OK, self._version_object())
            elif cesta == "/v1/health":
                self._send_json(HTTP_OK, sluzba.health())
            elif cesta == "/v1/config":
                self._send_json(HTTP_OK, self._config_object())
            elif cesta == "/v1/summary":
                self._send_json(HTTP_OK, sluzba.summary())
            else:
                self._send_error(
                    HTTP_NOT_FOUND, "unknown_path",
                    f"neznámá cesta {cesta}",
                    {"known": ["/version", "/v1/health", "/v1/config",
                               "/v1/summary", "/v1/records"]},
                )
        except Exception as e:  # noqa: BLE001 — poslední záchyt, viz níže
            # Poslední záchyt: neošetřená výjimka v obsluze by jinak zavřela
            # spojení bez odpovědi a volající by viděl výpadek sítě místo
            # chyby. `except: pass` je zakázaný, tenhle záchyt hlásí.
            self._handle_unexpected(e)

    # ----------------------------------------------------------------- POST

    def do_POST(self) -> None:
        """Obslouží zápis záznamů a vynulování souhrnu."""
        cesta = urlparse(self.path).path.rstrip("/") or "/"
        sluzba: LoggerService = self.server.service

        try:
            if cesta == "/v1/records":
                telo = self._read_json_object()
                if telo is None:
                    return
                vysledek = sluzba.accept(
                    telo.get("records"), received_ts=now_iso()
                )
                if "error" in vysledek:
                    self._send_error(
                        HTTP_BAD_REQUEST, "invalid_records",
                        vysledek["error"],
                        {"expected": '{"records": [ … ]}'},
                    )
                    return
                self._send_json(HTTP_OK, vysledek)

            elif cesta == "/v1/objects":
                # Druhý druh logu: celý JSON objekt místo řádku textu.
                # Vlastní cesta schválně — má jiný tvar záznamu, jiný proud
                # a jiné kukátko (viz objects.py).
                telo = self._read_json_object()
                if telo is None:
                    return
                vysledek = sluzba.accept_objects(
                    telo.get("objects"), received_ts=now_iso()
                )
                if "error" in vysledek:
                    self._send_error(
                        HTTP_BAD_REQUEST, "invalid_objects",
                        vysledek["error"],
                        {"expected": '{"objects": [ … ]}'},
                    )
                    return
                self._send_json(HTTP_OK, vysledek)

            elif cesta == "/v1/summary/reset":
                self._send_json(HTTP_OK, sluzba.reset_summary())

            else:
                self._send_error(
                    HTTP_NOT_FOUND, "unknown_path", f"neznámá cesta {cesta}",
                    {"known": ["/v1/records", "/v1/objects",
                               "/v1/summary/reset"]},
                )
        except Exception as e:  # noqa: BLE001 — poslední záchyt
            self._handle_unexpected(e)

    # -------------------------------------------------------------- pomocné

    def _version_object(self) -> dict[str, Any]:
        """Sestaví odpověď `GET /version`.

        Nesahá na data ani na závislosti schválně: musí odpovědět i tehdy,
        když je služba jinak nezdravá. Klient ji používá jako první kontrolu
        při vytvoření a `control.py` jako první krok po startu.
        """
        import sys

        return {
            "module": "cb-logger",
            "version": __version__,
            "api": list(__api__),
            "config_version": self.server.config["config_version"],
            "python": ".".join(str(c) for c in sys.version_info[:3]),
        }

    def _config_object(self) -> dict[str, Any]:
        """Sestaví odpověď `GET /v1/config`.

        Vrací **skutečně použitou** konfiguraci včetně cesty, ze které se
        načetla. Bez toho nikdo nezjistí, které nastavení vlastně běží —
        a hledá pak chybu v běžící službě, zatímco běží s jiným nastavením,
        než si myslí.
        """
        config = dict(self.server.config)
        meta = config.pop("_meta", {})
        return {"path": meta.get("path"), "fingerprint": meta.get("fingerprint"),
                "config": config}

    def _read_json_object(self) -> dict[str, Any] | None:
        """Přečte tělo požadavku jako JSON objekt.

        Vstup i výstup rozhraní je vždy JSON objekt, ne pole a ne skalár
        (README-MODULES.md § 7): do objektu jde přidat klíč, aniž se rozbijí stávající
        klienti.

        Výstup:
            Načtený objekt, nebo `None`, když bylo tělo špatně — v tom případě
            už je odpověď odeslaná a volající má skončit.

        Při chybě:
            Nevyhazuje; chybu pošle jako typovanou odpověď.
        """
        strop = self.server.config["service"]["max_request_bytes"]
        try:
            delka = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send_error(HTTP_BAD_REQUEST, "invalid_length",
                             "Content-Length není číslo", {})
            return None

        if delka > strop:
            # Limit platí i pro volání z vlastního systému: modul, který věří
            # vlastnímu klientovi, spadne na první chybě v tom klientovi.
            self._send_error(
                HTTP_PAYLOAD_TOO_LARGE, "too_large",
                f"požadavek má {delka} B, strop je {strop} B",
                {"max_request_bytes": strop},
            )
            return None

        try:
            data = json.loads(self.rfile.read(delka) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._send_error(HTTP_BAD_REQUEST, "invalid_json",
                             f"tělo požadavku není platný JSON: {e}", {})
            return None

        if not isinstance(data, dict):
            self._send_error(
                HTTP_BAD_REQUEST, "not_an_object",
                f"tělo musí být JSON objekt, ne {type(data).__name__}",
                {"expected": '{"records": [ … ]}'},
            )
            return None
        return data

    def _send_json(self, status: int, telo: dict[str, Any]) -> None:
        """Odešle JSON objekt s daným stavem."""
        data = json.dumps(telo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: int, typ: str, zprava: str,
                    detail: dict[str, Any]) -> None:
        """Odešle typovanou chybu.

        Chyba má typ, ne jen text. Volající se podle typu rozhoduje; podle
        textu by se rozhodovat nemohl, protože text se mění s překlady
        a upřesněními.
        """
        self._send_json(status, {
            "error": {"type": typ, "message": zprava, "detail": detail}
        })

    def _handle_unexpected(self, e: Exception) -> None:
        """Přeloží neočekávanou výjimku na chybu 500 a zapamatuje si ji.

        Poslední chyba se objeví v `GET /v1/health` a tedy i ve `status` —
        jinak by se o ní člověk dozvěděl jen z logu, který v tu chvíli nemusí
        jít zapisovat.
        """
        popis = f"{type(e).__name__}: {e}"
        try:
            self.server.service.note_error(popis)
        except Exception:
            pass
        try:
            self._send_error(HTTP_SERVER_ERROR, "internal_error", popis, {})
        except Exception:
            # Spojení už je pryč. Víc se dělat nedá a shodit kvůli tomu vlákno
            # obsluhy by shodilo i ostatní požadavky.
            pass

    def log_message(self, format: str, *args: Any) -> None:
        """Umlčí výchozí výpis na chybový výstup.

        `BaseHTTPRequestHandler` po každém požadavku píše řádek na stderr.
        U logovátka, které jich obsluhuje statisíce, by to zaplavilo terminál
        a při běhu na pozadí i soubor. Co je potřeba vědět, je v `/v1/summary`.
        """
        return


def make_api_server(service: LoggerService,
                    config: dict[str, Any]) -> ApiServer:
    """Postaví HTTP server REST rozhraní.

    Server se **nespouští** — vrací se připravený, aby si volající mohl
    přečíst skutečně přidělený port dřív, než začne obsluhovat. To je
    podstatné, když je v konfiguraci port `0`.

    Vstup:
        service: doménová logika. Předává se explicitně, aby šly mít dvě
            služby v jednom procesu (testy).
        config: ověřená konfigurace.

    Výstup:
        Připravený `ApiServer`. Skutečný port je v `server.server_address[1]`.

    Při chybě:
        `OSError`, když je port obsazený. Volající to přeloží na hlášku, která
        řekne, který port a co s tím.
    """
    server = ApiServer(
        (config["service"]["host"], config["service"]["port"]),
        ApiHandler,
        service=service,
        config=config,
    )
    server.timeout = config["service"]["request_timeout_s"]
    return server
