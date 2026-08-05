"""Konfigurace modulu cb-logger — konstanty a kontroly nad sdíleným jádrem.

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

from cb_config import ConfigError
from cb_config import check_schema_supported as _check_schema_supported
from cb_config import load as _load_shared

#: Adresář modulu. Relativní cesty z konfigurace se počítají vůči němu, ne
#: vůči pracovnímu adresáři procesu — jinak by se chování měnilo podle toho,
#: odkud se služba spustí, a to je chyba, kterou nikdo nehledá na správném
#: místě.
MODULE_DIR = Path(__file__).resolve().parent

#: Výchozí umístění konfigurace. Přebíjí se přepínačem --config.
DEFAULT_CONFIG_PATH = MODULE_DIR / "cb-logger-config.json"

#: Schéma, proti kterému se konfigurace ověřuje.
SCHEMA_PATH = MODULE_DIR / "config.schema.json"

#: Verze schématu, které tenhle kód rozumí. Když konfigurace nese jinou,
#: start selže — tiché načtení podle špatného předpokladu vyrobí čísla,
#: která vypadají správně (§ 14).
SUPPORTED_CONFIG_VERSION = 1

#: Klíče, jejichž hodnota je cesta. Vyjmenované schválně: hádání podle
#: jména („končí na _dir, tak je to cesta") by se rozešlo s obsahem, jakmile
#: přibude klíč, který se tak jmenuje a cesta není.
PATH_KEYS = (
    ('runtime', 'pid_file'),
    ('runtime', 'port_file'),
    ('runtime', 'self_log', 'path'),
    ('module', 'storage', 'dir'),
    ('module', 'storage', 'objects_dir'),
    ('module', 'routing', 'default'),
    ('module', 'summary', 'path'),
    ('module', 'objects', 'stream'),
)

__all__ = ["load", "ConfigError", "MODULE_DIR", "DEFAULT_CONFIG_PATH",
           "SCHEMA_PATH", "SUPPORTED_CONFIG_VERSION"]


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
        checks=[],
        path_specs=[(klice, MODULE_DIR) for klice in PATH_KEYS],
        post_resolve=_resolve_routing_rules)


def _resolve_routing_rules(config: dict[str, Any]) -> dict[str, Any]:
    """Rozvine cesty UVNITŘ pravidel směrování.

    Seznamem klíčů se vyjádřit nedají: pravidel je proměnný počet a cesta
    je v každém z nich. Hádat podle jména klíče by se rozešlo s obsahem,
    jakmile přibude pravidlo s klíčem, který cestu nenese.
    """
    for pravidlo in config.get("module", {}).get("routing", {}).get(
            "rules", []):
        if isinstance(pravidlo, dict) and isinstance(pravidlo.get("to"), str):
            cesta = Path(pravidlo["to"])
            pravidlo["to"] = str(cesta if cesta.is_absolute()
                                 else MODULE_DIR / cesta)
    return config
