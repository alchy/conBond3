"""Termy, relace, atomy a literály — datový model dle KNOWLEDGE_MODEL.md § 2–3.

Rovnost Entity je výhradně podle id: popisek je pro člověka a nesmí
vstoupit do žádného rozhodnutí (anti-overfitting, zadání § 43/46).
Stabilní klíče (term_key, atom_key) nesou determinismus všech iterací
(LOGIC_SEMANTICS § 8) — při shodě rozhoduje klíč, ne pořadí v paměti.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entity:
    """Jednotlivina se stabilní identitou; label je jen popisek."""
    id: str
    label: str | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Value:
    """Literální hodnota domény; musí být hashovatelná."""
    value: object


@dataclass(frozen=True)
class Variable:
    """Proměnná pravidel a dotazů; do báze nikdy nevstupuje volná."""
    name: str


Term = Entity | Value | Variable


def term_key(term: Term) -> str:
    """Stabilní řadicí klíč termu; druhy termů nekolidují prefixem."""
    if isinstance(term, Entity):
        return f"E:{term.id}"
    if isinstance(term, Value):
        return f"V:{type(term.value).__name__}:{term.value!r}"
    return f"?:{term.name}"


def is_ground(term: Term) -> bool:
    """Ground = bez proměnné."""
    return not isinstance(term, Variable)


@dataclass(frozen=True)
class Domain:
    """Pojmenovaná konečná množina ground termů (kvantifikační obor)."""
    name: str
    members: tuple[Term, ...]

    def __post_init__(self) -> None:
        for member in self.members:
            if not is_ground(member):
                raise ValueError(
                    f"doména {self.name!r}: člen {member!r} není ground")


@dataclass(frozen=True)
class Relation:
    """Deklarovaný predikát; překlep arity je hlasitá chyba, ne nová relace."""
    name: str
    arity: int

    def __post_init__(self) -> None:
        if self.arity < 1:
            raise ValueError(f"relace {self.name!r}: arita musí být >= 1")


@dataclass(frozen=True)
class Atom:
    """Aplikace relace na termy; jednotka pravdivosti."""
    relation: Relation
    args: tuple[Term, ...]

    def __post_init__(self) -> None:
        if len(self.args) != self.relation.arity:
            raise ValueError(
                f"atom {self.relation.name}: {len(self.args)} argumentů, "
                f"arita je {self.relation.arity}")

    @property
    def ground(self) -> bool:
        return all(is_ground(a) for a in self.args)


def atom_key(atom: Atom) -> str:
    """Stabilní řadicí klíč atomu."""
    args = ",".join(term_key(a) for a in atom.args)
    return f"{atom.relation.name}/{atom.relation.arity}({args})"


@dataclass(frozen=True)
class Literal:
    """Atom s polaritou; záporný literál je plnohodnotné tvrzení (INV-1)."""
    atom: Atom
    positive: bool = True

    def negated(self) -> "Literal":
        return Literal(self.atom, not self.positive)
