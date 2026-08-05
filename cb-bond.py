#!/usr/bin/env python3
"""Ovládání služby cb-bond — vrcholové služby projektu.

    ./cb-bond.py start   [--config PATH] [--foreground] [--no-deps]
    ./cb-bond.py stop
    ./cb-bond.py restart [--config PATH] [--no-deps]
    ./cb-bond.py status  [--json]

`start` nejdřív zajistí služby POD sebou (logger, pak udpipe) a teprve
pak staví korpus a zvedá vlastní API. `--no-deps` to vypne pro případ,
kdy si člověk služby řídí sám.

`status` neříká jen že služba běží, ale **co má v hlavě** — kolik vět,
hran, lemmat a os. Obsah se mění učením a promocí, takže bez čísel se
nedá poznat, jestli běží model, který se učil, nebo čerstvě postavený.

Návratové kódy: 0 uspěl · 1 selhal · 2 špatné argumenty nebo konfigurace ·
3 služba neběží.

Tenhle soubor je jen dveře. Logika řízení je v `cb_bond/control.py`, aby
šla otestovat bez spouštění procesu (README-MODULES.md § 12).
"""

import os
import sys
from pathlib import Path

KOREN = Path(__file__).resolve().parent
VENV_PYTHON = KOREN / ".venv" / "bin" / "python"


# Přepnutí do projektového interpretu. Shebang `env python3` najde ten, který
# je zrovna v PATH — na tomhle stroji je to homebrew 3.14, zatímco projekt
# stojí na 3.11 a `./run-python` na tom trvá. Bez tohohle řezu běžela služba
# na jiné verzi než testy i než měření, které se proti ní pouští: `GET
# /version` hlásil 3.14.6, kdežto měřicí skript 3.11.15. Je to tatáž třída
# vady, na kterou doplatil conBond2 — měřilo se proti něčemu jinému, než se
# tvrdilo.
#
# `os.execv` nahradí proces, takže nevzniká druhý ani režie navíc.
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve())]
             + sys.argv[1:])

# Bez prostředí se nespouští. Kód modulů sice nemá závislosti, ale stojí na
# syntaxi Pythonu 3.10+ (`str | None`) a projekt je přišpendlený na 3.11 —
# služba běžící na neověřené verzi je horší než služba, která nenaběhla
# (README-MODULES.md § 9). Sjednoceno se sourozenci.
if not VENV_PYTHON.exists():
    sys.exit(
        f"chybí virtuální prostředí: {KOREN / '.venv'}\n"
        f"Vytvoř ho:\n"
        f"  python3.11 -m venv .venv\n"
        f"  .venv/bin/pip install -r requirements.txt"
    )

# Kořen projektu na cestu, aby `import cb_bond` fungoval i při spuštění
# odjinud. `./run-python` dělá totéž přes PYTHONPATH; tady je to proto, aby
# šel skript spustit i přímo.
sys.path.insert(0, str(KOREN))

from cb_bond.control import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
