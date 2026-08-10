"""Testy invalidace derivací — INFERENCE_ENGINE § 6; zadání § 38."""
import unittest

from cb_logic.provenance import (Assertion, Evidence, EvidenceKind,
                                 LEVEL_DOCUMENTED)
from cb_logic.semantics import Truth
from cb_logic.terms import Atom, Entity, Literal
from cb_logic.inference import infer_forward, retract
from cb_logic.tests.test_inference import (T1, defrule, make_kb, say,
                                           unary_rule)

OBS = Evidence(EvidenceKind.OBSERVATION)


class TestRetract(unittest.TestCase):
    def test_scenar_zadani_38(self):
        """A→B, B→C, A; odstranění A ruší B i C tranzitivně."""
        kb = make_kb(("a", "b", "c"))
        defrule(kb, unary_rule(kb, "a", "b"))
        defrule(kb, unary_rule(kb, "b", "c"))
        say(kb, "a")
        infer_forward(kb)
        self.assertEqual(kb.truth_of(Atom(kb.relation("c"), (T1,))),
                         Truth.TRUE)
        result = retract(kb, Literal(Atom(kb.relation("a"), (T1,))))
        for rel in "abc":
            self.assertEqual(kb.truth_of(Atom(kb.relation(rel), (T1,))),
                             Truth.UNKNOWN)
        self.assertEqual(
            [lit.atom.relation.name for lit in result.removed],
            ["a", "b", "c"])

    def test_vlastni_evidence_prezije_ztratu_derivace(self):
        kb = make_kb(("a", "b"))
        defrule(kb, unary_rule(kb, "a", "b"))
        say(kb, "a")
        say(kb, "b")  # b má i vlastní evidenci
        infer_forward(kb)
        retract(kb, Literal(Atom(kb.relation("a"), (T1,))))
        self.assertEqual(kb.truth_of(Atom(kb.relation("b"), (T1,))),
                         Truth.TRUE)

    def test_vzajemna_podpora_se_sama_neudrzi(self):
        """A→B, B→A: po odstranění kořene nesmí cyklus derivací přežít."""
        kb = make_kb(("a", "b"))
        defrule(kb, unary_rule(kb, "a", "b"))
        defrule(kb, unary_rule(kb, "b", "a"))
        say(kb, "a")
        infer_forward(kb)
        retract(kb, Literal(Atom(kb.relation("a"), (T1,))))
        self.assertEqual(kb.truth_of(Atom(kb.relation("a"), (T1,))),
                         Truth.UNKNOWN)
        self.assertEqual(kb.truth_of(Atom(kb.relation("b"), (T1,))),
                         Truth.UNKNOWN)

    def test_shoda_s_prepoctem_od_nuly(self):
        """retract ≡ zahodit odvozené + infer_forward (recompute ekvivalence)."""
        kb = make_kb(tuple("abcd"))
        for lo, hi in (("a", "b"), ("b", "c"), ("a", "d")):
            defrule(kb, unary_rule(kb, lo, hi))
        say(kb, "a")
        say(kb, "d")  # d doložené i odvozené
        infer_forward(kb)
        retract(kb, Literal(Atom(kb.relation("a"), (T1,))))
        # nezávislý přepočet: čerstvá báze bez a
        fresh = make_kb(tuple("abcd"))
        for lo, hi in (("a", "b"), ("b", "c"), ("a", "d")):
            defrule(fresh, unary_rule(fresh, lo, hi))
        say(fresh, "d")
        infer_forward(fresh)
        for rel in "abcd":
            atom = Atom(kb.relation(rel), (T1,))
            self.assertEqual(kb.truth_of(atom), fresh.truth_of(atom),
                             msg=rel)


if __name__ == "__main__":
    unittest.main()
