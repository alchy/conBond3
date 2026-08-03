"""Cache rozborů: JSONL na disku, index klíč → offset v paměti.

Cache je důvod, proč modul existuje jako služba, a druhý odběratel (trénink
vlastního modelu) rozhoduje o jejím tvaru — proto se ukládá všech deset
sloupců a klíč nese model i verzi tokenizéru (koncepce, § 1 a § 4).
"""

import tempfile
import unicodedata
import unittest
from pathlib import Path

from cb_udpipe import cache, conllu

TS = "2026-08-03T10:00:00.000Z"

VETA = conllu.Sentence(
    source="Soňa odjela z Prahy.",
    tokens=(
        conllu.Token(id=1, form="Soňa", lemma="Soňa", upos="PROPN",
                     feats={"Case": "Nom"}, head=2, deprel="nsubj"),
        conllu.Token(id=2, form="odjela", lemma="odjet", upos="VERB",
                     head=0, deprel="root"),
    ),
    sent_id="1",
)

VETA2 = conllu.Sentence(
    source="Jela do Liberce.",
    tokens=(conllu.Token(id=1, form="Jela", lemma="jet", upos="VERB",
                         head=0, deprel="root"),),
    sent_id="2",
)


class ZakladCache(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def otevri(self, *, model="cs_all", tokenizer="a91f3e"):
        c = cache.Cache(directory=self.dir, model=model, tokenizer=tokenizer)
        self.addCleanup(c.close)
        return c

    @property
    def soubor(self) -> Path:
        return self.dir / "cs_all.jsonl"


class TestZapisACteni(ZakladCache):

    def test_ulozi_a_vrati(self):
        c = self.otevri()
        c.put(VETA, ts=TS)
        self.assertEqual(c.get(VETA.source), VETA)

    def test_neznama_veta_vrati_none(self):
        """None znamená nemám, ne chybu — volající pak větu rozebere.
        Kdyby to byla výjimka, byl by nejčastější případ nejdražší."""
        self.assertIsNone(self.otevri().get("Tuhle větu neznám."))

    def test_zachova_vsechny_sloupce(self):
        """Cache je dlouhodobá sbírka; co se do ní nezapíše, se nedá
        dopočítat jinak než pustit rozbor znovu (§ 1 koncepce)."""
        c = self.otevri()
        c.put(VETA, ts=TS)
        t = c.get(VETA.source).tokens[0]
        self.assertEqual(t.feats, {"Case": "Nom"})
        self.assertEqual(t.deprel, "nsubj")
        self.assertEqual(t.head, 2)

    def test_zachova_viceslovne_tvary(self):
        veta = conllu.Sentence(
            source="Abys to věděl.",
            tokens=(conllu.Token(id=1, form="Aby"),
                    conllu.Token(id=2, form="bys")),
            multiword=(conllu.Multiword(id=(1, 2), form="Abys"),),
        )
        c = self.otevri()
        c.put(veta, ts=TS)
        self.assertEqual(c.get(veta.source).multiword[0].form, "Abys")

    def test_zapis_je_pripis_ne_prepis(self):
        """Jeden velký JSON by se musel při každé nové větě přepsat celý;
        conBond2 měl obdobu a při 70 MB to už bolelo (§ 7 koncepce)."""
        c = self.otevri()
        c.put(VETA, ts=TS)
        velikost = self.soubor.stat().st_size
        c.put(VETA2, ts=TS)
        self.assertGreater(self.soubor.stat().st_size, velikost)

    def test_jeden_radek_na_vetu(self):
        c = self.otevri()
        c.put(VETA, ts=TS)
        c.put(VETA2, ts=TS)
        radky = self.soubor.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(radky), 2)

    def test_soubor_je_citelny_ocima(self):
        """Vidět do dat bez nástroje je zásada § 19 politiky — při hledání
        chyby je to rozdíl mezi minutou a hodinou."""
        c = self.otevri()
        c.put(VETA, ts=TS)
        obsah = self.soubor.read_text(encoding="utf-8")
        self.assertIn("Soňa odjela z Prahy.", obsah)


