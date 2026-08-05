"""Testy čtení pole — AnswerField a gaussovské vrcholy.

Čísla jsou ze zadání § krok 4 a jdou spočítat ručně: jádro σ=1,5 má
k0 = 0,267, k1 = 0,213; shluk tří jedniček dá vrchol 0,69, osamělá
špička 1,5 jen 0,40. Proto shluk poráží silnější špičku.
"""

import unittest

from cb_bond import AnswerField, MatchResult
from cb_bond.matcher import ScoreCandidate
from cb_bond.answer import gaussian_kernel


def _vysledek(*vety):
    """MatchResult z {pozice tokenu: skóre} pro každou větu."""
    kandidati = []
    for i, skore in enumerate(vety):
        for token, hodnota in skore.items():
            kandidati.append(ScoreCandidate(i, token, f"w{token}", hodnota,
                                            {}))
    kandidati.sort(key=lambda k: -k.score)
    return MatchResult(kandidati, "answer")


class TestJadro(unittest.TestCase):

    def test_jadro_ma_hodnoty_ze_zadani(self):
        jadro = gaussian_kernel(1.5)

        self.assertEqual(len(jadro), 9)          # poloměr int(3σ) = 4
        stred = len(jadro) // 2
        self.assertAlmostEqual(jadro[stred], 0.267, places=3)
        self.assertAlmostEqual(jadro[stred + 1], 0.213, places=3)
        self.assertAlmostEqual(jadro[stred + 2], 0.110, places=3)

    def test_jadro_je_normovane_a_symetricke(self):
        jadro = gaussian_kernel(1.5)

        self.assertAlmostEqual(sum(jadro), 1.0, places=6)
        self.assertEqual(list(jadro), list(reversed(jadro)))


class TestVrcholy(unittest.TestCase):

    def test_shluk_porazi_silnejsi_spicku(self):
        # dlouhá věta se shlukem 1,0+1,0+1,0 proti krátké se špičkou 1,5
        shluk = {11: 1.0, 12: 1.0, 13: 1.0}
        spicka = {1: 1.5}

        vrcholy = AnswerField(_vysledek(shluk, spicka)).gaussian_peaks(1.5)

        (veta, vrchol, index) = vrcholy[0]
        self.assertEqual(veta, 0)                       # vyhrál shluk
        self.assertAlmostEqual(vrchol, 0.69, places=2)
        self.assertEqual(index, 12)                     # střed shluku
        self.assertAlmostEqual(vrcholy[1][1], 0.40, places=2)

    def test_vrcholy_jsou_serazene_sestupne(self):
        vrcholy = AnswerField(
            _vysledek({0: 0.2}, {0: 1.0}, {0: 0.5})).gaussian_peaks()

        self.assertEqual([v[0] for v in vrcholy], [1, 2, 0])

    def test_kratka_veta_ukaze_vrchol_uvnitr_sebe(self):
        # past konvoluce: mode="same" vrací délku DELŠÍHO pole, takže
        # u věty kratší než jádro (9) by vrchol ukázal mimo větu
        vrcholy = AnswerField(_vysledek({0: 1.0, 1: 1.0})).gaussian_peaks(1.5)

        (_, _, index) = vrcholy[0]
        self.assertIn(index, (0, 1))

    def test_zaporne_skore_vrchol_nezvedne(self):
        vrcholy = AnswerField(
            _vysledek({5: -1.0, 6: 0.3})).gaussian_peaks(1.5)

        self.assertLess(vrcholy[0][1], 0.3)


class TestCteni(unittest.TestCase):

    def test_tokeny_jsou_kandidati_serazeni_podle_skore(self):
        pole = AnswerField(_vysledek({0: 0.2, 1: 0.9}))

        tokeny = pole.tokens()

        self.assertEqual([(k.sentence, k.token) for k in tokeny],
                         [(0, 1), (0, 0)])

    def test_okna_scitaji_sousedni_tokeny(self):
        pole = AnswerField(_vysledek({0: 0.2, 1: 0.9, 2: 0.1}))

        okna = pole.spans(width=2)

        # nejlepší okno je dvojice (0,1) se součtem 1,1
        self.assertEqual(okna[0][0], 0)
        self.assertAlmostEqual(okna[0][2], 1.1, places=5)

    def test_vety_scitaji_cele_pole(self):
        pole = AnswerField(_vysledek({0: 0.2, 1: 0.9}, {0: 0.5}))

        vety = pole.sentences()

        self.assertEqual(vety[0][0], 0)
        self.assertAlmostEqual(vety[0][1], 1.1, places=5)
        self.assertAlmostEqual(vety[1][1], 0.5, places=5)

    def test_ctyri_cteni_jsou_pohledy_na_TOTEZ_pole(self):
        vysledek = _vysledek({3: 0.4, 4: 0.6})
        pole = AnswerField(vysledek)

        # token, okno, věta i vrchol čtou touž množinu vět
        self.assertEqual({k.sentence for k in pole.tokens()}, {0})
        self.assertEqual({o[0] for o in pole.spans()}, {0})
        self.assertEqual({v[0] for v in pole.sentences()}, {0})
        self.assertEqual({v[0] for v in pole.gaussian_peaks()}, {0})


if __name__ == "__main__":
    unittest.main()
