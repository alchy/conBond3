"""Testy registru vertikál: append-only chování a round-trip serializace.

Zmražená data: tokeny jsou zapsané přímo tady jako literály — test nesmí
potřebovat běžící službu (§ 13). Hodnoty odpovídají skutečným výstupům
UDPipe z 2026-08-03 (věty „Šla kočka…", „Kde je Petr…", „Pět psů… 125…").
"""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cb_field import (Activations, Representation, VerticalRegistry,
                      activations, expand_token, seed_anchor_links)
from cb_field.service import is_question
from cb_field.registry import FORMAT_VERSION
from cb_udpipe import Token

# „Petr" — PROPN s NameType: v COMPLETE dostane WORD=PROPN:Petr.
PETR = Token(id=1, form="Petr", lemma="Petr", upos="PROPN",
             xpos="NNMS1-----A----",
             feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                    "NameType": "Giv", "Number": "Sing"},
             head=6, deprel="nsubj", deps=None, misc=None)

# „Šla" — multiatribut: Gender i Number nesou dvě hodnoty najednou.
SLA = Token(id=1, form="Šla", lemma="jít", upos="VERB",
            xpos="VpQW---XR-AAI--",
            feats={"Aspect": "Imp", "Gender": "Fem,Neut",
                   "Number": "Plur,Sing", "Polarity": "Pos",
                   "Tense": "Past", "VerbForm": "Part", "Voice": "Act"},
            head=0, deprel="root", deps=None, misc=None)

# „do" — zavřená třída ADP: dostane LEM vertikálu.
DO = Token(id=3, form="do", lemma="do", upos="ADP", xpos="RR--2----------",
           feats={"AdpType": "Prep", "Case": "Gen"},
           head=4, deprel="case", deps=None, misc=None)

# „Kde" — zájmenné příslovce: ADV s PronType, dostane LEM vertikálu.
KDE = Token(id=1, form="Kde", lemma="kde", upos="ADV", xpos="Db-------------",
            feats={"PronType": "Int,Rel"},
            head=0, deprel="advmod", deps=None, misc=None)

# „125" — NUM s číslicemi v lemmatu: LEM vertikálu dostat nesmí.
N125 = Token(id=7, form="125", lemma="125", upos="NUM",
             xpos="C=-------------", feats={"NumForm": "Digit"},
             head=8, deprel="nummod:gov", deps=None, misc=None)

# „pes" — otevřená třída NOUN: LEM vertikálu dostat nesmí.
PES = Token(id=2, form="pes", lemma="pes", upos="NOUN",
            xpos="NNMS1-----A----",
            feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                   "Number": "Sing"},
            head=1, deprel="nsubj", deps=None, misc=None)


class TestSouborV2(unittest.TestCase):

    def test_ulozeny_registr_nese_obsazeni_i_verzi(self):
        reg = VerticalRegistry(anchors=False)
        reg.link("A", "B", 0.5)
        reg.set_custom_axes(["NOUN:rok"])

        with tempfile.TemporaryDirectory() as tmp:
            cesta = reg.save(Path(tmp) / "registr.json")
            data = json.loads(cesta.read_text(encoding="utf-8"))
            self.assertEqual(data["format_version"], 2)
            self.assertEqual(data["custom_axes"], ["NOUN:rok"])
            self.assertEqual(data["axis_version"], 1)

            zpet = VerticalRegistry.load(cesta)
            self.assertEqual(zpet.custom_axes, ("NOUN:rok",))
            self.assertEqual(zpet.axis_version, 1)
            self.assertEqual(zpet.keys(), reg.keys())


