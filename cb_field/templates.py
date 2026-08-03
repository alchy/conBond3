"""Šablony — sloučené shodné vzory okolí středů (krok 2 extrakční vrstvy).

Šablona je identita vzoru: signatura okna kolem středu. Dvě zastavení
okna se shodnou signaturou jsou týž vzor. Poměr šablon k počtu středů
je test T2 — jediné měření, které umí koncept vyvrátit (~0,2 zdravé,
0,2–0,5 přijatelné, nad 0,7 okno nezobecňuje).

Dvě měřené páky (rozhodují čísla, ne dojem):

* **verticals** — které vertikály vstupují do signatury (rozhodnutí R2).
  None = všechny metadatové; R2_PREFIXES = doporučená podmnožina
  (upos, pád, deprel, kotvy — bez rodu/čísla, které šablony štěpí).
* **center** — maskování středu: "out" nahradí středový řádek značkou
  díry. Šablona pak popisuje tvar okolí a střed je to, co se hledá —
  otázka je díra ve středu (viz docs/koncepce.md § o maskování).

Reference šablony je signatura; id je odvozené (pořadí vzniku) a s jinou
konfigurací se přečísluje — proto se id nikdy neukládá jako odkaz.
"""

from typing import Iterable, Optional, Sequence

from cb_field.field import SentenceField

#: Doporučená podmnožina vertikál pro signaturu (rozhodnutí R2 z
#: README-EXTRAKCNI_VRSTVA): tvar drží slovní druh, pád, závislost
#: a kotvy; rod/číslo/osoba šablony jen štěpí (Šel pes / Šla kočka
#: je týž vzor). Plná sada (None) je druhá strana páky — měří se obě.
R2_PREFIXES = ("UPOS=", "DEPREL=", "Case=", "ANCHOR=", "QANCHOR=",
               "LEM=", "QLEM=")

#: Značka zamaskovaného středu v signatuře. Není to prázdný řádek —
#: díra po středu je strukturní informace, hranice věty je ().
CENTER_HOLE = "*"


def default_centers(field: SentenceField) -> tuple:
    """Středy podle výchozí varianty rozhodnutí R1.

    Střed je: kořen věty, sloveso (i nekořenové, kvůli koordinaci),
    nebo jmenný řádek s vlastním case-dítětem (jádro s předložkou).
    Interpunkce ani spojky středem nejsou — koš by nic nenesl.
    Správnost kritéria rozhodne měření T1/T2, tady je jen výchozí stav.
    """
    case_heads = {t.head for t in field.tokens if t.deprel == "case"}
    centers = []
    for i, token in enumerate(field.tokens):
        nominal = token.upos in ("NOUN", "PROPN", "PRON", "NUM")
        if (token.head == 0 and token.upos != "PUNCT") \
                or token.upos == "VERB" \
                or (nominal and token.id in case_heads):
            centers.append(i)
    return tuple(centers)


def _row_signature(weights: dict, verticals: Optional[Sequence[str]]) -> tuple:
    """Signatura jednoho řádku: setříděné klíče, záporná vazba s '!'.

    Znaménko váhy do identity patří (PronType=Rel@−0.7 je jiný stav než
    +0.7), velikost váhy ne — identita je diskrétní, síla je na ladění.
    """
    keys = []
    for key, weight in weights.items():
        if verticals is not None and not key.startswith(tuple(verticals)):
            continue
        keys.append(f"!{key}" if weight < 0 else key)
    return tuple(sorted(keys))


