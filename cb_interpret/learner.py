"""Učení z dialogu — validační cesta nad interpretací (INTERPRETATION.md § 2).

learn() zapisuje výhradně přes assert_candidate/add_rule; ask() je čistě
čtecí. Kopulové věty se složeným přísudkem vstupují jako konjunkce faktů
(jednotlivina) nebo pravidel (třída); dotaz je konjunkce atomů vyhodnocená
K3 nad bází. Nejednoznačná reference (obecné jméno v otázce) není hádání,
ale doptání; třídní čtení se ověří arbitrární instancí (probe).

Operátorové konstrukce běží jako DOTAZY nad prostorem modelů, nikdy jako
uložené tvrzení (LANGUAGE_LEARNING.md, guard).
"""
from __future__ import annotations

from dataclasses import dataclass

from cb_logic import (Accepted, Assertion, Atom, AtomRef, Conflicted, Entity,
                      Evidence, EvidenceKind, Explanation, InferenceResult,
                      KnowledgeBase, LEVEL_DEFINITION, LEVEL_DOCUMENTED,
                      Literal, ModalResult, ModalVerdict, Not, Provenance,
                      Rejected, Relation, Truth, WhyNotResult, classify_query,
                      evaluate_partial, infer_forward, why, why_not,
                      with_assumptions)
from cb_interpret.clarify import (ClarificationRequest, ReferenceClarification,
                                  build_clarification,
                                  build_reference_clarification)
from cb_interpret.interpret import Candidate, build_conjuncts, interpret_sentence
from cb_interpret.patterns import (LearnedPattern, Operation, PatternStore,
                                   StructuralSignature)
from cb_interpret.predication import ReferenceKind
from cb_interpret.profile import LanguageProfile, cs_profile

PROBE = Entity("__probe__")


@dataclass(frozen=True)
class LearnResult:
    candidate: Candidate
    outcome: Accepted | Rejected | Conflicted | None
    inference: InferenceResult | None
    accepted: int = 0            # kolik konjunktů se přijalo


@dataclass(frozen=True)
class AskResult:
    candidate: Candidate
    truth: Truth | None
    explanations: tuple[Explanation, ...]
    why_not: WhyNotResult | None
    conflicted: bool = False
    modal: dict | None = None
    clarification: ClarificationRequest | None = None
    reference: ReferenceClarification | None = None


def _run_modal(kb: KnowledgeBase, atoms, expr, operation: Operation,
               negated: bool):
    """Modální dotaz jako kvantifikace nad modely (∃M/∀M/¬∃M), ne operátor.

    Propozice smí být konjunkce atomů (složený vložený přísudek).
    `grounded` rozlišuje „našel model" od „nic to nezakazuje": je true,
    dotýká-li se KTERÝKOLI konjunkt nějaké znalosti.
    """
    mood = operation
    if negated:
        if operation is Operation.POSSIBLE:
            mood = Operation.IMPOSSIBLE
        elif operation is Operation.IMPOSSIBLE:
            mood = Operation.POSSIBLE
        else:
            mood, expr = Operation.POSSIBLE, Not(expr)
    result: ModalResult = classify_query(kb, expr)
    verdict = result.verdict
    if verdict is ModalVerdict.INCOMPLETE:
        answer: bool | None = None
    elif mood is Operation.POSSIBLE:
        answer = verdict in (ModalVerdict.POSSIBLE, ModalVerdict.NECESSARY)
    elif mood is Operation.NECESSARY:
        answer = verdict is ModalVerdict.NECESSARY
    else:
        answer = verdict in (ModalVerdict.IMPOSSIBLE,
                             ModalVerdict.UNSATISFIABLE)
    grounded = any(_touches_knowledge(kb, atom) for atom in atoms)
    return mood, result, answer, grounded


