"""Testy interpretace nad zmraženými rozbory skutečného UDPipe."""
import unittest

from cb_logic import Atom, Entity, Literal, Relation, Value
from cb_interpret.interpret import interpret_sentence
from cb_interpret.tests import vzorky


class TestFacts(unittest.TestCase):
    def test_kopula_propn(self):
        c = interpret_sentence(vzorky.PETR_PROGRAMATOR,
                               "Petr je programátor.")
        self.assertEqual(c.kind, "fact")
        self.assertEqual(c.literal,
                         Literal(Atom(Relation("programátor", 1),
                                      (Entity("petr"),))))
        self.assertEqual(c.entities, (Entity("petr"),))

    def test_kopula_negace(self):
        c = interpret_sentence(vzorky.PETR_NENI_STUDENT,
                               "Petr není student.")
        self.assertEqual(c.kind, "fact")
        self.assertFalse(c.literal.positive)
        self.assertEqual(c.literal.atom.relation.name, "student")

    def test_sloveso_s_predlozkou(self):
        c = interpret_sentence(vzorky.PETR_BYDLI, "Petr bydlí v Praze.")
        self.assertEqual(c.kind, "fact")
        self.assertEqual(c.literal.atom.relation, Relation("bydlet_v", 2))
        self.assertEqual(c.literal.atom.args,
                         (Entity("petr"), Entity("praha")))

    def test_prechodne_sloveso(self):
        c = interpret_sentence(vzorky.PETR_ZNA, "Petr zná Janu.")
        self.assertEqual(c.literal.atom.relation, Relation("znát", 2))
        self.assertEqual(c.literal.atom.args,
                         (Entity("petr"), Entity("jana")))


class TestRules(unittest.TestCase):
    def test_univerzalni_determinant(self):
        c = interpret_sentence(vzorky.KAZDY_PROGRAMATOR,
                               "Každý programátor je člověk.")
        self.assertEqual(c.kind, "rule")
        self.assertEqual(c.rule.head.atom.relation.name, "člověk")
        self.assertTrue(c.rule.head.positive)
        self.assertEqual(c.relations,
                         (Relation("programátor", 1), Relation("člověk", 1)))

    def test_zaporny_univerzalni_dvoji_zapor(self):
        c = interpret_sentence(vzorky.ZADNY_PTAK, "Žádný pták není savec.")
        self.assertEqual(c.kind, "rule")
        self.assertFalse(c.rule.head.positive)   # jedna logická negace
        self.assertEqual(c.rule.head.atom.relation.name, "savec")

    def test_genericke_cteni_holeho_noun(self):
        c = interpret_sentence(vzorky.PES_SAVEC, "Pes je savec.")
        self.assertEqual(c.kind, "rule")
        self.assertEqual(c.rule.head.atom.relation.name, "savec")

    def test_mnozne_cislo_tot(self):
        c = interpret_sentence(vzorky.VSICHNI_PROGRAMATORI,
                               "Všichni programátoři jsou lidé.")
        self.assertEqual(c.kind, "rule")
        self.assertEqual(c.rule.head.atom.relation.name, "lidé")


class TestQueriesAndHonesty(unittest.TestCase):
    def test_kopulova_otazka(self):
        c = interpret_sentence(vzorky.JE_PETR_CLOVEK, "Je Petr člověk?")
        self.assertEqual(c.kind, "query")
        self.assertEqual(c.literal,
                         Literal(Atom(Relation("člověk", 1),
                                      (Entity("petr"),))))

    def test_mimo_rozsah_je_unparsed_s_duvodem(self):
        c = interpret_sentence(vzorky.KOLIK_HODIN, "Kolik je hodin?")
        self.assertEqual(c.kind, "unparsed")
        self.assertIsNotNone(c.note)

    def test_obecny_podmet_slovesa_je_unparsed(self):
        c = interpret_sentence(vzorky.SLUNCE_SVITI, "Slunce svítí.")
        self.assertEqual(c.kind, "unparsed")

    def test_prejmenovani_lemmat_meni_jen_jmena(self):
        """Struktura rozhoduje; jména jsou data (zadání § 43)."""
        import dataclasses
        renamed = tuple(
            dataclasses.replace(t, lemma=f"rel_{t.lemma}")
            if t.upos in ("NOUN", "PROPN") else t
            for t in vzorky.PETR_PROGRAMATOR)
        c = interpret_sentence(renamed, "X je Y.")
        self.assertEqual(c.kind, "fact")
        self.assertEqual(c.literal.atom.relation.name, "rel_programátor")
        self.assertEqual(c.literal.atom.args[0].id, "rel_petr")


if __name__ == "__main__":
    unittest.main()
