"""REST kontrakt.

`api.py` nesmí obsahovat **jediné rozhodnutí o doméně** (README-MODULES.md § 1):
rozbalí požadavek, zavolá `service`, zabalí odpověď. Testy proto ověřují tvar
odpovědi a návratové kódy, ne obsah rozboru — ten se testuje ve `test_service`.
"""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from cb_udpipe import api, config, service
from cb_udpipe.tests.fake_upstream import FakeUpstream


class ZakladApi(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cfg = json.loads(
            config.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        )
        self.cfg["module"]["cache"]["dir"] = str(Path(self._tmp.name) / "cache")
        self.cfg["service"]["port"] = 0          # port přidělí systém
        self.cfg["_meta"] = {"path": "test", "fingerprint": "testtesttest"}
        self.upstream = FakeUpstream()
        self.service = service.UdpipeService(
            self.cfg, upstream=self.upstream, clock=lambda: "TS"
        )
        self.addCleanup(self.service.close)

        self.server = api.make_api_server(self.service, config=self.cfg)
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def get(self, cesta):
        return self._volej("GET", cesta)[1]

    def post(self, cesta, telo):
        return self._volej("POST", cesta, telo)[1]

    def _volej(self, metoda, cesta, telo=None):
        data = json.dumps(telo).encode("utf-8") if telo is not None else None
        req = urllib.request.Request(
            self.url + cesta, data=data, method=metoda,
            headers={"Content-Type": "application/json"} if data else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))


class TestPovinneBody(ZakladApi):

    def test_version_stoji_mimo_v1(self):
        """Kdo se ptá na verzi, ještě neví, kterou verzi rozhraní má volat.
        Kdyby /version žilo pod /v1/, klient by musel znát verzi, aby zjistil
        verzi (§ 7 politiky)."""
        r = self.get("/version")
        self.assertEqual(r["module"], "cb-udpipe")
        self.assertEqual(r["api"], ["v1"])
        self.assertIn("version", r)
        self.assertIn("python", r)

    def test_version_nese_verzi_tokenizeru(self):
        """Verze tokenizéru je součástí klíče cache — bez ní nejde poznat,
        čím rozbor vznikl (§ 4 koncepce)."""
        self.assertEqual(len(self.get("/version")["tokenizer"]), 12)

    def test_health(self):
        r = self.get("/v1/health")
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["upstream"]["available"])

    def test_config_nese_pouzitou_cestu(self):
        """Jinak nikdo nezjistí, které nastavení vlastně běží."""
        r = self.get("/v1/config")
        self.assertIn("path", r)
        self.assertIn("config", r)

    def test_summary(self):
        self.post("/v1/parse", {"text": "Petr je v Praze."})
        r = self.get("/v1/summary")
        self.assertEqual(r["parse"]["ok"], 1)

    def test_cache_stats(self):
        self.post("/v1/parse", {"text": "Petr je v Praze."})
        r = self.get("/v1/cache/stats")
        self.assertEqual(r["sentences"], 1)
        self.assertEqual(r["corrupt"], 0)


class TestParse(ZakladApi):

    def test_vraci_vety_s_tokeny(self):
        r = self.post("/v1/parse", {"text": "R.U.R. je drama."})
        formy = [t["form"] for t in r["sentences"][0]["tokens"]]
        self.assertIn("R.U.R.", formy)

    def test_vraci_pocty(self):
        r = self.post("/v1/parse", {"text": "Petr je v Praze."})
        self.assertEqual(r["cached"], 0)
        self.assertEqual(r["parsed"], 1)

    def test_from_cache_je_videt(self):
        """Bez toho by nešlo změřit podíl zásahů jinak než dopočítáváním
        ze souhrnu (§ 8 koncepce)."""
        self.post("/v1/parse", {"text": "Petr je v Praze."})
        r = self.post("/v1/parse", {"text": "Petr je v Praze."})
        self.assertTrue(r["sentences"][0]["from_cache"])

    def test_tokenize_vraci_vety_bez_tagu(self):
        r = self.post("/v1/tokenize", {"text": "R.U.R. je drama."})
        self.assertIn("R.U.R.",
                      [t["form"] for t in r["sentences"][0]["tokens"]])

    def test_stopa_se_prebira_z_tela(self):
        """Stopa prochází sítí v těle požadavku, ne v hlavičce — hlavička se
        po cestě ztratí (§ 7 politiky)."""
        r = self.post("/v1/parse",
                      {"text": "Petr je v Praze.", "trace": "q-7f3a91"})
        self.assertEqual(r["trace"], "q-7f3a91")


