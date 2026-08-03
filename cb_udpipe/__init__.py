"""Wrapper nad UDPipe 2: perfektní tokenizace, rozbor a cache rozborů.

Pošle se věta, dostane se kvalitní rozbor. Modul kromě volání UDPipe opravuje
jeho tokenizaci (zkratky, řadové číslovky, číselné skupiny — zhruba každá
jedenáctá věta korpusu ji má vadnou) a rozebrané věty si trvale pamatuje.

```python
from cb_udpipe import UdpipeClient

parser = UdpipeClient(endpoint=cfg["module"]["udpipe_endpoint"], log=log)
vety = parser.parse(text="R.U.R. je drama Karla Čapka.", trace=trace)

vety.sentences[0].tokens[0].form        # "R.U.R."  ← opravená tokenizace
vety.sentences[0].from_cache            # bylo to už rozebrané?
```

Co je tady, je veřejné API. Co tady není, je vnitřek a smí se kdykoli změnit
(README-MODULES.md § 3).
"""

#: Verze modulu. Roste s každou změnou chování; čte ji `GET /version`, aby šlo
#: z logu poznat, co běželo. Žije v kódu, ne v konfiguraci — konfigurace by se
#: s kódem rozešla při první úpravě (README-MODULES.md § 14).
__version__ = "0.1.0"

#: Verze rozhraní, které služba obsluhuje. Při přechodu na v2 tu chvíli stojí
#: obě, aby klienti měli čas přejít.
__api__ = ["v1"]

# Import až za verzemi: `client.py` si `__api__` bere, aby ověřil, že služba
# mluví jazykem, kterému rozumí.
from cb_udpipe.client import (  # noqa: E402
    IncompatibleApi,
    ServiceUnavailable,
    UdpipeClient,
    from_config,
)
from cb_udpipe.conllu import Multiword, Sentence, Token  # noqa: E402
from cb_udpipe.service import ParsedSentence, ParseResult  # noqa: E402

__all__ = [
    # klient — tohle si berou ostatní moduly
    "UdpipeClient",
    "from_config",
    "ServiceUnavailable",
    "IncompatibleApi",
    # datové typy, které klient vrací
    "ParseResult",
    "ParsedSentence",
    "Sentence",
    "Token",
    "Multiword",
    "__version__",
    "__api__",
]
