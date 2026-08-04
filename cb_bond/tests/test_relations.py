"""Testy těžby vztahů — definice z kopule a derivace z kmene.

Čísla jsou ze zadání § krok 7 a jdou spočítat ručně: rychlost(8)
× rychlostní(10) dá kmen 8, sílu 0,8 a váhu 0,7·(0,8/2 + 0/2) = 0,28.
"""

import unittest

from cb_bond import KnowledgeGraph, RelationMiner
from cb_bond.relations import kmen
from cb_bond.tests.vzorky import (ELEKTROMOTOR, GALAXIE, GRAVITACE, KRESTA,
                                  PELYNEK, SYNAGOGA, VEZENI)
from cb_field import Corpus


def _korpus(*vety):
    corpus = Corpus(r=1)
    for veta in vety:
        corpus.add_sentence(veta)
    return corpus


class TestDefinice(unittest.TestCase):

    def test_kopula_s_nominativem_dava_definicni_vazbu(self):
        corpus = _korpus(GRAVITACE)
        miner = RelationMiner()

        pocet = miner.mine_definitions(corpus, corpus.registry)

        self.assertEqual(pocet, 1)
        self.assertAlmostEqual(
            corpus.registry.get_link("WORD=NOUN:gravitace", "WORD=NOUN:síla"),
            0.7, places=6)

    def test_lokativni_kopula_definice_neni(self):
        # „Muž byl ve vězení" říká, KDE muž byl, ne co muž je —
        # rozdíl nese pád rootu, ne přítomnost kopule
        corpus = _korpus(VEZENI)
        miner = RelationMiner()

        self.assertEqual(miner.mine_definitions(corpus, corpus.registry), 0)
        self.assertIsNone(
            corpus.registry.get_link("WORD=NOUN:muž", "WORD=NOUN:vězení"))

    def test_vlastni_jmeno_smi_byt_definiens(self):
        # „Jméno té hvězdy je Pelyněk." — kdo připustí jen NOUN v rootu,
        # přijde o celou třídu definic (91 vazeb místo 94 na 12 258 větách)
        corpus = _korpus(PELYNEK)
        miner = RelationMiner()

        self.assertEqual(miner.mine_definitions(corpus, corpus.registry), 1)
        self.assertAlmostEqual(
            corpus.registry.get_link("WORD=NOUN:jméno",
                                     "WORD=PROPN:Pelyněk"), 0.7, places=6)

    def test_smycka_v_ose_se_nezaklada(self):
        # „Trpasličí galaxie je malá galaxie." — definiční tvar, ale obě
        # strany mají TÉŽ lemma; vazba by aktivaci zesilovala samu ze sebe
        corpus = _korpus(GALAXIE)
        miner = RelationMiner()

        self.assertEqual(miner.mine_definitions(corpus, corpus.registry), 0)

    def test_veta_bez_kopule_definice_neni(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        miner = RelationMiner()

        self.assertEqual(miner.mine_definitions(corpus, corpus.registry), 0)

    def test_definice_se_pamatuji_i_se_zdrojem(self):
        corpus = _korpus(GRAVITACE, ELEKTROMOTOR)
        miner = RelationMiner()

        miner.mine_definitions(corpus, corpus.registry)

        self.assertEqual(
            {(src, dst) for src, dst, _, _ in miner.definitions},
            {("WORD=NOUN:gravitace", "WORD=NOUN:síla"),
             ("WORD=NOUN:elektromotor", "WORD=NOUN:stroj")})
        self.assertEqual({zdroj for *_, zdroj in miner.definitions},
                         {"definition"})

    def test_opakovana_tezba_vazby_nezdvoji(self):
        corpus = _korpus(GRAVITACE)
        miner = RelationMiner()

        prvni = miner.mine_definitions(corpus, corpus.registry)
        druhy = miner.mine_definitions(corpus, corpus.registry)

        self.assertEqual(prvni, 1)
        self.assertEqual(druhy, 0)      # podruhé už není co přidat


class TestKmen(unittest.TestCase):

    def test_kmen_se_pocita_bez_diakritiky(self):
        self.assertEqual(kmen("rychlost", "rychlostní"), "rychlost")
        self.assertEqual(kmen("kámen", "kamení"), "kamen")

    def test_kratky_kmen_par_nedava(self):
        # naléhavý × náledí: bez diakritiky nalehavy × naledi → „nale",
        # tedy 4 znaky. Pod hranicí 5 — a je to přesně ten pár, který
        # by jinak spojil dvě nesouvisející slova.
        self.assertEqual(kmen("naléhavý", "náledí"), "nale")


class TestDerivace(unittest.TestCase):

    def test_dvojice_se_spolecnym_kmenem_dostane_vazbu(self):
        graf, registr = _graf_s_uzly("NOUN:rychlost", "ADJ:rychlostní")
        miner = RelationMiner()

        pocet = miner.mine_derivations(graf, registr)

        self.assertEqual(pocet, 1)
        # kmen 8 → síla 8/10 = 0,8; překryv sousedství 0
        # váha = 0,7·(0,8/2 + 0/2) = 0,28
        self.assertAlmostEqual(
            registr.get_link("WORD=NOUN:rychlost", "WORD=ADJ:rychlostní"),
            0.28, places=4)

    def test_nesouvisejici_slova_par_nedostanou(self):
        graf, registr = _graf_s_uzly("ADJ:naléhavý", "NOUN:náledí")
        miner = RelationMiner()

        self.assertEqual(miner.mine_derivations(graf, registr), 0)

    def test_kamen_a_kameni_par_dostanou(self):
        graf, registr = _graf_s_uzly("NOUN:kámen", "NOUN:kamení")
        miner = RelationMiner()

        self.assertEqual(miner.mine_derivations(graf, registr), 1)

    def test_kratsi_lemma_musi_byt_kmenem_ze_tri_ctvrtin(self):
        # „prst" × „prstenec": kmen „prst" má jen 4 znaky → pod hranicí
        graf, registr = _graf_s_uzly("NOUN:prst", "NOUN:prstenec")
        miner = RelationMiner()

        self.assertEqual(miner.mine_derivations(graf, registr), 0)

    def test_around_omezi_tezbu_na_okoli_otazky(self):
        # plošné nasazení stálo baseline 3,3 bodu — proto jen cíleně
        graf, registr = _graf_s_uzly("NOUN:rychlost", "ADJ:rychlostní",
                                     "NOUN:kámen", "NOUN:kamení")
        miner = RelationMiner()

        pocet = miner.mine_derivations(graf, registr, around={"rychlost"})

        self.assertEqual(pocet, 1)
        self.assertIsNotNone(
            registr.get_link("WORD=NOUN:rychlost", "WORD=ADJ:rychlostní"))
        self.assertIsNone(
            registr.get_link("WORD=NOUN:kámen", "WORD=NOUN:kamení"))

    def test_prekryv_sousedstvi_vahu_zvedne(self):
        graf, registr = _graf_s_uzly("NOUN:rychlost", "ADJ:rychlostní")
        # oba uzly dostanou téhož souseda → překryv 1,0
        graf._stats["NOUN:rychlost"].neighbours["VERB:jet"] = 1
        graf._stats["ADJ:rychlostní"].neighbours["VERB:jet"] = 1
        miner = RelationMiner()

        miner.mine_derivations(graf, registr)

        # váha = 0,7·(0,8/2 + 1,0/2) = 0,63
        self.assertAlmostEqual(
            registr.get_link("WORD=NOUN:rychlost", "WORD=ADJ:rychlostní"),
            0.63, places=4)


def _graf_s_uzly(*klice):
    """Graf s danými uzly a prázdný registr — bez parsování."""
    from cb_field.registry import VerticalRegistry
    graf = KnowledgeGraph()
    for klic in klice:
        graf._uzel(klic)
    return graf, VerticalRegistry()


if __name__ == "__main__":
    unittest.main()
