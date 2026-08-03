"""Doménová logika: čtyři fáze rozboru.

Testy nepotřebují běžící UDPipe — upstream se podstrčí. To je smysl rozdělení
na `service.py` a `api.py`: logika se testuje přímo, bez spuštěné služby
(README-MODULES.md § 1).
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_udpipe import conllu, config, service, upstream
from cb_udpipe.tests.fake_upstream import FakeUpstream, RozbityLog

TS = "2026-08-03T10:00:00.000Z"


class ZakladSluzby(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def sluzba(self, *, upstream_klient=None, log=None, log_objects="miss",
               batch=60):
        """Postaví službu s dočasnou cache a podstrčeným upstreamem."""
        cfg = json.loads(
            config.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        )
        cfg["module"]["cache"]["dir"] = str(self.dir / "cache")
        cfg["module"]["cache"]["batch_sentences"] = batch
        cfg["module"]["log_objects"] = log_objects
        cfg["_meta"] = {"path": "test", "fingerprint": "testtesttest"}
        s = service.UdpipeService(
            cfg,
            upstream=upstream_klient if upstream_klient is not None
            else FakeUpstream(),
            log=log,
            clock=lambda: TS,
        )
        self.addCleanup(s.close)
        return s


class TestCtyriFaze(ZakladSluzby):

    def test_prvni_pruchod_rozebere(self):
        s = self.sluzba()
        r = s.parse("Petr je v Praze.")
        self.assertEqual(len(r.sentences), 1)
        self.assertEqual((r.cached, r.parsed), (0, 1))
        self.assertFalse(r.sentences[0].from_cache)

    def test_druhy_pruchod_bere_z_cache(self):
        """Cache zásah znamená, že se dorozbor nezavolá vůbec — to je celý
        důvod, proč modul existuje jako služba (§ 1 koncepce)."""
        u = FakeUpstream()
        s = self.sluzba(upstream_klient=u)
        s.parse("Petr je v Praze.")
        u.reset()
        r = s.parse("Petr je v Praze.")
        self.assertEqual((r.cached, r.parsed), (1, 0))
        self.assertEqual(u.pocet_tag_and_parse, 0)
        self.assertTrue(r.sentences[0].from_cache)

    def test_tokenizace_probehne_i_pri_zasahu(self):
        """Segmentaci dělá UDPipe, takže se nedá přeskočit: bez ní není
        známo, na které věty se cache ptát (§ 2 koncepce)."""
        u = FakeUpstream()
        s = self.sluzba(upstream_klient=u)
        s.parse("Petr je v Praze.")
        u.reset()
        s.parse("Petr je v Praze.")
        self.assertEqual(u.pocet_tokenize, 1)

    def test_smiseny_vstup(self):
        """Věta z cache a věta k rozboru v jednom vstupu; jedním voláním
        jdou jen ty chybějící."""
        u = FakeUpstream()
        s = self.sluzba(upstream_klient=u)
        s.parse("Petr je v Praze.")
        u.reset()
        r = s.parse("Petr je v Praze. Jan je v Brně.")
        self.assertEqual((r.cached, r.parsed), (1, 1))
        self.assertEqual(u.pocet_tag_and_parse, 1)

    def test_poradi_vet_odpovida_vstupu(self):
        """Věty se vracejí v pořadí vstupu, i když část přišla z cache
        a část z dorozboru. Bez toho by se rozešly s tím, co volající poslal."""
        s = self.sluzba()
        s.parse("Druhá věta je tady.")
        r = s.parse("První věta je tu. Druhá věta je tady. Třetí věta také.")
        self.assertEqual(
            [v.source for v in r.sentences],
            ["První věta je tu.", "Druhá věta je tady.", "Třetí věta také."],
        )

    def test_davkovani(self):
        """Dorozbor jde po dávkách: jedno volání na celý článek je pro UDPipe
        moc a jedno na větu zbytečně pomalé (conBond2)."""
        u = FakeUpstream()
        s = self.sluzba(upstream_klient=u, batch=2)
        s.parse("A je tu. B je tu. C je tu. D je tu. E je tu.")
        self.assertEqual(u.pocet_tag_and_parse, 3)      # 2 + 2 + 1


class TestOpravaTokenizace(ZakladSluzby):

    def test_zkratka_se_sceli(self):
        """Kvůli tomuhle modul existuje (§ 1 koncepce)."""
        s = self.sluzba()
        r = s.parse("R.U.R. je drama.")
        self.assertIn("R.U.R.", [t.form for t in r.sentences[0].tokens])
        self.assertEqual(r.sentences[0].retokenized, 1)

    def test_ciselna_skupina_se_sceli(self):
        s = self.sluzba()
        r = s.parse("V úlu je 30 000 dělnic.")
        self.assertIn("30 000", [t.form for t in r.sentences[0].tokens])

    def test_veta_bez_vady_ma_nula_zasahu(self):
        s = self.sluzba()
        r = s.parse("Petr je v Praze.")
        self.assertEqual(r.sentences[0].retokenized, 0)

    def test_do_cache_jde_opravena_tokenizace(self):
        """Kdyby se ukládala neopravená, byla by cache k ničemu: každý
        průchod by musel opravovat znovu a klíč by neseděl na verzi
        tokenizéru."""
        s = self.sluzba()
        s.parse("R.U.R. je drama.")
        z_cache = s.cache.get("R.U.R. je drama.")
        self.assertIn("R.U.R.", [t.form for t in z_cache.tokens])


class TestPrazdnoAPreskoceni(ZakladSluzby):

    def test_prazdny_vstup(self):
        """T-K2: prázdno není chyba a není to výmysl."""
        s = self.sluzba()
        r = s.parse("")
        self.assertEqual(r.sentences, ())
        self.assertEqual(s.summary()["parse"]["empty"], 1)

    def test_vstup_ze_samych_mezer(self):
        s = self.sluzba()
        r = s.parse("   \n  ")
        self.assertEqual(r.sentences, ())

    def test_dlouha_veta_se_preskoci_s_duvodem(self):
        """Mez serveru je 1000 slov. Přeskočená věta musí být ve stopě vidět
        jako přeskočená s důvodem, ne jako tichá díra."""
        s = self.sluzba(upstream_klient=FakeUpstream(dlouha_veta=True))
        r = s.parse("Tohle bude moc dlouhé.")
        self.assertEqual(len(r.skipped), 1)
        self.assertEqual(r.skipped[0]["reason"], "sentence_too_long")
        self.assertEqual(s.summary()["parse"]["skipped"], 1)

    def test_dlouha_veta_nezahodi_zbytek_davky(self):
        """Věta přes mez se vyjme PŘED odesláním. Kdyby šla s dávkou, server
        by vrátil chybu na celou dávku kvůli jedné větě."""
        s = self.sluzba(upstream_klient=_JednaDlouha())
        r = s.parse("Krátká věta je tu. Dlouhá věta je tu.")
        self.assertEqual(len(r.sentences), 1)
        self.assertEqual(len(r.skipped), 1)


class TestChyby(ZakladSluzby):

    def test_nedostupny_upstream_probubla(self):
        """Povinná závislost → typovaná chyba, nikdy prázdný výsledek
        (§ 9 politiky)."""
        s = self.sluzba(upstream_klient=FakeUpstream(nedostupny=True))
        with self.assertRaises(upstream.UpstreamUnavailable):
            s.parse("Petr je v Praze.")

    def test_chyba_se_zapise_do_souhrnu(self):
        """Tichá chyba je nejhorší druh chyby, protože měření ji ukáže jako
        úspěch (§ 9 politiky)."""
        s = self.sluzba(upstream_klient=FakeUpstream(nedostupny=True))
        with self.assertRaises(upstream.UpstreamUnavailable):
            s.parse("Petr je v Praze.")
        self.assertEqual(s.summary()["parse"]["error"], 1)

    def test_rozbite_logovatko_neshodi_modul(self):
        """Nepovinná závislost při výpadku znamená degradaci, ne pád."""
        s = self.sluzba(log=RozbityLog())
        self.assertEqual(len(s.parse("Petr je v Praze.").sentences), 1)


class TestSouhrnAZdravi(ZakladSluzby):

    def test_summary_pocita_podle_metody_a_stavu(self):
        s = self.sluzba()
        s.parse("Petr je v Praze.")
        self.assertEqual(s.summary()["parse"]["ok"], 1)

    def test_summary_nese_cache(self):
        s = self.sluzba()
        s.parse("Petr je v Praze.")
        self.assertEqual(s.summary()["cache"]["sentences"], 1)

    def test_health_hlasi_dostupny_upstream(self):
        s = self.sluzba()
        h = s.health()
        self.assertTrue(h["upstream"]["available"])
        self.assertEqual(h["status"], "ok")

    def test_health_hlasi_nedostupny_upstream(self):
        """UDPipe je povinná závislost — bez něj je služba degradovaná
        a musí to být vidět (§ 9 politiky)."""
        s = self.sluzba(upstream_klient=FakeUpstream(nedostupny=True))
        h = s.health()
        self.assertFalse(h["upstream"]["available"])
        self.assertEqual(h["status"], "degraded")

    def test_health_nese_verzi_tokenizeru(self):
        """Bez ní se nedají porovnat dva běhy (§ 11 politiky)."""
        s = self.sluzba()
        self.assertEqual(len(s.health()["tokenizer"]), 12)


class TestTokenizeOnly(ZakladSluzby):

    def test_vraci_vety_s_opravenou_tokenizaci(self):
        s = self.sluzba()
        vety = s.tokenize_only("R.U.R. je drama.")
        self.assertIn("R.U.R.", [t.form for t in vety[0].tokens])

    def test_nesaha_na_cache(self):
        """Tokenizace bez tagů není rozbor a do cache nepatří — jinak by se
        do ní dostaly věty bez značek a příští zásah by vrátil prázdno."""
        s = self.sluzba()
        s.tokenize_only("Petr je v Praze.")
        self.assertEqual(s.cache.stats()["sentences"], 0)


class _JednaDlouha(FakeUpstream):
    """Upstream, kde mez překročí jen druhá věta.

    Ověřuje, že se přes mez vyjme jen ta jedna a zbytek dávky projde.
    """

    def tokenize(self, text, *, trace=None):
        vety = conllu.parse(super().tokenize(text, trace=trace))
        upravene = []
        for poradi, v in enumerate(vety):
            if poradi == 1:
                nafouknute = tuple(
                    conllu.Token(id=i + 1, form=t.form, misc=t.misc)
                    for i, t in enumerate(v.tokens * 300)
                )
                v = conllu.Sentence(source=v.source, tokens=nafouknute,
                                    sent_id=v.sent_id)
            upravene.append(v)
        return conllu.write(upravene)


if __name__ == "__main__":
    unittest.main()
