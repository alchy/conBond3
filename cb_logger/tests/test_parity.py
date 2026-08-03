"""`T-K3` — shoda tváří: v procesu a přes síť musí vyjít totéž.

Modul má dvě tváře (README-MODULES.md § 1): `service.py` se volá přímo a `client.py`
přes REST. Kdyby se rozešly, přestane platit to, kvůli čemu je to rozdělené —
že test měří totéž, co běží v provozu.

Zkouší se obojí naráz: týž vstup se pošle oběma cestami do dvou samostatných
logovátek a porovná se, co z nich vypadne.
"""

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from cb_logger.api import make_api_server
from cb_logger.client import LogClient
from cb_logger.config import DEFAULT_CONFIG_PATH
from cb_logger.record import Result
from cb_logger.service import LoggerService

START = "2026-08-03T14:00:00.000Z"
PRIJATO = "2026-08-03T14:22:41.183Z"


def _config(adresar: Path) -> dict:
    """Sestaví konfiguraci mířící do dočasného adresáře."""
    config = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    config["_meta"] = {"path": "test", "fingerprint": "test"}
    config["service"]["port"] = 0
    modul = config["module"]
    modul["routing"]["default"] = str(adresar / "log.jsonl")
    modul["summary"]["path"] = str(adresar / "summary.json")
    modul["storage"]["dir"] = str(adresar)
    modul["storage"]["objects_dir"] = str(adresar / "objects")
    modul["objects"]["stream"] = str(adresar / "objects" / "objects.jsonl")
    return config


def _bez_casu(objekt: dict) -> dict:
    """Odstraní razítka, která se mezi dvěma běhy nutně liší.

    Porovnávat čas nemá smysl — jde o to, jestli se shoduje **obsah**, který
    obě cesty vyrobí. Kdyby se čas porovnával, test by selhával na tom
    jediném, co se lišit smí.
    """
    return {k: v for k, v in objekt.items() if k != "ts"}


