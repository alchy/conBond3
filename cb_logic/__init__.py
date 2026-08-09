"""cb_logic — formální jádro znalosti a logiky.

Čistá knihovna (stdlib, žádný import z cb_*): termy, atomy, výrazy
a pravdivostní sémantika. Specifikace: KNOWLEDGE_MODEL.md,
LOGIC_SEMANTICS.md v kořeni repozitáře.
"""
from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Value,
                            Variable, atom_key, is_ground, term_key)
from cb_logic.expressions import (And, AtomRef, Const, Equiv, Expression,
                                  Implies, Not, Or, atoms, conj, disj,
                                  from_literal, substitute, to_text)
from cb_logic.semantics import (DEFAULT_MAX_ATOMS, Decision, DecisionResult,
                                Truth, UnboundAtomError, evaluate,
                                evaluate_partial, is_contradiction,
                                is_satisfiable, is_tautology, truth_table)

__all__ = [
    "Atom", "Domain", "Entity", "Literal", "Relation", "Value", "Variable",
    "atom_key", "is_ground", "term_key",
    "And", "AtomRef", "Const", "Equiv", "Expression", "Implies", "Not", "Or",
    "atoms", "conj", "disj", "from_literal", "substitute", "to_text",
    "DEFAULT_MAX_ATOMS", "Decision", "DecisionResult", "Truth",
    "UnboundAtomError", "evaluate", "evaluate_partial", "is_contradiction",
    "is_satisfiable", "is_tautology", "truth_table",
]
