"""Učení z dialogu — validační cesta nad interpretací (INTERPRETATION.md § 2).

learn() zapisuje výhradně přes assert_candidate/add_rule (jediná cesta,
mřížka provenience, konflikt se hlásí); ask() je čistě čtecí a při NEVÍM
vrací chybějící premisy jako formální podklad doptání.
"""
from __future__ import annotations

from dataclasses import dataclass

from cb_logic import (Accepted, Assertion, Conflicted, Evidence,
                      EvidenceKind, Explanation, InferenceResult,
                      KnowledgeBase, LEVEL_DEFINITION, LEVEL_DOCUMENTED,
                      Provenance, Rejected, Truth, WhyNotResult,
                      infer_forward, why, why_not)
from cb_interpret.interpret import Candidate, interpret_sentence
from cb_interpret.profile import LanguageProfile, cs_profile


@dataclass(frozen=True)
class LearnResult:
    candidate: Candidate
    outcome: Accepted | Rejected | Conflicted | None
    inference: InferenceResult | None


@dataclass(frozen=True)
class AskResult:
    candidate: Candidate
    truth: Truth | None                       # pravdivost DOTAZOVANÉHO literálu
    explanations: tuple[Explanation, ...]
    why_not: WhyNotResult | None
    conflicted: bool = False


class DialogueLearner:
    """Dialog nad jednou bází; žádný globální stav."""

    def __init__(self, kb: KnowledgeBase,
                 profile: LanguageProfile | None = None, *,
                 domain: str = "entita") -> None:
        self.kb = kb
        self.profile = profile or cs_profile()
        self.domain = domain

    def learn(self, tokens, text: str, *, source: str = "dialog",
              level: int = LEVEL_DOCUMENTED) -> LearnResult:
        candidate = interpret_sentence(
            tokens, text, domain=self.domain,
            question_mark=self.profile.question_mark)
        if candidate.kind in ("unparsed", "query"):
            return LearnResult(candidate, None, None)
        try:
            for relation in candidate.relations:
                self.kb.declare_relation(relation)
        except ValueError as error:
            return LearnResult(candidate, Rejected(str(error)), None)
        self.kb.extend_domain(self.domain, candidate.entities)
        evidence = Evidence(EvidenceKind.USER_ASSERTION, source=source)
        if candidate.kind == "fact":
            outcome = self.kb.assert_candidate(
                Assertion(candidate.literal, evidence, level))
        else:
            self.kb.add_rule(candidate.rule,
                             Provenance(LEVEL_DEFINITION, evidence))
            outcome = Accepted(candidate.rule.head)
        inference = infer_forward(self.kb)
        return LearnResult(candidate, outcome, inference)

    def ask(self, tokens, text: str) -> AskResult:
        """Čistě čtecí dotaz; bázi nikdy nemění."""
        candidate = interpret_sentence(
            tokens, text, domain=self.domain,
            question_mark=self.profile.question_mark)
        if candidate.literal is None:
            return AskResult(candidate, None, (), None)
        literal = candidate.literal
        atom_truth = self.kb.truth_of(literal.atom)
        if atom_truth is Truth.UNKNOWN:
            literal_truth = Truth.UNKNOWN
        else:
            holds = (atom_truth is Truth.TRUE) == literal.positive
            literal_truth = Truth.TRUE if holds else Truth.FALSE
        if literal_truth is Truth.TRUE:
            explanations = why(self.kb, literal)
        elif literal_truth is Truth.FALSE:
            explanations = why(self.kb, literal.negated())
        else:
            explanations = ()
        why_not_result = (why_not(self.kb, literal)
                          if literal_truth is Truth.UNKNOWN else None)
        return AskResult(candidate, literal_truth, explanations,
                         why_not_result,
                         conflicted=self.kb.is_conflicted(literal.atom))
