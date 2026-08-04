"""Testy spektrálního členu — truncated SVD jako most mezi osami.

Vzorek ze zadání § 5/S2 je tady zmražený: čtyři věty, pět os, a dvojice
*smět* × *povolený*, která spolu nikdy nestojí ve větě. Surově je jejich
kosinus 0,00; při k=1 se přes sdílený kontext slijí na 1,00.
"""

import unittest

import numpy as np

from cb_bond import SpectralMember, truncated_svd

#: Vzorek ze zadání. Osy: smět · povolený · rychlost · dálnice · jezdit.
VZOREK = np.array([
    [0, 1, 1, 1, 0],   # Na dálnici je povolená rychlost sto třicet.
    [1, 0, 1, 1, 1],   # Po dálnici se smí jezdit rychlostí 130.
    [0, 1, 1, 0, 0],   # Nejvyšší povolená rychlost platí v obci.
    [1, 0, 1, 0, 1],   # Kamion smí jezdit nižší rychlostí.
], dtype=np.float32)

SMET, POVOLENY = 0, 1


def _cos(a, b) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    return float(a @ b / (na * nb)) if na and nb else 0.0


class TestTruncatedSvd(unittest.TestCase):

    def test_singularni_hodnoty_sedi_se_zadanim(self):
        _, s, _ = truncated_svd(VZOREK, k=4)

        self.assertAlmostEqual(float(s[0]), 2.885, places=2)
        self.assertAlmostEqual(float(s[1]), 1.681, places=2)
        self.assertAlmostEqual(float(s[2]), 0.922, places=2)
        self.assertAlmostEqual(float(s[3]), 0.0, places=3)

    def test_je_DETERMINISTICKY(self):
        # princip 8: dvě měření musejí porovnávat totéž
        a = truncated_svd(VZOREK, k=2)[2]
        b = truncated_svd(VZOREK, k=2)[2]

        self.assertTrue(np.allclose(a, b))

    def test_jine_seminko_da_TYZ_podprostor(self):
        # náhoda je jen v projekci; podprostor je vlastnost matice
        a = truncated_svd(VZOREK, k=2, seed=1)[2]
        b = truncated_svd(VZOREK, k=2, seed=999)[2]

        # porovnává se podprostor, ne báze: |cos| mezi řádky ~ 1
        self.assertAlmostEqual(abs(_cos(a[0], b[0])), 1.0, places=3)

    def test_neposkodi_se_kdyz_k_prevysi_hodnost(self):
        _, s, Vt = truncated_svd(VZOREK, k=99)

        self.assertLessEqual(Vt.shape[0], VZOREK.shape[1])


class TestMost(unittest.TestCase):
    """Přejímka § 5/S2: k je páka mezi zobecněním a rozlišením."""

    def _cos_os(self, k):
        Vt = truncated_svd(VZOREK, k=k)[2]
        promitnute = VZOREK @ Vt.T @ Vt
        return _cos(promitnute[:, SMET], promitnute[:, POVOLENY])

    def test_surove_se_osy_NIKDY_nepotkaji(self):
        self.assertAlmostEqual(
            _cos(VZOREK[:, SMET], VZOREK[:, POVOLENY]), 0.0, places=6)

    def test_male_k_osy_SLIJE(self):
        # hlavní téma je společný kontext (rychlost, dálnice, jezdit)
        self.assertAlmostEqual(self._cos_os(1), 1.0, places=2)

    def test_vetsi_k_kontrast_VRATI(self):
        # druhá komponenta nese právě rozdíl smět × povolený
        self.assertAlmostEqual(self._cos_os(2), 0.0, places=1)


class TestClen(unittest.TestCase):

    def test_skore_je_kosinus_v_latentnim_prostoru(self):
        clen = SpectralMember()
        clen.fit(VZOREK, k=1)

        # otázka nesoucí „smět" má sednout na větu s „povolený"
        otazka = np.array([1, 0, 0, 0, 0], dtype=np.float32)
        s_povolenym = clen.score(otazka, 0)     # s1 nese povolený
        se_smetim = clen.score(otazka, 1)       # s2 nese smět

        self.assertGreater(s_povolenym, 0.5)
        self.assertGreater(se_smetim, 0.5)

    def test_bez_fitu_je_clen_NULA(self):
        # nenaučený člen nesmí mlčky ovlivňovat baseline
        self.assertEqual(SpectralMember().score(
            np.array([1, 0, 0, 0, 0], dtype=np.float32), 0), 0.0)

    def test_nulovy_pytel_da_nulu_ne_deleni_nulou(self):
        clen = SpectralMember()
        clen.fit(VZOREK, k=2)

        self.assertEqual(clen.score(np.zeros(5, dtype=np.float32), 0), 0.0)

    def test_kratsi_vektor_se_doplni_nulami(self):
        # osa roste; pytel z menšího registru musí projít
        clen = SpectralMember()
        clen.fit(VZOREK, k=2)

        self.assertIsInstance(
            clen.score(np.array([1, 0], dtype=np.float32), 0), float)

    def test_fit_se_pamatuje_kolik_os_mel(self):
        clen = SpectralMember()
        clen.fit(VZOREK, k=2)

        self.assertEqual(clen.axes, 5)
        self.assertEqual(clen.k, 2)


if __name__ == "__main__":
    unittest.main()
