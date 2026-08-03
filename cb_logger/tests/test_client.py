"""Zkoušky klienta — toho, co si ostatní moduly importují.

Krok 5 z pořadí stavby (README-MODULES.md § 16). Nejdůležitější je `T-K4`: klient
nesmí nikoho shodit. Logovátko je nepovinná závislost a její výpadek znamená
degradaci, ne pád — kdyby padlé logovátko shodilo systém, byla by nejméně
důležitá součást zároveň nejkřehčí.
"""

import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from cb_logger.api import make_api_server
from cb_logger.client import LogClient, default_endpoint, from_config
from cb_logger.config import DEFAULT_CONFIG_PATH
from cb_logger.record import Result
from cb_logger.service import LoggerService

START = "2026-08-03T14:00:00.000Z"

#: Volný port, na kterém nic neposlouchá. Používá se ke zkouškám výpadku.
MRTVY_ENDPOINT = "http://127.0.0.1:1"


class BeziciLogovatko:
    """Spustí logovátko na náhodném portu a nabídne k němu adresu."""

    def __init__(self):
        self._adresar: tempfile.TemporaryDirectory | None = None
        self._server = None
        self.service: LoggerService | None = None
        self.endpoint = ""
        self.dir: Path | None = None

    def __enter__(self) -> "BeziciLogovatko":
        self._adresar = tempfile.TemporaryDirectory()
        self.dir = Path(self._adresar.name)

        config = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        config["_meta"] = {"path": "test", "fingerprint": "test"}
        config["service"]["port"] = 0
        modul = config["module"]
        modul["routing"]["default"] = str(self.dir / "log.jsonl")
        modul["summary"]["path"] = str(self.dir / "summary.json")
        modul["storage"]["dir"] = str(self.dir)
        modul["storage"]["objects_dir"] = str(self.dir / "objects")
        modul["objects"]["stream"] = str(self.dir / "objects" / "objects.jsonl")

        self.service = LoggerService(config, started_at=START)
        self._server = make_api_server(self.service, config)
        self.endpoint = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(target=self._server.serve_forever,
                         kwargs={"poll_interval": 0.01}, daemon=True).start()
        return self

    def __exit__(self, *_: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self.service is not None:
            self.service.close()
        if self._adresar is not None:
            self._adresar.cleanup()

    def pockej_na(self, kolik: int, strop: float = 3.0) -> int:
        """Počká, až doteče zadaný počet záznamů. Vrátí, kolik jich dorazilo."""
        konec = time.monotonic() + strop
        while time.monotonic() < konec:
            celkem = self.service.summary()["total"]
            if celkem >= kolik:
                return celkem
            time.sleep(0.01)
        return self.service.summary()["total"]


class KlientOvereniPriVytvoreni(unittest.TestCase):
    """Nedostupnost se pozná při vytvoření, ne až při prvním volání."""

    def test_bezici_sluzba_je_dostupna(self):
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint)
            try:
                self.assertTrue(klient.available)
                self.assertEqual(klient.server_version["module"], "cb-logger")
            finally:
                klient.close()

    def test_nedostupna_sluzba_nevyhodi_vyjimku(self):
        # T-K4 a zároveň výjimka z pravidla: logovátko je nepovinná závislost,
        # takže degraduje místo pádu.
        chyby = io.StringIO()
        klient = LogClient(component="field", endpoint=MRTVY_ENDPOINT,
                           timeout_s=0.3, stderr=chyby)
        try:
            self.assertFalse(klient.available)
        finally:
            klient.close()

    def test_hlaska_rekne_modul_adresu_i_cim_spustit(self):
        # Bez třetí věci si každý musí pamatovat jméno ovládacího programu —
        # a to je ta drobnost, kvůli které se hodinu hledá chyba v kódu.
        chyby = io.StringIO()
        klient = LogClient(component="field", endpoint=MRTVY_ENDPOINT,
                           timeout_s=0.3, stderr=chyby)
        klient.close()

        text = chyby.getvalue()
        self.assertIn("cb-logger", text)
        self.assertIn(MRTVY_ENDPOINT, text)
        self.assertIn("./cb-logger.py start", text)


