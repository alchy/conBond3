"""Načtení a ověření konfigurace modulu cb-logger.

Proč se validuje při startu a ne při prvním použití: služba, která nastartovala
se špatnou konfigurací, je horší než služba, která nenastartovala. Chyba
v nastavení se pak projeví až za hodinu uprostřed dávky, a to na místě, které
s příčinou nesouvisí.

Proč vlastní validátor místo knihovny `jsonschema`: kód modulů nesmí mít
závislosti (README-MODULES.md § 19). Validátor zvládá jen tu část JSON Schema, kterou
naše schémata používají, a na cokoli jiného **hlasitě upozorní** — nikdy tiše
neprojde. Nedostatečný validátor, který mlčí, je horší než žádný.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: Adresář modulu. Relativní cesty z konfigurace se počítají vůči němu, ne vůči
#: pracovnímu adresáři procesu — jinak by se chování měnilo podle toho, odkud
#: se služba spustí, a to je chyba, kterou nikdo nehledá na správném místě.
MODULE_DIR = Path(__file__).resolve().parent

#: Výchozí umístění konfigurace. Přebíjí se přepínačem --config.
DEFAULT_CONFIG_PATH = MODULE_DIR / "cb-logger-config.json"

#: Schéma, proti kterému se konfigurace ověřuje.
SCHEMA_PATH = MODULE_DIR / "config.schema.json"

#: Verze schématu, které tenhle kód rozumí. Když konfigurace nese jinou,
#: start selže — tiché načtení podle špatného předpokladu vyrobí čísla, která
#: vypadají správně.
SUPPORTED_CONFIG_VERSION = 1

#: Klíče schématu, kterým validátor rozumí. Cokoli jiného ve schématu je chyba
#: schématu, ne konfigurace, a ohlásí se zvlášť (viz docstring modulu).
SUPPORTED_SCHEMA_KEYWORDS = frozenset({
    "$schema", "title", "description", "type", "properties", "required",
    "additionalProperties", "items", "enum", "minimum", "maximum",
    "exclusiveMinimum", "minProperties",
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

    Vlastní typ, aby ovládací program poznal tuhle chybu od ostatních a vrátil
    návratový kód 2 (špatné argumenty nebo neplatná konfigurace, README-MODULES.md
    § 12) místo obecné jedničky.
    """


def load(path: str | Path | None = None) -> dict[str, Any]:
    """Načte konfiguraci, ověří ji proti schématu a doplní odvozené hodnoty.

    Proč vrací obyčejný slovník a ne objekt `Config`: hodnoty se předávají
    funkcím po jedné (README-MODULES.md § 3). Objekt, ze kterého si funkce sama tahá,
    co potřebuje, schová závislost před čtenářem signatury.

    Vstup:
        path: cesta ke konfiguraci. `None` znamená výchozí umístění vedle
            modulu. Cesta se předává explicitně, aby test mohl ukázat jinam
            než provoz — bez toho by testy měřily proti provozním datům.

    Výstup:
        Slovník s konfigurací, doplněný o klíč `_meta` s absolutní cestou,
        ze které se načetla, a s otiskem obsahu. Cesta se vypisuje při startu
        a zapisuje do logu; jinak nikdo nezjistí, které nastavení vlastně běží.
        Relativní cesty v `runtime` a `module` jsou převedené na absolutní.

    Při chybě:
        `ConfigError` s českou hláškou, která říká, co konkrétně je špatně
        a kde. Nikdy nevrací částečně načtenou konfiguraci.
    """
    cesta = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    cesta = cesta.resolve()

    surova = _read_json(cesta, co="konfigurace")
    schema = _read_json(SCHEMA_PATH, co="schéma konfigurace")

    _check_schema_supported(schema)

    chyby = _validate(surova, schema, kde="")
    if chyby:
        raise ConfigError(
            f"neplatná konfigurace {cesta}:\n"
            + "\n".join(f"  {ch}" for ch in chyby)
        )

    verze = surova["config_version"]
    if verze != SUPPORTED_CONFIG_VERSION:
        raise ConfigError(
            f"neplatná konfigurace {cesta}:\n"
            f"  config_version je {verze}, tenhle kód rozumí "
            f"{SUPPORTED_CONFIG_VERSION}\n"
            f"  Konfigurace se musí převést, ne načíst — starý tvar podle "
            f"nového předpokladu vyrobí čísla, která vypadají správně."
        )

    hotova = _resolve_paths(surova)
    hotova["_meta"] = {
        "path": str(cesta),
        "fingerprint": _fingerprint(surova),
        "module_dir": str(MODULE_DIR),
    }
    return hotova


