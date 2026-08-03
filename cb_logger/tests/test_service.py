"""Zkoušky doménové logiky logovátka — bez HTTP a bez spuštěné služby.

Krok 2 z pořadí stavby (README-MODULES.md § 16). Pokrývá `T-K1` (umí) a `T-K2`
(přizná prázdno) v procesu; síťová tvář se ověřuje v `test_api.py`, shoda
obou v `test_parity.py`.

Každý test si zakládá vlastní dočasný adresář a nikdy nesahá na provozní
`data-persistent/`.
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_logger.config import DEFAULT_CONFIG_PATH
from cb_logger.record import Result, from_wire
from cb_logger.service import LoggerService, Summary, Writer, now_iso, route

PRIJATO = "2026-08-03T14:22:41.183Z"
START = "2026-08-03T14:00:00.000Z"


def zaznam(**zmeny: object) -> dict:
    """Vrátí platný záznam z drátu, volitelně se změněnými poli."""
    zaklad: dict = {
        "component": "field",
        "method": "build_field",
        "result": "ok",
        "trace": "q-7f3a91",
    }
    for klic, hodnota in zmeny.items():
        if hodnota is None:
            zaklad.pop(klic, None)
        else:
            zaklad[klic] = hodnota
    return zaklad


class DocasnaSluzba:
    """Postaví službu nad dočasným adresářem a uklidí po sobě.

    Konfigurace vychází z provozní, jen se jí přepíšou cesty — aby se testoval
    tvar, který opravdu běží, a ne zjednodušená kopie, která se s ním rozejde.
    """

    def __init__(self, **module_prepis: object):
        self._prepis = module_prepis
        self._adresar: tempfile.TemporaryDirectory | None = None
        self.service: LoggerService | None = None
        self.dir: Path | None = None

    def __enter__(self) -> LoggerService:
        self._adresar = tempfile.TemporaryDirectory()
        self.dir = Path(self._adresar.name)

        config = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        modul = config["module"]
        modul["routing"]["default"] = str(self.dir / "log.jsonl")
        modul["summary"]["path"] = str(self.dir / "summary.json")
        modul["storage"]["dir"] = str(self.dir)
        for klic, hodnota in self._prepis.items():
            sekce, _, pole = klic.partition("__")
            if pole:
                modul[sekce][pole] = hodnota
            else:
                modul[sekce] = hodnota

        self.service = LoggerService(config, started_at=START)
        return self.service

    def __exit__(self, *_: object) -> None:
        if self.service is not None:
            self.service.close()
        if self._adresar is not None:
            self._adresar.cleanup()

    def radky(self, jmeno: str = "log.jsonl") -> list[dict]:
        """Přečte zapsané záznamy z jednoho JSONL souboru.

        Volá se **uvnitř** bloku `with` — po jeho opuštění je dočasný adresář
        uklizený a soubory neexistují.
        """
        soubor = self.dir / jmeno
        if not soubor.exists():
            return []
        return [
            json.loads(r) for r in soubor.read_text(encoding="utf-8").splitlines() if r
        ]

    def vsechny_radky(self, zaklad: str = "log") -> list[dict]:
        """Přečte záznamy z živého proudu i ze všech otočených souborů.

        Proč to testy potřebují: rotace nastává **po** zápisu, který strop
        překročil, takže poslední záznam běžně skončí v právě otočeném souboru.
        Test, který se dívá jen do `log.jsonl`, by na tom občas spadl — a test,
        který občas spadne, se za měsíc vypne.
        """
        radky: list[dict] = []
        for soubor in sorted(self.dir.glob(f"{zaklad}*.jsonl")):
            radky += [
                json.loads(r)
                for r in soubor.read_text(encoding="utf-8").splitlines()
                if r
            ]
        return radky


class CasovaZnacka(unittest.TestCase):
    """Tvar razítka. Bez milisekund by se stovka záznamů za sekundu neseřadila."""

    def test_tvar_je_iso_s_milisekundami_v_utc(self):
        t = now_iso()
        self.assertRegex(t, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

    def test_dve_volani_jsou_neklesajici(self):
        self.assertLessEqual(now_iso(), now_iso())


class Smerovac(unittest.TestCase):
    """Čistá funkce záznam → cesta. Testuje se bez zapisování."""

    def _zaznam(self, **zmeny):
        return from_wire(zaznam(**zmeny), received_ts=PRIJATO)

    def test_bez_pravidel_jde_vse_do_vychoziho_proudu(self):
        smerovani = {"default": "/log.jsonl", "rules": []}
        self.assertEqual(route(self._zaznam(), smerovani), "/log.jsonl")

    def test_pravidlo_na_komponentu(self):
        smerovani = {
            "default": "/log.jsonl",
            "rules": [{"component": "field", "to": "/field.jsonl"}],
        }
        self.assertEqual(route(self._zaznam(), smerovani), "/field.jsonl")
        self.assertEqual(
            route(self._zaznam(component="udpipe"), smerovani), "/log.jsonl"
        )

    def test_pravidlo_na_uroven(self):
        smerovani = {
            "default": "/log.jsonl",
            "rules": [{"level": "debug", "to": "/debug.jsonl"}],
        }
        self.assertEqual(
            route(self._zaznam(level="debug"), smerovani), "/debug.jsonl"
        )
        self.assertEqual(route(self._zaznam(), smerovani), "/log.jsonl")

    def test_pravidlo_na_spatne_tvarovany_zaznam(self):
        # Odklonit je stranou, aby hlavní proud zůstal čistý.
        smerovani = {
            "default": "/log.jsonl",
            "rules": [{"malformed": True, "to": "/malformed.jsonl"}],
        }
        self.assertEqual(
            route(self._zaznam(result="hotovo"), smerovani), "/malformed.jsonl"
        )
        self.assertEqual(route(self._zaznam(), smerovani), "/log.jsonl")

    def test_prvni_shoda_vyhrava(self):
        smerovani = {
            "default": "/log.jsonl",
            "rules": [
                {"component": "field", "to": "/prvni.jsonl"},
                {"component": "field", "to": "/druhy.jsonl"},
            ],
        }
        self.assertEqual(route(self._zaznam(), smerovani), "/prvni.jsonl")

    def test_podminky_v_pravidle_plati_soucasne(self):
        # Dvě podmínky znamenají „obojí", ne „kterákoli" — jinak by nešlo
        # zúžit pravidlo na debug záznamy jedné komponenty.
        smerovani = {
            "default": "/log.jsonl",
            "rules": [
                {"component": "field", "level": "debug", "to": "/oboji.jsonl"}
            ],
        }
        self.assertEqual(
            route(self._zaznam(level="debug"), smerovani), "/oboji.jsonl"
        )
        # Sedí komponenta, nesedí úroveň → nesmí chytit.
        self.assertEqual(route(self._zaznam(), smerovani), "/log.jsonl")
        # Sedí úroveň, nesedí komponenta → nesmí chytit.
        self.assertEqual(
            route(self._zaznam(component="udpipe", level="debug"), smerovani),
            "/log.jsonl",
        )


class PrijemZaznamu(unittest.TestCase):
    """T-K1 — dávka dorazí, uloží se a započítá."""

    def test_zaznam_se_zapise(self):
        with DocasnaSluzba() as sluzba:
            vysledek = sluzba.accept([zaznam()], received_ts=PRIJATO)

            self.assertEqual(vysledek["accepted"], 1)
            self.assertEqual(vysledek["malformed"], 0)

    def test_zapsany_radek_je_platny_json(self):
        s = DocasnaSluzba()
        with s as sluzba:
            sluzba.accept([zaznam()], received_ts=PRIJATO)
            radky = s.radky()

        self.assertEqual(len(radky), 1)
        self.assertEqual(radky[0]["component"], "field")
        self.assertEqual(radky[0]["result"], "ok")
        self.assertEqual(radky[0]["trace"], "q-7f3a91")

    def test_davka_se_zapise_v_poradi(self):
        s = DocasnaSluzba()
        with s as sluzba:
            sluzba.accept(
                [zaznam(method=f"m{i}") for i in range(5)], received_ts=PRIJATO
            )
            radky = s.radky()

        self.assertEqual([r["method"] for r in radky], [f"m{i}" for i in range(5)])

    def test_prazdna_davka_neni_chyba(self):
        # T-K2: prázdný vstup dá prázdný výsledek, ne chybu.
        with DocasnaSluzba() as sluzba:
            vysledek = sluzba.accept([], received_ts=PRIJATO)

        self.assertEqual(vysledek["accepted"], 0)
        self.assertNotIn("error", vysledek)

    def test_davka_ktera_neni_pole(self):
        with DocasnaSluzba() as sluzba:
            vysledek = sluzba.accept({"component": "x"}, received_ts=PRIJATO)

        self.assertEqual(vysledek["accepted"], 0)
        self.assertIn("error", vysledek)

    def test_spatny_zaznam_se_ulozi_oznaceny(self):
        s = DocasnaSluzba()
        with s as sluzba:
            vysledek = sluzba.accept([zaznam(result="hotovo")], received_ts=PRIJATO)
            radky = s.radky()

        self.assertEqual(vysledek["accepted"], 1)
        self.assertEqual(vysledek["malformed"], 1)
        self.assertTrue(radky[0]["malformed"])
        self.assertEqual(radky[0]["raw"]["result"], "hotovo")

    def test_spatny_zaznam_nezastavi_zbytek_davky(self):
        # Kdyby jeden špatný záznam shodil dávku, přišlo by se o záznamy
        # komponenty, která má zjevně problém — tedy o ty nejcennější.
        s = DocasnaSluzba()
        with s as sluzba:
            vysledek = sluzba.accept(
                [zaznam(), zaznam(result="hotovo"), zaznam(method="dalsi")],
                received_ts=PRIJATO,
            )
            radky = s.radky()

        self.assertEqual(vysledek["accepted"], 3)
        self.assertEqual(vysledek["malformed"], 1)
        self.assertEqual(len(radky), 3)

    def test_smerovani_rozdeli_proud(self):
        s = DocasnaSluzba()
        with s as sluzba:
            sluzba._routing["rules"] = [
                {"malformed": True, "to": str(s.dir / "malformed.jsonl")}
            ]
            sluzba.accept(
                [zaznam(), zaznam(result="hotovo")], received_ts=PRIJATO
            )

            # Čte se uvnitř bloku — po jeho opuštění je adresář uklizený.
            self.assertEqual(len(s.radky("log.jsonl")), 1)
            self.assertEqual(len(s.radky("malformed.jsonl")), 1)


class SouhrnPocitaAPrezijeRestart(unittest.TestCase):
    """Měření je základ hodnocení, takže čísla nesmí mizet při restartu."""

    def test_pocty_podle_stavu(self):
        with DocasnaSluzba() as sluzba:
            sluzba.accept(
                [
                    zaznam(result="ok"),
                    zaznam(result="ok"),
                    zaznam(result="empty"),
                    zaznam(result="error"),
                ],
                received_ts=PRIJATO,
            )
            souhrn = sluzba.summary()

        radek = souhrn["by_method"]["field.build_field"]
        self.assertEqual(radek["ok"], 2)
        self.assertEqual(radek["empty"], 1)
        self.assertEqual(radek["error"], 1)
        self.assertEqual(radek["skipped"], 0)
        self.assertEqual(souhrn["total"], 4)

    def test_prazdno_a_chyba_se_neslijou(self):
        # Nejdůležitější zkouška souhrnu. Kdyby se slily, měření by odměnilo
        # právě tu chybu, kterou má chytat.
        with DocasnaSluzba() as sluzba:
            sluzba.accept([zaznam(result="empty")], received_ts=PRIJATO)
            radek = sluzba.summary()["by_method"]["field.build_field"]

        self.assertEqual(radek["empty"], 1)
        self.assertEqual(radek["error"], 0)

    def test_malformed_se_pocita_zvlast(self):
        with DocasnaSluzba() as sluzba:
            sluzba.accept([zaznam(result="hotovo")], received_ts=PRIJATO)
            souhrn = sluzba.summary()

        self.assertEqual(souhrn["malformed"], 1)

    def test_zaznamy_bez_stopy_se_pocitaji(self):
        # Měřitelná díra v řetězu doložení.
        with DocasnaSluzba() as sluzba:
            sluzba.accept(
                [zaznam(trace=None), zaznam()], received_ts=PRIJATO
            )
            souhrn = sluzba.summary()

        self.assertEqual(souhrn["without_trace"], 1)

    def test_souhrn_prezije_restart(self):
        with tempfile.TemporaryDirectory() as adresar:
            cesta = str(Path(adresar) / "summary.json")

            prvni = Summary(path=cesta, started_at=START)
            prvni.add(from_wire(zaznam(), received_ts=PRIJATO))
            prvni.add(from_wire(zaznam(result="empty"), received_ts=PRIJATO))
            prvni.flush()

            druhy = Summary(path=cesta, started_at="2026-08-04T00:00:00.000Z")
            souhrn = druhy.snapshot()

        self.assertEqual(souhrn["total"], 2)
        self.assertEqual(souhrn["by_method"]["field.build_field"]["ok"], 1)
        # Původní „od kdy" se zachová — jinak by číslo tvrdilo, že vzniklo
        # za kratší dobu, než ve skutečnosti.
        self.assertEqual(souhrn["since"], START)

    def test_nesouhlasna_verze_formatu_se_odsune_stranou(self):
        # Tiché načtení podle špatného předpokladu vyrobí čísla, která vypadají
        # správně. Odsunutí stranou je hlasité a data se neztratí.
        with tempfile.TemporaryDirectory() as adresar:
            cesta = Path(adresar) / "summary.json"
            cesta.write_text(
                json.dumps({"format_version": 99, "total": 7}), encoding="utf-8"
            )

            souhrn = Summary(path=str(cesta), started_at=START).snapshot()

            self.assertEqual(souhrn["total"], 0)
            self.assertTrue((Path(adresar) / "summary.v99.json").exists())

    def test_poskozeny_soubor_zacne_od_nuly(self):
        with tempfile.TemporaryDirectory() as adresar:
            cesta = Path(adresar) / "summary.json"
            cesta.write_text("{tohle není JSON", encoding="utf-8")

            souhrn = Summary(path=str(cesta), started_at=START).snapshot()

        self.assertEqual(souhrn["total"], 0)

    def test_vynulovani_je_explicitni(self):
        with DocasnaSluzba() as sluzba:
            sluzba.accept([zaznam()], received_ts=PRIJATO)
            self.assertEqual(sluzba.summary()["total"], 1)

            sluzba.reset_summary()
            self.assertEqual(sluzba.summary()["total"], 0)


class RotaceARetence(unittest.TestCase):
    """Debug na plném korpusu udělá gigabajty, takže rotace není detail."""

    def test_soubor_se_otoci_pri_prekroceni(self):
        s = DocasnaSluzba(storage__rotate_max_bytes=1024)
        with s as sluzba:
            # Dost záznamů na překročení kilobajtu.
            for _ in range(30):
                sluzba.accept([zaznam(input={"x": "y" * 40})], received_ts=PRIJATO)

            otocene = list(s.dir.glob("log.*.jsonl"))

        self.assertGreaterEqual(len(otocene), 1)

    def test_po_otoceni_se_zapisuje_dal(self):
        s = DocasnaSluzba(storage__rotate_max_bytes=512)
        with s as sluzba:
            for _ in range(20):
                sluzba.accept([zaznam(input={"x": "y" * 40})], received_ts=PRIJATO)
            sluzba.accept([zaznam(method="po_rotaci")], received_ts=PRIJATO)
            # Napříč živým i otočenými soubory: rotace nastává po zápisu,
            # takže poslední záznam může ležet v tom právě otočeném.
            radky = s.vsechny_radky()

        self.assertTrue(any(r["method"] == "po_rotaci" for r in radky))

    def test_bez_prekroceni_se_neotaci(self):
        s = DocasnaSluzba(storage__rotate_max_bytes=1048576)
        with s as sluzba:
            sluzba.accept([zaznam()], received_ts=PRIJATO)

            self.assertEqual(list(s.dir.glob("log.*.jsonl")), [])

    def test_stare_otocene_soubory_se_mazou(self):
        with tempfile.TemporaryDirectory() as adresar:
            adr = Path(adresar)
            (adr / "log.20200101T000000.jsonl").write_text("{}\n", encoding="utf-8")
            (adr / "log.29991231T235959.jsonl").write_text("{}\n", encoding="utf-8")

            Writer(rotate_max_bytes=1, retention_days=30)._delete_expired(adr)

            self.assertFalse((adr / "log.20200101T000000.jsonl").exists())
            self.assertTrue((adr / "log.29991231T235959.jsonl").exists())

    def test_retence_nula_nemaze_nic(self):
        with tempfile.TemporaryDirectory() as adresar:
            adr = Path(adresar)
            stary = adr / "log.20200101T000000.jsonl"
            stary.write_text("{}\n", encoding="utf-8")

            Writer(rotate_max_bytes=1, retention_days=0)._delete_expired(adr)

            self.assertTrue(stary.exists())

    def test_neotocene_soubory_se_nemazou(self):
        # Pojistka proti tomu, aby mazání sáhlo na živý proud.
        with tempfile.TemporaryDirectory() as adresar:
            adr = Path(adresar)
            zivy = adr / "log.jsonl"
            zivy.write_text("{}\n", encoding="utf-8")

            Writer(rotate_max_bytes=1, retention_days=1)._delete_expired(adr)

            self.assertTrue(zivy.exists())


class SledovaciBuffer(unittest.TestCase):
    """Kruhový buffer pro nově připojený prohlížeč."""

    def test_posledni_zaznamy_jsou_k_dispozici(self):
        with DocasnaSluzba() as sluzba:
            sluzba.accept([zaznam(method="a"), zaznam(method="b")],
                          received_ts=PRIJATO)

            posledni = sluzba.recent()

        self.assertEqual([r["method"] for r in posledni], ["a", "b"])

    def test_buffer_ma_strop(self):
        s = DocasnaSluzba(watch__buffer_records=3)
        with s as sluzba:
            sluzba.accept(
                [zaznam(method=f"m{i}") for i in range(10)], received_ts=PRIJATO
            )
            posledni = sluzba.recent()

        self.assertEqual(len(posledni), 3)
        self.assertEqual([r["method"] for r in posledni], ["m7", "m8", "m9"])

    def test_odberatel_dostane_zaznam(self):
        prijate: list[dict] = []
        with DocasnaSluzba() as sluzba:
            sluzba.subscribe(prijate.append)
            sluzba.accept([zaznam()], received_ts=PRIJATO)

        self.assertEqual(len(prijate), 1)
        self.assertEqual(prijate[0]["component"], "field")

    def test_padly_odberatel_se_odhlasi_a_nezastavi_zapis(self):
        # Zavřená záložka nesmí ovlivnit zápis ani ostatní okna.
        def padа(_):
            raise RuntimeError("zavřená záložka")

        prijate: list[dict] = []
        s = DocasnaSluzba()
        with s as sluzba:
            sluzba.subscribe(padа)
            sluzba.subscribe(prijate.append)

            sluzba.accept([zaznam()], received_ts=PRIJATO)
            sluzba.accept([zaznam()], received_ts=PRIJATO)

            radky = s.radky()

        self.assertEqual(len(radky), 2)
        self.assertEqual(len(prijate), 2)

    def test_odhlaseny_odberatel_uz_nedostava(self):
        prijate: list[dict] = []
        with DocasnaSluzba() as sluzba:
            sluzba.subscribe(prijate.append)
            sluzba.accept([zaznam()], received_ts=PRIJATO)
            sluzba.unsubscribe(prijate.append)
            sluzba.accept([zaznam()], received_ts=PRIJATO)

        self.assertEqual(len(prijate), 1)


class Zdravi(unittest.TestCase):
    """Vypnutá funkcionalita musí být vidět — systém s vypnutou částí není tentýž."""

    def test_zdravi_hlasi_zapnute_casti(self):
        with DocasnaSluzba() as sluzba:
            zdravi = sluzba.health()

        self.assertEqual(zdravi["status"], "ok")
        self.assertIn("watch", zdravi["enabled"])
        self.assertEqual(zdravi["started_at"], START)

    def test_vypnuta_stranka_je_videt(self):
        s = DocasnaSluzba(watch__enabled=False)
        with s as sluzba:
            self.assertFalse(sluzba.health()["enabled"]["watch"])

    def test_pocty_zaznamu_ve_zdravi(self):
        with DocasnaSluzba() as sluzba:
            sluzba.accept(
                [zaznam(), zaznam(result="hotovo")], received_ts=PRIJATO
            )
            zdravi = sluzba.health()

        self.assertEqual(zdravi["records_total"], 2)
        self.assertEqual(zdravi["records_malformed"], 1)

    def test_posledni_chyba_se_pamatuje(self):
        with DocasnaSluzba() as sluzba:
            self.assertIsNone(sluzba.health()["last_error"])
            sluzba.note_error("disk plný")
            self.assertEqual(sluzba.health()["last_error"], "disk plný")


if __name__ == "__main__":
    unittest.main()
