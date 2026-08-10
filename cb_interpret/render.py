"""Renderování vysvětlení do jazyka šablonami profilu (INTERPRETATION.md § 3).

Kód nezná česká slova — všechna jsou v šablonách profilu. Vědomá mez:
lemmata bez morfologie; důkazem zůstává strom Explanation, text je jen
jeho čtení (zadání § 36).
"""
from __future__ import annotations

from cb_logic import Explanation, Literal, Truth, Value, from_literal, to_text
from cb_interpret.profile import LanguageProfile


def _term_text(term) -> str:
    if isinstance(term, Value):
        return str(term.value)
    return term.id


def render_literal(literal: Literal, profile: LanguageProfile) -> str:
    relation = literal.atom.relation
    args = literal.atom.args
    relation_text = relation.name.replace("_", " ")
    templates = profile.templates
    if relation.arity == 1:
        key = "unary_positive" if literal.positive else "unary_negative"
        return templates[key].format(arg0=_term_text(args[0]),
                                     relation=relation_text)
    if relation.arity == 2:
        key = "binary_positive" if literal.positive else "binary_negative"
        return templates[key].format(arg0=_term_text(args[0]),
                                     relation=relation_text,
                                     arg1=_term_text(args[1]))
    return to_text(from_literal(literal))  # obecná arita: formální zápis


def render_explanation(explanation: Explanation,
                       profile: LanguageProfile) -> str:
    claim = render_literal(explanation.literal, profile)
    templates = profile.templates
    if explanation.kind == "fact":
        source = (explanation.evidence.source
                  or explanation.evidence.kind.value)
        return templates["fact_source"].format(claim=claim, source=source)
    if explanation.kind == "assumption":
        return templates["assumption_note"].format(claim=claim)
    premises = templates["premise_join"].join(
        render_explanation(p, profile) for p in explanation.premises)
    return templates["because"].format(claim=claim, premises=premises)


def render_truth(truth: Truth, profile: LanguageProfile) -> str:
    key = {Truth.TRUE: "truth_true", Truth.FALSE: "truth_false",
           Truth.UNKNOWN: "truth_unknown"}[truth]
    return profile.templates[key]
