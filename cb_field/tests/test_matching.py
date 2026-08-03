"""Testy propojení (T-P1, T-P2 ze spec) na zmražené mini-scéně."""

import unittest

from cb_field import Corpus, SentenceField, match
from cb_field.tests.test_templates import DO, LESA, PES, SEL, TECKA
from cb_udpipe import Token

KAM = Token(id=1, form="Kam", lemma="kam", upos="ADV",
            xpos="Db-------------", feats={"PronType": "Int,Rel"},
            head=2, deprel="advmod", deps=None, misc=None)
SEL2 = Token(id=2, form="šel", lemma="jít", upos="VERB",
             xpos="VpYS----R-AAI--",
             feats={"Aspect": "Imp", "Gender": "Masc", "Number": "Sing",
                    "Polarity": "Pos", "Tense": "Past", "VerbForm": "Part",
                    "Voice": "Act"},
             head=0, deprel="root", deps=None, misc=None)
PES2 = Token(id=3, form="pes", lemma="pes", upos="NOUN",
             xpos="NNMS1-----A----",
             feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                    "Number": "Sing"},
             head=2, deprel="nsubj", deps=None, misc=None)
BEZELA2 = Token(id=2, form="běžela", lemma="běžet", upos="VERB",
                xpos="VpQW---XR-AAI--",
                feats={"Gender": "Fem", "Number": "Sing", "Tense": "Past",
                       "VerbForm": "Part", "Polarity": "Pos"},
                head=0, deprel="root", deps=None, misc=None)
KOCKA2 = Token(id=3, form="kočka", lemma="kočka", upos="NOUN",
               xpos="NNFS1-----A----",
               feats={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
               head=2, deprel="nsubj", deps=None, misc=None)
OTAZNIK = Token(id=4, form="?", lemma="?", upos="PUNCT",
                xpos="Z:-------------", feats=None,
                head=2, deprel="punct", deps=None, misc=None)


def _scena():
    corpus = Corpus(r=1)
    corpus.fields.append(SentenceField(
        (SEL, PES, DO, LESA, TECKA), r=1, registry=corpus.registry,
        source="Šel pes do lesa."))
    return corpus


class TestPropojeni(unittest.TestCase):

    def test_tp1_odpoved_s_dolozenim(self):
        corpus = _scena()
        otazka = SentenceField((KAM, SEL2, PES2, OTAZNIK), r=1,
                               registry=corpus.registry, source="Kam šel pes?")
        vysledek = match(otazka, corpus)
        self.assertEqual(vysledek.outcome, "odpoved")
        self.assertEqual(vysledek.best.token.lemma, "les")
        self.assertTrue(vysledek.best.top_nodes)      # rozklad je povinný
        self.assertIn("WORD=VERB:jít", vysledek.best.shared_words)

    def test_tp2_nevim_bez_spolecneho_obsahu(self):
        corpus = _scena()
        otazka = SentenceField((KAM, BEZELA2, KOCKA2, OTAZNIK), r=1,
                               registry=corpus.registry,
                               source="Kam běžela kočka?")
        self.assertEqual(match(otazka, corpus).outcome, "nevim")


if __name__ == "__main__":
    unittest.main()
