"""Testy párování otázky s korpusem — Matcher, saturate, MatchResult.

Zmražené rozbory (vzorky.py), žádná běžící služba. Čísla, která jdou
spočítat ručně, se v testech počítají ručně: tanh(0,7) = 0,604 je váha
jednoho výskytu slovní osy, tanh(1,4) = 0,885 dvou.
"""

import math
import unittest

import numpy as np

from cb_bond import (Matcher, MatchResult, ScoreCandidate,
                     ScoreWeights, saturate, semantic_bag)
from cb_bond.tests.vzorky import KRESTA, OTAZKA_KREST, SYNAGOGA
from cb_field import Corpus, SentenceField
from cb_bond.matcher import _cos


def _korpus(*vety, r=1):
    corpus = Corpus(r=r)
    for veta in vety:
        corpus.add_sentence(veta)
    return corpus


def _otazka(corpus, veta=OTAZKA_KREST):
    """Otázka jako pole nad TÝMŽ registrem — osa musí být společná."""
    return SentenceField.from_sentence(veta, r=corpus.r,
                                       registry=corpus.registry)


class TestSaturate(unittest.TestCase):

    def test_bez_vazeb_je_to_jen_tanh(self):
        v = np.array([0.7, 1.4, 0.0], dtype=np.float32)

        out = saturate(v, None, steps=1)

        self.assertAlmostEqual(float(out[0]), math.tanh(0.7), places=5)
        self.assertAlmostEqual(float(out[1]), math.tanh(1.4), places=5)
        self.assertEqual(float(out[2]), 0.0)

    def test_tanh_po_kazdem_kroku_ne_az_na_konci(self):
        v = np.array([2.0], dtype=np.float32)

        dva = saturate(v, None, steps=2)

        # dvakrát tanh, ne tanh jednou: tanh(tanh(2)) < tanh(2)
        self.assertAlmostEqual(float(dva[0]), math.tanh(math.tanh(2.0)),
                               places=5)

    def test_nula_kroku_nechava_vektor_beze_zmeny(self):
        v = np.array([0.7, -0.3], dtype=np.float32)

        self.assertTrue(np.array_equal(saturate(v, None, steps=0), v))


class TestDaneOsy(unittest.TestCase):

    def test_given_axes_jsou_slova_otazky_bez_tazacich(self):
        corpus = _korpus(KRESTA)
        matcher = Matcher(corpus)

        osy = matcher.given_axes(_otazka(corpus))

        self.assertEqual(set(osy), {"WORD=AUX:být", "WORD=ADJ:pokřtěný",
                                    "WORD=PROPN:Ježíš"})
        # „kde" se ptá, netvrdí — mezi dané osy nepatří
        self.assertNotIn("WORD=ADV:kde", osy)


class TestSemantickaMaska(unittest.TestCase):

    def test_strukturni_osy_z_pytle_uplne_vypadnou(self):
        corpus = _korpus(KRESTA)
        otazka = _otazka(corpus)

        pytel = semantic_bag(otazka.complete)

        for klic in pytel:
            self.assertFalse(klic.startswith(("UPOS=", "DEPREL=", "Case=",
                                              "SUBPOS=", "Gender=",
                                              "Number=")),
                             f"strukturní osa {klic} v pytli zůstala")

    def test_vyznamove_osy_v_pytli_zustanou(self):
        corpus = _korpus(KRESTA)

        pytel = semantic_bag(_otazka(corpus).complete)

        self.assertIn("WORD=PROPN:Ježíš", pytel)
        self.assertIn("QLEM=ADV:kde", pytel)
        self.assertTrue(any(k.startswith("QANCHOR=") for k in pytel))

    def test_pytel_je_soucet_pres_radky(self):
        corpus = _korpus(KRESTA)
        pole = corpus[0]

        pytel = semantic_bag(pole.complete)

        rucne = sum(radek.get("WORD=PROPN:Ježíš", 0.0)
                    for radek in pole.complete)
        self.assertAlmostEqual(pytel["WORD=PROPN:Ježíš"], rucne, places=5)


