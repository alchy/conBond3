"""Testy vysvětlení — PROVENANCE.md § 2–3; zadání §35–§36, §39."""
import json
import unittest

from cb_logic.constraints import ExpressionConstraint
from cb_logic.expressions import AtomRef, Not, conj
from cb_logic.knowledge import KnowledgeBase, Rule
from cb_logic.models import ModalVerdict
from cb_logic.provenance import (Assertion, Evidence, EvidenceKind,
                                 LEVEL_DOCUMENTED)
from cb_logic.terms import Atom, Domain, Entity, Literal, Relation, Value, \
    Variable
from cb_logic.inference import infer_forward, with_assumptions
from cb_logic.explain import explain_conflict, why, why_not
from cb_logic.tests.test_models import DEF, mini_zebra
from cb_logic.tests.test_inference import (T1, defrule, make_kb, say,
                                           unary_rule)


class TestWhy(unittest.TestCase):
    def test_retez_da_strom_az_k_faktu(self):
        kb = make_kb(("a", "b", "c"))
        defrule(kb, unary_rule(kb, "a", "b"))
        defrule(kb, unary_rule(kb, "b", "c"))
        say(kb, "a")
        infer_forward(kb)
        explanations = why(kb, Literal(Atom(kb.relation("c"), (T1,))))
        self.assertEqual(len(explanations), 1)
        top = explanations[0]
        self.assertEqual((top.kind, top.rule_index), ("derived", 1))
        middle = top.premises[0]
        self.assertEqual((middle.kind, middle.rule_index), ("derived", 0))
        leaf = middle.premises[0]
        self.assertEqual(leaf.kind, "fact")
        self.assertEqual(leaf.evidence.kind, EvidenceKind.OBSERVATION)

    def test_predpoklad_nese_jmenovku(self):
        kb = make_kb(("a", "b"))
        defrule(kb, unary_rule(kb, "a", "b"))
        view = with_assumptions(kb,
                                (Literal(Atom(kb.relation("a"), (T1,))),))
        infer_forward(view)
        explanations = why(view, Literal(Atom(kb.relation("b"), (T1,))))
        self.assertEqual(explanations[0].assumptions, ("a(E:t1)",))
        leaf = explanations[0].premises[0]
        self.assertEqual(leaf.kind, "assumption")

    def test_bez_podpory_je_prazdno_a_json_serializace(self):
        kb = make_kb(("a",))
        self.assertEqual(why(kb, Literal(Atom(kb.relation("a"), (T1,)))), ())
        say(kb, "a")
        obj = why(kb, Literal(Atom(kb.relation("a"), (T1,))))[0]
        text = json.dumps(obj.to_json_object(), ensure_ascii=False)
        self.assertIn('"fact"', text)


class TestConflict(unittest.TestCase):
    def test_obe_strany_s_provenienci(self):
        kb = make_kb(("a",))
        atom = Atom(kb.relation("a"), (T1,))
        kb.assert_candidate(Assertion(
            Literal(atom), Evidence(EvidenceKind.OBSERVATION, source="korpus"),
            LEVEL_DOCUMENTED))
        kb.assert_candidate(Assertion(
            Literal(atom, positive=False),
            Evidence(EvidenceKind.USER_ASSERTION, source="dialog"),
            LEVEL_DOCUMENTED))
        explanations = explain_conflict(kb, atom)
        self.assertEqual(len(explanations), 2)
        self.assertEqual({e.evidence.source for e in explanations},
                         {"korpus", "dialog"})
        self.assertIsNone(explain_conflict(kb,
                                           Atom(kb.relation("a"),
                                                (Entity("jiny"),))))


class TestWhyNot(unittest.TestCase):
    def test_dolozene_ne(self):
        kb = make_kb(("a",))
        say(kb, "a", positive=False)
        result = why_not(kb, Literal(Atom(kb.relation("a"), (T1,))))
        self.assertEqual(result.kind, "documented_false")
        self.assertFalse(result.explanations[0].literal.positive)

    def test_modalne_nemozne(self):
        kb, hraje, anna, boris = mini_zebra()
        kb.assert_candidate(Assertion(
            Literal(Atom(hraje, (anna, Value("housle")))),
            Evidence(EvidenceKind.USER_ASSERTION), LEVEL_DOCUMENTED))
        result = why_not(kb,
                         Literal(Atom(hraje, (boris, Value("housle")))))
        self.assertEqual(result.kind, "impossible")
        self.assertEqual(result.modal.verdict, ModalVerdict.IMPOSSIBLE)

    def test_nevim_s_chybejicimi_premisami(self):
        """Co by to učinilo pravdou: NOT q(t1) — s polaritou z NNF."""
        kb = make_kb(("p", "q", "r"))
        x = Variable("X")
        kb.add_rule(Rule(((x, "things"),),
                         conj(AtomRef(Atom(kb.relation("p"), (x,))),
                              Not(AtomRef(Atom(kb.relation("q"), (x,))))),
                         Literal(Atom(kb.relation("r"), (x,)))), DEF)
        say(kb, "p")
        result = why_not(kb, Literal(Atom(kb.relation("r"), (T1,))))
        self.assertEqual(result.kind, "unknown")
        self.assertEqual(len(result.suggestions), 1)
        self.assertEqual(result.suggestions[0].missing,
                         (Literal(Atom(kb.relation("q"), (T1,)),
                                  positive=False),))


if __name__ == "__main__":
    unittest.main()
