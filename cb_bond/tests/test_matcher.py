"""Testy párování otázky s korpusem — Matcher, saturate, MatchResult.

Zmražené rozbory (vzorky.py), žádná běžící služba. Čísla, která jdou
spočítat ručně, se v testech počítají ručně: tanh(0,7) = 0,604 je váha
jednoho výskytu slovní osy, tanh(1,4) = 0,885 dvou.
"""

import math
import unittest

import numpy as np

from cb_bond import (Matcher, MatchResult, ScoreCandidate,
                     ScoreWeights, saturate)
from cb_bond.tests.vzorky import KRESTA, OTAZKA_KREST, SYNAGOGA
from cb_field import Corpus, SentenceField


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
        matcher = Matcher(corpus, spread_depth=1)
        otazka = _otazka(corpus)

        kandidat = matcher.match(otazka).candidates[0]
        pole = corpus[kandidat.sentence]
        kos = pole.baskets[kandidat.token]

        q = saturate(_vektor(corpus, otazka.complete), matcher.links, 1)
        okno = saturate(_vektor(corpus, kos.complete), matcher.links, 1)
        ocekavano = float(np.dot(q, okno) /
                          (np.linalg.norm(q) * np.linalg.norm(okno)))
        self.assertAlmostEqual(kandidat.decomposition()["meet"], ocekavano,
                               places=5)

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

    def test_top_k_vybere_vety_jednim_soucinem(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus)

        vety = matcher.recall(_otazka(corpus), top_k=1)

        self.assertEqual(len(vety), 1)
        self.assertEqual(vety[0], 0)          # křestní věta je bližší

    def test_jemne_cteni_bezi_jen_v_top_k(self):
        corpus = _korpus(KRESTA, SYNAGOGA)
        matcher = Matcher(corpus, top_k=1)

        vysledek = matcher.match(_otazka(corpus))

        self.assertEqual({k.sentence for k in vysledek.candidates}, {0})


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
