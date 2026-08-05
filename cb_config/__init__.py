"""cb-config — sdílené načítání a ověřování konfigurace modulů.

Modul vznikl sloučením tří kopií (`cb_logger`, `cb_udpipe`, `cb_bond`),
které se lišily jen konstantami: rozsahem portů, seznamem cest a několika
kontrolami navíc. Dohromady to bylo 1 190 řádků, z nichž se skoro tisíc
opakoval doslova.

Kopie tam původně byly úmyslně — politika § 4 měla konečný seznam
sdílených modulů (jen `cb-logger`) a rozšířit ho znamenalo změnit
politiku. To pravidlo řešilo, aby moduly nezačaly na sobě viset kvůli
maličkostem. U validátoru konfigurace je ale poměr obrácený: je to čistá
funkce bez stavu, bez sítě a bez závislostí, kterou potřebuje **každý**
modul dřív, než cokoli udělá. Třetí kopie byla ta, u které se to přestalo
vyplácet (rozhodnutí J. 2026-08-05).

```python
from cb_config import ConfigError, load

def nacti(path=None):
    return load(path or DEFAULT_CONFIG_PATH, SCHEMA_PATH,
                supported_version=1,
                checks=[_zkontroluj_porty],
                path_specs=[(("runtime", "pid_file"), MODULE_DIR)])
```

Co je tady, je veřejné API. Co tady není, je vnitřek a smí se kdykoli
změnit (README-MODULES.md § 3).

## Čím se tenhle modul liší od ostatních

Je to **knihovna, ne služba**: nemá port, REST API ani ovládací program,
protože nemá co obsluhovat. Konfiguraci potřebuje každý modul *před*
startem, takže kdyby ji poskytovala služba, nešlo by ji použít k jejímu
vlastnímu startu.
"""

#: Verze modulu; roste s každou změnou chování.
__version__ = "0.1.0"

from cb_config.loader import (  # noqa: E402
    ConfigError,
    check_schema_supported,
    fingerprint,
    load,
    read_json,
    resolve_paths,
    validate,
)

__all__ = [
    "load",
    "validate",
    "resolve_paths",
    "fingerprint",
    "read_json",
    "check_schema_supported",
    "ConfigError",
    "__version__",
]
