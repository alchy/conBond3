"""Testy interpretace nad zmraženými rozbory — obecná strukturní extrakce.

Generalizační sada (vzorky_struct) obsahuje strukturálně RŮZNÉ věty (jiná
adjektiva, předložky, entity), aby se ověřovala schopnost, ne jeden příklad
(INTERPRETATION_IR.md § 8).
"""
import unittest

from cb_logic import (Atom, AtomRef, Entity, Literal, Relation, Value,
                      Variable, to_text)
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


class TestVerbalCompound(unittest.TestCase):
    """Slovesná věta se rozkládá bezztrátově — HANDOVER 4.1.1, expanze § 2."""

    def test_dve_obliky_daji_dva_konjunkty(self):
        c = interpret_sentence(vs.PETR_JEDE_AUTEM,
                               "Petr jede autem po dálnici.")
        self.assertEqual(c.kind, "fact")
        rel = {l.atom.relation.name for l in c.literals}
        self.assertEqual(rel, {"jet_ins", "jet_po"})   # „autem" se neztrácí
        for l in c.literals:
            self.assertEqual(l.atom.args[0], Entity("petr"))

    def test_otazka_nad_konjunkci(self):
        c = interpret_sentence(vs.JEDE_PETR_AUTEM,
                               "Jede Petr autem po dálnici?")
        self.assertEqual(c.kind, "query")
        self.assertEqual({a.relation.name for a in c.query_atoms},
                         {"jet_ins", "jet_po"})

    def test_prislovce_je_vlastnost_deje(self):
        c = interpret_sentence(vs.PETR_RYCHLE_JEDE,
                               "Petr rychle jede po dálnici.")
        self.assertEqual(c.kind, "fact")
        rel = {l.atom.relation.name for l in c.literals}
        self.assertEqual(rel, {"jet_rychle", "jet_po"})  # „rychle" žije
        rychle = [l for l in c.literals
                  if l.atom.relation.name == "jet_rychle"][0]
        self.assertEqual(rychle.atom.args, (Entity("petr"),))

    def test_holy_dativ_je_vztah_pojmenovany_padem(self):
        c = interpret_sentence(vs.PETR_DAL_PAVLOVI, "Petr dal Pavlovi knihu.")
        self.assertEqual(c.kind, "fact")
        rel = {l.atom.relation.name for l in c.literals}
        self.assertEqual(rel, {"dát", "dát_dat"})
        dativ = [l for l in c.literals
                 if l.atom.relation.name == "dát_dat"][0]
        self.assertEqual(dativ.atom.args, (Entity("petr"), Entity("pavel")))

    def test_rozvity_argument_je_unparsed_ne_tichy(self):
        # „červené auto" jako předmět: amod nejde bez událostí věrně
        # snížit — poctivé odmítnutí místo tichého zahození
        c = interpret_sentence(vs.PETR_RIDI_AUTO, "Petr řídí červené auto.")
        self.assertEqual(c.kind, "unparsed")

    def test_generalizace_unseen_veta(self):
        c = interpret_sentence(vs.MARIE_PRACUJE, "Marie pracuje v Brně.")
        self.assertEqual(c.kind, "fact")
        self.assertEqual(c.literals[0].atom.relation,
                         Relation("pracovat_v", 2))
        self.assertEqual(c.literals[0].atom.args,
                         (Entity("marie"), Entity("brno")))

    def test_generalizace_prejmenovani(self):
        import dataclasses
        mapa = {"Petr": "Karel", "jet": "letět", "auto": "vlak",
                "dálnice": "pole"}
        prejmenovano = tuple(
            dataclasses.replace(t, lemma=mapa.get(t.lemma, t.lemma))
            for t in vs.PETR_JEDE_AUTEM)
        c = interpret_sentence(prejmenovano, "Karel letí vlakem po poli.")
        self.assertEqual({l.atom.relation.name for l in c.literals},
                         {"letět_ins", "letět_po"})

    def test_negace_slozeneho_prisudku_je_unparsed(self):
        import dataclasses
        negovano = tuple(
            dataclasses.replace(t, feats=dict(t.feats, Polarity="Neg"))
            if t.deprel == "root" else t for t in vs.PETR_JEDE_AUTEM)
        c = interpret_sentence(negovano, "Petr nejede autem po dálnici.")
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


