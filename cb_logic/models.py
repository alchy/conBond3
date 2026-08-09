"""Prostor modelů — scope, enumerace, modální dotazy (MODEL_REASONING.md).

Model = úplné ohodnocení atomů scope splňující doložená čtení, constrainty
a ground instance pravidel jako implikace. Possible/necessary/impossible je
obecná vlastnost enginu: protipříklad je dotaz NECESSARY. Limity vracejí
INCOMPLETE — nikdy se nevydávají za verdikt (zadání § 24).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum

from cb_logic.constraints import (CardinalityConstraint, Constraint,
                                  truth_partial)
from cb_logic.expressions import (Expression, Implies, atoms as expr_atoms,
                                  from_literal)
from cb_logic.inference import ground_rule
from cb_logic.knowledge import KnowledgeBase
from cb_logic.provenance import LEVEL_DOCUMENTED
from cb_logic.semantics import Truth, evaluate_partial
from cb_logic.terms import Atom, atom_key


@dataclass(frozen=True)
class ModelLimits:
    max_scope_atoms: int = 24
    max_nodes: int = 200_000
    max_models: int = 10_000


class SearchStatus(Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


Model = tuple[tuple[Atom, bool], ...]


@dataclass(frozen=True)
class ScopeResult:
    atoms: tuple[Atom, ...]
    instances: tuple[tuple[str, Expression], ...]
    status: SearchStatus


def _constraint_atoms(constraint: Constraint) -> tuple[Atom, ...]:
    if isinstance(constraint, CardinalityConstraint):
        return constraint.atoms
    return expr_atoms(constraint.expr)


def model_scope(kb: KnowledgeBase, seed_atoms: tuple[Atom, ...],
                limits: ModelLimits = ModelLimits()) -> ScopeResult:
    """Relevanční uzávěr (MODEL_REASONING § 1).

    Semínka: dotaz + atomy constraintů + doložené fakty (úroveň ≥ 2).
    Instance pravidla vstupuje celá, jakmile se s množinou protne —
    irelevantní pravidla se nikdy nepřitáhnou (zadání § 44).
    """
    scope: set[Atom] = set(seed_atoms)
    for constraint, _ in kb.constraints:
        scope.update(_constraint_atoms(constraint))
    for (atom, _), side in kb._sides.items():
        if side.own is not None and side.own.level >= LEVEL_DOCUMENTED:
            scope.add(atom)
    all_instances = []
    for i, (rule, _) in enumerate(kb.rules):
        for _, body, head in ground_rule(rule, kb):
            expr = Implies(body, from_literal(head))
            all_instances.append((f"rule[{i}]", frozenset(expr_atoms(expr)),
                                  expr))
    included = [False] * len(all_instances)
    changed = True
    while changed:
        changed = False
        for idx, (_, instance_atoms, _) in enumerate(all_instances):
            if not included[idx] and instance_atoms & scope:
                included[idx] = True
                scope.update(instance_atoms)
                changed = True
    instances = tuple((label, expr)
                      for idx, (label, _, expr) in enumerate(all_instances)
                      if included[idx])
    atoms_tuple = tuple(sorted(scope, key=atom_key))
    status = (SearchStatus.INCOMPLETE
              if len(atoms_tuple) > limits.max_scope_atoms
              else SearchStatus.COMPLETE)
    return ScopeResult(atoms_tuple, instances, status)


@dataclass(frozen=True)
class ModelSearchResult:
    models: tuple[Model, ...]
    status: SearchStatus
    nodes: int
    scope: tuple[Atom, ...]
    conflicted: tuple[Atom, ...]
    eliminated: tuple[tuple[str, int], ...]


def enumerate_models(kb: KnowledgeBase, *, seed_atoms: tuple[Atom, ...] = (),
                     limits: ModelLimits = ModelLimits(),
                     skip_constraint: int | None = None) -> ModelSearchResult:
    """DFS enumerace konzistentních modelů (MODEL_REASONING § 2)."""
    scope_result = model_scope(kb, tuple(seed_atoms), limits)
    if scope_result.status is SearchStatus.INCOMPLETE:
        return ModelSearchResult((), SearchStatus.INCOMPLETE, 0,
                                 scope_result.atoms, (), ())
    checks: list[tuple[str, str, object]] = []
    for i, (constraint, _) in enumerate(kb.constraints):
        if i == skip_constraint:
            continue
        label = constraint.label or f"constraint[{i}]"
        checks.append((label, "constraint", constraint))
    for label, expr in scope_result.instances:
        checks.append((label, "expr", expr))

    pinned: dict[Atom, bool] = {}
    conflicted: list[Atom] = []
    for atom in scope_result.atoms:
        if kb.is_conflicted(atom):
            conflicted.append(atom)
        value = kb.documented_truth(atom)
        if value is not Truth.UNKNOWN:
            pinned[atom] = value is Truth.TRUE

    free = [a for a in scope_result.atoms if a not in pinned]
    assignment = dict(pinned)
    models: list[Model] = []
    eliminated: Counter[str] = Counter()
    nodes = 0
    status = SearchStatus.COMPLETE

    def violated_label() -> str | None:
        for label, kind, payload in checks:
            if kind == "constraint":
                value = truth_partial(payload, assignment)
            else:
                value = evaluate_partial(payload, assignment)
            if value is Truth.FALSE:
                return label
        return None

    def dfs(i: int) -> None:
        nonlocal nodes, status
        if status is SearchStatus.INCOMPLETE:
            return
        label = violated_label()
        if label is not None:
            eliminated[label] += 1
            return
        if i == len(free):
            if len(models) >= limits.max_models:
                status = SearchStatus.INCOMPLETE
                return
            models.append(tuple(sorted(assignment.items(),
                                       key=lambda kv: atom_key(kv[0]))))
            return
        for value in (False, True):
            nodes += 1
            if nodes > limits.max_nodes:
                status = SearchStatus.INCOMPLETE
                return
            assignment[free[i]] = value
            dfs(i + 1)
            del assignment[free[i]]

    dfs(0)
    return ModelSearchResult(tuple(models), status, nodes,
                             scope_result.atoms, tuple(conflicted),
                             tuple(sorted(eliminated.items())))


@dataclass(frozen=True)
class AtomClassification:
    """Co musí / nemůže / může platit napříč modely (zadání § 26, § 30)."""
    necessary: tuple[Atom, ...]
    impossible: tuple[Atom, ...]
    possible: tuple[Atom, ...]


def classify_atoms(result: ModelSearchResult) -> AtomClassification:
    if not result.models:
        return AtomClassification((), (), ())
    necessary, impossible, possible = [], [], []
    for idx, (atom, _) in enumerate(result.models[0]):
        values = {model[idx][1] for model in result.models}
        if values == {True}:
            necessary.append(atom)
        elif values == {False}:
            impossible.append(atom)
        else:
            possible.append(atom)
    return AtomClassification(tuple(necessary), tuple(impossible),
                              tuple(possible))
