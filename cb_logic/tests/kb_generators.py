"""Generátor náhodných bází + nezávislé naivní orákulum forward chainingu.

Báze se generuje jako datová specifikace (KbSpec) a teprve staví — díky
tomu jdou metamorfní transformace (přejmenování, permutace, šum) provádět
nad daty, ne nad hotovou bází. Vědomé zúžení generátoru: hlavy pravidel
jsou kladné (záporné hlavy a mřížku úrovní kryjí jednotkové testy) — orákulum
tak zůstává úrovňově jednoduché a nezávislé.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

from cb_logic.expressions import atoms as expr_atoms
from cb_logic.expressions import conj, disj, from_literal, substitute
from cb_logic.knowledge import KnowledgeBase, Rule
from cb_logic.provenance import (Assertion, Evidence, EvidenceKind,
                                 LEVEL_DEFINITION, LEVEL_DOCUMENTED,
                                 Provenance)
from cb_logic.semantics import Truth, evaluate_partial
from cb_logic.terms import Atom, Domain, Entity, Literal, Relation, Variable, term_key

SEED = 328
SAMPLES = 50
OBS = Evidence(EvidenceKind.OBSERVATION)
USER = Evidence(EvidenceKind.USER_ASSERTION)


@dataclass(frozen=True)
class LitSpec:
    relation: int
    positive: bool


@dataclass(frozen=True)
class FactSpec:
    relation: int
    entity: int
    positive: bool


@dataclass(frozen=True)
class RuleSpec:
    kind: str  # "and" | "or"
    body: tuple[LitSpec, ...]
    head: int


@dataclass(frozen=True)
class KbSpec:
    entity_names: tuple[str, ...]
    relation_names: tuple[str, ...]
    facts: tuple[FactSpec, ...]
    rules: tuple[RuleSpec, ...]


def random_spec(rng: random.Random, *, entities: int = 4, relations: int = 5,
                facts: int = 7, rules: int = 5,
                negation_free: bool = False) -> KbSpec:
    fact_specs = tuple(
        FactSpec(rng.randrange(relations), rng.randrange(entities),
                 True if negation_free else rng.random() < 0.8)
        for _ in range(facts))
    rule_specs = []
    for _ in range(rules):
        size = rng.randint(1, 2)
        body = tuple(
            LitSpec(rng.randrange(relations),
                    True if negation_free else rng.random() < 0.75)
            for _ in range(size))
        rule_specs.append(RuleSpec(rng.choice(("and", "or")), body,
                                   rng.randrange(relations)))
    return KbSpec(tuple(f"e{i}" for i in range(entities)),
                  tuple(f"r{i}" for i in range(relations)),
                  fact_specs, tuple(rule_specs))


def rename_spec(spec: KbSpec, entity_map: dict[str, str],
                relation_map: dict[str, str]) -> KbSpec:
    """Bijektivní přejmenování — struktura (indexy) zůstává, jména se mění."""
    return KbSpec(tuple(entity_map[n] for n in spec.entity_names),
                  tuple(relation_map[n] for n in spec.relation_names),
                  spec.facts, spec.rules)


def permute_spec(spec: KbSpec, rng: random.Random) -> KbSpec:
    """Jiné pořadí faktů i pravidel; obsah beze změny."""
    facts = list(spec.facts)
    rules = list(spec.rules)
    rng.shuffle(facts)
    rng.shuffle(rules)
    return KbSpec(spec.entity_names, spec.relation_names,
                  tuple(facts), tuple(rules))


def add_noise(spec: KbSpec, rng: random.Random, *, relations: int = 3,
              facts: int = 10, rules: int = 4) -> KbSpec:
    """Irelevantní znalost: nové relace, fakta a pravidla jen mezi nimi."""
    base = len(spec.relation_names)
    noise_names = tuple(f"noise{i}" for i in range(relations))
    noise_facts = tuple(
        FactSpec(base + rng.randrange(relations),
                 rng.randrange(len(spec.entity_names)), rng.random() < 0.8)
        for _ in range(facts))
    noise_rules = tuple(
        RuleSpec(rng.choice(("and", "or")),
                 tuple(LitSpec(base + rng.randrange(relations),
                               rng.random() < 0.75)
                       for _ in range(rng.randint(1, 2))),
                 base + rng.randrange(relations))
        for _ in range(rules))
    return KbSpec(spec.entity_names, spec.relation_names + noise_names,
                  spec.facts + noise_facts, spec.rules + noise_rules)


def build_kb(spec: KbSpec) -> KnowledgeBase:
    kb = KnowledgeBase()
    for name in spec.relation_names:
        kb.declare_relation(Relation(name, 1))
    kb.declare_domain(Domain("all",
                             tuple(Entity(n) for n in spec.entity_names)))
    x = Variable("X")
    for rule in spec.rules:
        literals = [from_literal(Literal(
            Atom(kb.relation(spec.relation_names[l.relation]), (x,)),
            l.positive)) for l in rule.body]
        body = (conj(*literals) if rule.kind == "and" or len(literals) == 1
                else disj(*literals))
        kb.add_rule(Rule(((x, "all"),), body,
                         Literal(Atom(
                             kb.relation(spec.relation_names[rule.head]),
                             (x,)))),
                    Provenance(LEVEL_DEFINITION, USER))
    for fact in spec.facts:
        kb.assert_candidate(Assertion(
            Literal(Atom(kb.relation(spec.relation_names[fact.relation]),
                         (Entity(spec.entity_names[fact.entity]),)),
                    fact.positive),
            OBS, LEVEL_DOCUMENTED))
    return kb


def readings(kb: KnowledgeBase, spec: KbSpec,
             names: tuple[str, ...] | None = None) -> dict:
    """Čtení celého universa (relace × entity) — pro porovnávání běhů."""
    names = names if names is not None else spec.relation_names
    out = {}
    for rel_name in names:
        for ent_name in spec.entity_names:
            atom = Atom(kb.relation(rel_name), (Entity(ent_name),))
            out[(rel_name, ent_name)] = kb.truth_of(atom)
    return out


def naive_forward_readings(kb: KnowledgeBase, spec: KbSpec) -> dict:
    """Nezávislé orákulum: množinové čtení bez derivací a optimalizací.

    documented = strany s vlastní evidencí; derived = strany doplněné
    opakovaným průchodem pravidel do stabilizace. Čtení: doložené přebíjí
    odvozené, protistrany na téže úrovni = UNKNOWN.
    """
    documented: set[tuple[Atom, bool]] = {
        key for key, side in kb._sides.items() if side.own is not None}
    derived: set[tuple[Atom, bool]] = set()

    def reading(atom: Atom) -> Truth:
        pos_doc, neg_doc = (atom, True) in documented, (atom, False) in documented
        if pos_doc and neg_doc:
            return Truth.UNKNOWN
        if pos_doc:
            return Truth.TRUE
        if neg_doc:
            return Truth.FALSE
        pos_der, neg_der = (atom, True) in derived, (atom, False) in derived
        if pos_der and neg_der:
            return Truth.UNKNOWN
        if pos_der:
            return Truth.TRUE
        if neg_der:
            return Truth.FALSE
        return Truth.UNKNOWN

    changed = True
    while changed:
        changed = False
        for rule, _ in kb.rules:
            variables = [v for v, _ in rule.var_domains]
            member_lists = [sorted(kb.domain(d).members, key=term_key)
                            for _, d in rule.var_domains]
            for combo in itertools.product(*member_lists):
                binding = dict(zip(variables, combo))
                body = substitute(rule.body, binding)
                partial = {}
                for atom in expr_atoms(body):
                    value = reading(atom)
                    if value is not Truth.UNKNOWN:
                        partial[atom] = value is Truth.TRUE
                if evaluate_partial(body, partial) is not Truth.TRUE:
                    continue
                head_expr = substitute(from_literal(rule.head), binding)
                key = (head_expr.atom, True)
                if key not in derived and key not in documented:
                    derived.add(key)
                    changed = True
    out = {}
    for rel_name in spec.relation_names:
        for ent_name in spec.entity_names:
            atom = Atom(kb.relation(rel_name), (Entity(ent_name),))
            out[(rel_name, ent_name)] = reading(atom)
    return out