class TestVerbalRules(unittest.TestCase):
    """Slovesná věta s obecným podmětem — třídní čtení (po demu J.)."""

    def test_obecny_podmet_tvrzeni_da_pravidlo(self):
        c = interpret_sentence(vs.OVOCE_OBSAHUJE, "Ovoce obsahuje vitamíny.")
        self.assertEqual(c.kind, "rule")
        self.assertLessEqual({"ovoce", "obsahovat"}, relnames(c))
        [rule] = c.rules
        self.assertEqual(rule.head.atom.relation, Relation("obsahovat", 2))
        self.assertEqual(rule.head.atom.args[1], Value("vitamín"))

    def test_univerzalni_determinant_slovesne_vety(self):
        c = interpret_sentence(vs.KAZDE_OVOCE,
                               "Každé ovoce obsahuje vitamíny.")
        self.assertEqual(c.kind, "rule")
        self.assertLessEqual({"ovoce", "obsahovat"}, relnames(c))

    def test_obecny_podmet_otazky_se_dopta(self):
        c = interpret_sentence(vs.LETAJI_PTACI, "Létají ptáci?")
        self.assertEqual(c.kind, "reference_ambiguous")
        self.assertEqual(c.subject_lemma, "pták")
        self.assertTrue(c.literals)     # konjunkty s proměnnou pro rozřešení

    def test_generalizace_unseen_nepredmetna(self):
        c = interpret_sentence(vs.PTACI_LETAJI, "Ptáci létají.")
        self.assertEqual(c.kind, "rule")
        [rule] = c.rules
        self.assertEqual(rule.head.atom.relation, Relation("létat", 1))

    def test_rozbor_bez_podmetu_je_unparsed(self):
        # „Obsahuje citron vitamíny?" — UDPipe dá dva obj (nom == acc);
        # bez podmětu poctivé odmítnutí, ne hádání, kdo je podmět
        c = interpret_sentence(vs.OBSAHUJE_CITRON,
                               "Obsahuje citron vitamíny?")
        self.assertEqual(c.kind, "unparsed")


class TestPassiveParticiple(unittest.TestCase):
    """Trpné příčestí (aux:pass) a přívlastek podmětu — po demu J."""

    def test_pasivum_da_pravidla_s_privlastkem_podmetu_v_tele(self):
        c = interpret_sentence(vs.PROSTREDEK_URCEN,
                               "Dopravní prostředek je určen k přepravě.")
        self.assertEqual(c.kind, "rule")
        heads = {r.head.atom.relation.name for r in c.rules}
        self.assertEqual(heads, {"určený", "k"})
        # „dopravní" patří do TĚLA pravidla (popis podmětu), ne do hlavy
        self.assertLessEqual({"prostředek", "dopravní"}, relnames(c))
        for rule in c.rules:
            self.assertIn("dopravní", to_text(rule.body))

    def test_rozvity_cil_vztahu_je_unparsed_ne_tichy(self):
        # „k přepravě nákladů a osob" — genitivy a koordinace pod cílem
        # vztahu zatím rozklad neunese → poctivé odmítnutí
        c = interpret_sentence(
            vs.PROSTREDEK_URCEN_DLOUHY,
            "Dopravní prostředek je určen k přepravě nákladů a osob.")
        self.assertEqual(c.kind, "unparsed")
        self.assertIn("rozvitý cíl", c.note)

    def test_pasivni_otazka_se_dopta(self):
        c = interpret_sentence(vs.JE_AUTO_URCENO,
                               "Je auto určeno k přepravě?")
        self.assertEqual(c.kind, "reference_ambiguous")
        self.assertEqual(c.subject_lemma, "auto")

    def test_generalizace_unseen_pasivum(self):
        c = interpret_sentence(vs.NUZ_VYROBEN, "Nůž je vyroben z oceli.")
        self.assertEqual(c.kind, "rule")
        heads = {r.head.atom.relation.name for r in c.rules}
        self.assertEqual(heads, {"vyrobený", "z"})

    def test_slovesna_veta_s_privlastkem_podmetu(self):
        c = interpret_sentence(vs.PROSTREDEK_SLOUZI,
                               "Dopravní prostředek slouží k přepravě.")
        self.assertEqual(c.kind, "rule")
        [rule] = c.rules
        self.assertEqual(rule.head.atom.relation, Relation("sloužit_k", 2))
        self.assertIn("dopravní", to_text(rule.body))


