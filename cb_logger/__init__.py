"""Sdílené logovátko systému conBond3.

Modul, na který smí importovat kdokoli (README-MODULES.md § 4). Ostatní moduly z něj
berou typy záznamu a — až bude hotový — klienta, kterým do logovátka zapisují.

Co je tady, je veřejné API. Co tady není, je vnitřek a smí se kdykoli změnit.
"""

from cb_logger.client import (
    IncompatibleApi,
    LogClient,
    ServiceUnavailable,
    from_config,
)
from cb_logger.record import (
    RECORD_FORMAT_VERSION,
    Level,
    LogRecord,
    Result,
    from_wire,
)

#: Verze modulu. Roste s každou změnou chování; čte ji `GET /version`, aby šlo
#: z logu poznat, co běželo. Žije v kódu, ne v konfiguraci — konfigurace by se
#: s kódem rozešla při první úpravě (README-MODULES.md § 14).
__version__ = "0.1.0"

#: Verze rozhraní, které služba obsluhuje. Při přechodu na v2 tu chvíli stojí
#: obě, aby klienti měli čas přejít.
__api__ = ["v1"]

__all__ = [
    # klient — tohle si berou ostatní moduly
    "LogClient",
    "from_config",
    "ServiceUnavailable",
    "IncompatibleApi",
    # typy záznamu
    "Level",
    "Result",
    "LogRecord",
    "from_wire",
    "RECORD_FORMAT_VERSION",
    "__version__",
    "__api__",
]