class TestCustomSloty(unittest.TestCase):
    """Pojmenované neurony vstupní vrstvy — obsazení, verze, vratnost."""

    def test_obsazeni_pripise_osy_a_zvedne_verzi(self):
        reg = VerticalRegistry(anchors=False)
        self.assertEqual(reg.axis_version, 0)

        zmeny = reg.set_custom_axes(["NOUN:rok", "VERB:mít"])

        self.assertEqual(reg.axis_version, 1)
        self.assertIn("CUSTOM=NOUN:rok", reg)
        self.assertEqual(zmeny["pridano"], 2)
        self.assertEqual(zmeny["odebrano"], 0)

    def test_stejne_obsazeni_verzi_NEZVEDNE(self):
        # bez změny osy se nemá co přeučovat (naměřená stabilizace
        # 38 → 16 % výměn na přírůstek korpusu)
        reg = VerticalRegistry(anchors=False)
        reg.set_custom_axes(["NOUN:rok"])

        zmeny = reg.set_custom_axes(["NOUN:rok"])

        self.assertEqual(reg.axis_version, 1)
        self.assertEqual((zmeny["pridano"], zmeny["odebrano"]), (0, 0))

    def test_uvolneny_slot_nenecha_za_sebou_hrany(self):
        reg = VerticalRegistry(anchors=False)
        reg.set_custom_axes(["NOUN:rok"])
        reg.link("QLEM=ADV:kdy", "CUSTOM=NOUN:rok", 0.5)

        zmeny = reg.set_custom_axes(["VERB:mít"])

        self.assertEqual(zmeny["odebrano"], 1)
        self.assertEqual(zmeny["hran_odebrano"], 1)
        self.assertIsNone(reg.get_link("QLEM=ADV:kdy", "CUSTOM=NOUN:rok"))
        # klíč v ose zůstane — osa je append-only (princip 3)
        self.assertIn("CUSTOM=NOUN:rok", reg)
        self.assertNotIn("NOUN:rok", reg.custom_axes)

    def test_is_custom_rekne_jestli_ma_slovo_slot(self):
        reg = VerticalRegistry(anchors=False)
        reg.set_custom_axes(["NOUN:rok"])

        self.assertTrue(reg.is_custom("NOUN:rok"))
        self.assertFalse(reg.is_custom("PROPN:Hrabal"))


class TestSnapshot(unittest.TestCase):

    def test_restore_vrati_stav_BIT_PO_BITU(self):
        reg = VerticalRegistry(anchors=False)
        reg.link("A", "B", 0.5)
        reg.set_custom_axes(["NOUN:rok"])
        snap = reg.snapshot()

        reg.set_custom_axes(["VERB:mít", "ADJ:nový"])
        reg.link("A", "B", -0.9)
        reg.link("C", "D", 0.3)
        reg.restore(snap)

        self.assertEqual(reg.custom_axes, ("NOUN:rok",))
        self.assertAlmostEqual(reg.get_link("A", "B"), 0.5, places=6)
        self.assertIsNone(reg.get_link("C", "D"))
        self.assertEqual(reg.axis_version, 1)   # včetně verze

    def test_snapshot_je_odolny_proti_pozdejsim_zmenam(self):
        reg = VerticalRegistry(anchors=False)
        reg.link("A", "B", 0.5)
        snap = reg.snapshot()

        reg.link("A", "B", 0.1)
        reg.restore(snap)

        self.assertAlmostEqual(reg.get_link("A", "B"), 0.5, places=6)

    def test_klice_pridane_po_snapshotu_zustanou(self):
        # osa je append-only: rollback ruší vazby a obsazení, ne klíče
        reg = VerticalRegistry(anchors=False)
        snap = reg.snapshot()
        reg.add("NOVA=osa")

        reg.restore(snap)

        self.assertIn("NOVA=osa", reg)


class TestCteniAMazaniVazeb(unittest.TestCase):

    def test_get_link_vrati_vahu_a_u_nezname_dvojice_None(self):
        reg = VerticalRegistry(anchors=False)
        reg.link("A", "B", 0.7)

        self.assertAlmostEqual(reg.get_link("A", "B"), 0.7, places=6)
        self.assertIsNone(reg.get_link("B", "A"))   # vazba je směrová
        self.assertIsNone(reg.get_link("A", "C"))

    def test_unlink_vazbu_odstrani_ale_klice_nechá(self):
        reg = VerticalRegistry(anchors=False)
        reg.link("A", "B", 0.7)

        self.assertTrue(reg.unlink("A", "B"))
        self.assertIsNone(reg.get_link("A", "B"))
        self.assertIn("A", reg)          # osa je append-only (princip 3)
        self.assertIn("B", reg)

    def test_unlink_neexistujici_vazby_je_False_ne_vyjimka(self):
        reg = VerticalRegistry(anchors=False)

        self.assertFalse(reg.unlink("A", "B"))


