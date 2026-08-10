"""REST vrstva nad `service.py`.

Rozbalí požadavek, zavolá fasádu, zabalí odpověď. **Žádná logika navíc.**
Pravidlo, které to drží: jakmile se tady objeví `if` nad obsahem dat,
patří do `service.py` (§ 1 politiky). Bez té kázně přestane jít modul
použít v procesu a zkouška shody tváří ztratí smysl.

Staví se na `http.server.ThreadingHTTPServer` ze standardní knihovny.
Žádný framework: provozní backend nesmí potřebovat nic mimo standardní
knihovnu (§ 19).

## Proč je server tady, a ne v `service.py`

U sourozenců drží `service.py` HTTP server a `api.py` jen obsluhu.
V cb-bondu je `service.py` **doménová fasáda** — jeden vstup do systému,
který se dá použít i bez sítě (skripty přejímek ho volají přímo). Server
proto bydlí tady. Je to vědomá odchylka od tvaru sourozenců, zapsaná
v `docs/navrh-sluzby.md` § 2.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from cb_bond import __api__, __version__
from cb_bond.service import BondService

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500
HTTP_UNAVAILABLE = 503


class ApiServer(ThreadingHTTPServer):
    """HTTP server, který si nese odkaz na fasádu a konfiguraci."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler_class, *, service: BondService,
                 config: dict[str, Any]):
        super().__init__(address, handler_class)
        self.service = service
        self.config = config


