"""Kukátko na logované JSON objekty — třetí listener modulu.

Princip je stejný jako u textového kukátka (`watch.py`): objekty se posouvají,
jak přitékají, nejnovější dole, přes Server-Sent Events. Rozdíl je v tom, čím
je řádek — u textu je to řádek, tady je to **rozbalitelný strom**.

Proč vlastní port a ne záložka v témž okně: jsou to dva různé pohledy na dvě
různá data. Textový log se čte souvisle a zajímá u něj sled; objektový se čte
po jednom a zajímá u něj obsah. Sloučit je do jedné stránky znamená, že ani
jeden nejde nechat otevřený přes celou obrazovku — a přesně tak se používají.

Vykreslení stromu je vlastní, ne převzaté: strom má jen tři druhy uzlů
(objekt, pole, list) a napsat je zabere míň místa než jakákoli knihovna, kterou
bychom stejně nesměli stahovat ze sítě.
"""

from __future__ import annotations

import json
import queue
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from cb_logger import __version__
from cb_logger.service import LoggerService
from cb_logger.watch import (
    HEARTBEAT_S,
    QUEUE_LIMIT,
    send_stream_headers,
    write_chunk,
)


class ObjectWatchServer(ThreadingHTTPServer):
    """HTTP server kukátka na objekty."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler_class, *, service: LoggerService,
                 config: dict[str, Any]):
        super().__init__(address, handler_class)
        self.service = service
        self.config = config


class ObjectWatchHandler(BaseHTTPRequestHandler):
    """Obsluha stránky a živého proudu objektů."""

    server_version = "cb-logger-objects"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        cesta = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if cesta == "/":
                self._send_html(_page(self.server.config))
            elif cesta == "/stream":
                self._stream()
            else:
                self.send_error(404, "neznámá cesta")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001 — poslední záchyt
            try:
                self.server.service.note_error(
                    f"watch-objects: {type(e).__name__}: {e}"
                )
            except Exception:
                pass

    def _send_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _stream(self) -> None:
        """Drží spojení a posílá objekty, jak vznikají.

        Stejná mechanika jako v `watch.py`: nově připojené okno dostane obsah
        kruhového bufferu a pak živý proud; fronta okna má strop a při
        přetečení zahazuje nejstarší, aby pomalý prohlížeč nezdržel zápis.
        """
        sluzba: LoggerService = self.server.service
        fronta: queue.Queue = queue.Queue(maxsize=QUEUE_LIMIT)

        def posli(objekt: dict[str, Any]) -> None:
            try:
                fronta.put_nowait(objekt)
            except queue.Full:
                try:
                    fronta.get_nowait()
                except queue.Empty:
                    pass
                try:
                    fronta.put_nowait(objekt)
                except queue.Full:
                    pass

        send_stream_headers(self)

        sluzba.subscribe_objects(posli)
        try:
            for objekt in sluzba.recent_objects():
                self._send_event(objekt)
            while True:
                try:
                    objekt = fronta.get(timeout=HEARTBEAT_S)
                except queue.Empty:
                    write_chunk(self, b": ping\n\n")
                    continue
                self._send_event(objekt)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            sluzba.unsubscribe_objects(posli)

    def _send_event(self, objekt: dict[str, Any]) -> None:
        data = json.dumps(objekt, ensure_ascii=False)
        write_chunk(self, f"data: {data}\n\n".encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        return


def make_object_watch_server(
    service: LoggerService, config: dict[str, Any]
) -> ObjectWatchServer | None:
    """Postaví server kukátka na objekty, nebo `None`, když je vypnuté.

    Řídí se týmž přepínačem `module.watch.enabled` jako textové kukátko:
    vypnout jedno a nechat druhé by znamenalo dvě zdůvodnění tam, kde stačí
    jedno — na stroji bez displeje jsou zbytečná obě.

    Vstup:
        service: doménová logika, ke které se kukátko přihlásí jako odběratel.
        config: ověřená konfigurace.

    Výstup:
        `ObjectWatchServer`, nebo `None`. Vrací se nespuštěný.

    Při chybě:
        `OSError`, když je port obsazený.
    """
    watch = config["module"]["watch"]
    if not watch["enabled"]:
        return None
    return ObjectWatchServer(
        (config["service"]["host"], watch["objects_port"]),
        ObjectWatchHandler,
        service=service,
        config=config,
    )


def _page(config: dict[str, Any]) -> str:
    """Sestaví soběstačnou HTML stránku kukátka na objekty."""
    watch = config["module"]["watch"]
    return _PAGE_TEMPLATE \
        .replace("__WINDOW__", str(watch["window_records"])) \
        .replace("__VERSION__", __version__) \
        .replace("__TEXTPORT__", str(watch["port"]))


_PAGE_TEMPLATE = """<!doctype html>
<html lang="cs" translate="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>cb-logger · objekty</title>
<style>
:root {
  --bg: #fbfbfa; --fg: #1a1a19; --dim: #6b6b66; --line: #e3e3df;
  --panel: #ffffff; --ok: #3d7f52; --bad: #8a2f8a; --err: #b3453a;
  --klic: #3f5fa8; --text: #3d7f52; --cislo: #a5622b; --bool: #7a4fa8;
  --null: #8d8d88;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16171a; --fg: #e6e6e3; --dim: #8d8d88; --line: #2a2c31;
    --panel: #1c1e22; --ok: #6fbf85; --bad: #d18ad1; --err: #e0796c;
    --klic: #8fb0e8; --text: #8fd6a4; --cislo: #dda06a; --bool: #bda2e8;
    --null: #6f6f6a;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 13px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace;
}
header {
  position: sticky; top: 0; z-index: 3; background: var(--panel);
  border-bottom: 1px solid var(--line); padding: 10px 14px;
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
}
h1 { font-size: 13px; margin: 0; font-weight: 600; letter-spacing: .04em; }
h1 span { color: var(--dim); font-weight: 400; }
a { color: var(--dim); }
input, select, button {
  font: inherit; background: var(--bg); color: var(--fg);
  border: 1px solid var(--line); border-radius: 4px; padding: 3px 7px;
}
button { cursor: pointer; }
button[aria-pressed="true"] { border-color: var(--fg); }
.stav { margin-left: auto; color: var(--dim); display: flex; gap: 12px; }
.tecka { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
         background: var(--err); margin-right: 5px; vertical-align: middle; }
