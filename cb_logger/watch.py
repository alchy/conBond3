"""Sledovací stránka: druhý listener, na kterém jde log sledovat v prohlížeči.

Je to **zákazník logovátka, ne jeho součást** (README-MODULES.md § 6). Čte tentýž
proud jako kdokoli jiný — přihlásí se jako odběratel ke službě — a nemá vlastní
cestu k datům. Kdyby sahala do souborů přímo, nešla by vypnout a rozešla by se
s tím, co vidí ostatní.

Tři rozhodnutí, která tvar stránky určují:

* **Jen čte.** Ze stránky nejde nic zapsat ani smazat. Je to okno, ne ovládání.
* **Soběstačná.** Žádný framework, žádné stahování z internetu, styl i skript
  uvnitř. Musí fungovat na stroji bez sítě.
* **Server-Sent Events, ne websockety.** SSE je obyčejné HTTP, zvládne ho
  standardní knihovna a prohlížeč si po výpadku sám obnoví spojení.
"""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from cb_logger import __version__
from cb_logger.service import LoggerService

#: Jak často se do proudu posílá komentář, když nic neteče. Drží spojení
#: otevřené proti prostředníkům, kteří tiché spojení zavírají, a hlavně dá
#: zapisovači šanci poznat, že prohlížeč zmizel.
HEARTBEAT_S = 15.0

#: Kolik záznamů se drží ve frontě jednoho okna, než se začnou zahazovat
#: nejstarší. Pomalý prohlížeč nesmí zdržet zápis do logu — okno, které
#: nestíhá, přijde o staré záznamy, ne systém o výkon.
QUEUE_LIMIT = 2000


def send_stream_headers(handler: BaseHTTPRequestHandler) -> None:
    """Odešle hlavičky nekonečného SSE proudu.

    **Proč `Transfer-Encoding: chunked`.** Odpověď HTTP/1.1 musí mít buď
    `Content-Length`, nebo být dělená na kusy. Nekonečný proud délku znát nemůže,
    takže zbývá druhá možnost — a bez ní příjemce neví, kde tělo končí, drží ho
    ve vyrovnávací paměti a **nepředá ho dál**.

    *(Naměřeno při stavbě: stránka se neaktualizovala živě, přestože server
    záznamy odesílal. Odpověď byla `HTTP/1.1` s `keep-alive`, bez `Content-Length`
    i bez `Transfer-Encoding` — tedy neplatná, a prohlížeč čekal na něco, co
    nikdy nepřišlo.)*
    """
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("Transfer-Encoding", "chunked")
    # Vypíná vyrovnávací paměť u případného prostředníka; bez toho by proud
    # mohl váznout i při správném rámcování.
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()


def write_chunk(handler: BaseHTTPRequestHandler, telo: bytes) -> None:
    """Zapíše jeden kus dělené odpovědi a hned ho vytlačí na soket.

    Formát kusu je délka šestnáctkově, `CRLF`, data, `CRLF`. Bez `flush` by
    data zůstala v zápisové vyrovnávací paměti a živý proud by nebyl živý.
    """
    handler.wfile.write(f"{len(telo):X}\r\n".encode("ascii"))
    handler.wfile.write(telo)
    handler.wfile.write(b"\r\n")
    handler.wfile.flush()


