"""Testy vztahových vazeb — kroky A (definice) a E (derivace) návrhu
docs/rozsireni-otazky.md. Zmražená data sdílená s test_dialog
(„Dálnice je silnice.") a test_graph.
"""

import unittest

from cb_field.corpus import Corpus
from cb_field.graph import FactGraph
from cb_field.registry import VerticalRegistry
from cb_field.relations import DEFINITION_WEIGHT, definition_links, \
    derivation_links, ensure_definition
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


class TestDerivacniVazby(unittest.TestCase):
    """Krok E: derivace jako KMEN × PŘEKRYV sousedství — vážený
    součin, ne práh (sonda: překryv sám nestačí, zpěv×zpívat ≈
    náhoda; kmen sám by páral pes×peří)."""

    def _tok(self, id, form, lemma, upos, head, deprel):
        from cb_udpipe import Token
        return Token(id=id, form=form, lemma=lemma, upos=upos, xpos="",
                     feats=None, head=head, deprel=deprel, deps=None,
                     misc=None)

    def test_kmen_a_prekryv_daji_vazenou_vazbu(self):
        graph = FactGraph()
        # rychlost—{klesnout, limit}; rychlostní—{limit} → překryv 1,0
        graph.add_sentence(_Sentence((
            self._tok(1, "Rychlost", "rychlost", "NOUN", 3, "nsubj"),
            self._tok(2, "limitu", "limit", "NOUN", 1, "nmod"),
            self._tok(3, "klesla", "klesnout", "VERB", 0, "root"))))
        graph.add_sentence(_Sentence((
            self._tok(1, "rychlostní", "rychlostní", "ADJ", 2, "amod"),
            self._tok(2, "limit", "limit", "NOUN", 0, "root"))))
        # planeta—planetka: dlouhý kmen bez společného souseda →
        # slabá vazba jen z kmene
        graph.add_sentence(_Sentence((
            self._tok(1, "Planeta", "planeta", "NOUN", 2, "nsubj"),
            self._tok(2, "obíhá", "obíhat", "VERB", 0, "root"))))
        graph.add_sentence(_Sentence((
            self._tok(1, "Planetka", "planetka", "NOUN", 2, "nsubj"),
            self._tok(2, "letěla", "letět", "VERB", 0, "root"))))
        # naléhavý—náledí: po složení diakritiky kmen jen 4 znaky →
        # žádný pár (zavržená v2 je pářila)
        graph.add_sentence(_Sentence((
            self._tok(1, "naléhavý", "naléhavý", "ADJ", 2, "amod"),
            self._tok(2, "případ", "případ", "NOUN", 0, "root"))))
        graph.add_sentence(_Sentence((
            self._tok(1, "náledí", "náledí", "NOUN", 2, "nsubj"),
            self._tok(2, "klouzalo", "klouzat", "VERB", 0, "root"))))
        registry = VerticalRegistry(anchors=False)
        derivation_links(graph, registry)
        silna = registry.get_link("WORD=NOUN:rychlost",
                                  "WORD=ADJ:rychlostní")
        slaba = registry.get_link("WORD=NOUN:planeta",
                                  "WORD=NOUN:planetka")
        self.assertIsNotNone(silna)
        self.assertEqual(silna[1], "derivace")
        self.assertIsNotNone(slaba)
        self.assertGreater(silna[0], slaba[0])     # překryv zesiluje
        self.assertGreater(slaba[0], 0.0)          # kmen sám dá slabou
        self.assertIsNone(registry.get_link("WORD=ADJ:naléhavý",
                                            "WORD=NOUN:náledí"))