.tecka.zivy { background: var(--ok); }

main { padding: 12px 14px 60px; display: flex; flex-direction: column; gap: 8px; }
.karta { border: 1px solid var(--line); border-radius: 6px;
         background: var(--panel); overflow: hidden; }
.karta.vadna { border-color: var(--bad); }
.hlava { display: flex; gap: 10px; align-items: baseline; padding: 6px 10px;
         cursor: pointer; user-select: none; flex-wrap: wrap; }
.hlava:hover { background: color-mix(in srgb, var(--fg) 4%, transparent); }
.sipka { color: var(--dim); width: 10px; display: inline-block; }
.stitek { font-weight: 600; }
.kdo { color: var(--dim); }
.cas { color: var(--dim); margin-left: auto; }
.stopa { color: var(--dim); }
.stopa.chybi { color: var(--err); font-style: italic; }
.znacka { color: var(--bad); font-weight: 600; }
.velikost { color: var(--dim); }
.telo { padding: 6px 10px 10px 26px; border-top: 1px solid var(--line);
        overflow-x: auto; }
.telo[hidden] { display: none; }

.uzel { padding-left: 14px; border-left: 1px solid var(--line); }
.radek { white-space: nowrap; }
.prep { cursor: pointer; user-select: none; color: var(--dim);
        display: inline-block; width: 12px; }
.k { color: var(--klic); }
.s { color: var(--text); }
.n { color: var(--cislo); }
.b { color: var(--bool); }
.nu { color: var(--null); font-style: italic; }
.pocet { color: var(--dim); }
.rez { color: var(--bad); font-style: italic; }
.prazdno { padding: 30px 0; color: var(--dim); }
#dolu { position: fixed; right: 16px; bottom: 16px; display: none;
        box-shadow: 0 2px 8px rgba(0,0,0,.25); z-index: 4; }
#dolu.videt { display: block; }
</style>
</head>
<body>
<header>
  <h1>cb-logger <span>objekty · __VERSION__</span></h1>
  <a href="http://127.0.0.1:__TEXTPORT__" title="kukátko na textový log">→ text</a>
  <input id="filtr" placeholder="filtr: label, component, method, trace…" size="28">
  <button id="rozbal" aria-pressed="false">rozbalit nové</button>
  <button id="pauza" aria-pressed="false">pauza</button>
  <button id="smaz">smazat okno</button>
  <div class="stav">
    <span><i id="tecka" class="tecka"></i><span id="spojeni">připojuji…</span></span>
    <span id="pocty">0 / 0</span>
  </div>
