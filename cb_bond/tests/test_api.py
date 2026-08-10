"""Testy REST vrstvy cb-bondu.

Rozhraní se testuje přes skutečný HTTP server na portu 0 (přidělí systém),
ne přes volání obslužné funkce: půlka toho, co se tady může pokazit, je
v hlavičkách, kódech a JSONu, a to volání metody neuvidí.
"""

import json
import threading
import unittest
import urllib.error
import urllib.request

from cb_bond.api import make_api_server
from cb_bond.tests.test_service import _config, _Parser
from cb_bond.tests.vzorky import GRAVITACE, KRESTA, OTAZKA_KREST

import tempfile
from pathlib import Path

from cb_bond.service import BondService


class Zaklad(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        vety = (KRESTA, GRAVITACE, OTAZKA_KREST)
        config = _config(tmp, (KRESTA, GRAVITACE))
        config["service"] = {"host": "127.0.0.1", "port": 0,
                             "view_port": 0}
        self.service = BondService(config, _Parser(vety), verbose=False)
        self.server = make_api_server(self.service, config=config, port=0)
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever,
                         daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.adresa = f"http://127.0.0.1:{self.server.server_address[1]}"

    def get(self, cesta: str):
        with urllib.request.urlopen(self.adresa + cesta, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))


class TestVerze(Zaklad):

    def test_version_odpovida_i_NEPOSTAVENE_sluzbe(self):
        # `control.py` se ptá na /version jako první po startu, ještě
        # než je co odpovídat — nesmí to na ničem záviset (§ 7)
        kod, telo = self.get("/version")

        self.assertEqual(kod, 200)
        self.assertEqual(telo["module"], "cb-bond")
        self.assertIn("v1", telo["api"])


class TestZdravi(Zaklad):

    def test_nepostavena_sluzba_je_degraded(self):
        _, telo = self.get("/v1/health")

        self.assertEqual(telo["status"], "degraded")
        self.assertFalse(telo["built"])

    def test_postavena_sluzba_je_ok(self):
        self.service.build()

        _, telo = self.get("/v1/health")

        self.assertEqual(telo["status"], "ok")


class TestStav(Zaklad):
    """`/v1/state` je zdroj čísel pro `status` — jinde se nepočítají."""

    def test_state_nese_statistiky_grafu(self):
        self.service.build()

        kod, telo = self.get("/v1/state")

        self.assertEqual(kod, 200)
        self.assertEqual(telo["sentences"], 2)
        self.assertGreater(telo["edges"], 0)
        self.assertGreater(telo["lemmas"], 0)
        self.assertIn("degree", telo)

    def test_state_pred_stavbou_nevymysli_cisla(self):
        _, telo = self.get("/v1/state")

        self.assertFalse(telo["built"])
        self.assertIsNone(telo["edges"])


class TestDotaz(Zaklad):
    """`POST /v1/ask` — a s ním rozklad skóre (požadavek J.)."""

    def post(self, cesta: str, telo: dict):
        data = json.dumps(telo, ensure_ascii=False).encode("utf-8")
        pozadavek = urllib.request.Request(
            self.adresa + cesta, data=data, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(pozadavek, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def test_ask_vraci_odpoved_i_ROZKLAD(self):
        self.service.build()

        kod, telo = self.post("/v1/ask", {"text": OTAZKA_KREST.source})

        self.assertEqual(kod, 200)
        self.assertIn("answer", telo)
        self.assertIn("decomposition", telo)
        self.assertIn("sentences", telo)

    def test_ask_na_NEPOSTAVENOU_sluzbu_je_503_ne_prazdna_odpoved(self):
        # prázdná odpověď by se slila s platným „nevím" — a to jsou dvě
        # různé věci (§ 9)
        with self.assertRaises(urllib.error.HTTPError) as chyba:
            self.post("/v1/ask", {"text": OTAZKA_KREST.source})

        self.assertEqual(chyba.exception.code, 503)
        telo = json.loads(chyba.exception.read().decode("utf-8"))
        self.assertEqual(telo["error"]["type"], "not_built")

    def test_chybejici_text_je_400(self):
        self.service.build()

        with self.assertRaises(urllib.error.HTTPError) as chyba:
            self.post("/v1/ask", {"otazka": "překlep v klíči"})

        self.assertEqual(chyba.exception.code, 400)

    def test_top_se_da_zadat_v_pozadavku(self):
        self.service.build()

        _, telo = self.post("/v1/ask", {"text": OTAZKA_KREST.source,
                                        "top": 1})

        self.assertLessEqual(len(telo["sentences"]), 1)


class TestLogicResolve(Zaklad):
    """`POST /v1/logic/resolve` — dokončení doptání na referenci (§ 5)."""

    def post(self, cesta: str, telo: dict):
        data = json.dumps(telo, ensure_ascii=False).encode("utf-8")
        pozadavek = urllib.request.Request(
            self.adresa + cesta, data=data, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(pozadavek, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def test_spatna_volba_je_400(self):
        with self.assertRaises(urllib.error.HTTPError) as chyba:
            self.post("/v1/logic/resolve", {"choice": "cokoliv"})
        self.assertEqual(chyba.exception.code, 400)

    def test_bez_formalni_vrstvy_je_503(self):
        # fixtura nemá module.logic → služba to řekne typovaně, ne 500
        self.service.build()
        with self.assertRaises(urllib.error.HTTPError) as chyba:
            self.post("/v1/logic/resolve", {"choice": "class"})
        self.assertEqual(chyba.exception.code, 503)
        telo = json.loads(chyba.exception.read().decode("utf-8"))
        self.assertEqual(telo["error"]["type"], "not_built")


class TestNeznamaCesta(Zaklad):

    def test_neznama_cesta_je_404_s_JSON_chybou(self):
        # HTML chybová stránka by klienta rozbila na parsování, ne na
        # tom, co se skutečně stalo
        with self.assertRaises(urllib.error.HTTPError) as chyba:
            self.get("/v1/neexistuje")

        self.assertEqual(chyba.exception.code, 404)
        telo = json.loads(chyba.exception.read().decode("utf-8"))
        # tentýž tvar jako u sourozenců — klient rozumí jednomu kontraktu
        self.assertEqual(telo["error"]["type"], "not_found")


if __name__ == "__main__":
    unittest.main()
