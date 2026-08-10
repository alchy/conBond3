"""Guard — hranice, kterou učení jazyka NESMÍ prolomit (LANGUAGE_LEARNING.md).

Modalita je dotaz nad modely, ne osa pravdivosti (kap. 41). Tyto testy tu
hranici drží strojově: menu bez modálních operátorů, modální vzor produkuje
DOTAZ ne uložené tvrzení, objektový jazyk bez uzlu modality.
"""
import unittest

import cb_logic.expressions as expressions
from cb_logic import KnowledgeBase, Truth
from cb_interpret.learner import DialogueLearner
from cb_interpret.patterns import OPERATION_MENU, Operation, StructuralSignature
from cb_interpret.tests import vzorky


class TestBoundary(unittest.TestCase):
    def test_menu_obsahuje_jen_dotazy_nad_modely(self):
        # Uzavřené menu = přesně tři modelové dotazy, žádný modální operátor.
        self.assertEqual({op for op, _ in OPERATION_MENU},
                         {Operation.POSSIBLE, Operation.NECESSARY,
                          Operation.IMPOSSIBLE})

    def test_objektovy_jazyk_nema_uzel_modality(self):
        # V Expression AST nesmí být modální operátor (◇/□).
        node_names = {name for name in dir(expressions)
                      if name[:1].isupper()}
        for forbidden in ("Modal", "Possibly", "Necessarily", "Box",
                          "Diamond"):
            self.assertNotIn(forbidden, node_names)

    def test_modalni_dotaz_nezapisuje_do_baze(self):
        """Modální konstrukce spustí dotaz, NIKDY assert — báze beze změny."""
        learner = DialogueLearner(KnowledgeBase())
        learner.teach_pattern(StructuralSignature("moci", has_xcomp=True),
                              Operation.POSSIBLE, learned_from="…")
        before_facts = learner.kb.own_facts()
        before_rules = list(learner.kb.rules)
        result = learner.ask(vzorky.MUZE_AUTO_JET, "Auto může jet na silnici.")
        self.assertEqual(result.candidate.kind, "modal_query")
        # osa pravdivosti se nedotkla báze:
        self.assertEqual(learner.kb.own_facts(), before_facts)
        self.assertEqual(learner.kb.rules, before_rules)

    def test_uceni_modalu_pres_learn_nezapisuje_fakt(self):
        """I když modální větu pošleme jako sdělení, neuloží se jako fakt."""
        learner = DialogueLearner(KnowledgeBase())
        learner.teach_pattern(StructuralSignature("moci", has_xcomp=True),
                              Operation.POSSIBLE, learned_from="…")
        r = learner.learn(vzorky.MUZE_AUTO_JET, "Auto může jet na silnici.")
        self.assertIsNone(r.outcome)              # nic se nepřijalo
        self.assertEqual(learner.kb.own_facts(), ())


if __name__ == "__main__":
    unittest.main()
