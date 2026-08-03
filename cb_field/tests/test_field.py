"""Testy třídy SentenceField — pracovní úroveň: věta → pole → matice.

Zmražená data se sdílejí s test_registry (tamní tokeny odpovídají
skutečným výstupům UDPipe).
"""

import unittest

import numpy as np

from cb_field import Representation, SentenceField, VerticalRegistry
from cb_field.tests.test_registry import BYLI, KDE, PES
from cb_udpipe import Token

OTAZNIK = Token(id=9, form="?", lemma="?", upos="PUNCT",
                xpos="Z:-------------", feats=None,
                head=1, deprel="punct", deps=None, misc=None)

#: „Kde byli ? " — nejmenší tázací věta, na které je vidět celá vrstva.
VETA = (KDE, BYLI, OTAZNIK)


class TestSentenceField(unittest.TestCase):

    def test_konstruktor_spocita_vse_jednou(self):
        field = SentenceField(VETA, r=2)
        self.assertTrue(field.question)              # otazník → tázací
        self.assertEqual(len(field.baskets), 3)
        self.assertEqual(len(field.activations), 3)
        # otázkovost prošla dovnitř bez ručního protahování:
        self.assertEqual(field.activations[0].get("QANCHOR=space"), 0.7)

    def test_matice_ma_jednotnou_sirku(self):
        field = SentenceField(VETA)
        m = field.matrix()
        self.assertEqual(m.shape, (3, len(field.registry)))
        self.assertEqual(m.dtype, np.float32)

    def test_matice_kose_ma_fixni_tvar_s_nulovymi_radky(self):
        field = SentenceField(VETA, r=2)
        m = field.matrix()
        bm = field.baskets[0].array                  # koš na kraji věty
        self.assertEqual(bm.shape, (5, m.shape[1]))  # 2r+1 řádků vždy
        self.assertFalse(bm[0].any())                # za hranicí věty nuly
        self.assertFalse(bm[1].any())
        self.assertTrue(np.array_equal(bm[2], m[0])) # střed vždy na y=r
        with self.assertRaises(IndexError):
            field.baskets[7]

    def test_trojice_pohledu_je_symetricka(self):
        # věta i koš nabízejí metadata / complete / array stejným způsobem
        field = SentenceField(VETA, r=2)
        self.assertEqual(field.metadata[0],
                         field.activations[0].weights())
        self.assertIn("WORD=ADV:kde", field.complete[0])
        self.assertNotIn("WORD=ADV:kde", field.metadata[0])
        self.assertTrue(np.array_equal(field.array, field.matrix()))
        kos = field.baskets[1]
        self.assertEqual(kos.metadata[0], field.metadata[0])   # okno od 0
        self.assertIn("WORD=AUX:být", kos.complete[1])
        self.assertEqual(kos.array.shape, (5, field.array.shape[1]))
        self.assertEqual(kos.center_token.form, "byli")

    def test_from_text_je_jedna_veta(self):
        # atrapa parseru — test nesmí potřebovat běžící službu (§ 13)
        class _Result:
            def __init__(self, sentences): self.sentences = sentences
        class _Sentence:
            tokens = VETA
            source = "Kde byli ?"
        class _Parser:
            def __init__(self, n): self.n = n
            def parse(self, text): return _Result([_Sentence()] * self.n)

        field = SentenceField.from_text("Kde byli ?", _Parser(1))
        self.assertTrue(field.question)
        self.assertEqual(field.source, "Kde byli ?")
        with self.assertRaises(ValueError):
            SentenceField.from_text("Dvě věty. Tady.", _Parser(2))

    def test_sdileny_registr_drzi_osu_pres_vety(self):
        reg = VerticalRegistry()
        f1 = SentenceField((PES,), registry=reg)
        f2 = SentenceField(VETA, registry=reg)
        f2.matrix()
        # po růstu registru mají matice obou vět touž šířku (společné osy)
        self.assertEqual(f1.matrix().shape[1], f2.matrix().shape[1])

    def test_complete_reprezentace_pridava_slova(self):
        field = SentenceField(VETA)
        meta = field.matrix()
        comp = field.matrix(Representation.COMPLETE)
        self.assertGreater(comp.shape[1], meta.shape[1])   # WORD= sloupce


if __name__ == "__main__":
    unittest.main()
