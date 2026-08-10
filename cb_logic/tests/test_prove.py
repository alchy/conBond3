"""Testy backward proofu a assumptions — INFERENCE_ENGINE § 7–8; zadání § 37."""
import unittest

from cb_logic.expressions import AtomRef, disj
from cb_logic.knowledge import Rule
from cb_logic.semantics import Truth
from cb_logic.terms import Atom, Literal, Variable
from cb_logic.inference import (ProofStatus, infer_forward, prove,
                                with_assumptions)
from cb_logic.tests.test_inference import (T1, defrule, make_kb, say,
                                           unary_rule)


class TestProve(unittest.TestCase):
    def test_fakt_je_list_dukazu(self):
        kb = make_kb(("a",))
        say(kb, "a")
        proof, status = prove(kb, Literal(Atom(kb.relation("a"), (T1,))))
        self.assertEqual(status, ProofStatus.FOUND)
        self.assertIsNone(proof.rule_index)
        self.assertEqual(proof.premises, ())

    def test_retez_pravidel_da_strom_premis(self):
        kb = make_kb(("a", "b", "c"))
        defrule(kb, unary_rule(kb, "a", "b"))
        defrule(kb, unary_rule(kb, "b", "c"))
        say(kb, "a")
        proof, status = prove(kb, Literal(Atom(kb.relation("c"), (T1,))))
        self.assertEqual(status, ProofStatus.FOUND)
        self.assertEqual(proof.rule_index, 1)
        inner = proof.premises[0]
        self.assertEqual(inner.rule_index, 0)
        self.assertEqual(inner.premises[0].conclusion,
                         Literal(Atom(kb.relation("a"), (T1,))))

    def test_disjunktivni_telo_najde_prvni_uspesny_disjunkt(self):
        kb = make_kb(("b", "c", "d"))
        x = Variable("X")
        defrule(kb, Rule(((x, "things"),),
                         disj(AtomRef(Atom(kb.relation("b"), (x,))),
                              AtomRef(Atom(kb.relation("c"), (x,)))),
                         Literal(Atom(kb.relation("d"), (x,)))))
        say(kb, "c")
        proof, status = prove(kb, Literal(Atom(kb.relation("d"), (T1,))))
        self.assertEqual(status, ProofStatus.FOUND)
        self.assertEqual(proof.premises[0].conclusion,
                         Literal(Atom(kb.relation("c"), (T1,))))

    def test_cyklus_pravidel_neskonci_smyckou(self):
        kb = make_kb(("a", "b"))
        defrule(kb, unary_rule(kb, "a", "b"))
        defrule(kb, unary_rule(kb, "b", "a"))
        proof, status = prove(kb, Literal(Atom(kb.relation("b"), (T1,))))
        self.assertIsNone(proof)
        self.assertEqual(status, ProofStatus.NOT_FOUND)

    def test_hloubkovy_limit_je_incomplete(self):
        kb = make_kb(tuple("abcde"))
        for lo, hi in (("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")):
            defrule(kb, unary_rule(kb, lo, hi))
        say(kb, "a")
        proof, status = prove(kb, Literal(Atom(kb.relation("e"), (T1,))),
                              max_depth=2)
        self.assertIsNone(proof)
        self.assertEqual(status, ProofStatus.INCOMPLETE)


class TestAssumptions(unittest.TestCase):
    def test_scenar_zadani_37(self):
        """ASSUME a; a→b, b→c ⊢ c pod předpokladem a; báze nedotčená."""
        kb = make_kb(("a", "b", "c"))
        defrule(kb, unary_rule(kb, "a", "b"))
        defrule(kb, unary_rule(kb, "b", "c"))
        view = with_assumptions(
            kb, (Literal(Atom(kb.relation("a"), (T1,))),))
        infer_forward(view)
        c_atom = Atom(kb.relation("c"), (T1,))
        self.assertEqual(view.truth_of(c_atom), Truth.TRUE)
        c_derivation = next(d for d in view.derivations
                            if d.conclusion.atom == c_atom)
        self.assertEqual(c_derivation.assumptions, frozenset({"a(E:t1)"}))
        # původní báze se nezměnila
        self.assertEqual(kb.truth_of(c_atom), Truth.UNKNOWN)
        self.assertEqual(kb.derivations, [])


if __name__ == "__main__":
    unittest.main()