class TestCilenaDerivace(unittest.TestCase):

    def test_around_omezi_parovani_na_okoli_otazky(self):
        # derivace plošně v L stojí přesnost (naměřeno −3,3 b) —
        # cílená varianta páruje jen kmeny slov otázky/expanze
        graph = FactGraph()
        tok = TestDerivacniVazby._tok
        graph.add_sentence(_Sentence((
            tok(self, 1, "Rychlost", "rychlost", "NOUN", 3, "nsubj"),
            tok(self, 2, "limitu", "limit", "NOUN", 1, "nmod"),
            tok(self, 3, "klesla", "klesnout", "VERB", 0, "root"))))
        graph.add_sentence(_Sentence((
            tok(self, 1, "rychlostní", "rychlostní", "ADJ", 2, "amod"),
            tok(self, 2, "limit", "limit", "NOUN", 0, "root"))))
        graph.add_sentence(_Sentence((
            tok(self, 1, "Planeta", "planeta", "NOUN", 2, "nsubj"),
            tok(self, 2, "obíhá", "obíhat", "VERB", 0, "root"))))
        graph.add_sentence(_Sentence((
            tok(self, 1, "Planetka", "planetka", "NOUN", 2, "nsubj"),
            tok(self, 2, "letěla", "letět", "VERB", 0, "root"))))
        registry = VerticalRegistry(anchors=False)
        derivation_links(graph, registry, around=("rychlost",))
        self.assertIsNotNone(registry.get_link(
            "WORD=NOUN:rychlost", "WORD=ADJ:rychlostní"))
        self.assertIsNone(registry.get_link(
            "WORD=NOUN:planeta", "WORD=NOUN:planetka"))  # mimo okolí


class TestFixaceSlovniku(unittest.TestCase):

    def test_slovnikova_definice_se_fixuje_na_disk(self):
        import json
        import tempfile
        from pathlib import Path
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(KREST))
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "korpus-401.json"
            ensure_definition("WORD=NOUN:dálnice", corpus, FactGraph(),
                              _Parser(),
                              lookup=lambda t: "Dálnice je silnice.",
                              store=store)
            data = json.loads(store.read_text(encoding="utf-8"))
            self.assertEqual(data["format_version"], 1)
            self.assertEqual(data["blocks"][0]["text"],
                             "Dálnice je silnice.")
            # druhé heslo se PŘIPÍŠE, soubor se nepřepisuje
            ensure_definition("WORD=NOUN:vesmír", corpus, FactGraph(),
                              _Parser(),
                              lookup=lambda t: "Dálnice je silnice.",
                              store=store)
            data = json.loads(store.read_text(encoding="utf-8"))
            self.assertEqual(len(data["blocks"]), 2)


class _Parser:
    """Atrapa: text rozpadne na zmraženou větu „Dálnice je silnice."."""

    def parse(self, text):
        class _Result:
            sentences = [_Sentence(DALNICE)]
        return _Result()


class TestEnsureDefinition(unittest.TestCase):
    """Krok B: definici si systém opatří sám, třístupňově — korpus →
    slovník/Wikipedie (offline-first fixace) → dialog."""

    def _setup(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(KREST))
        return corpus, FactGraph()

    def test_slovnikova_definice_jde_standardni_cestou(self):
        corpus, graph = self._setup()
        calls = []

        def lookup(term):
            calls.append(term)
            return "Dálnice je silnice."

        before = len(corpus)
        outcome = ensure_definition("WORD=NOUN:dálnice", corpus, graph,
                                    _Parser(), lookup=lookup)
        self.assertEqual(outcome, "slovnik")
        self.assertEqual(calls, ["dálnice"])
        self.assertEqual(len(corpus), before + 1)      # věta v korpusu
        self.assertEqual(corpus.registry.get_link(
            "WORD=NOUN:dálnice", "WORD=NOUN:silnice"),
            (DEFINITION_WEIGHT, "definice"))
        self.assertIn("slovnik", {src for _s, _d, _r, _w, src
                                  in graph.edges()})    # hrany značené

    def test_existujici_definice_nesaha_na_sit(self):
        corpus, graph = self._setup()
        corpus.add_sentence(_Sentence(DALNICE))
        definition_links(corpus, corpus.registry)

        def lookup(term):
            raise AssertionError("lookup se nesmí volat")

        outcome = ensure_definition("WORD=NOUN:dálnice", corpus, graph,
                                    _Parser(), lookup=lookup)
        self.assertEqual(outcome, "korpus")

    def test_bez_definice_zbyva_dialog(self):
        corpus, graph = self._setup()
        before = len(corpus)
        outcome = ensure_definition("WORD=NOUN:dálnice", corpus, graph,
                                    _Parser(), lookup=lambda term: None)
        self.assertEqual(outcome, "dialog")
        self.assertEqual(len(corpus), before)          # nic se nevložilo


if __name__ == "__main__":
    unittest.main()
