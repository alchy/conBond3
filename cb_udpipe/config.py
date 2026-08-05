"""Konfigurace modulu cb-udpipe — konstanty a kontroly nad sdíleným jádrem.

Načítání, validaci proti schématu, rozvinutí cest i otisk dělá `cb_config`.
Tady zůstává jen to, co je pro modul vlastní: cesty, rozsah portů a verze
schématu.

Dřív tu stál vlastní validátor — tentýž, jaký měly další dva moduly.
Kopie byly úmyslné (politika § 4 měla konečný seznam sdílených modulů),
ale u třetí se to přestalo vyplácet: je to čistá funkce bez stavu, bez
sítě a bez závislostí, kterou potřebuje každý modul dřív, než cokoli
udělá (rozhodnutí J. 2026-08-05).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cb_config import ConfigError, read_json
from cb_config import check_schema_supported as _check_schema_supported
from cb_config import load as _load_shared

#: Adresář modulu. Relativní cesty z konfigurace se počítají vůči němu, ne
#: vůči pracovnímu adresáři procesu — jinak by se chování měnilo podle toho,
#: odkud se služba spustí, a to je chyba, kterou nikdo nehledá na správném
#: místě.
MODULE_DIR = Path(__file__).resolve().parent

#: Výchozí umístění konfigurace. Přebíjí se přepínačem --config.
DEFAULT_CONFIG_PATH = MODULE_DIR / "cb-udpipe-config.json"

#: Schéma, proti kterému se konfigurace ověřuje.
SCHEMA_PATH = MODULE_DIR / "config.schema.json"

#: Verze schématu, které tenhle kód rozumí. Když konfigurace nese jinou,
#: start selže — tiché načtení podle špatného předpokladu vyrobí čísla,
#: která vypadají správně (§ 14).
SUPPORTED_CONFIG_VERSION = 1

#: Rozsah portů, který patří modulu (§ 5).
PORT_RANGE = (42200, 42299)

#: Kde v konfiguraci porty stojí.
PORT_KEYS = (
    ('service', 'port'),
    ('module', 'upstream', 'port'),
)

#: Cesty relativní vůči ADRESÁŘI MODULU. PID, port a vendorovaný
#: kód nejsou data — zůstávají v repozitáři a mizí s ním.
MODULE_PATH_KEYS = (
    ('runtime', 'pid_file'),
    ('runtime', 'port_file'),
    ('runtime', 'self_log', 'path'),
    ('module', 'upstream', 'vendor_dir'),
)

#: Cesty relativní vůči `data_root`, který leží MIMO repozitář
#: (oddělení kódu od dat, rozhodnutí J. 2026-08-05). Vyjmenované
#: schválně: hádání podle jména („končí na _dir, tak je to cesta")
#: by se rozešlo s obsahem, jakmile přibude klíč, který se tak
#: jmenuje a cesta není.
DATA_PATH_KEYS = (
    ('module', 'cache', 'dir'),
    ('module', 'upstream', 'model_dir'),
    ('module', 'upstream', 'hf_home'),
)


__all__ = ["load", "ConfigError", "MODULE_DIR", "DEFAULT_CONFIG_PATH",
           "SCHEMA_PATH", "SUPPORTED_CONFIG_VERSION", "PORT_RANGE"]


def _data_root(path) -> Path:
    """Datový kořen z konfigurace — čte se dřív, než se cesty rozvinou.

    Musí se přečíst zvlášť: `resolve_paths` potřebuje základnu předem
    a ta stojí uvnitř téhož souboru, který se teprve načítá.
    """
    surova = read_json(
        Path(path if path is not None else DEFAULT_CONFIG_PATH).resolve(),
        co="konfigurace")
    return Path(str(surova.get("data_root", "/")))


def load(path: str | Path | None = None) -> dict[str, Any]:
    """Načte konfiguraci, ověří ji proti schématu a doplní odvozené hodnoty.

    Vstup:
        path: cesta ke konfiguraci. `None` znamená výchozí umístění vedle
            modulu. Cesta se předává explicitně, aby test mohl ukázat jinam
            než provoz — bez toho by testy měřily proti provozním datům.

    Výstup:
        Slovník s konfigurací, doplněný o `fingerprint` a `_meta` s cestou,
        ze které se načetla. Cesta se vypisuje při startu a zapisuje do
        logu; jinak nikdo nezjistí, které nastavení vlastně běží.

    Při chybě:
        `ConfigError` s českou hláškou, která říká, co konkrétně je špatně
        a kde. Nikdy nevrací částečně načtenou konfiguraci.
    """
    return _load_shared(
        path if path is not None else DEFAULT_CONFIG_PATH,
        SCHEMA_PATH,
        supported_version=SUPPORTED_CONFIG_VERSION,
        checks=[_check_ports],
        path_specs=([(k, MODULE_DIR) for k in MODULE_PATH_KEYS]
                    + [(k, _data_root(path)) for k in DATA_PATH_KEYS]),)


def _check_ports(config: dict[str, Any]) -> list[str]:
    """Porty musejí ležet v rozsahu modulu (§ 5).

    Kontroluje se proto, že cizí port se jinak pozná až tím, že se dva
    moduly poperou o totéž číslo — a to bývá za provozu, ne při startu.

    Při chybě:
        Nevyhazuje — chyby vrací, aby se ohlásily spolu s ostatními.
    """
    od, do = PORT_RANGE
    chyby: list[str] = []
    for klice in PORT_KEYS:
        uzel: Any = config
        for klic in klice:
            uzel = uzel.get(klic) if isinstance(uzel, dict) else None
        if not isinstance(uzel, int) or isinstance(uzel, bool) or uzel == 0:
            continue        # špatný typ ohlásilo schéma; nula = přidělí systém
        if not od <= uzel <= do:
            chyby.append(
                f"{'.'.join(klice)}: {uzel} je mimo rozsah modulu {od}–{do}. "
                f"Cizí port se pozná až tím, že se dva moduly poperou "
                f"o totéž číslo.")
    return chyby