class TestAppendOnly(unittest.TestCase):

    def test_add_prideluje_indexy_a_je_idempotentni(self):
        reg = VerticalRegistry(anchors=False)
        self.assertEqual(reg.add("UPOS=NOUN"), 0)
        self.assertEqual(reg.add("Case=Nom"), 1)
        self.assertEqual(reg.add("UPOS=NOUN"), 0)  # existující index se nemění
        self.assertEqual(len(reg), 2)

    def test_klic_podle_pozicniho_argumentu(self):
        reg = VerticalRegistry(["UPOS=NOUN", "Case=Nom"], anchors=False)
        self.assertEqual(reg.key(0), "UPOS=NOUN")
        self.assertEqual(reg.key(1), "Case=Nom")
        self.assertEqual(reg.index("Case=Nom"), 1)
        with self.assertRaises(IndexError):
            reg.key(2)
        with self.assertRaises(KeyError):
            reg.index("UPOS=VERB")


class TestRoundTrip(unittest.TestCase):
    """Zkouška funkčnosti: aktivace → vektor → zpět tentýž JSON objekt."""

    def test_multiatribut_prezije_cestu_tam_a_zpet(self):
        acts = activations(expand_token(SLA))
        # multiatribut je rozvinutý: obě hodnoty Gender i Number zvlášť
        self.assertIn("Gender=Fem", acts)
        self.assertIn("Gender=Neut", acts)
        self.assertIn("Number=Plur", acts)
        self.assertIn("Number=Sing", acts)

        reg = VerticalRegistry(anchors=False)
        vec = reg.vectorize(acts)
        self.assertEqual(vec.dtype, np.float32)
        self.assertEqual(len(vec), len(acts))
        self.assertEqual(reg.unvectorize(vec), acts)

    def test_zaporna_vaha_prezije(self):
        reg = VerticalRegistry(anchors=False)
        vec = reg.vectorize({"Polarity=Neg": -0.7})
        self.assertEqual(reg.unvectorize(vec), {"Polarity=Neg": -0.7})

    def test_nulovy_vektor_je_prazdny_objekt(self):
        reg = VerticalRegistry(["UPOS=NOUN", "Case=Nom"], anchors=False)
        self.assertEqual(reg.unvectorize(np.zeros(2)), {})

    def test_grow_false_odmitne_neznamou_vertikalu(self):
        reg = VerticalRegistry(["UPOS=NOUN"], anchors=False)
        with self.assertRaises(ValueError):
            reg.vectorize({"UPOS=VERB": 0.7}, grow=False)

    def test_delsi_vektor_nez_registr_je_chyba(self):
        reg = VerticalRegistry(["UPOS=NOUN"], anchors=False)
        with self.assertRaises(ValueError):
            reg.unvectorize(np.zeros(5))


class TestPravidlaAktivaci(unittest.TestCase):

    def test_zavrena_trida_dostane_lem(self):
        # klíč nese i UPOS: spojkové „jak" je jiné „jak" než příslovečné
        self.assertIn("LEM=ADP:do", activations(expand_token(DO)))

    def test_zajmenne_prislovce_dostane_lem_a_prontype(self):
        acts = activations(expand_token(KDE))
        self.assertIn("LEM=ADV:kde", acts)
        self.assertIn("PronType=Int", acts)   # multiatribut Int,Rel
        self.assertIn("PronType=Rel", acts)

    def test_tazaci_veta_prevrati_kde_na_otazkovou_stranu(self):
        acts = activations(expand_token(KDE), question=True)
        self.assertIn("QLEM=ADV:kde", acts)          # tázací kde je jiné kde
        self.assertNotIn("LEM=ADV:kde", acts)
        self.assertEqual(acts["PronType=Int"], 0.7)  # otázka: Int vyhrává
        self.assertEqual(acts["PronType=Rel"], -0.7) # Rel = negativní vazba

    def test_oznamovaci_veta_necha_kde_na_strane_odpovedi(self):
        acts = activations(expand_token(KDE), question=False)
        self.assertIn("LEM=ADV:kde", acts)
        self.assertNotIn("QLEM=ADV:kde", acts)
        self.assertEqual(acts["PronType=Int"], -0.7)
        self.assertEqual(acts["PronType=Rel"], 0.7)

    def test_is_question_pozna_otaznik(self):
        OTAZNIK = Token(id=9, form="?", lemma="?", upos="PUNCT",
                        xpos="Z:-------------", feats=None,
                        head=1, deprel="punct", deps=None, misc=None)
        TECKA = Token(id=9, form=".", lemma=".", upos="PUNCT",
                      xpos="Z:-------------", feats=None,
                      head=1, deprel="punct", deps=None, misc=None)
        self.assertTrue(is_question([PES, OTAZNIK]))
        self.assertFalse(is_question([PES, TECKA]))

    def test_cislice_lem_nedostanou(self):
        acts = activations(expand_token(N125))
        self.assertFalse(any(k.startswith(("LEM=", "QLEM=")) for k in acts))

    def test_otevrena_trida_lem_nedostane(self):
        acts = activations(expand_token(PES))
        self.assertFalse(any(k.startswith("LEM=") for k in acts))