class TestSlovaOtazky(unittest.TestCase):
    """Členy topic a given stojí na tom, co otázka TVRDÍ."""

    def test_slova_otazky_vynechaji_tazaci_slovo(self):
        # „kde" se ptá, netvrdí — v tématu ani v postihu nemá co dělat.
        # Bez toho člen `topic` odměňuje věty, které samy obsahují „kdo"
        # nebo „kde", tedy OTÁZKY v korpusu, ne odpovědi.
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)

        slova = matcher.question_words(_otazka(corpus))

        self.assertNotIn("WORD=ADV:kde", slova)
        self.assertIn("WORD=PROPN:Ježíš", slova)

    def test_slova_otazky_vynechaji_interpunkci(self):
        # otazník je v každé otázce a skoro v žádné oznamovací větě
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)

        slova = matcher.question_words(_otazka(corpus))

        self.assertFalse([k for k in slova if k.startswith("WORD=PUNCT:")])

    def test_slova_otazky_jsou_tytez_osy_jako_dane(self):
        # jedno pravidlo, ne dvě: co je „daná osa" pro pokrytí, je
        # slovem otázky i pro téma a postih
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)
        otazka = _otazka(corpus)

        self.assertEqual(set(matcher.question_words(otazka)),
                         set(matcher.given_axes(otazka)))


class TestCleny(unittest.TestCase):

    def test_meet_je_soucet_dvou_kosinu_ne_kosinus_souctu(self):
        # Identita kroku 3b: meet = cos(q̃, okno) + (W_CENTER−1)·cos(q̃, střed).
        # Kdo počítá cos(q̃, okno + 2·střed) nad surovým pytlem, trestá
        # středy s bohatou morfologií — proto je zdůraznění vlastní člen.
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1,
                          weights=ScoreWeights(center=2.0))

        kandidat = matcher.match(_otazka(corpus)).candidates[0]
        okno, stred = matcher.candidate_vectors(kandidat.sentence,
                                                kandidat.token)
        q = matcher.question_vector(_otazka(corpus))

        ocekavano = (_cos(q, okno) + (2.0 - 1.0) * _cos(q, stred))
        self.assertAlmostEqual(kandidat.decomposition()["meet"], ocekavano,
                               places=5)

    def test_okno_je_harmonicky_vazene_a_jednotkove(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)

        okno, stred = matcher.candidate_vectors(0, 3)

        self.assertAlmostEqual(float(np.linalg.norm(okno)), 1.0, places=5)
        self.assertAlmostEqual(float(np.linalg.norm(stred)), 1.0, places=5)

    def test_okno_dozniva_pres_celou_vetu_bez_hrany(self):
        # harmonická váha existuje proto, aby okno NEMĚLO hranu; ořez
        # na ±r by ji vrátil (naměřeno: stojí bod na etalonu)
        corpus = _korpus(KRESTA)
        matcher = Matcher(corpus, spread_depth=0)

        okno, _ = matcher.candidate_vectors(0, 0)   # střed na kraji věty

        # osa vzdáleného slova (Jan, poslední token) v okně svítí
        daleka = corpus.registry.index("WORD=PROPN:Jan")
        self.assertGreater(float(okno[daleka]), 0.0)

    def test_pokryti_radi_VETY_ne_tokeny(self):
        # cover je mohutnost věty, ne kosinus: všichni kandidáti téže věty
        # mají týž člen, různé věty různý
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)

        kandidati = matcher.match(_otazka(corpus)).candidates
        podle_vety = {}
        for kandidat in kandidati:
            podle_vety.setdefault(kandidat.sentence, set()).add(
                round(kandidat.decomposition()["cover"], 6))

        for veta, hodnoty in podle_vety.items():
            self.assertEqual(len(hodnoty), 1, f"věta {veta} má cover různý")
        self.assertGreater(len(set().union(*podle_vety.values())), 1,
                           "všechny věty mají týž cover — člen neřadí věty")

    def test_pokryti_vety_je_minimum_pres_dane_osy(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)
        otazka = _otazka(corpus)

        pokryti = matcher.sentence_coverage(otazka)

        # křestní věta má všechny tři dané osy, synagoga jen Ježíše →
        # její minimum je 0 (propast, ne škála)
        self.assertGreater(pokryti[0], 0.0)
        self.assertEqual(pokryti[1], 0.0)


