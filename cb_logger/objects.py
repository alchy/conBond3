"""Druhý druh logu: celý JSON objekt místo řádku textu.

Proč vedle textového záznamu existuje ještě tohle. Textový záznam odpovídá na
otázku *co se stalo* — komponenta, metoda, stav, shrnutí vstupu a výstupu.
Existuje ale druhá otázka, *jak vypadala data*, a na tu se řádkem odpovědět
nedá: pole po sítku, koš atomů, matice šablon. Zploštit takovou strukturu do
řetězce znamená přijít přesně o to, kvůli čemu se na ni člověk dívá.

Objektový záznam se proto ukládá celý a v kukátku se vykresluje jako
rozbalitelný strom. Posouvá se stejně jako textový log — nejnovější dole —
jen řádkem není řádek, ale objekt.

Dvě omezení, obě zapsaná dopředu, protože bez nich by se to nedalo používat:

* **Strop na velikost.** Zalogovat celý korpus by udělalo záznam, který nikdo
  neotevře, a zaplnilo by disk.
* **Strop na hloubku.** Chrání kukátko před stromem, který se nedá rozbalit,
  a zápis před strukturou, která odkazuje sama na sebe.

Objekt přes strop se **uloží oříznutý a označený, ne zahozený** — platí totéž
co u špatně tvarovaného záznamu: chybějící záznam není nic, označený je
informace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

#: Verze tvaru objektového záznamu.
OBJECT_FORMAT_VERSION = 1

#: Čím se nahradí větev, která přerostla strop hloubky. Text je součástí
#: kontraktu — kukátko podle něj větev označí jako uříznutou.
DEPTH_MARKER = "… hlouběji než max_depth"

#: Povinná a nepovinná pole objektového záznamu.
REQUIRED_FIELDS = ("component", "method", "object")
OPTIONAL_FIELDS = ("trace", "label", "ts", "kind")


@dataclass(frozen=True)
class ObjectRecord:
    """Jeden zalogovaný JSON objekt, připravený k zápisu.

    `label` je jméno, pod kterým se objekt v kukátku ukáže — „pole po sítku",
    „koš věty 4". Bez něj by šlo poznat jen komponentu a metodu, a to u modulu,
    který loguje tři různé struktury, nestačí.

    `kind` je volitelné zařazení objektu (`field`, `basket`, `template`…).
    Slouží k filtrování v kukátku; když chybí, použije se `label`.
    """

    ts: str
    component: str
    method: str
    label: str
    object: Any
    trace: str | None = None
    kind: str | None = None
    bytes: int = 0
    truncated: bool = False
    depth_limited: bool = False
    malformed: bool = False
    malformed_reason: str | None = None
    raw: Any = None

    def to_json_object(self) -> dict[str, Any]:
        """Převede záznam na JSON objekt určený k zápisu.

        Výstup:
            Slovník s klíči v pevném pořadí. Příznaky `truncated`,
            `depth_limited` a `malformed` se zapisují jen když platí — prázdné
            klíče jsou v logu šum, který zakrývá to podstatné.
        """
        objekt: dict[str, Any] = {
            "ts": self.ts,
            "component": self.component,
            "method": self.method,
            "trace": self.trace,
            "label": self.label,
            "kind": self.kind or self.label,
            "bytes": self.bytes,
            "object": self.object,
        }
        for jmeno in ("truncated", "depth_limited", "malformed"):
            if getattr(self, jmeno):
                objekt[jmeno] = True
        if self.malformed:
            objekt["malformed_reason"] = self.malformed_reason
            objekt["raw"] = self.raw
        return objekt


def from_wire(raw: Any, *, received_ts: str, max_object_bytes: int,
              max_depth: int) -> ObjectRecord:
    """Udělá z objektového záznamu přijatého po drátě ověřený `ObjectRecord`.

    Proč nikdy nevyhazuje výjimku: stejný důvod jako u textového záznamu.
    Objekt se loguje právě tehdy, když se člověk potřebuje podívat na data —
    odmítnout ho znamená přijít o pohled v okamžiku, kdy je nejcennější.

    Vstup:
        raw: cokoli, co přišlo po drátě. Očekává se JSON objekt s klíči
            `component`, `method` a `object`.
        received_ts: čas přijetí v ISO 8601. Předává se zvenčí, aby šla funkce
            deterministicky otestovat.
        max_object_bytes: strop na serializovanou velikost objektu.
        max_depth: nejhlubší ukládaná úroveň zanoření.

    Výstup:
        `ObjectRecord`. Když byl vstup v pořádku, `malformed` je `False`.
        Příznaky `truncated` a `depth_limited` říkají, že se objekt uložil
        celý, ale zkrácený — to **není** chyba, je to mez, o které se ví.

    Při chybě:
        Nevyhazuje nikdy.
    """
    if not isinstance(raw, dict):
        return _malformed(
            duvod=f"záznam není JSON objekt, ale {type(raw).__name__}",
            raw={"value": repr(raw)}, received_ts=received_ts,
        )

    duvody = _find_problems(raw)
    if duvody:
        return _malformed(
            duvod="; ".join(duvody), raw=raw, received_ts=received_ts
        )

    oriznuty, omezena_hloubka = _clamp_depth(raw["object"], max_depth)
    velikost = _size_of(oriznuty)
    zkraceny = False

    if velikost > max_object_bytes:
        oriznuty = {
            "_truncated": True,
            "_original_bytes": velikost,
            "_limit_bytes": max_object_bytes,
            "_preview": _preview(oriznuty, max_object_bytes),
        }
        zkraceny = True

    return ObjectRecord(
        ts=raw.get("ts") or received_ts,
        component=raw["component"],
        method=raw["method"],
        label=str(raw.get("label") or raw["method"]),
        object=oriznuty,
        trace=raw.get("trace"),
        kind=raw.get("kind"),
        bytes=velikost,
        truncated=zkraceny,
        depth_limited=omezena_hloubka,
    )


def _find_problems(raw: dict[str, Any]) -> list[str]:
    """Vrátí seznam důvodů, proč je objektový záznam špatně.

    Vrací všechny najednou: když komponenta posílá záznam ve špatném tvaru,
    je obvykle špatně víc věcí a opravovat to na třikrát nikoho nebaví.
    """
    duvody: list[str] = []

    for pole in ("component", "method"):
        if pole not in raw:
            duvody.append(f"chybí povinné pole '{pole}'")
        elif not isinstance(raw[pole], str):
            duvody.append(
                f"pole '{pole}' není řetězec, ale {type(raw[pole]).__name__}"
            )

    if "object" not in raw:
        duvody.append("chybí povinné pole 'object'")

    neznama = set(raw) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
    if neznama:
        duvody.append("neznámá pole: " + ", ".join(sorted(neznama)))

    return duvody


def _clamp_depth(hodnota: Any, max_depth: int,
                 _uroven: int = 0) -> tuple[Any, bool]:
    """Ořízne strukturu na zadanou hloubku.

    Proč to nedělá `json.dumps` sám: ten na příliš hluboké struktuře spadne
    přetečením zásobníku a na cyklické se zacyklí. Oříznutí dopředu je jediný
    způsob, jak zaručit, že se objekt uloží vždycky.

    Vstup:
        hodnota: cokoli serializovatelného.
        max_depth: nejhlubší úroveň, která se zachová.
        _uroven: vnitřní počitadlo zanoření.

    Výstup:
        Dvojice (oříznutá hodnota, jestli se něco uřízlo).
    """
    if _uroven >= max_depth:
        if isinstance(hodnota, (dict, list)):
            return DEPTH_MARKER, True
        return hodnota, False

    if isinstance(hodnota, dict):
        vysledek: dict[str, Any] = {}
        rezano = False
        for klic, podhodnota in hodnota.items():
            vysledek[str(klic)], r = _clamp_depth(
                podhodnota, max_depth, _uroven + 1
            )
            rezano = rezano or r
        return vysledek, rezano

    if isinstance(hodnota, list):
        vysledek_seznam: list[Any] = []
        rezano = False
        for polozka in hodnota:
            prvek, r = _clamp_depth(polozka, max_depth, _uroven + 1)
            vysledek_seznam.append(prvek)
            rezano = rezano or r
        return vysledek_seznam, rezano

    return hodnota, False


def _size_of(hodnota: Any) -> int:
    """Vrátí serializovanou velikost v bajtech.

    Při chybě:
        Nevyhazuje. Neserializovatelná hodnota vrátí nulu a chytí ji až
        `_preview`, které z ní udělá čitelný popis.
    """
    try:
        return len(json.dumps(hodnota, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError, RecursionError):
        return 0


def _preview(hodnota: Any, limit: int) -> str:
    """Vrátí zkrácenou textovou podobu objektu, který přerostl strop.

    Proč se místo celého objektu ukládá text: kdyby se ukládal oříznutý JSON,
    byl by to neplatný JSON a kukátko by ho nerozbalilo. Text je poctivější —
    je z něj vidět, co v objektu bylo, a je poznat, že je to náhražka.
    """
    try:
        cely = json.dumps(hodnota, ensure_ascii=False)
    except (TypeError, ValueError, RecursionError) as e:
        return f"<objekt nejde serializovat: {type(e).__name__}>"
    # Polovina stropu na náhled: zbytek místa patří hlavičce záznamu a musí
    # se vejít i s ní, jinak by ořezaný záznam byl zase přes strop.
    strop = max(256, limit // 2)
    return cely[:strop] + ("…" if len(cely) > strop else "")


def _malformed(*, duvod: str, raw: Any, received_ts: str) -> ObjectRecord:
    """Sestaví záznam pro vstup, který neprošel ověřením."""
    je_slovnik = isinstance(raw, dict)
    return ObjectRecord(
        ts=received_ts,
        component=str((raw.get("component") if je_slovnik else None) or "?"),
        method=str((raw.get("method") if je_slovnik else None) or "?"),
        label=str((raw.get("label") if je_slovnik else None) or "?"),
        object=None,
        trace=(raw.get("trace") if je_slovnik and
               isinstance(raw.get("trace"), str) else None),
        malformed=True,
        malformed_reason=duvod,
        raw=raw,
    )
