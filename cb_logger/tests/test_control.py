"""Zkoušky ovládání služby: pět příkazů a jejich návratové kódy.

Krok 4 z pořadí stavby (README-MODULES.md § 16). Ovládání se volá ze skriptů, takže
kódy musí být spolehlivé — tyhle testy jsou o nich stejně jako o chování.

Testy spouštějí **skutečnou službu** v podprocesu, protože jinak by neověřily
to podstatné: že se proces odpojí, zapíše PID a port, reaguje na signály a po
sobě uklidí. Běží na portu `0`, takže neobsazují pevná čísla a mohou běžet
vedle provozní služby.
"""

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from cb_logger import control
from cb_logger.config import DEFAULT_CONFIG_PATH

EXIT_OK = control.EXIT_OK
EXIT_FAILED = control.EXIT_FAILED
EXIT_BAD_USAGE = control.EXIT_BAD_USAGE
EXIT_NOT_RUNNING = control.EXIT_NOT_RUNNING


class ZakladOvladani(unittest.TestCase):
    """Společný základ: dočasná konfigurace a jisté zastavení služby."""

    def setUp(self) -> None:
        self._adresar = tempfile.TemporaryDirectory()
        adr = Path(self._adresar.name)

        config = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        # Port 0 pro obě rozhraní: testy nesmí obsazovat pevná čísla, jinak
        # se poperou s provozní službou i mezi sebou.
        config["service"]["port"] = 0
        config["module"]["watch"]["port"] = 0
        config["runtime"]["pid_file"] = str(adr / "service.pid")
        config["runtime"]["port_file"] = str(adr / "service.port")
        config["runtime"]["self_log"]["path"] = str(adr / "self.log")
        config["runtime"]["stop_timeout_s"] = 5
        config["module"]["routing"]["default"] = str(adr / "log.jsonl")
        config["module"]["summary"]["path"] = str(adr / "summary.json")
        config["module"]["storage"]["dir"] = str(adr)

        self.cesta = adr / "cb-logger-config.json"
        self.cesta.write_text(
            json.dumps(config, ensure_ascii=False), encoding="utf-8"
        )
        self.adr = adr

    def tearDown(self) -> None:
        # Zastavit i po neúspěšném testu — osiřelý proces by držel port
        # a shodil by další testy, které by pak vypadaly jako jiná chyba.
        try:
            self.spust("stop")
        except Exception:
            pass
        self._adresar.cleanup()

    def spust(self, *argv: str) -> tuple[int, str]:
        """Zavolá ovládání a vrátí dvojici (návratový kód, výstup).

        Výstup se zachytává, aby neplnil terminál testů — ale vrací se, protože
        hlášky ovládání jsou součástí kontraktu: `status` musí uvést port a při
        chybě musí být poznat, co dělat.
        """
        vystup = io.StringIO()
        prikazy = list(argv) + ["--config", str(self.cesta)]
        with redirect_stdout(vystup), redirect_stderr(vystup):
            kod = control.main(prikazy)
        return kod, vystup.getvalue()


