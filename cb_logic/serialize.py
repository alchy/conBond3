"""JSON persistence báze — round-trip beze ztráty sémantiky (PROVENANCE.md § 5).

Persistuje se, z čeho jde všechno rekonstruovat: deklarace, strany faktů
(vlastní evidence + aktivní derivace), pravidla, constrainty, ledger
derivací a konflikty. Modely se nepersistují — jsou odvozeniny (INV-14).
Kanonická pořadí ⇒ dva zápisy téže báze jsou textově shodné.
"""
from __future__ import annotations

import json

from cb_logic.constraints import (CardinalityConstraint, Constraint,
                                  ExpressionConstraint)
from cb_logic.expressions import (And, AtomRef, Const, Equiv, Expression,
                                  Implies, Not, Or)
from cb_logic.knowledge import KnowledgeBase, Rule
from cb_logic.provenance import (Conflict, Derivation, Evidence, EvidenceKind,
                                 Provenance)
from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Term,
                            Value, Variable, atom_key)

FORMAT_VERSION = 1


# -- termy a atomy -----------------------------------------------------------

def _term_to_json(term: Term) -> dict:
    if isinstance(term, Entity):
        obj: dict = {"t": "entity", "id": term.id}
        if term.label is not None:
            obj["label"] = term.label
        return obj
    if isinstance(term, Value):
        if not isinstance(term.value, (str, int, float, bool)):
            raise ValueError(
                f"hodnota není JSON skalár: {term.value!r} "
                f"({type(term.value).__name__})")
        return {"t": "value", "value": term.value}
    return {"t": "var", "name": term.name}


def _term_from_json(obj: dict) -> Term:
    if obj["t"] == "entity":
        return Entity(obj["id"], obj.get("label"))
    if obj["t"] == "value":
        return Value(obj["value"])
    return Variable(obj["name"])


def _atom_to_json(atom: Atom) -> dict:
    return {"relation": atom.relation.name,
            "args": [_term_to_json(a) for a in atom.args]}


def _atom_from_json(obj: dict, relations: dict[str, Relation]) -> Atom:
    return Atom(relations[obj["relation"]],
                tuple(_term_from_json(a) for a in obj["args"]))


def _literal_to_json(literal: Literal) -> dict:
    return {"atom": _atom_to_json(literal.atom), "positive": literal.positive}


def _literal_from_json(obj: dict, relations: dict[str, Relation]) -> Literal:
    return Literal(_atom_from_json(obj["atom"], relations), obj["positive"])


# -- výrazy ------------------------------------------------------------------

def _expr_to_json(expr: Expression) -> dict:
    if isinstance(expr, Const):
        return {"op": "const", "value": expr.value}
    if isinstance(expr, AtomRef):
        return {"op": "atom", "atom": _atom_to_json(expr.atom)}
    if isinstance(expr, Not):
        return {"op": "not", "arg": _expr_to_json(expr.operand)}
    if isinstance(expr, And):
        return {"op": "and", "args": [_expr_to_json(o) for o in expr.operands]}
    if isinstance(expr, Or):
        return {"op": "or", "args": [_expr_to_json(o) for o in expr.operands]}
    if isinstance(expr, Implies):
        return {"op": "implies", "antecedent": _expr_to_json(expr.antecedent),
                "consequent": _expr_to_json(expr.consequent)}
    return {"op": "equiv", "left": _expr_to_json(expr.left),
            "right": _expr_to_json(expr.right)}


def _expr_from_json(obj: dict, relations: dict[str, Relation]) -> Expression:
    op = obj["op"]
    if op == "const":
        return Const(obj["value"])
    if op == "atom":
        return AtomRef(_atom_from_json(obj["atom"], relations))
    if op == "not":
        return Not(_expr_from_json(obj["arg"], relations))
    if op == "and":
        return And(tuple(_expr_from_json(a, relations) for a in obj["args"]))
    if op == "or":
        return Or(tuple(_expr_from_json(a, relations) for a in obj["args"]))
    if op == "implies":
        return Implies(_expr_from_json(obj["antecedent"], relations),
                       _expr_from_json(obj["consequent"], relations))
    return Equiv(_expr_from_json(obj["left"], relations),
                 _expr_from_json(obj["right"], relations))


# -- provenience -------------------------------------------------------------

def _provenance_to_json(provenance: Provenance) -> dict:
    return {"level": provenance.level,
            "evidence": {"kind": provenance.evidence.kind.value,
                         "source": provenance.evidence.source,
                         "confidence": provenance.evidence.confidence},
            "derivation_id": provenance.derivation_id}


def _provenance_from_json(obj: dict) -> Provenance:
    evidence = obj["evidence"]
    return Provenance(obj["level"],
                      Evidence(EvidenceKind(evidence["kind"]),
                               evidence["source"], evidence["confidence"]),
                      obj["derivation_id"])


