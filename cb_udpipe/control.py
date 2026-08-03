"""Ovládání služby: start, stop, restart, reload, status.

Proti ostatním modulům je tu jedna práce navíc: cb-udpipe **provozuje cizí
proces** — vlastní instanci UDPipe 2. Ta se zvedá první a skládá poslední,
protože bez ní naše služba nemá co obsluhovat (README-MODULES.md § 19).

```
start   1 · ověří konfiguraci        (udělal už `main`)
        2 · ověří model a RobeCzech  → jinak exit 2 s návodem
        3 · zvedne UDPipe na 42201   → HF_HOME dovnitř, offline natvrdo
        4 · počká, až odpoví /models
        5 · zvedne naši službu na 42200
        6 · počká na /version a /v1/health
```

`stop` je ukončí v opačném pořadí. Že UDPipe neběží, je vidět v `/v1/health`
jako nedostupná **povinná** závislost, tedy `503`.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from cb_udpipe import api, service
from cb_udpipe.config import MODULE_DIR, ConfigError, load

#: Návratové kódy. Ovládání se volá ze skriptů a z testů, takže musí být
#: spolehlivé (README-MODULES.md § 12).
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BAD_USAGE = 2
EXIT_NOT_RUNNING = 3

#: Ovládací program v kořeni projektu. Sem se `start` odkazuje, když se
#: odpojuje na pozadí.
LAUNCHER = MODULE_DIR.parent / "cb-udpipe.py"

#: Skript, který pořídí model. Je součástí chybové hlášky — bez něj si každý
#: musí pamatovat, jak se model získává (README-MODULES.md § 19).
FETCH_SCRIPT = MODULE_DIR / "scripts" / "fetch-models.sh"

#: Kolik sekund se čeká na naši službu. UDPipe má vlastní, delší strop
#: v konfiguraci — načítá model o 357 MB.
START_TIMEOUT_S = 15.0

#: Jak často se kontroluje, jestli už služba odpovídá.
POLL_S = 0.1

#: Kolik jader se nechá systému, když se počet vláken odvozuje. Bez rezervy
#: stroj při rozboru zamrzne (převzato z conBondu2, `udpipe.sh`).
JADRA_SYSTEMU = 2


def main(argv: list[str] | None = None) -> int:
    """Zpracuje argumenty a provede příkaz. Vrací návratový kód."""
    parser = argparse.ArgumentParser(
        prog="cb-udpipe.py", description="Ovládání služby cb-udpipe.",
    )
    pod = parser.add_subparsers(dest="prikaz", required=True)

    p = pod.add_parser("start", help="spustí UDPipe a službu")
    p.add_argument("--config", help="cesta ke konfiguraci")
    p.add_argument("--foreground", action="store_true",
                   help="běží v terminálu bez odpojení")

    p = pod.add_parser("stop", help="zastaví službu a UDPipe")
    p.add_argument("--config", help="cesta ke konfiguraci")
    p.add_argument("--timeout", type=float,
                   help="kolik sekund čekat na ukončení")

    p = pod.add_parser("restart", help="zastaví a spustí")
    p.add_argument("--config", help="cesta ke konfiguraci")

    p = pod.add_parser("reload", help="znovu načte konfiguraci bez ztráty stavu")
    p.add_argument("--config", help="cesta ke konfiguraci")

    p = pod.add_parser("status", help="stav služby včetně portů")
    p.add_argument("--config", help="cesta ke konfiguraci")
    p.add_argument("--json", action="store_true", help="strojově čitelný tvar")

    args = parser.parse_args(argv)

    try:
        config = load(args.config)
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        return EXIT_BAD_USAGE

    if args.prikaz == "start":
        return cmd_start(config, foreground=args.foreground,
                         config_path=args.config)
    if args.prikaz == "stop":
        return cmd_stop(config, timeout=args.timeout)
    if args.prikaz == "restart":
        kod = cmd_stop(config, timeout=None)
        # `restart` na neběžící službu se chová jako `start`, ne jako chyba.
        if kod not in (EXIT_OK, EXIT_NOT_RUNNING):
            return kod
        return cmd_start(config, foreground=False, config_path=args.config)
    if args.prikaz == "reload":
        return cmd_reload(config)
    if args.prikaz == "status":
        return cmd_status(config, jako_json=args.json)
    return EXIT_BAD_USAGE


# ------------------------------------------------------------------ start


def cmd_start(config: dict[str, Any], *, foreground: bool,
              config_path: str | None) -> int:
    """Spustí UDPipe a nad ním naši službu.

    Data se kontrolují **před** spuštěním. Služba, která naběhla napůl, je
    horší než služba, která nenaběhla (README-MODULES.md § 9) — a u modelu
    o 357 MB je rozdíl mezi „chybí soubor" a „TensorFlow spadl po dvou
    minutách" celá minuta hledání.
    """
    bezici = _running_pid(config)
    if bezici is not None:
        print(f"cb-udpipe už běží (pid {bezici}, port {_port(config)})")
        return EXIT_OK

    chybi = _zkontroluj_data(config["module"]["upstream"])
    if chybi:
        print("\n".join(chybi), file=sys.stderr)
        return EXIT_BAD_USAGE

    if foreground:
        return _serve(config)

    prikaz = [sys.executable, str(LAUNCHER), "start", "--foreground"]
    if config_path:
        prikaz += ["--config", config_path]
    try:
        subprocess.Popen(prikaz, start_new_session=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError as e:
        print(f"nepodařilo se spustit {LAUNCHER}: {e}", file=sys.stderr)
        return EXIT_FAILED

    if _cekej_na_version(config, START_TIMEOUT_S) is None:
        print(
            f"cb-udpipe nenaběhl do {START_TIMEOUT_S:.0f} s\n"
            f"  konfigurace: {config['_meta']['path']}\n"
            f"  log UDPipe:  {_udpipe_log(config)}",
            file=sys.stderr,
        )
        return EXIT_FAILED

    print(f"cb-udpipe běží — API {_endpoint(config)}, "
          f"UDPipe {_upstream_endpoint(config)}")
    return EXIT_OK


def _zkontroluj_data(upstream: dict[str, Any]) -> list[str]:
    """Ověří, že jsou na disku všechna velká data a zdrojáky.

    Vrací **seznam** hlášek, ne první nález: když chybí model, chybí obvykle
    i RobeCzech, a dozvědět se to na dvakrát znamená dvakrát čekat.

    Vstup:
        upstream: blok `module.upstream` z konfigurace.

    Výstup:
        Seznam českých hlášek. Prázdný seznam znamená, že je vše na místě.
        Každá hláška uvádí očekávanou cestu **a skript, který data pořídí**.

    Při chybě:
        Nevyhazuje.
    """
    chyby: list[str] = []

    model = Path(upstream["model_dir"])
    if not model.is_dir():
        chyby.append(
            f"cb-udpipe: chybí model\n"
            f"  očekáváno:  {model}\n"
            f"  pořídíš:    {FETCH_SCRIPT}"
        )

    robeczech = Path(upstream["hf_home"]) / "hub" / \
        "models--ufal--robeczech-base"
    if not robeczech.is_dir():
        chyby.append(
            f"cb-udpipe: chybí embedding model RobeCzech\n"
            f"  očekáváno:  {robeczech}\n"
            f"  pořídíš:    {FETCH_SCRIPT}\n"
            f"  Bez něj si UDPipe sáhne na HuggingFace a bez sítě spadne."
        )

    server = Path(upstream["vendor_dir"]) / "udpipe2_server.py"
    if not server.is_file():
        chyby.append(
            f"cb-udpipe: chybí zdrojáky UDPipe 2\n"
            f"  očekáváno:  {server}\n"
            f"  pořídíš:    git submodule update --init"
        )
    return chyby


def _serve(config: dict[str, Any]) -> int:
    """Zvedne UDPipe, pak naši službu, a běží, dokud nepřijde signál.

    Pořadí je významné: kdyby se naše služba zvedla první, odpovídala by
    `503` na každý dotaz, dokud UDPipe nenaběhne — a `start` by mezitím
    ohlásil úspěch.
    """
    upstream_cfg = config["module"]["upstream"]
    proces = _spust_udpipe(config)
    if proces is None:
        return EXIT_FAILED

    try:
        if not _cekej_na_udpipe(config, upstream_cfg["start_timeout_s"]):
            print(f"UDPipe nenaběhl do {upstream_cfg['start_timeout_s']:.0f} s"
                  f" — log: {_udpipe_log(config)}", file=sys.stderr)
            _zastav_proces(proces, 10.0)
            return EXIT_FAILED

        sluzba = service.UdpipeService(config, log=_logovatko(config))
        server = api.make_api_server(sluzba, config=config)
        skutecny_port = server.server_address[1]
        _zapis_stav(config, pid=os.getpid(), port=skutecny_port,
                    udpipe_pid=proces.pid)

        if upstream_cfg["warmup"]:
            _predehrej(sluzba, upstream_cfg["warmup_sentence"])

        hotovo = threading.Event()
        _nastav_signaly(hotovo, config)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"cb-udpipe naslouchá na {config['service']['host']}:"
              f"{skutecny_port}")
        hotovo.wait()

        server.shutdown()
        server.server_close()
        sluzba.close()
        return EXIT_OK
    finally:
        _zastav_proces(proces, config["runtime"]["stop_timeout_s"])
        _uklid_stav(config)


def _spust_udpipe(config: dict[str, Any]) -> subprocess.Popen | None:
    """Spustí vlastní instanci UDPipe 2 jako samostatný proces.

    Hranice vede po procesu, ne po prostředí: to, že v `.venv` leží
    TensorFlow, neznamená, že si ho smí naimportovat náš kód
    (README-MODULES.md § 19).

    Výstup:
        `Popen`, nebo `None`, když se proces nepodařilo spustit.

    Při chybě:
        Nevyhazuje — hlášku vypíše a vrátí `None`.
    """
    u = config["module"]["upstream"]
    vendor = Path(u["vendor_dir"])
    log_cesta = _udpipe_log(config)
    log_cesta.parent.mkdir(parents=True, exist_ok=True)

    prikaz = [
        sys.executable, "udpipe2_server.py", str(u["port"]),
        f"--threads={_vlakna(u)}",
        "czech",
        f"{u['model']}:cs:ces:cze",
        str(Path(u["model_dir"]).resolve()),
        "cs_pdtc",
        "https://ufal.mff.cuni.cz/udpipe/2/models",
    ]
    prostredi = {**os.environ, **_prostredi_udpipe(u)}

    try:
        log = log_cesta.open("a", encoding="utf-8")
        return subprocess.Popen(
            prikaz, cwd=str(vendor), env=prostredi,
            stdout=log, stderr=subprocess.STDOUT,
        )
    except OSError as e:
        print(f"nepodařilo se spustit UDPipe: {e}", file=sys.stderr)
        return None


def _logovatko(config: dict[str, Any]) -> Any:
    """Postaví klienta logovátka, nebo vrátí `None`.

    Logovátko je **nepovinná** závislost (README-MODULES.md § 4): když neběží,
    jeho klient to ohlásí na chybový výstup, přepne se do spool režimu a nechá
    nás běžet. Kdyby padlé logovátko shodilo modul, byla by nejméně důležitá
    součást zároveň nejkřehčí.

    Proto se polyká i chyba importu: modul musí jít spustit i v prostředí, kde
    cb-logger vůbec není.

    Vstup:
        config: konfigurace; z bloku `logging` se bere adresa a úroveň.

    Výstup:
        `LogClient`, nebo `None`, když se ho nepodařilo postavit.

    Při chybě:
        Nevyhazuje.
    """
    try:
        from cb_logger import LogClient
    except ImportError as e:
        print(f"cb-logger není k dispozici, běží se bez logu: {e}",
              file=sys.stderr)
        return None

    nastaveni = config["logging"]
    try:
        return LogClient(
            component="udpipe",
            endpoint=nastaveni["endpoint"],
            level=nastaveni["level"],
            methods=tuple(nastaveni.get("methods") or ()),
            spool_dir=str(_run_dir(config) / "log-spool"),
        )
    except Exception as e:                       # noqa: BLE001
        print(f"logovátko se nepodařilo připojit, běží se bez něj: {e}",
              file=sys.stderr)
        return None


def _prostredi_udpipe(upstream: dict[str, Any]) -> dict[str, str]:
    """Sestaví proměnné prostředí pro proces UDPipe.

    **Offline natvrdo.** UDPipe si pro embeddingy sahá na RobeCzech přes
    HuggingFace a bez těchhle proměnných by si ho stáhl do `~/.cache`.
    V conBondu2 to při prvním spuštění bez sítě spadlo — přesně ta závislost
    na okolí, které se zbavujeme. Cache proto míří dovnitř modulu a chybějící
    váha se ohlásí hned, ne tichým stahováním.

    Vstup:
        upstream: blok `module.upstream` z konfigurace.

    Výstup:
        Slovník proměnných, které se přidají k prostředí procesu.

    Při chybě:
        Nevyhazuje.
    """
    return {
        "HF_HOME": str(upstream["hf_home"]),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }


def _vlakna(upstream: dict[str, Any]) -> int:
    """Kolik vláken dostane UDPipe.

    Nula v konfiguraci znamená odvodit z počtu jader a dvě nechat systému,
    ať stroj při rozboru nezamrzne (převzato z conBondu2, `udpipe.sh`).
    """
    zadano = upstream["threads"]
    if zadano > 0:
        return zadano
    jader = os.cpu_count() or 4
    return max(2, jader - JADRA_SYSTEMU)


def _predehrej(sluzba: service.UdpipeService, veta: str) -> None:
    """Pošle jednu větu, aby se načetla síť.

    UDPipe načítá síť líně až při prvním požadavku s taggerem; v conBondu2 to
    bylo přes 5 s plus 4,7 s na první embeddingy. Bez předehřátí ta cena
    dopadne na první skutečný dotaz.

    Naměřená doba jde na výstup: je to údaj o stroji, ne o kódu, a bez zápisu
    by se hledal v hlavě.

    Při chybě:
        Nevyhazuje. Nepovedené předehřátí není důvod službu nespustit —
        první dotaz si síť načte sám, jen bude pomalejší.
    """
    zacatek = time.monotonic()
    try:
        sluzba.parse(veta, trace="i-warmup")
    except Exception as e:                      # noqa: BLE001
        print(f"předehřátí selhalo: {e}", file=sys.stderr)
        return
    print(f"předehřáto za {time.monotonic() - zacatek:.1f} s")


# ------------------------------------------------------------------- stop


def cmd_stop(config: dict[str, Any], *, timeout: float | None) -> int:
    """Zastaví službu; UDPipe skončí s ní.

    Naše služba drží UDPipe jako svého potomka a ukončí ho ve svém `finally`.
    Tady se proto posílá signál jen jí — kdyby se UDPipe zabíjel odsud, mohl
    by ho mezitím zvednout jiný běh a zabil by se cizí proces.
    """
    pid = _running_pid(config)
    if pid is None:
        print("cb-udpipe neběží")
        return EXIT_NOT_RUNNING

    strop = timeout if timeout is not None \
        else config["runtime"]["stop_timeout_s"]
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        print(f"nepodařilo se poslat SIGTERM procesu {pid}: {e}",
              file=sys.stderr)
        return EXIT_FAILED

    if _cekej_na_konec(pid, strop):
        print(f"cb-udpipe zastaven (pid {pid})")
        _uklid_stav(config)
        return EXIT_OK

    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    print(f"cb-udpipe nereagoval do {strop:.0f} s, ukončen tvrdě (pid {pid})",
          file=sys.stderr)
    _uklid_stav(config)
    return EXIT_OK


def _zastav_proces(proces: subprocess.Popen, strop: float) -> None:
    """Ukončí proces UDPipe: SIGTERM, počkat, pak SIGKILL."""
    if proces.poll() is not None:
        return
    try:
        proces.terminate()
        proces.wait(timeout=strop)
    except subprocess.TimeoutExpired:
        proces.kill()
    except OSError:
        pass


def cmd_reload(config: dict[str, Any]) -> int:
    """Požádá běžící službu, aby znovu načetla konfiguraci."""
    pid = _running_pid(config)
    if pid is None:
        print("cb-udpipe neběží")
        return EXIT_NOT_RUNNING
    try:
        os.kill(pid, signal.SIGHUP)
    except OSError as e:
        print(f"nepodařilo se poslat SIGHUP procesu {pid}: {e}",
              file=sys.stderr)
        return EXIT_FAILED
    print(f"cb-udpipe dostal pokyn znovu načíst konfiguraci (pid {pid})")
    return EXIT_OK


# ----------------------------------------------------------------- status


def cmd_status(config: dict[str, Any], *, jako_json: bool) -> int:
    """Vypíše stav včetně **obou** portů.

    Port se uvádí vždycky: u běžící služby skutečný z `run/service.port`,
    u neběžící zamýšlený z konfigurace. A uvádějí se oba, protože modul
    provozuje dva — naše API a vlastní instanci UDPipe. Bez toho člověk hledá
    chybu v běžící službě, zatímco běží s jiným nastavením, než si myslí
    (README-MODULES.md § 12).
    """
    pid = _running_pid(config)
    port = _port(config)
    udpipe_port = config["module"]["upstream"]["port"]
    cesta = config["_meta"]["path"]

    if pid is None:
        stav: dict[str, Any] = {
            "module": "cb-udpipe", "running": False, "port": port,
            "upstream_port": udpipe_port, "config": cesta,
        }
        osirely = _osirely_pid(config)
        if osirely is not None:
            stav["orphan_pid"] = osirely
        if jako_json:
            print(json.dumps(stav, ensure_ascii=False, indent=1))
        else:
            print(f"cb-udpipe    NEBĚŽÍ   měl by běžet na "
                  f"{config['service']['host']}:{port}")
            print(f"             UDPipe   {config['service']['host']}:"
                  f"{udpipe_port}")
            print(f"             config   {cesta}")
            if osirely is not None:
                print(f"             pozn.    osiřelý run/service.pid "
                      f"(pid {osirely} neexistuje)")
        return EXIT_NOT_RUNNING

    zdravi = _zdravi(config)
    stav = {
        "module": "cb-udpipe", "running": True, "pid": pid, "port": port,
        "upstream_port": udpipe_port, "config": cesta, "health": zdravi,
    }
    if jako_json:
        print(json.dumps(stav, ensure_ascii=False, indent=1))
        return EXIT_OK

    print(f"cb-udpipe    BĚŽÍ     {config['service']['host']}:{port}  "
          f"pid {pid}")
    if zdravi:
        print(f"             zdraví   {zdravi.get('status', '?')}")
        u = zdravi.get("upstream", {})
        print(f"             UDPipe   {'ok' if u.get('available') else 'NEDOSTUPNÝ'}"
              f"  {u.get('endpoint') or ''}")
        c = zdravi.get("cache", {})
        print(f"             cache    {c.get('sentences', '?')} vět, "
              f"{c.get('corrupt', '?')} poškozených")
        print(f"             tokenizér {zdravi.get('tokenizer', '?')}")
    else:
        print("             zdraví   služba neodpovídá na /v1/health")
    print(f"             config   {cesta}")
    return EXIT_OK


# ------------------------------------------------------------- běhový stav


def _zapis_stav(config: dict[str, Any], *, pid: int, port: int,
                udpipe_pid: int) -> None:
    """Zapíše PID a skutečný port do `run/`.

    Skutečný port je podstatný, když je v konfiguraci nula a přidělil ho
    systém — jinak by ho nikdo nezjistil (README-MODULES.md § 5).
    """
    for cesta, hodnota in (
        (config["runtime"]["pid_file"], pid),
        (config["runtime"]["port_file"], port),
        (str(_run_dir(config) / "udpipe.pid"), udpipe_pid),
    ):
        p = Path(cesta)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{hodnota}\n", encoding="utf-8")


def _uklid_stav(config: dict[str, Any]) -> None:
    """Smaže běhový stav. Smazání `run/` musí být neškodné (§ 2 politiky)."""
    for cesta in (config["runtime"]["pid_file"],
                  config["runtime"]["port_file"],
                  str(_run_dir(config) / "udpipe.pid")):
        try:
            Path(cesta).unlink()
        except OSError:
            pass


def _run_dir(config: dict[str, Any]) -> Path:
    """Adresář běhového stavu, odvozený z cesty k PID souboru."""
    return Path(config["runtime"]["pid_file"]).parent


def _udpipe_log(config: dict[str, Any]) -> Path:
    """Kam píše proces UDPipe. Je to běhový stav, ne perzistentní data."""
    return _run_dir(config) / "udpipe.log"


def _precti_pid(config: dict[str, Any]) -> int | None:
    """Přečte PID ze souboru; `None`, když soubor není nebo je nečitelný."""
    try:
        return int(Path(config["runtime"]["pid_file"]).read_text().strip())
    except (OSError, ValueError):
        return None


def _running_pid(config: dict[str, Any]) -> int | None:
    """PID běžící služby, nebo `None`.

    Ověřuje se, že proces s tím PID **skutečně existuje**: osiřelý soubor po
    spadlé službě by jinak vypadal jako běžící služba.
    """
    pid = _precti_pid(config)
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def _osirely_pid(config: dict[str, Any]) -> int | None:
    """PID ze souboru, jehož proces neexistuje.

    Vrací se zvlášť, aby to `status` mohl nahlásit místo zamlčení — osiřelý
    soubor znamená, že služba spadla, a to je informace.
    """
    pid = _precti_pid(config)
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return pid
    return None


def _port(config: dict[str, Any]) -> int:
    """Skutečný port běžící služby, jinak zamýšlený z konfigurace."""
    try:
        skutecny = int(Path(config["runtime"]["port_file"]).read_text().strip())
        if skutecny > 0:
            return skutecny
    except (OSError, ValueError):
        pass
    return config["service"]["port"]


def _endpoint(config: dict[str, Any]) -> str:
    return f"http://{config['service']['host']}:{_port(config)}"


def _upstream_endpoint(config: dict[str, Any]) -> str:
    u = config["module"]["upstream"]
    return f"http://{u['host']}:{u['port']}"


# ------------------------------------------------------------- čekání


def _cekej_na_udpipe(config: dict[str, Any], strop: float) -> bool:
    """Čeká, až UDPipe začne odpovídat na `/models`.

    Je to nejlevnější dotaz, který nesahá na data ani nenačítá síť — server
    na něj odpoví, jakmile je proces připravený.
    """
    adresa = _upstream_endpoint(config) + "/models"
    konec = time.monotonic() + strop
    while time.monotonic() < konec:
        try:
            with urllib.request.urlopen(adresa, timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, socket.timeout):
            time.sleep(POLL_S)
    return False


def _cekej_na_version(config: dict[str, Any], strop: float) -> dict | None:
    """Čeká, až naše služba začne odpovídat na `/version`.

    `/version` nemá závislosti a nesahá na data, takže odpoví i tehdy, když
    je služba jinak nezdravá. Je to nejlevnější zkouška, že proces žije
    (README-MODULES.md § 7).
    """
    konec = time.monotonic() + strop
    while time.monotonic() < konec:
        try:
            with urllib.request.urlopen(_endpoint(config) + "/version",
                                        timeout=2) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(POLL_S)
    return None


def _cekej_na_konec(pid: int, strop: float) -> bool:
    """Čeká, až proces s daným PID skončí."""
    konec = time.monotonic() + strop
    while time.monotonic() < konec:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(POLL_S)
    return False


def _zdravi(config: dict[str, Any]) -> dict[str, Any] | None:
    """Přečte `/v1/health` běžící služby.

    `status` odpovídá odtud, ne jen „běží" — to je požadavek § 12 politiky.
    """
    try:
        with urllib.request.urlopen(_endpoint(config) + "/v1/health",
                                    timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _nastav_signaly(hotovo: threading.Event, config: dict[str, Any]) -> None:
    """Zaregistruje obsluhu SIGTERM, SIGINT a SIGHUP.

    `SIGHUP` znovu načte konfiguraci; co znovu načíst nejde (změna portu),
    se ohlásí a nechá běžet staré nastavení — služba se nikdy nerestartuje
    sama, protože by tím zahodila rozdělané spojení (§ 12 politiky).
    """
    def konec(signum, _frame):
        hotovo.set()

    def znovu_nacti(_signum, _frame):
        try:
            nova = load(config["_meta"]["path"])
        except ConfigError as e:
            print(f"reload: konfigurace je neplatná, běží se dál se starou\n"
                  f"{e}", file=sys.stderr)
            return
        if nova["service"]["port"] != config["service"]["port"]:
            print("reload: změnu portu nejde načíst za běhu, běží se dál "
                  "se starým nastavením", file=sys.stderr)
            return
        print("reload: konfigurace znovu načtena")

    signal.signal(signal.SIGTERM, konec)
    signal.signal(signal.SIGINT, konec)
    signal.signal(signal.SIGHUP, znovu_nacti)