class TestChybovyKontrakt(ZakladApi):

    def test_prazdny_vstup_je_200_ne_404(self):
        """Prázdný výsledek není chyba: vrací se 200 s prázdným obsahem
        a příznakem, ne 404 a ne 500 (§ 7 politiky)."""
        status, telo = self._volej("POST", "/v1/parse", {"text": ""})
        self.assertEqual(status, 200)
        self.assertEqual(telo["sentences"], [])

    def test_chybejici_klic_je_400_s_typem(self):
        """Chyba má typ, ne jen text — jinak si volající musí pamatovat,
        že má kontrolovat klíč `error` (§ 7 politiky)."""
        status, telo = self._volej("POST", "/v1/parse", {"txt": "A"})
        self.assertEqual(status, 400)
        self.assertEqual(telo["error"]["type"], "invalid_request")

    def test_spatny_typ_je_400(self):
        status, telo = self._volej("POST", "/v1/parse", {"text": 42})
        self.assertEqual(status, 400)

    def test_telo_neni_json_objekt_je_400(self):
        """Vstup i výstup je vždy JSON objekt, ne pole ani skalár: do objektu
        jde přidat klíč, aniž se rozbijí stávající klienti."""
        req = urllib.request.Request(
            self.url + "/v1/parse", data=b"[1,2,3]", method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(e.exception.code, 400)

    def test_neznama_cesta_je_404(self):
        status, telo = self._volej("GET", "/v1/neexistuje")
        self.assertEqual(status, 404)
        self.assertIn("type", telo["error"])

    def test_prilis_velke_telo_je_413(self):
        """Limity jsou součástí kontraktu, ne překvapení (§ 7 politiky)."""
        status, _ = self._volej(
            "POST", "/v1/parse", {"text": "x" * 3_000_000}
        )
        self.assertEqual(status, 413)

    def test_nedostupny_upstream_je_503_a_rekne_ktery(self):
        """Povinná závislost při výpadku znamená typovanou chybu s uvedením,
        která to je — nikdy prázdnou odpověď (§ 9 politiky)."""
        self.upstream.nedostupny = True
        status, telo = self._volej("POST", "/v1/parse", {"text": "A"})
        self.assertEqual(status, 503)
        self.assertEqual(telo["error"]["type"], "upstream_unavailable")
        self.assertIn("cb-udpipe", telo["error"]["message"])

    def test_health_pri_vypadku_hlasi_degraded(self):
        self.upstream.nedostupny = True
        self.assertEqual(self.get("/v1/health")["status"], "degraded")


class TestVlastnostiOdpovedi(ZakladApi):

    def test_vystup_je_vzdy_objekt(self):
        for cesta in ("/version", "/v1/health", "/v1/config", "/v1/summary"):
            self.assertIsInstance(self.get(cesta), dict, cesta)

    def test_determinismus(self):
        """Táž data a týž požadavek dají tytéž tokeny ve stejném pořadí.
        Bez toho se nedá měřit (§ 7 politiky).

        Porovnávají se **tokeny**, ne celé věty: `from_cache` se mezi
        průchody liší schválně a je to informace o cestě, ne o výsledku.
        Kdyby se lišily tokeny, znamenalo by to, že cache vrací něco jiného
        než čerstvý rozbor — a to je chyba klíče (§ 13 koncepce)."""
        telo = {"text": "Petr je v Praze. Jan je v Brně."}
        prvni = self.post("/v1/parse", telo)
        druhy = self.post("/v1/parse", telo)
        self.assertEqual([v["tokens"] for v in prvni["sentences"]],
                         [v["tokens"] for v in druhy["sentences"]])
        self.assertEqual([v["source"] for v in prvni["sentences"]],
                         [v["source"] for v in druhy["sentences"]])

    def test_cache_vraci_totez_co_cerstvy_rozbor(self):
        """Protiváha k podílu zásahů: ten jde nafouknout volnějším klíčem.
        Rozdíl mezi cache a čerstvým rozborem je chyba klíče, ne remíza."""
        telo = {"text": "R.U.R. je drama."}
        cerstvy = self.post("/v1/parse", telo)
        self.assertFalse(cerstvy["sentences"][0]["from_cache"])
        z_cache = self.post("/v1/parse", telo)
        self.assertTrue(z_cache["sentences"][0]["from_cache"])
        self.assertEqual(cerstvy["sentences"][0]["tokens"],
                         z_cache["sentences"][0]["tokens"])

    def test_odpoved_je_serializovatelna_bez_ztraty(self):
        """Totéž JSON, jaké vrací knihovna v procesu (§ 7 politiky)."""
        r = self.post("/v1/parse", {"text": "Petr je v Praze."})
        self.assertEqual(json.loads(json.dumps(r)), r)


if __name__ == "__main__":
    unittest.main()
