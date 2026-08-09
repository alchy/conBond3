"""Pravdivostní sémantika — LOGIC_SEMANTICS.md § 2–4.

Tabulka je pohled a referenční orákulum (kap. 20.6 návrhu): pomalá,
zjevně správná. Rychlejší rozhodovací cesty (fáze 5–7) se měří proti ní.
Limit vrací INCOMPLETE — nedopočítaný výsledek se nikdy nevydává za
verdikt (zadání § 24).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Mapping

from cb_logic.expressions import (And, AtomRef, Const, Equiv, Expression,
                                  Implies, Not, Or, atoms)
from cb_logic.terms import Atom, atom_key


class Truth(Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class Decision(Enum):
    YES = "yes"
    NO = "no"
    INCOMPLETE = "incomplete"


DEFAULT_MAX_ATOMS = 20


class UnboundAtomError(LookupError):
    """Úplné ohodnocení nezná atom — chyba volajícího, ne UNKNOWN (INV-9)."""


def evaluate(expr: Expression, assignment: Mapping[Atom, bool]) -> bool:
    """Dvouhodnotové vyhodnocení nad úplným ohodnocením."""
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, AtomRef):
        try:
            return assignment[expr.atom]
        except KeyError:
            raise UnboundAtomError(expr.atom) from None
    if isinstance(expr, Not):
        return not evaluate(expr.operand, assignment)
    if isinstance(expr, And):
        return all(evaluate(o, assignment) for o in expr.operands)
    if isinstance(expr, Or):
        return any(evaluate(o, assignment) for o in expr.operands)
    if isinstance(expr, Implies):
        return (not evaluate(expr.antecedent, assignment)
                or evaluate(expr.consequent, assignment))
    return evaluate(expr.left, assignment) == evaluate(expr.right, assignment)


def evaluate_partial(expr: Expression,
                     partial: Mapping[Atom, bool]) -> Truth:
    """Silná Kleeneho K3 nad částečným ohodnocením (LOGIC_SEMANTICS § 4).

    UNKNOWN je epistemické „nevím": není-li výsledek UNKNOWN, každé úplné
    doplnění dá touž hodnotu (monotonie — testovaná vlastnost).
    """
    if isinstance(expr, Const):
        return Truth.TRUE if expr.value else Truth.FALSE
    if isinstance(expr, AtomRef):
        if expr.atom not in partial:
            return Truth.UNKNOWN
        return Truth.TRUE if partial[expr.atom] else Truth.FALSE
    if isinstance(expr, Not):
        inner = evaluate_partial(expr.operand, partial)
        if inner is Truth.UNKNOWN:
            return Truth.UNKNOWN
        return Truth.FALSE if inner is Truth.TRUE else Truth.TRUE
    if isinstance(expr, And):
        values = [evaluate_partial(o, partial) for o in expr.operands]
        if Truth.FALSE in values:
            return Truth.FALSE
        if Truth.UNKNOWN in values:
            return Truth.UNKNOWN
        return Truth.TRUE
    if isinstance(expr, Or):
        values = [evaluate_partial(o, partial) for o in expr.operands]
        if Truth.TRUE in values:
            return Truth.TRUE
        if Truth.UNKNOWN in values:
            return Truth.UNKNOWN
        return Truth.FALSE
    if isinstance(expr, Implies):
        ante = evaluate_partial(expr.antecedent, partial)
        cons = evaluate_partial(expr.consequent, partial)
        if ante is Truth.FALSE or cons is Truth.TRUE:
            return Truth.TRUE
        if ante is Truth.TRUE and cons is Truth.FALSE:
            return Truth.FALSE
        return Truth.UNKNOWN
    left = evaluate_partial(expr.left, partial)
    right = evaluate_partial(expr.right, partial)
    if Truth.UNKNOWN in (left, right):
        return Truth.UNKNOWN
    return Truth.TRUE if left is right else Truth.FALSE


def truth_table(expr: Expression) -> Iterator[tuple[dict[Atom, bool], bool]]:
    """Všechna ohodnocení atomů výrazu v kanonickém pořadí.

    Atomy dle atom_key; řádky lexikograficky, False < True (poslední atom
    se mění nejrychleji). Výraz bez atomů má jeden řádek.
    """
    atom_list = atoms(expr)
    for values in itertools.product((False, True), repeat=len(atom_list)):
        assignment = dict(zip(atom_list, values))
        yield assignment, evaluate(expr, assignment)


@dataclass(frozen=True)
class DecisionResult:
    """Verdikt + svědek (protipříklad/model) + kolik řádků se prozkoumalo."""
    verdict: Decision
    witness: tuple[tuple[Atom, bool], ...] | None
    explored: int


def _decide(expr: Expression, *, max_atoms: int,
            stop_value: bool) -> DecisionResult:
    """Společné jádro: hledá řádek s hodnotou stop_value.

    Najde-li ho, verdikt univerzální otázky je NO (svědek = ten řádek);
    projde-li vše bez nálezu, YES.
    """
    atom_list = atoms(expr)
    if len(atom_list) > max_atoms:
        return DecisionResult(Decision.INCOMPLETE, None, 0)
    explored = 0
    for assignment, value in truth_table(expr):
        explored += 1
        if value is stop_value:
            witness = tuple(sorted(assignment.items(),
                                   key=lambda kv: atom_key(kv[0])))
            return DecisionResult(Decision.NO, witness, explored)
    return DecisionResult(Decision.YES, None, explored)


def is_tautology(expr: Expression, *,
                 max_atoms: int = DEFAULT_MAX_ATOMS) -> DecisionResult:
    """Platí ve všech ohodnoceních? NO nese protipříklad."""
    return _decide(expr, max_atoms=max_atoms, stop_value=False)


def is_contradiction(expr: Expression, *,
                     max_atoms: int = DEFAULT_MAX_ATOMS) -> DecisionResult:
    """Neplatí v žádném ohodnocení? NO nese splňující ohodnocení."""
    return _decide(expr, max_atoms=max_atoms, stop_value=True)


def is_satisfiable(expr: Expression, *,
                   max_atoms: int = DEFAULT_MAX_ATOMS) -> DecisionResult:
    """Existuje splňující ohodnocení? YES nese svědka."""
    inner = is_contradiction(expr, max_atoms=max_atoms)
    if inner.verdict is Decision.INCOMPLETE:
        return inner
    if inner.verdict is Decision.NO:
        return DecisionResult(Decision.YES, inner.witness, inner.explored)
    return DecisionResult(Decision.NO, None, inner.explored)