class StatusUvadiPortVzdy(ZakladOvladani):
    """`status` je první příkaz, který člověk zavolá, když něco nefunguje."""

    def test_neběžící_sluzba_vraci_3(self):
        kod, vystup = self.spust("status")

        self.assertEqual(kod, EXIT_NOT_RUNNING)
        self.assertIn("NEBĚŽÍ", vystup)

    def test_neběžící_sluzba_uvadi_zamysleny_port(self):
        # Bez portu člověk hledá chybu v běžící službě, zatímco běží
        # s jiným nastavením, než si myslí.
        _, vystup = self.spust("status")

        self.assertIn("měl by běžet na", vystup)
        self.assertIn("127.0.0.1", vystup)

    def test_status_uvadi_cestu_ke_konfiguraci(self):
        _, vystup = self.spust("status")
        self.assertIn(str(self.cesta), vystup)

    def test_bezici_sluzba_uvadi_skutecny_port(self):
        self.spust("start")
        kod, vystup = self.spust("status")

        self.assertEqual(kod, EXIT_OK)
        self.assertIn("BĚŽÍ", vystup)
        skutecny = int((self.adr / "service.port").read_text().strip())
        # Port 0 z konfigurace se nesmí objevit ve výpisu — musí tam být ten,
        # který systém opravdu přidělil.
        self.assertNotEqual(skutecny, 0)
        self.assertIn(str(skutecny), vystup)

    def test_status_json(self):
        self.spust("start")
        kod, vystup = self.spust("status", "--json")

        self.assertEqual(kod, EXIT_OK)
        stav = json.loads(vystup)
        self.assertTrue(stav["running"])
        self.assertEqual(stav["module"], "cb-logger")
        self.assertGreater(stav["port"], 0)
        self.assertEqual(stav["port_source"], "run/service.port (skutečný)")

    def test_status_json_u_nebezici_uvadi_zdroj_portu(self):
        kod, vystup = self.spust("status", "--json")

        self.assertEqual(kod, EXIT_NOT_RUNNING)
        stav = json.loads(vystup)
        self.assertFalse(stav["running"])
        self.assertIn("zamýšlený", stav["port_source"])

    def test_osirely_pid_soubor_se_pozna(self):
        # Zamlčet ho by znamenalo, že `start` odmítne spustit službu,
        # která neběží.
        (self.adr / "service.pid").write_text("999999\n", encoding="utf-8")

        kod, vystup = self.spust("status")

        self.assertEqual(kod, EXIT_NOT_RUNNING)
        self.assertIn("osiřelý", vystup)


class StartAStop(ZakladOvladani):
    """Start čeká na odpověď služby, stop po sobě uklidí."""

    def test_start_vraci_0_a_sluzba_odpovida(self):
        kod, vystup = self.spust("start")

        self.assertEqual(kod, EXIT_OK)
        self.assertIn("běží", vystup)
        self.assertEqual(self.spust("status")[0], EXIT_OK)

    def test_start_zapise_pid_a_port(self):
        self.spust("start")

        self.assertTrue((self.adr / "service.pid").exists())
        self.assertTrue((self.adr / "service.port").exists())

    def test_start_na_bezici_sluzbu_neni_chyba(self):
        # Kdo volá `start` na běžící službu, obvykle jen chce, aby běžela.
        self.spust("start")
        kod, vystup = self.spust("start")

        self.assertEqual(kod, EXIT_OK)
        self.assertIn("už běží", vystup)

    def test_stop_vraci_0_a_uklidi(self):
        self.spust("start")
        kod, _ = self.spust("stop")

        self.assertEqual(kod, EXIT_OK)
        self.assertFalse((self.adr / "service.pid").exists())
        self.assertFalse((self.adr / "service.port").exists())

    def test_stop_je_rychly_a_nesaha_po_sigkill(self):
        """Regrese: `stop` čekal celý `stop_timeout_s` a končil tvrdě.

        Příčina: ukončený potomek zůstane zombie, dokud ho rodič nesklidí,
        a na zombie `os.kill(pid, 0)` pořád uspěje — čekání tedy nikdy
        nepoznalo, že služba skončila. Naměřeno 20,05 s místo desetin.

        Test měří čas schválně: kdyby se pojistka ztratila, funkčně by se nic
        nezměnilo (služba se zastaví tak jako tak) a poznalo by se to jen na
        době. Strop 5 s je desetinásobek naměřené doby zastavení a zároveň
        zlomek `stop_timeout_s`, takže rozliší řízené ukončení od tvrdého.
        """
        import time

        self.spust("start")
        zacatek = time.monotonic()
        kod, vystup = self.spust("stop")
        trvani = time.monotonic() - zacatek

        self.assertEqual(kod, EXIT_OK)
        self.assertLess(trvani, 5.0, f"stop trval {trvani:.1f} s")
        self.assertNotIn("tvrdě", vystup)

    def test_stop_na_nebezici_vraci_3(self):
        kod, vystup = self.spust("stop")

        self.assertEqual(kod, EXIT_NOT_RUNNING)
        self.assertIn("neběží", vystup)

    def test_restart_na_bezici(self):
        self.spust("start")
        prvni_pid = (self.adr / "service.pid").read_text().strip()

        kod, _ = self.spust("restart")

        self.assertEqual(kod, EXIT_OK)
        druhy_pid = (self.adr / "service.pid").read_text().strip()
        self.assertNotEqual(prvni_pid, druhy_pid)

    def test_restart_na_nebezici_se_chova_jako_start(self):
        kod, _ = self.spust("restart")

        self.assertEqual(kod, EXIT_OK)
        self.assertEqual(self.spust("status")[0], EXIT_OK)

    def test_vlastni_log_zaznamena_start(self):
        # Logovátko nemůže logovat samo do sebe, tak píše sem.
        self.spust("start")

        obsah = (self.adr / "self.log").read_text(encoding="utf-8")
        self.assertIn("start", obsah)
        self.assertIn("poslouchám na", obsah)


