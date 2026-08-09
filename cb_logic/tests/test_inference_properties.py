"""Property a metamorfní testy inference — INFERENCE_ENGINE § 9; zadání §40–§44."""
import random
import unittest

from cb_logic.semantics import Truth
from cb_logic.inference import infer_forward
from cb_logic.tests.kb_generators import (SAMPLES, SEED, add_noise, build_kb,
                                          naive_forward_readings,
                                          permute_spec, random_spec, readings,
                                          rename_spec)


class TestOracleAgreement(unittest.TestCase):
    def test_produkce_se_shoduje_s_naivnim_orakulem(self):
        rng = random.Random(SEED)
        derived_somewhere = 0
        for _ in range(SAMPLES):
            spec = random_spec(rng)
            production = build_kb(spec)
            result = infer_forward(production)
            if result.new_facts:
                derived_somewhere += 1
            oracle = naive_forward_readings(build_kb(spec), spec)
            self.assertEqual(readings(production, spec), oracle)
        self.assertGreater(derived_somewhere, SAMPLES // 3)  # T-13


class TestMonotonicity(unittest.TestCase):
    def test_pridani_faktu_neubere_odvozene_bez_negace(self):
        rng = random.Random(SEED)
        checked = 0
        for _ in range(SAMPLES):
            spec = random_spec(rng, negation_free=True)
            kb1 = build_kb(spec)
            infer_forward(kb1)
            before = readings(kb1, spec)
            extra_spec = random_spec(rng, entities=len(spec.entity_names),
                                     relations=len(spec.relation_names),
                                     facts=1, rules=0, negation_free=True)
            spec2 = type(spec)(spec.entity_names, spec.relation_names,
                               spec.facts + extra_spec.facts, spec.rules)
            kb2 = build_kb(spec2)
            infer_forward(kb2)
            after = readings(kb2, spec2)
            for key, value in before.items():
                if value is Truth.TRUE:
                    checked += 1
                    self.assertEqual(after[key], Truth.TRUE, msg=str(key))
        self.assertGreater(checked, 50)  # T-13


class TestIdempotence(unittest.TestCase):
    def test_druhy_beh_nic_neprida(self):
        rng = random.Random(SEED)
        for _ in range(SAMPLES // 2):
            kb = build_kb(random_spec(rng))
            infer_forward(kb)
            second = infer_forward(kb)
            self.assertEqual(second.derivations_added, 0)
            self.assertEqual(second.new_facts, ())


class TestMetamorphic(unittest.TestCase):
    def test_prejmenovani_zachova_strukturu(self):
        """Zadání § 43: entity_17/relation_82 — výsledek izomorfní."""
        rng = random.Random(SEED)
        for i in range(SAMPLES // 2):
            spec = random_spec(rng)
            entity_map = {n: f"entity_{i}_{j}"
                          for j, n in enumerate(spec.entity_names)}
            relation_map = {n: f"relation_{i}_{j}"
                            for j, n in enumerate(spec.relation_names)}
            renamed = rename_spec(spec, entity_map, relation_map)
            kb1 = build_kb(spec)
            kb2 = build_kb(renamed)
            infer_forward(kb1)
            infer_forward(kb2)
            r1 = readings(kb1, spec)
            r2 = readings(kb2, renamed)
            for (rel, ent), value in r1.items():
                self.assertEqual(r2[(relation_map[rel], entity_map[ent])],
                                 value)

    def test_permutace_poradi_nemeni_vysledek(self):
        """Zadání § 40: jiné pořadí vstupních informací."""
        rng = random.Random(SEED)
        for _ in range(SAMPLES // 2):
            spec = random_spec(rng)
            shuffled = permute_spec(spec, rng)
            kb1, kb2 = build_kb(spec), build_kb(shuffled)
            infer_forward(kb1)
            infer_forward(kb2)
            self.assertEqual(readings(kb1, spec), readings(kb2, shuffled))

    def test_irelevantni_znalost_nemeni_cteni(self):
        """Zadání § 44: šum mimo dotazovanou část bázi nesmí ovlivnit."""
        rng = random.Random(SEED)
        for _ in range(SAMPLES // 2):
            spec = random_spec(rng)
            noisy = add_noise(spec, rng)
            kb1, kb2 = build_kb(spec), build_kb(noisy)
            infer_forward(kb1)
            infer_forward(kb2)
            self.assertEqual(readings(kb1, spec),
                             readings(kb2, noisy, names=spec.relation_names))


class TestGeneratorVacuum(unittest.TestCase):
    """T-13: generátor musí doložit, že vyrobil i negace a disjunkce."""

    def test_pokryti_generatoru(self):
        rng = random.Random(SEED)
        negative_bodies = 0
        or_rules = 0
        negative_facts = 0
        for _ in range(SAMPLES):
            spec = random_spec(rng)
            negative_bodies += sum(1 for r in spec.rules
                                   for l in r.body if not l.positive)
            or_rules += sum(1 for r in spec.rules
                            if r.kind == "or" and len(r.body) > 1)
            negative_facts += sum(1 for f in spec.facts if not f.positive)
        self.assertGreater(negative_bodies, 20)
        self.assertGreater(or_rules, 10)
        self.assertGreater(negative_facts, 10)


if __name__ == "__main__":
    unittest.main()
