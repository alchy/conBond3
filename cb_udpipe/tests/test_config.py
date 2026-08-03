"""Konfigurace se ověřuje při startu, ne při prvním použití.

Služba, která nastartovala se špatnou konfigurací, je horší než služba, která
nenastartovala: chyba se projeví až za hodinu uprostřed dávky, na místě, které
s příčinou nesouvisí.
"""

import contextlib
import json
import tempfile
import unittest
from pathlib import Path

from cb_udpipe import config


class ZakladKonfigurace(unittest.TestCase):
    """Společné pomůcky. Testy si píšou do dočasného adresáře, nikdy
    do provozního — cesty jsou v konfiguraci právě proto, aby to šlo."""

    def platna(self) -> dict:
        """Kopie konfigurace z repozitáře jako výchozí bod pro úpravy."""
        return json.loads(config.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))

    @contextlib.contextmanager
    def docasna(self, data: dict):
        """Zapíše konfiguraci do dočasného souboru a vrátí cestu k němu."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cb-udpipe-config.json"
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            yield p


class TestPlatnaKonfigurace(ZakladKonfigurace):

    def test_vychozi_konfigurace_projde(self):
        """Konfigurace v repozitáři musí být platná. Kdyby nebyla, modul by
        nenastartoval a poznalo by se to až u prvního spuštění."""
        cfg = config.load()
        self.assertEqual(cfg["config_version"], 1)
        self.assertEqual(cfg["service"]["port"], 42200)
        self.assertEqual(cfg["module"]["upstream"]["port"], 42201)

    def test_meta_nese_pouzitou_cestu_a_otisk(self):
        """Bez zapsané cesty nikdo nezjistí, které nastavení vlastně běží —
        a hledá pak chybu v běžící službě, zatímco běží s jiným nastavením,
        než si myslí (§ 5 politiky)."""
        cfg = config.load()
        self.assertTrue(cfg["_meta"]["path"].endswith("cb-udpipe-config.json"))
        self.assertEqual(len(cfg["_meta"]["fingerprint"]), 12)

    def test_otisk_se_meni_s_obsahem(self):
        """Verze v souboru se mění zřídka, hodnoty často. Otisk pozná i změnu,
        u které nikdo číslo nezvýšil (§ 11 politiky)."""
        prvni = config.load()["_meta"]["fingerprint"]
        upravena = self.platna()
        upravena["service"]["workers"] = 8
        with self.docasna(upravena) as p:
            druhy = config.load(p)["_meta"]["fingerprint"]
        self.assertNotEqual(prvni, druhy)

    def test_cesty_jsou_absolutni(self):
        """Relativní cesta se počítá vůči adresáři modulu, ne vůči pracovnímu
        adresáři procesu — jinak by se chování měnilo podle toho, odkud se
        služba spustí, a to je chyba, kterou nikdo nehledá na správném místě."""
        cfg = config.load()
        for cesta in (cfg["module"]["cache"]["dir"],
                      cfg["module"]["upstream"]["model_dir"],
                      cfg["module"]["upstream"]["hf_home"],
                      cfg["runtime"]["pid_file"]):
            self.assertTrue(Path(cesta).is_absolute(), cesta)

    def test_absolutni_cesta_se_necha_byt(self):
        """Kdo ji tam napsal, ví, co dělá — obvykle míří na jiný disk."""
        upravena = self.platna()
        upravena["module"]["cache"]["dir"] = "/tmp/cb-udpipe-test"
        with self.docasna(upravena) as p:
            cfg = config.load(p)
        self.assertEqual(cfg["module"]["cache"]["dir"], "/tmp/cb-udpipe-test")


class TestNeplatnaKonfigurace(ZakladKonfigurace):

    def test_neznamy_klic_je_chyba(self):
        """Tiše ignorovaný překlep znamená, že běží jiné nastavení, než si
        člověk myslí (§ 5 politiky)."""
        upravena = self.platna()
        upravena["sluzba"] = {}
        with self.docasna(upravena) as p:
            with self.assertRaises(config.ConfigError) as e:
                config.load(p)
        self.assertIn("sluzba", str(e.exception))

    def test_chybejici_povinny_klic_je_chyba(self):
        upravena = self.platna()
        del upravena["module"]["tokenizer"]
        with self.docasna(upravena) as p:
            with self.assertRaises(config.ConfigError) as e:
                config.load(p)
        self.assertIn("tokenizer", str(e.exception))

    def test_spatny_typ_je_chyba(self):
        upravena = self.platna()
        upravena["service"]["port"] = "42200"
        with self.docasna(upravena) as p:
            with self.assertRaises(config.ConfigError) as e:
                config.load(p)
        self.assertIn("port", str(e.exception))

    def test_hlasi_se_vsechny_chyby_najednou(self):
        """Když je konfigurace špatně, je obvykle špatně víc věcí. Nahlásit
        jen první znamená, že se to opravuje na třikrát."""
        upravena = self.platna()
        upravena["service"]["workers"] = 0
        upravena["module"]["log_objects"] = "nesmysl"
        with self.docasna(upravena) as p:
            with self.assertRaises(config.ConfigError) as e:
                config.load(p)
        zprava = str(e.exception)
        self.assertIn("workers", zprava)
        self.assertIn("log_objects", zprava)

    def test_jina_verze_konfigurace_je_chyba(self):
        """Tiché načtení podle špatného předpokladu vyrobí čísla, která
        vypadají správně (§ 14 politiky)."""
        upravena = self.platna()
        upravena["config_version"] = 99
        with self.docasna(upravena) as p:
            with self.assertRaises(config.ConfigError) as e:
                config.load(p)
        self.assertIn("config_version", str(e.exception))

    def test_chybejici_soubor_rekne_ktery(self):
        with self.assertRaises(config.ConfigError) as e:
            config.load("/neexistuje/cb-udpipe-config.json")
        self.assertIn("/neexistuje/", str(e.exception))

    def test_nevalidni_json_rekne_radek(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text('{"config_version": 1,,}', encoding="utf-8")
            with self.assertRaises(config.ConfigError) as e:
                config.load(p)
        self.assertIn("řádek", str(e.exception))


class TestRozsahPortu(ZakladKonfigurace):
    """Rozsah 42200–42299 je vlastnictví modulu (§ 5 politiky). Sáhnutí na cizí
    číslo je chyba konfigurace, ne provozu — a pozná se jinak až tím, že se dva
    moduly poperou o totéž číslo."""

    def test_port_sluzby_mimo_rozsah_je_chyba(self):
        upravena = self.platna()
        upravena["service"]["port"] = 42100          # port cb-loggeru
        with self.docasna(upravena) as p:
            with self.assertRaises(config.ConfigError) as e:
                config.load(p)
        self.assertIn("42200", str(e.exception))

    def test_port_upstreamu_mimo_rozsah_je_chyba(self):
        upravena = self.platna()
        upravena["module"]["upstream"]["port"] = 9010   # port conBondu2
        with self.docasna(upravena) as p:
            with self.assertRaises(config.ConfigError):
                config.load(p)

    def test_nula_je_povolena(self):
        """Port 0 znamená „přidělí systém" a používají ho testy, aby
        neobsazovaly pevná čísla (§ 5 politiky)."""
        upravena = self.platna()
        upravena["service"]["port"] = 0
        with self.docasna(upravena) as p:
            cfg = config.load(p)
        self.assertEqual(cfg["service"]["port"], 0)


class TestSchema(unittest.TestCase):

    def test_schema_nepouziva_neznama_klicova_slova(self):
        """Kdyby validátor na neznámé klíčové slovo mlčel, tvářilo by se
        schéma jako vynucené, ale ta část by nekontrolovala nic. Test, který
        zticha přestane hlídat, je horší než žádný test."""
        schema = json.loads(config.SCHEMA_PATH.read_text(encoding="utf-8"))
        config._check_schema_supported(schema)      # nesmí vyhodit

    def test_zkratky_jsou_v_konfiguraci_ne_v_kodu(self):
        """Seznam zkratek je jazykové datum (SEAM-8 návrhu). V kódu nesmí být
        jediné slovo přirozeného jazyka."""
        cfg = config.load()
        zkratky = cfg["module"]["tokenizer"]["abbreviations"]
        self.assertIn("tzv", zkratky)
        self.assertIn("např", zkratky)
        self.assertGreater(len(zkratky), 20)


if __name__ == "__main__":
    unittest.main()