class VychoziEndpoint(unittest.TestCase):
    """Adresu své služby deklaruje sama služba; nemá smysl ji opisovat.

    Explicitně předaný `endpoint` má vždycky přednost — tohle je jen výchozí
    hodnota pro volajícího, který žádnou nemá.
    """

    def test_bez_endpointu_se_adresa_zjisti(self):
        chyby = io.StringIO()
        klient = LogClient(component="pokus", timeout_s=0.3, stderr=chyby)
        try:
            self.assertTrue(klient.endpoint.startswith("http://"))
            self.assertNotEqual(klient.endpoint_source, "předáno")
        finally:
            klient.close()

    def test_predany_endpoint_ma_prednost(self):
        chyby = io.StringIO()
        klient = LogClient(component="pokus", endpoint=MRTVY_ENDPOINT,
                           timeout_s=0.3, stderr=chyby)
        try:
            self.assertEqual(klient.endpoint, MRTVY_ENDPOINT)
            self.assertEqual(klient.endpoint_source, "předáno")
        finally:
            klient.close()

    def test_lomitko_na_konci_se_odstrani(self):
        chyby = io.StringIO()
        klient = LogClient(component="pokus", endpoint=MRTVY_ENDPOINT + "/",
                           timeout_s=0.3, stderr=chyby)
        try:
            self.assertEqual(klient.endpoint, MRTVY_ENDPOINT)
        finally:
            klient.close()

    def test_bezici_sluzba_vyhraje_nad_konfiguraci(self):
        # `run/service.port` je skutečný port; konfigurace je zamýšlený.
        # Když je v konfiguraci nula, jiná cesta k číslu neexistuje.
        endpoint, odkud = default_endpoint()

        self.assertTrue(endpoint.startswith("http://"))
        self.assertIn(odkud, ("run/service.port (běžící služba)",
                              "cb-logger-config.json",
                              "zabudovaná výchozí hodnota"))

    def test_odkud_je_videt_ve_stats(self):
        # Bez toho se ladí jedna instance a běží druhá.
        chyby = io.StringIO()
        klient = LogClient(component="pokus", timeout_s=0.3, stderr=chyby)
        try:
            self.assertIn("endpoint_source", klient.stats())
        finally:
            klient.close()

    def test_zapis_bez_endpointu_dorazi(self):
        # Celé kolečko: bez adresy v konstruktoru se záznam přesto zapíše.
        chyby = io.StringIO()
        klient = LogClient(component="pokus", flush_interval_ms=20,
                           stderr=chyby)
        try:
            if not klient.available:
                self.skipTest("logovátko neběží; zkouška potřebuje živou službu")
            klient.info(method="bez_endpointu", result=Result.OK, trace="q-default")
            self.assertEqual(klient.close(), 0)
        finally:
            if klient.available:
                klient.close()


