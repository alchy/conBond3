"""Testy grafu faktů — krok 1 handoveru (docs/handover-implementace.md).

Zmražená data: tokeny věty „V těch dnech přišel Ježíš z Nazareta
v Galileji a byl v Jordánu pokřtěn od Jana." jsou zapsané jako literály
podle skutečného výstupu UDPipe z 2026-08-04 — test nesmí potřebovat
běžící službu (§ 13). Graf čte jen lemma/upos/head/deprel, feats tu
proto nejsou vypsané.
"""

import unittest

from cb_field.graph import FactGraph, light_up, promote_verticals
from cb_udpipe import Token


def _t(id, form, lemma, upos, head, deprel):
    return Token(id=id, form=form, lemma=lemma, upos=upos, xpos="",
                 feats=None, head=head, deprel=deprel, deps=None,
                 misc=None)


#: Věta z korpusu (bible_markus), na které stojí příklad v handoveru:
#: 8 obsahových uzlů, 7 hran, funkční slova uzlem nejsou.
KREST = (
    _t(1, "V", "v", "ADP", 3, "case"),
    _t(2, "těch", "ten", "DET", 3, "det"),
    _t(3, "dnech", "den", "NOUN", 4, "obl"),
    _t(4, "přišel", "přijít", "VERB", 0, "root"),
    _t(5, "Ježíš", "Ježíš", "PROPN", 4, "nsubj"),
    _t(6, "z", "z", "ADP", 7, "case"),
    _t(7, "Nazareta", "Nazareto", "PROPN", 4, "obl"),
    _t(8, "v", "v", "ADP", 9, "case"),
    _t(9, "Galileji", "Galilej", "PROPN", 4, "obl"),
    _t(10, "a", "a", "CCONJ", 14, "cc"),
    _t(11, "byl", "být", "AUX", 14, "aux:pass"),
    _t(12, "v", "v", "ADP", 13, "case"),
    _t(13, "Jordánu", "Jordán", "PROPN", 14, "obl"),
    _t(14, "pokřtěn", "pokřtěný", "ADJ", 4, "conj"),
    _t(15, "od", "od", "ADP", 16, "case"),
    _t(16, "Jana", "Jan", "PROPN", 14, "obl:arg"),
    _t(17, ".", ".", "PUNCT", 4, "punct"),
)


class _Sentence:
    """Nejmenší nosič věty: graf čte jen .tokens (SentenceField
    i ParsedSentence ho mají)."""

    def __init__(self, tokens):
        self.tokens = tokens


