"""Testy fasády `BondService` — hlavně toho, co o sobě umí říct.

`state()` je jediný zdroj čísel pro `status`, viewBase i log. Kdyby si je
každé místo počítalo samo, rozešla by se — a rozdíl by nikdo nehledal
v tom, že se měří dvakrát jinak.

Test nesmí potřebovat běžící službu (§ 13), takže rozbory jdou ze
zmražených vzorků a parser je atrapa.
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_bond.service import BondService
from cb_bond.tests.vzorky import GRAVITACE, KRESTA, OTAZKA_KREST


class _Parser:
    """Atrapa parseru: zná zmražené věty podle textu."""

    def __init__(self, vety):
        self.vety = {v.source: v for v in vety}
        self.calls = 0

    def parse(self, text):
        self.calls += 1
        veta = self.vety[text]

        class _Result:
            sentences = (veta,)
        return _Result()


class _Graf:
    """Atrapa grafu se zadanými uzly — na aritmetiku `state()`.

    Postavit skutečný homograf ze zmražených vzorků nejde: musely by
    v nich být `NOUN:vedení` i `VERB:vedení`. Rozdíl lemmat a uzlů je
    přitom aritmetika `state()`, ne grafu, takže se dá měřit tady.
    """

    def __init__(self, uzly: dict, hran: int) -> None:
        self._uzly = uzly
        self._hran = hran

    def statistics(self) -> dict:
        return self._uzly

    def edges(self) -> tuple:
        return tuple(range(self._hran))


def _config(adresar: Path, vety) -> dict:
    """Konfigurace ukazující na dočasný korpus se zadanými větami."""
    korpus = adresar / "corpus"
    korpus.mkdir(exist_ok=True)
    (korpus / "korpus-101.json").write_text(
        json.dumps({"format_version": 1, "language": "cs", "questions": [],
                    "blocks": [{"topic": "test", "text": v.source,
                                "sentences": [v.source]}
                               for v in vety]}, ensure_ascii=False),
        encoding="utf-8")
    return {
        "module": {
            "data_root": str(adresar),
            "corpus": {"directory": str(korpus),
                       "patterns": ["korpus-1*.json"],
                       "question_patterns": ["otazky-*.json"],
                       "radius": 1, "sentence_radius": 0},
            # Tytéž páky jako v provozu. Jiné hodnoty by znamenaly, že
            # testy měří něco jiného, než co běží.
            "matching": {"spread_depth": 1, "top_k": 50, "theta": 0.0,
                         "epsilon": 0.0, "graph_recall_depth": 2,
                         "spectral_k": 0, "top_sentences": 5,
                         "weights": {"center": 2.0, "cover": 1.0,
                                     "topic": 1.0, "given": -3.0,
                                     "fit": 0.0, "spectral": 0.0}},
            "reading": {"sigma": 1.5},
        },
        "_meta": {"fingerprint": "abcdef123456",
                  "path": str(adresar / "cb-bond-config.json")},
    }


class Zaklad(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.vety = (KRESTA, GRAVITACE)
        self.service = BondService(_config(self.tmp, self.vety),
                                   _Parser(self.vety), verbose=False)


class TestStavPredStavbou(Zaklad):
    """Nepostavená služba čísla nevymýšlí."""

    def test_state_rekne_ze_NENI_postaveno(self):
        stav = self.service.state()

        self.assertFalse(stav["built"])
        self.assertIsNone(stav["sentences"])
        self.assertIsNone(stav["edges"])

    def test_state_zna_cesty_i_bez_stavby(self):
        # `status` na neběžící službu musí říct, co by stavěl — jinak
        # člověk nepozná, že míří do prázdna
        stav = self.service.state()

        self.assertEqual(Path(stav["corpus_dir"]), self.tmp / "corpus")
        self.assertEqual(stav["config_fingerprint"], "abcdef123456")


class _Log:
    """Atrapa logovátka se SKUTEČNÝM podpisem `LogClient.info`.

    Atrapa, která bere cokoli, by tenhle test proměnila v ozdobu: první
    verze `_oznam` volala `log.info(zprava, source=…)`, což skutečný
    klient neumí — a protože se chyba polykala, běžela služba bez logu
    a nikdo si toho nevšiml.
    """

    def __init__(self):
        self.zaznamy = []
        self.postup = []

    def info(self, *, method, result, message=None, **_):
        self.zaznamy.append((method, result, message))

    def debug(self, *, method, result, message=None, **_):
        self.postup.append((method, result, message))


class TestLogovani(unittest.TestCase):
    """Nové služby a metody visí na centrálním loggeru (rozhodnutí J.)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.vety = (KRESTA, GRAVITACE)
        self.log = _Log()
        self.service = BondService(_config(self.tmp, self.vety),
                                   _Parser(self.vety), log=self.log,
                                   verbose=False)

    def test_stavba_se_zapise_do_loggeru(self):
        self.service.build()

        metody = [m for m, _, _ in self.log.zaznamy]
        self.assertIn("build", metody)

    def test_zaznam_nese_VYSLEDEK_ne_jen_hlasku(self):
        # souhrn se počítá podle komponenta × metoda × result; hláška
        # v `method` by z každé zprávy udělala vlastní řádek a čísla by
        # ztratila smysl
        self.service.build()

        for metoda, vysledek, _ in self.log.zaznamy:
            self.assertIn(vysledek, ("ok", "empty", "error", "skipped"))
            self.assertNotIn(" ", metoda)

    def test_zaznam_o_stavbe_nese_CISLA(self):
        self.service.build()

        zaznam = [z for z in self.log.zaznamy if z[0] == "build"][0]
        self.assertIn("2 vět", zaznam[2] or "")

    def test_prubezna_hlaska_jde_na_DEBUG_ne_info(self):
        # `info` je hranice komponenty (metoda doběhla). Kdyby tam šel
        # i začátek práce, souhrn by jednu stavbu počítal dvakrát.
        self.service.build()

        self.assertEqual(len(self.log.zaznamy), 1)
        self.assertTrue(self.log.postup)