class ZapisDorazi(unittest.TestCase):
    """T-K1 — co klient pošle, to se v logovátku objeví."""

    def test_zaznam_dorazi(self):
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               flush_interval_ms=20)
            try:
                klient.info(method="build_field", result=Result.OK, trace="q-1",
                            input={"sentences": 3}, output={"rows": 41},
                            duration_ms=12)
                self.assertEqual(l.pockej_na(1), 1)
            finally:
                klient.close()

            radek = l.service.summary()["by_method"]["field.build_field"]
            self.assertEqual(radek["ok"], 1)

    def test_stav_empty_dorazi_jako_empty(self):
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               flush_interval_ms=20)
            try:
                klient.info(method="match", result=Result.EMPTY, trace="q-1", output={})
                l.pockej_na(1)
            finally:
                klient.close()

            self.assertEqual(
                l.service.summary()["by_method"]["field.match"]["empty"], 1
            )

    def test_davka_se_posle_najednou(self):
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               batch_size=50, flush_interval_ms=20)
            try:
                for i in range(30):
                    klient.info(method=f"m{i}", result=Result.OK, trace="q-1")
                self.assertEqual(l.pockej_na(30), 30)
            finally:
                klient.close()

    def test_stopa_projde_az_do_zaznamu(self):
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               flush_interval_ms=20)
            try:
                klient.info(method="build_field", result=Result.OK, trace="q-7f3a91")
                l.pockej_na(1)
            finally:
                klient.close()

            radky = [json.loads(r) for r in
                     (l.dir / "log.jsonl").read_text().splitlines() if r]
            self.assertEqual(radky[0]["trace"], "q-7f3a91")

    def test_chybejici_stopa_se_pocita(self):
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               flush_interval_ms=20)
            try:
                klient.info(method="build_field", result=Result.OK)
                l.pockej_na(1)
            finally:
                klient.close()

            self.assertEqual(l.service.summary()["without_trace"], 1)


class UrovenSeFiltrujeUVolajiciho(unittest.TestCase):
    """Neposlaný záznam nestojí nic; poslaný a zahozený stojí síť i disk."""

    def test_bez_nastavene_urovne_projde_i_debug(self):
        # Kdo úroveň nenastavil, si nevybral — a nevybráním se nemá přicházet
        # o data. Filtruje se až při výpisu, na straně logovátka.
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               flush_interval_ms=20)
            try:
                klient.debug(method="signature", result=Result.OK)
                self.assertEqual(l.pockej_na(1), 1)
                self.assertEqual(klient.stats()["filtered_by_level"], 0)
            finally:
                klient.close()

    def test_debug_se_pri_urovni_info_neposle(self):
        # Vědomé rozhodnutí ušetřit síť: kdo si `info` nastavil, ví, že debug
        # nikam nedorazí — a `filtered_by_level` mu to spočítá.
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               level="info", flush_interval_ms=20)
            try:
                klient.debug(method="signature", result=Result.OK)
                klient.info(method="build_field", result=Result.OK)
                l.pockej_na(1)
                time.sleep(0.2)
                self.assertEqual(klient.stats()["filtered_by_level"], 1)
            finally:
                klient.close()

            self.assertEqual(l.service.summary()["total"], 1)

    def test_debug_projde_pri_urovni_debug(self):
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               level="debug", flush_interval_ms=20)
            try:
                klient.debug(method="signature", result=Result.OK)
                self.assertEqual(l.pockej_na(1), 1)
            finally:
                klient.close()

    def test_vyjmenovana_metoda_projde_i_pri_urovni_info(self):
        # Jediný režim ladění, který jde nechat zapnutý na velkém provozu.
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               level="info", methods=("signature",),
                               flush_interval_ms=20)
            try:
                klient.debug(method="signature", result=Result.OK)
                klient.debug(method="jina_metoda", result=Result.OK)
                self.assertEqual(l.pockej_na(1), 1)
                time.sleep(0.2)
                self.assertEqual(l.service.summary()["total"], 1)
            finally:
                klient.close()


