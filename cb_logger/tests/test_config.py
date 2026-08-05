"""Zkoušky načtení a ověření konfigurace.

Krok 1 z pořadí stavby modulu (README-MODULES.md § 16): *neplatná konfigurace
neprojde*. Je to schválně první věc, která se staví — modul, který umí
odpovídat dřív, než umí odmítnout špatnou konfiguraci, se ladí přes HTTP
místo přes test.

Testy si zakládají vlastní dočasný soubor a nikdy nesahají na provozní
konfiguraci. Kdyby ji měnily, měřilo by se něco jiného, než se tvrdí.
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_logger.config import (
    DEFAULT_CONFIG_PATH,
    MODULE_DIR,
    SUPPORTED_CONFIG_VERSION,
    ConfigError,
    load,
)


def platna_konfigurace() -> dict:
    """Vrátí kopii provozní konfigurace jako výchozí bod pro testy.

    Proč se čte provozní soubor místo psaní vlastního: kdyby si test držel
    vlastní kopii, rozešla by se s provozní při první změně schématu a testy
    by pak ověřovaly tvar, který nikde neběží.

    Výstup:
        Slovník načtený z `cb-logger-config.json`, který si test může měnit.
    """
    return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


class DocasnaKonfigurace:
    """Zapíše slovník do dočasného souboru a uklidí po sobě.

    Proč vlastní správce kontextu: `tempfile.NamedTemporaryFile` se na
    některých systémech nedá znovu otevřít, dokud je otevřený, a testy ho
    potřebují předat `load()` jako cestu.
    """

    def __init__(self, data: object):
        self._data = data
        self._adresar: tempfile.TemporaryDirectory | None = None

    def __enter__(self) -> Path:
        self._adresar = tempfile.TemporaryDirectory()
        cesta = Path(self._adresar.name) / "cb-logger-config.json"
        if isinstance(self._data, str):
            cesta.write_text(self._data, encoding="utf-8")
        else:
            cesta.write_text(
                json.dumps(self._data, ensure_ascii=False), encoding="utf-8"
            )
        return cesta

    def __exit__(self, *_: object) -> None:
        if self._adresar is not None:
            self._adresar.cleanup()


class PlatnaKonfiguraceProjde(unittest.TestCase):
    """T-K1 — správný vstup dá správný výstup."""

    def test_provozni_konfigurace_je_platna(self):
        # Pojistka proti tomu, aby se schéma a konfigurace rozešly.
        # Bez tohohle testu by se to zjistilo až při startu služby.
        config = load()
        self.assertEqual(config["config_version"], SUPPORTED_CONFIG_VERSION)

    def test_meta_nese_pouzitou_cestu(self):
        # Skutečně použitá cesta se vypisuje při startu; jinak nikdo nezjistí,
        # které nastavení vlastně běží.
        with DocasnaKonfigurace(platna_konfigurace()) as cesta:
            config = load(cesta)
            self.assertEqual(config["_meta"]["path"], str(cesta.resolve()))

    def test_otisk_se_meni_s_obsahem(self):
        # Verze v souboru se mění zřídka, hodnoty často. Otisk pozná i změnu,
        # u které nikdo číslo nezvýšil.
        zaklad = platna_konfigurace()
        zmeneny = platna_konfigurace()
        zmeneny["service"]["workers"] = 8

        with DocasnaKonfigurace(zaklad) as a, DocasnaKonfigurace(zmeneny) as b:
            self.assertNotEqual(
                load(a)["_meta"]["fingerprint"], load(b)["_meta"]["fingerprint"]
            )

    def test_stejny_obsah_da_stejny_otisk(self):
        with DocasnaKonfigurace(platna_konfigurace()) as a, \
             DocasnaKonfigurace(platna_konfigurace()) as b:
            self.assertEqual(
                load(a)["_meta"]["fingerprint"], load(b)["_meta"]["fingerprint"]
            )


class NeplatnaKonfiguraceNeprojde(unittest.TestCase):
    """Neznámý klíč je chyba, ne tiché ignorování."""

    def _ocekavej(self, config: object, *ocekavane_casti: str) -> str:
        """Načte konfiguraci, vyžádá si `ConfigError` a vrátí jeho text."""
        with DocasnaKonfigurace(config) as cesta:
            with self.assertRaises(ConfigError) as chycena:
                load(cesta)
        text = str(chycena.exception)
        for cast in ocekavane_casti:
            self.assertIn(cast, text)
        return text

    def test_neznamy_klic(self):
        # Obvykle je to překlep. Tiše ignorovaný překlep znamená, že běží jiné
        # nastavení, než si člověk myslí.
        config = platna_konfigurace()
        config["service"]["porrt"] = 42100
        self._ocekavej(config, "neznámý klíč", "porrt")

    def test_neznamy_klic_v_koreni(self):
        config = platna_konfigurace()
        config["neco_navic"] = True
        self._ocekavej(config, "neznámý klíč", "neco_navic")

    def test_chybejici_povinny_klic(self):
        config = platna_konfigurace()
        del config["service"]["port"]
        self._ocekavej(config, "chybí povinný klíč", "port")

    def test_chybejici_povinna_sekce(self):
        config = platna_konfigurace()
        del config["module"]
        self._ocekavej(config, "chybí povinný klíč", "module")

    def test_spatny_typ(self):
        config = platna_konfigurace()
        config["service"]["port"] = "42100"
        self._ocekavej(config, "service.port", "očekáván integer", "str")

    def test_bool_neprojde_jako_cislo(self):
        # `True` je v Pythonu instance `int` — bez zvláštní kontroly by prošlo.
        config = platna_konfigurace()
        config["service"]["workers"] = True
        self._ocekavej(config, "service.workers", "očekáván integer")

    def test_hodnota_mimo_vycet(self):
        config = platna_konfigurace()
        config["logging"]["level"] = "verbose"
        self._ocekavej(config, "logging.level", "verbose", "info", "debug")

    def test_hodnota_pod_minimem(self):
        config = platna_konfigurace()
        config["service"]["workers"] = 0
        self._ocekavej(config, "service.workers", "pod minimem")

    def test_hodnota_nad_maximem(self):
        config = platna_konfigurace()
        config["service"]["port"] = 70000
        self._ocekavej(config, "service.port", "nad maximem")

    def test_nula_neprojde_kde_musi_byt_kladne(self):
        config = platna_konfigurace()
        config["service"]["request_timeout_s"] = 0
        self._ocekavej(config, "request_timeout_s", "větší než")

    def test_vice_chyb_najednou(self):
        # Když je konfigurace špatně, je obvykle špatně víc věcí. Nahlásit jen
        # první znamená opravovat to na třikrát a mezi tím restartovat.
        config = platna_konfigurace()
        config["service"]["port"] = "ne číslo"
        config["service"]["neznamy"] = 1
        del config["runtime"]["stop_timeout_s"]

        text = self._ocekavej(config, "service.port", "neznamy", "stop_timeout_s")
        self.assertGreaterEqual(len(text.splitlines()), 4)

    def test_spatna_verze_konfigurace(self):
        config = platna_konfigurace()
        config["config_version"] = 99
        text = self._ocekavej(config, "config_version", "99")
        # Hláška musí říct, co se má stát — převést, ne načíst.
        self.assertIn("převést", text)

    def test_pravidlo_smerovani_bez_podminky(self):
        # Pravidlo jen s `to` by chytilo všechno a zastínilo výchozí proud.
        config = platna_konfigurace()
        config["module"]["routing"]["rules"] = [{"to": "data-persistent/x.jsonl"}]
        self._ocekavej(config, "rules[0]", "aspoň 2 klíčů")

    def test_okno_prohlizece_neni_mensi_nez_buffer_serveru(self):
        # Není to chyba schématu, ale nesmysl: server pošle při připojení víc
        # záznamů, než okno udrží, takže se část hned zahodí. Hlídá to test,
        # protože jako pravidlo schématu by to šlo napsat jen neohrabaně.
        config = load()
        watch = config["module"]["watch"]

        self.assertGreaterEqual(
            watch["window_records"],
            watch["buffer_records"],
            "window_records musí být aspoň jako buffer_records, jinak se část "
            "toho, co server pošle při připojení, hned zahodí",
        )

    def test_platne_pravidlo_smerovani_projde(self):
        config = platna_konfigurace()
        config["module"]["routing"]["rules"] = [
            {"malformed": True, "to": "data-persistent/malformed.jsonl"},
            {"component": "field", "to": "data-persistent/field.jsonl"},
        ]
        with DocasnaKonfigurace(config) as cesta:
            nactena = load(cesta)
        self.assertEqual(len(nactena["module"]["routing"]["rules"]), 2)


class NecitelnyNeboChybejiciSoubor(unittest.TestCase):
    """T-K4 část — chybějící vstup dá typovanou chybu, ne pád."""

    def test_chybejici_soubor(self):
        with self.assertRaises(ConfigError) as chycena:
            load("/cesta/ktera/neexistuje/cb-logger-config.json")
        self.assertIn("chybí konfigurace", str(chycena.exception))
        # Hláška musí říct kterou cestu zkoušel.
        self.assertIn("neexistuje", str(chycena.exception))

    def test_nevalidni_json(self):
        with DocasnaKonfigurace('{"config_version": 1,,}') as cesta:
            with self.assertRaises(ConfigError) as chycena:
                load(cesta)
        text = str(chycena.exception)
        self.assertIn("není platný JSON", text)
        # Bez řádku a sloupce se chyba v konfiguraci hledá očima.
        self.assertIn("řádek", text)

    def test_json_ktery_neni_objekt(self):
        with DocasnaKonfigurace("[1, 2, 3]") as cesta:
            with self.assertRaises(ConfigError) as chycena:
                load(cesta)
        self.assertIn("musí být JSON objekt", str(chycena.exception))


class CestySeResolvujiVuciModulu(unittest.TestCase):
    """Relativní cesty se počítají vůči adresáři modulu, ne vůči pracovnímu.

    Jinak by se chování měnilo podle toho, odkud se služba spustí — spuštění
    z jiného adresáře by tiše založilo druhou sadu dat.
    """

    def test_relativni_cesta_se_prevede(self):
        with DocasnaKonfigurace(platna_konfigurace()) as cesta:
            config = load(cesta)

        pid = Path(config["runtime"]["pid_file"])
        self.assertTrue(pid.is_absolute())
        self.assertEqual(pid, MODULE_DIR / "run" / "service.pid")

    def test_vnorena_cesta_se_prevede(self):
        with DocasnaKonfigurace(platna_konfigurace()) as cesta:
            config = load(cesta)

        self.assertEqual(
            Path(config["runtime"]["self_log"]["path"]),
            MODULE_DIR / "run" / "self.log",
        )

    def test_cesta_v_pravidle_smerovani_se_prevede(self):
        config = platna_konfigurace()
        config["module"]["routing"]["rules"] = [
            {"level": "debug", "to": "data-persistent/debug.jsonl"}
        ]
        with DocasnaKonfigurace(config) as cesta:
            nactena = load(cesta)

        self.assertEqual(
            Path(nactena["module"]["routing"]["rules"][0]["to"]),
            MODULE_DIR / "data-persistent" / "debug.jsonl",
        )

    def test_absolutni_cesta_zustane(self):
        # Kdo napsal absolutní cestu, ví, co dělá — obvykle míří na jiný disk.
        config = platna_konfigurace()
        config["module"]["storage"]["dir"] = "/var/log/conbond3"
        with DocasnaKonfigurace(config) as cesta:
            nactena = load(cesta)

        self.assertEqual(nactena["module"]["storage"]["dir"], "/var/log/conbond3")

    def test_puvodni_slovnik_se_nemeni(self):
        # Funkce, která vrátí hodnotu a zároveň změní, co dostala, se používá
        # špatně dřív nebo později.
        surova = platna_konfigurace()
        with DocasnaKonfigurace(surova) as cesta:
            load(cesta)
        self.assertEqual(surova["runtime"]["pid_file"], "run/service.pid")


class ValidatorPoznaRozbiteSchema(unittest.TestCase):
    """Vada SCHÉMATU se musí poznat od vady konfigurace.

    Dřív tu stál test, že validátor nemlčí nad klíčovým slovem, kterému
    nerozumí — ručně psaný uměl jen část Draft 7. S knihovnou
    `jsonschema` ten problém zmizel a zůstala potřeba opačná: rozbité
    schéma se jinak projeví jako podivná hláška o konfiguraci, která je
    ve skutečnosti v pořádku.
    """

    def test_rozbite_schema_je_hlasita_chyba(self):
        from cb_config import check_schema_supported

        with self.assertRaises(ConfigError) as chycena:
            check_schema_supported({"type": "objekt"})   # takový typ není

        self.assertIn("schéma", str(chycena.exception))

if __name__ == "__main__":
    unittest.main()
