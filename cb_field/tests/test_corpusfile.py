"""Testy fixovaného JSON korpusu — docs/korpus-json.md.

Jméno souboru je neprůhledný identifikátor: loader z něj nesmí nic
vyvozovat. Atrapa parseru podle § 13 (test nepotřebuje běžící službu).
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_field.corpus import Corpus
from cb_field.corpusfile import add_to_corpus, build_corpus, \
    etalon_entries, load_corpus_file
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
    """Atrapa: na každé volání vrátí další předepsaný počet vět bloku.

    Blok se parsuje vcelku, takže atrapa dostává posloupnost počtů
    po blocích ([2, 1] = první blok dvě věty, druhý jednu).
    """

    def __init__(self, counts=(2, 1)):
        self.counts = list(counts)
        self.texts = []

    def parse(self, text):
        self.texts.append(text)
        n = self.counts.pop(0)
        class _Result:
            sentences = [_Sentence(KREST)] * n
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
            positions = add_to_corpus(corpus, cf, _Parser((2, 1)))
        self.assertEqual(positions, (1, 2, 3))    # index vety → pozice
        self.assertEqual(len(corpus), 4)
        # blok = dokument: uvnitř bloku týž marker, přes bloky různý,
        # a nic z něj nenese jméno souboru
        self.assertIs(corpus.documents[1], corpus.documents[2])
        self.assertIsNot(corpus.documents[2], corpus.documents[3])

    def test_otazky_jdou_prevest_na_etalon(self):
        corpus = Corpus(r=1)
        with tempfile.TemporaryDirectory() as tmp:
            cf = load_corpus_file(_write(tmp, _valid_data()))
            positions = add_to_corpus(corpus, cf, _Parser((2, 1)))
        entries = etalon_entries(cf, positions)
        self.assertEqual(entries[0], {
            "otazka": "Na co?", "odpoved_lemma": "dva",
            "zodpoveditelna": True, "answer_position": positions[2]})
        self.assertEqual(entries[1], {
            "otazka": "A na co ne?", "odpoved_lemma": None,
            "zodpoveditelna": False})

    def test_build_corpus_spoji_vic_souboru_v_poradi(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = _write(tmp, _valid_data(), "a.json")
            second = _write(tmp, _valid_data(), "b.json")
            corpus = build_corpus((first, second), _Parser((2, 1, 2, 1)),
                                  r=1)
        self.assertEqual(len(corpus), 6)          # 3 + 3 vět v pořadí

    def test_blok_s_puvodnim_textem_se_parsuje_z_nej(self):
        # převod z txt ukládá původní odstavec: spojení položek mezerou
        # se může rozparsovat jinak (Válka.cz v citaci), původní text ne
        data = _valid_data()
        data["blocks"][0]["text"] = "Věta nula.  Věta jedna."
        corpus = Corpus(r=1)
        with tempfile.TemporaryDirectory() as tmp:
            cf = load_corpus_file(_write(tmp, data))
            parser = _Parser((2, 1))
            add_to_corpus(corpus, cf, parser)
        self.assertEqual(parser.texts[0], "Věta nula.  Věta jedna.")
        self.assertEqual(parser.texts[1], "Věta dva.")   # bez text: join

    def test_jiny_pocet_vet_z_parseru_hlasi_blok(self):
        # blok se parsuje vcelku (jako původní ingest po odstavcích);
        # jiný počet vět než položek by čísla otázek tiše rozjel
        corpus = Corpus(r=1)
        with tempfile.TemporaryDirectory() as tmp:
            cf = load_corpus_file(_write(tmp, _valid_data()))
            with self.assertRaises(ValueError) as ctx:
                add_to_corpus(corpus, cf, _Parser((3, 1)))
            self.assertIn("blok 0", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
