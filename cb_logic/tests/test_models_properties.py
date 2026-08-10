"""Property testy modelů — plná 2^n reference, cross-layer shoda, metamorfika."""
import itertools
import random
import unittest

from cb_logic.constraints import (CardinalityConstraint, ExpressionConstraint,
                                  atom_family, satisfied_by)
from cb_logic.knowledge import KnowledgeBase
from cb_logic.semantics import Truth
from cb_logic.terms import (Atom, Domain, Entity, Relation, Value, atom_key)
from cb_logic.inference import infer_forward
from cb_logic.models import (SearchStatus, classify_atoms, enumerate_models)
from cb_logic.serialize import kb_from_json, kb_to_json
from cb_logic.tests.generators import random_expression
from cb_logic.tests.kb_generators import (build_kb, random_spec, readings)
from cb_logic.tests.test_models import DEF

SEED = 328
SAMPLES = 30


def random_constraint_kb(rng):
    """Náhodný constraint problém nad jednou rodinou atomů (bez pravidel)."""
    kb = KnowledgeBase()
    has = Relation("has", 2)
    kb.declare_relation(has)
    person = Entity("e")
    n = rng.randint(3, 6)
    values = tuple(Value(f"v{i}") for i in range(n))
    kb.declare_domain(Domain("osoby", (person,)))
    kb.declare_domain(Domain("vals", values))
    family = atom_family(has, (person, None), kb.domain("vals"))
    for _ in range(rng.randint(1, 2)):
        size = rng.randint(2, n)
        sub = tuple(sorted(rng.sample(family, size), key=atom_key))
        at_least = rng.randint(0, size)
        at_most = rng.choice((None, rng.randint(at_least, size)))
        kb.add_constraint(CardinalityConstraint(sub, at_least, at_most), DEF)
    for _ in range(rng.randint(1, 2)):
        kb.add_constraint(
            ExpressionConstraint(random_expression(rng, family, 3)), DEF)
    return kb


def reference_models(kb, scope_atoms):
    """Plná 2^n enumerace — pomalá, zjevně správná (orákulum)."""
    out = set()
    for values in itertools.product((False, True), repeat=len(scope_atoms)):
        env = dict(zip(scope_atoms, values))
        if all(satisfied_by(c, env) for c, _ in kb.constraints):
            out.add(tuple(sorted(env.items(),
                                 key=lambda kv: atom_key(kv[0]))))
    return out


class TestReferenceAgreement(unittest.TestCase):
    def test_enumerace_se_shoduje_s_plnou_tabulkou(self):
        rng = random.Random(SEED)
        unsat = 0
        multi = 0
        for _ in range(SAMPLES):
            kb = random_constraint_kb(rng)
            result = enumerate_models(kb)
            self.assertEqual(result.status, SearchStatus.COMPLETE)
            expected = reference_models(kb, result.scope)
            self.assertEqual(set(result.models), expected)
            if not expected:
                unsat += 1
            if len(expected) > 1:
                multi += 1
        self.assertGreater(unsat, 0)   # T-13: vzorek měl i nesplnitelné
        self.assertGreater(multi, 0)   # ... i vícemodelové


class TestCrossLayer(unittest.TestCase):
    def test_k3_true_znamena_necessary(self):
        """Fixpoint (fáze 5) a modely (fáze 6) si nesmějí odporovat."""
        rng = random.Random(SEED)
        checked = 0
        for _ in range(10):
            spec = random_spec(rng, entities=3, relations=3, facts=4,
                               rules=3, negation_free=True)
            kb = build_kb(spec)
            infer_forward(kb)
            universe = tuple(
                Atom(kb.relation(rel), (Entity(ent),))
                for rel in spec.relation_names
                for ent in spec.entity_names)
            result = enumerate_models(kb, seed_atoms=universe)
            if result.status is not SearchStatus.COMPLETE:
                continue
            cls = classify_atoms(result)
            for atom in universe:
                if kb.truth_of(atom) is Truth.TRUE:
                    checked += 1
                    self.assertIn(atom, cls.necessary, msg=str(atom))
        self.assertGreater(checked, 10)  # T-13


class TestMetamorphicAndSerialize(unittest.TestCase):
    def test_prejmenovani_zachova_pocet_modelu(self):
        from cb_logic.tests.kb_generators import rename_spec
        rng = random.Random(SEED)
        for i in range(10):
            spec = random_spec(rng, entities=3, relations=3, facts=4, rules=3)
            renamed = rename_spec(
                spec,
                {n: f"ent_{i}_{j}" for j, n in enumerate(spec.entity_names)},
                {n: f"rel_{i}_{j}"
                 for j, n in enumerate(spec.relation_names)})
            r1 = enumerate_models(build_kb(spec))
            r2 = enumerate_models(build_kb(renamed))
            self.assertEqual(len(r1.models), len(r2.models))
            self.assertEqual(r1.status, r2.status)

    def test_serializace_nahodnych_bazi_po_inferenci(self):
        rng = random.Random(SEED)
        for _ in range(10):
            kb = build_kb(random_spec(rng))
            infer_forward(kb)
            restored = kb_from_json(kb_to_json(kb))
            self.assertEqual(kb_to_json(restored), kb_to_json(kb))

    def test_permutace_constraintu_nemeni_mnozinu_modelu(self):
        rng = random.Random(SEED)
        for _ in range(10):
            kb = random_constraint_kb(rng)
            data = kb_to_json(kb)
            order = list(range(len(data["constraints"])))
            rng.shuffle(order)
            data["constraints"] = [data["constraints"][i] for i in order]
            shuffled = kb_from_json(data)
            self.assertEqual(set(enumerate_models(kb).models),
                             set(enumerate_models(shuffled).models))


if __name__ == "__main__":
    unittest.main()