class TestZdravi(Zaklad):
    """`health()` musí rozlišit „běžím" od „umím odpovídat"."""

    def test_nepostavena_sluzba_NENI_ok(self):
        # port odpovídá, ale v hlavě nic není — kdyby to bylo „ok",
        # poznalo by se to až prvním dotazem, daleko od příčiny
        zdravi = self.service.health()

        self.assertEqual(zdravi["status"], "degraded")
        self.assertFalse(zdravi["built"])

    def test_postavena_sluzba_je_ok_a_nese_cisla(self):
        self.service.build()
        zdravi = self.service.health()

        self.assertEqual(zdravi["status"], "ok")
        self.assertEqual(zdravi["sentences"], 2)


class TestDotaz(Zaklad):
    """`ask()` je to, kvůli čemu systém je.

    Odpověď musí nést i **proč** — rozklad skóre a kandidátní věty.
    Bez toho by člověk viděl výsledek a neměl jak poznat, čím vznikl
    (princip 6: vidět dovnitř bez čtení kódu).
    """

    def setUp(self):
        super().setUp()
        self.vety = (KRESTA, GRAVITACE, OTAZKA_KREST)
        self.service = BondService(_config(self.tmp, (KRESTA, GRAVITACE)),
                                   _Parser(self.vety), verbose=False)
        self.service.build()

    def test_odpoved_nese_lemma_i_vychodisko(self):
        odpoved = self.service.ask(OTAZKA_KREST.source)

        self.assertIn("answer", odpoved)
        self.assertIn(odpoved["outcome"],
                      ("answer", "silent", "needs_context"))

    def test_odpoved_nese_ROZKLAD_skore(self):
        # požadavek J.: „ask přes REST vrací rozklad score"
        odpoved = self.service.ask(OTAZKA_KREST.source)

        rozklad = odpoved["decomposition"]
        self.assertTrue(rozklad)
        # součet členů musí dát skóre — jinak rozklad není rozklad,
        # ale komentář vedle čísla
        self.assertAlmostEqual(sum(rozklad.values()), odpoved["score"],
                               places=5)

    def test_odpoved_nese_KANDIDATNI_vety_s_kandidatnim_slovem(self):
        # konvence viewBase2: „[slovo] Věta"
        odpoved = self.service.ask(OTAZKA_KREST.source)

        self.assertTrue(odpoved["sentences"])
        prvni = odpoved["sentences"][0]
        self.assertIn("lemma", prvni)
        self.assertIn("text", prvni)
        self.assertIn("position", prvni)

    def test_pocet_vet_se_da_omezit(self):
        odpoved = self.service.ask(OTAZKA_KREST.source, top=1)

        self.assertLessEqual(len(odpoved["sentences"]), 1)

    def test_odpoved_nese_OSY_otazky_i_jejich_pokryti(self):
        # okno vertikál: co se použilo a jak dobře to korpus zná
        odpoved = self.service.ask(OTAZKA_KREST.source)

        self.assertTrue(odpoved["axes"])
        for osa in odpoved["axes"]:
            self.assertIn("axis", osa)
            self.assertIn("coverage", osa)

    def test_mezera_je_videt_jako_PRESNA_nula(self):
        # „nevím" se pozná podle nuly, ne podle prahu na malém čísle
        odpoved = self.service.ask(OTAZKA_KREST.source)

        nulove = [o["axis"] for o in odpoved["axes"]
                  if o["coverage"] == 0.0]
        self.assertEqual(nulove, odpoved["missing"])

    def test_odpoved_je_cela_JSONovatelna(self):
        json.dumps(self.service.ask(OTAZKA_KREST.source))

    def test_context_prida_vetu_do_KORPUSU_i_grafu(self):
        # žádná zvláštní cesta pro dialogová data: týž registr, týž graf,
        # liší se jen zdroj hrany
        pred = self.service.state()

        stav = self.service.context(GRAVITACE.source)

        self.assertEqual(stav["sentences"], pred["sentences"] + 1)
        self.assertGreater(stav["edges"], pred["edges"])

    def test_context_vraci_PRIRUSTEK_ne_jen_celek(self):
        # dialog o dálnici se popisuje jako „+9 hran"; kdyby se hlásil
        # celek se znaménkem plus, znamenalo by to něco úplně jiného
        pred = self.service.state()

        stav = self.service.context(GRAVITACE.source)

        self.assertEqual(stav["added_sentences"], 1)
        self.assertEqual(stav["added_edges"], stav["edges"] - pred["edges"])
        self.assertGreater(stav["added_edges"], 0)

    def test_context_ZNEPLATNI_parovac(self):
        # bez toho by párovač počítal nad starými pytli a nová věta by
        # v odpovědi nebyla vidět — vypadá to jako chyba párování
        self.service.ask(OTAZKA_KREST.source)
        stary = self.service.matcher()

        self.service.context(GRAVITACE.source)

        self.assertIsNot(self.service.matcher(), stary)

    def test_dotaz_na_NEPOSTAVENOU_sluzbu_je_hlasita_chyba(self):
        prazdna = BondService(_config(self.tmp, (KRESTA,)),
                              _Parser(self.vety), verbose=False)

        with self.assertRaises(RuntimeError) as chyba:
            prazdna.ask(OTAZKA_KREST.source)
        self.assertIn("postaven", str(chyba.exception))

    def test_resolve_reference_bez_logiky_je_chyba(self):
        # rozřešit referenci do neexistující vrstvy by bylo tiché
        # nedorozumění — táž zásada jako u teach_pattern
        with self.assertRaises(RuntimeError):
            self.service.resolve_reference("class")


