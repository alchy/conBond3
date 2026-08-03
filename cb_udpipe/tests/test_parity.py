"""T-K3 a T-K4: shoda tváří a přežití výpadku.

`T-K3` je důvod, proč je modul rozdělený na `service.py` a `api.py`. Kdyby se
obě cesty rozešly, ztratilo by rozdělení smysl: modul by šel použít jen jednou
z nich a druhá by tiše vracela něco jiného.
"""

import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from cb_udpipe import api, client, config, service
from cb_udpipe.tests.fake_upstream import FakeLog, FakeUpstream

TEXTY = [
    "Petr je v Praze.",
    "R.U.R. je drama Karla Čapka.",
    "V úlu je 30 000 dělnic.",
    "Alois Jirásek se narodil 23. srpna 1851 v tzv. Hronově.",
    "",
]


class ZakladParity(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.run_dir = self.dir / "run"
        self.run_dir.mkdir()

        self.cfg = json.loads(
            config.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        )
        self.cfg["service"]["port"] = 0
        self.cfg["module"]["cache"]["dir"] = str(self.dir / "cache")
        self.cfg["runtime"]["pid_file"] = str(self.run_dir / "service.pid")
        self.cfg["_meta"] = {"path": "test", "fingerprint": "testtesttest"}

    def postav(self, cache_podadresar: str):
        """Postaví službu s vlastní cache.

        Každá strana zkoušky má svou cache schválně: kdyby ji sdílely, druhá
        by odpovídala ze zásahu a porovnávaly by se dvě čtení téhož záznamu
        místo dvou cest ke stejnému výsledku.
        """
        cfg = json.loads(json.dumps(self.cfg))
        cfg["module"]["cache"]["dir"] = str(self.dir / cache_podadresar)
        s = service.UdpipeService(cfg, upstream=FakeUpstream(),
                                  clock=lambda: "TS")
        self.addCleanup(s.close)
        return s, cfg


class TestShodaTvari(ZakladParity):
    """T-K3 — `service.py` v procesu a `client.py` přes síť dají totéž."""

    def setUp(self):
        super().setUp()
        self.v_procesu, _ = self.postav("cache-proces")

        pres_sit_service, cfg = self.postav("cache-sit")
        self.server = api.make_api_server(pres_sit_service, config=cfg)
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.klient = client.UdpipeClient(
            endpoint="http://127.0.0.1:%d" % self.server.server_address[1]
        )

    def test_parse_dava_totez(self):
        for text in TEXTY:
            with self.subTest(text=text):
                self.assertEqual(self.klient.parse(text=text),
                                 self.v_procesu.parse(text))

    def test_tokenize_only_dava_totez(self):
        for text in TEXTY:
            with self.subTest(text=text):
                self.assertEqual(self.klient.tokenize_only(text=text),
                                 self.v_procesu.tokenize_only(text))

    def test_vraci_tytez_typy(self):
        """Nejde jen o hodnoty: kdyby klient vracel slovníky a služba
        dataclassy, musel by volající psát dvě větve."""
        pres_sit = self.klient.parse(text="Petr je v Praze.")
        v_procesu = self.v_procesu.parse("Petr je v Praze.")
        self.assertIs(type(pres_sit), type(v_procesu))
        self.assertIs(type(pres_sit.sentences[0]),
                      type(v_procesu.sentences[0]))
        self.assertIs(type(pres_sit.sentences[0].tokens[0]),
                      type(v_procesu.sentences[0].tokens[0]))

    def test_zachova_i_prazdne_sloupce(self):
        """Kdyby se cestou po drátě ztratily prázdné sloupce, vypadalo by to
        jako shoda, dokud by někdo nesáhl na `xpos`."""
        pres_sit = self.klient.parse(text="Petr je v Praze.")
        t = pres_sit.sentences[0].tokens[0]
        self.assertTrue(hasattr(t, "xpos"))
        self.assertTrue(hasattr(t, "deps"))


class TestPrezijeVypadek(ZakladParity):
    """T-K4 — klient nad neběžící službou, degradace, smazané `run/`."""

    def test_klient_selze_pri_vytvoreni_ne_pri_volani(self):
        """Klient nad neběžící službou je tikající chyba: ukázala by se
        uprostřed dávky, po hodině počítání a s polovinou zapsaných
        výsledků (§ 1 politiky)."""
        with self.assertRaises(client.ServiceUnavailable):
            client.UdpipeClient(endpoint="http://127.0.0.1:1")

    def test_hlaska_ma_vsechny_tri_veci(self):
        """Který modul, na jaké adrese a čím ho spustit."""
        with self.assertRaises(client.ServiceUnavailable) as e:
            client.UdpipeClient(endpoint="http://127.0.0.1:1")
        zprava = str(e.exception)
        self.assertIn("cb-udpipe", zprava)
        self.assertIn("127.0.0.1:1", zprava)
        self.assertIn("./cb-udpipe.py start", zprava)

    def test_nekompatibilni_api_ma_vlastni_vyjimku(self):
        """Služba běží, ale mluví jinou verzí. Je to jiná chyba než výpadek
        a volající na ni reaguje jinak."""
        s, cfg = self.postav("cache-api")
        server = api.make_api_server(s, config=cfg)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        with self.assertRaises(client.IncompatibleApi):
            client.UdpipeClient(
                endpoint="http://127.0.0.1:%d" % server.server_address[1],
                api="v99",
            )

    def test_vypadek_udpipe_je_pro_volajiciho_nedostupnost(self):
        """Služba běží, ale UDPipe pod ní ne. Pro volajícího je to totéž:
        rozbor nedostane. Nikdy ale prázdný výsledek — ten by se slil
        s platným prázdným rozborem (INV-9)."""
        u = FakeUpstream()
        s, cfg = self.postav("cache-vypadek")
        s.upstream = u
        server = api.make_api_server(s, config=cfg)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        k = client.UdpipeClient(
            endpoint="http://127.0.0.1:%d" % server.server_address[1]
        )
        u.nedostupny = True
        with self.assertRaises(client.ServiceUnavailable) as e:
            k.parse(text="Petr je v Praze.")
        self.assertIn("UDPipe", str(e.exception))

    def test_smazane_run_je_neskodne(self):
        """`run/` nesmí přežít restart a jeho smazání nesmí nic pokazit
        (§ 2 politiky). Perzistentní data jsou jinde."""
        s, cfg = self.postav("cache-run")
        s.parse("Petr je v Praze.")
        shutil.rmtree(self.run_dir)
        r = s.parse("Jan je v Brně.")
        self.assertEqual(len(r.sentences), 1)
        self.assertEqual(s.cache.stats()["sentences"], 2)


class TestKlientLoguje(ZakladParity):

    def setUp(self):
        super().setUp()
        s, cfg = self.postav("cache-log")
        self.server = api.make_api_server(s, config=cfg)
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.log = FakeLog()
        self.klient = client.UdpipeClient(
            endpoint="http://127.0.0.1:%d" % self.server.server_address[1],
            log=self.log,
        )

    def test_loguje_vytvoreni(self):
        """Klient se ozve už při vytvoření, ne až při prvním volání."""
        self.assertTrue(any(z["method"] == "__init__" and z["result"] == "ok"
                            for z in self.log.zaznamy))

    def test_loguje_volani_se_stopou(self):
        self.klient.parse(text="Petr je v Praze.", trace="q-7f3a91")
        zaznam = [z for z in self.log.zaznamy if z["method"] == "parse"]
        self.assertTrue(zaznam)
        self.assertEqual(zaznam[0]["trace"], "q-7f3a91")

    def test_prazdny_vysledek_je_empty_ne_error(self):
        """`empty` a `error` se nikde neslévají — jinak by měření odměnilo
        právě tu chybu, kterou má chytat."""
        self.klient.parse(text="")
        zaznam = [z for z in self.log.zaznamy if z["method"] == "parse"]
        self.assertEqual(zaznam[0]["result"], "empty")


if __name__ == "__main__":
    unittest.main()


class TestVychoziEndpoint(ZakladParity):
    """`endpoint` je nepovinný — adresu si deklaruje sama služba.

    Bez toho by ji musel opisovat každý volající, a to je přesně ten druh
    duplikace, kvůli které se dvě místa rozejdou (README-MODULES.md § 4).
    Stejný vzor má cb-logger.
    """

    def test_bez_endpointu_najde_bezici_sluzbu(self):
        s, cfg = self.postav("cache-vychozi")
        server = api.make_api_server(s, config=cfg)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)

        # Skutečný port do run/service.port — tam ho hledá `default_endpoint`,
        # a je to podstatné, když je v konfiguraci nula.
        port_file = Path(config.DEFAULT_CONFIG_PATH.parent
                         / "run" / "service.port")
        puvodni = port_file.read_text() if port_file.exists() else None
        port_file.parent.mkdir(parents=True, exist_ok=True)
        port_file.write_text(str(server.server_address[1]))
        try:
            k = client.UdpipeClient()          # bez endpointu
            self.assertEqual(k.endpoint_source, "run/service.port (běžící služba)")
            self.assertEqual(len(k.parse(text="Petr je v Praze.").sentences), 1)
        finally:
            if puvodni is None:
                port_file.unlink(missing_ok=True)
            else:
                port_file.write_text(puvodni)

    def test_predany_endpoint_prebiji(self):
        s, cfg = self.postav("cache-prebiti")
        server = api.make_api_server(s, config=cfg)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        adresa = "http://127.0.0.1:%d" % server.server_address[1]
        k = client.UdpipeClient(endpoint=adresa)
        self.assertEqual(k.endpoint_source, "předáno")
        self.assertEqual(k.endpoint, adresa)

    def test_default_endpoint_cte_konfiguraci(self):
        """Když služba neběží, vezme se zamýšlený port z konfigurace."""
        adresa, odkud = client.default_endpoint()
        self.assertTrue(adresa.startswith("http://127.0.0.1:"))
        self.assertIn(odkud, ("run/service.port (běžící služba)",
                              "cb-udpipe-config.json",
                              "zabudovaná výchozí hodnota"))

    def test_from_config_bez_adresy_pouzije_vychozi(self):
        """Modul, který mluví s instancí u sebe doma, adresu v konfiguraci
        mít nemusí."""
        s, cfg = self.postav("cache-fromcfg")
        server = api.make_api_server(s, config=cfg)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        k = client.from_config(
            {"module": {"udpipe_endpoint":
                        "http://127.0.0.1:%d" % server.server_address[1]}}
        )
        self.assertEqual(k.endpoint_source, "předáno")
