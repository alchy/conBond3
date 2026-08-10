"""Testy učení jazykových vzorů z dialogu — LANGUAGE_LEARNING.md.

Celý oblouk: neznámé → doptání z menu → naučení hypotézy → obecné použití
→ negace → životní cyklus → odvolání. Modální dotaz se ověřuje i sémanticky
(∃M/∀M/¬∃M) nad konstruovanou bází.
"""
import unittest

from cb_logic import (Assertion, Atom, AtomRef, Domain, Entity, Evidence,
                      EvidenceKind, ExpressionConstraint, KnowledgeBase,
                      LEVEL_DOCUMENTED, Literal, Not, Provenance,
                      LEVEL_DEFINITION, Relation, Value, at_least_one,
                      conj, disj)
from cb_interpret.learner import DialogueLearner, _run_modal
from cb_interpret.patterns import Operation, PatternStatus, StructuralSignature
from cb_interpret.tests import vzorky
from cb_interpret.tests import vzorky_struct as vs


def make_learner():
    return DialogueLearner(KnowledgeBase())


class TestAskWhenUnknown(unittest.TestCase):
    def test_nezname_sloveso_vyvola_doptani_z_menu(self):
        learner = make_learner()
        result = learner.ask(vzorky.MUZE_AUTO_JET, "Auto může jet na silnici.")
        self.assertEqual(result.candidate.kind, "needs_pattern")
        self.assertIsNotNone(result.clarification)
        ops = {op for op, _ in result.clarification.options}
        self.assertEqual(ops, {Operation.POSSIBLE, Operation.NECESSARY,
                               Operation.IMPOSSIBLE})
        # NEHÁDÁ: žádná odpověď, jen dotaz
        self.assertIsNone(result.truth)


class TestLearnAndApply(unittest.TestCase):
    def test_nauceni_hypotezy_pak_dotaz_funguje(self):
        learner = make_learner()
        sig = learner.ask(vzorky.MUZE_AUTO_JET,
                          "Auto může jet na silnici.").candidate.signature
        pattern = learner.teach_pattern(sig, Operation.POSSIBLE,
                                        learned_from="Auto může jet na silnici.")
        self.assertEqual(pattern.status, PatternStatus.HYPOTHESIS)
        result = learner.ask(vzorky.MUZE_AUTO_JET, "Auto může jet na silnici.")
        self.assertEqual(result.candidate.kind, "modal_query")

    def test_slozeny_xcomp_je_modalni_dotaz_nad_konjunkci(self):
        # „do města" se nesmí tiše ztratit — dotaz jde nad konjunkci
        learner = make_learner()
        learner.teach_pattern(
            StructuralSignature("moci", has_xcomp=True),
            Operation.POSSIBLE, learned_from="test")
        result = learner.ask(vs.AUTO_MUZE_JET_DO_MESTA,
                             "Auto může jet po dálnici do města.")
        self.assertEqual(result.candidate.kind, "modal_query")
        self.assertEqual({a.relation.name
                          for a in result.candidate.query_atoms},
                         {"jet_po", "jet_do"})
        self.assertIs(result.modal["answer"], True)   # nic to nezakazuje…
        self.assertFalse(result.modal["grounded"])    # …ale nic nedokládá
        self.assertEqual(result.modal["operation"], "possible")
        # prázdná báze nic nezakazuje ⇒ je to možné
        self.assertTrue(result.modal["answer"])

    def test_vzor_je_obecny_ne_veta(self):
        """Týž naučený vzor 'moci' platí pro jiný podmět i predikát (§60)."""
        learner = make_learner()
        learner.teach_pattern(StructuralSignature("moci", has_xcomp=True),
                              Operation.POSSIBLE, learned_from="…")
        for tokens, text in ((vzorky.MUZE_PETR_PRIJIT, "Petr může přijít."),
                             (vzorky.MUZE_ANNA_HRAT,
                              "Anna může hrát na housle.")):
            result = learner.ask(tokens, text)
            self.assertEqual(result.candidate.kind, "modal_query", msg=text)
            self.assertEqual(result.modal["operation"], "possible")

    def test_negace_meni_ktery_dotaz(self):
        """'nemůže' (Polarity=Neg, lemma moci) → IMPOSSIBLE, ne nová osa."""
        learner = make_learner()
        learner.teach_pattern(StructuralSignature("moci", has_xcomp=True),
                              Operation.POSSIBLE, learned_from="…")
        result = learner.ask(vzorky.NEMUZE_PETR_PRIJIT, "Petr nemůže přijít.")
        self.assertEqual(result.candidate.kind, "modal_query")
        self.assertEqual(result.modal["operation"], "impossible")

    def test_lifecycle_a_odvolani(self):
        learner = make_learner()
        learner.teach_pattern(StructuralSignature("moci", has_xcomp=True),
                              Operation.POSSIBLE, learned_from="…")
        self.assertEqual(learner.confirm_pattern("moci").status,
                         PatternStatus.CONFIRMED)
        learner.revoke_pattern("moci")
        # po odvolání se systém opět doptá — operace POSSIBLE dál existuje
        result = learner.ask(vzorky.MUZE_AUTO_JET, "Auto může jet na silnici.")
        self.assertEqual(result.candidate.kind, "needs_pattern")


