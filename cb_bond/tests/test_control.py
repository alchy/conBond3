"""Testy ovládání cb-bondu — hlavně `status`.

`status` je první příkaz, který člověk zavolá, když něco nefunguje. U
cb-bondu musí říct nejen že služba běží, ale **co má v hlavě**: obsah se
mění učením a promocí, takže bez čísel se nedá poznat, jestli běží model,
který se učil, nebo čerstvě postavený (požadavek J., 5. 8. 2026).

Testy nespouštějí skutečnou službu — stavba korpusu by potřebovala běžící
udpipe (§ 13). Místo toho se zvedne API server nad fasádou v procesu
a `run/` se naplní ručně; `status` pak čte totéž, co by četl v provozu.
"""

import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cb_bond import control
from cb_bond.api import make_api_server
from cb_bond.service import BondService
from cb_bond.tests.test_service import _config, _Parser
from cb_bond.tests.vzorky import GRAVITACE, KRESTA


class Zaklad(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.vety = (KRESTA, GRAVITACE)

        config = _config(self.tmp, self.vety)
        config["config_version"] = 1
        config["service"] = {"host": "127.0.0.1", "port": 0, "view_port": 0}
        config["runtime"] = {"pid_file": str(self.tmp / "run" / "service.pid"),
                             "port_file": str(self.tmp / "run"
                                              / "service.port"),
                             "stop_timeout_s": 5}
        config["dependencies"] = {"start_on_boot": True, "services": []}
        self.config = config
        self.cesta = self.tmp / "cb-bond-config.json"
        self.cesta.write_text(json.dumps(config, ensure_ascii=False),
                              encoding="utf-8")

    def spust_status(self, jako_json=False) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            kod = control.cmd_status(self.config, jako_json=jako_json)
        return kod, out.getvalue() + err.getvalue()

    def zvedni_sluzbu(self, postavit=True) -> None:
        """Spustí API server nad fasádou a zapíše běhový stav."""
        service = BondService(self.config, _Parser(self.vety), verbose=False)
        if postavit:
            service.build()
        server = make_api_server(service, config=self.config, port=0)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)

        bezi = self.tmp / "run"
        bezi.mkdir(exist_ok=True)
        (bezi / "service.pid").write_text(f"{os.getpid()}\n",
                                          encoding="utf-8")
        (bezi / "service.port").write_text(
            f"{server.server_address[1]}\n", encoding="utf-8")


class TestStatusNebezici(Zaklad):

    def test_nebezici_sluzba_vraci_3(self):
        kod, vystup = self.spust_status()

        self.assertEqual(kod, control.EXIT_NOT_RUNNING)
        self.assertIn("NEBĚŽÍ", vystup)

    def test_nebezici_sluzba_NEVYMYSLI_cisla(self):
        # kdyby si `status` korpus postavil sám, trvalo by to pět vteřin
        # a ukázal by, co by v hlavě bylo — ne co v ní je
        _, vystup = self.spust_status()

        self.assertIn("nenačteno", vystup)
        self.assertNotIn("hran", vystup)

    def test_nebezici_sluzba_rekne_co_by_STAVELA(self):
        _, vystup = self.spust_status()

        self.assertIn(str(self.tmp / "corpus"), vystup)
        self.assertIn("korpus-1*.json", vystup)

    def test_uvadi_datovy_koren_i_konfiguraci(self):
        _, vystup = self.spust_status()

        self.assertIn(str(self.tmp), vystup)
        self.assertIn("config", vystup)


class TestStatusBezici(Zaklad):
    """Čísla, kvůli kterým `status` vůbec je."""

    def test_uvadi_STATISTIKY_grafu(self):
        self.zvedni_sluzbu()

        kod, vystup = self.spust_status()

        self.assertEqual(kod, control.EXIT_OK)
        self.assertIn("BĚŽÍ", vystup)
        self.assertIn("hran", vystup)
        self.assertIn("lemmat", vystup)
        self.assertIn("vět", vystup)

    def test_uvadi_osy_i_jejich_verzi(self):
        self.zvedni_sluzbu()

        _, vystup = self.spust_status()

        self.assertIn("os", vystup)
        self.assertIn("verze", vystup)

    def test_nepostavena_ale_bezici_sluzba_je_videt(self):
        # port odpovídá, hlava prázdná — musí to být poznat, ne že se
        # tváří zdravě a spadne až u prvního dotazu
        self.zvedni_sluzbu(postavit=False)

        _, vystup = self.spust_status()

        self.assertIn("degraded", vystup)

    def test_status_json_nese_TATAZ_cisla(self):
        # viewBase i skripty čtou JSON; kdyby se rozešel s textem,
        # rozdíl by nikdo nehledal ve dvou cestách k témuž číslu
        self.zvedni_sluzbu()

        out = io.StringIO()
        with redirect_stdout(out):
            kod = control.cmd_status(self.config, jako_json=True)
        telo = json.loads(out.getvalue())

        self.assertEqual(kod, control.EXIT_OK)
        self.assertEqual(telo["state"]["sentences"], 2)
        self.assertGreater(telo["state"]["edges"], 0)


class TestPrikazKorpus(Zaklad):
    """`corpus status` odpovídá i tehdy, když služba neběží.

    Je to otázka na DATA, ne na službu: co leží v datovém kořeni se dá
    zjistit bez postaveného systému a člověk to typicky chce vědět
    právě ve chvíli, kdy služba nenaběhla.
    """

    def test_corpus_status_vypise_soubory_bez_bezici_sluzby(self):
        out = io.StringIO()
        with redirect_stdout(out):
            kod = control.cmd_corpus(self.config, akce="status")

        self.assertEqual(kod, control.EXIT_OK)
        self.assertIn("korpus-101.json", out.getvalue())
        self.assertIn(str(self.tmp / "corpus"), out.getvalue())

    def test_corpus_status_na_prazdny_adresar_je_hlasity(self):
        # tichá nula by vypadala jako „korpus je prázdný", ne jako
        # „ukazuješ jinam, než si myslíš"
        self.config["module"]["corpus"]["directory"] = str(self.tmp / "nic")

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            kod = control.cmd_corpus(self.config, akce="status")

        self.assertEqual(kod, control.EXIT_BAD_USAGE)
        self.assertIn("žádný soubor", out.getvalue() + err.getvalue())

    def test_neznama_akce_je_spatne_pouziti(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            kod = control.cmd_corpus(self.config, akce="tanci")

        self.assertEqual(kod, control.EXIT_BAD_USAGE)


class TestReload(Zaklad):

    def test_reload_na_nebezici_sluzbu_vraci_3(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            kod = control.cmd_reload(self.config)

        self.assertEqual(kod, control.EXIT_NOT_RUNNING)


if __name__ == "__main__":
    unittest.main()
