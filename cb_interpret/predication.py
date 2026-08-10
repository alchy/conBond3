"""Sémantická mezireprezentace kopulové věty — INTERPRETATION_IR.md.

Mezi strom a logiku vstupuje strukturovaný objekt: „podmět JE hlava
s vlastnostmi a vztahy". Extrakce rozhoduje podle role vazby (amod, nmod,
case), ne podle konkrétních slov — proto funguje obecně, ne jen na jedné
větě. Každý kus nese token, ze kterého vznikl (provenance).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReferenceKind(Enum):
    INDIVIDUAL = "individual"   # vlastní jméno → konkrétní entita
    CLASS = "class"             # obecné jméno v tvrzení → třída (univerzál)
    AMBIGUOUS = "ambiguous"     # obecné jméno v otázce → nejednoznačné


@dataclass(frozen=True)
class Reference:
    lemma: str
    upos: str
    kind: ReferenceKind
    token_id: int


@dataclass(frozen=True)
class Modifier:
    """Přívlastek (amod) jako vlastnost podmětu."""
    lemma: str
    token_id: int
    negated: bool = False


@dataclass(frozen=True)
class RelationMod:
    """Vazba nmod jako binární vztah k cíli.

    marker: co vztah pojmenovalo — předložka (nmod+case), nebo pádový
    marker holého pádu (`gen`, `dat`, …). Jméno z UD hodnoty Case je
    strukturální a nepodsouvá posesivní čtení, které věta nemá.
    """
    marker: str
    target_lemma: str
    target_upos: str
    token_id: int


@dataclass(frozen=True)
class Predication:
    subject: Reference
    head_lemma: str
    head_token: int
    modifiers: tuple[Modifier, ...]
    relations: tuple[RelationMod, ...]
    negated: bool
    is_question: bool
    determiner_prontypes: frozenset
    #: Kusy, které extrakce neunese — lowering je promění v `unparsed`
    #: s důvodem (tiché zahození mění význam).
    blockers: tuple[str, ...] = ()


def _kids(children, token, deprel):
    return [c for c in children.get(token.id, [])
            if c.deprel and (c.deprel == deprel
                             or c.deprel.startswith(deprel + ":"))]


def _negated(token) -> bool:
    return bool(token.feats) and token.feats.get("Polarity") == "Neg"


def _prontypes(token) -> set:
    if not token.feats or "PronType" not in token.feats:
        return set()
    return set(token.feats["PronType"].split(","))


def extract_copular(children, root, question: bool) -> Predication | None:
    """Strom kopulové věty → Predication; None, když chybí podmět."""
    subjects = _kids(children, root, "nsubj")
    if not subjects:
        return None
    subject = subjects[0]
    prontypes: set = set()
    for det in _kids(children, subject, "det"):
        prontypes |= _prontypes(det)

    kind = _reference_kind(subject, question, prontypes)
    reference = Reference(subject.lemma, subject.upos, kind, subject.id)

    modifiers = tuple(
        Modifier(a.lemma, a.id, _negated(a))
        for a in _kids(children, root, "amod"))
    relations = []
    blockers = []
    for nmod in _kids(children, root, "nmod"):
        cases = _kids(children, nmod, "case")
        if cases:
            relations.append(RelationMod(cases[0].lemma, nmod.lemma,
                                         nmod.upos, nmod.id))
        elif nmod.feats and nmod.feats.get("Case"):
            # holý pád (genitiv „město Česka") pojmenuje vztah sám —
            # strukturálně, žádný seznam slov
            relations.append(RelationMod(nmod.feats["Case"].lower(),
                                         nmod.lemma, nmod.upos, nmod.id))
        else:
            blockers.append(f"vazba nmod bez předložky i pádu "
                            f"({nmod.lemma!r}) mimo rozsah")
    negated = _negated(root) or any(_negated(c)
                                    for c in _kids(children, root, "cop"))
    return Predication(reference, root.lemma, root.id, modifiers,
                       tuple(relations), negated, question,
                       frozenset(prontypes), tuple(blockers))


def _reference_kind(subject, question: bool, prontypes: set) -> ReferenceKind:
    if subject.upos == "PROPN":
        return ReferenceKind.INDIVIDUAL
    if "Tot" in prontypes or "Neg" in prontypes:
        return ReferenceKind.CLASS          # „každý/žádný" → univerzál
    if question:
        return ReferenceKind.AMBIGUOUS      # obecné jméno v otázce
    return ReferenceKind.CLASS              # obecné jméno v tvrzení