class TestModalSemantics(unittest.TestCase):
    def _programmer_musician_kb(self):
        """Petr je programátor NEBO hudebník; v obou je člověk."""
        kb = KnowledgeBase()
        for name in ("programator", "hudebnik", "clovek"):
            kb.declare_relation(Relation(name, 1))
        petr = Entity("petr")
        kb.declare_domain(Domain("osoby", (petr,)))
        DEF = Provenance(LEVEL_DEFINITION,
                         Evidence(EvidenceKind.USER_ASSERTION))
        prog = Atom(kb.relation("programator"), (petr,))
        hud = Atom(kb.relation("hudebnik"), (petr,))
        clov = Atom(kb.relation("clovek"), (petr,))
        # buď/nebo (exkluzivně) + v obou případech člověk
        kb.add_constraint(ExpressionConstraint(
            disj(conj(AtomRef(prog), Not(AtomRef(hud))),
                 conj(Not(AtomRef(prog)), AtomRef(hud)))), DEF)
        kb.add_constraint(ExpressionConstraint(AtomRef(clov)), DEF)
        return kb, prog, hud, clov

    def test_moznost_nutnost_nemoznost(self):
        kb, prog, hud, clov = self._programmer_musician_kb()
        # Může být Petr programátor? → ano (∃ model)
        _, _, a, _ = _run_modal(kb, (prog,), AtomRef(prog),
                                Operation.POSSIBLE, negated=False)
        self.assertTrue(a)
        # Musí být Petr programátor? → ne (∃ model, kde není)
        _, res, a, _ = _run_modal(kb, (prog,), AtomRef(prog),
                                  Operation.NECESSARY, negated=False)
        self.assertFalse(a)
        self.assertIsNotNone(res.counterexample)   # protipříklad existuje
        # Musí být Petr člověk? → ano (∀ model)
        _, _, a, _ = _run_modal(kb, (clov,), AtomRef(clov),
                                Operation.NECESSARY, negated=False)
        self.assertTrue(a)

    def test_nemoznost_pri_vyloučeni(self):
        kb, prog, hud, clov = self._programmer_musician_kb()
        # přidáme: Petr je programátor  ⇒ hudebník je nemožný
        kb.assert_candidate(Assertion(
            Literal(prog), Evidence(EvidenceKind.USER_ASSERTION),
            LEVEL_DOCUMENTED))
        _, _, a, _ = _run_modal(kb, (hud,), AtomRef(hud),
                                Operation.IMPOSSIBLE, negated=False)
        self.assertTrue(a)


if __name__ == "__main__":
    unittest.main()