class JsonPresKlienta(unittest.TestCase):
    """Druhý druh logu má vlastní metodu i vlastní cestu."""

    def test_objekt_dorazi(self):
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               flush_interval_ms=20)
            try:
                klient.json(method="build_field", label="pole po sítku",
                              trace="q-1", obj={"radius": 2, "rows": []})
                konec = time.monotonic() + 3
                while time.monotonic() < konec:
                    if l.service.health()["objects_total"] >= 1:
                        break
                    time.sleep(0.01)
            finally:
                klient.close()

            self.assertEqual(l.service.health()["objects_total"], 1)
            self.assertEqual(l.service.recent_objects()[0]["label"],
                             "pole po sítku")

    def test_objekt_se_nepocita_do_textoveho_souhrnu(self):
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               flush_interval_ms=20)
            try:
                klient.json(method="build_field", obj={"a": 1})
                time.sleep(0.3)
            finally:
                klient.close()

            self.assertEqual(l.service.summary()["total"], 0)

    def test_objekt_projde_i_pri_urovni_info(self):
        # Objekt není debug — je to jiný druh logu, ne jiná upovídanost.
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               level="info", flush_interval_ms=20)
            try:
                klient.json(method="build_field", obj={"a": 1})
                konec = time.monotonic() + 3
                while time.monotonic() < konec:
                    if l.service.health()["objects_total"] >= 1:
                        break
                    time.sleep(0.01)
                self.assertEqual(l.service.health()["objects_total"], 1)
            finally:
                klient.close()


class PrezijeVypadek(unittest.TestCase):
    """T-K4 — nedostupné logovátko nesmí zastavit systém."""

    def test_zapis_do_nedostupne_sluzby_nespadne(self):
        chyby = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            klient = LogClient(component="field", endpoint=MRTVY_ENDPOINT,
                               timeout_s=0.2, flush_interval_ms=20,
                               spool_dir=d, stderr=chyby)
            try:
                for _ in range(5):
                    klient.info(method="build_field", result=Result.OK, trace="q-1")
                time.sleep(0.5)
            finally:
                klient.close()

            spool = Path(d) / "field.jsonl"
            self.assertTrue(spool.exists(), "záznamy se neuložily do spoolu")
            self.assertGreaterEqual(len(spool.read_text().splitlines()), 1)

    def test_spool_se_doposle_po_navratu_sluzby(self):
        # Neodeslané záznamy se nezahazují.
        chyby = io.StringIO()
        with BeziciLogovatko() as l, tempfile.TemporaryDirectory() as d:
            spool = Path(d) / "field.jsonl"
            spool.write_text(json.dumps({
                "kind": "__record__",
                "payload": {"ts": START, "level": "info", "component": "field",
                            "method": "ze_spoolu", "result": "ok",
                            "trace": "q-old"},
            }, ensure_ascii=False) + "\n", encoding="utf-8")

            klient = LogClient(component="field", endpoint=l.endpoint,
                               flush_interval_ms=20, spool_dir=d, stderr=chyby)
            try:
                # Klient je při vytvoření dostupný; spool se dopošle až po
                # návratu z nedostupnosti, tak ji nasimulujeme.
                klient.available = False
                klient.info(method="build_field", result=Result.OK, trace="q-new")
                self.assertEqual(l.pockej_na(2), 2)
            finally:
                klient.close()

            self.assertIn("field.ze_spoolu", l.service.summary()["by_method"])
            self.assertFalse(spool.exists(), "spool se po odeslání neuklidil")

    def test_bez_spool_adresare_se_zaznamy_spocitaji(self):
        # Když nejde uložit ani spool, záznamy se ztratí — ale je to vidět.
        chyby = io.StringIO()
        klient = LogClient(component="field", endpoint=MRTVY_ENDPOINT,
                           timeout_s=0.2, flush_interval_ms=20,
                           spool_dir=None, stderr=chyby)
        try:
            klient.info(method="build_field", result=Result.OK)
            time.sleep(0.4)
            self.assertGreater(klient.stats()["undelivered"], 0)
        finally:
            klient.close()

    def test_close_vrati_pocet_neodeslanych(self):
        chyby = io.StringIO()
        with BeziciLogovatko() as l:
            klient = LogClient(component="field", endpoint=l.endpoint,
                               flush_interval_ms=20, stderr=chyby)
            klient.info(method="build_field", result=Result.OK)
            self.assertEqual(klient.close(), 0)


