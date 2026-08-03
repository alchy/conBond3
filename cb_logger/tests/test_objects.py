"""Zkoušky druhého druhu logu — celý JSON objekt místo řádku textu.

Objektový záznam odpovídá na jinou otázku než textový: ne *co se stalo*, ale
*jak vypadala data*. Testy proto hlídají hlavně to, aby se odpověď na tu
otázku neztratila — objekt přes strop se ořízne a označí, ale neztratí se.
"""

import json
import tempfile
import unittest
from pathlib import Path

from cb_logger.config import DEFAULT_CONFIG_PATH
from cb_logger.objects import DEPTH_MARKER, ObjectRecord, from_wire
from cb_logger.service import LoggerService

PRIJATO = "2026-08-03T14:22:41.183Z"
START = "2026-08-03T14:00:00.000Z"

VOLNE = {"max_object_bytes": 1_000_000, "max_depth": 100}

#: Značka pro odebrání klíče. Bez ní by `None` znamenalo dvě různé věci —
#: „klíč tam není" a „hodnota je null" — a to je přesně ta záměna, kterou
#: má logovátko rozlišovat.
SMAZ = object()


def objekt(**zmeny: object) -> dict:
    """Vrátí platný objektový záznam z drátu.

    Vstup:
        zmeny: pole k přepsání. Hodnota `SMAZ` klíč odstraní; `None` ho
            nastaví na null, což je platný obsah.
    """
    zaklad: dict = {
        "component": "field",
        "method": "build_field",
        "label": "pole po sítku",
        "object": {"radius": 2, "rows": [{"tvar": "Soňa", "typ": "osoba"}]},
        "trace": "q-7f3a91",
    }
    for klic, hodnota in zmeny.items():
        if hodnota is SMAZ:
            zaklad.pop(klic, None)
        else:
            zaklad[klic] = hodnota
    return zaklad


class PlatnyObjekt(unittest.TestCase):
    """T-K1 — objekt projde a uloží se celý."""

    def test_projde_beze_zmeny(self):
        z = from_wire(objekt(), received_ts=PRIJATO, **VOLNE)

        self.assertFalse(z.malformed)
        self.assertFalse(z.truncated)
        self.assertFalse(z.depth_limited)
        self.assertEqual(z.object["radius"], 2)

    def test_stitek_chybi_pouzije_se_metoda(self):
        # Bez štítku by šlo poznat jen komponentu a metodu, a to u modulu,
        # který loguje tři různé struktury, nestačí. Metoda je aspoň něco.
        z = from_wire(objekt(label=SMAZ), received_ts=PRIJATO, **VOLNE)
        self.assertEqual(z.label, "build_field")

    def test_kind_chybi_pouzije_se_stitek(self):
        z = from_wire(objekt(), received_ts=PRIJATO, **VOLNE)
        self.assertEqual(z.to_json_object()["kind"], "pole po sítku")

    def test_velikost_se_zmeri(self):
        z = from_wire(objekt(), received_ts=PRIJATO, **VOLNE)
        self.assertGreater(z.bytes, 0)

    def test_prazdny_objekt_neni_chyba(self):
        # T-K2: prázdná struktura je platný výsledek, ne chybějící pole.
        z = from_wire(objekt(object={}), received_ts=PRIJATO, **VOLNE)

        self.assertFalse(z.malformed)
        self.assertEqual(z.object, {})

    def test_null_jako_objekt_neni_chyba(self):
        z = from_wire(objekt(object=None), received_ts=PRIJATO, **VOLNE)
        self.assertFalse(z.malformed)

    def test_pole_jako_objekt_projde(self):
        # Uvnitř záznamu smí být cokoli serializovatelného; JSON objekt musí
        # být obálka, ne obsah.
        z = from_wire(objekt(object=[1, 2, 3]), received_ts=PRIJATO, **VOLNE)

        self.assertFalse(z.malformed)
        self.assertEqual(z.object, [1, 2, 3])


