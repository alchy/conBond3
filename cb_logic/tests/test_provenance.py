"""Testy provenience — KNOWLEDGE_MODEL.md § 7, § 10."""
import unittest

from cb_logic.terms import Atom, Entity, Literal, Relation
from cb_logic.provenance import (Assertion, Conflict, Derivation, Evidence,
                                 EvidenceKind, LEVEL_CORRECTION,
                                 LEVEL_DERIVED, LEVEL_DOCUMENTED,
                                 LEVEL_HYPOTHESIS, Provenance)

LIT = Literal(Atom(Relation("p", 1), (Entity("a"),)))


class TestEvidence(unittest.TestCase):
    def test_confidence_mimo_rozsah_je_chyba(self):
        with self.assertRaises(ValueError):
            Evidence(EvidenceKind.OBSERVATION, confidence=1.5)
        with self.assertRaises(ValueError):
            Evidence(EvidenceKind.OBSERVATION, confidence=-0.1)

    def test_confidence_je_metadata(self):
        e = Evidence(EvidenceKind.OBSERVATION, source="korpus", confidence=0.9)
        self.assertEqual(e.kind, EvidenceKind.OBSERVATION)


class TestProvenance(unittest.TestCase):
    def test_uroven_mimo_mrizku_je_chyba(self):
        with self.assertRaises(ValueError):
            Provenance(5, Evidence(EvidenceKind.OBSERVATION))
        with self.assertRaises(ValueError):
            Provenance(-1, Evidence(EvidenceKind.OBSERVATION))

    def test_derived_vyzaduje_derivaci(self):
        with self.assertRaises(ValueError):
            Provenance(LEVEL_DERIVED, Evidence(EvidenceKind.DERIVED))
        p = Provenance(LEVEL_DERIVED, Evidence(EvidenceKind.DERIVED),
                       derivation_id=0)
        self.assertEqual(p.derivation_id, 0)

    def test_urovne_jsou_usporadane(self):
        self.assertLess(LEVEL_HYPOTHESIS, LEVEL_DERIVED)
        self.assertLess(LEVEL_DERIVED, LEVEL_DOCUMENTED)
        self.assertLess(LEVEL_DOCUMENTED, LEVEL_CORRECTION)


class TestDerivationConflict(unittest.TestCase):
    def test_derivace_je_hodnota(self):
        d1 = Derivation(0, LIT, (LIT,), 1, frozenset())
        d2 = Derivation(0, LIT, (LIT,), 1, frozenset())
        self.assertEqual(d1, d2)

    def test_konflikt_nese_obe_strany(self):
        pos = Provenance(LEVEL_DOCUMENTED, Evidence(EvidenceKind.OBSERVATION))
        neg = Provenance(LEVEL_DOCUMENTED, Evidence(EvidenceKind.USER_ASSERTION))
        c = Conflict(LIT.atom, pos, neg)
        self.assertEqual((c.positive, c.negative), (pos, neg))

    def test_assertion_je_kandidat(self):
        a = Assertion(LIT, Evidence(EvidenceKind.USER_ASSERTION),
                      LEVEL_DOCUMENTED)
        self.assertEqual(a.literal, LIT)


if __name__ == "__main__":
    unittest.main()
