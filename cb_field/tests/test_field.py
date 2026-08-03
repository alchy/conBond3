"""Testy třídy Field — pracovní úroveň: věta → pole → matice.

Zmražená data se sdílejí s test_registry (tamní tokeny odpovídají
skutečným výstupům UDPipe).
"""

import unittest

import numpy as np

from cb_field import Field, Representation, VerticalRegistry
from cb_field.tests.test_registry import BYLI, KDE, PES
from cb_udpipe import Token

OTAZNIK = Token(id=9, form="?", lemma="?", upos="PUNCT",
                xpos="Z:-------------", feats=None,
                head=1, deprel="punct", deps=None, misc=None)

#: „Kde byli ? " — nejmenší tázací věta, na které je vidět celá vrstva.
VETA = (KDE, BYLI, OTAZNIK)


class TestField(unittest.TestCase):

    def test_konstruktor_spocita_vse_jednou(self):
        field = Field(VETA, r=2)
        self.assertTrue(field.question)              # otazník → tázací
        self.assertEqual(len(field.baskets), 3)
        self.assertEqual(len(field.activations), 3)
        # otázkovost prošla dovnitř bez ručního protahování:
        self.assertEqual(field.activations[0].get("QANCHOR=space:loc"), 0.7)

    def test_matice_ma_jednotnou_sirku(self):
        field = Field(VETA)
        m = field.matrix()
        self.assertEqual(m.shape, (3, len(field.registry)))
        self.assertEqual(m.dtype, np.float32)

    def test_matice_kose_ma_fixni_tvar_s_nulovymi_radky(self):
        field = Field(VETA, r=2)
        m = field.matrix()
        bm = field.basket_matrix(0)                  # koš na kraji věty
        self.assertEqual(bm.shape, (5, m.shape[1]))  # 2r+1 řádků vždy
        self.assertFalse(bm[0].any())                # za hranicí věty nuly
        self.assertFalse(bm[1].any())
        self.assertTrue(np.array_equal(bm[2], m[0])) # střed vždy na y=r
        with self.assertRaises(IndexError):
            field.basket_matrix(7)

    def test_sdileny_registr_drzi_osu_pres_vety(self):
        reg = VerticalRegistry()
        f1 = Field((PES,), registry=reg)
        f2 = Field(VETA, registry=reg)
        f2.matrix()
        # po růstu registru mají matice obou vět touž šířku (společné osy)
        self.assertEqual(f1.matrix().shape[1], f2.matrix().shape[1])

    def test_complete_reprezentace_pridava_slova(self):
        field = Field(VETA)
        meta = field.matrix()
        comp = field.matrix(Representation.COMPLETE)
        self.assertGreater(comp.shape[1], meta.shape[1])   # WORD= sloupce


if __name__ == "__main__":
    unittest.main()
