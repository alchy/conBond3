"""Načtení konfigurace, ověření proti schématu, rozvinutí cest, otisk.

Proč se validuje při startu a ne při prvním použití: služba, která
nastartovala se špatnou konfigurací, je horší než služba, která
nenastartovala. Chyba v nastavení se pak projeví až za hodinu uprostřed
dávky, na místě, které s příčinou nesouvisí.

Validaci dělá knihovna `jsonschema` — **schválená závislost** (§ 19,
rozhodnutí J. 2026-08-05). Předtím tu stál ručně psaný validátor, protože
moduly neměly mít závislosti; uměl ale jen část Draft 7 a každé nové
klíčové slovo ve schématu se muselo doplnit do kódu, jinak by prošlo
mlčky. Knihovna rozumí celému standardu a ten problém mizí.

Co zůstalo vlastní: **překlad hlášek do češtiny** v domácím tvaru
(politika § 17 chce chybové hlášky pro člověka česky) a stabilní pořadí
řádků. Znění se drží doslova toho z `cb_logger`, protože na něm stojí
testy sourozenců.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import jsonschema


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


#: Jak se anglická hláška z `jsonschema` píše česky. Klíčem je `validator`
#: (klíčové slovo schématu, které selhalo), hodnotou funkce, která z chyby
#: udělá domácí větu.
#:
#: Proč se překládá a nepředává se hláška knihovny: politika § 17 chce
#: chybové hlášky pro člověka česky, a sourozenci na tenhle tvar mají
#: testy. Co v tabulce není, projde v původním znění — neúplný překlad je
#: pořád lepší než mlčení.
_HLASKY = {
    "type": lambda e: (
        f"očekáván {_typ(e.validator_value)}, "
        f"nalezeno {type(e.instance).__name__}"),
    "required": lambda e: f"chybí povinný klíč {_chybejici(e)!r}",
    "additionalProperties": lambda e: (
        f"neznámý klíč {_navic(e)!r}"),
    "enum": lambda e: (
        f"hodnota {e.instance!r} není z výčtu "
        + " | ".join(str(p) for p in e.validator_value)),
    "minimum": lambda e: f"{e.instance} je pod minimem {e.validator_value}",
    "maximum": lambda e: f"{e.instance} je nad maximem {e.validator_value}",
    "exclusiveMinimum": lambda e: (
        f"{e.instance} musí být větší než {e.validator_value}"),
    "minProperties": lambda e: (
        f"očekáváno aspoň {e.validator_value} klíčů, "
        f"nalezeno {len(e.instance)}"),
}


def check_schema_supported(schema: dict[str, Any], schema_path=None) -> None:
    """Ověří, že schéma samo je platné JSON Schema.

    Dřív tahle funkce hlídala, že schéma nepoužívá klíčové slovo, kterému
    náš ručně psaný validátor nerozumí. S knihovnou ten problém zmizel —
    rozumí celému Draft 7 — a zůstala potřeba opačná: poznat, že je
    rozbité SCHÉMA, ne konfigurace. To je jinak vada, která se projeví
    jako podivná hláška o konfiguraci, která je ve skutečnosti v pořádku.

    Při chybě:
        `ConfigError` s tím, co je ve schématu špatně.
    """
    try:
        jsonschema.Draft7Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        raise ConfigError(
            f"schéma {schema_path or 'konfigurace'} je neplatné:\n"
            f"  {'.'.join(str(k) for k in e.absolute_path) or '<kořen>'}: "
            f"{e.message}") from None


def _validate(hodnota: Any, schema: dict[str, Any], *,
              kde: str = "") -> list[str]:
    """Ověří hodnotu proti schématu; vrátí seznam českých popisů chyb.

    Validaci dělá knihovna `jsonschema` (schválená závislost, § 19) —
    ručně psaný validátor uměl jen část Draft 7 a každé nové klíčové
    slovo ve schématu se muselo doplnit do kódu. Tady zůstává jen
    překlad do češtiny a stabilní pořadí.

    Vrací seznam místo výjimky, aby šlo ohlásit **všechny** chyby
    najednou. Opravovat konfiguraci po jedné hlášce na spuštění je trest,
    ne pomoc.
    """
    validator = jsonschema.Draft7Validator(schema)
    chyby = []
    for e in validator.iter_errors(hodnota):
        # Index pole patří do hranatých závorek (rules[0]), ne za tečku:
        # tečkový zápis `rules.0` vypadá jako klíč, který se dá najít
        # v konfiguraci, a nejde.
        misto = kde
        for klic in e.absolute_path:
            if isinstance(klic, int):
                misto = f"{misto}[{klic}]"
            else:
                misto = f"{misto}.{klic}" if misto else str(klic)
        misto = misto or "<kořen>"
        preklad = _HLASKY.get(e.validator)
        chyby.append(f"{misto}: "
                     + (preklad(e) if preklad else e.message))
    # Stabilní pořadí: bez něj se dvě spuštění nad touž vadnou konfigurací
    # liší v pořadí řádků a diff hlášek nic neříká.
    return sorted(chyby)


def _typ(ocekavany: Any) -> str:
    """Očekávaný typ jako jedno slovo; `jsonschema` jich smí uvést víc."""
    if isinstance(ocekavany, list):
        return " | ".join(str(t) for t in ocekavany)
    return str(ocekavany)


def _chybejici(e) -> str:
    """Jméno chybějícího klíče z anglické hlášky knihovny."""
    return e.message.split("'")[1] if "'" in e.message else e.message


def _navic(e) -> str:
    """Jméno klíče navíc z anglické hlášky knihovny."""
    return e.message.split("'")[1] if "'" in e.message else e.message


def fingerprint(config: dict[str, Any]) -> str:
    """Krátký otisk obsahu konfigurace, nezávislý na pořadí klíčů.

    Každé naměřené číslo nese otisk nastavení, se kterým vzniklo; jinak se
    dvě měření nedají porovnat a nikdo nepozná, že běžela jinak.
    """
    kanonicky = json.dumps(config, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(kanonicky.encode("utf-8")).hexdigest()[:12]


def read_json(cesta: Path, *, co: str) -> dict[str, Any]:
    """Přečte JSON objekt; každá vada je `ConfigError` s adresou.

    Hlášky říkají řádek a sloupec, protože hledat čárku navíc v tisícovém
    souboru bez toho je zbytečná práce.
    """
    cesta = Path(cesta)
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
            f"{co} {cesta} není platný JSON:\n"
            f"  řádek {e.lineno}, sloupec {e.colno}: {e.msg}") from None
    if not isinstance(data, dict):
        raise ConfigError(
            f"{co} {cesta} musí být JSON objekt, ne {type(data).__name__}")
    return data
