"""Testy fixovaného korpusu v JSON — čtení, validace, stavba.

Parser je atrapa (§ 13): dělí text na věty za tečkou a každé dá jeden
zmražený token. Testy se dívají na čísla a hranice, ne na rozbor.

Kromě syntetických souborů se sahá i na skutečná data v tests/data/korpus —
formát, který se čte, je ten, který v repozitáři opravdu leží.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from cb_field import Corpus
from cb_field.corpusfile import (add_to_corpus, build_corpus, etalon_entries,
                                 load_corpus_file)
from cb_field.tests.test_registry import PES

DATA = Path(__file__).parent / "data" / "korpus"


class _Sentence:
    def __init__(self, source):
        self.tokens = (PES,)
        self.source = source


class _Result:
    def __init__(self, sentences):
        self.sentences = tuple(sentences)


class _Parser:
    """Dělí text za tečkou — tolik vět, kolik jich v textu opravdu je."""

    def __init__(self):
        self.calls = 0

    def parse(self, text):
        self.calls += 1
        kusy = [k.strip() for k in re.split(r"(?<=[.?!])\s+", text.strip())
                if k.strip()]
        return _Result([_Sentence(k) for k in kusy])


def _zapis(tmp: Path, name: str, data: dict) -> Path:
    path = tmp / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


SOUBOR = {
    "format_version": 1,
    "language": "cs",
    "blocks": [
        {"topic": "první", "text": "Pes běží. Petr stojí.",
         "sentences": ["Pes běží.", "Petr stojí."]},
        {"topic": "druhý", "sentences": ["Kočka spí."]},
    ],
    "questions": [
        {"text": "Kdo běží?", "sentence": 0, "answer_lemma": "pes",
         "answerable": True},
        {"text": "Na co text neodpovídá?", "sentence": None,
         "answer_lemma": None, "answerable": False},
    ],
}


class TestCteni(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_nacte_bloky_otazky_a_globalni_indexy(self):
        soubor = load_corpus_file(_zapis(self.tmp, "korpus-900.json", SOUBOR))

        self.assertEqual(len(soubor.blocks), 2)
        self.assertEqual(soubor.blocks[0].text, "Pes běží. Petr stojí.")
        self.assertIsNone(soubor.blocks[1].text)
        self.assertEqual(soubor.sentences,
                         ("Pes běží.", "Petr stojí.", "Kočka spí."))
        self.assertEqual(soubor.questions[0].sentence, 0)
        self.assertFalse(soubor.questions[1].answerable)
        self.assertIsNone(soubor.corpus)

    def test_otazkovy_soubor_nese_jmeno_ciziho_korpusu(self):
        path = _zapis(self.tmp, "otazky-900.json", {
            "format_version": 1, "language": "cs", "corpus": "korpus-900.json",
            "blocks": [], "questions": SOUBOR["questions"]})

        soubor = load_corpus_file(path)

        self.assertEqual(soubor.corpus, "korpus-900.json")
        self.assertEqual(soubor.sentences, ())
        self.assertEqual(len(soubor.questions), 2)

    def test_cizi_verze_formatu_je_hlasita_chyba(self):
        path = _zapis(self.tmp, "korpus-901.json", dict(SOUBOR,
                                                        format_version=2))
        with self.assertRaises(ValueError) as chyba:
            load_corpus_file(path)
        self.assertIn("format_version", str(chyba.exception))

    def test_index_otazky_mimo_rozsah_je_hlasita_chyba(self):
        vadny = dict(SOUBOR, questions=[
            {"text": "Kdo?", "sentence": 9, "answer_lemma": "pes",
             "answerable": True}])
        path = _zapis(self.tmp, "korpus-902.json", vadny)

        with self.assertRaises(ValueError) as chyba:
            load_corpus_file(path)
        self.assertIn("9", str(chyba.exception))

    def test_zodpoveditelna_otazka_bez_indexu_je_hlasita_chyba(self):
        vadny = dict(SOUBOR, questions=[
            {"text": "Kdo?", "sentence": None, "answer_lemma": "pes",
             "answerable": True}])
        path = _zapis(self.tmp, "korpus-903.json", vadny)

        with self.assertRaises(ValueError):
            load_corpus_file(path)

    def test_skutecna_data_v_repozitari_se_prectou(self):
        soubor = load_corpus_file(DATA / "korpus-001.json")

        self.assertEqual(len(soubor.sentences), 96)
        self.assertEqual(len(soubor.questions), 18)
        # věta o dálnici a otázka na ni — zemní pravda pro pozdější kroky
        self.assertIn("sto třicet", soubor.sentences[4])
        odpoved = [q for q in soubor.questions if q.sentence == 4]
        self.assertEqual(odpoved[0].answer_lemma, "třicet")


class TestStavba(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_add_to_corpus_vrati_pozice_a_drzi_bloky_jako_dokumenty(self):
        soubor = load_corpus_file(_zapis(self.tmp, "korpus-910.json", SOUBOR))
        corpus = Corpus()

        pozice = add_to_corpus(corpus, soubor, _Parser())

        self.assertEqual(pozice, (0, 1, 2))
        self.assertEqual(len(corpus), 3)
        # dvě věty prvního bloku sousedí, třetí je z jiného odstavce
        self.assertEqual(corpus.document_span(0), (0, 2))
        self.assertEqual(corpus.document_span(2), (2, 3))

    def test_pozice_navazuji_na_uz_naplneny_korpus(self):
        soubor = load_corpus_file(_zapis(self.tmp, "korpus-911.json", SOUBOR))
        corpus = Corpus()
        corpus.add_sentence(_Sentence("Cizí věta."))

        pozice = add_to_corpus(corpus, soubor, _Parser())

        self.assertEqual(pozice, (1, 2, 3))

    def test_blok_s_textem_se_parsuje_vcelku(self):
        soubor = load_corpus_file(_zapis(self.tmp, "korpus-912.json", SOUBOR))
        parser = _Parser()

        add_to_corpus(corpus := Corpus(), soubor, parser)

        # blok s textem = jedno volání, blok bez textu = jedno na větu
        self.assertEqual(parser.calls, 2)
        self.assertEqual(corpus[0].source, "Pes běží.")

    def test_rozjete_cislovani_je_hlasita_chyba_s_adresou_bloku(self):
        vadny = {
            "format_version": 1, "language": "cs",
            "blocks": [{"topic": "vadný", "text": "Pes běží. Petr stojí.",
                        "sentences": ["Pes běží. Petr stojí."]}],
            "questions": []}
        soubor = load_corpus_file(_zapis(self.tmp, "korpus-913.json", vadny))

        with self.assertRaises(ValueError) as chyba:
            add_to_corpus(Corpus(), soubor, _Parser())
        zprava = str(chyba.exception)
        self.assertIn("korpus-913.json", zprava)
        self.assertIn("blok 0", zprava)

    def test_odlisne_zneni_rozpadu_je_hlasita_chyba(self):
        vadny = {
            "format_version": 1, "language": "cs",
            "blocks": [{"topic": "vadný", "text": "Pes běží. Petr stojí.",
                        "sentences": ["Pes běží.", "Petr sedí."]}],
            "questions": []}
        soubor = load_corpus_file(_zapis(self.tmp, "korpus-914.json", vadny))

        with self.assertRaises(ValueError) as chyba:
            add_to_corpus(Corpus(), soubor, _Parser())
        self.assertIn("Petr sedí.", str(chyba.exception))

    def test_build_corpus_slozi_soubory_za_sebe_nad_jednou_osou(self):
        prvni = _zapis(self.tmp, "korpus-920.json", SOUBOR)
        druhy = _zapis(self.tmp, "korpus-921.json", SOUBOR)

        corpus = build_corpus([prvni, druhy], _Parser(), r=1)

        self.assertEqual(len(corpus), 6)
        self.assertEqual(corpus.r, 1)
        self.assertEqual(corpus.positions["korpus-920.json"], (0, 1, 2))
        self.assertEqual(corpus.positions["korpus-921.json"], (3, 4, 5))
        self.assertIs(corpus[0].registry, corpus[5].registry)

    def test_otazkovy_soubor_se_do_korpusu_nepridava(self):
        korpus = _zapis(self.tmp, "korpus-930.json", SOUBOR)
        otazky = _zapis(self.tmp, "otazky-930.json", {
            "format_version": 1, "language": "cs",
            "corpus": "korpus-930.json", "blocks": [],
            "questions": SOUBOR["questions"]})

        corpus = build_corpus([korpus, otazky], _Parser())

        self.assertEqual(len(corpus), 3)
        self.assertNotIn("otazky-930.json", corpus.positions)


class TestEtalon(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_etalon_entries_prepocita_index_na_pozici_v_korpusu(self):
        soubor = load_corpus_file(_zapis(self.tmp, "korpus-940.json", SOUBOR))

        polozky = etalon_entries(soubor, (10, 11, 12))

        self.assertEqual(polozky[0], {
            "otazka": "Kdo běží?", "odpoved_lemma": "pes",
            "zodpoveditelna": True, "answer_position": 10})
        self.assertIsNone(polozky[1]["answer_position"])
        self.assertFalse(polozky[1]["zodpoveditelna"])


if __name__ == "__main__":
    unittest.main()
