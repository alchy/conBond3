"""Testy promočního cyklu — výměna vstupní vrstvy a její vratnost.

Měřič i přeučení se předávají parametrem (§ 3), takže se cyklus dá
otestovat bez učení i bez etalonu: atrapa vrátí čísla, která test chce.
"""

import unittest

from cb_bond import KnowledgeGraph, PromotionCycle
from cb_bond.tests.vzorky import ELEKTROMOTOR, GRAVITACE, KRESTA, SYNAGOGA
from cb_field import Corpus


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


class _Merice:
    """Atrapa měřiče: vrací předem dané hodnoty, počítá volání."""

    def __init__(self, *hodnoty):
        self.hodnoty = list(hodnoty)
        self.calls = 0

    def __call__(self, corpus):
        self.calls += 1
        return self.hodnoty[min(self.calls - 1, len(self.hodnoty) - 1)]


class TestPrijeti(unittest.TestCase):

    def test_lepsi_mereni_se_prijme_a_osa_zustane(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        graf = _graf(corpus)
        merice = _Merice({"presnost": 0.2}, {"presnost": 0.4})
        preuceno = []
        cyklus = PromotionCycle(merice, preuceno.append, limit=3)

        vysledek = cyklus.run(corpus, graf)

        self.assertTrue(vysledek.accepted)
        self.assertTrue(vysledek.retrained)
        self.assertEqual(corpus.registry.axis_version, 1)
        self.assertEqual(len(preuceno), 1)
        self.assertEqual(vysledek.before, {"presnost": 0.2})
        self.assertEqual(vysledek.after, {"presnost": 0.4})

    def test_prijata_promoce_rozsviti_CUSTOM_v_korpusu(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        graf = _graf(corpus)
        cyklus = PromotionCycle(_Merice({"p": 0.0}, {"p": 1.0}),
                                lambda c: None, limit=3)

        vysledek = cyklus.run(corpus, graf)

        promovane = corpus.registry.custom_axes
        self.assertTrue(promovane)
        # aspoň jedno pole nese CUSTOM= osu promovaného slova
        osy = {klic for pole in corpus for radek in pole.complete
               for klic in radek if klic.startswith("CUSTOM=")}
        self.assertTrue(osy)
        self.assertEqual(vysledek.axis_changes["pridano"], len(promovane))


class TestVraceni(unittest.TestCase):

    def test_horsi_metrika_vrati_stav_BIT_PO_BITU(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        graf = _graf(corpus)
        pred_verzi = corpus.registry.axis_version
        cyklus = PromotionCycle(_Merice({"presnost": 0.5}, {"presnost": 0.3}),
                                lambda c: None, limit=3)

        vysledek = cyklus.run(corpus, graf)

        self.assertFalse(vysledek.accepted)
        self.assertEqual(corpus.registry.axis_version, pred_verzi)
        self.assertEqual(corpus.registry.custom_axes, ())
        osy = {klic for pole in corpus for radek in pole.complete
               for klic in radek if klic.startswith("CUSTOM=")}
        self.assertEqual(osy, set())     # koše jsou zpátky bez CUSTOM=

    def test_staci_JEDNA_horsi_metrika(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        graf = _graf(corpus)
        cyklus = PromotionCycle(
            _Merice({"presnost": 0.2, "dosah": 10},
                    {"presnost": 0.9, "dosah": 8}),
            lambda c: None, limit=3)

        self.assertFalse(cyklus.run(corpus, graf).accepted)

    def test_shodne_metriky_se_prijmou(self):
        # nezhoršilo se nic → promoce projde (vratná je pořád)
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        graf = _graf(corpus)
        cyklus = PromotionCycle(_Merice({"p": 0.5}, {"p": 0.5}),
                                lambda c: None, limit=3)

        self.assertTrue(cyklus.run(corpus, graf).accepted)


class TestBezZmenyOsy(unittest.TestCase):

    def test_stejne_obsazeni_se_NEPREUCUJE(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        graf = _graf(corpus)
        preuceno = []
        cyklus = PromotionCycle(_Merice({"p": 0.5}), preuceno.append, limit=3)
        cyklus.run(corpus, graf)
        preuceno.clear()

        druhy = cyklus.run(corpus, graf)

        self.assertTrue(druhy.accepted)
        self.assertFalse(druhy.retrained)
        self.assertEqual(preuceno, [])
        self.assertEqual(druhy.axis_changes["pridano"], 0)

    def test_bez_zmeny_osy_se_ani_nemeri_podruhe(self):
        # měření je drahé; když se osa nehnula, není co porovnávat
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        graf = _graf(corpus)
        merice = _Merice({"p": 0.5})
        cyklus = PromotionCycle(merice, lambda c: None, limit=3)
        cyklus.run(corpus, graf)
        volani_po_prvnim = merice.calls

        cyklus.run(corpus, graf)

        self.assertEqual(merice.calls, volani_po_prvnim + 1)


class TestUvolneniSlotu(unittest.TestCase):

    def test_uvolneny_slot_prijde_i_o_hrany(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        graf = _graf(corpus)
        cyklus = PromotionCycle(_Merice({"p": 0.0}, {"p": 1.0}), lambda c: None,
                                limit=1)
        cyklus.run(corpus, graf)
        obsazeny = corpus.registry.custom_axes[0]
        corpus.registry.link("QLEM=ADV:kde", f"CUSTOM={obsazeny}", 0.5)

        # jiný limit → jiné obsazení; starý slot se uvolní i s hranou
        corpus.add_sentence(ELEKTROMOTOR)
        PromotionCycle(_Merice({"p": 0.0}, {"p": 1.0}), lambda c: None,
                       limit=4).run(corpus, _graf(corpus))

        if obsazeny not in corpus.registry.custom_axes:
            self.assertIsNone(corpus.registry.get_link(
                "QLEM=ADV:kde", f"CUSTOM={obsazeny}"))


if __name__ == "__main__":
    unittest.main()