class TestCoverage(unittest.TestCase):

    def test_pokryti_je_maximum_pres_vety(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)

        pokryti = matcher.coverage(_otazka(corpus))

        # jeden výskyt slovní osy = váha 0,7 → tanh(0,7) = 0,604
        self.assertAlmostEqual(pokryti["WORD=ADJ:pokřtěný"],
                               math.tanh(0.7), places=3)
        # Ježíš je v obou větách, ale pokrytí je MAXIMUM, ne součet
        self.assertAlmostEqual(pokryti["WORD=PROPN:Ježíš"],
                               math.tanh(0.7), places=3)

    def test_dva_vyskyty_v_jedne_vete_se_scitaji_pred_tanh(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)

        # „být" je v křestní větě jednou (AUX byl); přidáme větu, kde je
        # dvakrát — pokrytí má stoupnout na tanh(1,4) = 0,885
        corpus.add_sentence(_dvakrat_byt())
        matcher = Matcher(corpus, spread_depth=1)
        pokryti = matcher.coverage(_otazka(corpus))

        self.assertAlmostEqual(pokryti["WORD=AUX:být"],
                               math.tanh(1.4), places=3)

    def test_mrtva_osa_je_presna_nula_ne_maly_zbytek(self):
        corpus = _korpus(SYNAGOGA)          # bez křtu: pokřtěný chybí
        matcher = Matcher(corpus, spread_depth=1)

        pokryti = matcher.coverage(_otazka(corpus))

        # propast, ne škála — na tomhle stojí detekce mezery (krok 8)
        self.assertEqual(pokryti["WORD=ADJ:pokřtěný"], 0.0)