class SpatnyObjektSePrijmeAOznaci(unittest.TestCase):
    """Objekt se loguje, když se člověk potřebuje podívat na data.

    Odmítnout ho znamená přijít o pohled v okamžiku, kdy je nejcennější.
    """

    def test_nikdy_nevyhodi_vyjimku(self):
        for vstup in [None, 42, "text", [], {}]:
            with self.subTest(vstup=repr(vstup)):
                z = from_wire(vstup, received_ts=PRIJATO, **VOLNE)
                self.assertIsInstance(z, ObjectRecord)
                self.assertTrue(z.malformed)

    def test_chybejici_object(self):
        # Chybějící klíč je chyba; `object: null` je platný obsah (viz výše).
        z = from_wire(objekt(object=SMAZ), received_ts=PRIJATO, **VOLNE)
        self.assertTrue(z.malformed)
        self.assertIn("object", z.malformed_reason)

    def test_chybejici_komponenta(self):
        z = from_wire({"method": "m", "object": {}},
                      received_ts=PRIJATO, **VOLNE)
        self.assertTrue(z.malformed)
        self.assertIn("component", z.malformed_reason)

    def test_nezname_pole(self):
        z = from_wire(objekt(vysledek="něco"), received_ts=PRIJATO, **VOLNE)
        self.assertTrue(z.malformed)
        self.assertIn("vysledek", z.malformed_reason)

    def test_puvodni_obsah_zustane(self):
        puvodni = {"method": "m", "object": {}}
        z = from_wire(puvodni, received_ts=PRIJATO, **VOLNE)
        self.assertEqual(z.raw, puvodni)


class StropVelikosti(unittest.TestCase):
    """Objekt přes strop se uloží oříznutý a označený, ne zahozený."""

    def test_velky_objekt_se_zkrati_a_oznaci(self):
        velky = {"vety": ["věta " + str(i) for i in range(5000)]}
        z = from_wire(objekt(object=velky), received_ts=PRIJATO,
                      max_object_bytes=4096, max_depth=100)

        self.assertTrue(z.truncated)
        self.assertFalse(z.malformed)  # zkrácení není chyba, je to mez
        self.assertTrue(z.object["_truncated"])
        self.assertGreater(z.object["_original_bytes"], 4096)

    def test_zkraceny_objekt_nese_nahled(self):
        # Náhled je text, ne oříznutý JSON: oříznutý JSON by byl neplatný
        # a kukátko by ho nerozbalilo.
        velky = {"vety": ["věta " + str(i) for i in range(5000)]}
        z = from_wire(objekt(object=velky), received_ts=PRIJATO,
                      max_object_bytes=4096, max_depth=100)

        self.assertIsInstance(z.object["_preview"], str)
        self.assertIn("věta 0", z.object["_preview"])

    def test_zaznam_o_puvodni_velikosti_zustane(self):
        # Bez toho by nešlo poznat, o kolik dat člověk přišel.
        velky = {"x": "y" * 20000}
        z = from_wire(objekt(object=velky), received_ts=PRIJATO,
                      max_object_bytes=1024, max_depth=100)

        self.assertGreater(z.bytes, 20000)

    def test_maly_objekt_se_nezkracuje(self):
        z = from_wire(objekt(), received_ts=PRIJATO,
                      max_object_bytes=1_000_000, max_depth=100)
        self.assertFalse(z.truncated)


class StropHloubky(unittest.TestCase):
    """Chrání kukátko před stromem, který se nedá rozbalit."""

    def _hluboky(self, uroven: int) -> dict:
        koren: dict = {}
        v = koren
        for _ in range(uroven):
            v["dal"] = {}
            v = v["dal"]
        v["dno"] = "sem se to nemá dostat"
        return koren

    def test_hluboka_struktura_se_orizne(self):
        z = from_wire(objekt(object=self._hluboky(30)), received_ts=PRIJATO,
                      max_object_bytes=1_000_000, max_depth=5)

        self.assertTrue(z.depth_limited)
        self.assertFalse(z.malformed)

    def test_na_dne_je_znacka(self):
        z = from_wire(objekt(object=self._hluboky(30)), received_ts=PRIJATO,
                      max_object_bytes=1_000_000, max_depth=5)

        v = z.object
        hloubka = 0
        while isinstance(v, dict) and "dal" in v:
            v = v["dal"]
            hloubka += 1
        self.assertEqual(v, DEPTH_MARKER)
        self.assertEqual(hloubka, 5)

    def test_mělká_struktura_se_nerezа(self):
        z = from_wire(objekt(object={"a": {"b": 1}}), received_ts=PRIJATO,
                      max_object_bytes=1_000_000, max_depth=10)
        self.assertFalse(z.depth_limited)

    def test_hloubka_v_poli_se_taky_orizne(self):
        z = from_wire(objekt(object=[[[[["hluboko"]]]]]), received_ts=PRIJATO,
                      max_object_bytes=1_000_000, max_depth=2)
        self.assertTrue(z.depth_limited)

    def test_cyklicka_struktura_neshodi_zapis(self):
        # Pojistka: cyklus by `json.dumps` zacyklil. Oříznutí hloubky ho
        # utne dřív, než se na serializaci dojde.
        cyklus: dict = {}
        cyklus["ja"] = cyklus

        z = from_wire(objekt(object=cyklus), received_ts=PRIJATO,
                      max_object_bytes=1_000_000, max_depth=8)

        self.assertTrue(z.depth_limited)
        json.dumps(z.to_json_object(), ensure_ascii=False)


