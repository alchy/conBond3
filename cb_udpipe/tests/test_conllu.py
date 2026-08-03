"""Čtení a psaní CoNLL-U.

Testuje se nad zmraženými daty ze skutečného UDPipe (`data/vzorek.conllu`).
Data generovaná při běhu testu by neřekla, jestli se změnilo chování, nebo
vstup (README-MODULES.md § 13).
"""

import unittest
from pathlib import Path

from cb_udpipe import conllu

VZOREK = (Path(__file__).parent / "data" / "vzorek.conllu").read_text(
    encoding="utf-8"
)


class TestParse(unittest.TestCase):

    def setUp(self):
        self.vety = conllu.parse(VZOREK)

    def test_pocet_vet(self):
        self.assertEqual(len(self.vety), 4)

    def test_vsech_deset_sloupcu(self):
        """conBond2 bral sedm z deseti (core/ingest.py) a MISC vynechával
        úplně — bez SpaceAfter nejde z tokenů složit původní text. Bralo se
        to, co bylo zrovna potřeba; chybějící sloupec se pozná až za půl roku
        (§ 5 koncepce)."""
        t = self.vety[0].tokens[0]
        self.assertEqual(t.id, 1)
        self.assertEqual(t.form, "Alois")
        self.assertEqual(t.lemma, "Alois")
        self.assertEqual(t.upos, "PROPN")
        self.assertEqual(t.xpos, "NNMS1-----A----")
        self.assertEqual(t.feats["NameType"], "Giv")
        self.assertEqual(t.head, 11)
        self.assertEqual(t.deprel, "nsubj")
        self.assertIsNone(t.deps)
        self.assertIsNone(t.misc)

    def test_feats_je_slovnik(self):
        """conBond2 měl ['Case=Nom', ...] a rozebíral to při každém čtení.
        Rozdělení dvojice na klíč a hodnotu stačí udělat jednou."""
        feats = self.vety[0].tokens[0].feats
        self.assertIsInstance(feats, dict)
        self.assertEqual(feats["Case"], "Nom")
        self.assertEqual(feats["Gender"], "Masc")

    def test_misc_je_slovnik(self):
        t = self.vety[0].tokens[2]           # „(" má SpaceAfter=No
        self.assertEqual(t.misc, {"SpaceAfter": "No"})

    def test_podtrzitko_je_none_ne_retezec(self):
        """„Nemá hodnotu" je stav, ne řetězec (INV-9)."""
        t = self.vety[0].tokens[2]           # „(" nemá feats
        self.assertIsNone(t.feats)

    def test_space_after(self):
        """Z SpaceAfter se skládá původní text zpět."""
        self.assertFalse(self.vety[0].tokens[2].space_after)   # „("
        self.assertTrue(self.vety[0].tokens[0].space_after)    # „Alois"

    def test_source_z_komentare_text(self):
        """Klíč cache pochází odtud (§ 4 koncepce)."""
        self.assertEqual(
            self.vety[0].source,
            "Alois Jirásek (23. srpna 1851 Hronov) byl spisovatel.",
        )

    def test_sent_id(self):
        """Podle sent_id se párují odpovědi 4. fáze na dotazy (§ 13.4)."""
        self.assertEqual([v.sent_id for v in self.vety], ["1", "2", "3", "4"])

    def test_viceslovny_token(self):
        """„Abys" je v textu jeden tvar, ale dva tokeny (Aby + bys).
        conBond2 to tiše zahazoval testem isdecimal() a text pak nešlo
        složit zpět (§ 5 koncepce)."""
        veta = self.vety[2]
        self.assertEqual(len(veta.multiword), 1)
        self.assertEqual(veta.multiword[0].id, (1, 2))
        self.assertEqual(veta.multiword[0].form, "Abys")
        self.assertTrue(all(isinstance(t.id, int) for t in veta.tokens))

    def test_hodnota_misc_s_escapovanym_znakem(self):
        """UDPipe píše `SpacesAfter=\\n\\n` — zpětné lomítko a „n" jako dva
        znaky. Nesmí se z toho stát skutečné zalomení, jinak by se rozbil
        zápis zpátky."""
        posledni = self.vety[0].tokens[-1]
        self.assertEqual(posledni.misc["SpacesAfter"], "\\n\\n")

    def test_m2_nespadne(self):
        """PAST, na kterou se doplatilo: `int(c[0])` spadlo na tokenu „²",
        protože „²".isdigit() je True, ale int() na tom spadne. Článek
        o betonu má „m²" a shodil stavbu celého korpusu na 86 článcích
        (conBond2, core/agents/base.py). Správný predikát je isdecimal()."""
        rozsypany = "# text = m²\n²\tm²\t_\t_\t_\t_\t_\t_\t_\t_\n\n"
        self.assertEqual(conllu.parse(rozsypany), [])

    def test_prazdny_uzel_se_preskoci(self):
        """Řádek s desetinným ID (5.1) je elidovaný uzel — do tokenů
        nepatří, protože vrstvy nad námi počítají s celočíselným id."""
        s = ("# text = A B\n"
             "1\tA\t_\t_\t_\t_\t_\t_\t_\t_\n"
             "1.1\tB\t_\t_\t_\t_\t_\t_\t_\t_\n\n")
        self.assertEqual(len(conllu.parse(s)[0].tokens), 1)

    def test_prazdny_vstup_je_prazdny_seznam(self):
        """Prázdno není chyba — vrací se prázdný seznam, ne výjimka."""
        self.assertEqual(conllu.parse(""), [])
        self.assertEqual(conllu.parse("\n\n"), [])

    def test_veta_bez_komentare_text_ma_source_z_forem(self):
        """Vlastní CoNLL-U (4. fáze) `# text` mít nemusí. Složí se z forem
        a SpaceAfter, ať `source` není nikdy prázdný — je to klíč cache."""
        s = ("1\tPetr\t_\t_\t_\t_\t_\t_\t_\t_\n"
             "2\tspí\t_\t_\t_\t_\t_\t_\t_\tSpaceAfter=No\n"
             "3\t.\t_\t_\t_\t_\t_\t_\t_\t_\n\n")
        self.assertEqual(conllu.parse(s)[0].source, "Petr spí.")


class TestWrite(unittest.TestCase):

    def test_round_trip(self):
        """Co se přečte, musí jít zapsat a znovu přečíst beze ztráty —
        na tom stojí 4. fáze rozboru: pošle se hotové CoNLL-U a segmentace
        i tokenizace jsou dané vstupem (§ 2 koncepce)."""
        vety = conllu.parse(VZOREK)
        self.assertEqual(conllu.parse(conllu.write(vety)), vety)

    def test_zapis_nese_text_a_sent_id(self):
        out = conllu.write(conllu.parse(VZOREK))
        self.assertIn("# text = R.U.R. je drama.", out)
        self.assertIn("# sent_id = 2", out)

    def test_zapis_viceslovneho_tokenu(self):
        """Víceslovný řádek stojí PŘED tokeny, které pokrývá."""
        veta = conllu.parse(VZOREK)[2]
        out = conllu.write([veta])
        radky = [r for r in out.splitlines() if r and not r.startswith("#")]
        self.assertTrue(radky[0].startswith("1-2\tAbys"))

    def test_prazdna_hodnota_je_podtrzitko(self):
        out = conllu.write(conllu.parse(VZOREK))
        for radek in out.splitlines():
            if radek and not radek.startswith("#"):
                self.assertEqual(len(radek.split("\t")), 10, radek)

    def test_zapis_prazdneho_seznamu(self):
        self.assertEqual(conllu.write([]), "")


if __name__ == "__main__":
    unittest.main()
