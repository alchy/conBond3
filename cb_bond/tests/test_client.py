"""Testy `BondClient` — jak cb-bond vidí ostatní moduly.

Klient je jediná cesta, kterou smí cizí modul cb-bond volat (§ 4).
Testuje se proti skutečnému serveru na portu 0: kdyby se testoval proti
atrapě, neuvidělo by se to, co se v praxi láme — hlavičky, kódy a to, že
nedostupná služba musí být typovaná chyba, ne prázdný výsledek.
"""

import tempfile
import threading
import unittest
from pathlib import Path

from cb_bond.api import make_api_server
from cb_bond.client import BondClient, ServiceUnavailable
from cb_bond.service import BondService
from cb_bond.tests.test_service import _config, _Parser
from cb_bond.tests.vzorky import GRAVITACE, KRESTA, OTAZKA_KREST


class Zaklad(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        vety = (KRESTA, GRAVITACE, OTAZKA_KREST)
        config = _config(tmp, (KRESTA, GRAVITACE))
        config["service"] = {"host": "127.0.0.1", "port": 0, "view_port": 0}
        self.service = BondService(config, _Parser(vety), verbose=False)
        self.server = make_api_server(self.service, config=config, port=0)
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever,
                         daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.klient = BondClient(
            endpoint=f"http://127.0.0.1:{self.server.server_address[1]}")


class TestDotaz(Zaklad):

    def test_ask_vrati_odpoved_i_rozklad(self):
        self.service.build()

        odpoved = self.klient.ask(OTAZKA_KREST.source)

        self.assertIn("answer", odpoved)
        self.assertIn("decomposition", odpoved)

    def test_state_vrati_statistiky(self):
        self.service.build()

        stav = self.klient.state()

        self.assertEqual(stav["sentences"], 2)
        self.assertGreater(stav["edges"], 0)

    def test_health_rekne_ze_neni_postaveno(self):
        self.assertEqual(self.klient.health()["status"], "degraded")


class TestNedostupnaSluzba(unittest.TestCase):

    def test_nedostupna_sluzba_je_TYPOVANA_chyba(self):
        # prázdný výsledek by se slil s platným „nevím"; volající by pak
        # hledal chybu v datech místo ve spojení (§ 9)
        klient = BondClient(endpoint="http://127.0.0.1:1", timeout=1)

        with self.assertRaises(ServiceUnavailable) as chyba:
            klient.ask("Kdo?")
        self.assertIn("127.0.0.1:1", str(chyba.exception))


if __name__ == "__main__":
    unittest.main()
