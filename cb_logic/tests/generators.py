"""Deterministický generátor náhodných výrazů pro property testy.

Náhoda výhradně z předaného random.Random se semínkem — žádný globální
stav (LOGIC_SEMANTICS § 8).
"""
from __future__ import annotations

import random

from cb_logic.expressions import (AtomRef, Const, Equiv, Expression, Implies,
                                  Not, conj, disj)
from cb_logic.terms import Atom

SEED = 328
SAMPLES = 200


def random_expression(rng: random.Random, atom_pool: tuple[Atom, ...],
                      max_depth: int) -> Expression:
    """Rekurzivní generátor; listy jsou atomy (většina) a konstanty (zřídka)."""
    if max_depth <= 0 or rng.random() < 0.3:
        if rng.random() < 0.1:
            return Const(rng.random() < 0.5)
        return AtomRef(rng.choice(atom_pool))
    kind = rng.choice(("not", "and", "or", "implies", "equiv"))

    def child() -> Expression:
        return random_expression(rng, atom_pool, max_depth - 1)

    if kind == "not":
        return Not(child())
    if kind == "and":
        return conj(*(child() for _ in range(rng.randint(2, 3))))
    if kind == "or":
        return disj(*(child() for _ in range(rng.randint(2, 3))))
    if kind == "implies":
        return Implies(child(), child())
    return Equiv(child(), child())
