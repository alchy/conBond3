"""Testy KnowledgeBase — INFERENCE_ENGINE.md § 1, mřížka provenience."""
import unittest

from cb_logic.expressions import AtomRef
from cb_logic.provenance import (Assertion, Evidence, EvidenceKind,
                                 LEVEL_CORRECTION, LEVEL_DEFINITION,
                                 LEVEL_DOCUMENTED, LEVEL_HYPOTHESIS,
                                 Provenance)
from cb_logic.semantics import Truth
from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Variable)
from cb_logic.knowledge import (Accepted, Conflicted, KnowledgeBase, Rejected,
                                Rule)

P = Relation("p", 1)
E1 = Entity("e1")
PA = Atom(P, (E1,))
OBS = Evidence(EvidenceKind.OBSERVATION)
USER = Evidence(EvidenceKind.USER_ASSERTION)


def make_kb():
    kb = KnowledgeBase()
    kb.declare_relation(P)
    kb.declare_domain(Domain("things", (E1,)))
    return kb


def say(kb, literal, level=LEVEL_DOCUMENTED, evidence=OBS):
    return kb.assert_candidate(Assertion(literal, evidence, level))


class TestDeclarations(unittest.TestCase):
    def test_dvoji_deklarace_jinak_je_chyba(self):
        kb = make_kb()
        kb.declare_relation(P)  # stejná znovu je OK
        with self.assertRaises(ValueError):
            kb.declare_relation(Relation("p", 2))

    def test_neznama_relace_a_domena_jsou_keyerror(self):
        kb = make_kb()
        with self.assertRaises(KeyError):
            kb.relation("neni")
        with self.assertRaises(KeyError):
            kb.domain("neni")


class TestAssert(unittest.TestCase):
    def test_nedeklarovana_relace_je_rejected(self):
        kb = make_kb()
        r = say(kb, Literal(Atom(Relation("q", 1), (E1,))))
        self.assertIsInstance(r, Rejected)

    def test_neground_literal_je_rejected(self):
        kb = make_kb()
        r = say(kb, Literal(Atom(P, (Variable("X"),))))
        self.assertIsInstance(r, Rejected)

    def test_cteni_true_false_unknown(self):
        kb = make_kb()
        self.assertEqual(kb.truth_of(PA), Truth.UNKNOWN)
        self.assertIsInstance(say(kb, Literal(PA)), Accepted)
        self.assertEqual(kb.truth_of(PA), Truth.TRUE)
        kb2 = make_kb()
        say(kb2, Literal(PA, positive=False))
        self.assertEqual(kb2.truth_of(PA), Truth.FALSE)

    def test_hypoteza_nedava_cteni(self):
        kb = make_kb()
        say(kb, Literal(PA), level=LEVEL_HYPOTHESIS,
            evidence=Evidence(EvidenceKind.HYPOTHESIS))
        self.assertEqual(kb.truth_of(PA), Truth.UNKNOWN)


class TestMrizka(unittest.TestCase):
    def test_oprava_prebiji_dolozene_obe_strany_zustavaji(self):
        kb = make_kb()
        say(kb, Literal(PA), level=LEVEL_DOCUMENTED)
        r = say(kb, Literal(PA, positive=False), level=LEVEL_CORRECTION,
                evidence=USER)
        self.assertIsInstance(r, Accepted)
        self.assertEqual(kb.truth_of(PA), Truth.FALSE)   # oprava vítězí
        self.assertTrue(kb.is_conflicted(PA))            # ale spor je vidět
        self.assertEqual(len(kb.conflicts), 1)
        self.assertEqual(kb.conflicts[0].positive.level, LEVEL_DOCUMENTED)

    def test_taz_uroven_je_conflicted_a_karantena(self):
        kb = make_kb()
        say(kb, Literal(PA), level=LEVEL_DOCUMENTED)
        r = say(kb, Literal(PA, positive=False), level=LEVEL_DOCUMENTED,
                evidence=USER)
        self.assertIsInstance(r, Conflicted)
        self.assertEqual(kb.truth_of(PA), Truth.UNKNOWN)
        self.assertTrue(kb.is_conflicted(PA))


class TestRules(unittest.TestCase):
    def test_promenna_bez_domeny_je_chyba(self):
        kb = make_kb()
        x, y = Variable("X"), Variable("Y")
        rule = Rule(((x, "things"),), AtomRef(Atom(P, (x,))),
                    Literal(Atom(P, (y,))))
        with self.assertRaises(ValueError):
            kb.add_rule(rule, Provenance(LEVEL_DEFINITION, USER))

    def test_nedeklarovana_domena_je_chyba(self):
        kb = make_kb()
        x = Variable("X")
        rule = Rule(((x, "neni"),), AtomRef(Atom(P, (x,))),
                    Literal(Atom(P, (x,))))
        with self.assertRaises(ValueError):
            kb.add_rule(rule, Provenance(LEVEL_DEFINITION, USER))


class TestExtendDomain(unittest.TestCase):
    def test_rust_je_append_only(self):
        kb = make_kb()
        kb.extend_domain("things", (Entity("e2"),))
        self.assertEqual(kb.domain("things").members,
                         (E1, Entity("e2")))
        kb.extend_domain("things", (E1,))  # duplicitní člen se nepřidá
        self.assertEqual(len(kb.domain("things").members), 2)

    def test_zalozi_novou_domenu(self):
        kb = make_kb()
        kb.extend_domain("nova", (Entity("x"),))
        self.assertEqual(kb.domain("nova").members, (Entity("x"),))


class TestCopy(unittest.TestCase):
    def test_kopie_je_nezavisla(self):
        kb = make_kb()
        say(kb, Literal(PA))
        clone = kb.copy()
        say(clone, Literal(PA, positive=False), level=LEVEL_CORRECTION,
            evidence=USER)
        self.assertEqual(kb.truth_of(PA), Truth.TRUE)
        self.assertEqual(clone.truth_of(PA), Truth.FALSE)
        self.assertFalse(kb.is_conflicted(PA))


if __name__ == "__main__":
    unittest.main()
