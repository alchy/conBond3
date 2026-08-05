"""Ovládání služby: pět příkazů a jejich návratové kódy.

Testy **nespouštějí** UDPipe ani naši službu naostro — vyžadovalo by to model
357 MB a TensorFlow. Ověřuje se všechno kolem: kontrola konfigurace, kontrola
modelu, hlášky, návratové kódy a čtení běhového stavu. Skutečný start je
předmětem měření (úkol 12), ne jednotkového testu.
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cb_udpipe import config, control


class ZakladControl(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def konfigurace(self, **zmeny) -> str:
        """Zapíše konfiguraci do dočasného souboru a vrátí cestu."""
        cfg = json.loads(
            config.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        )
        cfg["runtime"]["pid_file"] = str(self.dir / "service.pid")
        cfg["runtime"]["port_file"] = str(self.dir / "service.port")
        cfg["module"]["cache"]["dir"] = str(self.dir / "cache")
        cfg["module"]["upstream"]["model_dir"] = str(self.dir / "model")
        cfg["module"]["upstream"]["hf_home"] = str(self.dir / "hf")
        cfg["module"]["upstream"]["vendor_dir"] = str(self.dir / "vendor")
        cfg["data_root"] = str(self.dir / "koren")
        for cesta, hodnota in zmeny.items():
            uzel = cfg
            klice = cesta.split(".")
            for k in klice[:-1]:
                uzel = uzel[k]
            uzel[klice[-1]] = hodnota
        p = self.dir / "cb-udpipe-config.json"
        p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        return str(p)

    def spust(self, *argv) -> tuple[int, str, str]:
        """Zavolá `control.main` a zachytí oba výstupy."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            kod = control.main(list(argv))
        return kod, out.getvalue(), err.getvalue()


class TestNavratoveKody(ZakladControl):

    def test_status_na_nebezici_sluzbu_vraci_3(self):
        kod, _, _ = self.spust("status", "--config", self.konfigurace())
        self.assertEqual(kod, control.EXIT_NOT_RUNNING)

    def test_stop_na_nebezici_sluzbu_vraci_3(self):
        kod, _, _ = self.spust("stop", "--config", self.konfigurace())
        self.assertEqual(kod, control.EXIT_NOT_RUNNING)

    def test_reload_na_nebezici_sluzbu_vraci_3(self):
        kod, _, _ = self.spust("reload", "--config", self.konfigurace())
        self.assertEqual(kod, control.EXIT_NOT_RUNNING)

    def test_neplatna_konfigurace_vraci_2(self):
        """Špatné argumenty nebo neplatná konfigurace je 2, ne obecná
        jednička — ovládání se volá ze skriptů a kódy musí být spolehlivé
        (§ 12 politiky)."""
        vadny = self.dir / "vadny.json"
        vadny.write_text('{"config_version": 1}', encoding="utf-8")
        kod, _, err = self.spust("status", "--config", str(vadny))
        self.assertEqual(kod, control.EXIT_BAD_USAGE)
        self.assertIn("chybí povinný klíč", err)

    def test_chybejici_konfigurace_vraci_2(self):
        kod, _, err = self.spust("status", "--config", "/neexistuje.json")
        self.assertEqual(kod, control.EXIT_BAD_USAGE)


