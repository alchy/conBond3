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

import sys
from pathlib import Path

# Kořen projektu na cestu, aby `import cb_udpipe` fungoval i při spuštění
# odjinud. `./run-python` dělá totéž přes PYTHONPATH; tady je to proto, aby
# šel skript spustit i přímo.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cb_udpipe.control import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
