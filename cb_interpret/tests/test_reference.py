"""Testy jednotlivina vs. třída a rozřešení reference — INTERPRETATION_IR § 4–5.

Plný kruh: nauč „Auto je dopravní prostředek." (třída → pravidla), zeptej se
„Je auto dopravní prostředek?" → nejednoznačné → po volbě „třída" se ověří
arbitrární instancí (probe) a vyjde TRUE. Modifikátor „dopravní" se cestou
nikde neztratí.
"""
import unittest

from cb_logic import KnowledgeBase, Truth
from cb_interpret.learner import DialogueLearner
from cb_interpret.tests import vzorky_struct as vs


def make_learner():
    return DialogueLearner(KnowledgeBase())


class TestReferenceResolution(unittest.TestCase):
    def setUp(self):
        self.learner = make_learner()
        # třídní tvrzení → pravidla auto(X)→prostředek(X), auto(X)→dopravní(X)
        r = self.learner.learn(vs.AUTO_PROSTREDEK,
                               "Auto je dopravní prostředek.")
        self.assertEqual(r.candidate.kind, "rule")
        self.assertEqual(r.accepted, 2)          # oba konjunkty přijaty

    def test_otazka_je_nejednoznacna_a_dopta_se(self):
        result = self.learner.ask(vs.JE_AUTO_PROSTREDEK,
                                  "Je auto dopravní prostředek?")
        self.assertEqual(result.candidate.kind, "reference_ambiguous")
        self.assertIsNotNone(result.reference)
        self.assertEqual({c for c, _ in result.reference.options},
                         {"instance", "class"})

    def test_tridni_cteni_vyjde_true_pres_probe(self):
        candidate = self.learner.ask(
            vs.JE_AUTO_PROSTREDEK, "Je auto dopravní prostředek?").candidate
        result = self.learner.resolve_reference(candidate, "class")
        self.assertEqual(result.truth, Truth.TRUE)   # ∀x auto(x)→prostř.∧dopr.
        # báze se nezměnila (probe žil jen v kopii)
        self.assertNotIn("__probe__",
                         [e.id for _, e in _entities(self.learner.kb)])

    def test_instance_dedi_z_pravidel_pres_presupozici(self):
        # „konkrétní auto" JE auto už tím, jak je pojmenované — členství
        # zakládá reference sama. Doptávat se „je auto auto?" je nesmysl;
        # pravidla třídy se na referent vztahují bez další premisy.
        candidate = self.learner.ask(
            vs.JE_AUTO_PROSTREDEK, "Je auto dopravní prostředek?").candidate
        result = self.learner.resolve_reference(candidate, "instance")
        self.assertEqual(result.truth, Truth.TRUE)
        # báze se nezměnila (presupozice žila jen v kopii)
        self.assertNotIn("auto",
                         [e.id for _, e in _entities(self.learner.kb)])

    def test_instance_bez_jakekoli_znalosti_je_nevim(self):
        # prázdná báze: presupozice členství sama odpověď nedává
        learner = make_learner()
        candidate = learner.ask(
            vs.JE_AUTO_PROSTREDEK, "Je auto dopravní prostředek?").candidate
        result = learner.resolve_reference(candidate, "instance")
        self.assertEqual(result.truth, Truth.UNKNOWN)


def _entities(kb):
    out = []
    for domain in kb._domains.values():
        for m in domain.members:
            out.append((domain.name, m))
    return out


if __name__ == "__main__":
    unittest.main()
