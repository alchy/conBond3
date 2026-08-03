"""Zkoušky datového typu záznamu.

Pokrývá `T-K1` (umí) a `T-K2` (přizná prázdno) pro převod z drátu: záznam,
který přijde v pořádku, se převede beze změny; záznam, který v pořádku není,
se **nezahodí a nevyhodí výjimku**, ale vrátí se označený.
"""

import unittest

from cb_logger.record import Level, LogRecord, Result, from_wire

# Pevný čas přijetí. Předává se do `from_wire` zvenčí schválně — funkce,
# která si sáhne na hodiny sama, nejde deterministicky otestovat.
PRIJATO = "2026-08-03T14:22:41.183Z"


def zaznam(**zmeny: object) -> dict:
    """Vrátí platný záznam z drátu, volitelně se změněnými poli.

    Proč pomocná funkce a ne konstanta: každý test potřebuje týž základ
    s jednou vadou. Kdyby se záznam psal v každém testu znovu, nebylo by
    z testu poznat, která vada se právě zkouší.

    Vstup:
        zmeny: pole, která se mají v základu přepsat. Hodnota `None` klíč
            odstraní — tím se testuje chybějící povinné pole.

    Výstup:
        Slovník připravený k předání do `from_wire`.
    """
    zaklad: dict = {
        "component": "field",
        "method": "build_field",
        "result": "ok",
        "trace": "q-7f3a91",
        "input": {"sentences": 97, "radius": 2},
        "output": {"rows": 4213},
        "duration_ms": 412,
    }
    for klic, hodnota in zmeny.items():
        if hodnota is None:
            zaklad.pop(klic, None)
        else:
            zaklad[klic] = hodnota
    return zaklad


class PlatnyZaznam(unittest.TestCase):
    """T-K1 — správný vstup dá správný výstup."""

    def test_projde_beze_zmeny(self):
        z = from_wire(zaznam(), received_ts=PRIJATO)

        self.assertFalse(z.malformed)
        self.assertIsNone(z.malformed_reason)
        self.assertEqual(z.component, "field")
        self.assertEqual(z.method, "build_field")
        self.assertEqual(z.result, Result.OK)
        self.assertEqual(z.trace, "q-7f3a91")
        self.assertEqual(z.duration_ms, 412)

    def test_chybejici_uroven_je_info(self):
        # Úroveň je nepovinná; většina záznamů je `info` a psát to pokaždé
        # by byl šum.
        z = from_wire(zaznam(), received_ts=PRIJATO)
        self.assertEqual(z.level, Level.INFO)

    def test_razitko_z_dratu_ma_prednost(self):
        # Komponenta ví, kdy se událost stala; logovátko ví jen, kdy záznam
        # dorazil — a mezi tím leží fronta a dávkování.
        z = from_wire(
            zaznam(ts="2026-08-03T14:00:00.000Z"), received_ts=PRIJATO
        )
        self.assertEqual(z.ts, "2026-08-03T14:00:00.000Z")

    def test_bez_razitka_se_pouzije_cas_prijeti(self):
        z = from_wire(zaznam(), received_ts=PRIJATO)
        self.assertEqual(z.ts, PRIJATO)

    def test_vsechny_vysledky_projdou(self):
        for vysledek in Result:
            with self.subTest(vysledek=vysledek.value):
                z = from_wire(zaznam(result=vysledek.value), received_ts=PRIJATO)
                self.assertFalse(z.malformed)
                self.assertEqual(z.result, vysledek)


class PrazdnoNeniChyba(unittest.TestCase):
    """T-K2 — prázdný výsledek je platný stav, ne chyba.

    Tohle je nejdůležitější zkouška celého modulu. Kdyby se `empty` chovalo
    jako `error`, měření by odměnilo právě tu chybu, kterou má chytat.
    """

    def test_stav_empty_neni_malformed(self):
        z = from_wire(zaznam(result="empty", output={}), received_ts=PRIJATO)

        self.assertFalse(z.malformed)
        self.assertEqual(z.result, Result.EMPTY)

    def test_prazdny_vystup_projde(self):
        z = from_wire(zaznam(output={}), received_ts=PRIJATO)

        self.assertFalse(z.malformed)
        self.assertEqual(z.output, {})

    def test_chybejici_vystup_projde(self):
        # Záznam z úrovně debug často výstup nemá — je to mezistav, ne výsledek.
        z = from_wire(zaznam(output=None), received_ts=PRIJATO)

        self.assertFalse(z.malformed)
        self.assertIsNone(z.output)

    def test_chybejici_stopa_neni_chyba(self):
        # Chybějící stopa je měřitelná díra v řetězu, ne neplatný záznam.
        z = from_wire(zaznam(trace=None), received_ts=PRIJATO)

        self.assertFalse(z.malformed)
        self.assertIsNone(z.trace)


