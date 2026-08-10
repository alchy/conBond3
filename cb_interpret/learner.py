"""Učení z dialogu — validační cesta nad interpretací (INTERPRETATION.md § 2).

learn() zapisuje výhradně přes assert_candidate/add_rule (jediná cesta,
mřížka provenience, konflikt se hlásí); ask() je čistě čtecí a při NEVÍM
vrací chybějící premisy jako formální podklad doptání.

Operátorové konstrukce (moci, chtít…) běží jako DOTAZY nad prostorem
modelů (classify_query), nikdy jako uložené tvrzení — modalita se nikdy
neukládá do báze (LANGUAGE_LEARNING.md, guard). Neznámé mapování vyvolá
učicí dotaz z uzavřeného menu operací.
"""
from __future__ import annotations

from dataclasses import dataclass

from cb_logic import (Accepted, Assertion, AtomRef, Conflicted, Evidence,
                      EvidenceKind, Explanation, InferenceResult,
                      KnowledgeBase, LEVEL_DEFINITION, LEVEL_DOCUMENTED,
                      ModalResult, ModalVerdict, Not, Provenance, Rejected,
                      Truth, WhyNotResult, classify_query, infer_forward, why,
                      why_not)
from cb_interpret.clarify import ClarificationRequest, build_clarification
from cb_interpret.interpret import Candidate, interpret_sentence
from cb_interpret.patterns import (LearnedPattern, Operation, PatternStore,
                                   StructuralSignature)
from cb_interpret.profile import LanguageProfile, cs_profile


@dataclass(frozen=True)
class LearnResult:
    candidate: Candidate
    outcome: Accepted | Rejected | Conflicted | None
    inference: InferenceResult | None


@dataclass(frozen=True)
class AskResult:
    candidate: Candidate
    truth: Truth | None
    explanations: tuple[Explanation, ...]
    why_not: WhyNotResult | None
    conflicted: bool = False
    modal: dict | None = None                       # výsledek modálního dotazu
    clarification: ClarificationRequest | None = None


def _run_modal(kb: KnowledgeBase, atom, operation: Operation, negated: bool):
    """Modální dotaz jako kvantifikace nad modely (∃M/∀M/¬∃M), ne operátor.

    Negace mění, KTERÝ dotaz se ptá (dualita), ne osu pravdivosti:
    ¬POSSIBLE = IMPOSSIBLE, ¬IMPOSSIBLE = POSSIBLE, ¬NECESSARY(P) = POSSIBLE(¬P).
    """
    expr = AtomRef(atom)
    mood = operation
    if negated:
        if operation is Operation.POSSIBLE:
            mood = Operation.IMPOSSIBLE
        elif operation is Operation.IMPOSSIBLE:
            mood = Operation.POSSIBLE
        else:                                    # ¬□P ≡ ◇¬P
            mood, expr = Operation.POSSIBLE, Not(AtomRef(atom))
    result: ModalResult = classify_query(kb, expr)
    verdict = result.verdict
    if verdict is ModalVerdict.INCOMPLETE:
        answer: bool | None = None
    elif mood is Operation.POSSIBLE:
        answer = verdict in (ModalVerdict.POSSIBLE, ModalVerdict.NECESSARY)
    elif mood is Operation.NECESSARY:
        answer = verdict is ModalVerdict.NECESSARY
    else:                                        # IMPOSSIBLE
        answer = verdict in (ModalVerdict.IMPOSSIBLE,
                             ModalVerdict.UNSATISFIABLE)
    return mood, result, answer


class DialogueLearner:
    """Dialog nad jednou bází a jedním store vzorů; žádný globální stav."""

    def __init__(self, kb: KnowledgeBase,
                 profile: LanguageProfile | None = None, *,
                 domain: str = "entita",
                 patterns: PatternStore | None = None) -> None:
        self.kb = kb
        self.profile = profile or cs_profile()
        self.domain = domain
        self.patterns = patterns if patterns is not None else PatternStore()

    def _interpret(self, tokens, text: str) -> Candidate:
        return interpret_sentence(
            tokens, text, patterns=self.patterns, domain=self.domain,
            question_mark=self.profile.question_mark)

    def learn(self, tokens, text: str, *, source: str = "dialog",
              level: int = LEVEL_DOCUMENTED) -> LearnResult:
        candidate = self._interpret(tokens, text)
        if candidate.kind in ("unparsed", "query", "modal_query",
                              "needs_pattern"):
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
        candidate = self._interpret(tokens, text)
        if candidate.kind == "needs_pattern":
            return AskResult(candidate, None, (), None,
                             clarification=build_clarification(
                                 candidate.signature))
        if candidate.kind == "modal_query":
            mood, result, answer = _run_modal(
                self.kb, candidate.literal.atom, candidate.operation,
                candidate.negated)
            modal = {
                "operation": mood.value,
                "verdict": result.verdict.name,
                "answer": answer,
                "models_true": result.models_true,
                "models_false": result.models_false,
                "has_witness": result.witness is not None,
                "has_counterexample": result.counterexample is not None,
            }
            truth = (Truth.TRUE if answer is True
                     else Truth.FALSE if answer is False else Truth.UNKNOWN)
            return AskResult(candidate, truth, (), None, modal=modal)
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

    # --- učení jazykových vzorů ----------------------------------------

    def teach_pattern(self, signature: StructuralSignature,
                      operation: Operation, *, learned_from: str,
                      learned_at: str | None = None) -> LearnedPattern:
        """Naučí mapování operátoru na operaci z menu — jako HYPOTÉZU."""
        return self.patterns.teach(signature, operation,
                                   learned_from=learned_from,
                                   learned_at=learned_at)

    def confirm_pattern(self, root_lemma: str) -> LearnedPattern | None:
        return self.patterns.confirm(root_lemma)

    def revoke_pattern(self, root_lemma: str) -> LearnedPattern | None:
        """Odvolá mapování; formální operace v jádru zůstává."""
        return self.patterns.revoke(root_lemma)