</header>

<main id="hlavni"><div id="prazdno" class="prazdno">Zatím nepřitekl žádný objekt.</div></main>
<button id="dolu" title="skočit na nejnovější">↓ nové objekty</button>

<script>
"use strict";
const OKNO = __WINDOW__;

const hlavni = document.getElementById("hlavni");
const prazdno = document.getElementById("prazdno");
const poctyEl = document.getElementById("pocty");
const tecka = document.getElementById("tecka");
const spojeniEl = document.getElementById("spojeni");
const filtrEl = document.getElementById("filtr");
const rozbalEl = document.getElementById("rozbal");
const pauzaEl = document.getElementById("pauza");

let objekty = [];
let pozastaveno = false;
let cekajici = [];

// --- autoscroll ---------------------------------------------------------
// Stejná zásada jako u textového kukátka: nejnovější je vidět bez rolování,
// ale jakmile člověk odroluje nahoru, autoscroll se vypne. U objektů to platí
// dvojnásob — rozbalený strom se čte dlouho a uhýbat se nesmí.
const dolu = document.getElementById("dolu");
let drzetDole = true;

function uDna() {
  return window.innerHeight + window.scrollY >= document.body.scrollHeight - 40;
}

function skrolDolu() {
  window.scrollTo({ top: document.body.scrollHeight });
}

window.addEventListener("scroll", () => {
  drzetDole = uDna();
  dolu.classList.toggle("videt", !drzetDole);
}, { passive: true });

dolu.addEventListener("click", () => {
  drzetDole = true;
  dolu.classList.remove("videt");
  skrolDolu();
});

function cas(ts) { return typeof ts === "string" ? ts.slice(11, 23) : ""; }

function bajty(n) {
  if (typeof n !== "number") return "";
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " kB";
  return (n / 1048576).toFixed(1) + " MB";
}

// --- vykreslení stromu ---------------------------------------------------
// Tři druhy uzlů: objekt, pole, list. Víc jich JSON nemá, takže vlastní
// vykreslení je kratší než jakákoli knihovna — a hlavně nic nestahuje.

function listovaHodnota(v) {
  const s = document.createElement("span");
  if (v === null) { s.className = "nu"; s.textContent = "null"; return s; }
  switch (typeof v) {
    case "string": s.className = "s"; s.textContent = JSON.stringify(v); break;
    case "number": s.className = "n"; s.textContent = String(v); break;
    case "boolean": s.className = "b"; s.textContent = String(v); break;
    default: s.textContent = String(v);
  }
  // Značka uříznuté větve se odliší, ať je poznat, že tam data byla.
  if (typeof v === "string" && v.startsWith("… hlouběji než")) s.className = "rez";
  return s;
}

function vetev(klic, hodnota, hloubka) {
  const obal = document.createElement("div");
  obal.className = "uzel";
  const radek = document.createElement("div");
  radek.className = "radek";

  const slozeny = hodnota !== null && typeof hodnota === "object";
  const prep = document.createElement("span");
  prep.className = "prep";
  radek.append(prep);

  if (klic !== null) {
    const k = document.createElement("span");
    k.className = "k";
    k.textContent = klic + ": ";
    radek.append(k);
  }

  if (!slozeny) {
    radek.append(listovaHodnota(hodnota));
    obal.append(radek);
    return obal;
  }

  const pole = Array.isArray(hodnota);
  const polozky = pole ? hodnota.map((v, i) => [String(i), v])
                       : Object.entries(hodnota);
  const shrn = document.createElement("span");
  shrn.className = "pocet";
  shrn.textContent = pole ? `[${polozky.length}]` : `{${polozky.length}}`;
  radek.append(shrn);

  const deti = document.createElement("div");
  // Zabalené hluboko dole: první dvě úrovně otevřené, zbytek na kliknutí.
  // Rozbalit všechno u velkého objektu znamená stránku, ve které se nedá nic
  // najít; nechat všechno zabalené znamená pět kliknutí, než něco uvidíš.
  let otevreno = hloubka < 2;
  deti.hidden = !otevreno;
  prep.textContent = otevreno ? "▾" : "▸";
  prep.addEventListener("click", (e) => {
    e.stopPropagation();
    otevreno = !otevreno;
    deti.hidden = !otevreno;
    prep.textContent = otevreno ? "▾" : "▸";
  });

  for (const [k, v] of polozky) deti.append(vetev(k, v, hloubka + 1));
  obal.append(radek, deti);
  return obal;
}

