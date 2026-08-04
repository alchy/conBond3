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


class TestGaussovskyVrchol(unittest.TestCase):
    """Krok D návrhu: věta podle VRCHOLU gaussovsky vyhlazeného pole —
    shluk souhlasných aktivací poráží osamělou špičku, i silnější.
    Přesně patologie „Máš ženu?": krátká věta s jedním tokenem vyhrává
    normalizací průměrem, gaussovský vrchol ji srovná."""

    def _result(self):
        import numpy as np
        from cb_field.field import SentenceField
        from cb_field.matching import (Candidate, MatchResult,
                                       ScoreDecomposition)
        from cb_field.tests.test_graph import KREST, _t
        dlouha = SentenceField(KREST, r=1, source="dlouhá se shlukem")
        kratka = SentenceField((
            _t(1, "Prší", "pršet", "VERB", 0, "root"),
            _t(2, ".", ".", "PUNCT", 1, "punct")), r=1,
            source="krátká špička")
        dummy = ScoreDecomposition(None, np.array([], dtype=int),
                                   np.array([]), 4)

        def cand(sentence, center, score):
            return Candidate(sentence=sentence, center=center,
                             score=score, meet_score=0, cover_score=0,
                             fit_score=0, topic_score=0, given_score=0,
                             decomposition=dummy)

        candidates = [cand(dlouha, 11, 1.0), cand(dlouha, 12, 1.0),
                      cand(dlouha, 13, 1.0), cand(kratka, 0, 1.5)]
        return MatchResult(outcome="odpoved",
                           candidates=candidates), dlouha, kratka

    def test_shluk_porazi_osamelou_spicku(self):
        from cb_field.query import gaussian_peaks, sentence_activation
        result, dlouha, kratka = self._result()
        # normalizace průměrem preferuje degenerát (dokumentace vady):
        prumer = sentence_activation(result)
        self.assertIs(prumer[0][0], kratka)
        # gaussovský vrchol preferuje shluk:
        peaks = gaussian_peaks(result, sigma=1.5)
        self.assertIs(peaks[0][0], dlouha)
        self.assertGreater(peaks[0][1], peaks[1][1])
        self.assertIn(peaks[0][2], (11, 12, 13))   # vrchol uvnitř shluku

    def test_vrchol_je_v_mezich_pole(self):
        from cb_field.query import gaussian_peaks
        result, _dlouha, kratka = self._result()
        for sentence, peak, center in gaussian_peaks(result):
            self.assertGreaterEqual(peak, 0.0)
            self.assertTrue(0 <= center < len(sentence.tokens))
