"""Testy učení z dialogu — celá pipeline zadání § 9 nad zmraženými rozbory."""
import dataclasses
import unittest

from cb_logic import (Accepted, Conflicted, KnowledgeBase, Truth)
from cb_interpret.learner import DialogueLearner
from cb_interpret.tests import vzorky
from cb_interpret.tests import vzorky_struct as vs


def make_learner():
    return DialogueLearner(KnowledgeBase())


class TestLearn(unittest.TestCase):
    def test_fakt_pravidlo_inference(self):
        learner = make_learner()
        r1 = learner.learn(vzorky.KAZDY_PROGRAMATOR,
                           "Každý programátor je člověk.")
        self.assertIsInstance(r1.outcome, Accepted)
        r2 = learner.learn(vzorky.PETR_PROGRAMATOR, "Petr je programátor.")
        self.assertIsInstance(r2.outcome, Accepted)
        # inference po druhé větě odvodila člověk(petr)
        derived = [str(l.atom.relation.name) for l in r2.inference.new_facts]
        self.assertIn("člověk", derived)

    def test_otazka_a_neinterpretovatelne_nemeni_bazi(self):
        learner = make_learner()
        r1 = learner.learn(vzorky.JE_PETR_CLOVEK, "Je Petr člověk?")
        r2 = learner.learn(vzorky.KOLIK_HODIN, "Kolik je hodin?")
        self.assertIsNone(r1.outcome)
        self.assertIsNone(r2.outcome)
        self.assertEqual(learner.kb.own_facts(), ())

    def test_konflikt_se_hlasi(self):
        learner = make_learner()
        learner.learn(vzorky.PETR_PROGRAMATOR, "Petr je programátor.")
        negated_cop = tuple(
            dataclasses.replace(t, feats=dict(t.feats or {},
                                              Polarity="Neg"))
            if t.deprel == "cop" else t
            for t in vzorky.PETR_PROGRAMATOR)
        result = learner.learn(negated_cop, "Petr není programátor.")
        self.assertIsInstance(result.outcome, Conflicted)
        self.assertEqual(len(learner.kb.conflicts), 1)


class TestAsk(unittest.TestCase):
    def test_plny_kruh_slovesna_trida(self):
        # „Ptáci létají." → pravidlo; „Létají ptáci?" → doptání → obě
        # čtení TRUE (třída přes probe, instance přes presupozici)
        learner = make_learner()
        r = learner.learn(vs.PTACI_LETAJI, "Ptáci létají.")
        self.assertEqual(r.candidate.kind, "rule")
        result = learner.ask(vs.LETAJI_PTACI, "Létají ptáci?")
        self.assertEqual(result.candidate.kind, "reference_ambiguous")
        self.assertEqual(result.reference.subject_lemma, "pták")
        self.assertEqual(
            learner.resolve_reference(result.candidate, "class").truth,
            Truth.TRUE)
        self.assertEqual(
            learner.resolve_reference(result.candidate, "instance").truth,
            Truth.TRUE)

    def test_plny_kruh_genitiv(self):
        # „Česka" se cestou učení ani dotazu nikde neztratí (4.1.2)
        learner = make_learner()
        r = learner.learn(vs.PRAHA_MESTO_CESKA,
                          "Praha je hlavní město Česka.")
        self.assertEqual(r.candidate.kind, "fact")
        self.assertEqual(r.accepted, 3)
        result = learner.ask(vs.JE_PRAHA_MESTO_CESKA,
                             "Je Praha hlavní město Česka?")
        self.assertEqual(result.truth, Truth.TRUE)

    def test_nevim_s_chybejici_premisou_pak_ano_s_vysvetlenim(self):
        learner = make_learner()
        learner.learn(vzorky.KAZDY_PROGRAMATOR,
                      "Každý programátor je člověk.")
        before = learner.ask(vzorky.JE_PETR_CLOVEK, "Je Petr člověk?")
        self.assertEqual(before.truth, Truth.UNKNOWN)
        missing = [lit.atom.relation.name
                   for s in before.why_not.suggestions for lit in s.missing]
        self.assertIn("programátor", missing)   # formální podklad doptání

        learner.learn(vzorky.PETR_PROGRAMATOR, "Petr je programátor.")
        after = learner.ask(vzorky.JE_PETR_CLOVEK, "Je Petr člověk?")
        self.assertEqual(after.truth, Truth.TRUE)
        self.assertEqual(after.explanations[0].kind, "derived")

    def test_ask_je_cteci(self):
        learner = make_learner()
        learner.ask(vzorky.JE_PETR_CLOVEK, "Je Petr člověk?")
        self.assertEqual(learner.kb.own_facts(), ())
        self.assertEqual(learner.kb.rules, [])

    def test_zaporna_odpoved(self):
        learner = make_learner()
        learner.learn(vzorky.PETR_NENI_STUDENT, "Petr není student.")
        question = tuple(vzorky.PETR_NENI_STUDENT)  # dotaz na kladný literál
        # „Je Petr student?" — sestrojíme z faktové věty otazníkem
        positive_cop = tuple(
            dataclasses.replace(t, feats=dict(t.feats or {}, Polarity="Pos"))
            if t.deprel == "cop" else t for t in question)
        result = learner.ask(positive_cop, "Je Petr student?")
        self.assertEqual(result.truth, Truth.FALSE)
        self.assertFalse(result.explanations[0].literal.positive)


if __name__ == "__main__":
    unittest.main()
