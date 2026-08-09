"""Property a metamorfní testy — LOGIC_SEMANTICS.md § 5.

Ekvivalence ≡ znamená: shodná hodnota pro VŠECHNA ohodnocení sjednocení
atomů obou stran. Pojistka proti vakuu (T-13): generátor musí doložit,
že vyrobil negace, implikace, ekvivalence i hluboké výrazy.
"""
import itertools
import random
import unittest

from cb_logic.expressions import (And, AtomRef, Equiv, Implies, Not, Or,
                                  atoms, conj, disj)
from cb_logic.semantics import (Truth, evaluate, evaluate_partial,
                                is_tautology)
from cb_logic.terms import Atom, Entity, Relation, atom_key
from cb_logic.tests.generators import SAMPLES, SEED, random_expression

POOL = tuple(Atom(Relation(n, 1), (Entity(e),))
             for n, e in (("p", "a"), ("q", "b"), ("r", "c"), ("s", "d")))


def all_assignments(atom_set):
    for values in itertools.product((False, True), repeat=len(atom_set)):
        yield dict(zip(atom_set, values))


def equivalent(e1, e2):
    """Shodná hodnota pro všechna ohodnocení sjednocení atomů."""
    union = tuple(sorted(set(atoms(e1)) | set(atoms(e2)), key=atom_key))
    return all(evaluate(e1, env) == evaluate(e2, env)
               for env in all_assignments(union))


class TestAlgebraicLaws(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(SEED)

    def samples(self, n=SAMPLES):
        for _ in range(n):
            yield random_expression(self.rng, POOL, max_depth=4)

    def test_dvoji_negace(self):
        for e in self.samples():
            self.assertTrue(equivalent(Not(Not(e)), e))

    def test_komutativita_a_absorpce(self):
        for e1 in self.samples(SAMPLES // 2):
            e2 = random_expression(self.rng, POOL, max_depth=3)
            self.assertTrue(equivalent(conj(e1, e2), conj(e2, e1)))
            self.assertTrue(equivalent(disj(e1, e2), disj(e2, e1)))
            self.assertTrue(equivalent(disj(e1, conj(e1, e2)), e1))
            self.assertTrue(equivalent(conj(e1, disj(e1, e2)), e1))

    def test_de_morgan_a_implikace(self):
        for e1 in self.samples(SAMPLES // 2):
            e2 = random_expression(self.rng, POOL, max_depth=3)
            self.assertTrue(equivalent(Not(conj(e1, e2)),
                                       disj(Not(e1), Not(e2))))
            self.assertTrue(equivalent(Not(disj(e1, e2)),
                                       conj(Not(e1), Not(e2))))
            self.assertTrue(equivalent(Implies(e1, e2), disj(Not(e1), e2)))

    def test_identita_s_konstantami(self):
        from cb_logic.expressions import Const
        for e in self.samples(SAMPLES // 2):
            self.assertTrue(equivalent(conj(e, Const(True)), e))
            self.assertTrue(equivalent(disj(e, Const(False)), e))


class TestK3Monotonicity(unittest.TestCase):
    def test_rozsireni_nemeni_neunknown_vysledek(self):
        rng = random.Random(SEED)
        checked = 0
        for _ in range(SAMPLES):
            e = random_expression(rng, POOL, max_depth=4)
            atom_list = atoms(e)
            known = {a: rng.random() < 0.5 for a in atom_list
                     if rng.random() < 0.5}
            partial_value = evaluate_partial(e, known)
            if partial_value is Truth.UNKNOWN:
                continue
            checked += 1
            missing = [a for a in atom_list if a not in known]
            for values in itertools.product((False, True),
                                            repeat=len(missing)):
                env = dict(known)
                env.update(zip(missing, values))
                total = Truth.TRUE if evaluate(e, env) else Truth.FALSE
                self.assertEqual(total, partial_value)
        self.assertGreater(checked, 20)  # T-13: vlastnost se skutečně měřila


class TestMetamorphic(unittest.TestCase):
    def test_prejmenovani_atomu_zachova_tabulku(self):
        rng = random.Random(SEED)
        renamed_pool = tuple(Atom(Relation(f"rel_{i}", 1), (Entity(f"x{i}"),))
                             for i in range(len(POOL)))
        mapping = dict(zip(POOL, renamed_pool))
        for _ in range(SAMPLES // 2):
            e = random_expression(rng, POOL, max_depth=4)
            renamed = _rename(e, mapping)
            for env in all_assignments(atoms(e)):
                renamed_env = {mapping[a]: v for a, v in env.items()}
                self.assertEqual(evaluate(e, env),
                                 evaluate(renamed, renamed_env))

    def test_irelevantni_atom_nemeni_verdikt_tautologie(self):
        rng = random.Random(SEED)
        extra = AtomRef(Atom(Relation("noise", 1), (Entity("z"),)))
        for _ in range(SAMPLES // 4):
            e = random_expression(rng, POOL, max_depth=3)
            padded = conj(e, disj(extra, Not(extra)))
            self.assertEqual(is_tautology(e).verdict,
                             is_tautology(padded).verdict)


def _rename(expr, mapping):
    if isinstance(expr, AtomRef):
        return AtomRef(mapping[expr.atom])
    if isinstance(expr, Not):
        return Not(_rename(expr.operand, mapping))
    if isinstance(expr, And):
        return And(tuple(_rename(o, mapping) for o in expr.operands))
    if isinstance(expr, Or):
        return Or(tuple(_rename(o, mapping) for o in expr.operands))
    if isinstance(expr, Implies):
        return Implies(_rename(expr.antecedent, mapping),
                       _rename(expr.consequent, mapping))
    if isinstance(expr, Equiv):
        return Equiv(_rename(expr.left, mapping),
                     _rename(expr.right, mapping))
    return expr


class TestGeneratorVacuumGuard(unittest.TestCase):
    """T-13: generátor musí doložit, že testy měly co měřit."""

    def test_pokryti_druhu_uzlu_a_hloubky(self):
        rng = random.Random(SEED)
        kinds = set()
        max_atoms_seen = 0
        deep = 0
        for _ in range(SAMPLES):
            e = random_expression(rng, POOL, max_depth=4)
            kinds |= {type(n).__name__ for n in _walk(e)}
            max_atoms_seen = max(max_atoms_seen, len(atoms(e)))
            if _depth(e) >= 4:
                deep += 1
        self.assertLessEqual({"Not", "And", "Or", "Implies", "Equiv"}, kinds)
        self.assertGreaterEqual(max_atoms_seen, 4)
        self.assertGreater(deep, 10)


def _walk(expr):
    yield expr
    for child in _children(expr):
        yield from _walk(child)


def _children(expr):
    if isinstance(expr, Not):
        return (expr.operand,)
    if isinstance(expr, (And, Or)):
        return expr.operands
    if isinstance(expr, Implies):
        return (expr.antecedent, expr.consequent)
    if isinstance(expr, Equiv):
        return (expr.left, expr.right)
    return ()


def _depth(expr):
    children = _children(expr)
    if not children:
        return 1
    return 1 + max(_depth(c) for c in children)


if __name__ == "__main__":
    unittest.main()
