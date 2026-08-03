"""REST vrstva nad `service.py`.

Rozbalí požadavek, zavolá službu, zabalí odpověď. **Žádná logika navíc.**
Pravidlo, které to drží: když se tady objeví `if` nad obsahem dat, patří do
`service.py` (README-MODULES.md § 1). Bez té kázně přestane jít modul použít
v procesu a zkouška shody tváří (`T-K3`) ztratí smysl.

Staví se na `http.server.ThreadingHTTPServer` ze standardní knihovny. Žádný
framework: provozní backend nesmí potřebovat nic mimo standardní knihovnu —
těžké knihovny patří k přípravě dat, ne k běhu služby (§ 7 politiky).
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from cb_udpipe import __api__, __version__, upstream as upstream_modul
from cb_udpipe.service import ParsedSentence, ParseResult, UdpipeService

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_PAYLOAD_TOO_LARGE = 413
HTTP_SERVER_ERROR = 500
HTTP_UNAVAILABLE = 503


class ApiServer(ThreadingHTTPServer):
    """HTTP server, který si nese odkaz na službu a konfiguraci."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler_class, *, service: UdpipeService,
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
            elif cesta == "/v1/config":
                self._json(HTTP_OK, self._config())
            elif cesta == "/v1/summary":
                self._json(HTTP_OK, self.server.service.summary())
            elif cesta == "/v1/cache/stats":
                self._json(HTTP_OK, self.server.service.cache.stats())
            else:
                self._chyba(HTTP_NOT_FOUND, "not_found",
                            f"neznámá cesta {cesta}")
        except Exception as e:               # noqa: BLE001
            self._neocekavana(e)

    def do_POST(self) -> None:
        cesta = self.path.split("?", 1)[0].rstrip("/") or "/"
        if cesta not in ("/v1/parse", "/v1/tokenize"):
            self._chyba(HTTP_NOT_FOUND, "not_found", f"neznámá cesta {cesta}")
            return

        telo = self._precti_telo()
        if telo is None:
            return                            # chyba už je odeslaná

        text = telo.get("text")
        trace = telo.get("trace")
        if not isinstance(text, str):
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "chybí klíč 'text' typu string")
            return
        if trace is not None and not isinstance(trace, str):
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "klíč 'trace' musí být string")
            return

        try:
            if cesta == "/v1/parse":
                vysledek = self.server.service.parse(text, trace=trace)
                self._json(HTTP_OK, _parse_result_na_json(vysledek, trace))
            else:
                vety = self.server.service.tokenize_only(text, trace=trace)
                self._json(HTTP_OK, {
                    "sentences": [_veta_na_json(v) for v in vety],
                    "trace": trace,
                })
        except upstream_modul.UpstreamUnavailable as e:
            # Povinná závislost. Nikdy prázdná odpověď — ta by se slila
            # s platným prázdným výsledkem (§ 9 politiky).
            self._chyba(HTTP_UNAVAILABLE, "upstream_unavailable", str(e))
        except upstream_modul.UpstreamError as e:
            self._chyba(HTTP_SERVER_ERROR, "upstream_error", str(e))
        except Exception as e:               # noqa: BLE001
            self._neocekavana(e)

    # ----------------------------------------------------------- odpovědi

    def _version(self) -> dict[str, Any]:
        """Verze modulu a rozhraní.

        Odpovídá i tehdy, když je služba jinak nezdravá: nemá závislosti
        a nesahá na data. `control.py` ji používá jako první krok po `start`,
        ještě před `/v1/health` (§ 7 politiky).
        """
        return {
            "module": "cb-udpipe",
            "version": __version__,
            "api": list(__api__),
            "config_version": self.server.config["config_version"],
            "tokenizer": self.server.service.tokenizer_version,
            "python": "%d.%d.%d" % sys.version_info[:3],
        }

    def _config(self) -> dict[str, Any]:
        """Skutečně použitá konfigurace včetně cesty, ze které se načetla."""
        meta = self.server.config.get("_meta", {})
        return {
            "path": meta.get("path"),
            "fingerprint": meta.get("fingerprint"),
            "config": {k: v for k, v in self.server.config.items()
                       if k != "_meta"},
        }

    def _precti_telo(self) -> dict[str, Any] | None:
        """Přečte tělo požadavku jako JSON objekt.

        Výstup:
            Slovník, nebo `None`, když se chyba už odeslala. Volající pak
            jen skončí.

        Při chybě:
            Neodesílá výjimku ven — chybu pošle jako odpověď s typem.
        """
        try:
            delka = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "neplatná hlavička Content-Length")
            return None

        strop = self.server.config["service"]["max_request_bytes"]
        if delka > strop:
            # Limity jsou součástí kontraktu, ne překvapení. Náš strop je
            # nižší než serverový, ať chyba vznikne u nás s lepší hláškou.
            #
            # Tělo se musí DOČÍST, i když ho zahazujeme: kdybychom odpověděli
            # dřív, než klient dopíše, dostal by rozbité spojení místo naší
            # hlášky — a nedozvěděl by se, že narazil na limit. Čte se po
            # blocích, takže se velký požadavek nedostane do paměti.
            self._zahod_telo(delka)
            self._chyba(HTTP_PAYLOAD_TOO_LARGE, "payload_too_large",
                        f"tělo má {delka} B, strop je {strop} B")
            return None

        try:
            syrove = self.rfile.read(delka).decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        f"tělo se nepodařilo přečíst: {e}")
            return None

        try:
            data = json.loads(syrove) if syrove else {}
        except json.JSONDecodeError as e:
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        f"tělo není platný JSON: {e.msg}")
            return None

        if not isinstance(data, dict):
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "tělo musí být JSON objekt, ne "
                        f"{type(data).__name__}")
            return None
        return data

    def _zahod_telo(self, delka: int, blok: int = 65536) -> None:
        """Dočte a zahodí tělo požadavku, které se nebude zpracovávat.

        Vstup:
            delka: kolik bajtů klient posílá.
            blok: po kolika se čte. Velký požadavek se tím nikdy nedostane
                do paměti celý.

        Výstup:
            Nic.

        Při chybě:
            Nevyhazuje. Když spojení mezitím spadne, není co dočítat.
        """
        zbyva = delka
        while zbyva > 0:
            kus = self.rfile.read(min(blok, zbyva))
            if not kus:
                return
            zbyva -= len(kus)

    def _json(self, status: int, telo: dict[str, Any]) -> None:
        """Odešle JSON objekt.

        Vždy objekt, nikdy pole ani skalár: do objektu jde přidat klíč, aniž
        se rozbijí stávající klienti (§ 7 politiky).
        """
        data = json.dumps(telo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _chyba(self, status: int, typ: str, zprava: str) -> None:
        """Odešle typovanou chybu.

        Chyba má typ, ne jen text: odlišuje se „nemá výsledek" (platný
        výsledek) od „nepodařilo se" (chyba). Je to jediné místo, kde se
        `INV-9` láme do praxe (§ 7 politiky).
        """
        self._json(status, {"error": {"type": typ, "message": zprava}})

    def _neocekavana(self, e: Exception) -> None:
        """Obsluha chyby, se kterou se nepočítalo.

        Zapíše ji do souhrnu služby a odpoví `500` s typem. Tichá chyba je
        nejhorší druh chyby, protože měření ji ukáže jako úspěch.
        """
        try:
            self.server.service._souhrn.pricti("api", "error")
        except Exception:                    # noqa: BLE001
            pass
        self._chyba(HTTP_SERVER_ERROR, "internal_error",
                    f"{type(e).__name__}: {e}")

    def log_message(self, format: str, *args: Any) -> None:
        """Server nepíše do stderr.

        Log je šev; kam jde, rozhoduje klient (návrh, kap. 5). Provozní
        záznamy dělá `service.py` přes logovátko.
        """


def _parse_result_na_json(r: ParseResult, trace: str | None) -> dict[str, Any]:
    """Převede výsledek rozboru na JSON objekt.

    Serializace je zvlášť, ne metodou na `ParseResult`: doménový typ nemá znát
    tvar drátu. Kdyby ho znal, změna rozhraní by sahala do domény.
    """
    return {
        "sentences": [_parsed_na_json(v) for v in r.sentences],
        "cached": r.cached,
        "parsed": r.parsed,
        "skipped": [dict(s) for s in r.skipped],
        "trace": trace,
    }


def _parsed_na_json(v: ParsedSentence) -> dict[str, Any]:
    """Převede rozebranou větu na JSON objekt."""
    return {
        "source": v.source,
        "from_cache": v.from_cache,
        "retokenized": v.retokenized,
        "tokens": [_token_na_json(t) for t in v.tokens],
        "multiword": [{"id": list(m.id), "form": m.form, "misc": m.misc}
                      for m in v.multiword],
    }


def _veta_na_json(v: Any) -> dict[str, Any]:
    """Převede větu z `tokenize_only` na JSON objekt."""
    return {
        "source": v.source,
        "tokens": [_token_na_json(t) for t in v.tokens],
        "multiword": [{"id": list(m.id), "form": m.form, "misc": m.misc}
                      for m in v.multiword],
    }


def _token_na_json(t: Any) -> dict[str, Any]:
    """Převede token na JSON objekt.

    Vypisuje **všech deset sloupců** včetně prázdných: na drátě je pevný tvar
    důležitější než úspora, protože klient nemá jak poznat, jestli klíč chybí
    proto, že je prázdný, nebo proto, že ho tahle verze neposílá.
    """
    return {
        "id": t.id, "form": t.form, "lemma": t.lemma, "upos": t.upos,
        "xpos": t.xpos, "feats": t.feats, "head": t.head,
        "deprel": t.deprel, "deps": t.deps, "misc": t.misc,
    }


def make_api_server(service: UdpipeService, *,
                    config: dict[str, Any],
                    host: str | None = None,
                    port: int | None = None) -> ApiServer:
    """Postaví HTTP server nad službou.

    Vstup:
        service: doménová logika.
        config: konfigurace; z ní se berou host a port, když se nepředají.
        host, port: přebijí konfiguraci. Testy sem dávají port `0`, aby
            neobsazovaly pevná čísla — skutečně přidělený port si pak přečtou
            ze `server_address` (§ 5 politiky).

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