class TestFactGraph(unittest.TestCase):

    def test_uzly_jsou_jen_obsahova_slova(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        self.assertEqual(set(graph.nodes()), {
            "NOUN:den", "VERB:přijít", "PROPN:Ježíš", "PROPN:Nazareto",
            "PROPN:Galilej", "PROPN:Jordán", "ADJ:pokřtěný", "PROPN:Jan"})

    def test_hrany_vedou_od_zavisleho_k_hlave_s_deprel(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        edges = {(s, d, rel) for s, d, rel, _w, _src in graph.edges()}
        self.assertEqual(edges, {
            ("PROPN:Ježíš", "VERB:přijít", "nsubj"),
            ("NOUN:den", "VERB:přijít", "obl"),
            ("PROPN:Nazareto", "VERB:přijít", "obl"),
            ("PROPN:Galilej", "VERB:přijít", "obl"),
            ("ADJ:pokřtěný", "VERB:přijít", "conj"),
            ("PROPN:Jordán", "ADJ:pokřtěný", "obl"),
            ("PROPN:Jan", "ADJ:pokřtěný", "obl:arg")})

    def test_statistika_uzlu_zname_sceny(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        prijit = graph.node_stat("VERB:přijít")
        self.assertEqual(prijit.occurrences, 1)
        self.assertEqual(prijit.edges, 5)
        self.assertEqual(prijit.distinct, 5)
        self.assertEqual(prijit.ratio, 1.0)
        pokrteny = graph.node_stat("ADJ:pokřtěný")
        self.assertEqual(pokrteny.edges, 3)      # přijít, Jordán, Jan
        self.assertEqual(pokrteny.distinct, 3)

    def test_opakovana_veta_scita_hrany_ale_ne_sousedy(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        graph.add_sentence(_Sentence(KREST))
        prijit = graph.node_stat("VERB:přijít")
        self.assertEqual(prijit.occurrences, 2)
        self.assertEqual(prijit.edges, 10)       # instance se opakují
        self.assertEqual(prijit.distinct, 5)     # sousedé jsou titíž
        self.assertEqual(prijit.ratio, 0.5)      # diskriminátor obecnosti

    def test_zdroj_dialog_jde_kdykoli_odlisit(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        graph.add_sentence(_Sentence(KREST), source="dialog")
        sources = {src for _s, _d, _rel, _w, src in graph.edges()}
        self.assertEqual(sources, {"text", "dialog"})
        dialog = [e for e in graph.edges() if e[4] == "dialog"]
        self.assertEqual(len(dialog), 7)         # hrany věty ještě jednou

    def test_souhrnna_statistika(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        s = graph.stats()
        self.assertEqual(s["uzlu"], 8)
        self.assertEqual(s["hran"], 7)
        self.assertAlmostEqual(s["prumerny_stupen"], 2 * 7 / 8, places=6)

    def test_zajmeno_uzlem_neni(self):
        # PRON do referenčního měření (4. 8. 2026) nevstupoval: bez něj
        # sedí hrany na korpusu přesně (16 074), s ním ne (17 953).
        graph = FactGraph()
        graph.add_sentence(_Sentence((
            _t(1, "On", "on", "PRON", 2, "nsubj"),
            _t(2, "přišel", "přijít", "VERB", 0, "root"),
            _t(3, ".", ".", "PUNCT", 2, "punct"))))
        self.assertEqual(graph.nodes(), ("VERB:přijít",))
        self.assertEqual(graph.edges(), ())

    def test_izolovany_uzel_se_do_grafu_faktu_nepocita(self):
        # Fakt je vztah: obsahové slovo bez hrany zůstává evidované
        # (výskyty), ale graf faktů tvoří jen uzly s hranou.
        graph = FactGraph()
        graph.add_sentence(_Sentence((
            _t(1, "Prší", "pršet", "VERB", 0, "root"),
            _t(2, ".", ".", "PUNCT", 1, "punct"))))
        self.assertEqual(graph.node_stat("VERB:pršet").occurrences, 1)
        self.assertEqual(graph.stats()["uzlu"], 0)
        self.assertEqual(graph.stats()["hran"], 0)

    def test_veta_bez_obsahovych_slov_nic_nezmeni(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence((
            _t(1, "A", "a", "CCONJ", 0, "root"),
            _t(2, "?", "?", "PUNCT", 1, "punct"))))
        self.assertEqual(graph.nodes(), ())
        self.assertEqual(graph.stats()["uzlu"], 0)
        self.assertEqual(graph.stats()["prumerny_stupen"], 0.0)


class TestVysviceniGrafu(unittest.TestCase):
    """Krok H: kandidátní věty rozsvítí uzly, lemata otázky znásobí
    jas rozsvícených a záře teče po hranách — Jordán (visí na
    posíleném pokřtěný) zjasní nad Galilejí (visí na přijít)."""

    def test_jordan_zjasni_nad_galileji(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        lights = light_up(graph, [(_Sentence(KREST), 1.0)],
                          question_lemmas={"pokřtěný", "Ježíš"})
        self.assertGreater(lights["PROPN:Jordán"],
                           lights["PROPN:Galilej"])
        # posílené lemma otázky září víc než neposílený uzel
        self.assertGreater(lights["ADJ:pokřtěný"], lights["NOUN:den"])

    def test_nerozsvicene_uzly_zustavaji_tmave(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        graph.add_sentence(_Sentence((
            _t(1, "Prší", "pršet", "VERB", 2, "nsubj"),
            _t(2, "voda", "voda", "NOUN", 0, "root"))))
        lights = light_up(graph, [(_Sentence(KREST), 1.0)],
                          question_lemmas=set())
        self.assertNotIn("VERB:pršet", lights)


class TestEmitorDelt(unittest.TestCase):
    """Krok I: cokoli se děje v grafu, se VŽDY projeví ve vizualizaci
    — každá mutace i vysvícení jde přes emitor delt (viewBase2)."""

    def test_mutace_grafu_emituji_delty(self):
        events = []
        graph = FactGraph(emit=events.append)
        graph.add_sentence(_Sentence(KREST))
        kinds = {e["op"] for e in events}
        self.assertIn("node", kinds)
        self.assertIn("edge", kinds)
        nodes = {e["id"] for e in events if e["op"] == "node"}
        self.assertIn("PROPN:Jordán", nodes)

    def test_vysviceni_emituje_styl(self):
        events = []
        graph = FactGraph(emit=events.append)
        graph.add_sentence(_Sentence(KREST))
        events.clear()
        light_up(graph, [(_Sentence(KREST), 1.0)],
                 question_lemmas={"pokřtěný"})
        styles = [e for e in events if e["op"] == "style"]
        self.assertTrue(styles)
        self.assertTrue(all("glow" in e for e in styles))


class TestViewbaseAdapter(unittest.TestCase):

    def test_delty_se_prelozi_na_objektove_api(self):
        from cb_field.graphview import viewbase_emitter

        class _Window:
            calls = []
            def ensure_node(self, node_id, **kw):
                self.calls.append(("node", node_id))
            def ensure_edge(self, src, dst, **kw):
                self.calls.append(("edge", src, dst))
            def update_node(self, node_id, **kw):
                self.calls.append(("style", node_id, kw.get("glow")))

        window = _Window()
        graph = FactGraph(emit=viewbase_emitter(window))
        graph.add_sentence(_Sentence(KREST))
        light_up(graph, [(_Sentence(KREST), 1.0)],
                 question_lemmas={"pokřtěný"})
        kinds = {c[0] for c in window.calls}
        self.assertEqual(kinds, {"node", "edge", "style"})


class TestPromoteVerticals(unittest.TestCase):
    """Krok 2 handoveru: skóre = různých²/hran, limit, cílový stav."""

    def _graph(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        return graph

    def test_poradi_podle_ruznych_na_druhou_ku_hranam(self):
        # přijít 5²/5 = 5 > pokřtěný 3²/3 = 3 > ostatní 1²/1 = 1
        promoted = promote_verticals(self._graph(), limit=2)
        self.assertEqual(promoted, ("VERB:přijít", "ADJ:pokřtěný"))

    def test_opakovani_hran_skore_srazi(self):
        # dvojí táž věta: různých zůstává, hran se zdvojí → skóre
        # klesne na polovinu (odměna za rozmanitost, ne za frekvenci)
        graph = self._graph()
        graph.add_sentence(_Sentence(KREST))
        promoted = promote_verticals(graph, limit=2)
        self.assertEqual(promoted, ("VERB:přijít", "ADJ:pokřtěný"))

    def test_vraci_cely_cilovy_stav_a_je_deterministicka(self):
        graph = self._graph()
        first = promote_verticals(graph)
        self.assertEqual(first, promote_verticals(graph))
        self.assertEqual(len(first), 8)          # celé osazenstvo grafu
        self.assertEqual(promote_verticals(FactGraph()), ())

    def test_shodne_skore_rozhoduje_klic(self):
        # šest uzlů se skóre 1,0 → řadí se klíčem, ne pořadím vět
        promoted = promote_verticals(self._graph())
        self.assertEqual(promoted[2:], tuple(sorted(promoted[2:])))

    def test_izolovany_uzel_nekandiduje(self):
        graph = FactGraph()
        graph.add_sentence(_Sentence((
            _t(1, "Prší", "pršet", "VERB", 0, "root"),
            _t(2, ".", ".", "PUNCT", 1, "punct"))))
        self.assertEqual(promote_verticals(graph), ())


if __name__ == "__main__":
    unittest.main()