def _read_json(cesta: Path, *, co: str) -> dict[str, Any]:
    """Přečte JSON soubor a převede chyby na `ConfigError` s čitelnou hláškou.

    Proč zvlášť: `FileNotFoundError` ani `JSONDecodeError` neřeknou, o který
    ze dvou souborů šlo, a při startu je to první věc, kterou člověk potřebuje
    vědět.

    Vstup:
        cesta: absolutní cesta k souboru.
        co: jak se souboru říká v hlášce, česky (např. "konfigurace").

    Výstup:
        Načtený JSON objekt.

    Při chybě:
        `ConfigError`, když soubor chybí, nejde přečíst, není platný JSON
        nebo není objekt.
    """
    try:
        obsah = cesta.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"chybí {co}: {cesta}") from None
    except OSError as e:
        raise ConfigError(f"nejde přečíst {co} {cesta}: {e}") from None

    try:
        data = json.loads(obsah)
    except json.JSONDecodeError as e:
        raise ConfigError(
            f"{co} {cesta} není platný JSON:\n"
            f"  řádek {e.lineno}, sloupec {e.colno}: {e.msg}"
        ) from None

    if not isinstance(data, dict):
        raise ConfigError(
            f"{co} {cesta} musí být JSON objekt, ne {type(data).__name__}"
        )
    return data


def _check_schema_supported(schema: dict[str, Any]) -> None:
    """Ověří, že schéma nepoužívá nic, čemu validátor nerozumí.

    Proč to stojí za vlastní průchod: validátor umí jen podmnožinu JSON Schema.
    Kdyby na neznámé klíčové slovo mlčel, tvářilo by se schéma jako vynucené,
    ale ta část by nekontrolovala nic. Test, který zticha přestane hlídat, je
    horší než žádný test.

    Vstup:
        schema: načtené schéma.

    Výstup:
        Nic.

    Při chybě:
        `ConfigError` se seznamem klíčových slov, kterým validátor nerozumí,
        a s místem, kde ve schématu jsou.
    """
    nalezene: list[str] = []

    def projdi(uzel: Any, kde: str) -> None:
        if not isinstance(uzel, dict):
            return
        for klic, hodnota in uzel.items():
            if klic == "properties" and isinstance(hodnota, dict):
                for jmeno, podschema in hodnota.items():
                    projdi(podschema, f"{kde}.{jmeno}" if kde else jmeno)
            elif klic == "items":
                projdi(hodnota, f"{kde}[]")
            elif klic not in SUPPORTED_SCHEMA_KEYWORDS:
                nalezene.append(f"{kde or '<kořen>'}: {klic}")

    projdi(schema, "")
    if nalezene:
        raise ConfigError(
            f"schéma {SCHEMA_PATH} používá klíčová slova, kterým validátor "
            f"nerozumí:\n" + "\n".join(f"  {n}" for n in nalezene) + "\n"
            "  Buď se doplní do _validate, nebo se ze schématu odstraní. "
            "Mlčky ignorovat je nesmí."
        )


