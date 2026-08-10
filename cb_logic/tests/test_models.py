"""Testy prostoru modelů — MODEL_REASONING.md § 1–2; zadání §25–§26, §29, §44."""
import unittest

from cb_logic.constraints import atom_family, exactly_one
from cb_logic.expressions import AtomRef, Not
from cb_logic.constraints import ExpressionConstraint
from cb_logic.knowledge import KnowledgeBase, Rule
from cb_logic.provenance import (Assertion, Evidence, EvidenceKind,
                                 LEVEL_DEFINITION, LEVEL_DOCUMENTED,
                                 Provenance)
from cb_logic.semantics import Truth
from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Value,
                            Variable)
from cb_logic.models import (AtomClassification, ModelLimits, SearchStatus,
                             classify_atoms, enumerate_models, model_scope)

OBS = Evidence(EvidenceKind.OBSERVATION)
USER = Evidence(EvidenceKind.USER_ASSERTION)
DEF = Provenance(LEVEL_DEFINITION, USER)


def mini_zebra():
    """2 osoby × 2 nástroje, 'právě jeden' oběma směry — zapsáno DATY."""
    kb = KnowledgeBase()
    hraje = Relation("hraje", 2)
    kb.declare_relation(hraje)
    anna, boris = Entity("anna"), Entity("boris")
    kb.declare_domain(Domain("osoby", (anna, boris)))
    kb.declare_domain(Domain("nastroje", (Value("housle"), Value("viola"))))
    for person in (anna, boris):
        kb.add_constraint(exactly_one(
            atom_family(hraje, (person, None), kb.domain("nastroje"))), DEF)
    for instrument in (Value("housle"), Value("viola")):
        kb.add_constraint(exactly_one(
            atom_family(hraje, (None, instrument), kb.domain("osoby"))), DEF)
    return kb, hraje, anna, boris


class TestMiniZebra(unittest.TestCase):
    def test_bez_faktu_dva_modely(self):
        kb, *_ = mini_zebra()
        result = enumerate_models(kb)
        self.assertEqual(result.status, SearchStatus.COMPLETE)
        self.assertEqual(len(result.models), 2)

    def test_zapor_zuzi_na_jedno_reseni_a_klasifikuje(self):
        kb, hraje, anna, boris = mini_zebra()
        kb.assert_candidate(Assertion(
            Literal(Atom(hraje, (anna, Value("viola"))), positive=False),
            USER, LEVEL_DOCUMENTED))
        result = enumerate_models(kb)
        self.assertEqual(len(result.models), 1)
        cls = classify_atoms(result)
        self.assertIn(Atom(hraje, (anna, Value("housle"))), cls.necessary)
        self.assertIn(Atom(hraje, (boris, Value("viola"))), cls.necessary)
        self.assertIn(Atom(hraje, (boris, Value("housle"))), cls.impossible)
        self.assertEqual(cls.possible, ())


class TestRulesInModels(unittest.TestCase):
    def test_pravidlo_je_implikace_ve_vsech_modelech(self):
        kb = KnowledgeBase()
        for name in ("p", "q"):
            kb.declare_relation(Relation(name, 1))
        t1 = Entity("t1")
        kb.declare_domain(Domain("things", (t1,)))
        x = Variable("X")
        kb.add_rule(Rule(((x, "things"),),
                         AtomRef(Atom(kb.relation("p"), (x,))),
                         Literal(Atom(kb.relation("q"), (x,)))), DEF)
        kb.assert_candidate(Assertion(
            Literal(Atom(kb.relation("p"), (t1,))), OBS, LEVEL_DOCUMENTED))
        result = enumerate_models(kb,
                                  seed_atoms=(Atom(kb.relation("q"), (t1,)),))
        cls = classify_atoms(result)
        self.assertIn(Atom(kb.relation("q"), (t1,)), cls.necessary)
        self.assertIn(Atom(kb.relation("p"), (t1,)), cls.necessary)  # pinned

    def test_irelevantni_pravidlo_se_do_scope_nedostane(self):
        kb = KnowledgeBase()
        for name in ("p", "x", "y"):
            kb.declare_relation(Relation(name, 1))
        t1 = Entity("t1")
        kb.declare_domain(Domain("things", (t1,)))
        v = Variable("X")
        kb.add_rule(Rule(((v, "things"),),
                         AtomRef(Atom(kb.relation("x"), (v,))),
                         Literal(Atom(kb.relation("y"), (v,)))), DEF)
        seed = Atom(kb.relation("p"), (t1,))
        scope = model_scope(kb, (seed,))
        self.assertEqual(scope.atoms, (seed,))
        self.assertEqual(scope.instances, ())


class TestEdges(unittest.TestCase):
    def test_nesplnitelna_baze_da_nula_modelu_complete(self):
        kb = KnowledgeBase()
        kb.declare_relation(Relation("p", 1))
        t1 = Entity("t1")
        kb.declare_domain(Domain("things", (t1,)))
        atom = Atom(kb.relation("p"), (t1,))
        kb.assert_candidate(Assertion(Literal(atom), OBS, LEVEL_DOCUMENTED))
        kb.add_constraint(ExpressionConstraint(Not(AtomRef(atom)),
                                               label="zakaz"), DEF)
        result = enumerate_models(kb)
        self.assertEqual(result.status, SearchStatus.COMPLETE)
        self.assertEqual(result.models, ())
        self.assertEqual(result.eliminated, (("zakaz", 1),))

    def test_limit_uzlu_je_incomplete(self):
        kb, *_ = mini_zebra()
        result = enumerate_models(kb, limits=ModelLimits(max_nodes=1))
        self.assertEqual(result.status, SearchStatus.INCOMPLETE)

    def test_konfliktni_atom_neni_pinovany_a_hlasi_se(self):
        kb = KnowledgeBase()
        kb.declare_relation(Relation("p", 1))
        t1 = Entity("t1")
        kb.declare_domain(Domain("things", (t1,)))
        atom = Atom(kb.relation("p"), (t1,))
        kb.assert_candidate(Assertion(Literal(atom), OBS, LEVEL_DOCUMENTED))
        kb.assert_candidate(Assertion(Literal(atom, positive=False), USER,
                                      LEVEL_DOCUMENTED))
        result = enumerate_models(kb, seed_atoms=(atom,))
        self.assertEqual(result.conflicted, (atom,))
        self.assertEqual(len(result.models), 2)  # obě možnosti se prozkoumají

    def test_documented_truth_ignoruje_odvozene(self):
        kb = KnowledgeBase()
        kb.declare_relation(Relation("p", 1))
        t1 = Entity("t1")
        kb.declare_domain(Domain("things", (t1,)))
        atom = Atom(kb.relation("p"), (t1,))
        self.assertEqual(kb.documented_truth(atom), Truth.UNKNOWN)
        kb.assert_candidate(Assertion(Literal(atom), OBS, LEVEL_DOCUMENTED))
        self.assertEqual(kb.documented_truth(atom), Truth.TRUE)


if __name__ == "__main__":
    unittest.main()