class ApiHandler(BaseHTTPRequestHandler):
    """Obsluha jednoho požadavku."""

    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        cesta = self.path.split("?", 1)[0].rstrip("/") or "/"
        try:
            if cesta == "/version":
                self._json(HTTP_OK, self._version())
            elif cesta == "/v1/health":
                self._json(HTTP_OK, self.server.service.health())
            elif cesta == "/v1/state":
                self._json(HTTP_OK, self.server.service.state())
            elif cesta == "/v1/config":
                self._json(HTTP_OK, self._config())
            else:
                self._chyba(HTTP_NOT_FOUND, "not_found",
                            f"neznámá cesta {cesta}")
        except Exception as e:               # noqa: BLE001
            self._neocekavana(e)

    def do_POST(self) -> None:
        cesta = self.path.split("?", 1)[0].rstrip("/") or "/"
        if cesta in ("/v1/logic/pattern", "/v1/logic/forget"):
            self._logic_pattern(cesta)
            return
        if cesta not in ("/v1/ask", "/v1/context"):
            self._chyba(HTTP_NOT_FOUND, "not_found", f"neznámá cesta {cesta}")
            return

        telo = self._precti_telo()
        if telo is None:
            return                            # chyba už je odeslaná

        text = telo.get("text")
        if not isinstance(text, str) or not text.strip():
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "chybí klíč 'text' s neprázdným řetězcem")
            return
        top = telo.get("top")
        if top is not None and (not isinstance(top, int)
                                or isinstance(top, bool) or top < 1):
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "klíč 'top' musí být celé číslo aspoň 1")
            return

        try:
            if cesta == "/v1/context":
                self._json(HTTP_OK, self.server.service.context(text))
            else:
                self._json(HTTP_OK, self.server.service.ask(text, top=top))
        except RuntimeError as e:
            # Nepostavený systém je `503`, ne prázdná odpověď: prázdná by
            # se slila s platným „nevím" a to jsou dvě různé věci (§ 9).
            self._chyba(HTTP_UNAVAILABLE, "not_built", str(e))
        except Exception as e:               # noqa: BLE001
            self._neocekavana(e)

    def _precti_telo(self) -> dict[str, Any] | None:
        """Přečte tělo požadavku jako JSON objekt.

        Výstup:
            Slovník, nebo `None`, když se chyba už odeslala. Volající
            pak jen skončí.

        Při chybě:
            Neposílá výjimku ven — chybu pošle jako odpověď s typem.
        """
        try:
            delka = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "nečitelná hlavička Content-Length")
            return None
        if delka <= 0:
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "prázdné tělo požadavku")
            return None
        try:
            data = json.loads(self.rfile.read(delka).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        f"tělo není platný JSON: {e}")
            return None
        if not isinstance(data, dict):
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        f"tělo musí být JSON objekt, ne "
                        f"{type(data).__name__}")
            return None
        return data

    # ----------------------------------------------------------- odpovědi

    def _logic_pattern(self, cesta: str) -> None:
        """Naučení / odvolání jazykového vzoru operátoru (LANGUAGE_LEARNING)."""
        telo = self._precti_telo()
        if telo is None:
            return
        lemma = telo.get("lemma")
        if not isinstance(lemma, str) or not lemma.strip():
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "chybí klíč 'lemma' s neprázdným řetězcem")
            return
        try:
            if cesta == "/v1/logic/forget":
                self._json(HTTP_OK, self.server.service.forget_word(lemma))
                return
            operation = telo.get("operation")
            if operation not in ("possible", "necessary", "impossible"):
                self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                            "klíč 'operation' musí být possible|necessary|"
                            "impossible")
                return
            self._json(HTTP_OK, self.server.service.teach_pattern(
                lemma, operation, learned_from=telo.get("learned_from", "")))
        except RuntimeError as e:
            self._chyba(HTTP_UNAVAILABLE, "not_built", str(e))
        except Exception as e:               # noqa: BLE001
            self._neocekavana(e)

    def _version(self) -> dict[str, Any]:
        """Verze modulu a rozhraní.

        Odpovídá i tehdy, když je služba jinak nezdravá: nesahá na data
        ani na závislosti. `control.py` ji používá jako první krok po
        `start`, ještě před `/v1/health` (§ 7).
        """
        return {"module": "cb-bond", "version": __version__,
                "api": list(__api__)}

    def _config(self) -> dict[str, Any]:
        """Konfigurace, se kterou služba běží — včetně otisku.

        Bez otisku se dvě měření nedají porovnat a nikdo nepozná, že
        běžela jinak (§ 11).
        """
        meta = self.server.config.get("_meta", {})
        return {"path": meta.get("path"),
                "fingerprint": meta.get("fingerprint"),
                "config_version": self.server.config.get("config_version")}

    def _json(self, status: int, telo: dict[str, Any]) -> None:
        """Odešle JSON objekt.

        Vždy objekt, nikdy pole ani skalár: do objektu jde přidat klíč,
        aniž se rozbijí stávající klienti (§ 7).
        """
        data = json.dumps(telo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _chyba(self, status: int, typ: str, zprava: str) -> None:
        """Odešle typovanou chybu.

        Chyba má typ, ne jen text: odlišuje „nemá výsledek" (platný
        výsledek) od „nepodařilo se" (chyba).
        """
        self._json(status, {"error": {"type": typ, "message": zprava}})

    def _neocekavana(self, e: Exception) -> None:
        """Obsluha chyby, se kterou se nepočítalo.

        Tichá chyba je nejhorší druh chyby, protože měření ji ukáže jako
        úspěch.
        """
        self._chyba(HTTP_SERVER_ERROR, "internal_error",
                    f"{type(e).__name__}: {e}")

    def log_message(self, format: str, *args) -> None:
        """Ticho na stderr; co se má zaznamenat, jde přes logger.

        Výchozí obsluha píše řádek na stderr za každý požadavek, což
        v konzoli cb-bondu přehluší to, co člověk skutečně sleduje.
        """


def make_api_server(service: BondService, *, config: dict[str, Any],
                    host: str | None = None,
                    port: int | None = None) -> ApiServer:
    """Postaví HTTP server nad fasádou.

    Vstup:
        service: doménová fasáda.
        config: konfigurace; z ní se berou host a port, když se nepředají.
        host, port: přebijí konfiguraci. Testy sem dávají port `0`, aby
            neobsazovaly pevná čísla — skutečně přidělený port si pak
            přečtou ze `server_address` (§ 5).

    Výstup:
        `ApiServer`, který ještě neběží. Volající si ho spustí sám.

    Při chybě:
        `OSError`, když je port obsazený.
    """
    return ApiServer(
        (host if host is not None else config["service"]["host"],
         port if port is not None else config["service"]["port"]),
        ApiHandler, service=service, config=config,
    )
