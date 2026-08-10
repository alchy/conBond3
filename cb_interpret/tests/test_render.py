"""Testy renderování vysvětlení šablonami profilu."""
import unittest

from cb_logic import KnowledgeBase, Truth, why
from cb_interpret import cs_profile, render_explanation, render_literal, \
    render_truth
from cb_interpret.learner import DialogueLearner
from cb_interpret.tests import vzorky


class TestRender(unittest.TestCase):
    def setUp(self):
        self.profile = cs_profile()
        self.learner = DialogueLearner(KnowledgeBase(), self.profile)

    def test_literal_unarni_a_binarni(self):
        self.learner.learn(vzorky.PETR_BYDLI, "Petr bydlí v Praze.")
        self.learner.learn(vzorky.PETR_NENI_STUDENT, "Petr není student.")
        facts = {r[0].atom.relation.name: r[0]
                 for r in self.learner.kb.own_facts()}
        self.assertEqual(render_literal(facts["bydlet_v"], self.profile),
                         "petr bydlet v praha")
        self.assertEqual(render_literal(facts["student"], self.profile),
                         "petr není student")

    def test_vysvetleni_protoze_retez(self):
        self.learner.learn(vzorky.KAZDY_PROGRAMATOR,
                           "Každý programátor je člověk.")
        self.learner.learn(vzorky.PETR_PROGRAMATOR, "Petr je programátor.")
        result = self.learner.ask(vzorky.JE_PETR_CLOVEK, "Je Petr člověk?")
        text = render_explanation(result.explanations[0], self.profile)
        self.assertEqual(
            text, "petr je člověk, protože petr je programátor "
                  "(doloženo: dialog)")

    def test_truth(self):
        self.assertEqual(render_truth(Truth.UNKNOWN, self.profile), "Nevím.")


if __name__ == "__main__":
    unittest.main()
