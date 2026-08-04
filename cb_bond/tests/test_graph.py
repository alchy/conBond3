"""Testy KnowledgeGraph — paměť faktů nad rozebranými větami.

Vzorová věta o křtu je z zadání: 8 uzlů, 7 hran, a rozdíl Jordán ×
Galilej, který pytel aktivací nevidí. Čísla v testech jsou z výpočtu
v zadání, ne z běhu kódu.
"""

import unittest

from cb_bond import KnowledgeGraph
from cb_bond.tests.vzorky import (GRAVITACE, KRESTA, NECO_NOVEHO,
                                 TAM_BYDLI)


class TestStavba(unittest.TestCase):

    def test_uzly_jsou_obsahova_slova_bez_gramatiky(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)

        self.assertEqual(set(graf.nodes()), {
            "NOUN:den", "VERB:přijít", "PROPN:Ježíš", "PROPN:Nazareto",
            "PROPN:Galilej", "PROPN:Jordán", "ADJ:pokřtěný", "PROPN:Jan"})

    def test_hrany_vedou_od_zavisleho_k_ridicimu(self):
        graf = KnowledgeGraph()
        pocet = graf.add_sentence(KRESTA)

        self.assertEqual(pocet, 7)
        self.assertEqual(
            {(src, dst, deprel) for src, dst, deprel, _, _ in graf.edges()},
            {("PROPN:Ježíš", "VERB:přijít", "nsubj"),
             ("NOUN:den", "VERB:přijít", "obl"),
             ("PROPN:Nazareto", "VERB:přijít", "obl"),
             ("PROPN:Galilej", "VERB:přijít", "obl"),
             ("ADJ:pokřtěný", "VERB:přijít", "conj"),
             ("PROPN:Jordán", "ADJ:pokřtěný", "obl"),
             ("PROPN:Jan", "ADJ:pokřtěný", "obl:arg")})

    def test_hrana_vznika_jen_mezi_primymi_sousedy(self):
        # „nový" visí na „něco" (PRON), které uzel není — hrana na
        # „vidět" se NEDOVOZUJE. Přeskakování gramatiky by graf rozešlo
        # se zmraženou přejímkou (16 074 hran na 2 912 větách).
        graf = KnowledgeGraph()
        pocet = graf.add_sentence(NECO_NOVEHO)

        self.assertEqual(pocet, 0)
        self.assertEqual(graf.edges(), ())
        self.assertIn("ADJ:nový", graf.nodes())

    def test_kopula_hranu_neprerusi(self):
        # „Gravitace je síla": kopula visí na *síle*, mezi uzly nestojí —
        # definiční vazba proto vznikne přímo (vzorek kroku 7)
        graf = KnowledgeGraph()
        graf.add_sentence(GRAVITACE)

        self.assertIn(("NOUN:gravitace", "NOUN:síla", "nsubj"),
                      {(s, d, r) for s, d, r, _, _ in graf.edges()})

    def test_zajmenne_prislovce_je_uzel(self):
        # *tam* nese fakt (kde se bydlí), ne gramatiku — bez něj se graf
        # rozejde se zmraženou přejímkou
        graf = KnowledgeGraph()
        graf.add_sentence(TAM_BYDLI)

        self.assertIn("ADV:tam", graf.nodes())
        self.assertIn(("ADV:tam", "VERB:bydlet", "advmod"),
                      {(s, d, r) for s, d, r, _, _ in graf.edges()})

    def test_nodestat_pocita_vyskyty_hrany_a_ruzne_sousedy(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)

        stat = graf.node_stat("VERB:přijít")
        self.assertEqual(stat.occurrences, 1)
        self.assertEqual(stat.edges, 5)
        self.assertEqual(stat.distinct, 5)
        self.assertEqual(stat.ratio, 1.0)
        self.assertEqual(stat.neighbours["PROPN:Ježíš"], 1)

    def test_opakovana_veta_scita_vyskyty_i_hrany(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)
        graf.add_sentence(KRESTA)

        stat = graf.node_stat("VERB:přijít")
        self.assertEqual(stat.occurrences, 2)
        self.assertEqual(stat.edges, 10)      # hranové instance s opakováním
        self.assertEqual(stat.distinct, 5)    # různých sousedů pořád pět
        self.assertEqual(stat.ratio, 0.5)

    def test_statistika_vynecha_izolovany_uzel(self):
        # jednoslovná věta: uzel vznikne, hranu nemá → do statistiky nejde
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)
        pocet_pred = len(graf.statistics())
        graf.add_sentence(_jedno_slovo())

        self.assertIn("NOUN:pes", graf.nodes())
        self.assertEqual(len(graf.statistics()), pocet_pred)

    def test_zdroj_hrany_se_pamatuje(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA, source="dialog")

        self.assertEqual({z for *_, z in graf.edges()}, {"dialog"})


