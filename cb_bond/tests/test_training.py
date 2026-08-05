"""Testy kontrastivního učení — invariant, marže, odvolání epochy.

Nejdůležitější test tady je pojistka: do učicího pytle NESMÍ WORD=.
Konkrétní slovo se k učení dostane jedině promocí do custom slotu;
kdyby prošlo jinudy, systém by memoroval dvojice slov místo typů —
naměřeno, mosty slovo↔slovo se mezi otázkami nepřenášejí.
"""

import unittest

from cb_bond import ContrastiveTrainer, Matcher
from cb_bond.training import ValidationSplit, learning_bag, sentence_hit
from cb_bond.tests.vzorky import (GRAVITACE, KRESTA, OTAZKA_KREST, SYNAGOGA,
                                  VEZENI)
from cb_field import Corpus, SentenceField


def _korpus(*vety):
    corpus = Corpus(r=1)
    for veta in vety:
        corpus.add_sentence(veta)
    return corpus


class _Parser:
    """Atrapa: vrací zmražené rozbory podle textu otázky."""

    def __init__(self, mapa):
        self.mapa = mapa

    def parse(self, text):
        class _R:
            sentences = (self.mapa[text],)
        return _R()


def _trener(corpus, **kw):
    parser = _Parser({OTAZKA_KREST.source: OTAZKA_KREST})
    matcher = Matcher(corpus, spread_depth=1, theta=0.0)
    return ContrastiveTrainer(corpus, matcher, parser, **kw)


ZAZNAM = {"otazka": OTAZKA_KREST.source, "odpoved_lemma": "Jordán",
          "zodpoveditelna": True}