def _validate(hodnota: Any, schema: dict[str, Any], *, kde: str) -> list[str]:
    """Ověří hodnotu proti schématu; vrátí seznam českých popisů chyb.

    Proč seznam a ne první nález: když je konfigurace špatně, je obvykle špatně
    víc věcí. Nahlásit jen první znamená, že se to opravuje na třikrát a mezi
    tím se pokaždé restartuje.

    Vstup:
        hodnota: kus konfigurace k ověření.
        schema: odpovídající kus schématu.
        kde: tečková cesta k hodnotě pro hlášku (např. `service.port`).
            Prázdný řetězec znamená kořen.

    Výstup:
        Seznam vět. Prázdný seznam znamená, že je hodnota v pořádku.

    Při chybě:
        Nevyhazuje — chyby vrací, ne hází. Vyhodit by znamenalo ohlásit jen
        první z nich.
    """
    chyby: list[str] = []
    misto = kde or "<kořen>"

    ocekavany = schema.get("type")
    if ocekavany:
        povolene = _JSON_TYPES[ocekavany]
        # `bool` je v Pythonu podtyp `int`, takže by True prošlo jako číslo.
        je_bool_navic = isinstance(hodnota, bool) and ocekavany in (
            "integer", "number"
        )
        if not isinstance(hodnota, povolene) or je_bool_navic:
            chyby.append(
                f"{misto}: očekáván {ocekavany}, nalezeno "
                f"{type(hodnota).__name__}"
            )
            # Bez správného typu nemá smysl kontrolovat zbytek.
            return chyby

    if "enum" in schema and hodnota not in schema["enum"]:
        povolene = " | ".join(str(p) for p in schema["enum"])
        chyby.append(f"{misto}: hodnota {hodnota!r} není z výčtu {povolene}")

    if isinstance(hodnota, (int, float)) and not isinstance(hodnota, bool):
        if "minimum" in schema and hodnota < schema["minimum"]:
            chyby.append(f"{misto}: {hodnota} je pod minimem {schema['minimum']}")
        if "maximum" in schema and hodnota > schema["maximum"]:
            chyby.append(f"{misto}: {hodnota} je nad maximem {schema['maximum']}")
        if "exclusiveMinimum" in schema and hodnota <= schema["exclusiveMinimum"]:
            chyby.append(
                f"{misto}: {hodnota} musí být větší než "
                f"{schema['exclusiveMinimum']}"
            )

    if isinstance(hodnota, dict):
        chyby += _validate_object(hodnota, schema, kde=kde, misto=misto)

    if isinstance(hodnota, list) and "items" in schema:
        for i, polozka in enumerate(hodnota):
            chyby += _validate(schema=schema["items"], hodnota=polozka,
                               kde=f"{kde}[{i}]")

    return chyby


def _validate_object(
    hodnota: dict[str, Any], schema: dict[str, Any], *, kde: str, misto: str
) -> list[str]:
    """Ověří objektová pravidla: povinné klíče, neznámé klíče, podřazené hodnoty.

    Vyděleno z `_validate`, aby se ta funkce dala přečíst najednou.

    Vstup:
        hodnota: ověřovaný objekt.
        schema: jeho schéma.
        kde: tečková cesta pro sestavení cest podřazených hodnot.
        misto: tečková cesta pro hlášku (kořen se píše jako `<kořen>`).

    Výstup:
        Seznam českých popisů chyb.

    Při chybě:
        Nevyhazuje.
    """
    chyby: list[str] = []
    vlastnosti: dict[str, Any] = schema.get("properties", {})

    for povinny in schema.get("required", []):
        if povinny not in hodnota:
            chyby.append(f"{misto}: chybí povinný klíč '{povinny}'")

    if schema.get("additionalProperties") is False:
        neznamé = set(hodnota) - set(vlastnosti)
        for klic in sorted(neznamé):
            # Neznámý klíč je chyba, ne tiché ignorování: obvykle je to překlep
            # a tiše ignorovaný překlep znamená, že běží jiné nastavení,
            # než si člověk myslí.
            chyby.append(f"{misto}: neznámý klíč '{klic}'")

    if "minProperties" in schema and len(hodnota) < schema["minProperties"]:
        chyby.append(
            f"{misto}: očekáváno aspoň {schema['minProperties']} klíčů, "
            f"nalezeno {len(hodnota)}"
        )

    for klic, podschema in vlastnosti.items():
        if klic in hodnota:
            chyby += _validate(
                hodnota[klic], podschema, kde=f"{kde}.{klic}" if kde else klic
            )

    return chyby