class TestGenitiveNmod(unittest.TestCase):
    """Holý genitiv je vztah, ne tiché zahození — HANDOVER 4.1.2."""

    def test_genitiv_jednotlivina_da_tri_fakty(self):
        c = interpret_sentence(vs.PRAHA_MESTO_CESKA,
                               "Praha je hlavní město Česka.")
        self.assertEqual(c.kind, "fact")
        rel = {l.atom.relation.name for l in c.literals}
        self.assertEqual(rel, {"město", "hlavní", "gen"})   # „Česka" žije
        gen = [l for l in c.literals if l.atom.relation.name == "gen"][0]
        self.assertEqual(gen.atom.args, (Entity("praha"), Entity("česko")))

    def test_genitiv_otazka(self):
        c = interpret_sentence(vs.JE_PRAHA_MESTO_CESKA,
                               "Je Praha hlavní město Česka?")
        self.assertEqual(c.kind, "query")
        self.assertEqual({a.relation.name for a in c.query_atoms},
                         {"město", "hlavní", "gen"})

    def test_genitiv_trida_da_pravidla(self):
        c = interpret_sentence(vs.KLIC_SOUCAST_ZAMKU,
                               "Klíč je součást zámku.")
        self.assertEqual(c.kind, "rule")
        heads = {r.head.atom.relation.name for r in c.rules}
        self.assertEqual(heads, {"součást", "gen"})
        gen = [r for r in c.rules if r.head.atom.relation.name == "gen"][0]
        self.assertEqual(gen.head.atom.args[1], Value("zámek"))

    def test_nmod_bez_predlozky_i_padu_je_unparsed(self):
        import dataclasses
        bez_padu = tuple(
            dataclasses.replace(t, feats=None) if t.deprel == "nmod" else t
            for t in vs.PRAHA_MESTO_CESKA)
        c = interpret_sentence(bez_padu, "Praha je hlavní město Česka.")
        self.assertEqual(c.kind, "unparsed")   # pojistka, ne tiché zahození

    def test_generalizace_unseen_trida(self):
        c = interpret_sentence(vs.KNIHA_MAJETEK, "Kniha je majetek knihovny.")
        self.assertEqual(c.kind, "rule")
        self.assertEqual({r.head.atom.relation.name for r in c.rules},
                         {"majetek", "gen"})

    def test_generalizace_unseen_jednotlivina(self):
        c = interpret_sentence(vs.VLTAVA_REKA, "Vltava je řeka Česka.")
        self.assertEqual(c.kind, "fact")
        self.assertEqual({l.atom.relation.name for l in c.literals},
                         {"řeka", "gen"})


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

    def test_ukazovaci_zajmeno_je_mimo_rozsah(self):
        # „To je auto." — odkaz do rozhovoru (koreference) je mimo rozsah;
        # tiché čtení „to" jako třídy by vyrábělo pravidla to(X) → …
        import dataclasses
        to_je_auto = tuple(
            dataclasses.replace(t, lemma="to",
                                feats=dict(t.feats, PronType="Dem"))
            if t.upos == "PRON" else t for t in vs.CO_JE_AUTO)
        c = interpret_sentence(to_je_auto, "To je auto.")
        self.assertEqual(c.kind, "unparsed")
        self.assertIn("zájmenný podmět", c.note)


class TestDefinitionQuery(unittest.TestCase):
    """Definiční otázky „Kdo/Co je X?" — výčet z báze (po demu J.)."""

    def test_kdo_je_propn(self):
        # kořen kdo (PRON Int) + nsubj Hrabal
        c = interpret_sentence(vs.KDO_JE_HRABAL, "Kdo je Hrabal?")
        self.assertEqual(c.kind, "definition_query")
        self.assertEqual(c.subject_lemma, "Hrabal")
        self.assertEqual(c.subject_upos, "PROPN")

    def test_co_je_to_noun(self):
        # „to" je discourse — nesmí rozbít čtení
        c = interpret_sentence(vs.CO_JE_TO_VITAMIN, "Co je to vitamín?")
        self.assertEqual(c.kind, "definition_query")
        self.assertEqual(c.subject_lemma, "vitamín")
        self.assertEqual(c.subject_upos, "NOUN")

    def test_obraceny_tvar_stromu(self):
        # „Co je auto?" — kořen auto, nsubj co: týž druh otázky
        c = interpret_sentence(vs.CO_JE_AUTO, "Co je auto?")
        self.assertEqual(c.kind, "definition_query")
        self.assertEqual(c.subject_lemma, "auto")
        self.assertEqual(c.subject_upos, "NOUN")


if __name__ == "__main__":
    unittest.main()