class ShodaTvari(unittest.TestCase):
    """Táž data poslaná oběma cestami dají tentýž výsledek."""

    def _v_procesu(self, zaznamy: list[dict]) -> tuple[dict, list[dict]]:
        """Pošle záznamy přímo do `service.py` a vrátí (souhrn, zapsané řádky)."""
        with tempfile.TemporaryDirectory() as d:
            adr = Path(d)
            sluzba = LoggerService(_config(adr), started_at=START)
            try:
                sluzba.accept(zaznamy, received_ts=PRIJATO)
                souhrn = sluzba.summary()
            finally:
                sluzba.close()
            radky = [json.loads(r) for r in
                     (adr / "log.jsonl").read_text().splitlines() if r]
        return souhrn, radky

    def _pres_sit(self, zaznamy: list[dict]) -> tuple[dict, list[dict]]:
        """Pošle tytéž záznamy přes `client.py` a vrátí totéž."""
        with tempfile.TemporaryDirectory() as d:
            adr = Path(d)
            config = _config(adr)
            sluzba = LoggerService(config, started_at=START)
            server = make_api_server(sluzba, config)
            threading.Thread(target=server.serve_forever,
                             kwargs={"poll_interval": 0.01},
                             daemon=True).start()
            endpoint = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                klient = LogClient(component="field", endpoint=endpoint,
                                   flush_interval_ms=20)
                try:
                    for z in zaznamy:
                        klient.info(
                            method=z["method"], result=z["result"],
                            trace=z.get("trace"),
                            input=z.get("input"), output=z.get("output"),
                            duration_ms=z.get("duration_ms"),
                        )
                    konec = time.monotonic() + 3
                    while time.monotonic() < konec:
                        if sluzba.summary()["total"] >= len(zaznamy):
                            break
                        time.sleep(0.01)
                finally:
                    klient.close()
                souhrn = sluzba.summary()
            finally:
                server.shutdown()
                server.server_close()
                sluzba.close()
            radky = [json.loads(r) for r in
                     (adr / "log.jsonl").read_text().splitlines() if r]
        return souhrn, radky

    #: Vstup pokrývá všechny čtyři stavy, aby se shoda neověřovala jen
    #: na tom nejběžnějším.
    VZOREK = [
        {"component": "field", "method": "build_field", "result": "ok",
         "trace": "q-7f3a91", "input": {"sentences": 97, "radius": 2},
         "output": {"rows": 4213}, "duration_ms": 412},
        {"component": "field", "method": "match", "result": "empty",
         "trace": "q-7f3a91", "input": {"rows": 4213}, "output": {}},
        {"component": "field", "method": "compose", "result": "skipped",
         "trace": "q-7f3a91"},
        {"component": "field", "method": "parse", "result": "error",
         "trace": "q-7f3a91"},
    ]

    def test_souhrn_je_stejny(self):
        v_procesu, _ = self._v_procesu(self.VZOREK)
        pres_sit, _ = self._pres_sit(self.VZOREK)

        self.assertEqual(v_procesu["total"], pres_sit["total"])
        self.assertEqual(v_procesu["by_method"], pres_sit["by_method"])

    def test_zapsane_radky_jsou_stejne(self):
        _, v_procesu = self._v_procesu(self.VZOREK)
        _, pres_sit = self._pres_sit(self.VZOREK)

        self.assertEqual(
            [_bez_casu(r) for r in v_procesu],
            [_bez_casu(r) for r in pres_sit],
        )

    def test_poradi_zustava(self):
        # Determinismus je podmínka měřitelnosti: táž data a týž požadavek
        # musí dát tutéž odpověď včetně pořadí.
        _, v_procesu = self._v_procesu(self.VZOREK)
        _, pres_sit = self._pres_sit(self.VZOREK)

        self.assertEqual([r["method"] for r in v_procesu],
                         [r["method"] for r in pres_sit])

    def test_prazdno_zustane_prazdnem_obema_cestami(self):
        # Kdyby se `empty` cestou po síti změnilo na `error`, měření by
        # odměnilo právě tu chybu, kterou má chytat.
        vzorek = [{"component": "field", "method": "match", "result": "empty",
                   "trace": "q-1", "output": {}}]

        v_procesu, _ = self._v_procesu(vzorek)
        pres_sit, _ = self._pres_sit(vzorek)

        self.assertEqual(v_procesu["by_method"]["field.match"]["empty"], 1)
        self.assertEqual(pres_sit["by_method"]["field.match"]["empty"], 1)
        self.assertEqual(v_procesu["by_method"]["field.match"]["error"], 0)
        self.assertEqual(pres_sit["by_method"]["field.match"]["error"], 0)


class ShodaObjektu(unittest.TestCase):
    """Objektový log má taky dvě tváře a musí se shodovat stejně."""

    def test_objekt_je_stejny_obema_cestami(self):
        objekt = {"radius": 2, "rows": [{"tvar": "Soňa", "typ": "osoba"}]}

        with tempfile.TemporaryDirectory() as d:
            adr = Path(d)
            sluzba = LoggerService(_config(adr), started_at=START)
            try:
                sluzba.accept_objects([{
                    "component": "field", "method": "build_field",
                    "label": "pole", "object": objekt, "trace": "q-1",
                }], received_ts=PRIJATO)
                v_procesu = sluzba.recent_objects()[0]
            finally:
                sluzba.close()

        with tempfile.TemporaryDirectory() as d:
            adr = Path(d)
            config = _config(adr)
            sluzba = LoggerService(config, started_at=START)
            server = make_api_server(sluzba, config)
            threading.Thread(target=server.serve_forever,
                             kwargs={"poll_interval": 0.01},
                             daemon=True).start()
            try:
                klient = LogClient(
                    component="field",
                    endpoint=f"http://127.0.0.1:{server.server_address[1]}",
                    flush_interval_ms=20,
                )
                try:
                    klient.json(method="build_field", label="pole", trace="q-1",
                                  obj=objekt)
                    konec = time.monotonic() + 3
                    while time.monotonic() < konec:
                        if sluzba.recent_objects():
                            break
                        time.sleep(0.01)
                finally:
                    klient.close()
                pres_sit = sluzba.recent_objects()[0]
            finally:
                server.shutdown()
                server.server_close()
                sluzba.close()

        self.assertEqual(_bez_casu(v_procesu), _bez_casu(pres_sit))


if __name__ == "__main__":
    unittest.main()
