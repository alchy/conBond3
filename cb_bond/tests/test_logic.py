"""Testy mostu k formálnímu jádru — učení, dotaz, persistence přes restart.

Zmražené rozbory jsou vlastní kopií (testy nesmí sahat do testů cizího
modulu); zdrojem je UDPipe 2 (model cs_all-ud-2.17, 2026-08-09).
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cb_udpipe import Token

from cb_bond.logic import LogicBridge

PETR_PROGRAMATOR = (  # Petr je programátor.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN',
          xpos='NNMS1-----A----',
          feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc',
                 'NameType': 'Giv', 'Number': 'Sing'},
          head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--',
          feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing',
                 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres',
                 'VerbForm': 'Fin', 'Voice': 'Act'},
          head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='programátor', lemma='programátor', upos='NOUN',
          xpos='NNMS1-----A----',
          feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc',
                 'Number': 'Sing'},
          head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------',
          feats=None, head=3, deprel='punct', deps=None,
          misc={'SpaceAfter': 'No'}),
)

KAZDY_PROGRAMATOR = (  # Každý programátor je člověk.
    Token(id=1, form='Každý', lemma='každý', upos='DET',
          xpos='PLMS1----------',
          feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc',
                 'Number': 'Sing', 'PronType': 'Tot'},
          head=2, deprel='det', deps=None, misc=None),
    Token(id=2, form='programátor', lemma='programátor', upos='NOUN',
          xpos='NNMS1-----A----',
          feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc',
                 'Number': 'Sing'},
          head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--',
          feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing',
                 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres',
                 'VerbForm': 'Fin', 'Voice': 'Act'},
          head=4, deprel='cop', deps=None, misc=None),
    Token(id=4, form='člověk', lemma='člověk', upos='NOUN',
          xpos='NNMS1-----A----',
          feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc',
                 'Number': 'Sing'},
          head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------',
          feats=None, head=4, deprel='punct', deps=None,
          misc={'SpaceAfter': 'No'}),
)

JE_PETR_CLOVEK = (  # Je Petr člověk?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--',
          feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing',
                 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres',
                 'VerbForm': 'Fin', 'Voice': 'Act'},
          head=3, deprel='cop', deps=None, misc=None),
    Token(id=2, form='Petr', lemma='Petr', upos='PROPN',
          xpos='NNMS1-----A----',
          feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc',
                 'NameType': 'Giv', 'Number': 'Sing'},
          head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='člověk', lemma='člověk', upos='NOUN',
          xpos='NNMS1-----A----',
          feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc',
                 'Number': 'Sing'},
          head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------',
          feats=None, head=3, deprel='punct', deps=None,
          misc={'SpaceAfter': 'No'}),
)

MUZE_AUTO_JET = (  # Auto může jet na silnici.
    Token(id=1, form='Auto', lemma='auto', upos='NOUN',
          xpos='NNNS1-----A----',
          feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'},
          head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='může', lemma='moci', upos='VERB',
          xpos='VB-S---3P-AAI--',
          feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing',
                 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres',
                 'VerbForm': 'Fin', 'Voice': 'Act'},
          head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='jet', lemma='jet', upos='VERB', xpos='Vf--------A-I--',
          feats={'Aspect': 'Imp', 'Polarity': 'Pos', 'VerbForm': 'Inf'},
          head=2, deprel='xcomp', deps=None, misc=None),
    Token(id=4, form='na', lemma='na', upos='ADP', xpos='RR--6----------',
          feats={'AdpType': 'Prep', 'Case': 'Loc'},
          head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='silnici', lemma='silnice', upos='NOUN',
          xpos='NNFS6-----A----',
          feats={'Case': 'Loc', 'Gender': 'Fem', 'Number': 'Sing'},
          head=3, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------',
          feats=None, head=2, deprel='punct', deps=None,
          misc={'SpaceAfter': 'No'}),
)

AUTO_PROSTREDEK = (  # Auto je dopravní prostředek.
    Token(id=1, form='Auto', lemma='auto', upos='NOUN',
          xpos='NNNS1-----A----',
          feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'},
          head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--',
          feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing',
                 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres',
                 'VerbForm': 'Fin', 'Voice': 'Act'},
          head=4, deprel='cop', deps=None, misc=None),
    Token(id=3, form='dopravní', lemma='dopravní', upos='ADJ',
          xpos='AAIS1----1A----',
          feats={'Animacy': 'Inan', 'Case': 'Nom', 'Degree': 'Pos',
                 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'},
          head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='prostředek', lemma='prostředek', upos='NOUN',
          xpos='NNIS1-----A----',
          feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc',
                 'Number': 'Sing'},
          head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------',
          feats=None, head=4, deprel='punct', deps=None,
          misc={'SpaceAfter': 'No'}),
)

JE_AUTO_PROSTREDEK = (  # Je auto dopravní prostředek?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--',
          feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing',
                 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres',
                 'VerbForm': 'Fin', 'Voice': 'Act'},
          head=4, deprel='cop', deps=None, misc=None),
    Token(id=2, form='auto', lemma='auto', upos='NOUN',
          xpos='NNNS1-----A----',
          feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'},
          head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='dopravní', lemma='dopravní', upos='ADJ',
          xpos='AAIS1----1A----',
          feats={'Animacy': 'Inan', 'Case': 'Nom', 'Degree': 'Pos',
                 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'},
          head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='prostředek', lemma='prostředek', upos='NOUN',
          xpos='NNIS1-----A----',
          feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc',
                 'Number': 'Sing'},
          head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------',
          feats=None, head=4, deprel='punct', deps=None,
          misc={'SpaceAfter': 'No'}),
)

VETY = {
    "Petr je programátor.": PETR_PROGRAMATOR,
    "Každý programátor je člověk.": KAZDY_PROGRAMATOR,
    "Je Petr člověk?": JE_PETR_CLOVEK,
    "Auto může jet na silnici.": MUZE_AUTO_JET,
    "Auto je dopravní prostředek.": AUTO_PROSTREDEK,
    "Je auto dopravní prostředek?": JE_AUTO_PROSTREDEK,
}


class _Parser:
    """Atrapa se skutečnou tváří UdpipeClient.parse(text=…)."""

    def parse(self, *, text):
        tokens = VETY.get(text)
        sentences = ([SimpleNamespace(source=text, tokens=tokens)]
                     if tokens is not None else [])
        return SimpleNamespace(sentences=sentences, cached=0, parsed=1,
                               skipped=())


class TestLogicBridge(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.kb_file = Path(self._tmp.name) / "logic" / "kb.json"
        self.bridge = LogicBridge(_Parser(), self.kb_file)

    def tearDown(self):
        self._tmp.cleanup()

    def test_uceni_dotaz_a_vysvetleni(self):
        self.bridge.context("Každý programátor je člověk.")
        odpoved = self.bridge.ask("Je Petr člověk?")
        self.assertEqual(odpoved["truth"], "UNKNOWN")
        self.assertIn("petr je programátor", odpoved["missing"])

        vysledek = self.bridge.context("Petr je programátor.")
        self.assertEqual(vysledek["outcome"], "accepted")
        self.assertIn("petr je člověk", vysledek["derived"])

        odpoved = self.bridge.ask("Je Petr člověk?")
        self.assertEqual(odpoved["truth"], "TRUE")
        self.assertEqual(odpoved["answer"], "Ano.")
        self.assertEqual(odpoved["explanations"],
                         ["petr je člověk, protože petr je programátor "
                          "(doloženo: dialog)"])

    def test_neinterpretovatelna_otazka_vraci_none(self):
        self.assertIsNone(self.bridge.ask("Kde byl pokřtěn Ježíš?"))

    def test_znalost_prezije_restart(self):
        self.bridge.context("Každý programátor je člověk.")
        self.bridge.context("Petr je programátor.")
        znovu = LogicBridge(_Parser(), self.kb_file)  # „restart služby"
        odpoved = znovu.ask("Je Petr člověk?")
        self.assertEqual(odpoved["truth"], "TRUE")
        self.assertEqual(znovu.state()["rules"], 1)

    def test_stav(self):
        self.bridge.context("Petr je programátor.")
        stav = self.bridge.state()
        self.assertEqual(stav["facts"], 1)
        self.assertEqual(stav["conflicts"], 0)


class TestReferenceResolution(unittest.TestCase):
    """Plný kruh doptání na referenci — HANDOVER 4.1 bod 3, expanze § 1."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.kb_file = Path(self._tmp.name) / "logic" / "kb.json"
        self.bridge = LogicBridge(_Parser(), self.kb_file)

    def tearDown(self):
        self._tmp.cleanup()

    def test_otazka_se_dopta_a_nabidne_prikazy(self):
        self.bridge.context("Auto je dopravní prostředek.")
        odpoved = self.bridge.ask("Je auto dopravní prostředek?")
        self.assertEqual(odpoved["kind"], "reference_ambiguous")
        self.assertEqual({o["choice"] for o in odpoved["options"]},
                         {"instance", "class"})
        self.assertEqual({o["command"] for o in odpoved["options"]},
                         {":instance", ":trida"})
        self.assertTrue(self.bridge.state()["pending_reference"])

    def test_volba_trida_dokonci_dotaz_pres_probe(self):
        self.bridge.context("Auto je dopravní prostředek.")
        self.bridge.ask("Je auto dopravní prostředek?")
        vysledek = self.bridge.resolve_reference("class")
        self.assertEqual(vysledek["kind"], "reference_resolved")
        self.assertEqual(vysledek["truth"], "TRUE")
        self.assertEqual(vysledek["answer"], "Ano.")
        self.assertEqual(vysledek["subject"], "auto")
        self.assertFalse(self.bridge.state()["pending_reference"])

    def test_volba_instance_dedi_z_pravidel_pres_presupozici(self):
        # členství referentu zakládá reference sama — žádné
        # „chybí vědět: auto je auto" (zapsáno po demu)
        self.bridge.context("Auto je dopravní prostředek.")
        self.bridge.ask("Je auto dopravní prostředek?")
        vysledek = self.bridge.resolve_reference("instance")
        self.assertEqual(vysledek["truth"], "TRUE")
        self.assertEqual(vysledek["answer"], "Ano.")

    def test_bez_cekajiciho_doptani_je_hlaska_ne_chyba(self):
        vysledek = self.bridge.resolve_reference("class")
        self.assertEqual(vysledek["kind"], "no_pending_reference")

    def test_jina_otazka_doptani_zrusi(self):
        self.bridge.context("Auto je dopravní prostředek.")
        self.bridge.ask("Je auto dopravní prostředek?")
        self.bridge.ask("Je Petr člověk?")
        self.assertEqual(self.bridge.resolve_reference("class")["kind"],
                         "no_pending_reference")

    def test_tvrzeni_mezi_doptanim_a_volbou_slot_nerusi(self):
        # Člověk si smí PŘED volbou doplnit znalost — kontext slot nechává.
        self.bridge.ask("Je auto dopravní prostředek?")
        self.bridge.context("Auto je dopravní prostředek.")
        vysledek = self.bridge.resolve_reference("class")
        self.assertEqual(vysledek["truth"], "TRUE")

    def test_neplatna_volba_je_chyba(self):
        self.bridge.context("Auto je dopravní prostředek.")
        self.bridge.ask("Je auto dopravní prostředek?")
        with self.assertRaises(ValueError):
            self.bridge.resolve_reference("cokoliv")

    def test_chybejici_premisy_se_neopakuji(self):
        # Zapsáno po demu: dvakrát sdělené pravidlo → why_not navrhne
        # tutéž premisu vícekrát a okno vypsalo „chybí vědět" třikrát.
        self.bridge.context("Každý programátor je člověk.")
        self.bridge.context("Každý programátor je člověk.")
        odpoved = self.bridge.ask("Je Petr člověk?")
        self.assertEqual(odpoved["truth"], "UNKNOWN")
        self.assertTrue(odpoved["missing"])
        self.assertEqual(len(odpoved["missing"]),
                         len(set(odpoved["missing"])))