class TestStatus(ZakladControl):

    def test_uvadi_port_i_u_nebezici_sluzby(self):
        """status je první příkaz, který člověk zavolá, když něco nefunguje.
        Musí z něj být poznat, kam se má připojit — nebo kam by se připojil,
        kdyby služba běžela (§ 12 politiky)."""
        _, out, _ = self.spust("status", "--config", self.konfigurace())
        self.assertIn("42200", out)
        self.assertIn("NEBĚŽÍ", out)

    def test_uvadi_DATOVY_KOREN(self):
        """Data leží mimo repozitář; bez vypsaného kořene člověk hledá
        chybu v datech, která služba vůbec nečte (§ 19 politiky)."""
        _, out, _ = self.spust("status", "--config", self.konfigurace())

        self.assertIn("data", out)
        self.assertIn(str(self.dir / "koren"), out)

    def test_uvadi_cestu_ke_konfiguraci(self):
        """Jinak člověk hledá chybu v běžící službě, zatímco běží s jiným
        nastavením, než si myslí."""
        cesta = self.konfigurace()
        _, out, _ = self.spust("status", "--config", cesta)
        self.assertIn("cb-udpipe-config.json", out)

    def test_uvadi_i_port_udpipe(self):
        """Modul provozuje dva porty a při hledání chyby je potřeba vidět
        oba: naše API a vlastní instanci UDPipe."""
        _, out, _ = self.spust("status", "--config", self.konfigurace())
        self.assertIn("42201", out)

    def test_json_tvar(self):
        kod, out, _ = self.spust("status", "--config", self.konfigurace(),
                                 "--json")
        data = json.loads(out)
        self.assertFalse(data["running"])
        self.assertEqual(data["port"], 42200)
        self.assertEqual(data["module"], "cb-udpipe")

    def test_osirely_pid_se_pozna_a_nezamlci(self):
        """Proces s tím PID neexistuje → soubor je po spadlé službě.
        Přepíše se, ne zamlčí (§ 12 politiky)."""
        cesta = self.konfigurace()
        (self.dir / "service.pid").write_text("999999")
        kod, out, _ = self.spust("status", "--config", cesta)
        self.assertEqual(kod, control.EXIT_NOT_RUNNING)
        self.assertIn("osiřel", out)


class TestKontrolaModelu(ZakladControl):

    def test_chybejici_model_je_2_s_navodem(self):
        """Služba nenastartuje a řekne, který soubor chybí a **který skript
        ho pořídí**. Bez toho třetího si každý musí pamatovat, jak se model
        získává (§ 19 politiky)."""
        kod, _, err = self.spust("start", "--config", self.konfigurace())
        self.assertEqual(kod, control.EXIT_BAD_USAGE)
        self.assertIn("chybí model", err)
        self.assertIn("fetch-models.sh", err)

    def test_hlaska_uvadi_ocekavanou_cestu(self):
        kod, _, err = self.spust("start", "--config", self.konfigurace())
        self.assertIn(str(self.dir / "model"), err)

    def test_chybejici_robeczech_je_taky_chyba(self):
        """UDPipe si bez něj sáhne na HuggingFace a při prvním spuštění bez
        sítě spadne — přesně ta závislost na okolí, které se zbavujeme
        (§ 9 koncepce)."""
        (self.dir / "model").mkdir()
        kod, _, err = self.spust("start", "--config", self.konfigurace())
        self.assertEqual(kod, control.EXIT_BAD_USAGE)
        self.assertIn("RobeCzech", err)

    def test_chybejici_vendor_je_chyba(self):
        (self.dir / "model").mkdir()
        (self.dir / "hf" / "hub" / "models--ufal--robeczech-base").mkdir(
            parents=True
        )
        kod, _, err = self.spust("start", "--config", self.konfigurace())
        self.assertEqual(kod, control.EXIT_BAD_USAGE)
        self.assertIn("udpipe2_server.py", err)


class TestProstrediUdpipe(unittest.TestCase):
    """Prostředí procesu UDPipe se sestavuje odděleně, aby šlo otestovat
    bez spouštění čehokoli."""

    def test_offline_natvrdo(self):
        """HF_HOME míří dovnitř modulu a offline režim je natvrdo, ať se
        případná chybějící váha ohlásí hned a ne tichým stahováním."""
        prostredi = control._prostredi_udpipe(
            {"hf_home": "/tmp/hf", "threads": 4}
        )
        self.assertEqual(prostredi["HF_HOME"], "/tmp/hf")
        self.assertEqual(prostredi["HF_HUB_OFFLINE"], "1")
        self.assertEqual(prostredi["TRANSFORMERS_OFFLINE"], "1")
        self.assertEqual(prostredi["TOKENIZERS_PARALLELISM"], "false")

    def test_vlakna_z_konfigurace(self):
        self.assertEqual(control._vlakna({"threads": 6}), 6)

    def test_nula_vlaken_se_odvodi_z_jader(self):
        """Dvě jádra se nechají systému, ať stroj při rozboru nezamrzne
        (převzato z conBondu2, udpipe.sh)."""
        odvozeno = control._vlakna({"threads": 0})
        self.assertGreaterEqual(odvozeno, 2)


if __name__ == "__main__":
    unittest.main()
