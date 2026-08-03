"""Zkoušky REST kontraktu.

Krok 3 z pořadí stavby (README-MODULES.md § 16). Testy si službu spustí samy na portu
`0`, takže neobsazují pevná čísla a mohou běžet vedle provozní služby.

Ověřuje se kontrakt, ne doména: že vstup i výstup jsou JSON objekty, že chyba
má typ, že návratové kódy odpovídají tabulce v § 7. Co která hodnota znamená,
se ověřuje v `test_service.py`.
"""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from cb_logger import __version__
from cb_logger.api import make_api_server
from cb_logger.config import DEFAULT_CONFIG_PATH
from cb_logger.service import LoggerService

START = "2026-08-03T14:00:00.000Z"


class BeziciSluzba:
    """Spustí REST službu na náhodném volném portu a po sobě ji uklidí."""

    def __init__(self, **module_prepis: object):
        self._prepis = module_prepis
        self._adresar: tempfile.TemporaryDirectory | None = None
        self._server = None
        self._vlakno: threading.Thread | None = None
        self.service: LoggerService | None = None
        self.port: int = 0

    def __enter__(self) -> "BeziciSluzba":
        self._adresar = tempfile.TemporaryDirectory()
        adr = Path(self._adresar.name)

        config = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        config["_meta"] = {"path": str(adr / "cb-logger-config.json"),
                           "fingerprint": "test0000test"}
        # Port 0 znamená "přidělí systém" — testy tak neobsazují pevná čísla.
        config["service"]["port"] = 0
        modul = config["module"]
        modul["routing"]["default"] = str(adr / "log.jsonl")
        modul["summary"]["path"] = str(adr / "summary.json")
        modul["storage"]["dir"] = str(adr)
        for klic, hodnota in self._prepis.items():
            sekce, _, pole = klic.partition("__")
            if pole:
                modul[sekce][pole] = hodnota

        self.service = LoggerService(config, started_at=START)
        self._server = make_api_server(self.service, config)
        self.port = self._server.server_address[1]
        # Krátký interval kontroly: `shutdown()` čeká, až si ho `serve_forever`
        # všimne, a výchozích 0,5 s by z každého testu udělalo půlsekundu
        # čekání. V provozu na tom nezáleží, tady na tom záleží hodně —
        # pomalé testy se přestanou pouštět.
        self._vlakno = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        self._vlakno.start()
        return self

    def __exit__(self, *_: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self.service is not None:
            self.service.close()
        if self._adresar is not None:
            self._adresar.cleanup()

    # -- volání ------------------------------------------------------------

    def get(self, cesta: str) -> tuple[int, dict]:
        return self._call("GET", cesta, None)

    def post(self, cesta: str, telo: object) -> tuple[int, dict]:
        return self._call("POST", cesta, telo)

    def _call(self, metoda: str, cesta: str, telo: object) -> tuple[int, dict]:
        """Zavolá službu a vrátí dvojici (stavový kód, tělo odpovědi)."""
        data = None
        if telo is not None:
            data = (telo if isinstance(telo, (bytes, str))
                    else json.dumps(telo, ensure_ascii=False))
            data = data.encode("utf-8") if isinstance(data, str) else data

        pozadavek = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{cesta}", data=data, method=metoda,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(pozadavek, timeout=5) as odpoved:
                return odpoved.status, json.loads(odpoved.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")


def zaznam(**zmeny: object) -> dict:
    zaklad: dict = {
        "component": "field",
        "method": "build_field",
        "result": "ok",
        "trace": "q-7f3a91",
    }
    zaklad.update({k: v for k, v in zmeny.items() if v is not None})
    for klic, hodnota in zmeny.items():
        if hodnota is None:
            zaklad.pop(klic, None)
    return zaklad


class Version(unittest.TestCase):
    """`/version` stojí mimo verzování schválně.

    Kdo se ptá na verzi, ještě neví, kterou verzi rozhraní má volat — kdyby
    `/version` žilo pod `/v1/`, klient by musel znát verzi, aby zjistil verzi.
    """

    def test_odpovida_bez_prefixu_verze(self):
        with BeziciSluzba() as s:
            kod, telo = s.get("/version")

        self.assertEqual(kod, 200)
        self.assertEqual(telo["module"], "cb-logger")
        self.assertEqual(telo["version"], __version__)

    def test_hlasi_ktere_verze_rozhrani_obsluhuje(self):
        with BeziciSluzba() as s:
            _, telo = s.get("/version")

        self.assertIn("v1", telo["api"])

    def test_nese_verzi_konfigurace_a_interpretu(self):
        # Jedno .venv má být všude stejné a tohle to ověří.
        with BeziciSluzba() as s:
            _, telo = s.get("/version")

        self.assertEqual(telo["config_version"], 1)
        self.assertTrue(telo["python"].startswith("3.11"))


class PovinneBody(unittest.TestCase):
    """K-4 — health, config a summary odpovídají."""

    def test_health(self):
        with BeziciSluzba() as s:
            kod, telo = s.get("/v1/health")

        self.assertEqual(kod, 200)
        self.assertEqual(telo["status"], "ok")
        self.assertIn("enabled", telo)

    def test_config_vraci_pouzitou_cestu(self):
        # Bez toho nikdo nezjistí, které nastavení vlastně běží.
        with BeziciSluzba() as s:
            kod, telo = s.get("/v1/config")

        self.assertEqual(kod, 200)
        self.assertTrue(telo["path"].endswith("cb-logger-config.json"))
        self.assertEqual(telo["fingerprint"], "test0000test")
        self.assertEqual(telo["config"]["service"]["host"], "127.0.0.1")

    def test_summary(self):
        with BeziciSluzba() as s:
            kod, telo = s.get("/v1/summary")

        self.assertEqual(kod, 200)
        self.assertEqual(telo["total"], 0)
        self.assertIn("by_method", telo)

    def test_lomitko_na_konci_nevadi(self):
        with BeziciSluzba() as s:
            self.assertEqual(s.get("/v1/health/")[0], 200)


class ZapisZaznamu(unittest.TestCase):
    """T-K1 přes síť."""

    def test_davka_se_prijme(self):
        with BeziciSluzba() as s:
            kod, telo = s.post("/v1/records", {"records": [zaznam()]})

        self.assertEqual(kod, 200)
        self.assertEqual(telo["accepted"], 1)
        self.assertEqual(telo["malformed"], 0)

    def test_zapis_se_projevi_v_souhrnu(self):
        with BeziciSluzba() as s:
            s.post("/v1/records", {"records": [zaznam(), zaznam(result="empty")]})
            _, souhrn = s.get("/v1/summary")

        self.assertEqual(souhrn["total"], 2)
        radek = souhrn["by_method"]["field.build_field"]
        self.assertEqual(radek["ok"], 1)
        self.assertEqual(radek["empty"], 1)

    def test_prazdna_davka_neni_chyba(self):
        # T-K2 přes síť: prázdný vstup dá 200 s nulou, ne 400 a ne 500.
        with BeziciSluzba() as s:
            kod, telo = s.post("/v1/records", {"records": []})

        self.assertEqual(kod, 200)
        self.assertEqual(telo["accepted"], 0)

    def test_spatne_tvarovany_zaznam_se_prijme(self):
        # Přijme a označí. Odmítnout by znamenalo přijít o stopu právě od
        # komponenty, která má problém.
        with BeziciSluzba() as s:
            kod, telo = s.post("/v1/records",
                               {"records": [zaznam(result="hotovo")]})

        self.assertEqual(kod, 200)
        self.assertEqual(telo["accepted"], 1)
        self.assertEqual(telo["malformed"], 1)

    def test_vynulovani_souhrnu(self):
        with BeziciSluzba() as s:
            s.post("/v1/records", {"records": [zaznam()]})
            kod, telo = s.post("/v1/summary/reset", {})

        self.assertEqual(kod, 200)
        self.assertEqual(telo["total"], 0)


class ChybaMaTyp(unittest.TestCase):
    """Chyba má typ, ne jen text. Podle textu se volající rozhodovat nemůže."""

    def _chyba(self, odpoved: tuple[int, dict]) -> dict:
        kod, telo = odpoved
        self.assertIn("error", telo, f"odpověď {kod} nemá klíč error")
        self.assertIn("type", telo["error"])
        self.assertIn("message", telo["error"])
        return telo["error"]

    def test_neznama_cesta_je_404_a_vyjmenuje_znama(self):
        with BeziciSluzba() as s:
            kod, telo = s.get("/v1/neexistuje")

        self.assertEqual(kod, 404)
        chyba = self._chyba((kod, telo))
        self.assertEqual(chyba["type"], "unknown_path")
        # Hláška musí říct, co existuje — jinak se hádá.
        self.assertIn("/v1/health", chyba["detail"]["known"])

    def test_nevalidni_json_je_400(self):
        with BeziciSluzba() as s:
            kod, telo = s.post("/v1/records", "{tohle není json")

        self.assertEqual(kod, 400)
        self.assertEqual(self._chyba((kod, telo))["type"], "invalid_json")

    def test_telo_ktere_neni_objekt_je_400(self):
        # Vstup i výstup je vždy JSON objekt, ne pole.
        with BeziciSluzba() as s:
            kod, telo = s.post("/v1/records", [zaznam()])

        self.assertEqual(kod, 400)
        chyba = self._chyba((kod, telo))
        self.assertEqual(chyba["type"], "not_an_object")
        self.assertIn("records", chyba["detail"]["expected"])

    def test_records_ktere_nejsou_pole_je_400(self):
        with BeziciSluzba() as s:
            kod, telo = s.post("/v1/records", {"records": "ne pole"})

        self.assertEqual(kod, 400)
        self.assertEqual(self._chyba((kod, telo))["type"], "invalid_records")

    def test_prilis_velky_pozadavek_je_413(self):
        # Limit platí i pro volání z vlastního systému.
        with BeziciSluzba() as s:
            velky = {"records": [zaznam(input={"x": "y" * 3000})] * 5}
            s._prepis = {}
            kod, telo = self._s_malym_stropem(s, velky)

        self.assertEqual(kod, 413)
        self.assertEqual(self._chyba((kod, telo))["type"], "too_large")

    def _s_malym_stropem(self, s: BeziciSluzba, telo: object):
        """Sníží strop za běhu a pošle požadavek.

        Konfigurace je týž slovník, který drží server, takže změna se projeví
        okamžitě — v testu je to pohodlnější než zvedat druhou službu.
        """
        s._server.config["service"]["max_request_bytes"] = 1024
        return s.post("/v1/records", telo)


class OdpovedJeSerializovatelna(unittest.TestCase):
    """Odpověď musí projít JSON kolečkem beze ztráty."""

    def test_vsechny_body_vraci_json_objekt(self):
        with BeziciSluzba() as s:
            s.post("/v1/records", {"records": [zaznam()]})
            for cesta in ("/version", "/v1/health", "/v1/config", "/v1/summary"):
                with self.subTest(cesta=cesta):
                    kod, telo = s.get(cesta)
                    self.assertEqual(kod, 200)
                    self.assertIsInstance(telo, dict)
                    # Musí projít bez `default=` — co neprojde, neodejde ven.
                    json.dumps(telo, ensure_ascii=False)


class Soubeh(unittest.TestCase):
    """Služba je vícevláknová; zápis z víc vláken nesmí nic ztratit."""

    def test_soubezny_zapis_nic_neztrati(self):
        with BeziciSluzba() as s:
            def posli():
                for _ in range(20):
                    s.post("/v1/records", {"records": [zaznam()]})

            vlakna = [threading.Thread(target=posli) for _ in range(4)]
            for v in vlakna:
                v.start()
            for v in vlakna:
                v.join()

            _, souhrn = s.get("/v1/summary")

        self.assertEqual(souhrn["total"], 80)


if __name__ == "__main__":
    unittest.main()
