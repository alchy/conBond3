"""Načtení konfigurace, ověření proti schématu, rozvinutí cest, otisk.

Proč se validuje při startu a ne při prvním použití: služba, která
nastartovala se špatnou konfigurací, je horší než služba, která
nenastartovala. Chyba v nastavení se pak projeví až za hodinu uprostřed
dávky, na místě, které s příčinou nesouvisí.

Proč vlastní validátor místo knihovny `jsonschema`: kód modulů nesmí mít
závislosti (README-MODULES.md § 19) a konfigurace se čte dřív, než cokoli
jiného naběhne. Validátor zvládá jen tu část JSON Schema, kterou naše
schémata používají, a na cokoli jiného **hlasitě upozorní** — nedostatečný
validátor, který mlčí, je horší než žádný.

Implementace je PŘEVZATÁ z `cb_logger/config.py`, kde se osvědčila, ne
napsaná znovu. Znění hlášek se drží doslova: sourozenci na ně mají testy
a přeformulovat je při stěhování by znamenalo měnit dvě věci najednou.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


class ConfigError(Exception):
    """Konfigurace je neplatná nebo se nedá načíst.

    Vlastní typ, aby ovládací program poznal tuhle chybu od ostatních
    a vrátil návratový kód 2 (špatné argumenty nebo neplatná konfigurace,
    README-MODULES.md § 12) místo obecné jedničky.
    """


def load(config_path, schema_path, *, supported_version: int,
         checks: Iterable[Callable[[dict], Sequence[str]]] = (),
         path_specs: Iterable[tuple[Sequence[str], Path]] = (),
         post_resolve: Callable[[dict], dict] | None = None) -> dict:
    """Načte konfiguraci, ověří ji a doplní odvozené hodnoty.

    Vstup:
        config_path: cesta ke konfiguraci. Předává se explicitně, aby test
            mohl ukázat jinam než provoz — jinak by testy měřily proti
            provozním datům.
        schema_path: schéma, proti kterému se ověřuje.
        supported_version: verze, které volající rozumí. Jiná v souboru je
            chyba, ne varování: starý tvar načtený podle nového předpokladu
            vyrobí čísla, která vypadají správně (§ 14).
        checks: kontroly nad rámec schématu (rozsah portů, vzájemné vazby
            klíčů). Každá dostane surovou konfiguraci a vrátí seznam
            českých hlášek; prázdný seznam znamená v pořádku.
        path_specs: dvojice (klíče, základna) pro rozvinutí relativních
            cest. Základen smí být víc — cb-bond má běhové cesty v modulu
            a datové mimo repozitář.
        post_resolve: modulově vlastní dorovnání cest, které se seznamem
            klíčů vyjádřit nedá. cb-logger má cesty UVNITŘ pravidel
            směrování, tedy v poli proměnné délky; vyjmenovat je předem
            nejde a hádat podle jména by se rozešlo s obsahem.

    Výstup:
        Slovník s konfigurací; cesty absolutní a `_meta` s cestou i otiskem.
        Bez otisku se dvě měření nedají porovnat a nikdo nepozná, že běžela
        jinak.

    Při chybě:
        `ConfigError` s českou hláškou, která říká, co konkrétně je špatně
        a kde. Nikdy nevrací částečně načtenou konfiguraci — polovina
        nastavení je horší než žádné, protože vypadá funkčně.
    """
    cesta = Path(config_path).resolve()
    surova = read_json(cesta, co="konfigurace")
    schema = read_json(Path(schema_path), co="schéma konfigurace")

    check_schema_supported(schema, schema_path)

    chyby = _validate(surova, schema, kde="")
    for kontrola in checks:
        chyby.extend(kontrola(surova))
    if chyby:
        raise ConfigError(f"neplatná konfigurace {cesta}:\n"
                          + "\n".join(f"  {ch}" for ch in chyby))

    verze = surova.get("config_version")
    if verze != supported_version:
        raise ConfigError(
            f"neplatná konfigurace {cesta}:\n"
            f"  config_version je {verze!r}, tenhle kód rozumí "
            f"{supported_version}\n"
            f"  Konfigurace se musí převést, ne načíst — starý tvar podle "
            f"nového předpokladu vyrobí čísla, která vypadají správně.")

    hotova = resolve_paths(surova, path_specs)
    if post_resolve is not None:
        hotova = post_resolve(hotova)
    # Otisk patří do `_meta` vedle cesty: obojí je odvozené, ne nastavené.
    hotova["_meta"] = {"path": str(cesta), "fingerprint": fingerprint(surova)}
    return hotova


def validate(config: Any, schema: dict, *, where: str = "") -> list[str]:
    """Ověří hodnotu proti schématu; vrátí seznam českých hlášek.

    Vrací seznam místo výjimky, aby šlo ohlásit **všechny** chyby najednou.
    Opravovat konfiguraci po jedné hlášce na spuštění je trest, ne pomoc.
    """
    if not where:
        check_schema_supported(schema)
    return _validate(config, schema, kde=where)


def resolve_paths(config: dict,
                  path_specs: Iterable[tuple[Sequence[str], Path]]) -> dict:
    """Rozvine relativní cesty proti zadaným základnám; vstup nemění.

    Proč se základna předává a neuhodne: cb-bond má dvě — běhové cesty
    patří k modulu (PID není datum, je to stav procesu), datové leží mimo
    repozitář. Uhodnout to podle jména klíče by se rozešlo s obsahem.

    Absolutní cesta v konfiguraci se nechá být: kdo ji tam napsal, ví, co
    dělá, a obvykle míří na jiný disk.
    """
    vysledek = copy.deepcopy(config)
    for klice, zaklad in path_specs:
        uzel: Any = vysledek
        for klic in klice[:-1]:
            uzel = uzel.get(klic) if isinstance(uzel, dict) else None
            if uzel is None:
                break
        else:
            posledni = klice[-1]
            if isinstance(uzel, dict) and isinstance(uzel.get(posledni), str):
                p = Path(uzel[posledni])
                uzel[posledni] = str(p if p.is_absolute()
                                     else Path(zaklad) / p)
    return vysledek


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


def read_json(cesta: Path, *, co: str) -> dict[str, Any]:
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


def check_schema_supported(schema: dict[str, Any],
                           schema_path=None) -> None:
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
            f"schéma {schema_path or 'konfigurace'} používá klíčová "
            f"slova, kterým validátor "
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


def fingerprint(config: dict[str, Any]) -> str:
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