class TestSelectVerticals(unittest.TestCase):

    def test_skore_je_ruznych_na_druhou_deleno_hranami(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)
        graf.add_sentence(KRESTA)

        # přijít: 5 různých / 10 hran → 25/10 = 2,5
        # pokřtěný: 3 různí / 6 hran → 9/6 = 1,5
        skore = dict(graf.select_verticals(limit=8, with_scores=True))
        self.assertAlmostEqual(skore["VERB:přijít"], 2.5)
        self.assertAlmostEqual(skore["ADJ:pokřtěný"], 1.5)

    def test_limit_rezne_nejslabsi_a_poradi_je_sestupne(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)

        vybrane = graf.select_verticals(limit=2)
        self.assertEqual(len(vybrane), 2)
        self.assertEqual(vybrane[0], "VERB:přijít")   # nejvíc různých sousedů

    def test_uzitek_otazkam_je_vazeny_clen_ne_filtr(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)

        bez = graf.select_verticals(limit=8, with_scores=True)
        s_uzitkem = graf.select_verticals(
            limit=8, usage={"PROPN:Jordán": 4}, w_usage=1.0,
            with_scores=True)

        zaklad = dict(bez)["PROPN:Jordán"]
        self.assertAlmostEqual(dict(s_uzitkem)["PROPN:Jordán"],
                               zaklad * (1 + 1.0 * 4))
        # uzel bez dokladů si nepohorší — je to násobek, ne přerovnání
        self.assertAlmostEqual(dict(s_uzitkem)["VERB:přijít"],
                               dict(bez)["VERB:přijít"])


class TestIlluminate(unittest.TestCase):

    def test_zare_po_hranach_rozliseni_jordan_nad_galileji(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)

        jas = graf.illuminate({0: 1.0}, {"pokřtěný", "Ježíš"}, boost=2.0)

        # rozsvícení 1,0 + záře souseda ×(podíl hrany na jeho hranách)
        self.assertAlmostEqual(jas["PROPN:Jordán"], 1.0 + 2.0 / 3, places=4)
        self.assertAlmostEqual(jas["PROPN:Galilej"], 1.0 + 1.0 / 5, places=4)
        self.assertGreater(jas["PROPN:Jordán"], jas["PROPN:Galilej"])

    def test_lemata_otazky_zesili_svuj_uzel(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)

        jas = graf.illuminate({0: 1.0}, {"pokřtěný", "Ježíš"}, boost=2.0)

        # pokřtěný: zesílení 2,0 + záře tří sousedů — přijít dá pětinu
        # svých hran (0,2), Jordán a Jan celou svou jedinou (1,0 + 1,0)
        self.assertAlmostEqual(jas["ADJ:pokřtěný"],
                               2.0 + 1.0 / 5 + 1.0 + 1.0, places=4)
        # Ježíš: zesílení 2,0 + pětina záře jediného souseda přijít
        self.assertAlmostEqual(jas["PROPN:Ježíš"], 2.0 + 1.0 / 5, places=4)

    def test_vaha_kandidata_skaluje_rozsviceni(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)

        jas = graf.illuminate({0: 0.5}, set(), boost=2.0)

        self.assertAlmostEqual(jas["PROPN:Nazareto"], 0.5 + 0.5 / 5, places=4)


class TestEmitor(unittest.TestCase):

    def test_kazda_mutace_posle_deltu(self):
        delty = []
        graf = KnowledgeGraph(emit=delty.append)
        graf.add_sentence(KRESTA)

        uzly = [d for d in delty if d["op"] == "node"]
        hrany = [d for d in delty if d["op"] == "edge"]
        self.assertEqual(len(uzly), 8)
        self.assertEqual(len(hrany), 7)
        self.assertIn({"op": "node", "id": "PROPN:Jordán"}, delty)
        self.assertIn({"op": "edge", "src": "PROPN:Jordán",
                       "dst": "ADJ:pokřtěný", "deprel": "obl",
                       "source": "text"}, delty)

    def test_smycka_se_pocita_ale_nekresli(self):
        # Táž vertikála dvakrát ve větě (pes → psa) dá závislost na sebe
        # sama. Do součtu hran patří (přejímka 16 074 ji zahrnuje), ale
        # do sousedství ne — a nekreslí se, viewBase smyčky odmítá.
        delty = []
        graf = KnowledgeGraph(emit=delty.append)
        pocet = graf.add_sentence(_smycka())

        self.assertEqual(pocet, 1)
        self.assertEqual(len(graf.edges()), 1)
        self.assertEqual(graf.node_stat("NOUN:pes").neighbours, {})
        self.assertEqual(graf.statistics(), {})
        self.assertEqual([d for d in delty if d["op"] == "edge"], [])


def _jedno_slovo():
    from cb_field.tests.test_registry import PES
    from cb_bond.tests.vzorky import Veta
    from cb_udpipe import Token
    root = Token(id=1, form="Pes", lemma="pes", upos="NOUN",
                 xpos=PES.xpos, feats=PES.feats, head=0, deprel="root",
                 deps=None, misc=None)
    return Veta("Pes.", (root,))


def _smycka():
    """Věta, kde by dvě různá slova dala týž klíč uzlu — hrana na sebe."""
    from cb_bond.tests.vzorky import Veta
    from cb_udpipe import Token
    prvni = Token(id=1, form="pes", lemma="pes", upos="NOUN",
                  xpos="NNMS1-----A----", feats={"Case": "Nom"},
                  head=2, deprel="nmod", deps=None, misc=None)
    druhy = Token(id=2, form="psa", lemma="pes", upos="NOUN",
                  xpos="NNMS4-----A----", feats={"Case": "Acc"},
                  head=0, deprel="root", deps=None, misc=None)
    return Veta("pes psa", (prvni, druhy))


if __name__ == "__main__":
    unittest.main()
