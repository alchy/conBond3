"""Testy sdíleného načítání konfigurace.

Modul vznikl sloučením tří kopií (cb_logger, cb_udpipe, cb_bond), které
se lišily jen konstantami. Testy proto hlídají hlavně to, co se v kopiích
opakovalo a co se muselo držet stejné: hlasitost při neznámém klíči,
odmítnutí cizí verze a otisk, bez kterého se dvě měření nedají porovnat.
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_config import ConfigError, fingerprint, load, resolve_paths, validate

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Zkušební schéma",
    "type": "object",
    "additionalProperties": False,
    "required": ["config_version", "service"],
    "properties": {
        "config_version": {"type": "integer", "minimum": 1},
        "service": {
            "type": "object",
            "additionalProperties": False,
            "required": ["host", "port"],
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer", "minimum": 0, "maximum": 65535},
                "level": {"type": "string", "enum": ["info", "debug"]},
                "dir": {"type": "string"},
            },
        },
    },
}

PLATNA = {"config_version": 1,
          "service": {"host": "127.0.0.1", "port": 42400}}


class _Zaklad(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.schema_path = self.tmp / "schema.json"
        self.schema_path.write_text(json.dumps(SCHEMA), encoding="utf-8")

    def _config(self, data) -> Path:
        cesta = self.tmp / "config.json"
        cesta.write_text(json.dumps(data), encoding="utf-8")
        return cesta


class TestNacteni(_Zaklad):

    def test_platna_konfigurace_projde_a_nese_otisk(self):
        nactena = load(self._config(PLATNA), self.schema_path,
                       supported_version=1)

        self.assertEqual(nactena["service"]["port"], 42400)
        self.assertIn("fingerprint", nactena["_meta"])
        self.assertEqual(len(nactena["_meta"]["fingerprint"]), 12)

    def test_cizi_verze_je_hlasita_chyba(self):
        cesta = self._config(dict(PLATNA, config_version=7))

        with self.assertRaises(ConfigError) as chyba:
            load(cesta, self.schema_path, supported_version=1)
        self.assertIn("config_version", str(chyba.exception))

    def test_chybejici_soubor_rekne_KTERY(self):
        with self.assertRaises(ConfigError) as chyba:
            load(self.tmp / "neni.json", self.schema_path,
                 supported_version=1)
        self.assertIn("neni.json", str(chyba.exception))

    def test_rozbity_json_rekne_RADEK(self):
        cesta = self.tmp / "config.json"
        cesta.write_text('{"config_version": 1,,}', encoding="utf-8")

        with self.assertRaises(ConfigError) as chyba:
            load(cesta, self.schema_path, supported_version=1)
        self.assertIn("JSON", str(chyba.exception))


class TestValidace(_Zaklad):

    def test_neznamy_klic_je_chyba_ne_tiche_ignorovani(self):
        chyby = validate(dict(PLATNA, preklep=1), SCHEMA)

        self.assertTrue(chyby)
        self.assertIn("preklep", chyby[0])

    def test_chybejici_povinny_klic(self):
        chyby = validate({"config_version": 1}, SCHEMA)

        self.assertTrue(any("service" in ch for ch in chyby))

    def test_spatny_typ_rekne_co_cekal(self):
        chyby = validate({"config_version": "jedna",
                          "service": {"host": "h", "port": 1}}, SCHEMA)

        self.assertTrue(any("integer" in ch for ch in chyby))

    def test_mez_rozsahu(self):
        chyby = validate({"config_version": 1,
                          "service": {"host": "h", "port": 99999}}, SCHEMA)

        self.assertTrue(any("maxim" in ch for ch in chyby))

    def test_enum(self):
        chyby = validate({"config_version": 1,
                          "service": {"host": "h", "port": 1,
                                      "level": "hlasite"}}, SCHEMA)

        self.assertTrue(any("level" in ch for ch in chyby))

    def test_bool_neprojde_jako_integer(self):
        # True je v Pythonu instance int; kdyby prošlo, port by šel
        # nastavit na "true" a nikdo by nepoznal proč
        chyby = validate({"config_version": True,
                          "service": {"host": "h", "port": 1}}, SCHEMA)

        self.assertTrue(chyby)

    def test_ROZBITE_schema_je_hlasita_chyba(self):
        # Dřív se hlídalo, že schéma nepoužije klíč, kterému náš ručně
        # psaný validátor nerozumí. S knihovnou ten problém zmizel —
        # rozumí celému Draft 7 — a zůstala potřeba opačná: poznat, že je
        # rozbité SCHÉMA, ne konfigurace. Bez toho se vada schématu
        # projeví jako podivná hláška o konfiguraci, která je v pořádku.
        vadne = dict(SCHEMA, type="objekt")     # takový typ neexistuje

        with self.assertRaises(ConfigError) as chyba:
            validate(PLATNA, vadne)
        self.assertIn("schéma", str(chyba.exception))

    def test_klicove_slovo_navic_uz_NENI_problem(self):
        # patternProperties ručnímu validátoru vadilo; knihovna ho umí
        rozsirene = dict(SCHEMA, patternProperties={"^x": {"type": "string"}})

        self.assertEqual(validate(PLATNA, rozsirene), [])


class TestCesty(_Zaklad):

    def test_relativni_cesta_se_rozvine_vuci_ZADANE_zakladne(self):
        config = {"config_version": 1,
                  "service": {"host": "h", "port": 1, "dir": "data"}}

        hotova = resolve_paths(config, [((("service", "dir")),
                                         Path("/tmp/koren"))])

        self.assertEqual(hotova["service"]["dir"], "/tmp/koren/data")

    def test_absolutni_cesta_se_nechá_byt(self):
        config = {"config_version": 1,
                  "service": {"host": "h", "port": 1, "dir": "/jinde/data"}}

        hotova = resolve_paths(config, [((("service", "dir")),
                                         Path("/tmp/koren"))])

        self.assertEqual(hotova["service"]["dir"], "/jinde/data")

    def test_vstup_se_NEMENI(self):
        config = {"config_version": 1,
                  "service": {"host": "h", "port": 1, "dir": "data"}}

        resolve_paths(config, [((("service", "dir")), Path("/tmp/koren"))])

        self.assertEqual(config["service"]["dir"], "data")

    def test_dve_zakladny_najednou(self):
        # cb-bond má běhové cesty v modulu a datové mimo repozitář
        config = {"config_version": 1,
                  "service": {"host": "h", "port": 1, "dir": "data"},
                  "runtime": {"pid": "run/service.pid"}}

        hotova = resolve_paths(config, [
            (("service", "dir"), Path("/data")),
            (("runtime", "pid"), Path("/modul"))])

        self.assertEqual(hotova["service"]["dir"], "/data/data")
        self.assertEqual(hotova["runtime"]["pid"], "/modul/run/service.pid")


class TestOtisk(_Zaklad):

    def test_otisk_se_meni_s_obsahem(self):
        self.assertNotEqual(fingerprint(PLATNA),
                            fingerprint(dict(PLATNA, config_version=2)))

    def test_otisk_NEZAVISI_na_poradi_klicu(self):
        a = {"config_version": 1, "service": {"host": "h", "port": 1}}
        b = {"service": {"port": 1, "host": "h"}, "config_version": 1}

        self.assertEqual(fingerprint(a), fingerprint(b))


class TestVlastniKontroly(_Zaklad):

    def test_vlastni_kontrola_pripoji_svoje_chyby(self):
        def zakaz_localhost(config):
            return (["service.host nesmí být localhost"]
                    if config["service"]["host"] == "localhost" else [])

        cesta = self._config({"config_version": 1,
                              "service": {"host": "localhost", "port": 1}})

        with self.assertRaises(ConfigError) as chyba:
            load(cesta, self.schema_path, supported_version=1,
                 checks=[zakaz_localhost])
        self.assertIn("localhost", str(chyba.exception))


if __name__ == "__main__":
    unittest.main()