class TestStavPoStavbe(Zaklad):
    """Čísla, která uvidí člověk ve `status`."""

    def setUp(self):
        super().setUp()
        self.service.build()

    def test_pocty_vet_a_souboru(self):
        stav = self.service.state()

        self.assertTrue(stav["built"])
        self.assertEqual(stav["sentences"], 2)
        self.assertEqual(stav["files"], 1)

    def test_graf_uvadi_hrany_lemmata_a_stupen(self):
        stav = self.service.state()

        # zemní pravda: obě zmražené věty dohromady
        self.assertGreater(stav["edges"], 0)
        self.assertGreater(stav["lemmas"], 0)
        # tentýž vzorec jako přejímka § 6 — každá hrana se dotýká DVOU
        # uzlů; jiný vzorec by dal jiné číslo pro totéž a nikdo by
        # nehledal příčinu v tom, že se měří dvakrát jinak
        self.assertAlmostEqual(stav["degree"],
                               round(2 * stav["edges"] / stav["lemmas"], 1),
                               places=1)

    def test_lemmata_a_uzly_jsou_DVE_RUZNA_cisla(self):
        # `NOUN:vedení` a `VERB:vedení` jsou dva uzly, ale jedno lemma.
        # Přejímka § 6 zmrazila 5 695 LEMMAT; kdyby `state()` vracel uzly,
        # ukazoval by 5 727 pod tímtéž jménem a rozdíl by nikdo nehledal.
        self.service.graph = _Graf({"NOUN:vedení": 3, "VERB:vedení": 2,
                                    "NOUN:silnice": 4}, hran=9)
        stav = self.service.state()

        self.assertEqual(stav["lemmas"], 2)      # vedení, silnice
        self.assertEqual(stav["nodes"], 3)
        self.assertAlmostEqual(stav["degree"], 9.0)   # 2 * 9 / 2

    def test_osy_uvadi_pocet_i_VERZI(self):
        # verze osy je to, čím se pozná, že načtený registr sedí s pamětí
        stav = self.service.state()

        self.assertGreater(stav["axes"], 0)
        self.assertEqual(stav["custom_axes"], 0)   # bez promoce
        self.assertIsInstance(stav["axis_version"], int)

    def test_vazby_uvadi_pocet_i_verzi(self):
        stav = self.service.state()

        self.assertGreaterEqual(stav["links"], 0)
        self.assertIsInstance(stav["link_version"], int)

    def test_state_je_cely_JSONovatelny(self):
        # totéž, co jde do REST odpovědi a do logu; objekt modulu by tam
        # spadl až u klienta, tedy daleko od příčiny
        json.dumps(self.service.state())

    def test_build_vraci_TATAZ_cisla_jako_state(self):
        # dvě cesty ke stejnému číslu se rozejdou; tady je jedna
        otisk = self.service.build()
        stav = self.service.state()

        for klic in ("sentences", "edges", "lemmas", "axes"):
            self.assertEqual(otisk[klic], stav[klic], klic)


if __name__ == "__main__":
    unittest.main()
