"""Testy detekce mezery a dialogu — krok 4 handoveru.

Zmražená data podle skutečných výstupů UDPipe z 2026-08-04: otázka
„Kde byl pokřtěn Ježíš?" a věty „Dálnice je silnice." / o křtu
(sdílená s test_graph). Test nesmí potřebovat běžící službu (§ 13).
"""

import unittest

from cb_field.corpus import Corpus
from cb_field.dialog import Reply, append_context, axis_coverage, \
    expand_question, fact_gaps, reply
from cb_field.field import SentenceField
from cb_field.graph import FactGraph
from cb_field.tests.test_graph import KREST, _Sentence
from cb_udpipe import Token


def _tok(id, form, lemma, upos, feats, head, deprel):
    return Token(id=id, form=form, lemma=lemma, upos=upos, xpos="",
                 feats=feats, head=head, deprel=deprel, deps=None,
                 misc=None)


#: „Kde byl pokřtěn Ježíš?" — dané osy jsou být/pokřtěný/Ježíš;
#: řádek „Kde" je tázací (QLEM), ten se nekryje, ten se odpovídá.
OTAZKA_KREST = (
    _tok(1, "Kde", "kde", "ADV", {"PronType": "Int,Rel"}, 3, "advmod"),
    _tok(2, "byl", "být", "AUX",
         {"Aspect": "Imp", "Gender": "Masc", "Number": "Sing",
          "Polarity": "Pos", "Tense": "Past", "VerbForm": "Part",
          "Voice": "Act"}, 3, "aux:pass"),
    _tok(3, "pokřtěn", "pokřtěný", "ADJ",
         {"Aspect": "Perf", "Degree": "Pos", "Gender": "Masc",
          "Number": "Sing", "Polarity": "Pos", "Variant": "Short",
          "VerbForm": "Part", "Voice": "Pass"}, 0, "root"),
    _tok(4, "Ježíš", "Ježíš", "PROPN",
         {"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
          "NameType": "Giv", "Number": "Sing"}, 3, "nsubj:pass"),
    _tok(5, "?", "?", "PUNCT", None, 3, "punct"),
)

#: „Dálnice je silnice." — korpus, který zná být, ale ne křest.
DALNICE = (
    _tok(1, "Dálnice", "dálnice", "NOUN",
         {"Case": "Nom", "Gender": "Fem", "Number": "Sing"}, 3, "nsubj"),
    _tok(2, "je", "být", "AUX",
         {"Aspect": "Imp", "Mood": "Ind", "Number": "Sing",
          "Person": "3", "Polarity": "Pos", "Tense": "Pres",
          "VerbForm": "Fin", "Voice": "Act"}, 3, "cop"),
    _tok(3, "silnice", "silnice", "NOUN",
         {"Case": "Nom", "Gender": "Fem", "Number": "Sing"}, 0, "root"),
    _tok(4, ".", ".", "PUNCT", None, 3, "punct"),
)


class _Parser:
    """Atrapa parseru (§ 13) — vrací připravenou zmraženou větu."""

    def __init__(self, tokens):
        self._sentence = _Sentence(tokens)

    def parse(self, text):
        class _Result:
            sentences = [self._sentence]
        return _Result()


def _question(corpus):
    return SentenceField(OTAZKA_KREST, r=corpus.r,
                         registry=corpus.registry)


class TestFactGaps(unittest.TestCase):

    def test_pokryta_otazka_nema_mezeru(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(KREST))
        self.assertEqual(fact_gaps(_question(corpus), corpus), [])

    def test_mrtve_osy_se_oznaci_tazaci_ne(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(DALNICE))
        gaps = fact_gaps(_question(corpus), corpus)
        # být korpus zná; pokřtěný a Ježíš ne; tázací „kde" se nekryje
        self.assertEqual(gaps, ["WORD=ADJ:pokřtěný", "WORD=PROPN:Ježíš"])

    def test_pokryti_je_propast_ne_skala(self):
        # mrtvá osa dává PŘESNĚ nulu (v registru vůbec není), pokryté
        # osy začínají vysoko — proto krok 4 nepotřebuje práh
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(DALNICE))
        coverage = axis_coverage(_question(corpus), corpus)
        self.assertEqual(coverage["WORD=ADJ:pokřtěný"], 0.0)
        self.assertGreater(coverage["WORD=AUX:být"], 0.5)


class TestReply(unittest.TestCase):

    def test_odpovida_se_vzdy_i_pri_mezere(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(DALNICE))
        answer = reply(_question(corpus), corpus)
        self.assertIsInstance(answer, Reply)
        self.assertEqual(answer.outcome, "needs_context")
        self.assertIsNotNone(answer.best)            # nemlčí — vidí se,
        self.assertTrue(answer.missing)              # kam systém sáhl

    def test_bez_mezery_prebira_vychodisko_parovani(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(KREST))
        answer = reply(_question(corpus), corpus)
        self.assertIn(answer.outcome, ("odpoved", "dotaz", "nevim"))
        self.assertEqual(answer.missing, [])


class TestExpandQuestion(unittest.TestCase):

    def test_expanze_doplni_definice_a_cilene_derivace(self):
        # otázka o křtu: definice se opatří pro jmenné osy (dálnice
        # v korpusu není → lookup), derivace se párují JEN kolem
        # kmenů otázky a expanze — nic plošného
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(KREST))
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        question = _question(corpus)
        looked = []
        outcome = expand_question(
            question, corpus, graph, _Parser(KREST),
            lookup=lambda term: looked.append(term) or None)
        # jmenné dané osy otázky šly do opatřování definic
        self.assertIn("Ježíš", looked)
        self.assertEqual(outcome["definice"]["WORD=PROPN:Ježíš"],
                         "dialog")     # lookup nic nevrátil
        # derivace se párovaly jen kolem kmenů otázky (cíleně) —
        # okolí je v outcome a nic plošného se nepřidalo
        self.assertIn("derivaci", outcome)
        derivace = [1 for _s, _d, _w, src in corpus.registry.links()
                    if src == "derivace"]
        self.assertEqual(len(derivace), outcome["derivaci"])

    def test_veta_uzivatele_jde_stejnou_cestou_se_zdrojem_dialog(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(DALNICE))
        graph = FactGraph()
        before = len(corpus)
        field = append_context("Věta od uživatele.", corpus, graph,
                               _Parser(KREST))
        self.assertEqual(len(corpus), before + 1)
        self.assertIs(corpus[before], field)
        self.assertEqual(corpus.documents[before], "dialog")
        sources = {src for _s, _d, _rel, _w, src in graph.edges()}
        self.assertEqual(sources, {"dialog"})        # hrany jdou odlišit

    def test_mezera_po_doplneni_kontextu_zmizi(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(DALNICE))
        graph = FactGraph()
        question = _question(corpus)
        self.assertTrue(fact_gaps(question, corpus))
        append_context("Kontext o křtu.", corpus, graph, _Parser(KREST))
        self.assertEqual(fact_gaps(question, corpus), [])


if __name__ == "__main__":
    unittest.main()
