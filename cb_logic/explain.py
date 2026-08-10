"""Vysvětlení — why, explain_conflict, why_not (PROVENANCE.md § 2–3).

Důkaz je strom hodnot; přirozený jazyk z něj smí generovat vyšší vrstva,
nikdy naopak (zadání § 36, § 47). why_not má tři poctivé větve:
doloženě-ne / modálně-nemožné / nevím-a-tohle-chybí.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import itertools

from cb_logic.expressions import (And, AtomRef, Const, Not, Or, from_literal,
                                  substitute, to_text)
from cb_logic.inference import _nnf, _unify_head, assumption_label
from cb_logic.terms import term_key
from cb_logic.knowledge import KnowledgeBase
from cb_logic.models import (ModalResult, ModalVerdict, ModelLimits,
                             classify_query)
from cb_logic.provenance import Evidence, EvidenceKind, LEVEL_DERIVED, \
    LEVEL_HYPOTHESIS
from cb_logic.semantics import Truth
from cb_logic.terms import Atom, Literal


@dataclass(frozen=True)
class Explanation:
    """Uzel vysvětlení; kind ∈ {fact, assumption, derived}."""
    literal: Literal
    kind: str
    evidence: Evidence | None
    level: int | None
    rule_index: int | None
    assumptions: tuple[str, ...]
    premises: tuple["Explanation", ...]

    def to_json_object(self) -> dict:
        return {
            "literal": to_text(from_literal(self.literal)),
            "kind": self.kind,
            "evidence": (None if self.evidence is None else
                         {"kind": self.evidence.kind.value,
                          "source": self.evidence.source}),
            "level": self.level,
            "rule_index": self.rule_index,
            "assumptions": list(self.assumptions),
            "premises": [p.to_json_object() for p in self.premises],
        }


def why(kb: KnowledgeBase, literal: Literal, *, max_explanations: int = 3,
        max_depth: int = 16) -> tuple[Explanation, ...]:
    """Vysvětlení podpory literálu: vlastní evidence + větev za derivaci.

    Prázdný výsledek = literál nemá podporu. Jeden závěr smí mít víc
    vysvětlení (řetěz má druhy, kap. 18.1 návrhu).
    """
    side = kb._sides.get((literal.atom, literal.positive))
    if side is None or max_depth < 0:
        return ()
    out: list[Explanation] = []
    if side.own is not None and side.own.level > LEVEL_HYPOTHESIS:
        is_assumption = side.own.evidence.kind is EvidenceKind.ASSUMPTION
        out.append(Explanation(
            literal, "assumption" if is_assumption else "fact",
            side.own.evidence, side.own.level, None,
            (assumption_label(literal),) if is_assumption else (), ()))
    for derivation_id in side.derivations:
        if len(out) >= max_explanations:
            break
        derivation = kb.derivations[derivation_id]
        premises: list[Explanation] = []
        complete = True
        for premise in derivation.premises:
            sub = why(kb, premise, max_explanations=1,
                      max_depth=max_depth - 1)
            if not sub:
                complete = False
                break
            premises.append(sub[0])
        if complete:
            out.append(Explanation(literal, "derived", None, LEVEL_DERIVED,
                                   derivation.rule_index,
                                   tuple(sorted(derivation.assumptions)),
                                   tuple(premises)))
    return tuple(out[:max_explanations])


def explain_conflict(kb: KnowledgeBase,
                     atom: Atom) -> tuple[Explanation, ...] | None:
    """Vysvětlení obou stran konfliktu (zadání § 39); None = není konflikt."""
    if not kb.is_conflicted(atom):
        return None
    return (why(kb, Literal(atom, True), max_explanations=1)
            + why(kb, Literal(atom, False), max_explanations=1))


@dataclass(frozen=True)
class Suggestion:
    """Co by závěr učinilo pravdou: pravidlo + chybějící premisy."""
    rule_index: int
    missing: tuple[Literal, ...]


@dataclass(frozen=True)
class WhyNotResult:
    """kind ∈ {documented_false, impossible, unknown}."""
    kind: str
    explanations: tuple[Explanation, ...]
    modal: ModalResult | None
    suggestions: tuple[Suggestion, ...]


def why_not(kb: KnowledgeBase, literal: Literal, *,
            limits: ModelLimits = ModelLimits(),
            max_depth: int = 2) -> WhyNotResult:
    value = kb.truth_of(literal.atom)
    opposite_holds = ((value is Truth.FALSE and literal.positive)
                      or (value is Truth.TRUE and not literal.positive))
    if opposite_holds:
        return WhyNotResult("documented_false",
                            why(kb, literal.negated(), max_explanations=1),
                            None, ())
    modal = classify_query(kb, from_literal(literal), limits=limits)
    if modal.verdict is ModalVerdict.IMPOSSIBLE:
        return WhyNotResult("impossible", (), modal, ())
    return WhyNotResult("unknown", (), modal,
                        _suggestions(kb, literal, max_depth))


def _suggestions(kb: KnowledgeBase, literal: Literal,
                 depth: int) -> tuple[Suggestion, ...]:
    """Hlava se s cílem UNIFIKUJE (ne grounduje přes doménu) — návrh musí
    fungovat i pro entitu, kterou báze ještě nezná."""
    if depth <= 0:
        return ()
    out: list[Suggestion] = []
    for rule_index, (rule, _) in enumerate(kb.rules):
        if rule.head.positive != literal.positive:
            continue
        if rule.head.atom.relation != literal.atom.relation:
            continue
        binding = _unify_head(rule.head.atom, literal.atom)
        if binding is None:
            continue
        free = [(v, d) for v, d in rule.var_domains if v not in binding]
        member_lists = [sorted(kb.domain(d).members, key=term_key)
                        for _, d in free]
        for combo in itertools.product(*member_lists):
            full = dict(binding)
            full.update({v: t for (v, _), t in zip(free, combo)})
            body = substitute(rule.body, full)
            missing: list[Literal] = []
            for body_literal in _nnf_literals(_nnf(body, False)):
                if (kb.truth_of(body_literal.atom) is Truth.UNKNOWN
                        and body_literal not in missing):
                    missing.append(body_literal)
            if missing:
                out.append(Suggestion(rule_index, tuple(missing)))
                for body_literal in missing:
                    out.extend(_suggestions(kb, body_literal, depth - 1))
    seen: set[Suggestion] = set()
    return tuple(s for s in out if not (s in seen or seen.add(s)))


def _nnf_literals(expr) -> tuple[Literal, ...]:
    """Listy NNF výrazu jako literály (s potřebnou polaritou)."""
    if isinstance(expr, AtomRef):
        return (Literal(expr.atom, True),)
    if isinstance(expr, Not):
        return (Literal(expr.operand.atom, False),)
    if isinstance(expr, (And, Or)):
        out: list[Literal] = []
        for op in expr.operands:
            for lit in _nnf_literals(op):
                if lit not in out:
                    out.append(lit)
        return tuple(out)
    return ()  # Const
