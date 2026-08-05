"""T-K3: shoda tváří — v procesu musí dát totéž co přes síť.

Tohle je důvod, proč je modul rozdělený na `service.py` (fasáda) a
`api.py` (REST). Kdyby se obě cesty rozešly, ztratilo by rozdělení
smysl: modul by šel použít jen jednou z nich a druhá by tiše vracela
něco jiného — a „tiše" je tu to podstatné, protože takový rozdíl se
najde až ve chvíli, kdy na něm někdo staví.
"""

import tempfile
import threading
import unittest
from pathlib import Path

from cb_bond.api import make_api_server
from cb_bond.client import BondClient
from cb_bond.service import BondService
from cb_bond.tests.test_service import _config, _Parser
from cb_bond.tests.vzorky import GRAVITACE, KRESTA, OTAZKA_KREST


class TestShodaTvari(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        vety = (KRESTA, GRAVITACE, OTAZKA_KREST)
        config = _config(tmp, (KRESTA, GRAVITACE))
        config["service"] = {"host": "127.0.0.1", "port": 0, "view_port": 0}

        self.service = BondService(config, _Parser(vety), verbose=False)
        self.service.build()
        self.server = make_api_server(self.service, config=config, port=0)
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever,
                         daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.klient = BondClient(
            endpoint=f"http://127.0.0.1:{self.server.server_address[1]}")

    def test_ask_dava_TOTEZ_v_procesu_i_pres_sit(self):
        v_procesu = self.service.ask(OTAZKA_KREST.source, top=3)
        pres_sit = self.klient.ask(OTAZKA_KREST.source, top=3)

        self.assertEqual(v_procesu, pres_sit)

    def test_state_dava_TOTEZ(self):
        self.assertEqual(self.service.state(), self.klient.state())

    def test_health_dava_TOTEZ(self):
        self.assertEqual(self.service.health(), self.klient.health())

    def test_context_dava_TOTEZ(self):
        # obě cesty mění týž systém, takže se porovnává tvar, ne hodnota:
        # druhé volání staví na výsledku prvního
        v_procesu = self.service.context(GRAVITACE.source)
        pres_sit = self.klient.context(GRAVITACE.source)

        self.assertEqual(set(v_procesu), set(pres_sit))
        self.assertEqual(pres_sit["sentences"], v_procesu["sentences"] + 1)


if __name__ == "__main__":
    unittest.main()
