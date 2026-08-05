"""Načtení a ověření konfigurace modulu cb-bond.

Proč se validuje při startu a ne při prvním použití: služba, která
nastartovala se špatnou konfigurací, je horší než služba, která
nenastartovala. Chyba v nastavení se pak projeví až za hodinu uprostřed
dávky, na místě, které s příčinou nesouvisí.

Proč vlastní validátor místo knihovny `jsonschema`: kód modulů nesmí mít
závislosti (README-MODULES.md § 19). Validátor zvládá jen tu část JSON
Schema, kterou naše schémata používají, a na cokoli jiného **hlasitě
upozorní** — nikdy tiše neprojde.

Tvar validátoru je převzatý z `cb_udpipe/config.py` (a ten z
`cb_logger/config.py`); liší se konstanty, seznam cest a kontrola portů.

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

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

#: Adresář modulu. Běhové cesty se počítají vůči němu, ne vůči pracovnímu
#: adresáři procesu — jinak by se chování měnilo podle toho, odkud se služba
#: spustí, a to je chyba, kterou nikdo nehledá na správném místě.
MODULE_DIR = Path(__file__).resolve().parent

#: Výchozí umístění konfigurace. Přebíjí se přepínačem --config.
DEFAULT_CONFIG_PATH = MODULE_DIR / "cb-bond-config.json"

#: Schéma, proti kterému se konfigurace ověřuje.
SCHEMA_PATH = MODULE_DIR / "config.schema.json"

#: Verze schématu, které tenhle kód rozumí. Když konfigurace nese jinou,
#: start selže — tiché načtení podle špatného předpokladu vyrobí čísla,
#: která vypadají správně (§ 14).
SUPPORTED_CONFIG_VERSION = 1

#: Rozsah portů, který patří modulu (§ 5). Kontroluje se proto, že jinak se
#: kolize pozná až za provozu. Port 8080, na kterém dřív běžel graf, sem
#: nepatří — byl to CIZÍ port mimo rozsah projektu.
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

#: Klíče schématu, kterým validátor rozumí. Cokoli jiného ve schématu je
#: chyba schématu, ne konfigurace, a ohlásí se zvlášť.
SUPPORTED_SCHEMA_KEYWORDS = frozenset({
    "$schema", "title", "description", "type", "properties", "required",
    "additionalProperties", "items", "enum", "minimum", "maximum",
})

_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
}


class ConfigError(Exception):
    """Konfigurace je neplatná nebo se nedá načíst.

    Vlastní typ, aby ovládací program poznal tuhle chybu od ostatních
    a vrátil návratový kód 2 (§ 12) místo obecné jedničky.
    """


def load(path: str | Path | None = None) -> dict[str, Any]:
    """Načte konfiguraci, ověří ji a rozvine cesty proti oběma základnám.

    Vstup:
        path: cesta ke konfiguraci; `None` znamená výchozí umístění vedle
            modulu. Předává se explicitně, aby test mohl ukázat jinam než
            provoz — jinak by testy měřily proti provozním datům.

    Výstup:
        Slovník s konfigurací. Cesty jsou absolutní, `fingerprint` nese
        otisk obsahu (bez něj se nedají porovnat dva běhy) a `_meta` cestu,
        ze které se načetla.

    Při chybě:
        `ConfigError` s českou hláškou, která říká, co konkrétně je špatně
        a kde. Nikdy nevrací částečně načtenou konfiguraci.
    """
    cesta = (Path(path) if path is not None else DEFAULT_CONFIG_PATH).resolve()

    surova = _read_json(cesta, co="konfigurace")
    schema = _read_json(SCHEMA_PATH, co="schéma konfigurace")
    _check_schema_supported(schema)

    chyby = _validate(surova, schema, kde="")
    chyby += _check_ports(surova)
    chyby += _check_data_root(surova)
    if chyby:
        raise ConfigError(f"neplatná konfigurace {cesta}:\n"
                          + "\n".join(f"  {ch}" for ch in chyby))

    verze = surova["config_version"]
    if verze != SUPPORTED_CONFIG_VERSION:
        raise ConfigError(
            f"neplatná konfigurace {cesta}:\n"
            f"  config_version je {verze}, tenhle kód rozumí "
            f"{SUPPORTED_CONFIG_VERSION}\n"
            f"  Konfigurace se musí převést, ne načíst — starý tvar podle "
            f"nového předpokladu vyrobí čísla, která vypadají správně.")

    hotova = _resolve_paths(surova)
    hotova["fingerprint"] = _fingerprint(surova)
    hotova["_meta"] = {"path": str(cesta), "module_dir": str(MODULE_DIR)}
    return hotova


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


# --- vnitřek ---------------------------------------------------------------

def _projdi(config: dict[str, Any], cesta_klicu) -> Any:
    uzel: Any = config
    for klic in cesta_klicu:
        if not isinstance(uzel, dict):
            return None
        uzel = uzel.get(klic)
    return uzel


def _read_json(cesta: Path, *, co: str) -> dict[str, Any]:
    try:
        obsah = cesta.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"chybí {co}: {cesta}") from None
    except OSError as e:
        raise ConfigError(f"{co} {cesta} nejde přečíst: {e}") from None
    try:
        data = json.loads(obsah)
    except json.JSONDecodeError as e:
        raise ConfigError(
            f"{co} {cesta} není platný JSON: řádek {e.lineno}, "
            f"sloupec {e.colno}: {e.msg}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{co} {cesta} musí být objekt, ne "
                          f"{type(data).__name__}")
    return data


def _check_schema_supported(schema: dict[str, Any]) -> None:
    """Validátor umí jen část JSON Schema; na zbytek hlasitě upozorní."""
    nezname: set[str] = set()

    def projdi(uzel: Any, kde: str) -> None:
        if isinstance(uzel, dict):
            for klic, hodnota in uzel.items():
                if kde.endswith("properties") or kde.endswith("properties."):
                    projdi(hodnota, f"{kde}{klic}.")
                    continue
                if klic not in SUPPORTED_SCHEMA_KEYWORDS:
                    nezname.add(f"{kde}{klic}")
                    continue
                if klic in ("properties", "items"):
                    projdi(hodnota, f"{kde}{klic}"
                           + ("." if klic == "properties" else "."))

    projdi(schema, "")
    if nezname:
        raise ConfigError(
            "schéma konfigurace používá klíče, kterým tenhle validátor "
            "nerozumí:\n"
            + "\n".join(f"  {k}" for k in sorted(nezname))
            + "\n  Nedostatečný validátor, který mlčí, je horší než žádný.")


def _validate(hodnota: Any, schema: dict[str, Any], *, kde: str) -> list[str]:
    chyby: list[str] = []
    ocekavany = schema.get("type")
    if ocekavany:
        typy = _JSON_TYPES.get(ocekavany, ())
        if ocekavany == "number" and isinstance(hodnota, bool):
            typy = ()
        if ocekavany == "integer" and isinstance(hodnota, bool):
            typy = ()
        if not isinstance(hodnota, typy):
            return [f"{kde or '(kořen)'}: čekám {ocekavany}, je "
                    f"{type(hodnota).__name__}"]

    if "enum" in schema and hodnota not in schema["enum"]:
        chyby.append(f"{kde}: hodnota {hodnota!r} není z "
                     f"{schema['enum']}")
    for mez, znak in (("minimum", "<"), ("maximum", ">")):
        if mez in schema and isinstance(hodnota, (int, float)):
            prekroceno = (hodnota < schema[mez] if mez == "minimum"
                          else hodnota > schema[mez])
            if prekroceno:
                chyby.append(f"{kde}: {hodnota} je {znak} {schema[mez]}")

    if isinstance(hodnota, dict):
        chyby += _validate_object(hodnota, schema, kde=kde)
    elif isinstance(hodnota, list) and "items" in schema:
        for i, prvek in enumerate(hodnota):
            chyby += _validate(prvek, schema["items"], kde=f"{kde}[{i}]")
    return chyby


def _validate_object(hodnota: dict, schema: dict[str, Any], *,
                     kde: str) -> list[str]:
    chyby: list[str] = []
    vlastnosti = schema.get("properties", {})
    for klic in schema.get("required", []):
        if klic not in hodnota:
            chyby.append(f"{kde}{'.' if kde else ''}{klic}: chybí povinný "
                         f"klíč")
    if schema.get("additionalProperties") is False:
        for klic in hodnota:
            if klic not in vlastnosti:
                chyby.append(
                    f"{kde}{'.' if kde else ''}{klic}: neznámý klíč — "
                    f"obvykle překlep, a tiše ignorovaný překlep znamená, "
                    f"že běží jiné nastavení, než si člověk myslí")
    for klic, podschema in vlastnosti.items():
        if klic in hodnota:
            chyby += _validate(hodnota[klic], podschema,
                               kde=f"{kde}{'.' if kde else ''}{klic}")
    return chyby


def _resolve_paths(config: dict[str, Any]) -> dict[str, Any]:
    """Rozvine cesty proti oběma základnám; vstup nemění."""
    vysledek = copy.deepcopy(config)
    koren = Path(vysledek["module"]["data_root"])

    for cesta_klicu, zaklad in (
            [(k, MODULE_DIR) for k in MODULE_PATH_KEYS]
            + [(k, koren) for k in DATA_PATH_KEYS]):
        uzel: Any = vysledek
        for klic in cesta_klicu[:-1]:
            uzel = uzel.get(klic) if isinstance(uzel, dict) else None
            if uzel is None:
                break
        else:
            posledni = cesta_klicu[-1]
            if isinstance(uzel, dict) and isinstance(uzel.get(posledni), str):
                p = Path(uzel[posledni])
                uzel[posledni] = str(p if p.is_absolute() else zaklad / p)
    return vysledek


def _fingerprint(config: dict[str, Any]) -> str:
    """Krátký otisk obsahu konfigurace.

    Každé naměřené číslo nese otisk nastavení, se kterým vzniklo; jinak se
    dvě měření nedají porovnat a nikdo nepozná, že běžela jinak.
    """
    kanonicky = json.dumps(config, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(kanonicky.encode("utf-8")).hexdigest()[:12]
