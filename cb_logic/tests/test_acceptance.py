"""Závěrečný akceptační test (zadání § 59) — úloha vytvořená AŽ PO implementaci.

Expediční problém kombinuje: entity, relace, constrainty, AND/OR/NOT/
IMPLIES, vícekrokovou inferenci, větvení, irelevantní znalost, neúplnou
znalost, rozpornou znalost a alespoň jednu možnou alternativu. Buildér
je parametrizovaný přejmenováním, pořadím vkládání a šumem — tytéž
logické výsledky musí vyjít ve všech variantách (§ 59 závěr).
"""
import random
import unittest

from cb_logic.constraints import (ExpressionConstraint, at_least_one,
                                  exactly_one, requires)
from cb_logic.expressions import AtomRef, Not, conj, disj
from cb_logic.knowledge import KnowledgeBase, Rule
from cb_logic.provenance import (Assertion, Evidence, EvidenceKind,
                                 LEVEL_DEFINITION, LEVEL_DOCUMENTED,
                                 Provenance)
from cb_logic.semantics import Truth
from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Value,
                            Variable)
from cb_logic.explain import explain_conflict, why, why_not
from cb_logic.inference import infer_forward
from cb_logic.models import (ModalVerdict, ModelLimits, classify_query,
                             enumerate_models)

DEF = Provenance(LEVEL_DEFINITION, Evidence(EvidenceKind.USER_ASSERTION))
LIMITS = ModelLimits(max_scope_atoms=64)

RELATIONS = ("biolog", "vedec", "zacatecnik", "kandidat", "clen",
             "ridic", "jede", "lekar", "geolog")


def build_expedition(*, rename=lambda s: s, order_seed=None, noise=0):
    """Postaví problém; rename/order_seed/noise jsou metamorfní páky."""
    R = rename
    kb = KnowledgeBase()
    researchers = tuple(Entity(R(n)) for n in ("vera", "milos", "hana"))
    vera, milos, hana = researchers
    kb.declare_domain(Domain(R("vyzkumnici"), researchers))
    for name in RELATIONS:
        kb.declare_relation(Relation(R(name), 1))

    def atom(name, person):
        return Atom(kb.relation(R(name)), (person,))

    x = Variable("X")

    def head(name):
        return Literal(Atom(kb.relation(R(name)), (x,)))

    def ref(name):
        return AtomRef(Atom(kb.relation(R(name)), (x,)))

    dom = R("vyzkumnici")
    rules = [
        Rule(((x, dom),), ref("biolog"), head("vedec")),
        Rule(((x, dom),), conj(ref("vedec"), Not(ref("zacatecnik"))),
             head("kandidat")),
        Rule(((x, dom),), ref("kandidat"), head("clen")),
    ]
    constraints = [
        exactly_one(tuple(atom("ridic", p) for p in researchers),
                    label="prave-jeden-ridic"),
        at_least_one(tuple(atom("jede", p) for p in researchers),
                     label="nekdo-jede"),
        ExpressionConstraint(
            disj(AtomRef(atom("jede", vera)), AtomRef(atom("jede", milos))),
            label="vera-nebo-milos"),
    ] + [requires(AtomRef(atom("ridic", p)), AtomRef(atom("jede", p)),
                  label=f"ridic-jede-{p.id}") for p in researchers]
    facts = [
        (Literal(atom("biolog", vera)), "terenni-zaznam"),
        (Literal(atom("zacatecnik", vera), False), "terenni-zaznam"),
        (Literal(atom("ridic", hana), False), "terenni-zaznam"),
        (Literal(atom("lekar", hana)), "databaze"),          # rozpor —
        (Literal(atom("lekar", hana), False), "dialog"),     # obě strany
    ]
    if noise:
        strangers = tuple(Entity(R(f"cizinec{i}")) for i in range(noise))
        kb.declare_domain(Domain(R("cizinci"), strangers))
        for name in ("pocasi", "stan"):
            kb.declare_relation(Relation(R(name), 1))
        y = Variable("Y")
        rules.append(Rule(((y, R("cizinci")),),
                          AtomRef(Atom(kb.relation(R("pocasi")), (y,))),
                          Literal(Atom(kb.relation(R("stan")), (y,)))))
        facts += [(Literal(Atom(kb.relation(R("pocasi")), (s,))), "cizi")
                  for s in strangers]
    if order_seed is not None:
        rng = random.Random(order_seed)
        rng.shuffle(rules)
        rng.shuffle(constraints)
        rng.shuffle(facts)
    for rule in rules:
        kb.add_rule(rule, DEF)
    for constraint in constraints:
        kb.add_constraint(constraint, DEF)
    for literal, source in facts:
        kb.assert_candidate(Assertion(
            literal, Evidence(EvidenceKind.USER_ASSERTION, source=source),
            LEVEL_DOCUMENTED))
    infer_forward(kb)
    handles = {"kb": kb, "researchers": researchers, "atom": atom}
    return handles


