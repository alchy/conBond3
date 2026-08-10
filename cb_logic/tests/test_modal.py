"""Testy modálních dotazů a meta-dotazů — MODEL_REASONING.md § 3–4; zadání §26–§27, §30–§31."""
import unittest

from cb_logic.constraints import ExpressionConstraint, requires
from cb_logic.expressions import AtomRef, Not
from cb_logic.knowledge import KnowledgeBase
from cb_logic.provenance import (Assertion, Evidence, EvidenceKind,
                                 LEVEL_DEFINITION, LEVEL_DOCUMENTED,
                                 Provenance)
from cb_logic.semantics import Decision
from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Value)
from cb_logic.models import (ModalVerdict, classify_query, is_redundant,
                             uniqueness_critical, violations,
                             enumerate_models)
from cb_logic.tests.test_models import USER, OBS, DEF, mini_zebra


class TestModal(unittest.TestCase):
    def test_possible_s_protiprikladem(self):
        """„Vyplývá, že Boris hraje na housle?" — ne: existuje protipříklad."""
        kb, hraje, anna, boris = mini_zebra()
        expr = AtomRef(Atom(hraje, (boris, Value("housle"))))
        result = classify_query(kb, expr)
        self.assertEqual(result.verdict, ModalVerdict.POSSIBLE)
        self.assertIsNotNone(result.witness)
        self.assertIsNotNone(result.counterexample)
        # protipříklad je konzistentní model, kde Boris housle NEHRAJE
        env = dict(result.counterexample)
        self.assertFalse(env[Atom(hraje, (boris, Value("housle")))])

    def test_necessary_po_zuzeni(self):
        kb, hraje, anna, boris = mini_zebra()
        kb.assert_candidate(Assertion(
            Literal(Atom(hraje, (anna, Value("housle"))), positive=False),
            USER, LEVEL_DOCUMENTED))
        result = classify_query(kb, AtomRef(Atom(hraje,
                                                 (boris, Value("housle")))))
        self.assertEqual(result.verdict, ModalVerdict.NECESSARY)
        self.assertIsNone(result.counterexample)

    def test_impossible(self):
        kb, hraje, anna, boris = mini_zebra()
        kb.assert_candidate(Assertion(
            Literal(Atom(hraje, (anna, Value("housle")))), USER,
            LEVEL_DOCUMENTED))
        result = classify_query(kb, AtomRef(Atom(hraje,
                                                 (boris, Value("housle")))))
        self.assertEqual(result.verdict, ModalVerdict.IMPOSSIBLE)

    def test_unsatisfiable_se_hlasi_zvlast(self):
        kb = KnowledgeBase()
        kb.declare_relation(Relation("p", 1))
        t1 = Entity("t1")
        kb.declare_domain(Domain("things", (t1,)))
        atom = Atom(kb.relation("p"), (t1,))
        kb.assert_candidate(Assertion(Literal(atom), OBS, LEVEL_DOCUMENTED))
        kb.add_constraint(ExpressionConstraint(Not(AtomRef(atom))), DEF)
        result = classify_query(kb, AtomRef(atom))
        self.assertEqual(result.verdict, ModalVerdict.UNSATISFIABLE)


class TestMeta(unittest.TestCase):
    def _abc_kb(self):
        kb = KnowledgeBase()
        for name in ("a", "b", "c"):
            kb.declare_relation(Relation(name, 1))
        t1 = Entity("t1")
        kb.declare_domain(Domain("things", (t1,)))
        atoms = {name: Atom(kb.relation(name), (t1,)) for name in "abc"}
        kb.add_constraint(requires(AtomRef(atoms["a"]), AtomRef(atoms["b"]),
                                   label="a->b"), DEF)
        kb.add_constraint(requires(AtomRef(atoms["b"]), AtomRef(atoms["c"]),
                                   label="b->c"), DEF)
        kb.add_constraint(requires(AtomRef(atoms["a"]), AtomRef(atoms["c"]),
                                   label="a->c"), DEF)
        return kb, atoms

    def test_redundance_zadani_31(self):
        """a→b, b→c, a→c: třetí je logicky redundantní, první dvě ne."""
        kb, _ = self._abc_kb()
        self.assertEqual(is_redundant(kb, 2), Decision.YES)
        self.assertEqual(is_redundant(kb, 0), Decision.NO)
        self.assertEqual(is_redundant(kb, 1), Decision.NO)

    def test_violations_vraci_porusene_popisky(self):
        kb, atoms = self._abc_kb()
        model = ((atoms["a"], True), (atoms["b"], False), (atoms["c"], True))
        self.assertEqual(violations(kb, model), ("a->b",))

    def test_uniqueness_critical(self):
        """Mini zebra + zápor = 1 řešení; zápor rozhoduje, kardinality taky."""
        kb, hraje, anna, boris = mini_zebra()
        kb.add_constraint(ExpressionConstraint(
            Not(AtomRef(Atom(hraje, (anna, Value("viola"))))),
            label="anna_ne_viola"), DEF)
        result = enumerate_models(kb)
        self.assertEqual(len(result.models), 1)
        critical = uniqueness_critical(kb)
        self.assertIn(4, critical)  # bez záporu jsou modely 2


if __name__ == "__main__":
    unittest.main()
