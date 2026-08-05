"""Ovládání služby cb-bond: `start`, `stop`, `restart`, `status`.

cb-bond je **vrcholová služba** — pod ním stojí logger a udpipe. `start`
tedy nejdřív zajistí je (`stack.py`) a teprve pak staví korpus a zvedá
vlastní API. Pořadí není libovolné: udpipe do loggeru loguje už při
vlastním startu, takže obrácené pořadí by první záznamy zahodilo.

## Proč `status` vypisuje statistiky

*(Požadavek J., 5. 8. 2026.)* U loggeru i udpipe `status` říká, co má
služba v sobě — kolik záznamů, kolik vět v cache. U cb-bondu je ta otázka
nejzajímavější, protože obsah hlavy se mění učením a promocí: bez čísel
se nedá poznat, jestli běží model, který se učil, nebo čerstvě postavený.

Čísla jdou **od běžící služby** (`GET /v1/state`), ne z vlastního
počítání. Kdyby si je `status` spočítal sám, trvalo by to pět vteřin
a ukázal by, co by v hlavě bylo, kdyby se postavila znovu — ne co v ní
je. To je přesně ta třída vady, kterou § 11 zakazuje u měření.

Když služba neběží, čísla se nevymýšlejí: vypíše se, co by se stavělo.

Návratové kódy podle § 12: 0 v pořádku · 1 selhání · 2 špatné argumenty
nebo neplatná konfigurace · 3 služba neběží.
"""

from __future__ import annotations

import argparse
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

from cb_bond import api, service as service_modul, stack as stack_modul
from cb_bond.config import DEFAULT_CONFIG_PATH, MODULE_DIR, ConfigError, load

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BAD_USAGE = 2
EXIT_NOT_RUNNING = 3

#: Ovládací program v kořeni projektu. `start` bez `--foreground` se přes
#: něj spouští znovu, aby démon vznikl tímtéž způsobem jako u sourozenců.
LAUNCHER = MODULE_DIR.parent / "cb-bond.py"

#: Kolik vteřin rodič čeká, než potomek začne odpovídat na `/version`.
#: Stavba korpusu je drahá (12 258 vět ≈ 23 s), takže strop je vysoko;
#: nízký strop by hlásil neúspěch, zatímco potomek ještě poctivě staví.
START_TIMEOUT_S = 300


