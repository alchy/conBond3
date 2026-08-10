"""Testy datové vrstvy učených vzorů — LANGUAGE_LEARNING.md."""
import unittest

from cb_interpret.patterns import (LearnedPattern, Operation, PatternStatus,
                                   PatternStore, StructuralSignature, Trigger)


class TestTrigger(unittest.TestCase):
    def test_sedi_na_lemma_a_xcomp_ne_na_vetu(self):
        trigger = Trigger("moci", requires_xcomp=True)
        self.assertTrue(trigger.matches(
            StructuralSignature("moci", has_xcomp=True)))
        self.assertFalse(trigger.matches(
            StructuralSignature("moci", has_xcomp=False)))
        self.assertFalse(trigger.matches(
            StructuralSignature("muset", has_xcomp=True)))


class TestStore(unittest.TestCase):
    def test_teach_je_hypoteza_a_matchuje(self):
        store = PatternStore()
        sig = StructuralSignature("moci", has_xcomp=True)
        pattern = store.teach(sig, Operation.POSSIBLE,
                              learned_from="Auto může jet.")
        self.assertEqual(pattern.status, PatternStatus.HYPOTHESIS)
        matched = store.match(StructuralSignature("moci", has_xcomp=True))
        self.assertEqual(matched.operation, Operation.POSSIBLE)

    def test_confirm_a_revoke(self):
        store = PatternStore()
        store.teach(StructuralSignature("moci", has_xcomp=True),
                    Operation.POSSIBLE, learned_from="…")
        self.assertEqual(store.confirm("moci").status,
                         PatternStatus.CONFIRMED)
        self.assertIsNotNone(store.match(
            StructuralSignature("moci", has_xcomp=True)))
        store.revoke("moci")
        # odvolaný vzor se přestane používat — operace v jádru tím nemizí
        self.assertIsNone(store.match(
            StructuralSignature("moci", has_xcomp=True)))

    def test_json_roundtrip(self):
        store = PatternStore()
        store.teach(StructuralSignature("moci", has_xcomp=True),
                    Operation.POSSIBLE, learned_from="Auto může jet.",
                    learned_at="2026-08-10")
        restored = PatternStore.from_json(store.to_json())
        self.assertEqual(restored.to_json(), store.to_json())
        pattern = restored.match(StructuralSignature("moci", has_xcomp=True))
        self.assertEqual(pattern.operation, Operation.POSSIBLE)
        self.assertEqual(pattern.learned_at, "2026-08-10")


if __name__ == "__main__":
    unittest.main()