# „byli" — minulý čas + množné číslo: dvojí kotva (čas i množství).
BYLI = Token(id=2, form="byli", lemma="být", upos="AUX",
             xpos="VpMP---XR-AAI--",
             feats={"Animacy": "Anim", "Aspect": "Imp", "Gender": "Masc",
                    "Number": "Plur", "Polarity": "Pos", "Tense": "Past",
                    "VerbForm": "Part", "Voice": "Act"},
             head=0, deprel="root", deps=None, misc=None)

# „přijde" — dokonavý prézens: tvar Pres, čas budoucí.
PRIJDE = Token(id=3, form="přijde", lemma="přijít", upos="VERB",
               xpos="VB-S---3P-AAP--",
               feats={"Aspect": "Perf", "Mood": "Ind", "Number": "Sing",
                      "Person": "3", "Polarity": "Pos", "Tense": "Pres",
                      "VerbForm": "Fin", "Voice": "Act"},
               head=0, deprel="root", deps=None, misc=None)

# „nikdy" — záporné zájmenné příslovce: kotva času se záporným znaménkem.
NIKDY = Token(id=4, form="nikdy", lemma="nikdy", upos="ADV",
              xpos="Db-------------", feats={"PronType": "Neg"},
              head=2, deprel="advmod", deps=None, misc=None)

# „nepřítel" — jmenná negace: feats Polarity nemají, poziční tag ano (N).
NEPRITEL = Token(id=5, form="nepřítel", lemma="nepřítel", upos="NOUN",
                 xpos="NNMS1-----N----",
                 feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                        "Number": "Sing"},
                 head=0, deprel="root", deps=None, misc=None)


class TestKotvyAVazby(unittest.TestCase):
    """Sémantická vrstva: kotvy, vazby v registru, SUBPOS, jmenná negace."""

    def test_byli_kotvi_cas_i_mnozstvi(self):
        acts = activations(expand_token(BYLI))
        self.assertEqual(acts["ANCHOR=time:past"], 0.7)
        self.assertEqual(acts["ANCHOR=quantity:plur"], 0.7)

    def test_dokonavy_prezens_kotvi_do_budoucnosti(self):
        acts = activations(expand_token(PRIJDE))
        self.assertIn("ANCHOR=time:fut", acts)
        self.assertNotIn("ANCHOR=time:pres", acts)

    def test_kde_kotvi_podle_strany_vety(self):
        self.assertIn("QANCHOR=space:loc",
                      activations(expand_token(KDE), question=True))
        self.assertIn("ANCHOR=space:loc",
                      activations(expand_token(KDE), question=False))

    def test_zaporne_deiktikum_kotvi_zaporne(self):
        acts = activations(expand_token(NIKDY))
        self.assertEqual(acts["ANCHOR=time"], -0.7)

    def test_subpos_z_pozicniho_tagu(self):
        self.assertIn("SUBPOS=NN", activations(expand_token(PES)))
        self.assertIn("SUBPOS=RR", activations(expand_token(DO)))
        self.assertIn("SUBPOS=C=", activations(expand_token(N125)))

    def test_jmenna_negace_z_pozicniho_tagu(self):
        acts = activations(expand_token(NEPRITEL))
        self.assertEqual(acts["Polarity=Neg"], 0.7)
        # kladný stav je výchozí, nesvítí
        self.assertNotIn("Polarity=Pos", activations(expand_token(PES)))

    def test_vazby_prezijou_save_load(self):
        reg = VerticalRegistry(anchors=False)
        reg.link("ANCHOR=time:past", "ANCHOR=time", 1.0)
        with tempfile.TemporaryDirectory() as d:
            cesta = Path(d) / "verticals.json"
            reg.save(cesta)
            nacteny = VerticalRegistry.load(cesta)
            self.assertEqual(nacteny.links(),
                             (("ANCHOR=time:past", "ANCHOR=time", 1.0),))

    def test_parovani_otazky_s_odpovedi_pres_vazby(self):
        # „Kdy?" (QANCHOR=time:when) se má potkat s „přijde" (time:fut)
        # v uzlu ANCHOR=time — a nemá se potkat s „tam" (space).
        reg = VerticalRegistry()          # kotevní vazby má od narození
        otazka = reg.vectorize({"QANCHOR=time:when": 0.7})
        odpoved = reg.vectorize({"ANCHOR=time:fut": 0.7})
        jinam = reg.vectorize({"ANCHOR=space": 0.7})
        skore_ano = float(np.dot(reg.spread(otazka), reg.spread(odpoved)))
        skore_ne = float(np.dot(reg.spread(otazka), reg.spread(jinam)))
        self.assertGreater(skore_ano, 0.0)
        self.assertEqual(skore_ne, 0.0)


