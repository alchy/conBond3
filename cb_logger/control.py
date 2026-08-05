"""Ovládání služby: start, stop, restart, reload, status.

Logika řízení je tady, ne v `cb-logger.py` v kořeni — ten skript je jen dveře
(README-MODULES.md § 12). Díky tomu jde řízení testovat jako kód, ne jako podproces.

Návratové kódy jsou součástí kontraktu, protože se ovládání volá ze skriptů
a z testů:

    0   příkaz uspěl; u `status` služba běží a je zdravá
    1   příkaz selhal
    2   špatné argumenty nebo neplatná konfigurace
    3   služba neběží
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from cb_logger import __version__
from cb_logger.api import make_api_server
from cb_logger.config import DEFAULT_CONFIG_PATH, MODULE_DIR, ConfigError, load
from cb_logger.service import LoggerService, now_iso
from cb_logger.watch import make_watch_server
from cb_logger.watch_objects import make_object_watch_server

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BAD_USAGE = 2
EXIT_NOT_RUNNING = 3

#: Ovládací program v kořeni projektu. `start` bez `--foreground` se přes něj
#: spustí znovu, takže existuje jen jedna cesta ke spuštění služby.
LAUNCHER = MODULE_DIR.parent / "cb-logger.py"

#: Jak dlouho se po startu čeká, než služba odpoví na `/version`.
START_TIMEOUT_S = 10.0

#: Jak často se při čekání ptáme. Krátký interval schválně: start má být
#: hotový co nejdřív, ne za pevnou dobu.
POLL_S = 0.05


# ---------------------------------------------------------------- příkazy

def main(argv: list[str] | None = None) -> int:
    """Zpracuje argumenty a provede příkaz. Vrací návratový kód."""
    parser = argparse.ArgumentParser(
        prog="cb-logger.py", description="Ovládání služby cb-logger.",
    )
    pod = parser.add_subparsers(dest="prikaz", required=True)

    p = pod.add_parser("start", help="spustí službu")
    p.add_argument("--config", help="cesta ke konfiguraci")
    p.add_argument("--foreground", action="store_true",
                   help="běží v terminálu bez odpojení")

    p = pod.add_parser("stop", help="zastaví službu")
    p.add_argument("--config", help="cesta ke konfiguraci")
    p.add_argument("--timeout", type=float,
                   help="kolik sekund čekat na ukončení")

    p = pod.add_parser("restart", help="zastaví a spustí")
    p.add_argument("--config", help="cesta ke konfiguraci")

    p = pod.add_parser("reload", help="znovu načte konfiguraci bez ztráty stavu")
    p.add_argument("--config", help="cesta ke konfiguraci")

    p = pod.add_parser("status", help="stav služby včetně portu")
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


def cmd_start(config: dict[str, Any], *, foreground: bool,
              config_path: str | None) -> int:
    """Spustí službu.

    Konfigurace se ověřuje **před** spuštěním (stalo se už v `main`), takže
    služba s neplatným nastavením vůbec nenaběhne. Po spuštění se čeká na
    `GET /version` a teprve pak se ohlásí úspěch — jinak by `start` vracel
    nulu i pro službu, která za vteřinu spadne.
    """
    bezici = _running_pid(config)
    if bezici is not None:
        # Není to chyba. Kdo volá `start` na běžící službu, obvykle jen chce,
        # aby běžela — a ona běží.
        print(f"cb-logger už běží (pid {bezici}, port {_port(config)})")
        return EXIT_OK

    if foreground:
        return _serve(config)

    prikaz = [sys.executable, str(LAUNCHER), "start", "--foreground"]
    if config_path:
        prikaz += ["--config", config_path]

    try:
        # start_new_session odpojí potomka od terminálu, takže přežije zavření
        # okna. Výstup jde do vlastního logu služby, ne do terminálu rodiče.
        subprocess.Popen(prikaz, start_new_session=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError as e:
        print(f"nepodařilo se spustit {LAUNCHER}: {e}", file=sys.stderr)
        return EXIT_FAILED

    verze = _wait_for_version(config, START_TIMEOUT_S)
    if verze is None:
        print(
            f"cb-logger nenaběhl do {START_TIMEOUT_S:.0f} s\n"
            f"  konfigurace: {config['_meta']['path']}\n"
            f"  vlastní log: {config['runtime']['self_log']['path']}",
            file=sys.stderr,
        )
        return EXIT_FAILED

    watch = config["module"]["watch"]
    if watch["enabled"]:
        host = config["service"]["host"]
        print(f"cb-logger běží — API {_endpoint(config)}"
              f", kukátko text http://{host}:{watch['port']}"
              f", kukátko objekty http://{host}:{watch['objects_port']}")
    else:
        print(f"cb-logger běží — API {_endpoint(config)}, kukátka vypnutá")
    return EXIT_OK


def cmd_stop(config: dict[str, Any], *, timeout: float | None) -> int:
    """Zastaví službu: SIGTERM, počkat, pak SIGKILL."""
    pid = _running_pid(config)
    if pid is None:
        print("cb-logger neběží")
        return EXIT_NOT_RUNNING

    strop = timeout if timeout is not None else config["runtime"]["stop_timeout_s"]
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        print(f"nepodařilo se poslat SIGTERM procesu {pid}: {e}", file=sys.stderr)
        return EXIT_FAILED

    if _wait_for_exit(pid, strop):
        print(f"cb-logger zastaven (pid {pid})")
        _cleanup_runtime(config)
        return EXIT_OK

    # Rozpracované požadavky měly svůj čas. Teď je přednější, aby port zůstal
    # volný pro restart, než aby doběhl poslední zápis.
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    print(f"cb-logger nereagoval do {strop:.0f} s, ukončen tvrdě (pid {pid})",
          file=sys.stderr)
    _cleanup_runtime(config)
    return EXIT_OK


def cmd_reload(config: dict[str, Any]) -> int:
    """Požádá běžící službu, aby znovu načetla konfiguraci.

    Co znovu načíst nejde (změna portu), služba ohlásí a nechá běžet staré
    nastavení — nikdy se nerestartuje sama, protože by tím zahodila rozdělané
    spojení, o kterých volající neví.
    """
    pid = _running_pid(config)
    if pid is None:
        print("cb-logger neběží")
        return EXIT_NOT_RUNNING
    try:
        os.kill(pid, signal.SIGHUP)
    except OSError as e:
        print(f"nepodařilo se poslat SIGHUP procesu {pid}: {e}", file=sys.stderr)
        return EXIT_FAILED
    print(f"cb-logger dostal pokyn znovu načíst konfiguraci (pid {pid})")
    return EXIT_OK


def cmd_status(config: dict[str, Any], *, jako_json: bool) -> int:
    """Vypíše stav služby včetně portu.

    Port se uvádí **vždycky**: u běžící služby skutečný z `run/service.port`,
    u neběžící zamýšlený z konfigurace. Bez toho člověk hledá chybu v běžící
    službě, zatímco běží s jiným nastavením, než si myslí.
    """
    pid = _running_pid(config)
    port = _port(config)
    cesta_config = config["_meta"]["path"]
    watch = config["module"]["watch"]

    if pid is None:
        stav: dict[str, Any] = {
            "module": "cb-logger",
            "running": False,
            "port": port,
            "port_source": "konfigurace (zamýšlený)",
            "config": cesta_config,
        }
        osirely = _read_pid(config)
        if osirely is not None:
            stav["note"] = (
                f"osiřelý {config['runtime']['pid_file']} (pid {osirely} "
                f"neexistuje)"
            )
        if jako_json:
            print(json.dumps(stav, ensure_ascii=False, indent=1))
        else:
            print(f"cb-logger    NEBĚŽÍ   měl by běžet na "
                  f"{config['service']['host']}:{port}")
            print(f"             data     {config.get('data_root', '?')}")
            print(f"             config   {cesta_config}")
            if "note" in stav:
                print(f"             pozn.    {stav['note']}")
        return EXIT_NOT_RUNNING

    verze = _http_get(config, "/version", port=port)
    zdravi = _http_get(config, "/v1/health", port=port)
    souhrn = _http_get(config, "/v1/summary", port=port)

    stav = {
        "module": "cb-logger",
        "running": True,
        "pid": pid,
        "host": config["service"]["host"],
        "port": port,
        "port_source": "run/service.port (skutečný)",
        "config": cesta_config,
        "version": (verze or {}).get("version", __version__),
        "health": zdravi,
        "summary": souhrn,
        "watch": {"enabled": watch["enabled"], "port": watch["port"],
                  "objects_port": watch["objects_port"]},
    }

    if jako_json:
        print(json.dumps(stav, ensure_ascii=False, indent=1))
        return EXIT_OK if zdravi else EXIT_FAILED

    zdrave = "ok" if zdravi else "NEODPOVÍDÁ"
    print(f"cb-logger    BĚŽÍ     {config['service']['host']}:{port}"
          f"   pid {pid}")
    print(f"             zdraví   {zdrave}")
    print(f"             verze    modul {stav['version']} · konfigurace "
          f"{config['config_version']}")
    if souhrn:
        po_stavech = _states_line(souhrn)
        print(f"             záznamy  {souhrn['total']}  ({po_stavech})")
        if souhrn.get("malformed"):
            print(f"             vadné    {souhrn['malformed']}")
        if souhrn.get("without_trace"):
            print(f"             bez stopy {souhrn['without_trace']}")
    if souhrn and (zdravi or {}).get("objects_total"):
        print(f"             objekty  {zdravi['objects_total']}"
              + (f"  (zkrácených {zdravi['objects_truncated']})"
                 if zdravi.get("objects_truncated") else ""))
    if watch["enabled"]:
        host = config["service"]["host"]
        print(f"             kukátka  text http://{host}:{watch['port']}")
        print(f"                      objekty http://{host}:"
              f"{watch['objects_port']}")
    else:
        print("             kukátka  vypnutá")
    print(f"             data     {config.get('data_root', '?')}")
    print(f"             config   {cesta_config}")
    return EXIT_OK if zdravi else EXIT_FAILED


# ------------------------------------------------------------ běh služby

def _serve(config: dict[str, Any]) -> int:
    """Postaví službu, obsluhuje požadavky a řízeně skončí.

    Běží v popředí. `start` bez `--foreground` sem vede přes odpojený podproces,
    takže existuje jen jedna cesta ke spuštění služby a nemůže se rozejít.

    Ukončení řídí `SIGTERM`: hlavní vlákno čeká na událost, obsluha běží
    vedle. Volat `shutdown()` přímo z obsluhy signálu by zamrzlo, protože
    `serve_forever` běží v témž vlákně, které signál obsluhuje.
    """
    service = LoggerService(config)
    self_log = _SelfLog(config["runtime"]["self_log"])
    self_log.write(f"start · konfigurace {config['_meta']['path']} "
                   f"· otisk {config['_meta']['fingerprint']}")

    try:
        api = make_api_server(service, config)
    except OSError as e:
        self_log.write(f"start selhal: port {config['service']['port']}: {e}")
        print(f"nepodařilo se obsadit port {config['service']['port']}: {e}",
              file=sys.stderr)
        return EXIT_FAILED

    port = api.server_address[1]

    # Kukátka jsou pohodlí, ne podmínka. Když port nejde obsadit, služba běží
    # dál a je to vidět ve zdraví — vypnutá část musí být poznat.
    kukatka = []
    for jmeno, postav in (("text", make_watch_server),
                          ("objekty", make_object_watch_server)):
        try:
            server = postav(service, config)
        except OSError as e:
            self_log.write(f"kukátko ({jmeno}) se nespustilo: {e}")
            service.note_error(f"watch/{jmeno}: {e}")
            continue
        if server is not None:
            kukatka.append((jmeno, server))

    _write_runtime(config, pid=os.getpid(), port=port)

    hotovo = threading.Event()
    _install_signals(hotovo, config, service, self_log)

    vlakna = [threading.Thread(target=api.serve_forever,
                              kwargs={"poll_interval": 0.1}, daemon=True)]
    for _, server in kukatka:
        vlakna.append(threading.Thread(target=server.serve_forever,
                                       kwargs={"poll_interval": 0.1},
                                       daemon=True))
    vlakna.append(threading.Thread(
        target=_flush_loop, args=(service, config, hotovo), daemon=True))
    for v in vlakna:
        v.start()

    popis_kukatek = ", ".join(
        f"kukátko {jmeno} na {server.server_address[1]}"
        for jmeno, server in kukatka
    ) or "kukátka vypnutá"
    self_log.write(
        f"poslouchám na {config['service']['host']}:{port}, {popis_kukatek}"
    )

    try:
        hotovo.wait()
    except KeyboardInterrupt:
        pass

    self_log.write("ukončuji")
    api.shutdown()
    api.server_close()
    for _, server in kukatka:
        server.shutdown()
        server.server_close()
    service.close()
    _cleanup_runtime(config)
    self_log.write("ukončeno")
    return EXIT_OK


def _install_signals(hotovo: threading.Event, config: dict[str, Any],
                     service: LoggerService, self_log: "_SelfLog") -> None:
    """Nastaví obsluhu SIGTERM, SIGINT a SIGHUP."""

    def konec(signum, _frame):
        self_log.write(f"signál {signal.Signals(signum).name}")
        hotovo.set()

    def znovu_nacti(_signum, _frame):
        """Znovu načte konfiguraci; co načíst nejde, ohlásí a nechá být."""
        try:
            nova = load(config["_meta"]["path"])
        except ConfigError as e:
            self_log.write(f"reload selhal, běží staré nastavení: {e}")
            service.note_error(f"reload: {e}")
            return

        nelze = []
        if nova["service"]["port"] != config["service"]["port"]:
            nelze.append("service.port")
        if nova["module"]["watch"]["port"] != config["module"]["watch"]["port"]:
            nelze.append("module.watch.port")
        if nova["module"]["watch"]["enabled"] != \
                config["module"]["watch"]["enabled"]:
            nelze.append("module.watch.enabled")

        # Směrování a retenci lze vyměnit za běhu; porty ne — na tom visí
        # otevřená spojení, o kterých volající neví.
        config["module"]["routing"].clear()
        config["module"]["routing"].update(nova["module"]["routing"])
        config["logging"] = nova.get("logging", config.get("logging", {}))

        if nelze:
            zprava = ("reload: nelze za běhu změnit " + ", ".join(nelze)
                      + "; běží staré hodnoty, použij restart")
            self_log.write(zprava)
            service.note_error(zprava)
        else:
            self_log.write(f"reload · otisk {nova['_meta']['fingerprint']}")

    signal.signal(signal.SIGTERM, konec)
    signal.signal(signal.SIGINT, konec)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, znovu_nacti)


def _flush_loop(service: LoggerService, config: dict[str, Any],
                hotovo: threading.Event) -> None:
    """Pravidelně ukládá souhrn, aby ho pád procesu nestál celý."""
    interval = config["module"]["summary"]["flush_interval_s"]
    while not hotovo.wait(interval):
        service.flush()


class _SelfLog:
    """Vlastní log logovátka — jediné místo v systému, kde se loguje jinak.

    Logovátko nemůže logovat samo do sebe, zacyklilo by se. Píše tedy do
    prostého souboru s rotací podle velikosti.
    """

    def __init__(self, nastaveni: dict[str, Any]):
        self._path = Path(nastaveni["path"])
        self._max_bytes = nastaveni["max_bytes"]
        self._keep = nastaveni["keep"]
        self._lock = threading.Lock()

    def write(self, zprava: str) -> None:
        """Zapíše řádek. Nikdy nevyhazuje — vlastní log nesmí shodit službu."""
        radek = f"{now_iso()}  {zprava}\n"
        try:
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                if self._path.exists() and \
                        self._path.stat().st_size >= self._max_bytes:
                    self._rotate()
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(radek)
        except OSError:
            pass

    def _rotate(self) -> None:
        """Posune otočené soubory o jedna a nejstarší zahodí."""
        for i in range(self._keep, 0, -1):
            zdroj = self._path if i == 1 else self._path.with_suffix(f".{i - 1}")
            cil = self._path.with_suffix(f".{i}")
            if zdroj.exists():
                zdroj.replace(cil)


# ------------------------------------------------------------- pomocné

def _write_runtime(config: dict[str, Any], *, pid: int, port: int) -> None:
    """Zapíše PID a skutečný port do run/.

    Port je tam schválně: když je v konfiguraci nula, přidělí ho systém a jinak
    by nikdo nezjistil, kam se připojit.
    """
    for cesta, hodnota in (
        (config["runtime"]["pid_file"], str(pid)),
        (config["runtime"]["port_file"], str(port)),
    ):
        p = Path(cesta)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(hodnota + "\n", encoding="utf-8")


def _cleanup_runtime(config: dict[str, Any]) -> None:
    """Uklidí PID a port. Nevyhazuje — úklid nesmí shodit ukončení."""
    for cesta in (config["runtime"]["pid_file"], config["runtime"]["port_file"]):
        try:
            Path(cesta).unlink()
        except OSError:
            pass


def _read_pid(config: dict[str, Any]) -> int | None:
    """Přečte PID ze souboru, nebo `None`, když soubor chybí či je nečitelný."""
    try:
        return int(Path(config["runtime"]["pid_file"]).read_text().strip())
    except (OSError, ValueError):
        return None


def _running_pid(config: dict[str, Any]) -> int | None:
    """Vrátí PID běžící služby, nebo `None`.

    Osiřelý PID soubor po spadlé službě se pozná a chová se jako neběžící —
    zamlčet ho by znamenalo, že `start` odmítne spustit službu, která neběží.
    """
    pid = _read_pid(config)
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
    except OSError as e:
        if e.errno == errno.EPERM:
            # Proces existuje, jen patří někomu jinému. Pro nás běží.
            return pid
        return None
    return pid


def _port(config: dict[str, Any]) -> int:
    """Vrátí port: skutečný z run/, jinak zamýšlený z konfigurace."""
    try:
        return int(Path(config["runtime"]["port_file"]).read_text().strip())
    except (OSError, ValueError):
        return config["service"]["port"]


def _endpoint(config: dict[str, Any], port: int | None = None) -> str:
    """Sestaví adresu služby."""
    return f"http://{config['service']['host']}:{port or _port(config)}"


def _http_get(config: dict[str, Any], cesta: str,
              port: int | None = None, timeout: float = 2.0) -> dict | None:
    """Zavolá běžící službu; vrátí objekt, nebo `None`, když neodpověděla."""
    try:
        with urllib.request.urlopen(
            _endpoint(config, port) + cesta, timeout=timeout
        ) as odpoved:
            return json.loads(odpoved.read() or b"{}")
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def _wait_for_version(config: dict[str, Any], strop: float) -> dict | None:
    """Počká, až služba odpoví na `/version`.

    Ptá se na `/version`, ne na `/v1/health`: je to bod bez závislostí, který
    odpoví, i když je služba jinak nezdravá, takže rozliší „ještě nenaběhla"
    od „naběhla, ale něco jí chybí".
    """
    konec = time.monotonic() + strop
    while time.monotonic() < konec:
        odpoved = _http_get(config, "/version", timeout=0.5)
        if odpoved is not None:
            return odpoved
        time.sleep(POLL_S)
    return None


def _wait_for_exit(pid: int, strop: float) -> bool:
    """Počká, až proces zmizí. Vrátí `True`, když se to stihlo.

    Proč se vedle `os.kill(pid, 0)` zkouší i `waitpid`: ukončený potomek
    zůstane zombie, dokud ho rodič nesklidí, a na zombie `os.kill` **pořád
    uspěje**. Čekání by tedy vždycky vyčerpalo celý strop a sáhlo po `SIGKILL`,
    přestože služba skončila hned a řízeně.

    *(Naměřeno při stavbě: `stop` trval 20,05 s místo desetin sekundy —
    přesně `stop_timeout_s`. V terminálu se to neprojevilo, protože tam rodič
    hned skončí a potomka sklidí init; projevilo se to až v testech, které
    startují a zastavují službu v jednom procesu.)*
    """
    konec = time.monotonic() + strop
    while time.monotonic() < konec:
        try:
            # Sklidit, pokud je to náš potomek. Cizímu procesu to vrátí
            # ChildProcessError a rozhodne až `os.kill` níž.
            sklizeny, _ = os.waitpid(pid, os.WNOHANG)
            if sklizeny == pid:
                return True
        except (ChildProcessError, OSError):
            pass
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(POLL_S)
    return False


def _states_line(souhrn: dict[str, Any]) -> str:
    """Sestaví řádek s počty po výsledcích pro výpis `status`."""
    celkem = {"ok": 0, "empty": 0, "skipped": 0, "error": 0}
    for radek in souhrn.get("by_method", {}).values():
        for stav in celkem:
            celkem[stav] += radek.get(stav, 0)
    return " · ".join(f"{k} {v}" for k, v in celkem.items())