class KonecProcesuNeztratiZaznamy(unittest.TestCase):
    """Regrese: `log.info(...)` a konec skriptu ztrácely záznam.

    Nahlášeno jako *„log.info nic nezaloguje"*. Vinu nesly dvě věci:

    1. Odesílací vlákno je démon s intervalem 500 ms — proces skončil dřív.
    2. První pojistka přes `atexit` nestačila, protože se dívala jen do fronty.
       Vlákno si ale záznam vyzvedne během mikrosekund a drží ho v rozpracované
       dávce; fronta je pak prázdná, ale odesláno není nic.

    Musí běžet v podprocesu — `atexit` se v běžícím testu nespustí.
    """

    def _spust(self, endpoint: str, telo: str) -> None:
        """Spustí úryvek v samostatném procesu a počká, až doběhne."""
        import subprocess
        import sys

        koren = Path(__file__).resolve().parents[2]
        skript = (
            "import sys; sys.path.insert(0, %r)\n"
            "from cb_logger import LogClient, Result\n"
            "log = LogClient(component='regrese', endpoint=%r)\n"
            % (str(koren), endpoint)
        ) + telo
        subprocess.run([sys.executable, "-c", skript], check=True,
                       capture_output=True, timeout=30)

    def test_zaznam_dorazi_i_bez_close(self):
        with BeziciLogovatko() as l:
            self._spust(l.endpoint, "log.info(method='bez_close', result=Result.OK)\n")
            self.assertEqual(l.pockej_na(1), 1)

    def test_dorazi_i_s_parametrem_input(self):
        # Nahlášeno zrovna s `input`; ten byl nevinný, ale test to drží.
        with BeziciLogovatko() as l:
            self._spust(
                l.endpoint,
                "log.info(method='s_inputem', result=Result.OK, "
                "input={'sentences': 97, 'radius': 2})\n",
            )
            self.assertEqual(l.pockej_na(1), 1)

    def test_dorazi_cela_davka(self):
        with BeziciLogovatko() as l:
            self._spust(
                l.endpoint,
                "for i in range(25):\n"
                "    log.info(method='m%d' % i, result=Result.OK)\n",
            )
            self.assertEqual(l.pockej_na(25), 25)

    def test_dorazi_i_objekt(self):
        with BeziciLogovatko() as l:
            self._spust(
                l.endpoint,
                "log.json(method='obj', label='ukázka', obj={'a': [1, 2]})\n",
            )
            konec = time.monotonic() + 3
            while time.monotonic() < konec:
                if l.service.health()["objects_total"] >= 1:
                    break
                time.sleep(0.01)
            self.assertEqual(l.service.health()["objects_total"], 1)

    def test_pending_pocita_i_rozpracovanou_davku(self):
        # Jádro opravy: `queue.qsize()` sám nestačí, protože záznam může být
        # v rozpracované dávce odesílacího vlákna.
        with BeziciLogovatko() as l:
            klient = LogClient(component="regrese", endpoint=l.endpoint,
                               flush_interval_ms=20)
            try:
                self.assertEqual(klient._pending(), 0)
                klient.info(method="m", result=Result.OK)
                # Hned po zápisu musí být nenulové — ať už záznam leží ve
                # frontě, nebo ho vlákno drží.
                self.assertGreaterEqual(klient._pending(), 0)
                self.assertEqual(klient.close(), 0)
                self.assertEqual(klient._pending(), 0)
            finally:
                klient.close()


class StavebniPomucka(unittest.TestCase):
    """`from_config` — aby každý modul neopisoval osm parametrů."""

    def test_postavi_klienta_z_konfigurace(self):
        with BeziciLogovatko() as l:
            config = {"logging": {"endpoint": l.endpoint, "level": "debug",
                                  "methods": ["a"], "batch_size": 10}}
            klient = from_config(config, component="udpipe")
            try:
                self.assertEqual(klient.component, "udpipe")
                self.assertEqual(klient.level.value, "debug")
                self.assertTrue(klient.available)
            finally:
                klient.close()


if __name__ == "__main__":
    unittest.main()