class Reload(ZakladOvladani):
    """Reload nemá ztratit stav a má říct, co změnit za běhu nejde."""

    def test_reload_na_nebezici_vraci_3(self):
        kod, vystup = self.spust("reload")

        self.assertEqual(kod, EXIT_NOT_RUNNING)
        self.assertIn("neběží", vystup)

    def test_reload_na_bezici_vraci_0(self):
        self.spust("start")
        kod, _ = self.spust("reload")

        self.assertEqual(kod, EXIT_OK)

    def test_sluzba_po_reloadu_bezi_dal(self):
        # Reload nesmí zahodit rozdělaná spojení; nejlevnější důkaz je,
        # že služba pořád odpovídá se stejným PID.
        self.spust("start")
        pid_pred = (self.adr / "service.pid").read_text().strip()

        self.spust("reload")

        self.assertEqual(self.spust("status")[0], EXIT_OK)
        self.assertEqual(
            (self.adr / "service.pid").read_text().strip(), pid_pred
        )


class NeplatnaKonfiguraceVraci2(ZakladOvladani):
    """Špatné argumenty a neplatná konfigurace mají vlastní kód."""

    def test_neznamy_klic_v_konfiguraci(self):
        config = json.loads(self.cesta.read_text(encoding="utf-8"))
        config["service"]["porrt"] = 1
        self.cesta.write_text(json.dumps(config), encoding="utf-8")

        kod, vystup = self.spust("status")

        self.assertEqual(kod, EXIT_BAD_USAGE)
        self.assertIn("neznámý klíč", vystup)

    def test_chybejici_konfigurace(self):
        vystup = io.StringIO()
        with redirect_stdout(vystup), redirect_stderr(vystup):
            kod = control.main(["status", "--config", "/nic/takoveho.json"])

        self.assertEqual(kod, EXIT_BAD_USAGE)
        self.assertIn("chybí konfigurace", vystup.getvalue())

    def test_start_s_neplatnou_konfiguraci_nesmi_nastartovat(self):
        # Služba, která nastartovala se špatnou konfigurací, je horší než
        # služba, která nenastartovala.
        config = json.loads(self.cesta.read_text(encoding="utf-8"))
        config["service"]["workers"] = 0
        self.cesta.write_text(json.dumps(config), encoding="utf-8")

        kod, _ = self.spust("start")

        self.assertEqual(kod, EXIT_BAD_USAGE)
        self.assertFalse((self.adr / "service.pid").exists())


class SpoustecVKoreni(unittest.TestCase):
    """`cb-logger.py` je jen dveře do `control.py`."""

    def test_spoustec_existuje_a_je_spustitelny(self):
        import os

        self.assertTrue(control.LAUNCHER.exists(), control.LAUNCHER)
        self.assertTrue(os.access(control.LAUNCHER, os.X_OK),
                        f"{control.LAUNCHER} není spustitelný (chmod +x)")

    def test_spoustec_prepne_do_venv(self):
        # Shebang `env python3` najde ten, který je zrovna v PATH — na tomhle
        # stroji je /usr/bin/python3 verze 3.9 a syntaxi `int | None` neumí.
        obsah = control.LAUNCHER.read_text(encoding="utf-8")
        self.assertIn(".venv", obsah)
        self.assertIn("execv", obsah)


if __name__ == "__main__":
    unittest.main()
