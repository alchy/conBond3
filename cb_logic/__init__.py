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
from cb_logic.provenance import (Assertion, Conflict, Derivation, Evidence,
                                 EvidenceKind, LEVEL_CORRECTION,
                                 LEVEL_DEFINITION, LEVEL_DERIVED,
                                 LEVEL_DOCUMENTED, LEVEL_HYPOTHESIS,
                                 Provenance)
from cb_logic.constraints import (CardinalityConstraint, Constraint,
                                  ExpressionConstraint, MAX_EXPANSION_ATOMS,
                                  at_least_one, at_most_one, atom_family,
                                  equivalent, exactly_one, excludes, requires,
                                  satisfied_by, to_expression, truth_partial)
from cb_logic.knowledge import (Accepted, Conflicted, KnowledgeBase, Rejected,
                                Rule)
from cb_logic.inference import (InferenceResult, InferenceStatus, Limits,
                                Proof, ProofStatus, RetractResult,
                                assumption_label, ground_rule, infer_forward,
                                prove, retract, with_assumptions)
from cb_logic.models import (AtomClassification, ModalResult, ModalVerdict,
                             Model, ModelLimits, ModelSearchResult,
                             ScopeResult, SearchStatus, classify_atoms,
                             classify_query, enumerate_models, is_redundant,
                             model_scope, uniqueness_critical, violations)
from cb_logic.explain import (Explanation, Suggestion, WhyNotResult,
                              explain_conflict, why, why_not)
from cb_logic.serialize import (FORMAT_VERSION, kb_from_json, kb_to_json,
                                kb_to_json_text)

__all__ = [
    "Atom", "Domain", "Entity", "Literal", "Relation", "Value", "Variable",
    "atom_key", "is_ground", "term_key",
    "And", "AtomRef", "Const", "Equiv", "Expression", "Implies", "Not", "Or",
    "atoms", "conj", "disj", "from_literal", "substitute", "to_text",
    "DEFAULT_MAX_ATOMS", "Decision", "DecisionResult", "Truth",
    "UnboundAtomError", "evaluate", "evaluate_partial", "is_contradiction",
    "is_satisfiable", "is_tautology", "truth_table",
    "Assertion", "Conflict", "Derivation", "Evidence", "EvidenceKind",
    "LEVEL_CORRECTION", "LEVEL_DEFINITION", "LEVEL_DERIVED",
    "LEVEL_DOCUMENTED", "LEVEL_HYPOTHESIS", "Provenance",
    "CardinalityConstraint", "Constraint", "ExpressionConstraint",
    "MAX_EXPANSION_ATOMS", "at_least_one", "at_most_one", "atom_family",
    "equivalent", "exactly_one", "excludes", "requires", "satisfied_by",
    "to_expression", "truth_partial",
    "Accepted", "Conflicted", "KnowledgeBase", "Rejected", "Rule",
    "InferenceResult", "InferenceStatus", "Limits", "Proof", "ProofStatus",
    "RetractResult", "assumption_label", "ground_rule", "infer_forward",
    "prove", "retract", "with_assumptions",
    "AtomClassification", "ModalResult", "ModalVerdict", "Model",
    "ModelLimits", "ModelSearchResult", "ScopeResult", "SearchStatus",
    "classify_atoms", "classify_query", "enumerate_models", "is_redundant",
    "model_scope", "uniqueness_critical", "violations",
    "Explanation", "Suggestion", "WhyNotResult", "explain_conflict", "why",
    "why_not",
    "FORMAT_VERSION", "kb_from_json", "kb_to_json", "kb_to_json_text",
]