class SpatnyZaznamSePrijmeAOznaci(unittest.TestCase):
    """Špatně tvarovaný záznam se uloží označený, nezahodí se.

    Záznam se posílá právě tehdy, když se něco děje. Odmítnout ho znamená
    přijít o stopu v okamžiku, kdy je nejcennější.
    """

    def test_nikdy_nevyhodi_vyjimku(self):
        for vstup in [None, 42, "text", [], {"co": "nesmysl"}, {}]:
            with self.subTest(vstup=repr(vstup)):
                z = from_wire(vstup, received_ts=PRIJATO)
                self.assertIsInstance(z, LogRecord)
                self.assertTrue(z.malformed)

    def test_neznamy_stav_je_oznacen_a_vyjmenuje_povolene(self):
        z = from_wire(zaznam(result="hotovo"), received_ts=PRIJATO)

        self.assertTrue(z.malformed)
        self.assertIn("hotovo", z.malformed_reason)
        # Hláška musí říct, co se čekalo — jinak se druhá strana neopraví.
        for povoleny in ("ok", "empty", "skipped", "error"):
            self.assertIn(povoleny, z.malformed_reason)

    def test_spatny_zaznam_ma_stav_error(self):
        # Špatně tvarovaný záznam je chyba ve volajícím, ne prázdný výsledek.
        z = from_wire(zaznam(result="hotovo"), received_ts=PRIJATO)
        self.assertEqual(z.result, Result.ERROR)

    def test_chybejici_povinne_pole(self):
        for pole in ("component", "method", "result"):
            with self.subTest(pole=pole):
                z = from_wire(zaznam(**{pole: None}), received_ts=PRIJATO)
                self.assertTrue(z.malformed)
                self.assertIn(pole, z.malformed_reason)

    def test_nezname_pole_se_ohlasi(self):
        # Neznámý klíč je obvykle překlep. Tiché ignorování znamená, že se
        # záznam tváří kompletně, ale chybí v něm to, co tam autor chtěl.
        z = from_wire(zaznam(vysledek="něco"), received_ts=PRIJATO)

        self.assertTrue(z.malformed)
        self.assertIn("vysledek", z.malformed_reason)

    def test_vice_vad_se_ohlasi_najednou(self):
        # Když komponenta posílá záznam ve špatném tvaru, je obvykle špatně
        # víc věcí. Nahlásit jen první znamená opravovat to na třikrát.
        z = from_wire(
            {"component": "field", "result": "hotovo", "input": "ne objekt"},
            received_ts=PRIJATO,
        )

        self.assertTrue(z.malformed)
        self.assertIn("method", z.malformed_reason)
        self.assertIn("hotovo", z.malformed_reason)
        self.assertIn("input", z.malformed_reason)

    def test_puvodni_obsah_zustane_pod_raw(self):
        puvodni = zaznam(result="hotovo")
        z = from_wire(puvodni, received_ts=PRIJATO)

        self.assertEqual(z.raw, puvodni)

    def test_spatny_zaznam_si_nechá_komponentu_kdyz_ji_ma(self):
        # Aby šlo v souhrnu poznat, KDO posílá nesmysly.
        z = from_wire(zaznam(result="hotovo"), received_ts=PRIJATO)
        self.assertEqual(z.component, "field")

    def test_bez_komponenty_je_otaznik(self):
        z = from_wire({"method": "m", "result": "ok"}, received_ts=PRIJATO)

        self.assertTrue(z.malformed)
        self.assertEqual(z.component, "?")

    def test_spatny_typ_trvani(self):
        z = from_wire(zaznam(duration_ms="412"), received_ts=PRIJATO)

        self.assertTrue(z.malformed)
        self.assertIn("duration_ms", z.malformed_reason)

    def test_bool_neni_trvani(self):
        # `True` je v Pythonu instance `int` — bez zvláštní kontroly by prošlo.
        z = from_wire(zaznam(duration_ms=True), received_ts=PRIJATO)

        self.assertTrue(z.malformed)
        self.assertIn("duration_ms", z.malformed_reason)


