"""Testy šablon: signatury, maskování středu, slučování, R1 středy.

Zmražená data: dvě mini-věty se stejným tvarem a jinými slovy —
„Šel pes do lesa." a „Běžela kočka do parku." Hodnoty odpovídají
skutečným výstupům UDPipe.
"""

import unittest

from cb_field import SentenceField
from cb_field.templates import (CENTER_HOLE, R2_PREFIXES, TemplateBank,
                                default_centers)
from cb_udpipe import Token


def _veta(*tokens):
    return SentenceField(tokens, r=2)


SEL = Token(id=1, form="Šel", lemma="jít", upos="VERB",
            xpos="VpYS----R-AAI--",
            feats={"Aspect": "Imp", "Gender": "Masc", "Number": "Sing",
                   "Polarity": "Pos", "Tense": "Past", "VerbForm": "Part",
                   "Voice": "Act"},
            head=0, deprel="root", deps=None, misc=None)
PES = Token(id=2, form="pes", lemma="pes", upos="NOUN",
            xpos="NNMS1-----A----",
            feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                   "Number": "Sing"},
            head=1, deprel="nsubj", deps=None, misc=None)
DO = Token(id=3, form="do", lemma="do", upos="ADP", xpos="RR--2----------",
           feats={"AdpType": "Prep", "Case": "Gen"},
           head=4, deprel="case", deps=None, misc=None)
LESA = Token(id=4, form="lesa", lemma="les", upos="NOUN",
             xpos="NNIS2-----A----",
             feats={"Animacy": "Inan", "Case": "Gen", "Gender": "Masc",
                    "Number": "Sing"},
             head=1, deprel="obl", deps=None, misc=None)
TECKA = Token(id=5, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=1, deprel="punct", deps=None, misc=None)

BEZELA = Token(id=1, form="Běžela", lemma="běžet", upos="VERB",
               xpos="VpQW---XR-AAI--",
               feats={"Aspect": "Imp", "Gender": "Fem", "Number": "Sing",
                      "Polarity": "Pos", "Tense": "Past",
                      "VerbForm": "Part", "Voice": "Act"},
               head=0, deprel="root", deps=None, misc=None)
KOCKA = Token(id=2, form="kočka", lemma="kočka", upos="NOUN",
              xpos="NNFS1-----A----",
              feats={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
              head=1, deprel="nsubj", deps=None, misc=None)
PARKU = Token(id=4, form="parku", lemma="park", upos="NOUN",
              xpos="NNIS2-----A----",
              feats={"Animacy": "Inan", "Case": "Gen", "Gender": "Masc",
                     "Number": "Sing"},
              head=1, deprel="obl", deps=None, misc=None)

S1 = _veta(SEL, PES, DO, LESA, TECKA)          # Šel pes do lesa.
S2 = _veta(BEZELA, KOCKA, DO, PARKU, TECKA)    # Běžela kočka do parku.


class TestStredyR1(unittest.TestCase):

    def test_stredem_je_sloveso_a_jadro_s_predlozkou(self):
        # šel (VERB, root) a lesa (jmenné jádro s case-dítětem „do")
        self.assertEqual(default_centers(S1), (0, 3))
        # interpunkce, předložka ani podmět bez předložky středem nejsou


class TestSignatura(unittest.TestCase):

    def test_maskovany_stred_neni_hranice(self):
        bank = TemplateBank(center="out")
        sig = bank.signature(S1, 0)             # střed „Šel" na kraji věty
        self.assertEqual(sig[0], ())            # za hranicí věty: prázdno
        self.assertEqual(sig[2], (CENTER_HOLE,))  # díra po středu: značka
        self.assertNotEqual(sig[0], sig[2])     # obojí se nesmí slít

    def test_stred_uvnitr_nese_sve_klice(self):
        bank = TemplateBank(center="in")
        sig = bank.signature(S1, 0)
        self.assertIn("UPOS=VERB", sig[2])

    def test_zaporna_vazba_je_soucasti_identity(self):
        # „kde" v oznamovací větě má PronType=Int@−0.7 → v signatuře '!'
        from cb_field.tests.test_registry import KDE
        veta = _veta(KDE, SEL)
        bank = TemplateBank(center="in")
        sig = bank.signature(veta, 0)
        self.assertIn("!PronType=Int", sig[2])


class TestSlucovani(unittest.TestCase):
    """Jádro T2: shodné vzory se musí slít, rozdílné ne."""

    def test_r2_vertikaly_sleji_pes_a_kocku(self):
        # R2 signatura nemá rod: „Šel pes…" a „Běžela kočka…" = tytéž vzory
        bank = TemplateBank(verticals=R2_PREFIXES, center="out")
        ids1 = bank.add(S1)
        ids2 = bank.add(S2)
        self.assertEqual(ids1, ids2)            # střed po středu tatáž šablona
        self.assertEqual(bank.templates, 2)     # slovesná + jádrová
        self.assertEqual(bank.centers, 4)
        self.assertEqual(bank.ratio(), 0.5)
        self.assertEqual(bank.shared(), 2)      # obě šablony mají ≥2 doklady

    def test_plne_vertikaly_pes_a_kocku_rozdeli(self):
        # plná signatura nese Gender/Animacy → vzory se štěpí (páka R2)
        bank = TemplateBank(verticals=None, center="out")
        bank.add(S1)
        bank.add(S2)
        self.assertEqual(bank.templates, 4)
        self.assertEqual(bank.ratio(), 1.0)

    def test_prazdna_banka_ma_pomer_nula(self):
        self.assertEqual(TemplateBank().ratio(), 0.0)

    def test_kanonizace_je_necitliva_na_poradi_okoli(self):
        # mitigace S1: prohoz[…] sousedů nesmí změnit kanonickou signaturu
        prohozene = _veta(SEL, DO, PES, LESA, TECKA)   # syntetická permutace
        linear = TemplateBank(verticals=R2_PREFIXES, center="out")
        canon = TemplateBank(verticals=R2_PREFIXES, center="out",
                             order="canon")
        self.assertNotEqual(linear.signature(S1, 3),
                            linear.signature(prohozene, 3))
        self.assertEqual(canon.signature(S1, 3),
                         canon.signature(prohozene, 3))


if __name__ == "__main__":
    unittest.main()
