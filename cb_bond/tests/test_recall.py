"""Testy předvýběru grafem — lemata otázky → uzly → záře → věty.

Graf nese STRUKTURU, kterou pytel nemá: když se rozsvítí *Ježíš*
a *pokřtěný*, záře po hranách dojde k *Jordánu*, protože na *pokřtěném*
opravdu visí. Pytel vidí jen množinu slov a Jordán s Galilejí jsou
v něm k nerozeznání.
"""

import unittest

from cb_bond import GraphRecall, KnowledgeGraph
from cb_bond.tests.vzorky import (GRAVITACE, KRESTA, OTAZKA_KREST, SYNAGOGA,
                                  VEZENI)
from cb_field import Corpus, SentenceField


def _korpus(*vety):
    corpus = Corpus(r=1)
    for veta in vety:
        corpus.add_sentence(veta)
    return corpus


def _graf(corpus):
    graf = KnowledgeGraph()
    for pole in corpus:
        graf.add_sentence(pole)
    return graf


def _otazka(corpus, veta=OTAZKA_KREST):
    return SentenceField.from_sentence(veta, r=corpus.r,
                                       registry=corpus.registry)


class TestPredvyber(unittest.TestCase):

    def test_najde_vetu_pres_lemata_otazky(self):
        corpus = _korpus(SYNAGOGA, KRESTA, GRAVITACE)
        recall = GraphRecall(_graf(corpus), corpus)

        vety = recall.sentences(_otazka(corpus), top_k=1)

        self.assertEqual(vety, (1,))          # věta o křtu

    def test_vraci_nejvyse_top_k_vet(self):
        corpus = _korpus(SYNAGOGA, KRESTA, GRAVITACE)
        recall = GraphRecall(_graf(corpus), corpus)

        self.assertEqual(len(recall.sentences(_otazka(corpus), top_k=2)), 2)

    def test_otazka_bez_znameho_lemmatu_nevrati_nic(self):
        corpus = _korpus(GRAVITACE)
        recall = GraphRecall(_graf(corpus), corpus)

        self.assertEqual(recall.sentences(_otazka(corpus)), ())

    def test_serazeno_sestupne_podle_zare(self):
        corpus = _korpus(SYNAGOGA, KRESTA, GRAVITACE)
        recall = GraphRecall(_graf(corpus), corpus)
        otazka = _otazka(corpus)

        vety = recall.sentences(otazka)
        skore = recall.sentence_scores(otazka)

        hodnoty = [skore[v] for v in vety]
        self.assertEqual(hodnoty, sorted(hodnoty, reverse=True))


class TestZare(unittest.TestCase):

    def test_zare_dojde_po_hrane_na_soused_uzel(self):
        # otázka nese Ježíš a pokřtěný; Jordán v ní NENÍ, ale visí
        # na pokřtěném — záře k němu musí dojít
        corpus = _korpus(KRESTA)
        recall = GraphRecall(_graf(corpus), corpus, depth=1)

        jas = recall.glow(_otazka(corpus))

        self.assertIn("PROPN:Jordán", jas)
        self.assertGreater(jas["PROPN:Jordán"], 0.0)

    def test_hloubka_rozhoduje_kam_zare_dojde(self):
        corpus = _korpus(KRESTA)
        recall_1 = GraphRecall(_graf(corpus), corpus, depth=1)
        recall_2 = GraphRecall(_graf(corpus), corpus, depth=2)

        # „den" visí na „přijít", to na „pokřtěném" — dva skoky
        self.assertNotIn("NOUN:den", recall_1.glow(_otazka(corpus)))
        self.assertIn("NOUN:den", recall_2.glow(_otazka(corpus)))

    def test_uzel_s_mnoha_hranami_rozdava_MENE(self):
        # podíl hrany na sousedových hranách: rozcestí rozdělí záři,
        # slepá ulice předá všechno
        corpus = _korpus(KRESTA)
        recall = GraphRecall(_graf(corpus), corpus, depth=1)

        jas = recall.glow(_otazka(corpus))

        # pokřtěný má 3 hrany, přijít 5 → z pokřtěného přiteče víc
        self.assertGreater(jas["PROPN:Jordán"], jas["NOUN:den"] if
                           "NOUN:den" in jas else 0.0)

    def test_zare_ze_dvou_lemat_se_SCITA(self):
        # uzel, ke kterému vede cesta od víc lemat otázky, je nosnější
        corpus = _korpus(KRESTA)
        recall = GraphRecall(_graf(corpus), corpus, depth=1)

        jedno = GraphRecall(_graf(corpus), corpus, depth=1)._zar(
            {"ADJ:pokřtěný": 1.0})
        obe = jedno_a_druhe = recall._zar(
            {"ADJ:pokřtěný": 1.0, "PROPN:Jan": 1.0})

        self.assertGreater(obe["ADJ:pokřtěný"], jedno.get("ADJ:pokřtěný", 0.0))


class TestSkoreVety(unittest.TestCase):

    def test_veta_se_skoruje_MAXIMEM_ne_souctem(self):
        # součet zvýhodňuje dlouhé věty — týž degenerát, kvůli kterému
        # je čtení gaussovské (naměřeno: max 25/30, součet 23/30)
        corpus = _korpus(KRESTA, SYNAGOGA)
        recall = GraphRecall(_graf(corpus), corpus, depth=1)
        otazka = _otazka(corpus)

        jas = recall.glow(otazka)
        skore = recall.sentence_scores(otazka)

        uzly_krestni = _graf(corpus).sentence_nodes(0)
        self.assertAlmostEqual(
            skore[0], max(jas.get(u, 0.0) for u in uzly_krestni), places=6)

    def test_slova_otazky_zari_taky(self):
        # uzel, který je přímo v otázce, startuje na 1,0
        corpus = _korpus(KRESTA)
        recall = GraphRecall(_graf(corpus), corpus, depth=0)

        jas = recall.glow(_otazka(corpus))

        self.assertAlmostEqual(jas["ADJ:pokřtěný"], 1.0)
        self.assertAlmostEqual(jas["PROPN:Ježíš"], 1.0)


class TestStopSlova(unittest.TestCase):

    def test_predvyber_stoji_na_uzlech_grafu_ne_na_vsech_slovech(self):
        # graf uzly zavřených tříd nemá a je to naměřené rozhodnutí:
        # s předložkami klesne recall 54 → 48/117, se zájmeny na 27/117
        corpus = _korpus(KRESTA, VEZENI)
        recall = GraphRecall(_graf(corpus), corpus)

        jas = recall.glow(_otazka(corpus))

        self.assertFalse([k for k in jas if k.startswith(("ADP:", "AUX:",
                                                          "PRON:", "DET:"))])


if __name__ == "__main__":
    unittest.main()
