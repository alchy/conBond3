"""Datové typy jednoho záznamu logu a jejich převod z drátu.

Proč je záznam vlastní typ a ne slovník: stav záznamu rozhoduje o tom, jestli
se něco povedlo, nevrátilo nic, nebo selhalo — a to je rozlišení, na kterém
stojí celé měření systému (README-MODULES.md § 6). Slovník s domluvenými klíči je typ,
o kterém neví editor ani test, a první překlep v hodnotě stavu by tiše rozpadl
výčet, který má chránit rozdíl mezi „nemá hodnotu" a „nepodařilo se".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# Verze tvaru záznamu. Roste, když se změní pole tak, že starší čtečka
# záznam přečte špatně; přidání nepovinného pole verzi nezvyšuje.
#
# 2 — pole `result` přejmenováno na `result`, aby se popisky v kódu, v JSON
#     i v kukátku jmenovaly stejně. Záznamy s `result` jsou z verze 1.
RECORD_FORMAT_VERSION = 2


class Level(str, Enum):
    """Úroveň záznamu.

    Proč jen dvě: víc úrovní znamená, že se u každého zápisu rozhoduje, která
    z nich to je, a to rozhodnutí nikdo nedělá konzistentně. Dvě úrovně mají
    jasnou hranici — `INFO` je hranice komponenty (kdo se volal, s čím, s jakým
    výsledkem), `DEBUG` je vnitřek funkcí.

    Dědí ze `str` schválně: hodnota jde rovnou do JSON bez převodu a porovnání
    s řetězcem z drátu funguje bez přemýšlení.
    """

    INFO = "info"
    DEBUG = "debug"


class Result(str, Enum):
    """Jak volání dopadlo.

    Tohle je nejdůležitější výčet v celém systému. `EMPTY` a `ERROR` se nesmějí
    slít: věta, ze které nevznikl atom, protože v ní žádný nebyl, je `EMPTY`;
    věta, ze které nevznikl atom, protože spadl parser, je `ERROR`. Kdyby obojí
    bylo „nula atomů", měření by odměnilo právě tu chybu, kterou má chytat.

    `SKIPPED` je tam kvůli požadavku na stopu: přeskočená položka musí být
    v logu vidět jako přeskočená s důvodem, ne jako tichá díra.
    """

    OK = "ok"
    EMPTY = "empty"
    SKIPPED = "skipped"
    ERROR = "error"


#: Pole, která musí přijít z drátu. Odpovídají čtyřem povinným položkám
#: ze zadání: komponenta, metoda, vstup-výstup, stav. `input` a `output` jsou
#: povinné jako klíče, ne jako neprázdné hodnoty — prázdný vstup je platný.
REQUIRED_FIELDS = ("component", "method", "result")

#: Pole, která záznam nese navíc a bez kterých by log nešlo použít:
#: `trace` skládá jeden průchod, `version` umožňuje porovnat dva běhy.
OPTIONAL_FIELDS = (
    "message",
    "trace",
    "input",
    "output",
    "duration_ms",
    "version",
    "level",
    "ts",
)


@dataclass(frozen=True)
class LogRecord:
    """Jeden záznam logu, už ověřený a připravený k zápisu.

    Proč `frozen`: záznam je fakt o tom, co se stalo. Kdyby šel po vytvoření
    změnit, mohl by ho směrovač nebo zapisovač cestou upravit a v souboru by
    skončilo něco jiného, než co komponenta ohlásila.

    Proč nese `malformed` místo toho, aby špatný záznam nevznikl: záznam se
    posílá právě tehdy, když se něco děje. Odmítnout ho znamená přijít o stopu
    v okamžiku, kdy je nejcennější — a volající se to stejně nedozví, protože
    zápis je asynchronní. Špatně tvarovaný záznam v logu je informace;
    chybějící záznam není nic (README-MODULES.md § 6).
    """

    ts: str
    level: Level
    component: str
    method: str
    result: Result
    message: str | None = None
    trace: str | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    duration_ms: int | None = None
    version: dict[str, Any] | None = None
    malformed: bool = False
    malformed_reason: str | None = None
    raw: dict[str, Any] | None = None

    def to_json_object(self) -> dict[str, Any]:
        """Převede záznam na JSON objekt určený k zápisu.

        Proč se nepoužije `dataclasses.asdict`: ten by zapsal i pole s hodnotou
        `None`, takže by každý řádek logu nesl sedm prázdných klíčů. Log se čte
        očima a prázdné klíče v něm jsou šum, který zakrývá to podstatné.

        Vstup:
            Žádný — pracuje nad vlastními poli.

        Výstup:
            Slovník s klíči v pevném pořadí: nejdřív kdy a kdo, pak co a jak
            to dopadlo, nakonec doplňky. Pořadí je pevné schválně — dva řádky
            logu vedle sebe pak jde porovnat okem, ne nástrojem.
            Pole s hodnotou `None` se vynechávají, s výjimkou `trace`.

        Při chybě:
            Nevyhazuje. Všechna pole už jsou ověřená z `from_wire`.
        """
        objekt: dict[str, Any] = {
            "ts": self.ts,
            "level": self.level.value,
            "component": self.component,
            "method": self.method,
            # `trace` se zapisuje i jako None schválně: chybějící stopa je
            # měřitelná díra v řetězu a musí být v záznamu vidět, ne tichá.
            "trace": self.trace,
            "result": self.result.value,
        }
        # Hláška hned za stavem: je to to, co člověk čte jako první, když
        # v kukátku hledá, co se stalo.
        if self.message is not None:
            objekt["message"] = self.message
        for jmeno in ("input", "output", "duration_ms", "version"):
            hodnota = getattr(self, jmeno)
            if hodnota is not None:
                objekt[jmeno] = hodnota
        if self.malformed:
            objekt["malformed"] = True
            objekt["malformed_reason"] = self.malformed_reason
            objekt["raw"] = self.raw
        return objekt


def from_wire(raw: Any, *, received_ts: str) -> LogRecord:
    """Udělá ze záznamu přijatého po drátě ověřený `LogRecord`.

    Proč nikdy nevyhazuje výjimku: tahle funkce stojí na vstupu logovátka a
    dostává data od cizích modulů. Kdyby na špatném tvaru spadla, ztratil by se
    záznam z komponenty, která má zjevně problém — tedy ten nejcennější. Místo
    toho vrátí záznam označený `malformed=True` s důvodem a s původním obsahem
    pod `raw`, aby šlo dohledat, co vlastně přišlo (README-MODULES.md § 6).

    Aby to nebylo tiché svolení k rozpadu výčtu výsledků, počítá se `malformed`
    zvlášť v souhrnu a směrovač na něj smí mít pravidlo.

    Vstup:
        raw: cokoli, co přišlo po drátě. Očekává se JSON objekt, ale funkce
            počítá i s tím, že to objekt není.
        received_ts: čas přijetí v ISO 8601 (UTC). Předává se zvenčí, protože
            funkce, která si sáhne na hodiny sama, nejde deterministicky
            otestovat (README-MODULES.md § 3).

    Výstup:
        `LogRecord`. Když byl vstup v pořádku, `malformed` je `False`.
        Když nebyl, záznam přesto vznikne — s náhradními hodnotami
        (`component="?"`, `result=ERROR`) a s `malformed_reason`, které říká,
        co konkrétně bylo špatně.

    Při chybě:
        Nevyhazuje nikdy. To je celý smysl téhle funkce.
    """
    if not isinstance(raw, dict):
        return _malformed(
            duvod=f"záznam není JSON objekt, ale {type(raw).__name__}",
            raw={"value": repr(raw)},
            received_ts=received_ts,
        )

    duvody = _find_problems(raw)
    if duvody:
        return _malformed(
            duvod="; ".join(duvody), raw=raw, received_ts=received_ts
        )

    return LogRecord(
        # Razítko z drátu má přednost: komponenta ví, kdy se událost stala,
        # kdežto logovátko ví jen, kdy záznam dorazil — a mezi tím leží fronta
        # a dávkování, tedy klidně půl sekundy.
        ts=raw.get("ts") or received_ts,
        level=Level(raw.get("level", Level.INFO.value)),
        component=raw["component"],
        method=raw["method"],
        result=Result(raw["result"]),
        message=raw.get("message"),
        trace=raw.get("trace"),
        input=raw.get("input"),
        output=raw.get("output"),
        duration_ms=raw.get("duration_ms"),
        version=raw.get("version"),
    )


def _find_problems(raw: dict[str, Any]) -> list[str]:
    """Vrátí seznam důvodů, proč je záznam špatně; prázdný seznam znamená v pořádku.

    Proč seznam a ne první nález: když komponenta posílá záznam ve špatném
    tvaru, obvykle je špatně víc věcí najednou. Nahlásit jen první z nich
    znamená, že se chyba opravuje na třikrát.

    Vstup:
        raw: záznam z drátu, o kterém už víme, že je to slovník.

    Výstup:
        Seznam českých vět popisujících, co je špatně. Prázdný, když je vše
        v pořádku.

    Při chybě:
        Nevyhazuje.
    """
    duvody: list[str] = []

    for pole in REQUIRED_FIELDS:
        if pole not in raw:
            duvody.append(f"chybí povinné pole '{pole}'")
        elif not isinstance(raw[pole], str):
            duvody.append(
                f"pole '{pole}' není řetězec, ale {type(raw[pole]).__name__}"
            )

    if isinstance(raw.get("result"), str):
        try:
            Result(raw["result"])
        except ValueError:
            povolene = "|".join(r.value for r in Result)
            duvody.append(f"result '{raw['result']}' není z výčtu {povolene}")

    if "level" in raw:
        try:
            Level(raw["level"])
        except (ValueError, KeyError):
            povolene = "|".join(u.value for u in Level)
            duvody.append(f"level '{raw['level']}' není z výčtu {povolene}")

    if raw.get("message") is not None and not isinstance(raw["message"], str):
        duvody.append(
            f"pole 'message' není řetězec, ale {type(raw['message']).__name__}"
        )

    for pole in ("input", "output", "version"):
        if raw.get(pole) is not None and not isinstance(raw[pole], dict):
            duvody.append(
                f"pole '{pole}' není JSON objekt, ale {type(raw[pole]).__name__}"
            )

    trvani = raw.get("duration_ms")
    if trvani is not None and (not isinstance(trvani, int) or isinstance(trvani, bool)):
        duvody.append(
            f"pole 'duration_ms' není celé číslo, ale {type(trvani).__name__}"
        )

    neznama = set(raw) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
    if neznama:
        duvody.append("neznámá pole: " + ", ".join(sorted(neznama)))

    return duvody


def _malformed(*, duvod: str, raw: dict[str, Any], received_ts: str) -> LogRecord:
    """Sestaví záznam pro vstup, který neprošel ověřením.

    Proč `component="?"` a ne třeba prázdný řetězec: v souhrnu a ve výpisu je
    otazník vidět jako chybějící údaj, kdežto prázdný řetězec vypadá jako
    komponenta bez jména a splyne s okolím.

    Vstup:
        duvod: co konkrétně bylo špatně, česky a v jedné větě.
        raw: původní obsah beze změny, aby šlo dohledat, co přišlo.
        received_ts: čas přijetí; u špatného záznamu je to jediné razítko,
            kterému se dá věřit.

    Výstup:
        `LogRecord` s `malformed=True`. Stav je `ERROR`, protože špatně
        tvarovaný záznam je chyba ve volajícím — ne prázdný výsledek.

    Při chybě:
        Nevyhazuje.
    """
    return LogRecord(
        ts=received_ts,
        level=Level.INFO,
        component=str(raw.get("component") or "?"),
        method=str(raw.get("method") or "?"),
        result=Result.ERROR,
        trace=raw.get("trace") if isinstance(raw.get("trace"), str) else None,
        malformed=True,
        malformed_reason=duvod,
        raw=raw,
    )
