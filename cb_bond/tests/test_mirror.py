"""Testy zrcadla grafu — delty do viewBase2.

Okno se předává parametrem (§ 3), takže testy nepotřebují běžící
server ani nainstalovaný frontend: atrapa jen zapisuje, co jí přišlo.
"""

import unittest

from cb_bond import KnowledgeGraph
from cb_bond.mirror import GraphMirror
from cb_bond.tests.vzorky import KRESTA


class _Okno:
    """Atrapa GraphWindow — pamatuje si, co se do ní nakreslilo."""

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.updates = []
        self.types = []

    def define_type(self, name, **style):
        self.types.append((name, style))

    def add_node(self, node_id, **meta):
        if meta.get("type") not in dict(self.types):
            raise ValueError(f"neznámý typ uzlu {meta.get('type')!r}")
        self.nodes.append((node_id, meta))

    def add_edge(self, source, target, **meta):
        # viewBase klíčuje hrany NEORIENTOVANĚ (_edge_key řadí dvojici)
        if any({h[0], h[1]} == {source, target} for h in self.edges):
            raise ValueError(f"Hrana {source}–{target} už existuje")
        self.edges.append((source, target, meta))

    def update_node(self, node_id, **meta):
        self.updates.append((node_id, meta))


class TestZrcadlo(unittest.TestCase):

    def test_graf_kresli_prubezne_pri_kazde_mutaci(self):
        okno = _Okno()
        graf = KnowledgeGraph(emit=GraphMirror(okno).emit)

        graf.add_sentence(KRESTA)

        self.assertEqual(len(okno.nodes), 8)
        self.assertEqual(len(okno.edges), 7)

    def test_uzel_nese_citelny_popisek_a_slovni_druh(self):
        okno = _Okno()
        graf = KnowledgeGraph(emit=GraphMirror(okno).emit)

        graf.add_sentence(KRESTA)

        podle_id = dict(okno.nodes)
        self.assertIn("PROPN:Jordán", podle_id)
        self.assertEqual(podle_id["PROPN:Jordán"]["label"], "Jordán")
        self.assertEqual(podle_id["PROPN:Jordán"]["type"], "PROPN")

    def test_hrana_nese_deprel_i_zdroj(self):
        # provenience jde do okna jako `origin`: viewBase má `source`
        # obsazený zdrojovým UZLEM hrany (kolize jmen, reálná TypeError)
        okno = _Okno()
        graf = KnowledgeGraph(emit=GraphMirror(okno).emit)

        graf.add_sentence(KRESTA, source="dialog")

        hrana = next(h for h in okno.edges
                     if h[:2] == ("PROPN:Jordán", "ADJ:pokřtěný"))
        self.assertEqual(hrana[2]["deprel"], "obl")
        self.assertEqual(hrana[2]["origin"], "dialog")

    def test_tataz_hrana_se_kresli_jen_jednou(self):
        # graf počítá hranové instance S OPAKOVÁNÍM (zmražených 16 074),
        # obrázek má každou dvojici jednou — viewBase duplicitu odmítá
        okno = _Okno()
        graf = KnowledgeGraph(emit=GraphMirror(okno).emit)

        graf.add_sentence(KRESTA)
        graf.add_sentence(KRESTA)

        self.assertEqual(len(graf.edges()), 14)   # data: s opakováním
        self.assertEqual(len(okno.edges), 7)      # obrázek: jednou

    def test_opacny_smer_je_TATAZ_hrana(self):
        # viewBase klíčuje hrany neorientovaně: A→B a B→A je jedna hrana.
        # Graf orientaci drží (nese ji deprel), obrázek ji nekreslí dvakrát.
        okno = _Okno()
        zrcadlo = GraphMirror(okno)

        zrcadlo.emit({"op": "edge", "src": "A", "dst": "B",
                      "deprel": "nsubj", "source": "text"})
        zrcadlo.emit({"op": "edge", "src": "B", "dst": "A",
                      "deprel": "obl", "source": "text"})

        self.assertEqual(len(okno.edges), 1)

    def test_typ_uzlu_se_definuje_pred_prvnim_uzlem(self):
        # viewBase odmítne uzel s nedefinovaným typem — zrcadlo si typ
        # zavede samo při prvním setkání, aby na to nikdo nemusel myslet
        okno = _Okno()
        graf = KnowledgeGraph(emit=GraphMirror(okno).emit)

        graf.add_sentence(KRESTA)

        self.assertEqual({jmeno for jmeno, _ in okno.types},
                         {"NOUN", "PROPN", "VERB", "ADJ"})
        self.assertEqual(len(okno.types), 4)      # každý typ jednou

    def test_jas_se_kresli_jako_zmena_uzlu(self):
        okno = _Okno()
        zrcadlo = GraphMirror(okno)

        zrcadlo.emit({"op": "style", "id": "PROPN:Jordán", "glow": 1.67})

        self.assertEqual(okno.updates, [("PROPN:Jordán", {"glow": 1.67})])

    def test_neznama_operace_je_hlasita_chyba(self):
        # tichý průchod by znamenal, že se něco nekreslí a nikdo neví proč
        zrcadlo = GraphMirror(_Okno())

        with self.assertRaises(ValueError):
            zrcadlo.emit({"op": "cosi", "id": "x"})

    def test_glow_na_uzel_pribyly_z_dialogu_ho_nejdriv_zalozi(self):
        """viewBase glow na neznámý uzel odmítá — obrázek má graf DOHNAT,

        ne na něm spadnout. Věta z dialogu přidá do grafu uzel, který
        okno ještě nezná; illuminate ho musí založit, ne shodit službu.
        """
        class _StriktniOkno(_Okno):
            def update_node(self, node_id, **meta):
                if node_id not in {n[0] for n in self.nodes}:
                    raise ValueError(f"Uzel '{node_id}' neexistuje")
                super().update_node(node_id, **meta)

        okno = _StriktniOkno()
        zrcadlo = GraphMirror(okno)

        zrcadlo.emit({"op": "style", "id": "NOUN:programátor", "glow": 1.0})

        self.assertIn("NOUN:programátor", {n[0] for n in okno.nodes})
        self.assertEqual(len(okno.updates), 1)

    def test_zrcadleni_grafu_dohoni_co_uz_v_nem_je(self):
        # graf postavený bez zrcadla se dá zrcadlit dodatečně
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)
        okno = _Okno()

        GraphMirror(okno).mirror(graf)

        self.assertEqual(len(okno.nodes), 8)
        self.assertEqual(len(okno.edges), 7)

    def test_metadata_uzlu_rikaji_sousedy_a_stupen(self):
        # co je na obrázku vidět, má jít i přečíst: kliknutím na uzel
        # se člověk dozví, s kým sousedí a jakým vztahem
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)
        okno = _Okno()
        zrcadlo = GraphMirror(okno)
        zrcadlo.mirror(graf)

        zrcadlo.refresh(graf)

        meta = dict(okno.updates)
        self.assertEqual(meta["PROPN:Jordán"]["sousede"], "ADJ:pokřtěný (obl)")
        self.assertEqual(meta["PROPN:Jordán"]["stupen"], 1)
        self.assertEqual(meta["VERB:přijít"]["stupen"], 5)

    def test_vysviceni_se_promitne_jako_jas(self):
        graf = KnowledgeGraph()
        graf.add_sentence(KRESTA)
        okno = _Okno()
        zrcadlo = GraphMirror(okno)
        zrcadlo.mirror(graf)

        zrcadlo.illuminate(graf, {0: 1.0}, {"pokřtěný", "Ježíš"})

        jasy = dict(okno.updates)
        self.assertGreater(jasy["PROPN:Jordán"]["glow"],
                           jasy["PROPN:Galilej"]["glow"])


if __name__ == "__main__":
    unittest.main()