class VolnaHlaska(unittest.TestCase):
    """`message` — volný text pro člověka.

    Přibylo poté, co se ukázalo, že vývojář si hlášku cpe do `method`, protože
    volné pole nebylo. `method` má být jméno metody, aby šlo počítat souhrn
    podle komponenta × metoda × result; kdyby v něm byl volný text, byla by každá
    hláška vlastní řádek souhrnu a měření by ztratilo smysl.
    """

    def test_hlaska_projde(self):
        z = from_wire(zaznam(message="načteno 97 vět"), received_ts=PRIJATO)

        self.assertFalse(z.malformed)
        self.assertEqual(z.message, "načteno 97 vět")

    def test_hlaska_je_nepovinna(self):
        z = from_wire(zaznam(), received_ts=PRIJATO)

        self.assertFalse(z.malformed)
        self.assertIsNone(z.message)

    def test_bez_hlasky_se_klic_nezapise(self):
        objekt = from_wire(zaznam(), received_ts=PRIJATO).to_json_object()
        self.assertNotIn("message", objekt)

    def test_hlaska_stoji_hned_za_stavem(self):
        # V kukátku se čte jako první; v souboru má být na očích taky.
        objekt = from_wire(
            zaznam(message="něco"), received_ts=PRIJATO
        ).to_json_object()
        klice = list(objekt)
        self.assertEqual(klice[klice.index("result") + 1], "message")

    def test_hlaska_musi_byt_retezec(self):
        z = from_wire(zaznam(message={"ne": "objekt"}), received_ts=PRIJATO)

        self.assertTrue(z.malformed)
        self.assertIn("message", z.malformed_reason)

    def test_hlaska_neni_stopa(self):
        # Dvě různé věci: hláška je text pro člověka, stopa drží pohromadě
        # jeden průchod systémem. Kdyby se slily, přestalo by jít vyfiltrovat,
        # co se dělo při jedné otázce napříč moduly.
        z = from_wire(
            zaznam(message="hláška", trace="q-7f3a91"), received_ts=PRIJATO
        )

        self.assertEqual(z.message, "hláška")
        self.assertEqual(z.trace, "q-7f3a91")


class ZapisDoJson(unittest.TestCase):
    """Tvar, ve kterém záznam skončí v souboru."""

    def test_prazdna_pole_se_nezapisuji(self):
        # Log se čte očima a prázdné klíče v něm jsou šum.
        z = from_wire(
            {"component": "c", "method": "m", "result": "empty"},
            received_ts=PRIJATO,
        )
        objekt = z.to_json_object()

        self.assertNotIn("input", objekt)
        self.assertNotIn("output", objekt)
        self.assertNotIn("duration_ms", objekt)

    def test_stopa_se_zapise_i_kdyz_chybi(self):
        # Výjimka z pravidla výše: chybějící stopa musí být v záznamu vidět,
        # protože je to měřitelná díra v řetězu.
        z = from_wire(
            {"component": "c", "method": "m", "result": "ok"},
            received_ts=PRIJATO,
        )
        objekt = z.to_json_object()

        self.assertIn("trace", objekt)
        self.assertIsNone(objekt["trace"])

    def test_poradi_klicu_je_pevne(self):
        # Dva řádky logu vedle sebe pak jde porovnat okem, ne nástrojem.
        objekt = from_wire(zaznam(), received_ts=PRIJATO).to_json_object()

        self.assertEqual(
            list(objekt)[:6],
            ["ts", "level", "component", "method", "trace", "result"],
        )

    def test_vycty_jdou_do_json_jako_retezce(self):
        objekt = from_wire(zaznam(), received_ts=PRIJATO).to_json_object()

        self.assertEqual(objekt["level"], "info")
        self.assertEqual(objekt["result"], "ok")
        self.assertIsInstance(objekt["result"], str)

    def test_spatny_zaznam_nese_priznak_duvod_i_puvodni_obsah(self):
        objekt = from_wire(
            zaznam(result="hotovo"), received_ts=PRIJATO
        ).to_json_object()

        self.assertTrue(objekt["malformed"])
        self.assertIn("hotovo", objekt["malformed_reason"])
        self.assertEqual(objekt["raw"]["result"], "hotovo")

    def test_dobry_zaznam_priznak_nenese(self):
        objekt = from_wire(zaznam(), received_ts=PRIJATO).to_json_object()

        self.assertNotIn("malformed", objekt)
        self.assertNotIn("raw", objekt)

    def test_cely_zaznam_je_serializovatelny(self):
        import json

        for vstup in (zaznam(), zaznam(result="hotovo"), {"nesmysl": 1}):
            with self.subTest(vstup=repr(vstup)[:40]):
                objekt = from_wire(vstup, received_ts=PRIJATO).to_json_object()
                # Musí projít bez `default=` — co neprojde, neskončí v logu.
                json.dumps(objekt, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
