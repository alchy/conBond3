"""Testy constraintů — CONSTRAINT_MODEL.md; křížová shoda čtení (T-11)."""
import itertools
import unittest

from cb_logic.expressions import AtomRef
from cb_logic.semantics import Truth
from cb_logic.terms import Atom, Domain, Entity, Relation, Value
from cb_logic.constraints import (CardinalityConstraint, ExpressionConstraint,
                                  at_least_one, at_most_one, atom_family,
                                  equivalent, exactly_one, excludes, requires,
                                  satisfied_by, to_expression, truth_partial)
from cb_logic.semantics import evaluate

HAS = Relation("instrument", 2)
ANNA = Entity("anna")
NASTROJE = Domain("nastroje", (Value("housle"), Value("viola"),
                               Value("cello")))
FAMILY = atom_family(HAS, (ANNA, None), NASTROJE)


def assignments(atoms):
    for values in itertools.product((False, True), repeat=len(atoms)):
        yield dict(zip(atoms, values))


class TestValidation(unittest.TestCase):
    def test_prazdna_rodina_a_duplicita_jsou_chyby(self):
        with self.assertRaises(ValueError):
            CardinalityConstraint((), 0, None)
        with self.assertRaises(ValueError):
            CardinalityConstraint((FAMILY[0], FAMILY[0]), 1, 1)

    def test_meze_kardinality(self):
        with self.assertRaises(ValueError):
            CardinalityConstraint(FAMILY, 4, None)  # at_least > |rodina|
        with self.assertRaises(ValueError):
            CardinalityConstraint(FAMILY, 2, 1)     # at_most < at_least


class TestSemantics(unittest.TestCase):
    def test_exactly_one(self):
        c = exactly_one(FAMILY)
        for env in assignments(FAMILY):
            expected = sum(env.values()) == 1
            self.assertEqual(satisfied_by(c, env), expected)

    def test_krizova_shoda_expanze_a_pocitani(self):
        """T-11: dvě čtení téže sémantiky si nesmějí odporovat."""
        for c in (exactly_one(FAMILY), at_least_one(FAMILY),
                  at_most_one(FAMILY),
                  CardinalityConstraint(FAMILY, 1, 2)):
            expr = to_expression(c)
            for env in assignments(FAMILY):
                self.assertEqual(satisfied_by(c, env), evaluate(expr, env),
                                 msg=f"{c} × {env}")

    def test_vyrazove_zkratky(self):
        a, b = AtomRef(FAMILY[0]), AtomRef(FAMILY[1])
        env_tt = {FAMILY[0]: True, FAMILY[1]: True, FAMILY[2]: False}
        self.assertFalse(satisfied_by(excludes(a, b), env_tt))
        self.assertTrue(satisfied_by(requires(a, b), env_tt))
        self.assertTrue(satisfied_by(equivalent(a, b), env_tt))

    def test_expanze_nad_limit_je_chyba_pocitani_funguje(self):
        big_domain = Domain("big", tuple(Value(f"v{i}") for i in range(15)))
        big = atom_family(Relation("r", 2), (ANNA, None), big_domain)
        c = exactly_one(big)
        with self.assertRaises(ValueError):
            to_expression(c)
        env = {a: (i == 3) for i, a in enumerate(big)}
        self.assertTrue(satisfied_by(c, env))


class TestPartial(unittest.TestCase):
    def test_kleene_cteni_kardinality(self):
        c = exactly_one(FAMILY)
        self.assertEqual(truth_partial(c, {}), Truth.UNKNOWN)
        self.assertEqual(
            truth_partial(c, {FAMILY[0]: True, FAMILY[1]: True}), Truth.FALSE)
        self.assertEqual(
            truth_partial(c, {FAMILY[0]: False, FAMILY[1]: False,
                              FAMILY[2]: False}), Truth.FALSE)
        self.assertEqual(
            truth_partial(c, {FAMILY[0]: True, FAMILY[1]: False,
                              FAMILY[2]: False}), Truth.TRUE)

    def test_neunknown_se_doplnenim_nezmeni(self):
        """Monotonie parciálního čtení — enumerací všech doplnění."""
        checked = 0
        for c in (exactly_one(FAMILY), at_least_one(FAMILY),
                  CardinalityConstraint(FAMILY, 1, 2)):
            for env in assignments(FAMILY):
                for known_mask in itertools.product((False, True),
                                                    repeat=len(FAMILY)):
                    partial = {a: env[a] for a, keep in zip(FAMILY, known_mask)
                               if keep}
                    verdict = truth_partial(c, partial)
                    if verdict is Truth.UNKNOWN:
                        continue
                    checked += 1
                    expected = (Truth.TRUE if satisfied_by(c, env)
                                else Truth.FALSE)
                    missing = [a for a in FAMILY if a not in partial]
                    for values in itertools.product((False, True),
                                                    repeat=len(missing)):
                        total = dict(partial)
                        total.update(zip(missing, values))
                        total_verdict = (Truth.TRUE
                                         if satisfied_by(c, total)
                                         else Truth.FALSE)
                        self.assertEqual(total_verdict, verdict)
        self.assertGreater(checked, 50)  # T-13


class TestAtomFamily(unittest.TestCase):
    def test_deterministicke_poradi_dle_term_key(self):
        self.assertEqual(
            [a.args[1] for a in FAMILY],
            [Value("cello"), Value("housle"), Value("viola")])

    def test_prave_jedno_volne_misto(self):
        with self.assertRaises(ValueError):
            atom_family(HAS, (None, None), NASTROJE)
        with self.assertRaises(ValueError):
            atom_family(HAS, (ANNA, Value("housle")), NASTROJE)


if __name__ == "__main__":
    unittest.main()
