"""Testy promočního cyklu — krok 3 handoveru.

Nejnebezpečnější místo návrhu: s limitem custom vertikál se sloupce
uvolňují a přeobsazují, takže stará matice by ukazovala na sloupec,
který mezitím znamená něco jiného — tichá záměna významu, ne pád.
Testy proto míří přesně tam: stará cache se musí odmítnout použít,
uvolněná vertikála odchází i s hranami a cyklus, který zhorší měření,
vrátí registr bit po bitu.

Zmražená data se sdílejí s test_graph (věta o křtu).
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from cb_field.field import SentenceField
from cb_field.corpus import Corpus
from cb_field.graph import FactGraph
from cb_field.matching import _fact_bags
from cb_field.promotion import promotion_cycle
from cb_field.registry import CUSTOM_PREFIX, VerticalRegistry
from cb_field.tests.test_graph import KREST, _Sentence


def _registry_state(registry):
    """Úplný stav registru pro porovnání bit po bitu."""
    return (tuple(registry._keys), dict(registry._index),
            frozenset(registry.links()), registry.axis_version,
            registry.link_version)


class TestCustomAxes(unittest.TestCase):

    def test_zapis_prideli_sloupce_a_zvedne_verzi(self):
        reg = VerticalRegistry(anchors=False)
        before = len(reg)
        changes = reg.set_custom_axes(("CUSTOM=NOUN:rok",
                                       "CUSTOM=VERB:mít"))
        self.assertEqual(reg.axis_version, 1)
        self.assertEqual(len(reg), before + 2)
        self.assertEqual(changes["pridano"], 2)
        self.assertEqual(reg.key(reg.index("CUSTOM=NOUN:rok")),
                         "CUSTOM=NOUN:rok")
        # týž cílový stav podruhé: žádná změna obsazení, verze stojí
        changes = reg.set_custom_axes(("CUSTOM=NOUN:rok",
                                       "CUSTOM=VERB:mít"))
        self.assertEqual(reg.axis_version, 1)
        self.assertEqual((changes["pridano"], changes["odebrano"]), (0, 0))

    def test_cizi_prefix_je_hlasita_chyba(self):
        reg = VerticalRegistry(anchors=False)
        with self.assertRaises(ValueError):
            reg.set_custom_axes(("WORD=NOUN:rok",))

    def test_uvolneny_sloupec_se_preobsadi(self):
        reg = VerticalRegistry(anchors=False)
        reg.set_custom_axes(("CUSTOM=a", "CUSTOM=b"))
        column = reg.index("CUSTOM=b")
        reg.set_custom_axes(("CUSTOM=a", "CUSTOM=c"))
        self.assertEqual(reg.axis_version, 2)
        self.assertNotIn("CUSTOM=b", reg)
        self.assertEqual(reg.index("CUSTOM=c"), column)

    def test_uvolneni_bez_nahrady_je_hlasita_dira(self):
        reg = VerticalRegistry(anchors=False)
        reg.set_custom_axes(("CUSTOM=a", "CUSTOM=b"))
        column = reg.index("CUSTOM=b")
        width = len(reg)
        reg.set_custom_axes(("CUSTOM=a",))
        self.assertEqual(len(reg), width)        # osa se nezkracuje
        with self.assertRaises(ValueError):
            reg.key(column)                      # čtení díry je chyba
        # starý vektor s aktivací v uvolněném sloupci se odmítne
        stale = np.zeros(width, dtype=np.float32)
        stale[column] = 0.5
        with self.assertRaises(ValueError):
            reg.unvectorize(stale)
        # nulová aktivace v díře nevadí — nula nic netvrdí
        self.assertEqual(reg.unvectorize(np.zeros(width)), {})

    def test_uvolnena_vertikala_odchazi_i_s_hranami(self):
        reg = VerticalRegistry(anchors=False)
        reg.set_custom_axes(("CUSTOM=a",))
        reg.link("WORD=x", "CUSTOM=a", 0.5, source="hebb")
        reg.link("CUSTOM=a", "WORD=y", 0.3, source="hebb")
        reg.set_custom_axes(())
        self.assertIsNone(reg.get_link("WORD=x", "CUSTOM=a"))
        self.assertIsNone(reg.get_link("CUSTOM=a", "WORD=y"))
        self.assertFalse(any("CUSTOM=a" in (s, d)
                             for s, d, _w, _src in reg.links()))

    def test_save_load_nese_verzi_osy_i_diry(self):
        reg = VerticalRegistry(anchors=False)
        reg.add("WORD=x")
        reg.set_custom_axes(("CUSTOM=a", "CUSTOM=b"))
        reg.set_custom_axes(("CUSTOM=a",))       # díra po b
        column = len(reg) - 1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registr.json"
            reg.save(path)
            loaded = VerticalRegistry.load(path)
            self.assertEqual(loaded.axis_version, reg.axis_version)
            self.assertEqual(loaded.keys(), reg.keys())
            with self.assertRaises(ValueError):
                loaded.key(column)               # díra přežila round-trip
            with self.assertRaises(ValueError):
                VerticalRegistry.load(path, expected_axis_version=99)


class TestInvalidaceCache(unittest.TestCase):

    def test_stara_matice_vety_se_odmitne_pouzit(self):
        reg = VerticalRegistry()
        field = SentenceField(KREST, r=1, registry=reg)
        old = field.matrix()
        self.assertIs(field.matrix(), old)       # cache drží při téže ose
        reg.set_custom_axes(("CUSTOM=VERB:přijít",))
        rebuilt = field.matrix()
        self.assertIsNot(rebuilt, old)
        self.assertEqual(rebuilt.shape[1], len(reg))
        # obsah starých sloupců se přestavbou nemění (žádný nebyl uvolněn)
        np.testing.assert_array_equal(rebuilt[:, :old.shape[1]], old)

    def test_pytle_faktu_se_prestavi(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(KREST))
        bags = _fact_bags(corpus)
        self.assertIs(_fact_bags(corpus), bags)  # cache drží
        corpus.registry.set_custom_axes(("CUSTOM=VERB:přijít",))
        self.assertIsNot(_fact_bags(corpus), bags)


class TestPromocniCyklus(unittest.TestCase):

    def _setup(self):
        corpus = Corpus(r=1)
        corpus.add_sentence(_Sentence(KREST))
        graph = FactGraph()
        graph.add_sentence(_Sentence(KREST))
        return corpus, graph

    def test_zhorseni_vrati_registr_bit_po_bitu(self):
        corpus, graph = self._setup()
        state = _registry_state(corpus.registry)
        measures = iter([{"presnost": 0.5, "mlceni": 1.0},
                         {"presnost": 0.4, "mlceni": 1.0}])

        def retrain(c):
            c.registry.link("WORD=a", "WORD=b", 0.5, source="etalon")

        outcome = promotion_cycle(corpus, graph,
                                  measure=lambda c: next(measures),
                                  retrain=retrain)
        self.assertFalse(outcome["prijato"])
        self.assertEqual(_registry_state(corpus.registry), state)

    def test_zlepseni_se_prijme(self):
        corpus, graph = self._setup()
        measures = iter([{"presnost": 0.5}, {"presnost": 0.6}])
        outcome = promotion_cycle(corpus, graph,
                                  measure=lambda c: next(measures),
                                  retrain=lambda c: None)
        self.assertTrue(outcome["prijato"])
        self.assertIn(CUSTOM_PREFIX + "VERB:přijít", corpus.registry)
        self.assertEqual(corpus.registry.axis_version, 1)

    def test_zhorseni_jedine_metriky_staci_k_odvolani(self):
        # protiváha (workflow § B5): přesnost nahoru, mlčení dolů = zpět
        corpus, graph = self._setup()
        state = _registry_state(corpus.registry)
        measures = iter([{"presnost": 0.5, "mlceni": 1.0},
                         {"presnost": 0.9, "mlceni": 0.5}])
        outcome = promotion_cycle(corpus, graph,
                                  measure=lambda c: next(measures),
                                  retrain=lambda c: None)
        self.assertFalse(outcome["prijato"])
        self.assertEqual(_registry_state(corpus.registry), state)

    def test_stejne_mereni_se_prijme(self):
        corpus, graph = self._setup()
        measures = iter([{"presnost": 0.5}, {"presnost": 0.5}])
        outcome = promotion_cycle(corpus, graph,
                                  measure=lambda c: next(measures),
                                  retrain=lambda c: None)
        self.assertTrue(outcome["prijato"])


if __name__ == "__main__":
    unittest.main()