class TestMatch(unittest.TestCase):

    def test_kandidati_jsou_serazeni_sestupne_podle_skore(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus)

        vysledek = matcher.match(_otazka(corpus))

        skore = [k.score for k in vysledek.candidates]
        self.assertEqual(skore, sorted(skore, reverse=True))
        self.assertTrue(vysledek.candidates)

    def test_kandidat_zna_svou_vetu_i_token(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus)

        nejlepsi = matcher.match(_otazka(corpus)).candidates[0]

        self.assertIn(nejlepsi.sentence, range(len(corpus)))
        self.assertEqual(nejlepsi.lemma,
                         corpus[nejlepsi.sentence].tokens[nejlepsi.token].lemma)

    def test_rozklad_skore_secte_na_skore(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus)

        nejlepsi = matcher.match(_otazka(corpus)).candidates[0]
        rozklad = nejlepsi.decomposition()

        self.assertAlmostEqual(sum(rozklad.values()), nejlepsi.score,
                               places=5)
        self.assertIn("cover", rozklad)

    def test_postih_dane_osy_sraz_kandidata_z_otazky(self):
        # „Ježíš" v otázce je — kandidát Ježíš dostane záporný člen given,
        # kandidát Jordán ne (v otázce není)
        corpus = _korpus(KRESTA)
        matcher = Matcher(corpus)

        podle_lemmatu = {k.lemma: k
                         for k in matcher.match(_otazka(corpus)).candidates}

        self.assertLess(podle_lemmatu["Ježíš"].decomposition()["given"], 0.0)
        self.assertEqual(podle_lemmatu["Jordán"].decomposition()["given"], 0.0)

    def test_setkani_se_meri_az_po_sireni_obou_stran(self):
        # Otázka i okno musí protéct vazbami, jinak se nemají KDE potkat:
        # QANCHOR=space:loc a ANCHOR=space:loc stečou obojí do ANCHOR=space
        # a teprve tam je společná souřadnice. Šířit jen otázku znamená
        # měřit setkání v místě, kam druhá strana nedošla.
        corpus = _korpus(KRESTA, SYNAGOGA)
        bez_sireni = Matcher(corpus, spread_depth=0)
        se_sirenim = Matcher(corpus, spread_depth=1)

        okno_0, stred_0 = bez_sireni.candidate_vectors(0, 3)
        okno_1, stred_1 = se_sirenim.candidate_vectors(0, 3)

        self.assertFalse(np.allclose(okno_0, okno_1),
                         "okno kandidáta se po vazbách nešíří")
        self.assertFalse(np.allclose(stred_0, stred_1),
                         "střed kandidáta se po vazbách nešíří")

    def test_interpunkce_neni_kandidat(self):
        # tečka odpovědí být nemůže; jako kandidát jen ředí pořadí
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus)

        vysledek = matcher.match(_otazka(corpus))

        lemmata = {k.lemma for k in vysledek.candidates}
        self.assertNotIn(".", lemmata)
        self.assertIn("Jordán", lemmata)

    def test_vahy_jsou_paky_ne_pravidla(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        bez_tematu = Matcher(corpus, weights=ScoreWeights(topic=0.0))

        nejlepsi = bez_tematu.match(_otazka(corpus)).candidates[0]

        self.assertEqual(nejlepsi.decomposition()["topic"], 0.0)


class TestSpektralniClen(unittest.TestCase):

    def test_vypnuty_clen_skore_NEMENI(self):
        # W_SPECTRAL = 0 musí dát bit po bitu dnešek
        corpus = _korpus(KRESTA, SYNAGOGA)
        bez = Matcher(corpus, spread_depth=1)
        se_clenem = Matcher(corpus, spread_depth=1, spectral_k=2,
                            weights=ScoreWeights(spectral=0.0))

        a = bez.match(_otazka(corpus)).candidates[0]
        b = se_clenem.match(_otazka(corpus)).candidates[0]

        self.assertEqual(a.key, b.key)
        self.assertAlmostEqual(a.score, b.score, places=6)
        self.assertEqual(b.decomposition()["spectral"], 0.0)

    def test_zapnuty_clen_se_objevi_v_rozkladu(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1, spectral_k=2,
                          weights=ScoreWeights(spectral=1.0))

        rozklad = matcher.match(_otazka(corpus)).candidates[0].decomposition()

        self.assertIn("spectral", rozklad)
        self.assertNotEqual(rozklad["spectral"], 0.0)
        self.assertAlmostEqual(
            sum(rozklad.values()),
            matcher.match(_otazka(corpus)).candidates[0].score, places=5)

    def test_clen_je_VETNY_stejne_jako_pokryti(self):
        # latentní podobnost patří větě, ne tokenu — řadí věty
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1, spectral_k=2,
                          weights=ScoreWeights(spectral=1.0))

        podle_vety = {}
        for kandidat in matcher.match(_otazka(corpus)).candidates:
            podle_vety.setdefault(kandidat.sentence, set()).add(
                round(kandidat.decomposition()["spectral"], 6))

        for veta, hodnoty in podle_vety.items():
            self.assertEqual(len(hodnoty), 1, f"věta {veta} má člen různý")

    def test_bez_spectral_k_se_spektrum_nepocita(self):
        # drahé se nepočítá, dokud si o to nikdo neřekne
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)

        self.assertIsNone(matcher.spectral)


