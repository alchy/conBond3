"""Testy forward chainingu — INFERENCE_ENGINE § 2–5; zadání §21–§24."""
import unittest

from cb_logic.expressions import AtomRef, Not, conj
from cb_logic.knowledge import KnowledgeBase, Rule
from cb_logic.provenance import (Assertion, Evidence, EvidenceKind,
                                 LEVEL_DEFINITION, LEVEL_DOCUMENTED,
                                 Provenance)
from cb_logic.semantics import Truth
from cb_logic.terms import Atom, Domain, Entity, Literal, Relation, Variable
from cb_logic.inference import (InferenceStatus, Limits, ground_rule,
                                infer_forward)

OBS = Evidence(EvidenceKind.OBSERVATION)
USER = Evidence(EvidenceKind.USER_ASSERTION)
T1 = Entity("t1")


def make_kb(relations, entities=(T1,)):
    kb = KnowledgeBase()
    for name in relations:
        kb.declare_relation(Relation(name, 1))
    kb.declare_domain(Domain("things", tuple(entities)))
    return kb


def unary_rule(kb, body_rel, head_rel, *, negative_head=False):
    x = Variable("X")
    return Rule(((x, "things"),),
                AtomRef(Atom(kb.relation(body_rel), (x,))),
                Literal(Atom(kb.relation(head_rel), (x,)), not negative_head))


def say(kb, rel, entity=T1, positive=True):
    return kb.assert_candidate(Assertion(
        Literal(Atom(kb.relation(rel), (entity,)), positive),
        OBS, LEVEL_DOCUMENTED))


def defrule(kb, rule):
    return kb.add_rule(rule, Provenance(LEVEL_DEFINITION, USER))


class TestGrounding(unittest.TestCase):
    def test_kanonicke_poradi_instanci(self):
        kb = make_kb(("p", "q"), entities=(Entity("b"), Entity("a")))
        rule = unary_rule(kb, "p", "q")
        bindings = [b for b, _, _ in ground_rule(rule, kb)]
        names = [next(iter(b.values())).id for b in bindings]
        self.assertEqual(names, ["a", "b"])  # dle term_key, ne pořadí vložení


class TestChains(unittest.TestCase):
    def test_retez_bez_pevneho_poctu_kroku(self):
        kb = make_kb(tuple("abcde"))
        for lo, hi in (("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")):
            defrule(kb, unary_rule(kb, lo, hi))
        say(kb, "a")
        result = infer_forward(kb)
        self.assertEqual(result.status, InferenceStatus.FIXPOINT)
        for rel in "bcde":
            self.assertEqual(kb.truth_of(Atom(kb.relation(rel), (T1,))),
                             Truth.TRUE)
        derived = kb.derivations[-1]
        self.assertEqual(derived.conclusion,
                         Literal(Atom(kb.relation("e"), (T1,))))
        self.assertEqual(derived.premises,
                         (Literal(Atom(kb.relation("d"), (T1,))),))

    def test_cyklus_terminuje(self):
        kb = make_kb(("a", "b"))
        defrule(kb, unary_rule(kb, "a", "b"))
        defrule(kb, unary_rule(kb, "b", "a"))
        say(kb, "a")
        result = infer_forward(kb)
        self.assertEqual(result.status, InferenceStatus.FIXPOINT)
        self.assertEqual(kb.truth_of(Atom(kb.relation("b"), (T1,))),
                         Truth.TRUE)

    def test_fixpoint_je_idempotentni(self):
        kb = make_kb(("a", "b"))
        defrule(kb, unary_rule(kb, "a", "b"))
        say(kb, "a")
        infer_forward(kb)
        second = infer_forward(kb)
        self.assertEqual(second.derivations_added, 0)
        self.assertEqual(second.new_facts, ())


class TestInv1(unittest.TestCase):
    def test_z_absence_se_nic_neodvozuje(self):
        kb = make_kb(("a", "b", "c"))
        x = Variable("X")
        # b(X) AND NOT c(X) → a(X); c není známé ⇒ tělo UNKNOWN ⇒ nevystřelí
        defrule(kb, Rule(((x, "things"),),
                         conj(AtomRef(Atom(kb.relation("b"), (x,))),
                              Not(AtomRef(Atom(kb.relation("c"), (x,))))),
                         Literal(Atom(kb.relation("a"), (x,)))))
        say(kb, "b")
        infer_forward(kb)
        self.assertEqual(kb.truth_of(Atom(kb.relation("a"), (T1,))),
                         Truth.UNKNOWN)

    def test_negace_v_tele_jen_z_dolozeneho_zaporu(self):
        kb = make_kb(("a", "b", "c"))
        x = Variable("X")
        defrule(kb, Rule(((x, "things"),),
                         conj(AtomRef(Atom(kb.relation("b"), (x,))),
                              Not(AtomRef(Atom(kb.relation("c"), (x,))))),
                         Literal(Atom(kb.relation("a"), (x,)))))
        say(kb, "b")
        say(kb, "c", positive=False)  # doložený zápor
        infer_forward(kb)
        self.assertEqual(kb.truth_of(Atom(kb.relation("a"), (T1,))),
                         Truth.TRUE)


class TestConflictsAndLimits(unittest.TestCase):
    def test_odvozene_ustupuje_dolozenemu_ale_zaznamena_se(self):
        kb = make_kb(("a", "b"))
        defrule(kb, unary_rule(kb, "a", "b", negative_head=True))
        say(kb, "a")
        say(kb, "b")  # doložené kladné b
        result = infer_forward(kb)
        b_atom = Atom(kb.relation("b"), (T1,))
        self.assertEqual(kb.truth_of(b_atom), Truth.TRUE)   # doložené drží
        self.assertTrue(kb.is_conflicted(b_atom))           # spor je vidět
        self.assertEqual(len(result.conflicts), 1)

    def test_limit_derivaci_vraci_incomplete(self):
        kb = make_kb(tuple("abcde"))
        for lo, hi in (("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")):
            defrule(kb, unary_rule(kb, lo, hi))
        say(kb, "a")
        result = infer_forward(kb, Limits(max_derivations=2))
        self.assertEqual(result.status, InferenceStatus.INCOMPLETE)
        self.assertEqual(result.derivations_added, 2)

    def test_limit_kol_vraci_incomplete(self):
        kb = make_kb(tuple("abc"))
        defrule(kb, unary_rule(kb, "a", "b"))
        defrule(kb, unary_rule(kb, "b", "c"))
        say(kb, "a")
        result = infer_forward(kb, Limits(max_rounds=1))
        self.assertEqual(result.status, InferenceStatus.INCOMPLETE)


if __name__ == "__main__":
    unittest.main()
