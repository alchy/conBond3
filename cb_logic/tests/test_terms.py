"""Testy datového modelu termů — KNOWLEDGE_MODEL.md § 2–3."""
import unittest

from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Value,
                            Variable, atom_key, is_ground, term_key)


class TestEntity(unittest.TestCase):
    def test_rovnost_jen_podle_id(self):
        self.assertEqual(Entity("petr", label="Petr N."), Entity("petr"))
        self.assertNotEqual(Entity("petr"), Entity("pavel"))

    def test_hash_konzistentni_s_rovnosti(self):
        self.assertEqual(len({Entity("petr", label="A"), Entity("petr", label="B")}), 1)


class TestTermKey(unittest.TestCase):
    def test_klice_jsou_stabilni_a_ruzne_druhy_nekoliduji(self):
        self.assertEqual(term_key(Entity("petr")), "E:petr")
        self.assertEqual(term_key(Variable("X")), "?:X")
        self.assertNotEqual(term_key(Value("petr")), term_key(Entity("petr")))

    def test_hodnoty_ruznych_typu_nekoliduji(self):
        self.assertNotEqual(term_key(Value(1)), term_key(Value("1")))


class TestGround(unittest.TestCase):
    def test_promenna_neni_ground(self):
        self.assertTrue(is_ground(Entity("e")))
        self.assertTrue(is_ground(Value(3)))
        self.assertFalse(is_ground(Variable("X")))


class TestDomain(unittest.TestCase):
    def test_clen_s_promennou_je_hlasita_chyba(self):
        with self.assertRaises(ValueError):
            Domain("osoby", (Entity("a"), Variable("X")))


class TestRelation(unittest.TestCase):
    def test_arita_pod_jedna_je_chyba(self):
        with self.assertRaises(ValueError):
            Relation("nic", 0)


class TestAtom(unittest.TestCase):
    def setUp(self):
        self.programmer = Relation("programmer", 1)
        self.lives = Relation("lives_in", 2)

    def test_spatna_arita_je_hlasita_chyba(self):
        with self.assertRaises(ValueError):
            Atom(self.programmer, (Entity("a"), Entity("b")))

    def test_ground_a_klic(self):
        a = Atom(self.lives, (Entity("petr"), Value("Praha")))
        self.assertTrue(a.ground)
        self.assertFalse(Atom(self.programmer, (Variable("X"),)).ground)
        self.assertEqual(atom_key(a), "lives_in/2(E:petr,V:str:'Praha')")

    def test_atom_je_hashovatelny(self):
        a = Atom(self.programmer, (Entity("petr"),))
        self.assertEqual(len({a, Atom(self.programmer, (Entity("petr"),))}), 1)


class TestLiteral(unittest.TestCase):
    def test_negace_obraci_polaritu_a_je_involuce(self):
        lit = Literal(Atom(Relation("p", 1), (Entity("a"),)))
        self.assertTrue(lit.positive)
        self.assertFalse(lit.negated().positive)
        self.assertEqual(lit.negated().negated(), lit)


if __name__ == "__main__":
    unittest.main()
