"""Testy persistence — PROVENANCE.md § 5; zadání § 54."""
import unittest

from cb_logic.constraints import exactly_one
from cb_logic.terms import Atom, Entity, Literal, Value
from cb_logic.inference import infer_forward, retract
from cb_logic.serialize import (kb_from_json, kb_to_json, kb_to_json_text)
from cb_logic.tests.test_models import mini_zebra, DEF, USER
from cb_logic.tests.test_inference import T1, defrule, make_kb, say, \
    unary_rule
from cb_logic.provenance import Assertion, Evidence, EvidenceKind, \
    LEVEL_DOCUMENTED
from cb_logic.semantics import Truth


class TestRoundTrip(unittest.TestCase):
    def test_po_inferenci_vcetne_derivaci_a_konfliktu(self):
        kb = make_kb(("a", "b", "c"))
        defrule(kb, unary_rule(kb, "a", "b"))
        defrule(kb, unary_rule(kb, "b", "c"))
        say(kb, "a")
        say(kb, "c", positive=False)  # vyvolá konflikt s odvozeným c
        infer_forward(kb)
        restored = kb_from_json(kb_to_json(kb))
        self.assertEqual(kb_to_json(restored), kb_to_json(kb))
        for rel in "abc":
            atom = Atom(kb.relation(rel), (T1,))
            self.assertEqual(restored.truth_of(atom), kb.truth_of(atom))
        self.assertEqual(len(restored.conflicts), len(kb.conflicts))
        self.assertEqual(restored.derivations, kb.derivations)

    def test_po_retractu(self):
        kb = make_kb(("a", "b"))
        defrule(kb, unary_rule(kb, "a", "b"))
        say(kb, "a")
        infer_forward(kb)
        retract(kb, Literal(Atom(kb.relation("a"), (T1,))))
        restored = kb_from_json(kb_to_json(kb))
        self.assertEqual(kb_to_json(restored), kb_to_json(kb))
        self.assertEqual(restored.truth_of(Atom(kb.relation("b"), (T1,))),
                         Truth.UNKNOWN)

    def test_zebra_s_constrainty(self):
        kb, hraje, anna, boris = mini_zebra()
        kb.assert_candidate(Assertion(
            Literal(Atom(hraje, (anna, Value("viola"))), positive=False),
            USER, LEVEL_DOCUMENTED))
        restored = kb_from_json(kb_to_json(kb))
        self.assertEqual(kb_to_json(restored), kb_to_json(kb))
        self.assertEqual(len(restored.constraints), 4)


class TestDeterminismAndErrors(unittest.TestCase):
    def test_dva_zapisy_jsou_textove_shodne(self):
        kb1, *_ = mini_zebra()
        kb2, *_ = mini_zebra()
        self.assertEqual(kb_to_json_text(kb1), kb_to_json_text(kb2))

    def test_cizi_verze_je_hlasita_chyba(self):
        kb = make_kb(("a",))
        data = kb_to_json(kb)
        data["format_version"] = 99
        with self.assertRaises(ValueError):
            kb_from_json(data)

    def test_nejson_hodnota_je_hlasita_chyba(self):
        kb = make_kb(("a",))
        kb.declare_domain(__import__("cb_logic").Domain(
            "divna", (Value(object()),)))
        with self.assertRaises(ValueError):
            kb_to_json(kb)


if __name__ == "__main__":
    unittest.main()