class TestInvariant(unittest.TestCase):
    """Pojistka: učení jen nad metadaty vertikál (princip 1)."""

    def test_ucici_pytel_NIKDY_nenese_WORD(self):
        corpus = _korpus(KRESTA)
        pole = corpus[0]

        pytel = learning_bag(pole.complete)

        self.assertFalse([klic for klic in pytel if klic.startswith("WORD=")],
                         "WORD= v učicím pytli = memorování dvojic slov")

    def test_ucici_pytel_nese_metadata_vertikal(self):
        corpus = _korpus(KRESTA)

        pytel = learning_bag(corpus[0].complete)

        self.assertTrue(any(k.startswith("ANCHOR=") for k in pytel))
        self.assertTrue(any(k.startswith("Polarity=") for k in pytel))

    def test_promovane_slovo_se_do_uceni_dostane_JEN_slotem(self):
        # jediná cesta konkrétního slova do učení je CUSTOM=
        corpus = _korpus(KRESTA)
        corpus.registry.set_custom_axes(["PROPN:Jordán"])
        corpus.regenerate()

        pytel = learning_bag(corpus[0].complete)

        self.assertIn("CUSTOM=PROPN:Jordán", pytel)
        self.assertNotIn("WORD=PROPN:Jordán", pytel)

    def test_zadna_naucena_hrana_nevede_ze_slovni_osy(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        trener = _trener(corpus)
        pred = set(corpus.registry.links())

        trener.train([ZAZNAM], max_epochs=1)

        nove = set(corpus.registry.links()) - pred
        for src, dst, _ in nove:
            self.assertFalse(src.startswith("WORD=") or dst.startswith("WORD="),
                             f"naučená hrana {src}→{dst} nese slovo")


class TestSplit(unittest.TestCase):

    def test_odklada_tretinu_a_je_deterministicky(self):
        zaznamy = [{"otazka": f"q{i}", "zodpoveditelna": i % 3 != 0}
                   for i in range(30)]

        a = ValidationSplit().split(zaznamy)
        b = ValidationSplit().split(zaznamy)

        self.assertEqual(len(a[1]), 9)          # 30 % z 30
        self.assertEqual(len(a[0]), 21)
        self.assertEqual([z["otazka"] for z in a[1]],
                         [z["otazka"] for z in b[1]])

    def test_los_je_VRSTVENY_podle_zodpoveditelnosti(self):
        zaznamy = ([{"otazka": f"a{i}", "zodpoveditelna": True}
                    for i in range(20)]
                   + [{"otazka": f"n{i}", "zodpoveditelna": False}
                      for i in range(10)])

        _, odlozene = ValidationSplit().split(zaznamy)

        zodp = sum(1 for z in odlozene if z["zodpoveditelna"])
        self.assertEqual(zodp, 6)               # 30 % z 20
        self.assertEqual(len(odlozene) - zodp, 3)   # 30 % z 10

    def test_jine_seminko_da_jine_rozdeleni(self):
        zaznamy = [{"otazka": f"q{i}", "zodpoveditelna": True}
                   for i in range(30)]

        a = ValidationSplit(seed=328).split(zaznamy)[1]
        b = ValidationSplit(seed=1).split(zaznamy)[1]

        self.assertNotEqual([z["otazka"] for z in a],
                            [z["otazka"] for z in b])


class TestKrokUceni(unittest.TestCase):

    def test_bez_souperici_vety_se_NEUCI(self):
        # korpus, kde lemma odpovědi nese jediná věta → soupeř není
        corpus = _korpus(KRESTA)
        trener = _trener(corpus)
        pred = dict(((s, d), w) for s, d, w in corpus.registry.links())

        zprava = trener.train([ZAZNAM], max_epochs=1)

        self.assertEqual(zprava.epochs[0]["korekci"], 0)
        self.assertEqual(
            dict(((s, d), w) for s, d, w in corpus.registry.links()), pred)

    def test_splnena_marze_krok_nedela(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        trener = _trener(corpus, margin=0.0, lr=0.0)

        zprava = trener.train([ZAZNAM], max_epochs=1)

        self.assertEqual(zprava.epochs[0]["korekci"], 0)

    def test_porusena_marze_zalozi_hranu_z_metadat_otazky(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        trener = _trener(corpus, margin=9.0)      # marže se splnit nedá
        pred = set(corpus.registry.links())

        zprava = trener.train([ZAZNAM], max_epochs=1)

        self.assertGreater(zprava.epochs[0]["korekci"], 0)
        nove = set(corpus.registry.links()) - pred
        self.assertTrue(nove)
        self.assertTrue(any(src.startswith(("QLEM=", "QANCHOR="))
                            for src, _, _ in nove))

    def test_vazba_osy_na_sebe_samu_nevznikne(self):
        # Naměřeno: učení zakládalo LEM=ADP:v → LEM=ADP:v. Taková hrana
        # při šíření jen zesiluje aktivaci samu ze sebe a žádný vztah
        # nenese — táž úvaha jako u smyček v grafu, o patro výš.
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        trener = _trener(corpus, margin=9.0, lr=0.5)

        trener.train([ZAZNAM], max_epochs=3)

        smycky = [(s, d) for s, d, _ in corpus.registry.links() if s == d]
        self.assertEqual(smycky, [])

    def test_axiomy_se_uchrani(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        axiomy = {(s, d): w for s, d, w in corpus.registry.links()
                  if s.startswith(("ANCHOR=", "QANCHOR="))
                  and d.startswith("ANCHOR=")}
        trener = _trener(corpus, margin=9.0)

        trener.train([ZAZNAM], max_epochs=2)

        for (src, dst), vaha in axiomy.items():
            self.assertAlmostEqual(corpus.registry.get_link(src, dst), vaha,
                                   places=6)

    def test_vahy_zustanou_v_mezich(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        trener = _trener(corpus, margin=9.0, lr=0.9)

        trener.train([ZAZNAM], max_epochs=5)

        for _, _, vaha in corpus.registry.links():
            self.assertGreaterEqual(vaha, -1.0)
            self.assertLessEqual(vaha, 1.0)


class TestOdvolaniEpochy(unittest.TestCase):

    def test_sum_v_posledni_cifre_epochu_NEODVOLA(self):
        # Naměřeno: epocha srazila trénink 0,114 → 0,095 a validaci
        # zhoršila o 0,00006. Odvolat kvůli šesti stotisícinám znamená
        # neučit se vůbec — odvolání má hlídat ZHORŠENÍ, ne poslední bit.
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE, VEZENI)
        trener = _trener(corpus, margin=9.0, lr=0.5)
        hodnoty = iter([0.11444, 0.11450, 0.11450])
        trener._validacni_loss = lambda entries: next(hodnoty)

        zprava = trener.train([ZAZNAM], max_epochs=2)

        self.assertFalse(zprava.epochs[0]["odvolano"])

    def test_horsi_validace_epochu_ODVOLA(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE, VEZENI)
        trener = _trener(corpus, margin=9.0, lr=0.5)
        # validační loss uměle roste s každým měřením → epocha se vrátí
        pocitadlo = iter([0.1, 0.05, 0.4, 0.9])   # 0,05 → 0,4 je 8×
        trener._validacni_loss = lambda entries: next(pocitadlo)

        zprava = trener.train([ZAZNAM], max_epochs=3)

        self.assertTrue(zprava.epochs[-1]["odvolano"])
        self.assertGreaterEqual(len(zprava.epochs), 2)

    def test_odvolana_epocha_vrati_vazby(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE, VEZENI)
        trener = _trener(corpus, margin=9.0, lr=0.5)
        # validace se měří i PŘED učením: 0,1 na začátku, 9,9 po epoše
        hodnoty = iter([0.1, 9.9])
        trener._validacni_loss = lambda entries: next(hodnoty)
        pred = {(s, d): w for s, d, w in corpus.registry.links()}

        trener.train([ZAZNAM], max_epochs=1)

        self.assertEqual({(s, d): w for s, d, w in corpus.registry.links()},
                         pred)


class TestPoctivostLossu(unittest.TestCase):
    """Loss se nesmí ředit otázkami, které nešly ani zkusit."""

    def test_epocha_hlasi_kolik_otazek_PRESKOCILA(self):
        # Naměřeno: z 85 tréninkových otázek jich 66 nemá fitující větu.
        # Když se loss dělí všemi, vyjde 0,0949 místo 0,4248 — číslo
        # vypadá 4,5× lépe, než jaká je skutečnost.
        corpus = _korpus(KRESTA)          # jediná věta → není soupeř
        trener = _trener(corpus)

        zprava = trener.train([ZAZNAM], max_epochs=1)

        self.assertEqual(zprava.epochs[0]["preskoceno"], 1)
        self.assertEqual(zprava.epochs[0]["skorovano"], 0)

    def test_loss_se_deli_SKOROVANYMI_ne_vsemi(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        trener = _trener(corpus, margin=9.0)

        # jedna skórovatelná otázka + dvě, které skórovat nejdou
        zaznamy = [ZAZNAM,
                   {"otazka": OTAZKA_KREST.source,
                    "odpoved_lemma": "nesmysl", "zodpoveditelna": True},
                   {"otazka": OTAZKA_KREST.source,
                    "odpoved_lemma": "nesmysl2", "zodpoveditelna": True}]
        zprava = trener.train(zaznamy, max_epochs=1)

        epocha = zprava.epochs[0]
        self.assertEqual(epocha["skorovano"], 1)
        self.assertEqual(epocha["preskoceno"], 2)
        # loss patří k té JEDNÉ otázce, ne k průměru přes tři
        self.assertGreater(epocha["loss"], 0.3)


class TestPohledNaVahy(unittest.TestCase):
    """Co se model naučil — v průběhu, ne až na konci."""

    def test_epocha_hlasi_KTERE_hrany_zmenila(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        trener = _trener(corpus, margin=9.0, lr=0.5)

        zprava = trener.train([ZAZNAM], max_epochs=1)

        zmeny = zprava.epochs[0]["zmeny"]
        self.assertTrue(zmeny)
        src, dst, stara, nova = zmeny[0]
        self.assertNotEqual(stara, nova)
        self.assertIsInstance(src, str)

    def test_zmeny_jsou_serazene_podle_VELIKOSTI_kroku(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        trener = _trener(corpus, margin=9.0, lr=0.5)

        zmeny = trener.train([ZAZNAM], max_epochs=1).epochs[0]["zmeny"]

        kroky = [abs(nova - stara) for _, _, stara, nova in zmeny]
        self.assertEqual(kroky, sorted(kroky, reverse=True))

    def test_odvolana_epocha_hlasi_co_se_ZAHODILO(self):
        # i odvolaná epocha má být čitelná: člověk chce vidět, co se
        # systém pokusil naučit a proč to bylo vráceno
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE, VEZENI)
        trener = _trener(corpus, margin=9.0, lr=0.5)
        hodnoty = iter([0.1, 9.9])
        trener._validacni_loss = lambda entries: next(hodnoty)

        zprava = trener.train([ZAZNAM], max_epochs=1)

        self.assertTrue(zprava.epochs[0]["odvolano"])
        self.assertTrue(zprava.epochs[0]["zmeny"])

    def test_souhrn_rika_MEZI_KTERYMI_vrstvami_se_ucilo(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        trener = _trener(corpus, margin=9.0, lr=0.5)

        zprava = trener.train([ZAZNAM], max_epochs=1)

        # {(prefix zdroje, prefix cíle): počet hran}
        souhrn = zprava.epochs[0]["vrstvy"]
        self.assertTrue(souhrn)
        for (src, dst), pocet in souhrn.items():
            self.assertNotIn("=", src)      # jen prefix, ne celý klíč
            self.assertGreater(pocet, 0)


class TestPrubeh(unittest.TestCase):
    """Učení běží desítky sekund — nesmí u toho mlčet."""

    def test_hlasi_prubeh_uz_BEHEM_epochy(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        zpravy = []
        trener = _trener(corpus, margin=9.0, progress=zpravy.append)

        trener.train([ZAZNAM, dict(ZAZNAM), dict(ZAZNAM)], max_epochs=1)

        faze = [z["faze"] for z in zpravy]
        self.assertIn("otazka", faze)      # ne až po epoše
        self.assertIn("epocha", faze)

    def test_prubeh_nese_kolik_je_hotovo_z_kolika(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        zpravy = []
        trener = _trener(corpus, margin=9.0, progress=zpravy.append)

        trener.train([ZAZNAM], max_epochs=1)

        otazky = [z for z in zpravy if z["faze"] == "otazka"]
        self.assertTrue(otazky)
        self.assertIn("hotovo", otazky[0])
        self.assertIn("celkem", otazky[0])

    def test_bez_hlasice_se_nic_nedeje(self):
        # výchozí stav je tichý — jádro nesmí psát na výstup samo
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)

        zprava = _trener(corpus, margin=9.0).train([ZAZNAM], max_epochs=1)

        self.assertTrue(zprava.epochs)


class TestZasah(unittest.TestCase):

    def test_sentence_hit_hleda_lemma_mezi_TOP_vetami(self):
        corpus = _korpus(KRESTA, SYNAGOGA, GRAVITACE)
        matcher = Matcher(corpus, spread_depth=1, theta=0.0)
        otazka = SentenceField.from_sentence(OTAZKA_KREST, r=1,
                                             registry=corpus.registry)
        vysledek = matcher.match(otazka)

        self.assertTrue(sentence_hit(vysledek, "Jordán", corpus, top=3))
        self.assertFalse(sentence_hit(vysledek, "nesmysl", corpus, top=3))


if __name__ == "__main__":
    unittest.main()
