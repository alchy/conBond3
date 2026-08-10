"""Testy AST výrazů — LOGIC_SEMANTICS.md § 1."""
import unittest

from cb_logic.terms import Atom, Entity, Literal, Relation, Value, Variable
from cb_logic.expressions import (And, AtomRef, Const, Equiv, Implies, Not,
                                  Or, atoms, conj, disj, from_literal,
                                  substitute, to_text)

P = Relation("p", 1)
Q = Relation("q", 1)
A_ = Atom(P, (Entity("a"),))
B_ = Atom(Q, (Entity("b"),))


class TestConstruction(unittest.TestCase):
    def test_vyrazy_jsou_hodnoty(self):
        self.assertEqual(Not(AtomRef(A_)), Not(AtomRef(A_)))
        self.assertEqual(len({conj(AtomRef(A_), AtomRef(B_)),
                              conj(AtomRef(A_), AtomRef(B_))}), 1)

    def test_conj_zplosti_a_jeden_operand_vraci_primo(self):
        inner = conj(AtomRef(A_), AtomRef(B_))
        flat = conj(inner, AtomRef(A_))
        self.assertIsInstance(flat, And)
        self.assertEqual(len(flat.operands), 3)
        self.assertEqual(conj(AtomRef(A_)), AtomRef(A_))

    def test_disj_nula_operandu_je_chyba(self):
        with self.assertRaises(ValueError):
            disj()

    def test_implies_se_neprepisuje(self):
        e = Implies(AtomRef(A_), AtomRef(B_))
        self.assertIsInstance(e, Implies)  # strukturu nese vysvětlení

    def test_from_literal(self):
        self.assertEqual(from_literal(Literal(A_)), AtomRef(A_))
        self.assertEqual(from_literal(Literal(A_, positive=False)),
                         Not(AtomRef(A_)))


class TestAtoms(unittest.TestCase):
    def test_deduplikovane_a_deterministicky_serazene(self):
        e = disj(AtomRef(B_), Not(AtomRef(A_)), AtomRef(B_))
        self.assertEqual(atoms(e), (A_, B_))  # p/1 < q/1 dle atom_key

    def test_const_nema_atomy(self):
        self.assertEqual(atoms(Const(True)), ())


class TestSubstitute(unittest.TestCase):
    def test_dosazeni_promenne(self):
        x = Variable("X")
        e = Implies(AtomRef(Atom(P, (x,))), AtomRef(Atom(Q, (x,))))
        g = substitute(e, {x: Entity("petr")})
        self.assertEqual(
            g, Implies(AtomRef(Atom(P, (Entity("petr"),))),
                       AtomRef(Atom(Q, (Entity("petr"),)))))

    def test_nenavazana_promenna_zustava(self):
        x, y = Variable("X"), Variable("Y")
        e = AtomRef(Atom(P, (x,)))
        self.assertEqual(substitute(e, {y: Entity("a")}), e)

    def test_substituce_nemutuje(self):
        x = Variable("X")
        e = AtomRef(Atom(P, (x,)))
        substitute(e, {x: Entity("a")})
        self.assertEqual(e, AtomRef(Atom(P, (x,))))


class TestToText(unittest.TestCase):
    def test_kanonicky_zapis(self):
        e = disj(conj(AtomRef(A_), AtomRef(B_)), Not(AtomRef(A_)))
        self.assertEqual(
            to_text(e),
            "((p(E:a) AND q(E:b)) OR (NOT p(E:a)))")

    def test_konstanty_a_ekvivalence(self):
        self.assertEqual(to_text(Const(True)), "TRUE")
        self.assertEqual(to_text(Equiv(AtomRef(A_), Const(False))),
                         "(p(E:a) EQUIV FALSE)")


if __name__ == "__main__":
    unittest.main()