def verdicts(handles):
    """Logický profil problému — musí být invariantní přes varianty."""
    kb = handles["kb"]
    atom = handles["atom"]
    vera, milos, hana = handles["researchers"]
    models = enumerate_models(kb, limits=LIMITS)
    return {
        "clen_vera": kb.truth_of(atom("clen", vera)),
        "geolog_milos": kb.truth_of(atom("geolog", milos)),
        "lekar_conflicted": kb.is_conflicted(atom("lekar", hana)),
        "jede_milos": classify_query(kb, AtomRef(atom("jede", milos)),
                                     limits=LIMITS).verdict,
        "ridic_hana": classify_query(kb, AtomRef(atom("ridic", hana)),
                                     limits=LIMITS).verdict,
        "ridic_v_nebo_m": classify_query(
            kb, disj(AtomRef(atom("ridic", vera)),
                     AtomRef(atom("ridic", milos))),
            limits=LIMITS).verdict,
        "models": len(models.models),
        "status": models.status.name,
    }


BASE = {
    "clen_vera": Truth.TRUE,
    "geolog_milos": Truth.UNKNOWN,
    "lekar_conflicted": True,
    "jede_milos": ModalVerdict.POSSIBLE,
    "ridic_hana": ModalVerdict.IMPOSSIBLE,
    "ridic_v_nebo_m": ModalVerdict.NECESSARY,
    "models": 16,
    "status": "COMPLETE",
}


class TestAcceptance(unittest.TestCase):
    def test_formalni_reprezentace_a_zaklad(self):
        handles = build_expedition()
        kb = handles["kb"]
        self.assertEqual(len(kb.rules), 3)
        self.assertEqual(len(kb.constraints), 6)
        self.assertEqual(len(kb.own_facts()), 5)
        self.assertEqual(verdicts(handles), BASE)

    def test_vicekrokova_inference_s_provenienci(self):
        handles = build_expedition()
        kb = handles["kb"]
        vera = handles["researchers"][0]
        explanations = why(kb, Literal(handles["atom"]("clen", vera)))
        top = explanations[0]                       # clen ← kandidat
        middle = top.premises[0]                    # kandidat ← vedec ∧ ¬zač.
        self.assertEqual(top.kind, "derived")
        self.assertEqual(middle.kind, "derived")
        leaf_kinds = {p.kind for p in middle.premises}
        self.assertIn("derived", leaf_kinds)        # vedec ← biolog
        self.assertIn("fact", leaf_kinds)           # ¬začátečník doloženě

    def test_protipriklad_a_rozpor(self):
        handles = build_expedition()
        kb = handles["kb"]
        vera, milos, hana = handles["researchers"]
        modal = classify_query(kb, AtomRef(handles["atom"]("jede", milos)),
                               limits=LIMITS)
        self.assertIsNotNone(modal.witness)
        self.assertIsNotNone(modal.counterexample)  # alternativa existuje
        sides = explain_conflict(kb, handles["atom"]("lekar", hana))
        self.assertEqual({e.evidence.source for e in sides},
                         {"databaze", "dialog"})
        # rozpor je lokální: ostatní verdikty drží (viz BASE v test výše)

    def test_neuplna_znalost_ma_poctivou_odpoved(self):
        handles = build_expedition()
        kb = handles["kb"]
        milos = handles["researchers"][1]
        result = why_not(kb, Literal(handles["atom"]("geolog", milos)),
                         limits=LIMITS)
        self.assertEqual(result.kind, "unknown")

    def test_prejmenovani_zachova_vysledky(self):
        renamed = build_expedition(rename=lambda s: f"x_{s}")
        self.assertEqual(verdicts(renamed), BASE)

    def test_permutace_poradi_zachova_vysledky(self):
        for seed in (7, 42, 328):
            shuffled = build_expedition(order_seed=seed)
            self.assertEqual(verdicts(shuffled), BASE, msg=f"seed {seed}")

    def test_irelevantni_znalost_zachova_vysledky(self):
        noisy = build_expedition(noise=6)
        self.assertEqual(verdicts(noisy), BASE)

    def test_kombinace_vsech_transformaci(self):
        combined = build_expedition(rename=lambda s: f"jina_{s}",
                                    order_seed=99, noise=4)
        self.assertEqual(verdicts(combined), BASE)


if __name__ == "__main__":
    unittest.main()
