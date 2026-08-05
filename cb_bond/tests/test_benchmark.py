"""Testy měřicího protokolu — ramena A–F a kalibrace θ.

Protokol nic nepočítá sám: skládá hotové díly a hlídá, aby se ramena
měřila nad TÝMŽ korpusem a etalon se nikdy nedostal do tréninku.
"""

import unittest

from cb_bond import BenchmarkProtocol
from cb_bond.benchmark import ThresholdCalibrator


class _Kandidat:
    def __init__(self, lemma, score):
        self.lemma = lemma
        self.score = score
        self.sentence = 0
        self.token = 0


class _Vysledek:
    def __init__(self, lemma, score):
        self.best = _Kandidat(lemma, score)
        self.candidates = (self.best,)
        self.outcome = "answer"


class TestKalibrace(unittest.TestCase):

    def test_najde_theta_ktere_oddeli_spravne_od_svodu(self):
        # zodpověditelné trefy mají vysoké skóre, svody nízké →
        # existuje θ, které pustí první a umlčí druhé
        zaznamy = [{"odpoved_lemma": "a", "zodpoveditelna": True},
                   {"odpoved_lemma": "b", "zodpoveditelna": True},
                   {"odpoved_lemma": None, "zodpoveditelna": False},
                   {"odpoved_lemma": None, "zodpoveditelna": False}]
        vysledky = [_Vysledek("a", 3.0), _Vysledek("b", 2.8),
                    _Vysledek("x", 1.0), _Vysledek("y", 0.9)]

        vysledek = ThresholdCalibrator().calibrate(zaznamy, vysledky)

        self.assertGreater(vysledek["theta"], 1.0)
        self.assertLessEqual(vysledek["theta"], 2.8)
        self.assertAlmostEqual(vysledek["presnost"], 1.0)
        self.assertAlmostEqual(vysledek["mlceni"], 1.0)
        self.assertAlmostEqual(vysledek["merit"], 1.0)

    def test_kdyz_se_oddelit_neda_vybere_nejlepsi_kompromis(self):
        zaznamy = [{"odpoved_lemma": "a", "zodpoveditelna": True},
                   {"odpoved_lemma": None, "zodpoveditelna": False}]
        vysledky = [_Vysledek("a", 1.0), _Vysledek("x", 2.0)]

        vysledek = ThresholdCalibrator().calibrate(zaznamy, vysledky)

        self.assertLessEqual(vysledek["merit"], 1.0)
        self.assertIn("theta", vysledek)

    def test_bez_zaznamu_vrati_nulove_theta_ne_vyjimku(self):
        vysledek = ThresholdCalibrator().calibrate([], [])

        self.assertEqual(vysledek["theta"], 0.0)


class TestProtokol(unittest.TestCase):

    def test_ramena_jdou_v_predepsanem_poradi(self):
        self.assertEqual([a[0] for a in BenchmarkProtocol.ARMS],
                         ["A", "B", "D", "C", "E", "F"])

    def test_kazde_rameno_ma_popis(self):
        for znacka, popis in BenchmarkProtocol.ARMS:
            self.assertTrue(popis, f"rameno {znacka} nemá popis")

    def test_B_je_kontrola_k_C(self):
        # rozdíl C−B je čistý příspěvek promovaných os: obě ramena
        # mají učení, liší se jen promocí
        popisy = dict(BenchmarkProtocol.ARMS)

        self.assertIn("učení", popisy["B"])
        self.assertIn("promoc", popisy["C"].lower())

    def test_D_meri_hloubku_na_CISTEM_baselinu(self):
        popisy = dict(BenchmarkProtocol.ARMS)

        self.assertIn("čist", popisy["D"].lower())


if __name__ == "__main__":
    unittest.main()
