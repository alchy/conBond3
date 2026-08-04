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
    """Propojení je čistě váhové: žádné filtry, jen členy skóre a θ/ε."""

    def test_tp1_rozklad_skore_je_povinny(self):
        corpus = _scena()
        otazka = SentenceField((KAM, SEL2, PES2, OTAZNIK), r=1,
                               registry=corpus.registry, source="Kam šel pes?")
        vysledek = match(otazka, corpus)
        self.assertTrue(vysledek.candidates)
        nejlepsi = vysledek.best
        self.assertTrue(nejlepsi.top_nodes)           # doložení (P-D)
        # skóre je součtem svých členů, nic se neztrácí ani nepřidává
        self.assertAlmostEqual(
            nejlepsi.score,
            nejlepsi.meet_score + nejlepsi.cover_score
            + nejlepsi.fit_score
            + nejlepsi.topic_score
            + nejlepsi.given_score,
            places=3)

    def test_tp2_kandiduje_kazdy_token_bez_filtru(self):
        # dřív obsahový filtr větu bez sdílených slov zahodil — a tím
        # vyhladověl učení, které má právě takové mosty stavět
        corpus = _scena()
        otazka = SentenceField((KAM, BEZELA2, KOCKA2, OTAZNIK), r=1,
                               registry=corpus.registry,
                               source="Kam běžela kočka?")
        vysledek = match(otazka, corpus)
        self.assertEqual(len(vysledek.candidates),
                         len(corpus[0].tokens))       # každý token kandidát

    def test_tp3_uceni_stavi_metadatovy_vzor_ne_synonyma(self):
        """Učení staví METADATOVÝ vzor, ne vazbu mezi dvěma slovy.

        Pravidlo J. (2026-08-04): trénink nesmí utíkat k posilování
        vazeb synonymy — vzory se dělají na metadatech a teprve pak se
        povyšují ty, kde sedí vlastní lemma. Slovní most (běžet→les) by
        platil pro jedinou dvojici slov; metadatový vzor (co poptává
        „kam" → jaká kotva odpovídá) platí pro celý typ otázky.
        """
        from cb_field.learning import train_on_etalon
        corpus = _scena()

        class _Parser:                     # atrapa: vrací zmraženou otázku
            def parse(self, text):
                class _R:
                    sentences = [type("_S", (), {
                        "tokens": (KAM, BEZELA2, KOCKA2, OTAZNIK),
                        "source": "Kam běžela kočka?"})()]
                return _R()

        train_on_etalon(corpus, [{"otazka": "Kam běžela kočka?",
                                  "odpoved_lemma": "les",
                                  "zodpoveditelna": True}], _Parser())
        naucene = [(s, d, w) for s, d, w, zdroj
                   in corpus.registry.links() if zdroj == "etalon"]
        self.assertTrue(naucene, "učení nepostavilo žádnou hranu")
        # slovo se smí povýšit na TYP (WORD→ANCHOR), ale synonymní
        # hrana slovo↔slovo musí být řádově slabší (útlum, ne zákaz)
        synonyma = [abs(w) for s, d, w in naucene
                    if s.startswith("WORD=") and d.startswith("WORD=")]
        typove = [abs(w) for s, d, w in naucene
                  if s.startswith("WORD=") and d.startswith("ANCHOR=")]
        if synonyma and typove:
            self.assertLess(max(synonyma), max(typove))
        # a poptávaná souřadnice otázky musí být mezi konci vazeb
        konce = {s for s, _d, _w in naucene} | {d for _s, d, _w in naucene}
        self.assertTrue(any(k.startswith(("QANCHOR=", "QLEM=", "ANCHOR="))
                            for k in konce))


if __name__ == "__main__":
    unittest.main()
