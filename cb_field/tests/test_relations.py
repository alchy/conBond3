"""Testy vztahových vazeb — kroky A (definice) a E (derivace) návrhu
docs/rozsireni-otazky.md. Zmražená data sdílená s test_dialog
(„Dálnice je silnice.") a test_graph.
"""

import unittest

from cb_field.corpus import Corpus
from cb_field.registry import VerticalRegistry
from cb_field.relations import DEFINITION_WEIGHT, definition_links
from cb_field.tests.test_dialog import DALNICE, OTAZKA_KREST
from cb_field.tests.test_graph import KREST, _Sentence


class TestDefinicniHrany(unittest.TestCase):
    """Krok A: kopulární vzor = vztahová vazba subjekt → predikátové
    jméno, zdroj definice. Expanze pak jde „jen maticí": šíření po
    vazbě rozšíří koš otázky bez jediné zvláštní větve."""

    def test_kopularni_veta_da_vazbu_se_zdrojem_definice(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(DALNICE))    # Dálnice je silnice.
        added = definition_links(corpus, corpus.registry)
        self.assertEqual(added, 1)
        link = corpus.registry.get_link("WORD=NOUN:dálnice",
                                        "WORD=NOUN:silnice")
        self.assertEqual(link, (DEFINITION_WEIGHT, "definice"))

    def test_lokativni_kopula_neni_definice(self):
        # „Muž byl ve vězení." — kopula s příslovečným určením místa
        # (predikát v lokálu) pojem nedefinuje; vzor žádá nominativ
        from cb_udpipe import Token
        def t(id, form, lemma, upos, feats, head, deprel):
            return Token(id=id, form=form, lemma=lemma, upos=upos,
                         xpos="", feats=feats, head=head, deprel=deprel,
                         deps=None, misc=None)
        veta = (
            t(1, "Muž", "muž", "NOUN",
              {"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
              4, "nsubj"),
            t(2, "byl", "být", "AUX", {"Tense": "Past"}, 4, "cop"),
            t(3, "ve", "v", "ADP", {"Case": "Loc"}, 4, "case"),
            t(4, "vězení", "vězení", "NOUN",
              {"Case": "Loc", "Gender": "Neut", "Number": "Sing"},
              0, "root"),
            t(5, ".", ".", "PUNCT", None, 4, "punct"),
        )
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(veta))
        self.assertEqual(definition_links(corpus, corpus.registry), 0)

    def test_nekopularni_veta_vazbu_neda(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(KREST))      # věta o křtu, bez cop
        self.assertEqual(definition_links(corpus, corpus.registry), 0)
        self.assertFalse(any(src == "definice" for _s, _d, _w, src
                             in corpus.registry.links()))

    def test_opakovane_volani_je_idempotentni(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(DALNICE))
        definition_links(corpus, corpus.registry)
        self.assertEqual(definition_links(corpus, corpus.registry), 0)

    def test_expanze_jde_siremim_po_vazbe(self):
        # koš otázky s dálnicí po jednom kroku šíření svítí i na
        # silnici — složení do koše bez zvláštního kódu (jen matice)
        import numpy as np
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(DALNICE))
        registry = corpus.registry
        definition_links(corpus, registry)
        vec = registry.vectorize({"WORD=NOUN:dálnice": 0.7})
        spread = registry.spread(vec)
        lit = registry.unvectorize(np.tanh(spread))
        self.assertIn("WORD=NOUN:silnice", lit)
        self.assertGreater(lit["WORD=NOUN:silnice"], 0.3)


if __name__ == "__main__":
    unittest.main()