function karta(o) {
  const el = document.createElement("div");
  el.className = "karta" + (o.malformed ? " vadna" : "");

  const hlava = document.createElement("div");
  hlava.className = "hlava";
  const sipka = document.createElement("span");
  sipka.className = "sipka";
  const stitek = document.createElement("span");
  stitek.className = "stitek";
  stitek.textContent = o.label || o.kind || "?";
  const kdo = document.createElement("span");
  kdo.className = "kdo";
  kdo.textContent = (o.component || "?") + " · " + (o.method || "?");
  const stopa = document.createElement("span");
  stopa.className = o.trace ? "stopa" : "stopa chybi";
  stopa.textContent = o.trace || "— bez stopy";
  const vel = document.createElement("span");
  vel.className = "velikost";
  vel.textContent = bajty(o.bytes);
  const casEl = document.createElement("span");
  casEl.className = "cas";
  casEl.textContent = cas(o.ts);
  hlava.append(sipka, stitek, kdo, stopa, vel);

  if (o.malformed || o.truncated || o.depth_limited) {
    const zn = document.createElement("span");
    zn.className = "znacka";
    zn.textContent = o.malformed ? "VADNÝ: " + (o.malformed_reason || "")
      : (o.truncated ? "ZKRÁCENO" : "OŘÍZNUTA HLOUBKA");
    hlava.append(zn);
  }
  hlava.append(casEl);

  const telo = document.createElement("div");
  telo.className = "telo";
  telo.append(vetev(null, o.object === undefined ? null : o.object, 0));

  let otevreno = rozbalEl.getAttribute("aria-pressed") === "true" || !!o.malformed;
  telo.hidden = !otevreno;
  sipka.textContent = otevreno ? "▾" : "▸";
  hlava.addEventListener("click", () => {
    otevreno = !otevreno;
    telo.hidden = !otevreno;
    sipka.textContent = otevreno ? "▾" : "▸";
  });

  el.append(hlava, telo);
  return el;
}

function vyhovuje(o) {
  const q = filtrEl.value.trim().toLowerCase();
  if (!q) return true;
  return [o.label, o.kind, o.component, o.method, o.trace]
    .some((v) => typeof v === "string" && v.toLowerCase().includes(q));
}

function prekresli() {
  hlavni.replaceChildren();
  let videno = 0;
  for (const o of objekty) {
    if (!vyhovuje(o)) continue;
    hlavni.append(karta(o));
    videno++;
  }
  if (!objekty.length) hlavni.append(prazdno);
  poctyEl.textContent = videno + " / " + objekty.length;
  if (drzetDole) skrolDolu();
}

function pridej(o) {
  objekty.push(o);
  if (objekty.length > OKNO) objekty.splice(0, objekty.length - OKNO);
  if (prazdno.parentNode) prazdno.remove();
  if (vyhovuje(o)) {
    hlavni.append(karta(o));
    while (hlavni.childElementCount > OKNO) hlavni.firstElementChild.remove();
  }
  poctyEl.textContent = hlavni.childElementCount + " / " + objekty.length;
  if (drzetDole) skrolDolu();
}

filtrEl.addEventListener("input", prekresli);
rozbalEl.addEventListener("click", () => {
  const stav = rozbalEl.getAttribute("aria-pressed") === "true";
  rozbalEl.setAttribute("aria-pressed", String(!stav));
});
pauzaEl.addEventListener("click", () => {
  pozastaveno = !pozastaveno;
  pauzaEl.setAttribute("aria-pressed", String(pozastaveno));
  if (!pozastaveno) { for (const o of cekajici) pridej(o); cekajici = []; }
});
document.getElementById("smaz").addEventListener("click", () => {
  objekty = []; cekajici = []; prekresli();
});

const proud = new EventSource("/stream");
proud.onopen = () => { tecka.classList.add("zivy"); spojeniEl.textContent = "živě"; };
proud.onerror = () => {
  tecka.classList.remove("zivy");
  spojeniEl.textContent = "odpojeno, zkouším znovu…";
};
proud.onmessage = (e) => {
  let o;
  try { o = JSON.parse(e.data); } catch (_) { return; }
  if (pozastaveno) { cekajici.push(o); return; }
  pridej(o);
};
</script>
</body>
</html>
"""
