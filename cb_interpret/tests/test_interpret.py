"""Testy interpretace nad zmraženými rozbory — obecná strukturní extrakce.

Generalizační sada (vzorky_struct) obsahuje strukturálně RŮZNÉ věty (jiná
adjektiva, předložky, entity), aby se ověřovala schopnost, ne jeden příklad
(INTERPRETATION_IR.md § 8).
"""
import unittest

from cb_logic import (Atom, AtomRef, Entity, Literal, Relation, Value,
                      Variable)
from cb_interpret.interpret import interpret_sentence
from cb_interpret.predication import ReferenceKind
from cb_interpret.tests import vzorky
from cb_interpret.tests import vzorky_struct as vs


def relnames(c):
    return {r.name for r in c.relations}


class TestSimpleFacts(unittest.TestCase):
    def test_kopula_propn_jeden_konjunkt(self):
        c = interpret_sentence(vzorky.PETR_PROGRAMATOR, "Petr je programátor.")
        self.assertEqual(c.kind, "fact")
        self.assertEqual(c.literals,
                         (Literal(Atom(Relation("programátor", 1),
                                       (Entity("petr"),))),))

    def test_kopula_negace(self):
        c = interpret_sentence(vzorky.PETR_NENI_STUDENT, "Petr není student.")
        self.assertEqual(c.kind, "fact")
        self.assertFalse(c.literals[0].positive)

    def test_sloveso_s_predlozkou(self):
        c = interpret_sentence(vzorky.PETR_BYDLI, "Petr bydlí v Praze.")
        self.assertEqual(c.kind, "fact")
        self.assertEqual(c.literals[0].atom.relation, Relation("bydlet_v", 2))

    def test_prechodne_sloveso(self):
        c = interpret_sentence(vzorky.PETR_ZNA, "Petr zná Janu.")
        self.assertEqual(c.literals[0].atom.args,
                         (Entity("petr"), Entity("jana")))


class TestCompoundPredicate(unittest.TestCase):
    """Složený přísudek se NESMÍ zjednodušit ztrátou modifikátoru."""

    def test_amod_trida_da_dve_pravidla(self):
        c = interpret_sentence(vs.AUTO_PROSTREDEK, "Auto je dopravní prostředek.")
        self.assertEqual(c.kind, "rule")
        heads = {r.head.atom.relation.name for r in c.rules}
        self.assertEqual(heads, {"prostředek", "dopravní"})  # „dopravní" žije
        self.assertLessEqual({"auto", "prostředek", "dopravní"}, relnames(c))

    def test_nmod_case_da_binarni_vztah(self):
        c = interpret_sentence(vs.SILNICE_CESTA, "Silnice je cesta pro vozidla.")
        self.assertEqual(c.kind, "rule")
        pro = [r for r in c.rules if r.head.atom.relation.name == "pro"]
        self.assertEqual(len(pro), 1)
        self.assertEqual(pro[0].head.atom.args[1], Value("vozidlo"))  # cíl

    def test_amod_jednotlivina_da_dva_fakty(self):
        c = interpret_sentence(vs.PETR_ZKUSENY, "Petr je zkušený programátor.")
        self.assertEqual(c.kind, "fact")
        rel = {l.atom.relation.name for l in c.literals}
        self.assertEqual(rel, {"programátor", "zkušený"})
        for l in c.literals:
            self.assertEqual(l.atom.args, (Entity("petr"),))

    def test_vztah_na_vlastni_jmeno(self):
        c = interpret_sentence(vs.KNIHA_DAREK, "Kniha je dárek pro Petra.")
        # „kniha" je obecné jméno → třída → pravidla
        self.assertEqual(c.kind, "rule")
        pro = [r for r in c.rules if r.head.atom.relation.name == "pro"]
        self.assertEqual(pro[0].head.atom.args[1], Entity("petr"))

    def test_provenance_mapuje_modifikator_na_token(self):
        c = interpret_sentence(vs.AUTO_PROSTREDEK, "Auto je dopravní prostředek.")
        # „dopravní" je token 3, „prostředek" token 4 (z rozboru)
        prov = dict((popis, tok) for popis, tok in c.provenance)
        self.assertEqual(prov["dopravní(auto)"], 3)
        self.assertEqual(prov["prostředek(auto)"], 4)

    def test_negace_slozeneho_prisudku_je_unparsed_ne_tiche(self):
        # „Petr není zkušený programátor" — negace složeného přísudku má
        # nejednoznačný dosah; raději unparsed než tiché zjednodušení.
        import dataclasses
        negated = tuple(
            dataclasses.replace(t, feats=dict(t.feats or {}, Polarity="Neg"))
            if t.deprel == "cop" else t for t in vs.PETR_ZKUSENY)
        c = interpret_sentence(negated, "Petr není zkušený programátor.")
        self.assertEqual(c.kind, "unparsed")


class TestRules(unittest.TestCase):
    def test_univerzalni_determinant(self):
        c = interpret_sentence(vzorky.KAZDY_PROGRAMATOR,
                               "Každý programátor je člověk.")
        self.assertEqual(c.kind, "rule")
        self.assertEqual(c.rules[0].head.atom.relation.name, "člověk")
        self.assertTrue(c.rules[0].head.positive)

    def test_zaporny_univerzalni_dvoji_zapor(self):
        c = interpret_sentence(vzorky.ZADNY_PTAK, "Žádný pták není savec.")
        self.assertEqual(c.kind, "rule")
        self.assertFalse(c.rules[0].head.positive)

    def test_genericke_cteni_holeho_noun(self):
        c = interpret_sentence(vs.PES_DOMACI, "Pes je domácí zvíře.")
        self.assertEqual(c.kind, "rule")
        heads = {r.head.atom.relation.name for r in c.rules}
        self.assertEqual(heads, {"zvíře", "domácí"})


class TestQueries(unittest.TestCase):
    def test_kopulova_otazka_propn(self):
        c = interpret_sentence(vzorky.JE_PETR_CLOVEK, "Je Petr člověk?")
        self.assertEqual(c.kind, "query")
        self.assertEqual(c.query_atoms,
                         (Atom(Relation("člověk", 1), (Entity("petr"),)),))

    def test_slozena_otazka_propn(self):
        c = interpret_sentence(vs.JE_PETR_ZKUSENY,
                               "Je Petr zkušený programátor?")
        self.assertEqual(c.kind, "query")
        rel = {a.relation.name for a in c.query_atoms}
        self.assertEqual(rel, {"programátor", "zkušený"})

    def test_obecne_jmeno_v_otazce_je_nejednoznacne(self):
        c = interpret_sentence(vs.JE_AUTO_PROSTREDEK,
                               "Je auto dopravní prostředek?")
        self.assertEqual(c.kind, "reference_ambiguous")
        self.assertEqual(c.predication.subject.kind, ReferenceKind.AMBIGUOUS)

    def test_mimo_rozsah_je_unparsed(self):
        c = interpret_sentence(vzorky.KOLIK_HODIN, "Kolik je hodin?")
        self.assertEqual(c.kind, "unparsed")


if __name__ == "__main__":
    unittest.main()
