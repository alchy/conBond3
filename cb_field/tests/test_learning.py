"""Testy učení vah: Hebb, kontrastivní krok, ochrana axiomů."""

import unittest

from cb_field import Corpus, SentenceField, VerticalRegistry
from cb_field.learning import LEARN_PREFIXES, _semantic_bag, \
    contrastive_step, hebb, sentence_hit, split_etalon
from cb_field.tests.test_templates import (BEZELA, DO, KOCKA, LESA, PARKU,
                                           PES, SEL, TECKA)


class TestHebb(unittest.TestCase):

    def test_souaktivace_vytvori_hranu_se_zdrojem_hebb(self):
        # třetí věta bez páru je nutná: kde se vše souvyskytuje všude,
        # je PMI po právu nula — „nad náhodu" potřebuje kontrast
        corpus = Corpus(r=1)
        for tokens, source in (
                ((SEL, PES, DO, LESA, TECKA), "Šel pes do lesa."),
                ((BEZELA, PES, DO, PARKU, TECKA), "Běžel pes do parku."),
                ((BEZELA, KOCKA, TECKA), "Běžela kočka.")):
            corpus.fields.append(SentenceField(
                tokens, r=1, registry=corpus.registry, source=source))
        stats = hebb(corpus)
        self.assertGreater(stats["hran"], 0)
        # pes a dir:to se souaktivují v obou větách → hrana hebb
        edge = corpus.registry.get_link("WORD=NOUN:pes", "ANCHOR=dir:to")
        self.assertIsNotNone(edge)
        self.assertEqual(edge[1], "hebb")
        # axiomy zůstaly axiomy
        self.assertEqual(
            corpus.registry.get_link("QANCHOR=space", "ANCHOR=space"),
            (1.0, "axiom"))


class TestKontrastivniKrok(unittest.TestCase):

    def test_posili_spravnou_oslabi_vitez_a_respektuje_meze(self):
        registry = VerticalRegistry(anchors=False)
        question = {"QLEM=ADV:kde": 0.7}
        correct = {"WORD=PROPN:Brno": 0.7}
        wrong = {"WORD=PROPN:Praha": 0.7}
        changed = contrastive_step(registry, question, correct, wrong,
                                   eta=0.2)
        self.assertEqual(changed, 2)
        up = registry.get_link("QLEM=ADV:kde", "WORD=PROPN:Brno")
        down = registry.get_link("QLEM=ADV:kde", "WORD=PROPN:Praha")
        self.assertGreater(up[0], 0)
        self.assertLess(down[0], 0)
        self.assertEqual(up[1], "etalon")
        # opakování narazí na meze ±1, nikdy je nepřekročí
        for _ in range(50):
            contrastive_step(registry, question, correct, wrong, eta=0.2)
        self.assertLessEqual(
            registry.get_link("QLEM=ADV:kde", "WORD=PROPN:Brno")[0], 1.0)
        self.assertGreaterEqual(
            registry.get_link("QLEM=ADV:kde", "WORD=PROPN:Praha")[0], -1.0)

    def test_axiom_se_neuci(self):
        registry = VerticalRegistry()          # kotevní axiomy od narození
        contrastive_step(
            registry, {"QANCHOR=space": 0.7}, {"ANCHOR=space": 0.7}, {},
            eta=0.2)
        # šíření rozdílu smí stavět DALŠÍ hrany (rozdíl teče po
        # axiomech do sousedních kotev), ale axiom sám zůstává axiom
        self.assertEqual(
            registry.get_link("QANCHOR=space", "ANCHOR=space"),
            (1.0, "axiom"))


