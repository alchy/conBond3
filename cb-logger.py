#!/usr/bin/env python3
"""Ovládání služby cb-logger.

Tenhle skript je jen dveře — zpracování příkazů i logika řízení jsou
v `cb_logger/control.py`, aby šly testovat jako kód, ne jako podproces
(README-MODULES.md § 12).

Použití:

    ./cb-logger.py start   [--config PATH] [--foreground]
    ./cb-logger.py stop    [--timeout SEC]
    ./cb-logger.py restart [--config PATH]
    ./cb-logger.py reload
    ./cb-logger.py status  [--json]

Návratové kódy: 0 uspěl · 1 selhal · 2 špatné argumenty nebo konfigurace ·
3 služba neběží.
"""

import os
import sys
from pathlib import Path

KOREN = Path(__file__).resolve().parent
VENV_PYTHON = KOREN / ".venv" / "bin" / "python"

# Přepnutí do projektového interpretu. Shebang `env python3` najde ten, který
# je zrovna v PATH — na tomhle stroji /usr/bin/python3 je 3.9 a syntaxi
# `int | None` neumí, takže by skript spadl na importu s hláškou, která
# s příčinou nesouvisí. Projekt stojí na jednom .venv (README-MODULES.md § 19)
# a služba musí běžet právě v něm, ať se spustí odkudkoli a jakkoli.
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve())]
             + sys.argv[1:])

if not VENV_PYTHON.exists():
    sys.exit(
        f"chybí virtuální prostředí: {KOREN / '.venv'}\n"
        f"Vytvoř ho:\n"
        f"  python3.11 -m venv .venv\n"
        f"  .venv/bin/pip install -r requirements.txt"
    )

# Kořen projektu na cestu, aby `import cb_logger` fungoval bez ohledu na to,
# odkud se skript spustí. Bez toho by `./cb-logger.py` fungovalo jen z kořene.
sys.path.insert(0, str(KOREN))

from cb_logger.control import main  # noqa: E402 — až po úpravě sys.path

if __name__ == "__main__":
    sys.exit(main())
