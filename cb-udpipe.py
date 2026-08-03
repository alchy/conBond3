#!/usr/bin/env python3
"""Ovládání služby cb-udpipe.

    ./cb-udpipe.py start   [--config PATH] [--foreground]
    ./cb-udpipe.py stop    [--timeout SEC]
    ./cb-udpipe.py restart [--config PATH]
    ./cb-udpipe.py reload
    ./cb-udpipe.py status  [--json]

Návratové kódy: 0 uspěl · 1 selhal · 2 špatné argumenty nebo konfigurace ·
3 služba neběží.

Tenhle soubor je jen dveře. Logika řízení je v `cb_udpipe/control.py`, aby
šla otestovat bez spouštění procesu (README-MODULES.md § 12).
"""

import os
import sys
from pathlib import Path

KOREN = Path(__file__).resolve().parent
VENV_PYTHON = KOREN / ".venv" / "bin" / "python"


def _prepni_na_projektovy_interpret() -> None:
    """Přepne běh na interpret z `.venv`, když jsme na jiném.

    Proč je to potřeba: shebang `#!/usr/bin/env python3` vezme **první**
    `python3` z PATH, což je systémový interpret — na vývojovém stroji to byl
    Python 3.14, zatímco projekt stojí na 3.11 a `./run-python` na tom trvá.
    Služba by tedy běžela na jiné verzi než testy a než měření, které se
    proti ní pouští.

    Naměřeno při stavbě: služba spuštěná přes `./cb-udpipe.py start` hlásila
    na `GET /version` Python 3.14.6, kdežto měřicí skript pod `./run-python`
    běžel na 3.11.15. Je to tatáž třída vady, na kterou doplatil conBond2 —
    měřilo se proti něčemu jinému, než se tvrdilo.

    Přepnutí je `os.execv`, tedy nahrazení procesu: nevzniká druhý proces ani
    režie navíc a `$$` zůstává platné pro PID soubor.

    Vstup:
        Nic; čte `sys.executable` a `sys.argv`.

    Výstup:
        Nic. Buď se vrátí (už běžíme správně), nebo se proces nahradí.

    Při chybě:
        Nevyhazuje. Chybějící `.venv` znamená běh dál na současném interpretu:
        náš kód vystačí se standardní knihovnou a spustit se má i tam, kde
        prostředí ještě není postavené. Že UDPipe pak nepůjde spustit, ohlásí
        `control.py` vlastní hláškou.
    """
    if not VENV_PYTHON.is_file():
        return
    if Path(sys.executable).resolve() == VENV_PYTHON.resolve():
        return
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve())]
             + sys.argv[1:])


_prepni_na_projektovy_interpret()

# Kořen projektu na cestu, aby `import cb_udpipe` fungoval i při spuštění
# odjinud. `./run-python` dělá totéž přes PYTHONPATH; tady je to proto, aby
# šel skript spustit i přímo.
sys.path.insert(0, str(KOREN))

from cb_udpipe.control import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
