"""Wrapper nad UDPipe 2: perfektní tokenizace, rozbor a cache rozborů.

Pošle se věta, dostane se kvalitní rozbor. Modul kromě volání UDPipe opravuje
jeho tokenizaci (zkratky, řadové číslovky, číselné skupiny — zhruba každá
jedenáctá věta korpusu ji má vadnou) a rozebrané věty si trvale pamatuje.

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

__all__ = ["__version__", "__api__"]
