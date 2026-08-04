"""Testy třídy Corpus — posloupnost polí nad JEDNÍM registrem.

Zmražená data: tokeny jsou literály sdílené s test_registry (skutečné
výstupy UDPipe). Parser je atrapa — test nesmí potřebovat běžící službu
(§ 13 politiky).
"""

import unittest

from cb_field import Corpus, SentenceField
from cb_field.tests.test_registry import BYLI, KDE, PES, PETR


class _Sentence:
    """Rozparsovaná věta v podobě, v jaké chodí z cb_udpipe."""

    def __init__(self, tokens, source):
        self.tokens = tuple(tokens)
        self.source = source


class _Result:
    def __init__(self, sentences):
        self.sentences = tuple(sentences)


class _Parser:
    """Atrapa parseru: text rozdělí po tečkách a každé větě dá dané tokeny.

    Počítá volání — regenerate() nesmí parsovat znovu.
    """

    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = 0

    def parse(self, text):
        self.calls += 1
        kusy = [k.strip() for k in text.split("|") if k.strip()]
        return _Result([_Sentence(self.mapping[k], k) for k in kusy])


PARSER = {
    "Pes.": (PES,),
    "Petr.": (PETR,),
    "Kde byli?": (KDE, BYLI),
}


class TestCorpusPosloupnost(unittest.TestCase):

    def test_add_sentence_vraci_pole_a_korpus_je_posloupnost(self):
        corpus = Corpus(r=2)
        pole = corpus.add_sentence(_Sentence((PES,), "Pes."))

        self.assertIsInstance(pole, SentenceField)
        self.assertEqual(len(corpus), 1)
        self.assertIs(corpus[0], pole)
        self.assertEqual(corpus[0].source, "Pes.")
        self.assertEqual([f.source for f in corpus], ["Pes."])

    def test_pole_sdileji_jeden_registr(self):
        corpus = Corpus()
        prvni = corpus.add_sentence(_Sentence((PES,), "Pes."))
        druhe = corpus.add_sentence(_Sentence((KDE, BYLI), "Kde byli?"))

        self.assertIs(prvni.registry, corpus.registry)
        self.assertIs(druhe.registry, corpus.registry)
        # jedna společná osa → matice vět jsou porovnatelné
        self.assertEqual(prvni.matrix().shape[1], druhe.matrix().shape[1])

    def test_add_text_projde_parserem_a_je_jedna_veta(self):
        parser = _Parser(PARSER)
        corpus = Corpus()
        pole = corpus.add_text("Pes.", parser)

        self.assertEqual(pole.source, "Pes.")
        self.assertEqual(len(corpus), 1)
        with self.assertRaises(ValueError):
            corpus.add_text("Pes.|Petr.", parser)


class TestDokumentoveMarkery(unittest.TestCase):

    def test_add_document_drzi_vety_pod_jednim_markerem(self):
        parser = _Parser(PARSER)
        corpus = Corpus()
        pole = corpus.add_document("Pes.|Petr.", parser)

        self.assertEqual([f.source for f in pole], ["Pes.", "Petr."])
        self.assertEqual(corpus.documents, (0, 0))

    def test_kazdy_dokument_ma_vlastni_marker(self):
        parser = _Parser(PARSER)
        corpus = Corpus()
        corpus.add_document("Pes.|Petr.", parser)
        corpus.add_document("Kde byli?", parser)
        corpus.add_sentence(_Sentence((PES,), "Pes."))

        # dvě položky prvního dokumentu, jedna druhého, samostatná věta třetí
        self.assertEqual(corpus.documents, (0, 0, 1, 2))

    def test_pojmenovany_dokument_sdruzi_i_oddelena_pridani(self):
        parser = _Parser(PARSER)
        corpus = Corpus()
        corpus.add_sentence(_Sentence((PES,), "Pes."), document="blok-a")
        corpus.add_text("Petr.", parser, document="blok-b")
        corpus.add_sentence(_Sentence((KDE, BYLI), "Kde byli?"),
                            document="blok-a")

        self.assertEqual(corpus.documents, (0, 1, 0))

    def test_document_span_vraci_hranice_bloku(self):
        parser = _Parser(PARSER)
        corpus = Corpus()
        corpus.add_document("Pes.|Petr.", parser)
        corpus.add_document("Kde byli?", parser)

        # kontext r_sentences nesmí přetéct odstavec: span dá meze
        self.assertEqual(corpus.document_span(0), (0, 2))
        self.assertEqual(corpus.document_span(1), (0, 2))
        self.assertEqual(corpus.document_span(2), (2, 3))


class TestRegenerate(unittest.TestCase):

    def test_regenerate_nestavi_znovu_parserem(self):
        parser = _Parser(PARSER)
        corpus = Corpus()
        corpus.add_document("Pes.|Petr.", parser)
        po_stavbe = parser.calls

        corpus.regenerate()

        self.assertEqual(parser.calls, po_stavbe)   # ani jedno volání navíc
        self.assertEqual([f.source for f in corpus], ["Pes.", "Petr."])

    def test_regenerate_zachova_markery_i_registr(self):
        parser = _Parser(PARSER)
        corpus = Corpus()
        corpus.add_document("Pes.|Petr.", parser)
        corpus.add_document("Kde byli?", parser)
        registr = corpus.registry

        corpus.regenerate()

        self.assertEqual(corpus.documents, (0, 0, 1))
        self.assertIs(corpus.registry, registr)
        self.assertIs(corpus[0].registry, registr)

    def test_regenerate_prestavi_pole_proti_aktualni_ose(self):
        corpus = Corpus()
        corpus.add_sentence(_Sentence((PES,), "Pes."))
        pred = corpus[0]

        corpus.regenerate()

        self.assertIsNot(corpus[0], pred)           # pole je nové
        self.assertEqual(corpus[0].tokens, pred.tokens)
        self.assertEqual(corpus[0].source, pred.source)


if __name__ == "__main__":
    unittest.main()
