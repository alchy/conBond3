"""Kukátko na pole: služba, která zobrazí poslední publikovanou větu.

Použití ze dvou stran:

    terminál:    ./run-python -m cb_field.viewer          # zvedne službu
    python CLI:  from cb_field import visualize
                 visualize.sentence(a.sentences[0])       # aktualizuje pohled

Prohlížeč na http://127.0.0.1:42301/ ukazuje větu ve stylu POLE — řádek na
slovo, vertikála na dvojici atribut=hodnota (multiatribut je rozvinutý na
víc vertikál) — ale rozdělenou na jednotlivé koše, aby byly patrné. Pohled
se přepíná mezi kompletním (se slovy) a jen atributy (bez slov).

Stránka jen čte (je to okno, ne ovládání) a data bere z run/current.json —
běhový stav, jehož smazání je neškodné: viewer pak ukáže „zatím nic".

Mockup: bez logování a bez konfigurace; port je zapsán v tabulce rozsahů
v README-MODULES § 5.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from cb_field.service import (activations, build_baskets, expand_basket,
                              is_question)

MODULE_DIR = Path(__file__).resolve().parent

#: Kam se publikuje aktuální věta. run/ nepřežívá restart a nemá přežívat.
CURRENT_PATH = MODULE_DIR / "run" / "current.json"

#: Soběstačná stránka kukátka; leží vedle tohohle souboru.
PAGE_PATH = MODULE_DIR / "viewer.html"

#: Adresa kukátka. Port je z rozsahu cb-field (42300–42399, § 5 politiky);
#: 42300 si drží budoucí REST API modulu.
HOST = "127.0.0.1"
PORT = 42301


class Visualizer:
    """Publikuje větu pro kukátko; pohled v prohlížeči se sám obnoví.

    Proč třída a ne holá funkce: ponese si výchozí poloměr a cíl, a až
    bude viewerů víc (jiný port, jiný stroj), vznikne druhá instance —
    stejný vzor jako u klientů služeb (§ 1 politiky).
    """

    def __init__(self, r: int = 2, path: Path = CURRENT_PATH) -> None:
        self.r = r
        self.path = path

    def sentence(self, parsed_sentence, r: int | None = None) -> Path:
        """Postaví koše věty a publikuje je jako aktuální pohled.

        Vstup:
            parsed_sentence: ParsedSentence z cb_udpipe (má .tokens
                a .source).
            r: poloměr okna; když se nedá, platí poloměr instance.

        Výstup:
            Cesta zapsaného souboru. Když služba kukátka neběží, zápis
            proběhne i tak — jen se vypíše, čím ji spustit.
        """
        baskets = build_baskets(parsed_sentence.tokens,
                                r=self.r if r is None else r)
        path = _write_current(baskets, self.path,
                              source=getattr(parsed_sentence, "source", None),
                              question=is_question(parsed_sentence.tokens))
        if not _viewer_alive():
            print(f"pozn.: kukátko na http://{HOST}:{PORT}/ neodpovídá — "
                  f"spusť ho: ./run-python -m cb_field.viewer",
                  file=sys.stderr)
        return path


#: Připravená instance pro CLI: from cb_field import visualize
visualize = Visualizer()


def _write_current(baskets, path: Path, source=None,
                   question: bool = False) -> Path:
    """Zapíše publikovanou větu pro stránku kukátka (atomicky).

    Soukromá přepravka jen mezi Visualizerem a stránkou — obecné ukládání
    košů vede přes maticovou cestu (VerticalRegistry); tenhle JSON žije
    a umírá s viewerem.

    Aktivace (acts) se počítají tady v Pythonu — stránka je jen kreslí,
    aby pravidla vertikál nežila dvakrát a nerozešla se.
    """
    record = {
        "r": baskets[0].r if baskets else None,
        "source": source,
        "question": question,
        "baskets": [
            {
                "center": b.center,
                "rows": [
                    {
                        "form": row["form"],
                        "acts": activations(row, question),
                    }
                    for row in expand_basket(b)
                ],
            }
            for b in baskets
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)
    return path


def _viewer_alive(timeout_s: float = 0.3) -> bool:
    try:
        with urlopen(f"http://{HOST}:{PORT}/health", timeout=timeout_s):
            return True
    except OSError:
        return False


class _Handler(BaseHTTPRequestHandler):
    """Tři cesty: stránka, data a zdraví. Kukátko jen čte, nic nezapisuje."""

    def do_GET(self) -> None:  # noqa: N802 — jméno předepisuje http.server
        if self.path == "/":
            self._send(200, "text/html; charset=utf-8",
                       PAGE_PATH.read_bytes())
        elif self.path == "/health":
            self._send_json(200, {"ok": True, "current": CURRENT_PATH.is_file()})
        elif self.path.split("?")[0] == "/data":
            if CURRENT_PATH.is_file():
                payload = {
                    "stamp": CURRENT_PATH.stat().st_mtime_ns,
                    "record": json.loads(
                        CURRENT_PATH.read_text(encoding="utf-8")),
                }
            else:
                payload = {"stamp": None, "record": None}
            self._send_json(200, payload)
        else:
            self._send_json(404, {"error": {"type": "not_found",
                                            "message": self.path}})

    def _send_json(self, code: int, payload: dict) -> None:
        self._send(code, "application/json; charset=utf-8",
                   json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        # Mockup bez logovátka; provozní šum z kukátka nikoho nezajímá.
        pass


def main() -> None:
    try:
        server = ThreadingHTTPServer((HOST, PORT), _Handler)
    except OSError as e:
        sys.exit(f"kukátko nejde spustit na {HOST}:{PORT} ({e}); "
                 f"nejspíš už běží — zkus http://{HOST}:{PORT}/")
    print(f"cb-field kukátko na pole: http://{HOST}:{PORT}/  "
          f"(čte {CURRENT_PATH.relative_to(MODULE_DIR.parent)})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