def main(argv: list[str] | None = None) -> int:
    """Vstupní bod ovládání."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_BAD_USAGE

    try:
        config = load(args.config)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return EXIT_BAD_USAGE

    if args.command == "start":
        return cmd_start(config, foreground=args.foreground,
                         no_deps=args.no_deps, config_path=args.config)
    if args.command == "stop":
        return cmd_stop(config)
    if args.command == "restart":
        cmd_stop(config)
        return cmd_start(config, foreground=False, no_deps=args.no_deps,
                         config_path=args.config)
    if args.command == "status":
        return cmd_status(config, jako_json=args.json)
    if args.command == "reload":
        return cmd_reload(config)
    if args.command == "corpus":
        return cmd_corpus(config, akce=args.action)
    return EXIT_BAD_USAGE


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cb-bond.py", description="ovládání služby cb-bond")
    pod = p.add_subparsers(dest="command")

    s = pod.add_parser("start", help="spustí službu i vše pod ní")
    s.add_argument("--config", help="cesta ke konfiguraci")
    s.add_argument("--foreground", action="store_true",
                   help="běž v popředí místo démona")
    s.add_argument("--no-deps", action="store_true",
                   help="nespouštěj služby pod sebou (řídím si je sám)")

    for jmeno, napoveda in (("stop", "zastaví službu"),
                            ("restart", "zastaví a spustí")):
        q = pod.add_parser(jmeno, help=napoveda)
        q.add_argument("--config", help="cesta ke konfiguraci")
        if jmeno == "restart":
            q.add_argument("--no-deps", action="store_true",
                           help="nespouštěj služby pod sebou")

    q = pod.add_parser("status", help="stav služby a co má v hlavě")
    q.add_argument("--config", help="cesta ke konfiguraci")
    q.add_argument("--json", action="store_true", help="výstup jako JSON")

    q = pod.add_parser("reload", help="znovu načte konfiguraci (SIGHUP)")
    q.add_argument("--config", help="cesta ke konfiguraci")

    q = pod.add_parser("corpus", help="co je v korpusu, ověření, stavba")
    q.add_argument("action", choices=CORPUS_ACTIONS,
                   help="status · validate · parse · build")
    q.add_argument("--config", help="cesta ke konfiguraci")
    return p


# ----------------------------------------------------------------- start


def cmd_start(config: dict[str, Any], *, foreground: bool, no_deps: bool,
              config_path: str | None) -> int:
    """Zajistí služby pod sebou, postaví korpus a zvedne API."""
    bezici = _running_pid(config)
    if bezici is not None:
        print(f"cb-bond už běží (pid {bezici}, port {_port(config)})")
        return EXIT_OK

    if foreground:
        return _serve(config, no_deps=no_deps)

    prikaz = [sys.executable, str(LAUNCHER), "start", "--foreground"]
    if no_deps:
        prikaz.append("--no-deps")
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
        print(f"cb-bond nenaběhl do {START_TIMEOUT_S:.0f} s\n"
              f"  konfigurace: {config['_meta']['path']}",
              file=sys.stderr)
        return EXIT_FAILED

    print(f"cb-bond běží — API {_endpoint(config)}")
    return EXIT_OK


def _serve(config: dict[str, Any], *, no_deps: bool) -> int:
    """Postaví systém a běží, dokud nepřijde signál.

    Pořadí je významné: nejdřív závislosti, pak stavba, pak teprve port.
    Kdyby se API zvedlo první, odpovídalo by `degraded` na každý dotaz,
    zatímco `start` už ohlásil úspěch.
    """
    print("cb-bond    kontroluji služby pod sebou…", flush=True)
    stack = stack_modul.ServiceStack(_zavislosti(config))
    try:
        stack.ensure(start=not no_deps)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return EXIT_FAILED

    sluzba = service_modul.BondService(config, _parser_klient(config),
                                       log=_logovatko(config))
    try:
        sluzba.build()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return EXIT_BAD_USAGE

    server = api.make_api_server(sluzba, config=config)
    skutecny_port = server.server_address[1]
    _zapis_stav(config, pid=os.getpid(), port=skutecny_port)
    _zvedni_okna(config, sluzba)
    try:
        hotovo = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: hotovo.set())
        # SIGHUP MUSÍ mít obsluhu: bez ní je výchozí akcí ukončení
        # procesu, takže by `reload` službu tiše zabil místo aby ji
        # přenastavil — a vypadalo by to jako pád.
        signal.signal(signal.SIGHUP,
                      lambda *_: _prenastav(sluzba, config))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"cb-bond    BĚŽÍ     {config['service']['host']}:"
              f"{skutecny_port}  pid {os.getpid()}", flush=True)
        hotovo.wait()

        server.shutdown()
        server.server_close()
        return EXIT_OK
    finally:
        _uklid_stav(config)


def _prenastav(sluzba, config: dict[str, Any]) -> None:
    """Znovu načte konfiguraci a nechá páky projevit se.

    Korpus se **nestaví znovu** — to je práce na vteřiny a `reload` má
    být levný. Zneplatní se jen párovač, protože v něm sedí váhy,
    hloubka šíření a prahy; ty se tím přenastaví při dalším dotazu.

    Změna portu se takhle promítnout nedá a netváříme se, že ano.
    """
    try:
        nova = load(config["_meta"]["path"])
    except ConfigError as e:
        print(f"           konfigurace se nenačetla, běžím s původní:\n{e}",
              file=sys.stderr, flush=True)
        return
    if nova["service"]["port"] != config["service"]["port"]:
        print(f"           POZOR: změna portu ({config['service']['port']} → "
              f"{nova['service']['port']}) se za běhu provést nedá — "
              f"vyžaduje restart", file=sys.stderr, flush=True)
    sluzba.config = nova
    sluzba.invalidate()
    print(f"           konfigurace načtena znovu · otisk "
          f"{nova['_meta']['fingerprint']}", flush=True)


def _zvedni_okna(config: dict[str, Any], sluzba) -> None:
    """Zvedne viewBase2 vedle API — graf, dialog, věty, vertikály.

    `viewbase` je **nepovinná** závislost: bez frontendu služba běží dál,
    jen bez oken. Výpadek se ale neututlá — řekne se, co chybí a čím se
    to doinstaluje, jinak by člověk čekal okno, které nikdy nepřijde.

    Běží ve vlákně: `serve` blokuje a služba má obsluhovat REST i tak.
    """
    port = config["service"]["view_port"]
    if not port:
        return
    try:
        from viewbase import GraphWindow, serve

        from cb_bond.mirror import GraphMirror
        from cb_bond.window import EXPECTED_BUNDLE, BondWindows, \
            bundle_fingerprint
    except ImportError as e:
        print(f"           viewBase2 není k dispozici, okna nebudou: {e}\n"
              f"           doinstaluješ: pip install 'viewbase @ "
              f"git+https://github.com/alchy/viewBase2#subdirectory=python'",
              file=sys.stderr, flush=True)
        return

    jmeno, otisk = bundle_fingerprint()
    stav = ("OK" if otisk == EXPECTED_BUNDLE
            else f"JINÁ GENERACE (čekáno {EXPECTED_BUNDLE})")
    print(f"           frontend {jmeno} · otisk {otisk} — {stav}",
          flush=True)

    okno = GraphWindow(title="cb-bond — graf faktů")
    zrcadlo = GraphMirror(okno)
    # `mirror` napřed: graf vznikl při `build()`, tedy dřív než okno,
    # takže v okně žádné uzly nejsou. `refresh` jim jen doplňuje
    # metadata a na neexistujícím uzlu spadne.
    zrcadlo.mirror(sluzba.graph)
    zrcadlo.refresh(sluzba.graph)
    BondWindows(sluzba, okno, mirror=zrcadlo,
                top=config["module"]["matching"]["top_sentences"]).attach()

    host = config["service"]["host"]
    threading.Thread(
        target=lambda: serve(okno, host=host, port=port, block=True),
        daemon=True).start()
    print(f"           viewBase http://{host}:{port}", flush=True)


def _zavislosti(config: dict[str, Any]) -> tuple:
    """Závislosti z konfigurace, v jejím pořadí.

    Pořadí se bere ze souboru, ne z kódu: je to páka, a páky žijí
    v konfiguraci (§ 5).
    """
    return tuple(
        stack_modul.Dependency(s["name"], s["control"], s["endpoint"])
        for s in config["dependencies"]["services"])


def _parser_klient(config: dict[str, Any]):
    """Klient rozboru. Import až tady — službu potřebuje jen běh, ne testy."""
    from cb_udpipe import UdpipeClient
    return UdpipeClient()


def _logovatko(config: dict[str, Any]):
    """Klient loggeru, nebo `None`.

    Nepovinná závislost (§ 4): když logger neběží, klient to ohlásí,
    přepne se do spool režimu a nechá nás běžet. Kdyby padlý logger
    shodil modul, byla by nejméně důležitá součást zároveň nejkřehčí.

    Výpadek se **neututlá** — řekne se to na konzoli. Tichý běh bez logu
    je horší než žádný log: člověk si myslí, že měření má, a nemá.
    """
    try:
        from cb_logger import LogClient
    except ImportError as e:
        print(f"           cb-logger není k dispozici, běží se bez logu: {e}",
              file=sys.stderr, flush=True)
        return None

    nastaveni = config["logging"]
    try:
        return LogClient(
            component="bond",
            endpoint=nastaveni["endpoint"],
            level=nastaveni["level"],
            methods=tuple(nastaveni.get("methods") or ()),
            spool_dir=str(Path(config["runtime"]["pid_file"]).parent
                          / "log-spool"),
        )
    except Exception as e:                    # noqa: BLE001
        print(f"           logovátko se nepodařilo připojit, běží se bez "
              f"něj: {e}", file=sys.stderr, flush=True)
        return None


# ------------------------------------------------------------------ stop


def cmd_stop(config: dict[str, Any]) -> int:
    """Zastaví službu. Služby pod sebou nechává běžet.

    Zastavovat je taky by překvapilo každého, kdo na nich má něco dalšího;
    kdo chce zastavit celý strom, řekne si o to zvlášť.
    """
    pid = _running_pid(config)
    if pid is None:
        osirely = _osirely_pid(config)
        if osirely is not None:
            print(f"cb-bond neběží (osiřelý pid {osirely} — služba spadla)")
            _uklid_stav(config)
        else:
            print("cb-bond neběží")
        return EXIT_NOT_RUNNING

    os.kill(pid, signal.SIGTERM)
    strop = time.monotonic() + config["runtime"]["stop_timeout_s"]
    while time.monotonic() < strop:
        try:
            os.kill(pid, 0)
        except OSError:
            print(f"cb-bond zastaven (pid {pid})")
            return EXIT_OK
        time.sleep(0.05)

    print(f"cb-bond neskončil do {config['runtime']['stop_timeout_s']} s "
          f"(pid {pid})", file=sys.stderr)
    return EXIT_FAILED


# ---------------------------------------------------------------- korpus


#: Co umí `corpus`. `status` a `validate` se ptají na DATA, takže běží
#: i bez služby; `parse` a `build` dělají práci a potřebují parser.
CORPUS_ACTIONS = ("status", "validate", "parse", "build")


def cmd_corpus(config: dict[str, Any], *, akce: str) -> int:
    """Práce s korpusem: co v něm je, jestli je v pořádku, postavit ho.

    Existuje proto, že stavba korpusu je drahá a dnes ji dělá každý
    skript sám. `status` odpovídá i tehdy, když služba neběží — je to
    otázka na data, ne na službu, a člověk ji typicky klade právě ve
    chvíli, kdy služba nenaběhla.
    """
    if akce not in CORPUS_ACTIONS:
        print(f"neznámá akce {akce!r}; umím "
              f"{' · '.join(CORPUS_ACTIONS)}", file=sys.stderr)
        return EXIT_BAD_USAGE

    modul = config["module"]["corpus"]
    adresar = Path(modul["directory"])
    cesty: list[Path] = []
    for vzor in modul["patterns"]:
        cesty.extend(adresar.glob(vzor))
    cesty = sorted(set(cesty))

    if not cesty:
        print(f"korpusový adresář {adresar} nedal žádný soubor "
              f"(vzory {' '.join(modul['patterns'])})\n"
              f"  ukazuješ jinam, než si myslíš? data_root je "
              f"{config['module']['data_root']}", file=sys.stderr)
        return EXIT_BAD_USAGE

    if akce == "status":
        return _corpus_status(cesty, adresar)
    if akce == "validate":
        return _corpus_validate(cesty)
    return _corpus_prace(config, cesty, akce=akce)


def _corpus_status(cesty: list[Path], adresar: Path) -> int:
    """Co leží v datovém kořeni — soubory a jejich velikost."""
    print(f"korpus       {adresar}")
    celkem = 0
    for cesta in cesty:
        velikost = cesta.stat().st_size
        celkem += velikost
        print(f"             {cesta.name:24} {velikost / 1024:8.1f} kB")
    print(f"             {'celkem':24} {celkem / 1024:8.1f} kB "
          f"· {len(cesty)} souborů")
    return EXIT_OK


def _corpus_validate(cesty: list[Path]) -> int:
    """Ověří formát souborů — bez parseru, tedy i bez běžících služeb.

    Kontrolu dělá `cb_field.corpusfile`; tady je jen proto, aby se
    člověk nemusel učit dvě cesty k téže věci.
    """
    from cb_field.corpusfile import load_corpus_file

    spatne = 0
    for cesta in cesty:
        try:
            soubor = load_corpus_file(cesta)
            vet = sum(len(b.sentences) for b in soubor.blocks)
            print(f"             {cesta.name:24} OK  "
                  f"{len(soubor.blocks)} bloků · {vet} vět")
        except (ValueError, OSError) as e:
            spatne += 1
            print(f"             {cesta.name:24} CHYBA  {e}",
                  file=sys.stderr)
    if spatne:
        print(f"vadných souborů: {spatne} z {len(cesty)}", file=sys.stderr)
        return EXIT_FAILED
    print(f"             všech {len(cesty)} souborů v pořádku")
    return EXIT_OK


def _corpus_prace(config: dict[str, Any], cesty: list[Path], *,
                  akce: str) -> int:
    """`parse` naplní cache UDPipe, `build` postaví korpus a graf.

    Obojí potřebuje parser, takže obojí potřebuje běžící cb-udpipe.
    Rozdíl je v tom, co zůstane: `parse` naplní trvalou cache rozborů
    (druhá stavba je pak vteřinová), `build` navíc postaví graf a
    vypíše, co v něm je.
    """
    stack = stack_modul.ServiceStack(_zavislosti(config))
    try:
        stack.ensure(start=True)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return EXIT_FAILED

    sluzba = service_modul.BondService(config, _parser_klient(config),
                                       log=_logovatko(config))
    try:
        stav = sluzba.build()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return EXIT_BAD_USAGE

    if akce == "parse":
        print(f"             cache naplněna z {stav['files']} souborů "
              f"· {stav['sentences']} vět")
        return EXIT_OK
    print(f"             graf     {stav['edges']} hran · "
          f"{stav['lemmas']} lemmat · stupeň {stav['degree']}")
    print(f"             osy      {stav['axes']} celkem")
    return EXIT_OK


# ---------------------------------------------------------------- reload


def cmd_reload(config: dict[str, Any]) -> int:
    """Znovu načte konfiguraci běžící službě (SIGHUP).

    Co znovu načíst nejde — změna portu — vyžaduje `restart`. Tvrdit
    opak by znamenalo službu, která běží s jiným nastavením, než jaké
    má v souboru, a nikdo by nepoznal proč.
    """
    pid = _running_pid(config)
    if pid is None:
        print("cb-bond neběží")
        return EXIT_NOT_RUNNING
    os.kill(pid, signal.SIGHUP)
    print(f"cb-bond dostal SIGHUP (pid {pid}) — konfigurace se načte znovu\n"
          f"  změna portu vyžaduje restart, ta se za běhu nedá provést")
    return EXIT_OK


# ---------------------------------------------------------------- status


def cmd_status(config: dict[str, Any], *, jako_json: bool) -> int:
    """Stav služby a **co má v hlavě**.

    Vrací 0, když služba běží, jinak 3 (§ 12). Čísla jdou od běžící
    služby; neběžící se nedopočítávají.
    """
    zdravi = _zeptej_se(config, "/v1/health")
    stav = _zeptej_se(config, "/v1/state") if zdravi else None
    pid = _running_pid(config)
    modul = config["module"]

    if jako_json:
        print(json.dumps({
            "running": zdravi is not None,
            "pid": pid,
            "port": _port(config),
            "health": zdravi,
            "state": stav,
            "data_root": str(modul["data_root"]),
            "config": config["_meta"]["path"],
        }, ensure_ascii=False))
        return EXIT_OK if zdravi else EXIT_NOT_RUNNING

    if zdravi is None:
        print(f"cb-bond      NEBĚŽÍ   měl by běžet na "
              f"{config['service']['host']}:{config['service']['port']}")
        osirely = _osirely_pid(config)
        if osirely is not None:
            print(f"             pozor    osiřelý pid {osirely} — "
                  f"služba spadla")
        print(f"             korpus   {modul['corpus']['directory']}  ·  "
              f"vzory {' '.join(modul['corpus']['patterns'])}  (nenačteno)")
    else:
        print(f"cb-bond      BĚŽÍ     {config['service']['host']}:"
              f"{_port(config)}  pid {pid}")
        print(f"             zdraví   {zdravi['status']}"
              + (f"  ({zdravi['reason']})" if zdravi.get("reason") else ""))
        _vypis_hlavu(stav)

    print(f"             data     {modul['data_root']}")
    print(f"             config   {config['_meta']['path']}"
          f"  otisk {config['_meta']['fingerprint']}")
    return EXIT_OK if zdravi else EXIT_NOT_RUNNING


def _vypis_hlavu(stav: dict[str, Any] | None) -> None:
    """Statistiky obsahu — to, kvůli čemu `status` u cb-bondu je.

    Nepostavená služba nedostane vymyšlené nuly: „nevím" a „nic tam není"
    jsou dvě různé věci a jen jedna z nich je chyba.
    """
    if not stav or not stav.get("built"):
        print("             korpus   nenačteno")
        return
    print(f"             korpus   {stav['sentences']} vět · "
          f"{stav['files']} souborů")
    print(f"             graf     {stav['edges']} hran · "
          f"{stav['lemmas']} lemmat · {stav['nodes']} uzlů · "
          f"stupeň {stav['degree']}")
    print(f"             osy      {stav['axes']} celkem · "
          f"{stav['custom_axes']} vlastních (verze {stav['axis_version']})")
    print(f"             vazby    {stav['links']} "
          f"(verze {stav['link_version']})")


# ------------------------------------------------------------ běhový stav


def _zapis_stav(config: dict[str, Any], *, pid: int, port: int) -> None:
    """Zapíše PID a SKUTEČNÝ port do `run/`.

    Skutečný port je podstatný, když je v konfiguraci nula a přidělil ho
    systém — jinak by ho nikdo nezjistil (§ 5).
    """
    for cesta, hodnota in ((config["runtime"]["pid_file"], pid),
                           (config["runtime"]["port_file"], port)):
        p = Path(cesta)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{hodnota}\n", encoding="utf-8")


def _uklid_stav(config: dict[str, Any]) -> None:
    """Smaže běhový stav. Smazání `run/` musí být neškodné (§ 2)."""
    for cesta in (config["runtime"]["pid_file"],
                  config["runtime"]["port_file"]):
        try:
            Path(cesta).unlink()
        except OSError:
            pass


def _precti_pid(config: dict[str, Any]) -> int | None:
    """PID ze souboru; `None`, když soubor není nebo je nečitelný."""
    try:
        return int(Path(config["runtime"]["pid_file"]).read_text().strip())
    except (OSError, ValueError):
        return None


def _running_pid(config: dict[str, Any]) -> int | None:
    """PID běžící služby, nebo `None`.

    Ověřuje se, že proces s tím PID **skutečně existuje**: osiřelý soubor
    po spadlé službě by jinak vypadal jako běžící služba.
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

    Vrací se zvlášť, aby to `status` mohl nahlásit místo zamlčení —
    osiřelý soubor znamená, že služba spadla, a to je informace.
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
        skutecny = int(
            Path(config["runtime"]["port_file"]).read_text().strip())
        if skutecny > 0:
            return skutecny
    except (OSError, ValueError):
        pass
    return config["service"]["port"]


def _endpoint(config: dict[str, Any]) -> str:
    return f"http://{config['service']['host']}:{_port(config)}"


def _zeptej_se(config: dict[str, Any], cesta: str) -> dict[str, Any] | None:
    """Zeptá se běžící služby; `None` znamená neodpovídá."""
    try:
        with urllib.request.urlopen(_endpoint(config) + cesta,
                                    timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _cekej_na_version(config: dict[str, Any], strop: float):
    """Čeká, až služba začne odpovídat na `/version`.

    `/version` schválně, ne `/v1/health`: odpovídá i nezdravé službě,
    takže rozliší „nenaběhla" od „naběhla a je jí zle" (§ 7).
    """
    konec = time.monotonic() + strop
    while time.monotonic() < konec:
        odpoved = _zeptej_se(config, "/version")
        if odpoved is not None:
            return odpoved
        time.sleep(0.2)
    return None
