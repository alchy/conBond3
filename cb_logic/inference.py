"""Inferenční jádro — grounding a forward chaining (INFERENCE_ENGINE § 2–5).

Tělo pravidla se čte K3 nad bází: z absence se nic neodvozuje (INV-1),
negace v těle platí jen z doloženého záporu, karanténovaný atom je UNKNOWN.
Odvození nese premisy z rozhodující větve a pravidlo (INV-2). Konflikt se
eviduje, nikdy tiše neřeší (INV-5). Limity vracejí INCOMPLETE — nedopočítaný
běh se nevydává za fixpoint (zadání § 24).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum
from typing import Iterator

from cb_logic.expressions import (And, AtomRef, Const, Equiv, Expression,
                                  Implies, Not, Or, from_literal, substitute,
                                  to_text)
from cb_logic.knowledge import KnowledgeBase, Rule
from cb_logic.provenance import (Conflict, Derivation, Evidence, EvidenceKind,
                                 LEVEL_HYPOTHESIS, Provenance)
from cb_logic.semantics import Truth
from cb_logic.terms import (Atom, Literal, Term, Variable, atom_key, term_key)


@dataclass(frozen=True)
class Limits:
    """Deterministické stropy; čas jádro neměří (determinismus)."""
    max_rounds: int = 100
    max_derivations: int = 10_000
    max_ground_instances: int = 100_000


class InferenceStatus(Enum):
    FIXPOINT = "fixpoint"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class InferenceResult:
    status: InferenceStatus
    new_facts: tuple[Literal, ...]
    conflicts: tuple[Conflict, ...]
    rounds: int
    derivations_added: int


def ground_rule(rule: Rule, kb: KnowledgeBase) -> Iterator[
        tuple[dict[Variable, Term], Expression, Literal]]:
    """Instanciace pravidla přes konečné domény v kanonickém pořadí."""
    variables = [v for v, _ in rule.var_domains]
    member_lists = [sorted(kb.domain(name).members, key=term_key)
                    for _, name in rule.var_domains]
    for combo in itertools.product(*member_lists):
        binding = dict(zip(variables, combo))
        body = substitute(rule.body, binding)
        head_expr = substitute(from_literal(rule.head), binding)
        if isinstance(head_expr, Not):
            head = Literal(head_expr.operand.atom, False)
        else:
            head = Literal(head_expr.atom, True)
        yield binding, body, head


def assumption_label(literal: Literal) -> str:
    """Kanonická jmenovka předpokladu (KNOWLEDGE_MODEL § 9)."""
    return to_text(from_literal(literal))


def _support_assumptions(kb: KnowledgeBase, literal: Literal) -> frozenset[str]:
    """Jmenovky předpokladů nejsilnější podpory literálu.

    Vlastní evidence bez předpokladu ⇒ žádné; předpoklad ⇒ jeho jmenovka;
    jen derivace ⇒ nejmenší množina jmenovek (deterministicky).
    """
    side = kb._sides.get((literal.atom, literal.positive))
    if side is None:
        return frozenset()
    if side.own is not None and side.own.level > LEVEL_HYPOTHESIS:
        if side.own.evidence.kind is EvidenceKind.ASSUMPTION:
            return frozenset({assumption_label(literal)})
        return frozenset()
    if side.derivations:
        candidate_sets = [kb.derivations[i].assumptions
                          for i in side.derivations]
        return min(candidate_sets, key=lambda s: (len(s), sorted(s)))
    return frozenset()


def _eval_collect(expr: Expression,
                  kb: KnowledgeBase) -> tuple[Truth, tuple[Literal, ...]]:
    """K3 vyhodnocení nad bází + premisy rozhodující větve.

    And: všechny konjunkty; Or: první TRUE disjunkt; Not: vnitřek;
    Implies: FALSE antecedent nebo TRUE konsekvent; Equiv: obě strany.
    """
    if isinstance(expr, Const):
        return (Truth.TRUE if expr.value else Truth.FALSE), ()
    if isinstance(expr, AtomRef):
        value = kb.truth_of(expr.atom)
        if value is Truth.TRUE:
            return value, (Literal(expr.atom, True),)
        if value is Truth.FALSE:
            return value, (Literal(expr.atom, False),)
        return Truth.UNKNOWN, ()
    if isinstance(expr, Not):
        inner, premises = _eval_collect(expr.operand, kb)
        if inner is Truth.UNKNOWN:
            return Truth.UNKNOWN, ()
        return (Truth.FALSE if inner is Truth.TRUE else Truth.TRUE), premises
    if isinstance(expr, And):
        collected: list[Literal] = []
        unknown = False
        for op in expr.operands:
            value, premises = _eval_collect(op, kb)
            if value is Truth.FALSE:
                return Truth.FALSE, premises
            if value is Truth.UNKNOWN:
                unknown = True
            else:
                collected.extend(premises)
        if unknown:
            return Truth.UNKNOWN, ()
        return Truth.TRUE, _dedupe(collected)
    if isinstance(expr, Or):
        collected = []
        unknown = False
        for op in expr.operands:
            value, premises = _eval_collect(op, kb)
            if value is Truth.TRUE:
                return Truth.TRUE, premises
            if value is Truth.UNKNOWN:
                unknown = True
            else:
                collected.extend(premises)
        if unknown:
            return Truth.UNKNOWN, ()
        return Truth.FALSE, _dedupe(collected)
    if isinstance(expr, Implies):
        ante, ante_premises = _eval_collect(expr.antecedent, kb)
        cons, cons_premises = _eval_collect(expr.consequent, kb)
        if ante is Truth.FALSE:
            return Truth.TRUE, ante_premises
        if cons is Truth.TRUE:
            return Truth.TRUE, cons_premises
        if ante is Truth.TRUE and cons is Truth.FALSE:
            return Truth.FALSE, _dedupe(list(ante_premises + cons_premises))
        return Truth.UNKNOWN, ()
    left, left_premises = _eval_collect(expr.left, kb)
    right, right_premises = _eval_collect(expr.right, kb)
    if Truth.UNKNOWN in (left, right):
        return Truth.UNKNOWN, ()
    value = Truth.TRUE if left is right else Truth.FALSE
    return value, _dedupe(list(left_premises + right_premises))


def _dedupe(literals: list[Literal]) -> tuple[Literal, ...]:
    seen: set[Literal] = set()
    out = []
    for lit in literals:
        if lit not in seen:
            seen.add(lit)
            out.append(lit)
    return tuple(out)


@dataclass(frozen=True)
class Proof:
    """Uzel důkazu: list (rule_index None) = fakt báze, jinak aplikace pravidla."""
    conclusion: Literal
    rule_index: int | None
    premises: tuple["Proof", ...]


class ProofStatus(Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    INCOMPLETE = "incomplete"


def prove(kb: KnowledgeBase, literal: Literal, *,
          max_depth: int = 32) -> tuple[Proof | None, ProofStatus]:
    """Backward proof — dotazová a vysvětlovací cesta (INFERENCE_ENGINE § 7).

    Cyklus cílů na cestě větev ukončí (žádná smyčka); vyčerpaná hloubka je
    INCOMPLETE, nikoli NOT_FOUND (zadání § 24).
    """
    hit_limit = [False]
    proof = _prove_literal(kb, literal, frozenset(), max_depth, hit_limit)
    if proof is not None:
        return proof, ProofStatus.FOUND
    return None, (ProofStatus.INCOMPLETE if hit_limit[0]
                  else ProofStatus.NOT_FOUND)


def _prove_literal(kb: KnowledgeBase, literal: Literal,
                   path: frozenset[Literal], depth: int,
                   hit_limit: list[bool]) -> Proof | None:
    value = kb.truth_of(literal.atom)
    if value is Truth.TRUE and literal.positive:
        return Proof(literal, None, ())
    if value is Truth.FALSE and not literal.positive:
        return Proof(literal, None, ())
    if depth <= 0:
        hit_limit[0] = True
        return None
    if literal in path:
        return None
    for rule_index, (rule, _) in enumerate(kb.rules):
        head = rule.head
        if head.positive != literal.positive:
            continue
        if head.atom.relation != literal.atom.relation:
            continue
        binding = _unify_head(head.atom, literal.atom)
        if binding is None:
            continue
        free = [(v, d) for v, d in rule.var_domains if v not in binding]
        member_lists = [sorted(kb.domain(d).members, key=term_key)
                        for _, d in free]
        for combo in itertools.product(*member_lists):
            full = dict(binding)
            full.update({v: t for (v, _), t in zip(free, combo)})
            body = _nnf(substitute(rule.body, full), False)
            sub = _prove_expr(kb, body, path | {literal}, depth - 1,
                              hit_limit)
            if sub is not None:
                return Proof(literal, rule_index, sub)
    return None


def _unify_head(head_atom: Atom, goal_atom: Atom) -> dict[Variable, Term] | None:
    binding: dict[Variable, Term] = {}
    for h, g in zip(head_atom.args, goal_atom.args):
        if isinstance(h, Variable):
            if h in binding and binding[h] != g:
                return None
            binding[h] = g
        elif h != g:
            return None
    return binding


def _prove_expr(kb: KnowledgeBase, expr: Expression,
                path: frozenset[Literal], depth: int,
                hit_limit: list[bool]) -> tuple[Proof, ...] | None:
    """Důkaz výrazu v NNF (listy: AtomRef, Not(AtomRef), Const)."""
    if isinstance(expr, Const):
        return () if expr.value else None
    if isinstance(expr, AtomRef):
        proof = _prove_literal(kb, Literal(expr.atom, True), path, depth,
                               hit_limit)
        return (proof,) if proof is not None else None
    if isinstance(expr, Not):
        proof = _prove_literal(kb, Literal(expr.operand.atom, False), path,
                               depth, hit_limit)
        return (proof,) if proof is not None else None
    if isinstance(expr, And):
        collected: list[Proof] = []
        for op in expr.operands:
            sub = _prove_expr(kb, op, path, depth, hit_limit)
            if sub is None:
                return None
            collected.extend(sub)
        return tuple(collected)
    for op in expr.operands:  # Or: první úspěšný disjunkt
        sub = _prove_expr(kb, op, path, depth, hit_limit)
        if sub is not None:
            return sub
    return None


def _nnf(expr: Expression, negated: bool) -> Expression:
    """Negační normální forma — interní pohled pro důkaz, ne druhý kalkul."""
    if isinstance(expr, Const):
        return Const(expr.value != negated)
    if isinstance(expr, AtomRef):
        return Not(expr) if negated else expr
    if isinstance(expr, Not):
        return _nnf(expr.operand, not negated)
    if isinstance(expr, And):
        ops = tuple(_nnf(o, negated) for o in expr.operands)
        return Or(ops) if negated else And(ops)
    if isinstance(expr, Or):
        ops = tuple(_nnf(o, negated) for o in expr.operands)
        return And(ops) if negated else Or(ops)
    if isinstance(expr, Implies):
        if negated:  # ¬(a→b) ≡ a ∧ ¬b
            return And((_nnf(expr.antecedent, False),
                        _nnf(expr.consequent, True)))
        return Or((_nnf(expr.antecedent, True),
                   _nnf(expr.consequent, False)))
    a, b = expr.left, expr.right
    if negated:  # ¬(a↔b) ≡ (a∧¬b) ∨ (b∧¬a)
        return Or((And((_nnf(a, False), _nnf(b, True))),
                   And((_nnf(b, False), _nnf(a, True)))))
    return And((Or((_nnf(a, True), _nnf(b, False))),
                Or((_nnf(b, True), _nnf(a, False)))))


def with_assumptions(kb: KnowledgeBase,
                     literals: tuple[Literal, ...]) -> KnowledgeBase:
    """Pohled na bázi s předpoklady (KNOWLEDGE_MODEL § 9); báze se nemění.

    Předpoklad je fakt s Evidence(ASSUMPTION) a jmenovkou; derivace pod ním
    vzniklé nesou jmenovky přes _support_assumptions.
    """
    from cb_logic.provenance import LEVEL_DOCUMENTED
    view = kb.copy()
    for literal in literals:
        side = view._side(literal.atom, literal.positive)
        if side.own is None or LEVEL_DOCUMENTED > side.own.level:
            side.own = Provenance(
                LEVEL_DOCUMENTED,
                Evidence(EvidenceKind.ASSUMPTION,
                         source=assumption_label(literal)))
    return view


@dataclass(frozen=True)
class RetractResult:
    """Strany, které odstraněním ztratily veškerou podporu (kanonicky)."""
    removed: tuple[Literal, ...]


def retract(kb: KnowledgeBase, literal: Literal) -> RetractResult:
    """Odstranění vlastní evidence + well-founded přepočet podpory (INV-12).

    Podporované strany se přepočítají uzávěrem z vlastních evidencí přes
    derivace — vzájemná podpora dvou odvozených se sama neudrží. Derivace
    bez opory se odpojí od stran (ledger derivací zůstává historií).
    """
    side = kb._sides.get((literal.atom, literal.positive))
    before = {key for key, s in kb._sides.items() if s.supported()}
    if side is not None:
        side.own = None
    grounded: set[tuple[Atom, bool]] = {
        key for key, s in kb._sides.items()
        if s.own is not None and s.own.level > LEVEL_HYPOTHESIS}
    active: set[int] = set()
    changed = True
    while changed:
        changed = False
        for derivation in kb.derivations:
            if derivation.id in active:
                continue
            conclusion_key = (derivation.conclusion.atom,
                              derivation.conclusion.positive)
            if kb._sides.get(conclusion_key) is None:
                continue
            if derivation.id not in kb._sides[conclusion_key].derivations:
                continue
            if all((p.atom, p.positive) in grounded
                   for p in derivation.premises):
                active.add(derivation.id)
                if conclusion_key not in grounded:
                    grounded.add(conclusion_key)
                changed = True
    for key, s in kb._sides.items():
        s.derivations = [i for i in s.derivations if i in active]
    removed = [Literal(atom, positive)
               for (atom, positive) in sorted(
                   before - {key for key, s in kb._sides.items()
                             if s.supported()},
                   key=lambda k: (atom_key(k[0]), not k[1]))]
    return RetractResult(tuple(removed))


def infer_forward(kb: KnowledgeBase,
                  limits: Limits = Limits()) -> InferenceResult:
    """Forward chaining do fixpointu; mutuje bázi (odvozená vrstva)."""
    signatures = {(d.conclusion, d.premises, d.rule_index)
                  for d in kb.derivations}
    new_facts: list[Literal] = []
    conflicts: list[Conflict] = []
    derivations_added = 0
    instances = 0
    rounds = 0
    while rounds < limits.max_rounds:
        rounds += 1
        changed = False
        for rule_index, (rule, _) in enumerate(kb.rules):
            for _, body, head in ground_rule(rule, kb):
                instances += 1
                if instances > limits.max_ground_instances:
                    return InferenceResult(InferenceStatus.INCOMPLETE,
                                           tuple(new_facts), tuple(conflicts),
                                           rounds, derivations_added)
                value, premises = _eval_collect(body, kb)
                if value is not Truth.TRUE:
                    continue
                signature = (head, premises, rule_index)
                if signature in signatures:
                    continue
                if derivations_added >= limits.max_derivations:
                    return InferenceResult(InferenceStatus.INCOMPLETE,
                                           tuple(new_facts), tuple(conflicts),
                                           rounds, derivations_added)
                assumptions = frozenset().union(
                    *(_support_assumptions(kb, p) for p in premises)) \
                    if premises else frozenset()
                derivation = Derivation(len(kb.derivations), head, premises,
                                        rule_index, assumptions)
                was_conflicted = kb.is_conflicted(head.atom)
                side = kb._side(head.atom, head.positive)
                was_supported = side.supported()
                kb.derivations.append(derivation)
                side.derivations.append(derivation.id)
                signatures.add(signature)
                derivations_added += 1
                changed = True
                if not was_supported:
                    new_facts.append(head)
                opposite = kb._sides.get((head.atom, not head.positive))
                if (opposite is not None and opposite.supported()
                        and not was_conflicted):
                    conflict = kb._record_conflict(head.atom)
                    conflicts.append(conflict)
        if not changed:
            return InferenceResult(InferenceStatus.FIXPOINT,
                                   tuple(new_facts), tuple(conflicts),
                                   rounds, derivations_added)
    return InferenceResult(InferenceStatus.INCOMPLETE, tuple(new_facts),
                           tuple(conflicts), rounds, derivations_added)