def _touches_knowledge(kb: KnowledgeBase, atom) -> bool:
    """Dotýká se propozice nějaké uložené znalosti?"""
    name = atom.relation.name
    if kb.truth_of(atom) is not Truth.UNKNOWN:
        return True
    for rule, _ in kb.rules:
        if rule.head.atom.relation.name == name:
            return True
    return False


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
        if candidate.kind not in ("fact", "rule"):
            return LearnResult(candidate, None, None)
        try:
            for relation in candidate.relations:
                self.kb.declare_relation(relation)
        except ValueError as error:
            return LearnResult(candidate, Rejected(str(error)), None)
        self.kb.extend_domain(self.domain, candidate.entities)
        evidence = Evidence(EvidenceKind.USER_ASSERTION, source=source)
        outcome: Accepted | Rejected | Conflicted | None = None
        accepted = 0
        if candidate.kind == "fact":
            for literal in candidate.literals:
                result = self.kb.assert_candidate(
                    Assertion(literal, evidence, level))
                if isinstance(result, Conflicted):
                    outcome = result
                elif outcome is None:
                    outcome = result
                if isinstance(result, Accepted):
                    accepted += 1
        else:
            for rule in candidate.rules:
                self.kb.add_rule(rule, Provenance(LEVEL_DEFINITION, evidence))
                accepted += 1
            outcome = Accepted(candidate.rules[0].head)
        inference = infer_forward(self.kb)
        return LearnResult(candidate, outcome, inference, accepted)

    def ask(self, tokens, text: str) -> AskResult:
        """Čistě čtecí dotaz; bázi nikdy nemění."""
        candidate = self._interpret(tokens, text)
        if candidate.kind == "reference_ambiguous":
            return AskResult(
                candidate, None, (), None,
                reference=build_reference_clarification(
                    candidate.predication.subject.lemma))
        if candidate.kind == "needs_pattern":
            return AskResult(candidate, None, (), None,
                             clarification=build_clarification(
                                 candidate.signature))
        if candidate.kind == "modal_query":
            return self._answer_modal(candidate)
        if candidate.kind == "query":
            return self._answer_query(candidate)
        return AskResult(candidate, None, (), None)

    def resolve_reference(self, candidate: Candidate,
                          choice: str) -> AskResult:
        """Rozřeší nejednoznačnou referenci po volbě uživatele (§5).

        Obě čtení sdílejí presupozici členství: co je řečeno jménem
        „auto", JE auto — u třídy se předpokládá arbitrární instance
        (probe), u instance referent sám. Doptávat se „je auto auto?"
        je nesmysl; členství zakládá reference sama.
        """
        pred = candidate.predication
        subject_rel = Relation(pred.subject.lemma, 1)
        if choice == "instance":
            referent = Entity(pred.subject.lemma.lower())
            view = self._assumed_view(candidate, subject_rel, referent)
            conjuncts, relations, entities = build_conjuncts(pred, referent)
            query = _query_from(conjuncts)
            result = self._answer_query(Candidate(
                "query", candidate.source_text, query_expr=query[0],
                query_atoms=query[1], relations=tuple(relations),
                entities=tuple(entities)), kb=view)
            # bez řetězu vysvětlení — symetrie s třídním čtením; řetěz by
            # jen opakoval presupozici („auto je auto (za předpokladu)")
            return AskResult(result.candidate, result.truth, (),
                             result.why_not, conflicted=result.conflicted)
        # třída: „platí ∀x subj(x) → …?" ověříme arbitrární instancí (probe)
        view = self._assumed_view(candidate, subject_rel, PROBE)
        conjuncts, _, _ = build_conjuncts(pred, PROBE)
        values = [view.truth_of(atom) if pos
                  else _flip(view.truth_of(atom))
                  for atom, pos, _, _ in conjuncts]
        if all(v is Truth.TRUE for v in values):
            truth = Truth.TRUE
        elif any(v is Truth.FALSE for v in values):
            truth = Truth.FALSE
        else:
            truth = Truth.UNKNOWN
        return AskResult(candidate, truth, (), None)

    def _assumed_view(self, candidate: Candidate, subject_rel: Relation,
                      entity: Entity) -> KnowledgeBase:
        """Kopie báze s presupozicí členství subject_rel(entity)."""
        view = self.kb.copy()
        for rel in tuple(candidate.relations) + (subject_rel,):
            try:
                view.declare_relation(rel)
            except ValueError:
                pass
        view.extend_domain(self.domain, (entity,))
        view = with_assumptions(view,
                                (Literal(Atom(subject_rel, (entity,))),))
        infer_forward(view)
        return view

    # --- vnitřní odpovědi ----------------------------------------------

    def _answer_modal(self, candidate: Candidate) -> AskResult:
        atoms = candidate.query_atoms or (candidate.literal.atom,)
        expr = candidate.query_expr or AtomRef(candidate.literal.atom)
        mood, result, answer, grounded = _run_modal(
            self.kb, atoms, expr, candidate.operation, candidate.negated)
        modal = {
            "operation": mood.value, "verdict": result.verdict.name,
            "answer": answer, "grounded": grounded,
            "models_true": result.models_true,
            "models_false": result.models_false,
            "has_witness": result.witness is not None,
            "has_counterexample": result.counterexample is not None,
        }
        truth = (Truth.TRUE if answer is True
                 else Truth.FALSE if answer is False else Truth.UNKNOWN)
        return AskResult(candidate, truth, (), None, modal=modal)

    def _answer_query(self, candidate: Candidate, *,
                      kb: KnowledgeBase | None = None) -> AskResult:
        kb = self.kb if kb is None else kb
        partial = {}
        for atom in candidate.query_atoms:
            value = kb.truth_of(atom)
            if value is not Truth.UNKNOWN:
                partial[atom] = value is Truth.TRUE
        truth = evaluate_partial(candidate.query_expr, partial)
        conflicted = any(kb.is_conflicted(a)
                         for a in candidate.query_atoms)
        explanations: tuple[Explanation, ...] = ()
        why_not_result: WhyNotResult | None = None
        if truth is Truth.TRUE:
            expl: list[Explanation] = []
            for atom in candidate.query_atoms:
                lit = Literal(atom, kb.truth_of(atom) is Truth.TRUE)
                expl.extend(why(kb, lit)[:1])
            explanations = tuple(expl)
        elif truth is Truth.FALSE:
            expl = []
            for atom in candidate.query_atoms:
                if kb.truth_of(atom) is Truth.FALSE:
                    expl.extend(why(kb, Literal(atom, False))[:1])
            explanations = tuple(expl)
        else:
            for atom in candidate.query_atoms:
                if kb.truth_of(atom) is Truth.UNKNOWN:
                    why_not_result = why_not(kb, Literal(atom, True))
                    break
        return AskResult(candidate, truth, explanations, why_not_result,
                         conflicted=conflicted)

    # --- učení jazykových vzorů ----------------------------------------

    def teach_pattern(self, signature: StructuralSignature,
                      operation: Operation, *, learned_from: str,
                      learned_at: str | None = None) -> LearnedPattern:
        return self.patterns.teach(signature, operation,
                                   learned_from=learned_from,
                                   learned_at=learned_at)

    def confirm_pattern(self, root_lemma: str) -> LearnedPattern | None:
        return self.patterns.confirm(root_lemma)

    def revoke_pattern(self, root_lemma: str) -> LearnedPattern | None:
        return self.patterns.revoke(root_lemma)


def _query_from(conjuncts):
    exprs = tuple(AtomRef(atom) if pos else Not(AtomRef(atom))
                  for atom, pos, _, _ in conjuncts)
    from cb_logic import conj
    query = conj(*exprs) if len(exprs) > 1 else exprs[0]
    return query, tuple(a for a, _, _, _ in conjuncts)


def _flip(value: Truth) -> Truth:
    if value is Truth.TRUE:
        return Truth.FALSE
    if value is Truth.FALSE:
        return Truth.TRUE
    return Truth.UNKNOWN
