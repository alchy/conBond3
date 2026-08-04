"""Testy dialogové vrstvy — mezery, odpověď, doplnění kontextu.

Vyhledávač i úložiště se předávají parametrem (§ 3), takže testy
nesahají na síť ani na disk mimo dočasný adresář.
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_bond import (DefinitionResolver, KnowledgeGraph, Matcher,
                     QuestionExpander, RelationMiner, Responder)
from cb_bond.tests.vzorky import (ELEKTROMOTOR, GRAVITACE, KRESTA,
                                  OTAZKA_KREST, SYNAGOGA, Veta)
from cb_field import Corpus, SentenceField


def _korpus(*vety):
    corpus = Corpus(r=1)
    for veta in vety:
        corpus.add_sentence(veta)
    return corpus


def _otazka(corpus, veta=OTAZKA_KREST):
    return SentenceField.from_sentence(veta, r=corpus.r,
                                       registry=corpus.registry)


class _Parser:
    """Atrapa parseru: zná pár vět a hlídá, kolikrát ji kdo zavolal."""

    def __init__(self, veta):
        self.veta = veta
        self.calls = 0

    def parse(self, text):
        self.calls += 1

        class _Result:
            sentences = (self.veta,)
        return _Result()


class TestMezery(unittest.TestCase):

    def test_mezera_je_osa_s_PRESNOU_nulou(self):
        # korpus zná Ježíše i „být" (kopule v GRAVITACI), ale ne křest
        corpus = _korpus(SYNAGOGA, GRAVITACE)
        responder = Responder(Matcher(corpus, spread_depth=1),
                              KnowledgeGraph())

        mezery = responder.gaps(_otazka(corpus))

        self.assertEqual(mezery, ["WORD=ADJ:pokřtěný"])

    def test_bez_mezery_je_seznam_prazdny(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        responder = Responder(Matcher(corpus, spread_depth=1),
                              KnowledgeGraph())

        self.assertEqual(responder.gaps(_otazka(corpus)), [])

    def test_pta_se_jen_na_to_co_nezna(self):
        # osy, které korpus zná (Ježíš, být), mezi chybějící nepatří —
        # systém se ptá na JEDNU věc, ne na celou otázku
        corpus = _korpus(SYNAGOGA, GRAVITACE)
        responder = Responder(Matcher(corpus, spread_depth=1),
                              KnowledgeGraph())

        mezery = responder.gaps(_otazka(corpus))

        self.assertNotIn("WORD=PROPN:Ježíš", mezery)
        self.assertNotIn("WORD=AUX:být", mezery)


class TestOdpoved(unittest.TestCase):

    def test_pri_mezere_zada_kontext_ale_ODPOVI_stejne(self):
        corpus = _korpus(SYNAGOGA, GRAVITACE)
        responder = Responder(Matcher(corpus, spread_depth=1, theta=0.0),
                              KnowledgeGraph())

        reply = responder.reply(_otazka(corpus))

        self.assertEqual(reply.outcome, "needs_context")
        self.assertEqual(reply.missing, ["WORD=ADJ:pokřtěný"])
        self.assertIsNotNone(reply.best)     # mlčet naslepo se nesmí

    def test_bez_mezery_rozhoduje_matcher(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        responder = Responder(Matcher(corpus, spread_depth=1, theta=0.0),
                              KnowledgeGraph())

        reply = responder.reply(_otazka(corpus))

        self.assertEqual(reply.outcome, "answer")
        self.assertEqual(reply.missing, [])

    def test_mlceni_matcheru_zustava_mlcenim(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        responder = Responder(Matcher(corpus, spread_depth=1, theta=99.0),
                              KnowledgeGraph())

        self.assertEqual(responder.reply(_otazka(corpus)).outcome, "silent")


class TestDoplneniKontextu(unittest.TestCase):

    def test_veta_uzivatele_jde_do_korpusu_i_do_grafu(self):
        corpus = _korpus(SYNAGOGA)
        graf = KnowledgeGraph()
        responder = Responder(Matcher(corpus, spread_depth=1), graf)
        parser = _Parser(KRESTA)

        pole = responder.append_context(KRESTA.source, parser)

        self.assertEqual(len(corpus), 2)
        self.assertIs(corpus[1], pole)
        self.assertEqual(len(graf.edges()), 7)   # hrany křestní věty
        self.assertEqual({z for *_, z in graf.edges()}, {"dialog"})

    def test_po_doplneni_se_mezera_zavre(self):
        corpus = _korpus(SYNAGOGA, GRAVITACE)
        matcher = Matcher(corpus, spread_depth=1, theta=0.0)
        responder = Responder(matcher, KnowledgeGraph())
        self.assertEqual(responder.reply(_otazka(corpus)).outcome,
                         "needs_context")

        responder.append_context(KRESTA.source, _Parser(KRESTA))

        reply = responder.reply(_otazka(corpus))
        self.assertEqual(reply.missing, [])
        self.assertEqual(reply.outcome, "answer")


class TestResolver(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Path(self._tmp.name) / "slovnik.json"
        self.addCleanup(self._tmp.cleanup)

    def test_kdyz_definice_v_korpusu_je_nikam_se_nechodi(self):
        corpus = _korpus(GRAVITACE)
        RelationMiner().mine_definitions(corpus, corpus.registry)
        volani = []
        resolver = DefinitionResolver(
            corpus, KnowledgeGraph(), _Parser(GRAVITACE),
            lookup=lambda slovo: volani.append(slovo) or None,
            store=self.store)

        zdroj = resolver.resolve("WORD=NOUN:gravitace")

        self.assertEqual(zdroj, "corpus")
        self.assertEqual(volani, [])          # síť se nevolala

    def test_neznamé_slovo_se_dohleda_a_FIXUJE_do_uloziste(self):
        corpus = _korpus(GRAVITACE)
        resolver = DefinitionResolver(
            corpus, KnowledgeGraph(), _Parser(ELEKTROMOTOR),
            lookup=lambda slovo: ELEKTROMOTOR.source, store=self.store)

        zdroj = resolver.resolve("WORD=NOUN:elektromotor")

        self.assertEqual(zdroj, "dictionary")
        self.assertEqual(len(corpus), 2)      # heslo se přidalo do korpusu
        ulozene = json.loads(self.store.read_text(encoding="utf-8"))
        self.assertIn("elektromotor", ulozene["hesla"])

    def test_podruhe_uz_se_na_sit_nechodi(self):
        # offline-first: co se jednou fixovalo, platí z disku
        corpus = _korpus(GRAVITACE)
        volani = []

        def lookup(slovo):
            volani.append(slovo)
            return ELEKTROMOTOR.source

        DefinitionResolver(corpus, KnowledgeGraph(), _Parser(ELEKTROMOTOR),
                           lookup=lookup, store=self.store
                           ).resolve("WORD=NOUN:elektromotor")
        DefinitionResolver(_korpus(GRAVITACE), KnowledgeGraph(),
                           _Parser(ELEKTROMOTOR), lookup=lookup,
                           store=self.store).resolve("WORD=NOUN:elektromotor")

        self.assertEqual(volani, ["elektromotor"])   # jen poprvé

    def test_kdyz_nic_nenajde_zbyva_dialog(self):
        corpus = _korpus(GRAVITACE)
        resolver = DefinitionResolver(
            corpus, KnowledgeGraph(), _Parser(GRAVITACE),
            lookup=lambda slovo: None, store=self.store)

        self.assertEqual(resolver.resolve("WORD=NOUN:dálnice"), "dialogue")


class TestExpander(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Path(self._tmp.name) / "slovnik.json"
        self.addCleanup(self._tmp.cleanup)

    def test_expanze_opatri_definici_chybejici_ose(self):
        corpus = _korpus(GRAVITACE)
        graf = KnowledgeGraph()
        resolver = DefinitionResolver(
            corpus, graf, _Parser(ELEKTROMOTOR),
            lookup=lambda slovo: ELEKTROMOTOR.source, store=self.store)
        expander = QuestionExpander(resolver, RelationMiner())
        otazka = SentenceField.from_sentence(
            _otazka_elektromotor(), r=1, registry=corpus.registry)

        expanze = expander.expand(otazka)

        self.assertIn("WORD=NOUN:elektromotor", expanze.definitions)
        self.assertEqual(expanze.definitions["WORD=NOUN:elektromotor"],
                         "dictionary")


def _otazka_elektromotor():
    """Otázka „Co je elektromotor?" ze zmražených dílů."""
    from cb_udpipe import Token
    return Veta("Co je elektromotor?", (
        Token(id=1, form="Co", lemma="co", upos="PRON",
              xpos="PQ--1----------",
              feats={"Case": "Nom", "PronType": "Int,Rel"},
              head=3, deprel="nsubj", deps=None, misc=None),
        Token(id=2, form="je", lemma="být", upos="AUX",
              xpos="VB-S---3P-AAI--",
              feats={"Aspect": "Imp", "Mood": "Ind", "Number": "Sing",
                     "Person": "3", "Polarity": "Pos", "Tense": "Pres",
                     "VerbForm": "Fin", "Voice": "Act"},
              head=3, deprel="cop", deps=None, misc=None),
        Token(id=3, form="elektromotor", lemma="elektromotor", upos="NOUN",
              xpos="NNIS1-----A----",
              feats={"Animacy": "Inan", "Case": "Nom", "Gender": "Masc",
                     "Number": "Sing"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=4, form="?", lemma="?", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=3, deprel="punct", deps=None, misc=None)))


if __name__ == "__main__":
    unittest.main()