class WatchServer(ThreadingHTTPServer):
    """HTTP server sledovací stránky. Nese si službu a konfiguraci."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler_class, *, service: LoggerService,
                 config: dict[str, Any]):
        super().__init__(address, handler_class)
        self.service = service
        self.config = config


class WatchHandler(BaseHTTPRequestHandler):
    """Obsluha stránky a živého proudu."""

    server_version = "cb-logger-watch"
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
            # Zavřená záložka. Není to chyba serveru a nemá se hlásit.
            pass
        except Exception as e:  # noqa: BLE001 — poslední záchyt
            try:
                self.server.service.note_error(f"watch: {type(e).__name__}: {e}")
            except Exception:
                pass

    def _send_html(self, html: str) -> None:
        """Odešle stránku."""
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        # Stránka se mění jen s verzí modulu; ukládat ji do mezipaměti by
        # znamenalo, že po aktualizaci vidí člověk starou.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _stream(self) -> None:
        """Drží spojení a posílá záznamy, jak vznikají.

        Nově připojené okno dostane nejdřív obsah kruhového bufferu služby,
        aby nezačínalo u prázdna, a teprve pak živý proud.

        Fronta okna má strop a při přetečení zahazuje nejstarší. Pomalý
        prohlížeč tak nezdrží zápis do logu — a hlavně se **neodhlásí sám**
        vyhozením výjimky, což by ho tiše odpojilo právě ve chvíli, kdy se
        nejvíc děje.
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

        sluzba.subscribe(posli)
        try:
            for objekt in sluzba.recent():
                self._send_event(objekt)
            while True:
                try:
                    objekt = fronta.get(timeout=HEARTBEAT_S)
                except queue.Empty:
                    # Komentář v SSE. Prohlížeč ho ignoruje, ale zápis do
                    # soketu odhalí zavřenou záložku.
                    write_chunk(self, b": ping\n\n")
                    continue
                self._send_event(objekt)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            sluzba.unsubscribe(posli)

    def _send_event(self, objekt: dict[str, Any]) -> None:
        """Odešle jeden záznam jako SSE událost."""
        data = json.dumps(objekt, ensure_ascii=False)
        write_chunk(self, f"data: {data}\n\n".encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        """Umlčí výchozí výpis na chybový výstup (viz `api.py`)."""
        return


def make_watch_server(service: LoggerService,
                      config: dict[str, Any]) -> WatchServer | None:
    """Postaví server sledovací stránky, nebo `None`, když je vypnutá.

    Vrací se **nespuštěný**, aby si volající mohl přečíst skutečně přidělený
    port dřív, než začne obsluhovat.

    Vstup:
        service: doménová logika, ke které se stránka přihlásí jako odběratel.
        config: ověřená konfigurace.

    Výstup:
        `WatchServer`, nebo `None`, když je `module.watch.enabled` vypnuté.
        Že je vypnutá, musí být vidět v `GET /v1/health` — o to se stará
        `service.health()`.

    Při chybě:
        `OSError`, když je port obsazený.
    """
    watch = config["module"]["watch"]
    if not watch["enabled"]:
        return None
    return WatchServer(
        (config["service"]["host"], watch["port"]),
        WatchHandler,
        service=service,
        config=config,
    )


def _page(config: dict[str, Any]) -> str:
    """Sestaví soběstačnou HTML stránku.

    Proč se skládá v Pythonu a není to soubor vedle: do stránky se dosazují
    hodnoty z konfigurace (strop okna, port). Soubor by je musel dostat jinak
    a vznikla by druhá cesta ke konfiguraci.

    Vstup:
        config: ověřená konfigurace.

    Výstup:
        Kompletní HTML dokument. Všechen styl i skript uvnitř — stránka musí
        fungovat na stroji bez sítě.
    """
    watch = config["module"]["watch"]
    return _PAGE_TEMPLATE.replace("__WINDOW__", str(watch["window_records"])) \
                         .replace("__VERSION__", __version__) \
                         .replace("__PORT__", str(config["service"]["port"]))


_PAGE_TEMPLATE = """<!doctype html>
<html lang="cs" translate="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>cb-logger</title>
<style>
:root {
  --bg: #fbfbfa; --fg: #1a1a19; --dim: #6b6b66; --line: #e3e3df;
  --panel: #ffffff; --ok: #3d7f52; --empty: #8a7f3d; --skip: #5b6b8a;
  --err: #b3453a; --bad: #8a2f8a;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16171a; --fg: #e6e6e3; --dim: #8d8d88; --line: #2a2c31;
    --panel: #1c1e22; --ok: #6fbf85; --empty: #c9b45e; --skip: #8fa5cf;
    --err: #e0796c; --bad: #d18ad1;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
}
header {
  position: sticky; top: 0; z-index: 2; background: var(--panel);
  border-bottom: 1px solid var(--line); padding: 10px 14px;
  display: flex; gap: 14px; align-items: center; flex-wrap: wrap;
}
h1 { font-size: 13px; margin: 0; font-weight: 600; letter-spacing: .04em; }
h1 span { color: var(--dim); font-weight: 400; }
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
main { padding: 0 0 40px; }
table { width: 100%; border-collapse: collapse; }
th {
  text-align: left; font-weight: 500; color: var(--dim); font-size: 11px;
  letter-spacing: .06em; text-transform: uppercase; padding: 8px 10px;
  border-bottom: 1px solid var(--line); position: sticky; top: 41px;
  background: var(--bg);
}
td { padding: 4px 10px; border-bottom: 1px solid var(--line);
     vertical-align: top; white-space: nowrap; }
td.io { white-space: normal; word-break: break-word; color: var(--dim);
        max-width: 40vw; }
.zprava { color: var(--fg); }
tr:hover td { background: var(--panel); }
.cas { color: var(--dim); }
.stopa { color: var(--dim); }
.stopa.chybi { color: var(--err); font-style: italic; }
.st { font-weight: 600; }
.st-ok { color: var(--ok); } .st-empty { color: var(--empty); }
.st-skipped { color: var(--skip); } .st-error { color: var(--err); }
tr.spatny { background: color-mix(in srgb, var(--bad) 12%, transparent); }
tr.spatny td:first-child { border-left: 3px solid var(--bad); }
.znacka { color: var(--bad); font-weight: 600; }
.prazdno { padding: 30px 14px; color: var(--dim); }
#dolu { position: fixed; right: 16px; bottom: 16px; display: none;
        box-shadow: 0 2px 8px rgba(0,0,0,.25); z-index: 4; }
#dolu.videt { display: block; }
</style>
</head>
<body>
<header>
  <h1>cb-logger <span>__VERSION__ · API :__PORT__</span></h1>
  <input id="filtr" placeholder="filtr: component, method, trace, message…" size="30">
  <select id="uroven">
    <option value="">level: vše</option>
    <option value="info">info</option>
    <option value="debug">debug</option>
  </select>
  <select id="stav">
    <option value="">result: vše</option>
    <option value="ok">ok</option>
    <option value="empty">empty</option>
    <option value="skipped">skipped</option>
    <option value="error">error</option>
  </select>
  <button id="jenSpatne" aria-pressed="false">jen vadné</button>
  <button id="pauza" aria-pressed="false">pauza</button>
  <button id="smaz">smazat okno</button>
  <div class="stav">
    <span><i id="tecka" class="tecka"></i><span id="spojeni">připojuji…</span></span>
    <span id="pocty">0 / 0</span>
  </div>
</header>

<main>
  <table>
    <thead><tr>
      <th>ts</th><th>level</th><th>component</th><th>method</th>
      <th>trace</th><th>result</th><th>ms</th><th>message · input → output</th>
    </tr></thead>
    <tbody id="telo"></tbody>
  </table>
  <div id="prazdno" class="prazdno">Zatím nic nepřiteklo.</div>
</main>
<button id="dolu" title="skočit na nejnovější">↓ nové záznamy</button>

<script>
"use strict";
// Strop okna z konfigurace modulu. Bez něj by stránka nechaná otevřená přes
// noc narostla o statisíce řádků a prohlížeč by se zadrhl — zrovna ve chvíli,
// kdy se něco děje a člověk se na ni dívá.
const OKNO = __WINDOW__;

const telo = document.getElementById("telo");
const prazdno = document.getElementById("prazdno");
const poctyEl = document.getElementById("pocty");
const tecka = document.getElementById("tecka");
const spojeniEl = document.getElementById("spojeni");
const filtrEl = document.getElementById("filtr");
const urovenEl = document.getElementById("uroven");
const stavEl = document.getElementById("stav");
const jenSpatneEl = document.getElementById("jenSpatne");
const pauzaEl = document.getElementById("pauza");

let zaznamy = [];          // okno záznamů, nejnovější na konci
let pozastaveno = false;
let cekajici = [];         // co přiteklo během pauzy

// --- autoscroll ---------------------------------------------------------
// Nejnovější záznam má být vidět bez rolování. Drží se ale zásada, že
// samočinné rolování nesmí přebít člověka: jakmile odroluje nahoru (čte něco
// staršího), autoscroll se vypne a nabídne se tlačítko zpět dolů. Bez toho
// by se text pod rukama uhýbal a nešlo by nic přečíst.
const dolu = document.getElementById("dolu");
let drzetDole = true;

function uDna() {
  // 40 px tolerance: po doskrolování bývá zbytek pár pixelů a přísná
  // rovnost by autoscroll vypnula hned po prvním záznamu.
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

function sekundy(ts) {
  return typeof ts === "string" ? ts.slice(11, 23) : "";
}

function shrnuti(o) {
  const kus = (v) => {
    if (v === undefined || v === null) return "";
    const s = JSON.stringify(v);
    return s.length > 120 ? s.slice(0, 117) + "…" : s;
  };
  const vstup = kus(o.input), vystup = kus(o.output);
  if (!vstup && !vystup) return "";
  return vstup + (vystup ? "  →  " + vystup : "");
}

function vyhovuje(o) {
  if (jenSpatneEl.getAttribute("aria-pressed") === "true"
      && !o.malformed && o.result !== "error") return false;
  if (urovenEl.value && o.level !== urovenEl.value) return false;
  if (stavEl.value && o.result !== stavEl.value) return false;
  const q = filtrEl.value.trim().toLowerCase();
  if (!q) return true;
  return [o.component, o.method, o.trace, o.message, o.malformed_reason]
    .some((v) => typeof v === "string" && v.toLowerCase().includes(q));
}

function radek(o) {
  const tr = document.createElement("tr");
  if (o.malformed) tr.className = "spatny";
  const bunka = (text, trida) => {
    const td = document.createElement("td");
    if (trida) td.className = trida;
    td.textContent = text;
    return td;
  };
  tr.append(
    bunka(sekundy(o.ts), "cas"),
    bunka(o.level || "", "cas"),
    bunka(o.component || "", ""),
    bunka(o.method || "", ""),
  );
  const stopa = bunka(o.trace || "— bez stopy", o.trace ? "stopa" : "stopa chybi");
  tr.append(stopa);
  const st = bunka(o.result || "", "st st-" + (o.result || ""));
  tr.append(st);
  tr.append(bunka(o.duration_ms === undefined ? "" : String(o.duration_ms), "cas"));
  const io = bunka(shrnuti(o), "io");
  // Volná hláška před shrnutím a v barvě textu: je to to, co člověk čte
  // jako první, když hledá, co se stalo.
  if (o.message) {
    const zprava = document.createElement("span");
    zprava.className = "zprava";
    zprava.textContent = o.message + (io.textContent ? "   " : "");
    io.prepend(zprava);
  }
  if (o.malformed) {
    const znacka = document.createElement("span");
    znacka.className = "znacka";
    znacka.textContent = "VADNÝ: " + (o.malformed_reason || "") + "  ";
    io.prepend(znacka);
  }
  tr.append(io);
  return tr;
}

function prekresli() {
  telo.replaceChildren();
  let videno = 0;
  for (const o of zaznamy) {
    if (!vyhovuje(o)) continue;
    telo.append(radek(o));
    videno++;
  }
  poctyEl.textContent = videno + " / " + zaznamy.length;
  prazdno.style.display = zaznamy.length ? "none" : "block";
  if (drzetDole) skrolDolu();
}

function pridej(o) {
  zaznamy.push(o);
  // Odsun nejstarších při překročení stropu okna.
  if (zaznamy.length > OKNO) zaznamy.splice(0, zaznamy.length - OKNO);
  if (!vyhovuje(o)) { poctyEl.textContent = telo.childElementCount + " / " + zaznamy.length; return; }
  telo.append(radek(o));
  while (telo.childElementCount > OKNO) telo.firstElementChild.remove();
  poctyEl.textContent = telo.childElementCount + " / " + zaznamy.length;
  prazdno.style.display = "none";
  if (drzetDole) skrolDolu();
}

for (const el of [filtrEl, urovenEl, stavEl]) {
  el.addEventListener("input", prekresli);
}
for (const el of [jenSpatneEl]) {
  el.addEventListener("click", () => {
    el.setAttribute("aria-pressed",
      el.getAttribute("aria-pressed") === "true" ? "false" : "true");
    prekresli();
  });
}
pauzaEl.addEventListener("click", () => {
  pozastaveno = !pozastaveno;
  pauzaEl.setAttribute("aria-pressed", String(pozastaveno));
  if (!pozastaveno) {
    for (const o of cekajici) pridej(o);
    cekajici = [];
  }
});
document.getElementById("smaz").addEventListener("click", () => {
  zaznamy = []; cekajici = []; prekresli();
});

const proud = new EventSource("/stream");
proud.onopen = () => {
  tecka.classList.add("zivy");
  spojeniEl.textContent = "živě";
};
proud.onerror = () => {
  tecka.classList.remove("zivy");
  // EventSource se pokouší připojit sám; není co dělat, jen to říct.
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