class TestLearnedPatterns(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.kb_file = Path(self._tmp.name) / "logic" / "kb.json"
        self.bridge = LogicBridge(_Parser(), self.kb_file)

    def tearDown(self):
        self._tmp.cleanup()

    def test_neznamy_operator_se_dopta(self):
        odpoved = self.bridge.ask("Auto může jet na silnici.")
        self.assertEqual(odpoved["kind"], "needs_pattern")
        self.assertEqual(odpoved["lemma"], "moci")
        self.assertEqual({o["operation"] for o in odpoved["options"]},
                         {"possible", "necessary", "impossible"})

    def test_nauceni_pak_modalni_odpoved(self):
        self.bridge.teach_pattern("moci", "possible", learned_from="test")
        odpoved = self.bridge.ask("Auto může jet na silnici.")
        self.assertEqual(odpoved["kind"], "modal_query")
        self.assertEqual(odpoved["operation"], "possible")
        self.assertEqual(odpoved["answer"], "Ano.")

    def test_vzor_prezije_restart(self):
        self.bridge.teach_pattern("moci", "possible", learned_from="test")
        znovu = LogicBridge(_Parser(), self.kb_file)   # „restart služby"
        self.assertEqual(znovu.state()["patterns"], 1)
        odpoved = znovu.ask("Auto může jet na silnici.")
        self.assertEqual(odpoved["kind"], "modal_query")

    def test_odvolani_maze_mapovani_ne_operaci(self):
        self.bridge.teach_pattern("moci", "possible", learned_from="test")
        vysledek = self.bridge.forget_word("moci")
        self.assertTrue(vysledek["revoked"])
        # po odvolání se zase ptá; operace POSSIBLE existuje dál
        self.assertEqual(self.bridge.ask("Auto může jet na silnici.")["kind"],
                         "needs_pattern")

    def test_kb_i_vzory_v_jednom_souboru(self):
        self.bridge.context("Petr je programátor.")
        self.bridge.teach_pattern("moci", "possible", learned_from="test")
        znovu = LogicBridge(_Parser(), self.kb_file)
        self.assertEqual(znovu.state()["facts"], 1)
        self.assertEqual(znovu.state()["patterns"], 1)


if __name__ == "__main__":
    unittest.main()