class ObjektyVeSluzbe(unittest.TestCase):
    """Vlastní proud, vlastní buffer, vlastní odběratelé."""

    def _sluzba(self):
        adresar = tempfile.TemporaryDirectory()
        adr = Path(adresar.name)
        config = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        modul = config["module"]
        modul["routing"]["default"] = str(adr / "log.jsonl")
        modul["summary"]["path"] = str(adr / "summary.json")
        modul["storage"]["dir"] = str(adr)
        modul["storage"]["objects_dir"] = str(adr / "objects")
        modul["objects"]["stream"] = str(adr / "objects" / "objects.jsonl")
        return adresar, adr, LoggerService(config, started_at=START)

    def test_objekt_se_zapise_do_vlastniho_proudu(self):
        # Mísit objekty s textem v jednom souboru znamená, že se ani jedno
        # nedá číst.
        adresar, adr, sluzba = self._sluzba()
        try:
            sluzba.accept_objects([objekt()], received_ts=PRIJATO)
            sluzba.close()

            proud = adr / "objects" / "objects.jsonl"
            self.assertTrue(proud.exists())
            self.assertFalse((adr / "log.jsonl").exists())
        finally:
            adresar.cleanup()

    def test_pocty_se_vraci(self):
        adresar, _, sluzba = self._sluzba()
        try:
            vysledek = sluzba.accept_objects(
                [objekt(), {"method": "m"}], received_ts=PRIJATO
            )
            self.assertEqual(vysledek["accepted"], 2)
            self.assertEqual(vysledek["malformed"], 1)
        finally:
            sluzba.close()
            adresar.cleanup()

    def test_davka_ktera_neni_pole(self):
        adresar, _, sluzba = self._sluzba()
        try:
            vysledek = sluzba.accept_objects({"a": 1}, received_ts=PRIJATO)
            self.assertIn("error", vysledek)
            self.assertEqual(vysledek["accepted"], 0)
        finally:
            sluzba.close()
            adresar.cleanup()

    def test_objekty_maji_vlastni_odberatele(self):
        # Kukátko na text nesmí dostat objekty a naopak — jsou to dva různé
        # pohledy na dvě různá data.
        adresar, _, sluzba = self._sluzba()
        try:
            texty: list = []
            objekty: list = []
            sluzba.subscribe(texty.append)
            sluzba.subscribe_objects(objekty.append)

            sluzba.accept_objects([objekt()], received_ts=PRIJATO)

            self.assertEqual(len(objekty), 1)
            self.assertEqual(len(texty), 0)
        finally:
            sluzba.close()
            adresar.cleanup()

    def test_objekty_se_nepocitaji_do_textoveho_souhrnu(self):
        adresar, _, sluzba = self._sluzba()
        try:
            sluzba.accept_objects([objekt()], received_ts=PRIJATO)
            self.assertEqual(sluzba.summary()["total"], 0)
            self.assertEqual(sluzba.health()["objects_total"], 1)
        finally:
            sluzba.close()
            adresar.cleanup()

    def test_buffer_pro_kukatko(self):
        adresar, _, sluzba = self._sluzba()
        try:
            sluzba.accept_objects(
                [objekt(label="a"), objekt(label="b")], received_ts=PRIJATO
            )
            posledni = sluzba.recent_objects()

            self.assertEqual([o["label"] for o in posledni], ["a", "b"])
        finally:
            sluzba.close()
            adresar.cleanup()

    def test_zdravi_hlasi_zkracene(self):
        adresar, _, sluzba = self._sluzba()
        try:
            sluzba._objects_cfg = dict(sluzba._objects_cfg,
                                       max_object_bytes=256)
            sluzba.accept_objects(
                [objekt(object={"x": "y" * 5000})], received_ts=PRIJATO
            )
            self.assertEqual(sluzba.health()["objects_truncated"], 1)
        finally:
            sluzba.close()
            adresar.cleanup()


if __name__ == "__main__":
    unittest.main()
