"""Testy konfigurace cb-bondu — validace, cesty, otisk.

Konfigurace se ověřuje PŘI STARTU: služba, která nastartovala se špatným
nastavením, je horší než služba, která nenastartovala. Chyba se pak
projeví za hodinu uprostřed dávky, na místě, které s příčinou nesouvisí.
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_bond import config as cfg


def _zapis(tmp: Path, uprav=None) -> Path:
    data = json.loads(cfg.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    if uprav:
        uprav(data)
    cesta = tmp / "cb-bond-config.json"
    cesta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return cesta


class TestNacteni(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_dodavana_konfigurace_projde(self):
        nactena = cfg.load()

        self.assertEqual(nactena["config_version"], 1)
        self.assertEqual(nactena["service"]["port"], 42400)
        self.assertEqual(nactena["service"]["view_port"], 42401)

    def test_cizi_verze_konfigurace_je_hlasita_chyba(self):
        cesta = _zapis(self.tmp, lambda d: d.update(config_version=99))

        with self.assertRaises(cfg.ConfigError) as chyba:
            cfg.load(cesta)
        self.assertIn("config_version", str(chyba.exception))

    def test_neznamy_klic_je_chyba_ne_tiche_ignorovani(self):
        # překlep tiše ignorovaný znamená, že běží jiné nastavení,
        # než si člověk myslí
        cesta = _zapis(self.tmp, lambda d: d["module"].update(sedm=1))

        with self.assertRaises(cfg.ConfigError):
            cfg.load(cesta)

    def test_chybejici_povinna_sekce_je_chyba(self):
        cesta = _zapis(self.tmp, lambda d: d.pop("module"))

        with self.assertRaises(cfg.ConfigError):
            cfg.load(cesta)

    def test_port_mimo_rozsah_modulu_je_chyba(self):
        # cb-bond má 42400–42499; sáhnout po cizím portu je chyba, ne
        # rozhodnutí (README-MODULES § 5)
        cesta = _zapis(self.tmp,
                       lambda d: d["service"].update(port=8080))

        with self.assertRaises(cfg.ConfigError) as chyba:
            cfg.load(cesta)
        self.assertIn("42400", str(chyba.exception))

    def test_kolize_portu_uvnitr_modulu_je_chyba(self):
        cesta = _zapis(self.tmp,
                       lambda d: d["service"].update(view_port=42400))

        with self.assertRaises(cfg.ConfigError):
            cfg.load(cesta)


class TestCesty(unittest.TestCase):

    def test_data_root_je_JEDINA_absolutni_cesta(self):
        # oddělení kódu od dat: všechno ostatní je relativní vůči kořeni,
        # takže se instalace přenese změnou jednoho řádku
        syrova = json.loads(cfg.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        modul = syrova["module"]

        self.assertTrue(Path(modul["data_root"]).is_absolute())
        for klic in ("directory",):
            self.assertFalse(Path(modul["corpus"][klic]).is_absolute())
        self.assertFalse(
            Path(modul["state"]["registry_dir"]).is_absolute())

    def test_datove_cesty_se_rozvinou_vuci_data_root(self):
        nactena = cfg.load()
        koren = Path(nactena["module"]["data_root"])

        self.assertEqual(Path(nactena["module"]["corpus"]["directory"]),
                         koren / "corpus")
        self.assertEqual(
            Path(nactena["module"]["state"]["registry_dir"]),
            koren / "cb_bond" / "persistent-registry")

    def test_behove_cesty_zustavaji_v_MODULU(self):
        # run/ je stav procesu, ne data — zůstává v repozitáři
        nactena = cfg.load()

        self.assertEqual(Path(nactena["runtime"]["pid_file"]).parent,
                         cfg.MODULE_DIR / "run")


class TestOtisk(unittest.TestCase):

    def test_otisk_se_meni_s_obsahem(self):
        prvni = cfg.load()["_meta"]["fingerprint"]
        with tempfile.TemporaryDirectory() as tmp:
            cesta = _zapis(Path(tmp),
                           lambda d: d["module"]["matching"].update(top_k=99))
            druhy = cfg.load(cesta)["_meta"]["fingerprint"]

        self.assertNotEqual(prvni, druhy)

    def test_otisk_je_stabilni(self):
        self.assertEqual(cfg.load()["_meta"]["fingerprint"], cfg.load()["_meta"]["fingerprint"])


class TestPaky(unittest.TestCase):
    """Konfigurace je jediné místo, kde žijí páky systému."""

    def test_nese_vsechny_paky_ktere_se_kalibrovaly(self):
        modul = cfg.load()["module"]

        self.assertEqual(modul["promotion"]["limit"], 328)
        self.assertEqual(modul["reading"]["sigma"], 1.5)
        self.assertEqual(modul["matching"]["spread_depth"], 1)
        self.assertEqual(modul["training"]["learning_rate"], 0.001)
        self.assertEqual(modul["matching"]["graph_recall_depth"], 2)
        self.assertEqual(modul["seed"], 328)

    def test_vahy_skore_jsou_v_konfiguraci(self):
        vahy = cfg.load()["module"]["matching"]["weights"]

        self.assertEqual(vahy["given"], -3.0)
        self.assertEqual(vahy["spectral"], 0.0)     # vypnuto = dnešek


class TestZavislosti(unittest.TestCase):

    def test_poradi_sluzeb_je_LOGGER_PRVNI(self):
        # udpipe do loggeru loguje už při vlastním startu; obrácené
        # pořadí by první záznamy zahodilo
        sluzby = [s["name"] for s in
                  cfg.load()["dependencies"]["services"]]

        self.assertEqual(sluzby, ["cb-logger", "cb-udpipe"])

    def test_spousteni_zavislosti_je_vychozi(self):
        self.assertTrue(cfg.load()["dependencies"]["start_on_boot"])


if __name__ == "__main__":
    unittest.main()
