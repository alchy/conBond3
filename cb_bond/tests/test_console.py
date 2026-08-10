"""Testy konzole — textový prompt nad fasádou.

Konzole je tenká: přečte řádek, zavolá `ask` a vypíše odpověď i rozklad.
Testuje se přes vstup a výstup jako soubory, ne přes skutečný terminál —
jinak by test potřeboval člověka.
"""

import io
import unittest

from cb_bond.console import Console


class _Sluzba:
    """Atrapa fasády."""

    def __init__(self):
        self.dotazy = []
        self.kontexty = []

    def ask(self, text, *, top=None):
        self.dotazy.append(text)
        return {"question": text, "answer": "Jordán", "outcome": "answer",
                "score": 2.0, "missing": [],
                "decomposition": {"meet": 2.0},
                "sentences": [{"position": 1, "lemma": "Jordán",
                               "score": 2.0, "text": "…v Jordánu…"}],
                "axes": [{"axis": "WORD=PROPN:Ježíš", "coverage": 0.885}]}

    def context(self, text):
        self.kontexty.append(text)
        return {"sentences": 2913, "edges": 9}

    def resolve_reference(self, choice):
        self.rozreseno = choice
        return {"kind": "reference_resolved", "choice": choice,
                "subject": "auto", "source_text": "Je auto prostředek?",
                "truth": "TRUE", "answer": "Ano.",
                "explanations": ["auto je prostředek (doloženo: dialog)"],
                "conflicted": False}

    def state(self):
        return {"sentences": 2912, "edges": 16074, "lemmas": 5695}


def _konzole(vstup: str):
    sluzba = _Sluzba()
    vystup = io.StringIO()
    return Console(sluzba, vstup=io.StringIO(vstup), vystup=vystup), vystup


class TestOtazky(unittest.TestCase):

    def test_radek_se_zepta_a_vypise_odpoved(self):
        konzole, vystup = _konzole("Kde byl pokřtěn Ježíš?\n")

        konzole.run()

        self.assertIn("Jordán", vystup.getvalue())

    def test_vypise_i_ROZKLAD_skore(self):
        konzole, vystup = _konzole("Kdo?\n")

        konzole.run()

        self.assertIn("meet", vystup.getvalue())

    def test_prazdny_radek_se_PRESKOCI(self):
        konzole, _ = _konzole("\n\nKdo?\n")

        konzole.run()

        self.assertEqual(konzole.service.dotazy, ["Kdo?"])


class TestPrikazy(unittest.TestCase):
    """Bez příkazů by dialogová vrstva nešla vyzkoušet jinak než skriptem."""

    def test_context_prida_vetu_do_korpusu(self):
        konzole, _ = _konzole(":context Dálnice je silnice.\n")

        konzole.run()

        self.assertEqual(konzole.service.kontexty, ["Dálnice je silnice."])

    def test_state_vypise_statistiky(self):
        konzole, vystup = _konzole(":state\n")

        konzole.run()

        self.assertIn("16074", vystup.getvalue())

    def test_neznamy_prikaz_je_HLASKA_ne_otazka(self):
        # tiché položení „:neco" jako otázky by vypadalo jako chyba
        # párování, ne jako překlep v příkazu
        konzole, vystup = _konzole(":neexistuje\n")

        konzole.run()

        self.assertEqual(konzole.service.dotazy, [])
        self.assertIn("neznámý příkaz", vystup.getvalue())

    def test_quit_ukonci(self):
        konzole, _ = _konzole(":quit\nKdo?\n")

        konzole.run()

        self.assertEqual(konzole.service.dotazy, [])

    def test_trida_dokonci_doptani_na_referenci(self):
        konzole, vystup = _konzole(":trida\n")

        konzole.run()

        self.assertEqual(konzole.service.rozreseno, "class")
        self.assertIn("Ano.", vystup.getvalue())

    def test_instance_dokonci_doptani_na_referenci(self):
        konzole, _ = _konzole(":instance\n")

        konzole.run()

        self.assertEqual(konzole.service.rozreseno, "instance")

    def test_chyba_prikazu_se_vypise_a_konzole_bezi_dal(self):
        # Zapsáno po reálném pádu: stará služba bez /v1/logic/resolve
        # hodila RuntimeError a spadla celá konzole. Chyba se píše do
        # výstupu jako u otázky — člověk čte dál, nehledá traceback.
        konzole, vystup = _konzole(":trida\nKdo?\n")

        def chyba(choice):
            raise RuntimeError("neznámá cesta /v1/logic/resolve")
        konzole.service.resolve_reference = chyba

        konzole.run()

        self.assertIn("chyba", vystup.getvalue())
        self.assertEqual(konzole.service.dotazy, ["Kdo?"])   # běží dál


if __name__ == "__main__":
    unittest.main()