#: Které klíče nesou cesty. Vyjmenované schválně: automatické hádání podle
#: jména ("končí na _path, tak je to cesta") by se rozešlo s obsahem, jakmile
#: přibude klíč, který se tak jmenuje a cesta není.
PATH_KEYS = (
    ("runtime", "pid_file"),
    ("runtime", "port_file"),
    ("runtime", "self_log", "path"),
    ("module", "storage", "dir"),
    ("module", "storage", "objects_dir"),
    ("module", "routing", "default"),
    ("module", "summary", "path"),
    ("module", "objects", "stream"),
)


def _resolve_paths(config: dict[str, Any]) -> dict[str, Any]:
    """Převede relativní cesty na absolutní vůči adresáři modulu.

    Proč vůči modulu a ne vůči pracovnímu adresáři: jinak by se chování měnilo
    podle toho, odkud se služba spustí. Spuštění z jiného adresáře by tiše
    založilo druhou sadu dat a nikdo by nehledal chybu tam.

    Absolutní cesta v konfiguraci se nechá být — kdo ji tam napsal, ví, co
    dělá, a obvykle míří na jiný disk.

    Vstup:
        config: ověřená konfigurace.

    Výstup:
        Nová konfigurace s absolutními cestami. Vstup se nemění — funkce, která
        vrátí hodnotu a zároveň změní, co dostala, se používá špatně.

    Při chybě:
        Nevyhazuje. Cesty jsou už ověřené jako řetězce.
    """
    import copy

    vysledek = copy.deepcopy(config)

    for cesta_klicu in PATH_KEYS:
        uzel: Any = vysledek
        for klic in cesta_klicu[:-1]:
            uzel = uzel.get(klic) if isinstance(uzel, dict) else None
            if uzel is None:
                break
        else:
            posledni = cesta_klicu[-1]
            if isinstance(uzel, dict) and isinstance(uzel.get(posledni), str):
                uzel[posledni] = str(_absolute(uzel[posledni]))

    for pravidlo in vysledek.get("module", {}).get("routing", {}).get("rules", []):
        if isinstance(pravidlo, dict) and isinstance(pravidlo.get("to"), str):
            pravidlo["to"] = str(_absolute(pravidlo["to"]))

    return vysledek


def _absolute(cesta: str) -> Path:
    """Vrátí absolutní podobu cesty; relativní počítá vůči adresáři modulu.

    Vstup:
        cesta: cesta z konfigurace, absolutní nebo relativní.

    Výstup:
        Absolutní `Path`. Cesta se nenormalizuje přes `resolve()`, protože
        cílový soubor ještě nemusí existovat.

    Při chybě:
        Nevyhazuje.
    """
    p = Path(cesta)
    return p if p.is_absolute() else MODULE_DIR / p


def _fingerprint(config: dict[str, Any]) -> str:
    """Vrátí krátký otisk obsahu konfigurace.

    Proč je potřeba: každé naměřené číslo nese verzi konfigurace, jinak jsou
    dvě čísla nesrovnatelná (README-MODULES.md § 11). Verze v souboru se mění zřídka,
    kdežto hodnoty často — otisk pozná i změnu, u které nikdo číslo nezvýšil.

    Vstup:
        config: konfigurace před doplněním `_meta`, aby otisk nezávisel sám
            na sobě.

    Výstup:
        Prvních dvanáct znaků SHA-256 z kanonického JSON zápisu. Dvanáct
        hexadecimálních znaků je dost na rozlišení a krátké na přečtení v logu.

    Při chybě:
        Nevyhazuje.
    """
    import hashlib

    kanonicky = json.dumps(config, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(kanonicky.encode("utf-8")).hexdigest()[:12]
