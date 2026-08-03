"""Napojení na logovátko.

Textově na hranicích komponenty, objektově do kukátka na `:42102`. Čtyři stavy
se nikde neslévají — na tom stojí měření (README-MODULES.md § 6).
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_udpipe import config, service, upstream
from cb_udpipe.tests.fake_upstream import FakeLog, FakeUpstream, RozbityLog


class ZakladLogu(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.log = FakeLog()

    def sluzba(self, *, log=None, log_objects="miss", upstream_klient=None):
        cfg = json.loads(
            config.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        )
        cfg["module"]["cache"]["dir"] = str(Path(self._tmp.name) / "cache")
        cfg["module"]["log_objects"] = log_objects
        cfg["_meta"] = {"path": "test", "fingerprint": "testtesttest"}
        s = service.UdpipeService(
            cfg,
            upstream=upstream_klient if upstream_klient is not None
            else FakeUpstream(),
            log=self.log if log is None else log,
            clock=lambda: "TS",
        )
        self.addCleanup(s.close)
        return s

    def zaznamy(self, method):
        return [z for z in self.log.zaznamy if z.get("method") == method]


class TestCtyriStavy(ZakladLogu):
    """`empty` a `error` se **nesmí** slít. Věta, ze které nevznikl rozbor,
    protože v ní nebyl, je `empty`. Věta, ze které nevznikl, protože spadl
    parser, je `error`. Kdyby bylo obojí totéž, měření by odměnilo právě tu
    chybu, kterou má chytat (§ 6 politiky)."""

    def test_ok(self):
        self.sluzba().parse("Petr je v Praze.")
        self.assertEqual(self.zaznamy("parse")[0]["result"], "ok")

    def test_empty_pri_prazdnem_vstupu(self):
        self.sluzba().parse("")
        self.assertEqual(self.zaznamy("parse")[0]["result"], "empty")

    def test_error_pri_vypadku_upstreamu(self):
        s = self.sluzba(upstream_klient=FakeUpstream(nedostupny=True))
        with self.assertRaises(upstream.UpstreamUnavailable):
            s.parse("Petr je v Praze.")
        self.assertEqual(self.zaznamy("parse")[0]["result"], "error")

    def test_error_nese_duvod(self):
        """Každá zachycená výjimka končí záznamem s důvodem — tichá chyba je
        nejhorší druh chyby (§ 9 politiky)."""
        s = self.sluzba(upstream_klient=FakeUpstream(nedostupny=True))
        with self.assertRaises(upstream.UpstreamUnavailable):
            s.parse("Petr je v Praze.")
        self.assertIn("UDPipe", self.zaznamy("parse")[0]["message"])


class TestStopa(ZakladLogu):

    def test_prochazi_vsemi_zaznamy(self):
        """Bez společné stopy nejde z logu složit jeden průchod: do jednoho
        proudu zapisují všechny komponenty naráz a záznamy z různých otázek
        se prokládají (§ 6 politiky)."""
        self.sluzba().parse("R.U.R. je drama.", trace="q-7f3a91")
        self.assertTrue(self.log.zaznamy)
        for z in self.log.zaznamy:
            self.assertEqual(z["trace"], "q-7f3a91", z)

    def test_modul_stopu_nikdy_nerazi(self):
        """Kdyby si ji razil každý modul, rozpadl by se řetěz na tolik kusů,
        kolik je modulů — a to je horší než žádná stopa, protože to vypadá,
        že funguje (§ 6 politiky)."""
        self.sluzba().parse("Petr je v Praze.")
        for z in self.log.zaznamy:
            self.assertIsNone(z["trace"], z)


class TestObsahZaznamu(ZakladLogu):

    def test_vstup_je_shrnuti_ne_cely_text(self):
        """Log s celými korpusovými daty naroste tak, že se v něm nedá
        hledat — a dostane se do něj všechno, co bylo ve vstupu (§ 6, § 10
        politiky)."""
        self.sluzba().parse("Petr je v Praze a Jan je v Brně.")
        vstup = self.zaznamy("parse")[0]["input"]
        self.assertIn("chars", vstup)
        self.assertNotIn("Praze", json.dumps(vstup, ensure_ascii=False))

    def test_vystup_nese_pocty(self):
        self.sluzba().parse("Petr je v Praze.")
        vystup = self.zaznamy("parse")[0]["output"]
        self.assertEqual(vystup["cached"], 0)
        self.assertEqual(vystup["parsed"], 1)

    def test_doba_se_meri(self):
        """`duration_ms` živí metriku doby odpovědi (§ 6 politiky)."""
        self.sluzba().parse("Petr je v Praze.")
        self.assertIn("duration_ms", self.zaznamy("parse")[0])

    def test_retokenizace_ma_vlastni_zaznam(self):
        """Kolik oprav se udělalo, je vlastní metrika — kvůli ní modul
        vzniká (§ 1 koncepce)."""
        self.sluzba().parse("R.U.R. je drama.")
        z = self.zaznamy("retokenize")
        self.assertTrue(z)
        self.assertEqual(z[0]["output"]["merges"], 1)

    def test_bez_oprav_se_retokenize_neloguje(self):
        """Záznam o nule je šum: nejčastější případ je věta bez vady."""
        self.sluzba().parse("Petr je v Praze.")
        self.assertEqual(self.zaznamy("retokenize"), [])


class TestObjektoveLogovani(ZakladLogu):

    def test_miss_loguje_jen_nove(self):
        """Výchozí režim. Logovat cache zásah jako objekt znamená psát
        podruhé to, co už v cache leží (§ 10 koncepce)."""
        s = self.sluzba(log_objects="miss")
        s.parse("Petr je v Praze.")
        po_prvnim = len(self.log.objekty)
        s.parse("Petr je v Praze.")
        self.assertEqual(po_prvnim, 1)
        self.assertEqual(len(self.log.objekty), po_prvnim)

    def test_all_loguje_i_zasahy(self):
        s = self.sluzba(log_objects="all")
        s.parse("Petr je v Praze.")
        s.parse("Petr je v Praze.")
        self.assertEqual(len(self.log.objekty), 2)

    def test_off_neloguje_nic(self):
        s = self.sluzba(log_objects="off")
        s.parse("Petr je v Praze.")
        self.assertEqual(self.log.objekty, [])

    def test_retokenized_loguje_jen_zasahy_do_tokenizace(self):
        """Ladicí režim pravidel § 3: ukáže přesně věty, do kterých modul
        zasáhl, a nic jiného. Jediný režim, který jde nechat zapnutý na
        velkém korpusu."""
        s = self.sluzba(log_objects="retokenized")
        s.parse("Petr je v Praze.")
        self.assertEqual(self.log.objekty, [])
        s.parse("R.U.R. je drama.")
        self.assertEqual(len(self.log.objekty), 1)

    def test_objekt_nese_zdroj_a_tokeny(self):
        s = self.sluzba(log_objects="miss")
        s.parse("R.U.R. je drama.")
        obj = self.log.objekty[0]["obj"]
        self.assertEqual(obj["source"], "R.U.R. je drama.")
        self.assertEqual(obj["retokenized"], 1)
        self.assertIn("R.U.R.", [t["form"] for t in obj["tokens"]])

    def test_objekt_ma_label_a_kind(self):
        """Bez nich by šlo poznat jen komponentu a metodu, a to u modulu,
        který loguje víc struktur, nestačí."""
        s = self.sluzba(log_objects="miss")
        s.parse("Petr je v Praze.")
        self.assertEqual(self.log.objekty[0]["kind"], "parse")
        self.assertIn("rozbor", self.log.objekty[0]["label"])


class TestDegradace(ZakladLogu):

    def test_rozbite_logovatko_neshodi_modul(self):
        """Nepovinná závislost při výpadku znamená degradaci, ne pád. Kdyby
        padlé logovátko shodilo systém, byla by nejméně důležitá součást
        zároveň nejkřehčí (§ 9 politiky)."""
        s = self.sluzba(log=RozbityLog())
        r = s.parse("R.U.R. je drama.")
        self.assertEqual(len(r.sentences), 1)

    def test_bez_logovatka_funguje(self):
        s = self.sluzba(log=None)
        s.log = None
        self.assertEqual(len(s.parse("Petr je v Praze.").sentences), 1)


if __name__ == "__main__":
    unittest.main()
