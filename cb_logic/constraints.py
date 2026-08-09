"""Constrainty — omezení prostoru modelů (CONSTRAINT_MODEL.md).

Jedna sémantika, více výpočetních čtení: každý constraint umí vydat
ekvivalentní výraz (definice, orákulum, vysvětlení) a zároveň se umí
vyhodnotit přímo (počítáním). Shodu obou čtení hlídají testy (T-11).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Mapping

from cb_logic.expressions import (AtomRef, Equiv, Expression, Implies, Not,
                                  conj, disj)
from cb_logic.semantics import Truth, evaluate, evaluate_partial
from cb_logic.terms import Atom, Domain, Relation, Term, term_key


@dataclass(frozen=True)
class CardinalityConstraint:
    """Právě/nejméně/nejvýše k pravdivých atomů z rodiny."""
    atoms: tuple[Atom, ...]
    at_least: int
    at_most: int | None
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.atoms:
            raise ValueError("kardinalita nad prázdnou rodinou")
        if len(set(self.atoms)) != len(self.atoms):
            raise ValueError("rodina atomů obsahuje duplicitu")
        for atom in self.atoms:
            if not atom.ground:
                raise ValueError(f"atom rodiny není ground: {atom}")
        if not 0 <= self.at_least <= len(self.atoms):
            raise ValueError(
                f"at_least {self.at_least} mimo 0–{len(self.atoms)}")
        if self.at_most is not None and self.at_most < self.at_least:
            raise ValueError(
                f"at_most {self.at_most} < at_least {self.at_least}")


@dataclass(frozen=True)
class ExpressionConstraint:
    """Obecný výraz, který musí platit ve všech modelech."""
    expr: Expression
    label: str | None = None


Constraint = CardinalityConstraint | ExpressionConstraint


def exactly_one(atoms: tuple[Atom, ...],
                label: str | None = None) -> CardinalityConstraint:
    return CardinalityConstraint(atoms, 1, 1, label)


def at_least_one(atoms: tuple[Atom, ...],
                 label: str | None = None) -> CardinalityConstraint:
    return CardinalityConstraint(atoms, 1, None, label)


def at_most_one(atoms: tuple[Atom, ...],
                label: str | None = None) -> CardinalityConstraint:
    return CardinalityConstraint(atoms, 0, 1, label)


def excludes(a: Expression, b: Expression,
             label: str | None = None) -> ExpressionConstraint:
    return ExpressionConstraint(Not(conj(a, b)), label)


def requires(a: Expression, b: Expression,
             label: str | None = None) -> ExpressionConstraint:
    return ExpressionConstraint(Implies(a, b), label)


def equivalent(a: Expression, b: Expression,
               label: str | None = None) -> ExpressionConstraint:
    return ExpressionConstraint(Equiv(a, b), label)


MAX_EXPANSION_ATOMS = 12


def to_expression(constraint: Constraint, *,
                  max_expansion_atoms: int = MAX_EXPANSION_ATOMS) -> Expression:
    """Ekvivalentní výraz constraintu (definice sémantiky).

    Kombinatorická expanze kardinality je přípustná jen pro malé rodiny —
    nad limit je to hlasitá chyba a volající použije přímé počítání.
    """
    if isinstance(constraint, ExpressionConstraint):
        return constraint.expr
    n = len(constraint.atoms)
    if n > max_expansion_atoms:
        raise ValueError(
            f"expanze kardinality nad {max_expansion_atoms} atomů "
            f"(rodina má {n}); použij přímé počítání")
    upper = n if constraint.at_most is None else constraint.at_most
    options: list[Expression] = []
    for k in range(constraint.at_least, upper + 1):
        for chosen in itertools.combinations(range(n), k):
            chosen_set = set(chosen)
            parts: list[Expression] = []
            for i, atom in enumerate(constraint.atoms):
                ref: Expression = AtomRef(atom)
                parts.append(ref if i in chosen_set else Not(ref))
            options.append(conj(*parts) if len(parts) > 1 else parts[0])
    return disj(*options) if len(options) > 1 else options[0]


def satisfied_by(constraint: Constraint,
                 assignment: Mapping[Atom, bool]) -> bool:
    """Splňuje úplné ohodnocení constraint? Kardinalita počítáním."""
    if isinstance(constraint, ExpressionConstraint):
        return evaluate(constraint.expr, assignment)
    true_count = sum(1 for a in constraint.atoms if assignment[a])
    if true_count < constraint.at_least:
        return False
    return constraint.at_most is None or true_count <= constraint.at_most


def truth_partial(constraint: Constraint,
                  partial: Mapping[Atom, bool]) -> Truth:
    """K3 čtení constraintu nad částečným ohodnocením (CONSTRAINT_MODEL § 3)."""
    if isinstance(constraint, ExpressionConstraint):
        return evaluate_partial(constraint.expr, partial)
    known_true = sum(1 for a in constraint.atoms
                     if a in partial and partial[a])
    known_false = sum(1 for a in constraint.atoms
                      if a in partial and not partial[a])
    open_count = len(constraint.atoms) - known_true - known_false
    if constraint.at_most is not None and known_true > constraint.at_most:
        return Truth.FALSE
    if known_true + open_count < constraint.at_least:
        return Truth.FALSE
    if (constraint.at_least <= known_true
            and (constraint.at_most is None
                 or known_true + open_count <= constraint.at_most)):
        return Truth.TRUE
    return Truth.UNKNOWN


def atom_family(relation: Relation, template: tuple[Term | None, ...],
                over: Domain) -> tuple[Atom, ...]:
    """Rodina atomů: šablona s právě jedním volným místem doplněným doménou.

    Čistá funkce nad deklaracemi — žádná znalost konkrétních úloh; pořadí
    členů domény dle term_key (determinismus).
    """
    if len(template) != relation.arity:
        raise ValueError(
            f"šablona má {len(template)} míst, arita je {relation.arity}")
    holes = [i for i, t in enumerate(template) if t is None]
    if len(holes) != 1:
        raise ValueError(f"šablona musí mít právě jedno volné místo, "
                         f"má {len(holes)}")
    hole = holes[0]
    members = sorted(over.members, key=term_key)
    family = []
    for member in members:
        args = tuple(member if i == hole else t
                     for i, t in enumerate(template))
        family.append(Atom(relation, args))
    return tuple(family)
