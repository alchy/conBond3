"""Testy logických operací mezi koši (spec docs/query-basket.md § 6)."""

import unittest

from cb_field import SentenceField, match
from cb_field.query import (AND, NOT, OR, activation_field,
                            sentence_activation, span)
from cb_field.tests.test_matching import (BEZELA2, KAM, KOCKA2, OTAZNIK,
                                          PES2, SEL2, _scena)


class TestOperaceMeziKosi(unittest.TestCase):
    """Operace jsou vahami nad výsledky, ne filtrem nad kandidáty."""

    def setUp(self):
        self.corpus = _scena()
        self.kam_pes = match(SentenceField(
            (KAM, SEL2, PES2, OTAZNIK), r=1, registry=self.corpus.registry,
            source="Kam šel pes?"), self.corpus)
        self.kam_kocka = match(SentenceField(
            (KAM, BEZELA2, KOCKA2, OTAZNIK), r=1,
            registry=self.corpus.registry, source="Kam běžela kočka?"),
            self.corpus)

    def test_and_nezahazuje_kandidaty(self):
        # průnik nad TÝMIŽ kandidáty — každý token zůstává kandidátem
        spolu = AND(self.kam_pes, self.kam_kocka)
        self.assertEqual(len(spolu.candidates),
                         len(self.kam_pes.candidates))

    def test_not_obraci_poradi(self):
        obraceno = NOT(self.kam_pes)
        self.assertEqual(obraceno.candidates[0].token.form,
                         self.kam_pes.candidates[-1].token.form)
        self.assertAlmostEqual(obraceno.candidates[0].score,
                               -self.kam_pes.candidates[-1].score, places=6)

    def test_and_s_negaci_je_vyraz(self):
        """AND(a, NOT(b)) — co odpovídá první otázce a druhé ne."""
        vyraz = AND(self.kam_pes, NOT(self.kam_kocka))
        self.assertTrue(vyraz.candidates)
        # výsledek je zase koš, dá se řetězit dál
        self.assertTrue(OR(vyraz, self.kam_pes).candidates)

    def test_or_scita_skore(self):
        soucet = OR(self.kam_pes, self.kam_kocka)
        klic = (soucet.candidates[0].sentence, soucet.candidates[0].center)
        a = next(c.score for c in self.kam_pes.candidates
                 if (c.sentence, c.center) == klic)
        b = next(c.score for c in self.kam_kocka.candidates
                 if (c.sentence, c.center) == klic)
        self.assertAlmostEqual(soucet.candidates[0].score, a + b, places=6)

    def test_odpoved_muze_byt_veta_skupina_i_pole(self):
        """Token, skupina a věta jsou jen různá rozlišení téhož pole."""
        veta, aktivace = activation_field(self.kam_pes)
        self.assertEqual(len(aktivace), len(veta.tokens))
        # nejaktivnější řádek pole == nejlepší kandidát
        self.assertEqual(int(aktivace.argmax()), self.kam_pes.best.center)
        # věta nese PRŮMĚRNOU kladnou aktivaci svých středů — prostý
        # součet by měřil délku věty, ne shodu (§ 21)
        _v, prumer, kandidati = sentence_activation(self.kam_pes)[0]
        self.assertAlmostEqual(
            prumer, float(aktivace[aktivace > 0].sum()) / len(kandidati),
            places=5)
        # surový součet jde vyžádat, ale není výchozí
        _v, soucet, _k = sentence_activation(self.kam_pes, mean=False)[0]
        self.assertGreater(soucet, prumer)
        # skupina slov je okno nad týmž polem
        _v, od, do, sila = span(self.kam_pes, width=2)[0]
        self.assertEqual(do - od, 2)
        self.assertGreater(sila, 0)


if __name__ == "__main__":
    unittest.main()
