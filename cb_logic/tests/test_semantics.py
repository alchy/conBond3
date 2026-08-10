"""Testy pravdivostní sémantiky — LOGIC_SEMANTICS.md § 2–4."""
import unittest

from cb_logic.terms import Atom, Entity, Relation
from cb_logic.expressions import (AtomRef, Const, Equiv, Implies, Not, conj,
                                  disj)
from cb_logic.semantics import (Decision, Truth, UnboundAtomError, evaluate,
                                evaluate_partial, is_contradiction,
                                is_satisfiable, is_tautology, truth_table)

A_ = Atom(Relation("p", 1), (Entity("a"),))
B_ = Atom(Relation("q", 1), (Entity("b"),))
a, b = AtomRef(A_), AtomRef(B_)


class TestEvaluate(unittest.TestCase):
    def test_spojky(self):
        env = {A_: True, B_: False}
        self.assertFalse(evaluate(conj(a, b), env))
        self.assertTrue(evaluate(disj(a, b), env))
        self.assertFalse(evaluate(Not(a), env))
        self.assertFalse(evaluate(Implies(a, b), env))
        self.assertTrue(evaluate(Implies(b, a), env))
        self.assertFalse(evaluate(Equiv(a, b), env))
        self.assertTrue(evaluate(Const(True), {}))

    def test_chybejici_atom_je_hlasita_chyba(self):
        with self.assertRaises(UnboundAtomError):
            evaluate(conj(a, b), {A_: True})


class TestTruthTable(unittest.TestCase):
    def test_pocet_a_poradi_radku(self):
        rows = list(truth_table(conj(a, b)))
        self.assertEqual(len(rows), 4)
        self.assertEqual([r[0][A_] for r in rows], [False, False, True, True])
        self.assertEqual([r[0][B_] for r in rows], [False, True, False, True])
        self.assertEqual([r[1] for r in rows], [False, False, False, True])

    def test_vyraz_bez_atomu_ma_jeden_radek(self):
        rows = list(truth_table(Const(False)))
        self.assertEqual(rows, [({}, False)])


class TestDecisions(unittest.TestCase):
    def test_tautologie(self):
        r = is_tautology(disj(a, Not(a)))
        self.assertEqual(r.verdict, Decision.YES)
        self.assertIsNone(r.witness)

    def test_tautologie_ne_s_protiprikladem(self):
        r = is_tautology(a)
        self.assertEqual(r.verdict, Decision.NO)
        self.assertEqual(dict(r.witness), {A_: False})

    def test_kontradikce(self):
        self.assertEqual(is_contradiction(conj(a, Not(a))).verdict, Decision.YES)
        r = is_contradiction(a)
        self.assertEqual(r.verdict, Decision.NO)
        self.assertEqual(dict(r.witness), {A_: True})

    def test_splnitelnost_se_svedkem(self):
        r = is_satisfiable(conj(a, Not(b)))
        self.assertEqual(r.verdict, Decision.YES)
        self.assertEqual(dict(r.witness), {A_: True, B_: False})

    def test_limit_vraci_incomplete_ne_verdikt(self):
        exprs = [AtomRef(Atom(Relation("r", 1), (Entity(f"e{i}"),)))
                 for i in range(3)]
        r = is_tautology(disj(*exprs), max_atoms=2)
        self.assertEqual(r.verdict, Decision.INCOMPLETE)
        self.assertEqual(r.explored, 0)


class TestEvaluatePartial(unittest.TestCase):
    def test_kleene_tabulky(self):
        self.assertEqual(evaluate_partial(Not(a), {}), Truth.UNKNOWN)
        self.assertEqual(evaluate_partial(conj(a, b), {A_: False}), Truth.FALSE)
        self.assertEqual(evaluate_partial(conj(a, b), {A_: True}), Truth.UNKNOWN)
        self.assertEqual(evaluate_partial(disj(a, b), {A_: True}), Truth.TRUE)
        self.assertEqual(evaluate_partial(disj(a, b), {A_: False}), Truth.UNKNOWN)
        self.assertEqual(evaluate_partial(Implies(a, b), {A_: False}), Truth.TRUE)
        self.assertEqual(evaluate_partial(Implies(a, b), {B_: True}), Truth.TRUE)
        self.assertEqual(evaluate_partial(Implies(a, b), {A_: True, B_: False}),
                         Truth.FALSE)
        self.assertEqual(evaluate_partial(Equiv(a, b), {A_: True}), Truth.UNKNOWN)

    def test_epistemicke_cteni_tautologie(self):
        # A OR NOT A s neznámým A je v K3 UNKNOWN — nutnost rozhoduje tabulka.
        self.assertEqual(evaluate_partial(disj(a, Not(a)), {}), Truth.UNKNOWN)
        self.assertEqual(is_tautology(disj(a, Not(a))).verdict, Decision.YES)

    def test_shoda_s_uplnym_ohodnocenim(self):
        env = {A_: True, B_: False}
        e = Equiv(Implies(a, b), disj(Not(a), b))
        expected = Truth.TRUE if evaluate(e, env) else Truth.FALSE
        self.assertEqual(evaluate_partial(e, env), expected)


if __name__ == "__main__":
    unittest.main()