# -- báze --------------------------------------------------------------------

def kb_to_json(kb: KnowledgeBase) -> dict:
    sides = []
    for (atom, positive), side in sorted(
            kb._sides.items(),
            key=lambda item: (atom_key(item[0][0]), not item[0][1])):
        if side.own is None and not side.derivations:
            continue
        sides.append({"atom": _atom_to_json(atom), "positive": positive,
                      "own": (None if side.own is None
                              else _provenance_to_json(side.own)),
                      "derivations": list(side.derivations)})
    constraints = []
    for constraint, provenance in kb.constraints:
        if isinstance(constraint, CardinalityConstraint):
            constraints.append({
                "type": "cardinality",
                "atoms": [_atom_to_json(a) for a in constraint.atoms],
                "at_least": constraint.at_least,
                "at_most": constraint.at_most,
                "label": constraint.label,
                "provenance": _provenance_to_json(provenance)})
        else:
            constraints.append({
                "type": "expression",
                "expr": _expr_to_json(constraint.expr),
                "label": constraint.label,
                "provenance": _provenance_to_json(provenance)})
    return {
        "format_version": FORMAT_VERSION,
        "relations": [{"name": r.name, "arity": r.arity}
                      for r in sorted(kb._relations.values(),
                                      key=lambda r: r.name)],
        "domains": [{"name": d.name,
                     "members": [_term_to_json(m) for m in d.members]}
                    for d in sorted(kb._domains.values(),
                                    key=lambda d: d.name)],
        "sides": sides,
        "rules": [{"vars": [[v.name, domain] for v, domain in
                            rule.var_domains],
                   "body": _expr_to_json(rule.body),
                   "head": _literal_to_json(rule.head),
                   "provenance": _provenance_to_json(provenance)}
                  for rule, provenance in kb.rules],
        "constraints": constraints,
        "derivations": [{"id": d.id,
                         "conclusion": _literal_to_json(d.conclusion),
                         "premises": [_literal_to_json(p)
                                      for p in d.premises],
                         "rule_index": d.rule_index,
                         "assumptions": sorted(d.assumptions)}
                        for d in kb.derivations],
        "conflicts": [{"atom": _atom_to_json(c.atom),
                       "positive": _provenance_to_json(c.positive),
                       "negative": _provenance_to_json(c.negative)}
                      for c in kb.conflicts],
    }


def kb_to_json_text(kb: KnowledgeBase) -> str:
    """Deterministický textový zápis — dva zápisy téže báze jsou shodné."""
    return json.dumps(kb_to_json(kb), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def kb_from_json(data: dict) -> KnowledgeBase:
    version = data.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(f"neznámá verze formátu: {version!r} "
                         f"(očekávána {FORMAT_VERSION})")
    kb = KnowledgeBase()
    for entry in data["relations"]:
        kb.declare_relation(Relation(entry["name"], entry["arity"]))
    relations = {name: kb.relation(name)
                 for name in (e["name"] for e in data["relations"])}
    for entry in data["domains"]:
        kb.declare_domain(Domain(
            entry["name"],
            tuple(_term_from_json(m) for m in entry["members"])))
    for entry in data["rules"]:
        rule = Rule(tuple((Variable(name), domain)
                          for name, domain in entry["vars"]),
                    _expr_from_json(entry["body"], relations),
                    _literal_from_json(entry["head"], relations))
        kb.add_rule(rule, _provenance_from_json(entry["provenance"]))
    for entry in data["constraints"]:
        provenance = _provenance_from_json(entry["provenance"])
        if entry["type"] == "cardinality":
            constraint: Constraint = CardinalityConstraint(
                tuple(_atom_from_json(a, relations)
                      for a in entry["atoms"]),
                entry["at_least"], entry["at_most"], entry["label"])
        else:
            constraint = ExpressionConstraint(
                _expr_from_json(entry["expr"], relations), entry["label"])
        kb.add_constraint(constraint, provenance)
    for entry in data["derivations"]:
        kb.derivations.append(Derivation(
            entry["id"],
            _literal_from_json(entry["conclusion"], relations),
            tuple(_literal_from_json(p, relations)
                  for p in entry["premises"]),
            entry["rule_index"], frozenset(entry["assumptions"])))
    for entry in data["sides"]:
        side = kb._side(_atom_from_json(entry["atom"], relations),
                        entry["positive"])
        side.own = (None if entry["own"] is None
                    else _provenance_from_json(entry["own"]))
        side.derivations = list(entry["derivations"])
    for entry in data["conflicts"]:
        kb.conflicts.append(Conflict(
            _atom_from_json(entry["atom"], relations),
            _provenance_from_json(entry["positive"]),
            _provenance_from_json(entry["negative"])))
    return kb