class TestVysledek(unittest.TestCase):

    def test_theta_rozhoduje_o_mlceni(self):
        corpus = _korpus(KRESTA, SYNAGOGA)

        odpovi = Matcher(corpus, theta=0.0).match(_otazka(corpus))
        mlci = Matcher(corpus, theta=99.0).match(_otazka(corpus))

        self.assertEqual(odpovi.outcome, "answer")
        self.assertEqual(mlci.outcome, "silent")

    def test_epsilon_rozhoduje_o_dotazu(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        # dva nejlepší kandidáti blízko sebe → systém se má zeptat
        vysledek = Matcher(corpus, theta=0.0, epsilon=99.0).match(
            _otazka(corpus))

        self.assertEqual(vysledek.outcome, "ask")

    def test_logika_kosu_and_je_soucin_kladnych(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, theta=0.0)
        a = matcher.match(_otazka(corpus))

        spolecne = a & a

        podle = {k.key: k.score for k in a.candidates}
        kladnych = 0
        for kandidat in spolecne.candidates:
            puvodni = podle[kandidat.key]
            if puvodni >= 0:
                self.assertAlmostEqual(kandidat.score, puvodni ** 2, places=4)
                kladnych += 1
        self.assertGreater(kladnych, 0)   # jinak by test netvrdil nic

    def test_logika_kosu_dve_zaporna_nedaji_kladne(self):
        # ručně postavené koše: součin −0,5 × −0,5 by dal +0,25, což by
        # z „ani jedno" udělalo „obojí". Minimum ten degenerát nemá.
        zaporny = _vysledek({(0, 0): -0.5, (0, 1): 0.4})

        soucin = zaporny & zaporny

        podle = {k.key: k.score for k in soucin.candidates}
        self.assertAlmostEqual(podle[(0, 0)], -0.5)     # minimum, ne součin
        self.assertAlmostEqual(podle[(0, 1)], 0.16)     # kladné se násobí

    def test_and_zachova_jen_spolecne_kandidaty(self):
        a = _vysledek({(0, 0): 0.5, (0, 1): 0.4})
        b = _vysledek({(0, 1): 0.2})

        self.assertEqual([k.key for k in (a & b).candidates], [(0, 1)])

    def test_negace_obraci_znamenko(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, theta=0.0)
        puvodni = matcher.match(_otazka(corpus))

        obraceny = ~puvodni

        podle = {k.key: k.score for k in puvodni.candidates}
        for kandidat in obraceny.candidates:
            self.assertAlmostEqual(kandidat.score, -podle[kandidat.key],
                                   places=5)


class TestDvoustupnoveCteni(unittest.TestCase):

    def test_predvyber_radi_podle_toho_co_otazka_TVRDI(self):
        # Naměřeno na 117 tréninkových otázkách: řazení podle slov, která
        # otázka tvrdí, dostane do top-50 věty s odpovědí 37×, kdežto
        # kosinus celého saturovaného pytle jen 31×. Týž princip jako
        # u členů topic a given — tázací slovo netvrdí nic.
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, spread_depth=1)
        otazka = _otazka(corpus)

        skore = matcher.recall_scores(otazka)

        self.assertEqual(len(skore), len(corpus))
        # věta s Ježíšem a křtem musí být nad větou bez nich
        self.assertGreater(float(skore[0]), 0.0)

    def test_top_k_vybere_jen_tolik_vet_kolik_ma(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus)

        vety = matcher.recall(_otazka(corpus), top_k=1)

        self.assertEqual(len(vety), 1)
        self.assertIn(vety[0], (0, 1))

    def test_jemne_cteni_bezi_JEN_v_top_k(self):
        # celý smysl dvoustupňového čtení: co se do shortlistu nedostane,
        # se po tokenech vůbec nečte
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, top_k=1)

        vysledek = matcher.match(_otazka(corpus))

        self.assertEqual(len({k.sentence for k in vysledek.candidates}), 1)


def _vektor(corpus, radky):
    """Součet aktivací řádků nad osou korpusu — pro ruční kontrolu."""
    vec = np.zeros(len(corpus.registry), dtype=np.float32)
    for radek in radky:
        for klic, vaha in radek.items():
            if klic in corpus.registry:
                vec[corpus.registry.index(klic)] += vaha
    return vec


def _vysledek(skore):
    """MatchResult z ručně zadaných skóre — pro algebru košů."""
    return MatchResult(
        [ScoreCandidate(veta, token, "x", hodnota, {})
         for (veta, token), hodnota in skore.items()], "answer")


def _dvakrat_byt():
    """Věta se dvěma výskyty AUX být — pro součet před tanh."""
    from cb_bond.tests.vzorky import Veta
    from cb_udpipe import Token
    byl = dict(lemma="být", upos="AUX", xpos="VpYS----R-AAI--",
               feats={"Aspect": "Imp", "Gender": "Masc", "Number": "Sing",
                      "Polarity": "Pos", "Tense": "Past",
                      "VerbForm": "Part", "Voice": "Act"})
    return Veta("byl a byl", (
        Token(id=1, form="byl", head=2, deprel="aux", deps=None, misc=None,
              **byl),
        Token(id=2, form="byl", head=0, deprel="root", deps=None, misc=None,
              **byl)))


if __name__ == "__main__":
    unittest.main()