class TestActivationsTrida(unittest.TestCase):
    """Getter/setter vah a dvě reprezentace poskytnuté jako pole."""

    def test_metadata_nenesou_slovo_complete_ano(self):
        acts = Activations.from_row(expand_token(PETR))
        self.assertNotIn("WORD=PROPN:Petr", acts.weights())
        self.assertIn("WORD=PROPN:Petr", acts.weights(Representation.COMPLETE))
        # z COMPLETE jde METADATA odvodit — je to nadmnožina
        meta = acts.weights()
        comp = acts.weights(Representation.COMPLETE)
        self.assertEqual({k: v for k, v in comp.items()
                          if not k.startswith("WORD=")}, meta)

    def test_getter_a_setter_vahy(self):
        acts = Activations.from_row(expand_token(PETR))
        self.assertEqual(acts.get("UPOS=PROPN"), 0.7)
        acts.set("UPOS=PROPN", -0.5)
        self.assertEqual(acts.get("UPOS=PROPN"), -0.5)
        acts.set("WORD=PROPN:Petr", 0.9)
        self.assertEqual(acts.get("WORD=PROPN:Petr"), 0.9)
        with self.assertRaises(ValueError):
            acts.set("UPOS=PROPN", 1.5)          # mimo rozsah
        with self.assertRaises(KeyError):
            acts.set("UPOS=VERB", 0.7)           # neexistující vertikála
        with self.assertRaises(KeyError):
            acts.get("Case=Loc")

    def test_poskytnuti_jako_pole_v_obou_reprezentacich(self):
        acts = Activations.from_row(expand_token(PETR))
        reg = VerticalRegistry(anchors=False)
        meta_pole = acts.as_array(reg)
        comp_pole = acts.as_array(reg, Representation.COMPLETE)
        # complete má o slovní vertikálu víc a rekonstruuje se z něj slovo
        self.assertEqual(len(comp_pole), len(meta_pole) + 1)
        self.assertEqual(comp_pole.dtype, np.float32)
        zpet = reg.unvectorize(comp_pole)
        self.assertEqual(zpet["WORD=PROPN:Petr"], 0.7)
        self.assertNotIn("WORD=PROPN:Petr", reg.unvectorize(meta_pole))

    def test_zmena_vahy_se_propise_do_pole(self):
        acts = Activations.from_row(expand_token(PETR))
        reg = VerticalRegistry(anchors=False)
        acts.set("Case=Nom", -0.7)
        zpet = reg.unvectorize(acts.as_array(reg))
        self.assertEqual(zpet["Case=Nom"], -0.7)


class TestTrvalost(unittest.TestCase):

    def test_save_load_zachova_indexy_a_rust_pokracuje(self):
        reg = VerticalRegistry(anchors=False)
        reg.vectorize(activations(expand_token(SLA)))
        klice_pred = reg.keys()
        with tempfile.TemporaryDirectory() as d:
            cesta = Path(d) / "verticals.json"
            reg.save(cesta)
            nacteny = VerticalRegistry.load(cesta)
            self.assertEqual(nacteny.keys(), klice_pred)
            for i, klic in enumerate(klice_pred):
                self.assertEqual(nacteny.key(i), klic)
            # růst pokračuje na konci, staré indexy se nehnuly
            novy = nacteny.add("LEM=do")
            self.assertEqual(novy, len(klice_pred))

    def test_cizi_verze_formatu_se_odmitne(self):
        with tempfile.TemporaryDirectory() as d:
            cesta = Path(d) / "verticals.json"
            cesta.write_text('{"format_version": 99, "keys": []}',
                             encoding="utf-8")
            with self.assertRaises(ValueError):
                VerticalRegistry.load(cesta)


if __name__ == "__main__":
    unittest.main()