class TestCustomOsyVUceni(unittest.TestCase):
    """Promovaná osa vstupuje do učení AKTIVACÍ řádku (J. 2026-08-04):
    po selektu vertikál do custom slotů se koše přepočítají a surový
    učicí pytel nese osu jako každou jinou — transparentně, bez
    zvláštní větve. Šíření pytlů maticí zavrženo měřením (22,9M hran,
    0,43 → 0,17)."""

    def test_invariant_nn_trenuje_jen_nad_metadaty_z_vertikal(self):
        # NEPORUŠITELNÉ (J. 2026-08-04): „nemůžeme nikdy trénovat NN
        # nad jinými daty, než metadaty z vertikál." Pojistka proti
        # vakuu: řádky věty slova NESOU (WORD= v COMPLETE existuje),
        # a přesto do učicího pytle neprojdou.
        field = SentenceField((SEL, PES, DO, LESA, TECKA), r=1)
        self.assertTrue(any(k.startswith("WORD=")
                            for row in field.complete for k in row))
        bag = _semantic_bag(field, range(len(field.tokens)))
        self.assertTrue(bag)                       # pytel není prázdný
        self.assertTrue(all(k.startswith(LEARN_PREFIXES) for k in bag))
        self.assertFalse(any(k.startswith("WORD=") for k in bag))
        self.assertNotIn("WORD=", "".join(LEARN_PREFIXES))

    def test_uceni_je_metadatovy_model_slovo_jen_promoci(self):
        # učení probíhá nad metadaty (J.): konkrétní slovo do pytle
        # nevstupuje — jedinou branou je promoce do vertikál
        registry = VerticalRegistry(anchors=False)
        registry.set_custom_axes(("CUSTOM=NOUN:pes",))
        field = SentenceField((SEL, PES, DO, LESA, TECKA), r=1,
                              registry=registry)
        bag = _semantic_bag(field, range(len(field.tokens)))
        self.assertNotIn("WORD=NOUN:pes", bag)     # slovo ne
        self.assertNotIn("WORD=NOUN:les", bag)
        self.assertEqual(bag["CUSTOM=NOUN:pes"], 0.7)   # promované ano
        self.assertIn("LEM=ADP:do", bag)           # zavřená třída zůstává
        changed = contrastive_step(registry, {"QLEM=ADV:kde": 0.7},
                                   bag, {}, eta=0.2)
        self.assertGreater(changed, 0)
        edge = registry.get_link("QLEM=ADV:kde", "CUSTOM=NOUN:pes")
        self.assertIsNotNone(edge)
        self.assertGreater(edge[0], 0)
        self.assertEqual(edge[1], "etalon")


class TestVetnyKontrast(unittest.TestCase):
    """Krok C: učicí vztah je otázka(meta) → VĚTA(meta) — kontrast
    fitující věty proti nejlepší nefitující, pytle celých vět bez
    zdůrazněného středu (poziční nezávislost)."""

    def test_bez_soupericí_vety_se_neuci(self):
        from cb_field.learning import train_on_etalon
        from cb_field.tests.test_matching import _scena

        class _P:
            def parse(self, text):
                from cb_field.tests.test_matching import (KAM, BEZELA2,
                                                          KOCKA2, OTAZNIK)
                class _R:
                    sentences = [type("_S", (), {
                        "tokens": (KAM, BEZELA2, KOCKA2, OTAZNIK),
                        "source": "Kam běžela kočka?"})()]
                return _R()

        corpus = _scena()              # jediná věta — soupeř není
        stats = train_on_etalon(corpus, [{"otazka": "Kam běžela kočka?",
                                          "odpoved_lemma": "les",
                                          "zodpoveditelna": True}], _P())
        self.assertEqual(stats["kroku"], 0)


class TestValidacniSada(unittest.TestCase):
    """Zobecnění (J. 2026-08-04): 30 % otázek se při učení nepoužije
    a měří se na nich loss; rozdělení je deterministické (semínko)
    a vrstvené — zodpověditelné i nezodpověditelné v témž poměru."""

    def _entries(self):
        return ([{"otazka": f"Z{i}?", "odpoved_lemma": "x",
                  "zodpoveditelna": True} for i in range(7)]
                + [{"otazka": f"N{i}?", "odpoved_lemma": None,
                    "zodpoveditelna": False} for i in range(3)])

    def test_rozdeleni_je_deterministicke_a_vrstvene(self):
        train, valid = split_etalon(self._entries(), share=0.3, seed=328)
        train2, valid2 = split_etalon(self._entries(), share=0.3,
                                      seed=328)
        self.assertEqual(valid, valid2)          # totéž semínko, týž los
        self.assertEqual(len(train) + len(valid), 10)
        texts = {e["otazka"] for e in train} \
            & {e["otazka"] for e in valid}
        self.assertEqual(texts, set())           # disjunktní
        self.assertEqual(sum(1 for e in valid if e["zodpoveditelna"]), 2)
        self.assertEqual(sum(1 for e in valid
                             if not e["zodpoveditelna"]), 1)

    def test_jine_seminko_jiny_los(self):
        _t1, valid1 = split_etalon(self._entries(), share=0.3, seed=1)
        _t2, valid2 = split_etalon(self._entries(), share=0.3, seed=2)
        self.assertNotEqual([e["otazka"] for e in valid1],
                            [e["otazka"] for e in valid2])


class TestVetaVKandidatech(unittest.TestCase):

    def test_uspech_optimalizace_je_veta_v_kandidatech(self):
        # úspěch posílení: validní věta je mezi kandidátními větami
        from cb_field.matching import match
        from cb_field.tests.test_matching import (KAM, OTAZNIK, PES2,
                                                  SEL2, _scena)
        corpus = _scena()
        question = SentenceField((KAM, SEL2, PES2, OTAZNIK), r=1,
                                 registry=corpus.registry)
        result = match(question, corpus)
        self.assertTrue(sentence_hit(result, "les"))     # věta s lesem
        self.assertFalse(sentence_hit(result, "kočka"))  # v korpusu není


if __name__ == "__main__":
    unittest.main()
