"""Testy fixovaného JSON korpusu — docs/korpus-json.md.

Jméno souboru je neprůhledný identifikátor: loader z něj nesmí nic
vyvozovat. Atrapa parseru podle § 13 (test nepotřebuje běžící službu).
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_field.corpus import Corpus
from cb_field.corpusfile import add_to_corpus, load_corpus_file
from cb_field.tests.test_graph import KREST, _Sentence


def _write(tmp, data, name="cokoli.json"):
    path = Path(tmp) / name
    path.write_text(json.dumps(data, ensure_ascii=False),
                    encoding="utf-8")
    return path


def _valid_data():
    return {
        "format_version": 1,
        "language": "cs",
        "blocks": [
            {"topic": "první", "sentences": ["Věta nula.", "Věta jedna."]},
            {"topic": "druhý", "sentences": ["Věta dva."]},
        ],
        "questions": [
            {"text": "Na co?", "sentence": 2, "answer_lemma": "dva",
             "answerable": True},
            {"text": "A na co ne?", "sentence": None,
             "answer_lemma": None, "answerable": False},
        ],
    }


class _Parser:
    """Atrapa: každé větě vrátí zmraženou větu o křtu (n_sentences krát)."""

    def __init__(self, n=1):
        self.n = n

    def parse(self, text):
        class _Result:
            sentences = [_Sentence(KREST)] * self.n
        return _Result()


class TestLoadCorpusFile(unittest.TestCase):

    def test_nacte_bloky_vety_a_otazky(self):
        with tempfile.TemporaryDirectory() as tmp:
            cf = load_corpus_file(_write(tmp, _valid_data()))
            self.assertEqual(len(cf.blocks), 2)
            self.assertEqual(cf.sentences,
                             ("Věta nula.", "Věta jedna.", "Věta dva."))
            self.assertEqual(cf.questions[0].sentence, 2)
            self.assertTrue(cf.questions[0].answerable)
            self.assertFalse(cf.questions[1].answerable)

    def test_cizi_verze_formatu_se_odmitne(self):
        data = _valid_data()
        data["format_version"] = 99
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_corpus_file(_write(tmp, data))

    def test_index_mimo_rozsah_je_hlasita_chyba(self):
        data = _valid_data()
        data["questions"][0]["sentence"] = 3
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_corpus_file(_write(tmp, data))

    def test_zodpoveditelna_bez_lemmatu_je_chyba(self):
        data = _valid_data()
        data["questions"][0]["answer_lemma"] = None
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_corpus_file(_write(tmp, data))


class TestAddToCorpus(unittest.TestCase):

    def test_vraci_pozice_a_drzi_hranice_bloku(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(KREST))     # korpus už něco má
        with tempfile.TemporaryDirectory() as tmp:
            cf = load_corpus_file(_write(tmp, _valid_data()))
            positions = add_to_corpus(corpus, cf, _Parser())
        self.assertEqual(positions, (1, 2, 3))    # index vety → pozice
        self.assertEqual(len(corpus), 4)
        # blok = dokument: uvnitř bloku týž marker, přes bloky různý,
        # a nic z něj nenese jméno souboru
        self.assertIs(corpus.documents[1], corpus.documents[2])
        self.assertIsNot(corpus.documents[2], corpus.documents[3])

    def test_rozpad_vety_parserem_hlasi_index(self):
        corpus = Corpus(r=1)
        with tempfile.TemporaryDirectory() as tmp:
            cf = load_corpus_file(_write(tmp, _valid_data()))
            with self.assertRaises(ValueError) as ctx:
                add_to_corpus(corpus, cf, _Parser(n=2))
            self.assertIn("0", str(ctx.exception))  # globální index věty


if __name__ == "__main__":
    unittest.main()