class TemplateBank:
    """Sbírka šablon nad korpusem: signatura → id, počty, doklady.

    Jedna banka = jedna konfigurace pák (verticals × center). Pro
    porovnání konfigurací se staví víc bank nad týmž korpusem.
    """

    def __init__(self, verticals: Optional[Sequence[str]] = None,
                 center: str = "out", order: str = "linear") -> None:
        if center not in ("in", "out"):
            raise ValueError(f"center musí být 'in' nebo 'out', ne {center!r}")
        if order not in ("linear", "canon"):
            raise ValueError(
                f"order musí být 'linear' nebo 'canon', ne {order!r}")
        self.verticals = tuple(verticals) if verticals is not None else None
        self.center = center
        #: order="canon" kanonizuje pořadí okna: signatura je střed +
        #: setříděná množina okolních řádků. Mitigace slabého místa S1
        #: (volný slovosled: „Petr je v Praze" × „V Praze je Petr") —
        #: cena je ztráta lineární pozice, rozhodne měření T2.
        self.order = order
        self._ids: dict = {}        # signatura -> id (pořadí vzniku)
        self._counts: dict = {}     # id -> počet výskytů
        self._examples: dict = {}   # id -> [(věta, střed), …] max 3
        self._centers_total = 0

    def signature(self, field: SentenceField, center: int) -> tuple:
        """Signatura okna kolem středu: n-tice 2r+1 řádkových signatur.

        Hranice věty je prázdný řádek (), zamaskovaný střed je
        (CENTER_HOLE,) — obě informace jsou strukturní a nesmí se slít.
        """
        rows = []
        for offset in range(-field.r, field.r + 1):
            j = center + offset
            if not 0 <= j < len(field.tokens):
                rows.append(())
            elif offset == 0 and self.center == "out":
                rows.append((CENTER_HOLE,))
            else:
                rows.append(_row_signature(field.metadata[j], self.verticals))
        if self.order == "canon":
            # střed zůstává na svém místě, okolí se kanonizuje setříděním
            middle = rows[field.r]
            around = tuple(sorted(rows[:field.r] + rows[field.r + 1:]))
            return (middle, around)
        return tuple(rows)

    def add(self, field: SentenceField,
            centers: Optional[Iterable[int]] = None) -> list:
        """Zařadí středy pole do banky; vrátí id šablony pro každý střed.

        Bez centers se použije default_centers (R1). Nová signatura
        založí šablonu, známá se sloučí — a právě míra slučování je T2.
        """
        assigned = []
        for center in (default_centers(field) if centers is None else centers):
            sig = self.signature(field, center)
            template_id = self._ids.get(sig)
            if template_id is None:
                template_id = len(self._ids)
                self._ids[sig] = template_id
                self._counts[template_id] = 0
                self._examples[template_id] = []
            self._counts[template_id] += 1
            self._centers_total += 1
            if len(self._examples[template_id]) < 3:
                self._examples[template_id].append(
                    (field.source, field.tokens[center].form))
            assigned.append(template_id)
        return assigned

    def add_corpus(self, corpus) -> None:
        """Zařadí všechna pole korpusu."""
        for field in corpus:
            self.add(field)

    # --- čísla ----------------------------------------------------------

    @property
    def templates(self) -> int:
        return len(self._ids)

    @property
    def centers(self) -> int:
        return self._centers_total

    def ratio(self) -> float:
        """T2: šablony / středy. Bez středů je poměr 0 — prázdno, ne chyba."""
        if not self._centers_total:
            return 0.0
        return len(self._ids) / self._centers_total

    def shared(self) -> int:
        """Kolik šablon sdílí víc středů (≥ 2 doklady) — míra zobecnění."""
        return sum(1 for n in self._counts.values() if n >= 2)

    def top(self, n: int = 5) -> list:
        """Nejčastější šablony: (id, počet, doklady) — k ručnímu čtení."""
        ordered = sorted(self._counts.items(), key=lambda kv: -kv[1])
        return [(tid, count, self._examples[tid])
                for tid, count in ordered[:n]]

    def __repr__(self) -> str:
        verticals = "plné" if self.verticals is None else "R2"
        return (f"TemplateBank({self.templates} šablon / "
                f"{self.centers} středů, T2={self.ratio():.2f}, "
                f"vertikály {verticals}, střed {self.center})")
