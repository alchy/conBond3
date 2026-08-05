"""Testy oken viewBase2.

Okna jsou čtyři (rozhodnutí J.): graf · dialog · top 5 vět · použité
vertikály. Co se tady testuje, je **naše** část — co se do oken píše
a kdy se přepisují. Samotný frontend a `viewbase` se netestují: je to
cizí knihovna a test nesmí potřebovat běžící službu (§ 13).
"""

import unittest

from cb_bond.window import (
    AXES_ID,
    DIALOG_ID,
    SENTENCES_ID,
    BondWindows,
    format_answer,
    format_axes,
    format_sentence,
)

ODPOVED = {
    "question": "Kde byl pokřtěn Ježíš?",
    "answer": "říci",
    "outcome": "answer",
    "missing": [],
    "score": 2.366,
    "decomposition": {"meet": 1.23, "cover": 0.60, "topic": 0.54,
                      "given": -0.0},
    "sentences": [
        {"position": 12, "lemma": "říci", "score": 2.366,
         "text": "Ježíš jim řekl: „Kalich, který já piji…"},
        {"position": 8, "lemma": "přijít", "score": 1.904,
         "text": "V těch dnech přišel Ježíš z Nazareta…"},
    ],
    "axes": [{"axis": "WORD=AUX:být", "coverage": 1.0},
             {"axis": "WORD=ADJ:pokřtěný", "coverage": 0.604}],
}


class _Okno:
    """Atrapa okna viewBase: pamatuje si, co se kam zapsalo."""

    def __init__(self):
        self.zapsano = []
        self.otevrena = []
        self.jas = None

    def open_terminal(self, window, on_input=None):
        self.otevrena.append(window.window_id)

    def terminal_write(self, window_id, text):
        self.zapsano.append((window_id, text))

    def texty(self, window_id) -> str:
        return "\n".join(t for w, t in self.zapsano if w == window_id)


class _Sluzba:
    """Atrapa fasády — vrací hotovou odpověď."""

    def __init__(self, odpoved=ODPOVED):
        self.odpoved = odpoved
        self.dotazy = []
        self.graph = object()

    def ask(self, text, *, top=None):
        self.dotazy.append((text, top))
        return dict(self.odpoved, question=text)


class TestFormatovani(unittest.TestCase):
    """Konvence `[slovo] Věta` je dohodnutá — okna ji drží stejně."""

    def test_veta_ma_kandidatni_slovo_v_ZAVORCE_pred_textem(self):
        radek = format_sentence(ODPOVED["sentences"][0])

        self.assertTrue(radek.startswith("[říci]"))
        self.assertIn("Ježíš jim řekl", radek)

    def test_veta_nese_i_skore(self):
        # bez skóre nejde poznat odstup druhé volby od první
        self.assertIn("2.37", format_sentence(ODPOVED["sentences"][0]))

    def test_osy_uvadi_pokryti(self):
        radky = format_axes(ODPOVED["axes"])

        self.assertEqual(len(radky), 2)
        self.assertIn("WORD=AUX:být", radky[0])
        self.assertIn("1.000", radky[0])

    def test_odpoved_nese_ROZKLAD_skore(self):
        text = "\n".join(format_answer(ODPOVED))

        self.assertIn("říci", text)
        self.assertIn("meet", text)
        self.assertIn("+1.23", text)

    def test_mlceni_je_videt_jako_mlceni(self):
        ticho = dict(ODPOVED, answer=None, outcome="silent",
                     sentences=[], decomposition={})

        text = "\n".join(format_answer(ticho))

        self.assertIn("mlčí", text)


class TestPrepisOken(unittest.TestCase):

    def setUp(self):
        self.okno = _Okno()
        self.sluzba = _Sluzba()
        self.okna = BondWindows(self.sluzba, self.okno, mirror=None)

    def test_attach_otevre_TRI_terminaly_vedle_grafu(self):
        self.okna.attach()

        self.assertEqual(set(self.okno.otevrena),
                         {DIALOG_ID, SENTENCES_ID, AXES_ID})

    def test_dotaz_prepise_VSECHNA_tri_okna(self):
        self.okna.attach()

        self.okna.ask("Kde byl pokřtěn Ježíš?")

        self.assertIn("říci", self.okno.texty(DIALOG_ID))
        self.assertIn("[přijít]", self.okno.texty(SENTENCES_ID))
        self.assertIn("WORD=ADJ:pokřtěný", self.okno.texty(AXES_ID))

    def test_dotaz_jde_do_sluzby_s_dohodnutym_poctem_vet(self):
        self.okna.attach()

        self.okna.ask("Kdo?")

        self.assertEqual(self.sluzba.dotazy, [("Kdo?", 5)])


try:
    import viewbase                                       # noqa: F401
    MAME_VIEWBASE = True
except ImportError:
    MAME_VIEWBASE = False


@unittest.skipUnless(MAME_VIEWBASE, "viewbase není nainstalovaný")
class TestZrcadleniSkutecnehoGrafu(unittest.TestCase):
    """Graf vzniká PŘED oknem — zrcadlo to musí zvládnout.

    Zapsáno po chybě: služba staví graf v `build()`, tedy dřív, než okno
    vůbec existuje. `refresh()` jen doplňuje uzlům metadata a na uzlu,
    který v okně není, spadne (`ValueError: Uzel 'NOUN:počátek'
    neexistuje`). Napřed musí jít `mirror()`, který graf do okna dožene.
    """

    def test_mirror_pred_refresh_projde(self):
        from viewbase import GraphWindow

        from cb_bond.graph import KnowledgeGraph
        from cb_bond.mirror import GraphMirror
        from cb_bond.tests.vzorky import KRESTA
        from cb_field import SentenceField

        pole = SentenceField(KRESTA.tokens, r=1, source=KRESTA.source)
        graf = KnowledgeGraph()
        graf.add_sentence(pole)

        zrcadlo = GraphMirror(GraphWindow(title="test"))
        zrcadlo.mirror(graf)
        zrcadlo.refresh(graf)          # bez mirror() spadne

    def test_SAMOTNY_refresh_na_prazdne_okno_spadne(self):
        # to je ta vada — test ji drží popsanou, aby se nevrátila
        from viewbase import GraphWindow

        from cb_bond.graph import KnowledgeGraph
        from cb_bond.mirror import GraphMirror
        from cb_bond.tests.vzorky import KRESTA
        from cb_field import SentenceField

        pole = SentenceField(KRESTA.tokens, r=1, source=KRESTA.source)
        graf = KnowledgeGraph()
        graf.add_sentence(pole)

        zrcadlo = GraphMirror(GraphWindow(title="test"))

        with self.assertRaises(ValueError):
            zrcadlo.refresh(graf)


if __name__ == "__main__":
    unittest.main()