class TestIndex(ZakladCache):

    def test_index_prezije_restart(self):
        """Index se staví při startu ze souboru; bez toho je cache po
        restartu prázdná, i když soubor data má."""
        c = self.otevri()
        c.put(VETA, ts=TS)
        c.close()
        self.assertEqual(self.otevri().get(VETA.source), VETA)

    def test_nfc_normalizace_klice(self):
        """Rozložené ě musí trefit tutéž větu jako složené. Totéž dělá sám
        server (unicodedata.normalize NFC), takže klíč odpovídá tomu,
        co se poslalo (§ 4 koncepce)."""
        c = self.otevri()
        c.put(VETA, ts=TS)
        rozlozene = unicodedata.normalize("NFD", VETA.source)
        self.assertIsNotNone(c.get(rozlozene))

    def test_opakovany_zapis_prepise_v_indexu(self):
        """Poslední zápis vyhrává. Starý řádek v souboru zůstane — je to
        append-only —, ale číst se musí ten novější."""
        c = self.otevri()
        c.put(VETA, ts=TS)
        jina = conllu.Sentence(
            source=VETA.source,
            tokens=(conllu.Token(id=1, form="ZMĚNA"),),
        )
        c.put(jina, ts=TS)
        self.assertEqual(c.get(VETA.source).tokens[0].form, "ZMĚNA")


class TestKlicNeseModelATokenizer(ZakladCache):
    """Rozbor bez modelu a verze tokenizéru není určený. Kdyby se vrátil
    rozbor jiné tokenizace, byla by to tichá záměna dat — přesně to, co
    INV-9 a § 14 politiky zakazují (§ 4 koncepce)."""

    def test_jina_verze_tokenizeru_neni_zasah(self):
        c = self.otevri(tokenizer="stara")
        c.put(VETA, ts=TS)
        c.close()
        self.assertIsNone(self.otevri(tokenizer="nova").get(VETA.source))

    def test_jiny_model_ma_vlastni_soubor(self):
        c = self.otevri(model="cs_all")
        c.put(VETA, ts=TS)
        c.close()
        druhy = self.otevri(model="en_ewt")
        self.assertIsNone(druhy.get(VETA.source))
        self.assertTrue((self.dir / "en_ewt.jsonl").exists()
                        or druhy.stats()["sentences"] == 0)

    def test_stary_zaznam_zustane_v_souboru(self):
        """Změna pravidel cache NEznehodnotí — staré záznamy zůstanou platné
        pro svou verzi a nové se doplní (§ 4 koncepce)."""
        c = self.otevri(tokenizer="stara")
        c.put(VETA, ts=TS)
        c.close()
        c2 = self.otevri(tokenizer="nova")
        c2.put(VETA, ts=TS)
        c2.close()
        radky = self.soubor.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(radky), 2)


class TestOdolnost(ZakladCache):

    def test_poskozeny_radek_se_preskoci_a_spocita(self):
        """Po pádu procesu je rozbitý nejvýš poslední řádek. Tiše se
        nezahazuje — rostoucí číslo je signál, že něco padá (§ 7 koncepce)."""
        self.soubor.write_text(
            '{"source":"A","model":"cs_all","tokenizer":"a91f3e",'
            '"tokens":[],"multiword":[],"format_version":1}\n'
            '{"nedopsan\n',
            encoding="utf-8",
        )
        c = self.otevri()
        self.assertEqual(c.stats()["corrupt"], 1)

    def test_poskozeny_radek_nebrani_cteni_zbytku(self):
        c = self.otevri()
        c.put(VETA, ts=TS)
        c.close()
        with self.soubor.open("a", encoding="utf-8") as f:
            f.write('{"rozbity\n')
        c2 = self.otevri()
        self.assertEqual(c2.get(VETA.source), VETA)
        self.assertEqual(c2.stats()["corrupt"], 1)

    def test_zaznam_bez_povinneho_klice_je_poskozeny(self):
        self.soubor.write_text('{"source":"A"}\n', encoding="utf-8")
        self.assertEqual(self.otevri().stats()["corrupt"], 1)

    def test_neexistujici_soubor_je_prazdna_cache(self):
        """Studený start není chyba."""
        c = self.otevri()
        self.assertEqual(c.stats()["sentences"], 0)
        self.assertIsNone(c.get("cokoli"))

    def test_adresar_se_zalozi(self):
        c = cache.Cache(directory=self.dir / "hloubeji" / "jeste",
                        model="m", tokenizer="t")
        self.addCleanup(c.close)
        c.put(VETA, ts=TS)
        self.assertTrue((self.dir / "hloubeji" / "jeste" / "m.jsonl").exists())


class TestStats(ZakladCache):

    def test_stats_nese_pocty(self):
        c = self.otevri()
        c.put(VETA, ts=TS)
        s = c.stats()
        self.assertEqual(s["sentences"], 1)
        self.assertEqual(s["corrupt"], 0)
        self.assertEqual(s["format_version"], cache.CACHE_FORMAT_VERSION)
        self.assertEqual(s["model"], "cs_all")
        self.assertEqual(s["tokenizer"], "a91f3e")

    def test_stats_nese_velikost(self):
        c = self.otevri()
        c.put(VETA, ts=TS)
        self.assertGreater(c.stats()["bytes"], 0)


if __name__ == "__main__":
    unittest.main()
