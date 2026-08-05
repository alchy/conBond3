"""Konfigurace modulu cb-bond — konstanty a kontroly nad sdíleným jádrem.

Načítání, validaci proti schématu, rozvinutí cest i otisk dělá `cb_config`.
Tady zůstává jen to, co je pro cb-bond vlastní: rozsah portů, seznam cest
a dvě kontroly, které schéma vyjádřit neumí.

## Dvě základny cest — a proč

Sourozenci mají jednu: všechno relativní vůči adresáři modulu. cb-bond má
dvě, protože kód a data jsou oddělené (rozhodnutí J. 2026-08-05):

    runtime/*          → vůči ADRESÁŘI MODULU. PID a port nejsou data,
                         jsou to stav procesu a mají zmizet s ním.
    module/* (datové)  → vůči `data_root`, který leží MIMO repozitář.

`data_root` je **jediná absolutní cesta v konfiguraci**. Tím zůstává
zachované to, co chránilo pravidlo § 19 („modul nesmí sahat mimo
repozitář"): cesta se nedá vyrobit potichu za běhu, přenos instalace je
změna jednoho řádku, a `status` ji musí vypsat — jinak člověk hledá chybu
v datech, která služba vůbec nečte.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cb_config import ConfigError, read_json
from cb_config import check_schema_supported as _check_schema_supported
from cb_config import load as _load_shared

#: Adresář modulu. Běhové cesty se počítají vůči němu, ne vůči pracovnímu
#: adresáři procesu — jinak by se chování měnilo podle toho, odkud se služba
#: spustí, a to je chyba, kterou nikdo nehledá na správném místě.
MODULE_DIR = Path(__file__).resolve().parent

#: Výchozí umístění konfigurace. Přebíjí se přepínačem --config.
DEFAULT_CONFIG_PATH = MODULE_DIR / "cb-bond-config.json"

#: Schéma, proti kterému se konfigurace ověřuje.
SCHEMA_PATH = MODULE_DIR / "config.schema.json"

#: Verze schématu, které tenhle kód rozumí.
SUPPORTED_CONFIG_VERSION = 1

#: Rozsah portů, který patří modulu (§ 5). Port 8080, na kterém dřív běžel
#: graf, sem nepatří — byl to CIZÍ port mimo rozsah projektu.
PORT_RANGE = (42400, 42499)

#: Cesty relativní vůči ADRESÁŘI MODULU (stav procesu, zůstává v repozitáři).
MODULE_PATH_KEYS = (
    ("runtime", "pid_file"),
    ("runtime", "port_file"),
    ("runtime", "self_log", "path"),
)

#: Cesty relativní vůči `data_root` (data, leží mimo repozitář).
DATA_PATH_KEYS = (
    ("module", "corpus", "directory"),
    ("module", "relations", "dictionary_dir"),
    ("module", "state", "registry_dir"),
)

__all__ = ["load", "ConfigError", "MODULE_DIR", "DEFAULT_CONFIG_PATH",
           "SCHEMA_PATH", "PORT_RANGE", "SUPPORTED_CONFIG_VERSION"]


def load(path: str | Path | None = None) -> dict[str, Any]:
    """Načte konfiguraci cb-bondu a rozvine cesty proti oběma základnám.

    Vstup:
        path: cesta ke konfiguraci; `None` znamená výchozí umístění vedle
            modulu. Předává se explicitně, aby test mohl ukázat jinam než
            provoz — jinak by testy měřily proti provozním datům.

    Výstup:
        Slovník s konfigurací; cesty absolutní, `fingerprint` s otiskem.

    Při chybě:
        `ConfigError` s českou hláškou, co konkrétně je špatně a kde.
    """
    cesta = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    surova = read_json(Path(cesta).resolve(), co="konfigurace")
    koren = Path(str(surova.get("module", {}).get("data_root", "/")))

    return _load_shared(
        cesta, SCHEMA_PATH,
        supported_version=SUPPORTED_CONFIG_VERSION,
        checks=[_check_ports, _check_data_root],
        path_specs=([(k, MODULE_DIR) for k in MODULE_PATH_KEYS]
                    + [(k, koren) for k in DATA_PATH_KEYS]))


# --- kontroly nad rámec schématu -----------------------------------------

def _check_ports(config: dict[str, Any]) -> list[str]:
    """Porty musejí ležet v rozsahu modulu a nesmějí kolidovat mezi sebou."""
    chyby: list[str] = []
    sluzba = config.get("service")
    if not isinstance(sluzba, dict):
        return chyby
    videne: dict[int, str] = {}
    for klic in ("port", "view_port"):
        hodnota = sluzba.get(klic)
        if not isinstance(hodnota, int) or hodnota == 0:
            continue          # nula = přidělí systém, to je v pořádku
        if not PORT_RANGE[0] <= hodnota <= PORT_RANGE[1]:
            chyby.append(
                f"service.{klic} = {hodnota} je mimo rozsah modulu "
                f"{PORT_RANGE[0]}–{PORT_RANGE[1]}; sáhnout po cizím portu "
                f"je chyba, ne rozhodnutí (§ 5)")
        if hodnota in videne:
            chyby.append(
                f"service.{klic} = {hodnota} koliduje se "
                f"service.{videne[hodnota]}; dvě věci na jednom portu se "
                f"poperou až za provozu")
        videne[hodnota] = klic
    return chyby


def _check_data_root(config: dict[str, Any]) -> list[str]:
    """`data_root` musí být absolutní; datové cesty naopak relativní.

    Kdyby byla datová cesta absolutní, přenos instalace by přestal být
    změnou jednoho řádku a někdo by si vyrobil druhou sadu dat, aniž by to
    bylo z konfigurace poznat.
    """
    modul = config.get("module")
    if not isinstance(modul, dict):
        return []
    chyby: list[str] = []
    koren = modul.get("data_root")
    if isinstance(koren, str) and not Path(koren).is_absolute():
        chyby.append(f"module.data_root = {koren!r} musí být absolutní — "
                     f"je to jediná absolutní cesta v konfiguraci")
    for cesta_klicu in DATA_PATH_KEYS:
        hodnota = _projdi(config, cesta_klicu)
        if isinstance(hodnota, str) and Path(hodnota).is_absolute():
            chyby.append(
                f"{'.'.join(cesta_klicu)} = {hodnota!r} je absolutní; datové "
                f"cesty jsou relativní vůči data_root")
    return chyby


def _projdi(config: dict[str, Any], cesta_klicu) -> Any:
    """Hodnota na cestě klíčů, nebo None — bez pádu na chybějícím uzlu."""
    uzel: Any = config
    for klic in cesta_klicu:
        if not isinstance(uzel, dict):
            return None
        uzel = uzel.get(klic)
    return uzel
