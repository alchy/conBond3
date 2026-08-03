"""Pravidla opravy tokenizace.

Každý test odpovídá jednomu pravidlu z koncepce § 3 nebo jedné pasti
z předchozích projektů. Testy nepotřebují běžící UDPipe — pravidla jsou čistá
funkce nad tokeny.
"""

import unittest

from cb_udpipe import conllu, tokenize

PRAVIDLA = tokenize.Rules(
    abbreviations=frozenset({"tzv", "např", "sv", "n", "l", "vyd", "stol"}),
    min_pairs=2,
    merge_number_groups=True,
    merge_decimal_comma=True,
)


def veta(formy, pripojene=()):
    """Postaví větu z forem; `pripojene` jsou indexy tokenů bez mezery za sebou.

    `source` se skládá z forem podle týchž mezer, takže odpovídá tomu, co by
    přišlo z UDPipe — a testy tím zároveň hlídají, že se `source` opravou
    nemění.
    """
    tokeny = []
    for i, f in enumerate(formy):
        misc = {"SpaceAfter": "No"} if i in pripojene else None
        tokeny.append(conllu.Token(id=i + 1, form=f, misc=misc))
    kusy = []
    for i, f in enumerate(formy):
        kusy.append(f)
        if i not in pripojene and i < len(formy) - 1:
            kusy.append(" ")
    return conllu.Sentence(source="".join(kusy), tokens=tuple(tokeny))


class TestZkratky(unittest.TestCase):

    def test_rur_se_sceli(self):
        """R.U.R. je jeden pojem. UDPipe z něj dělá šest tokenů a rozbor pak
        označí poslední R za podmět věty (§ 13.3 koncepce)."""
        v = veta(["R", ".", "U", ".", "R", ".", "je", "drama"],
                 pripojene={0, 1, 2, 3, 4})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens], ["R.U.R.", "je", "drama"])
        self.assertEqual(n, 1)

    def test_jedina_iniciala_se_nesceli(self):
        """K. Čapek je jméno, ne zkratka. Vyžadují se aspoň dva páry —
        conBond (normalize.py) i jellyAI3 (test_normalize.py) to mají shodně."""
        v = veta(["K", ".", "Čapek"], pripojene={0})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens], ["K", ".", "Čapek"])
        self.assertEqual(n, 0)

    def test_pismena_s_mezerami_se_nesceli(self):
        """Výčtové odrážky (a . b .) nejsou zkratka — běh vyžaduje těsně
        navazující tokeny, což se pozná podle SpaceAfter=No."""
        v = veta(["a", ".", "b", "."], pripojene=())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)

    def test_tri_pary_taky(self):
        """Běh není omezený shora."""
        v = veta(["T", ".", "G", ".", "M", ".", "byl"],
                 pripojene={0, 1, 2, 3, 4})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(out.tokens[0].form, "T.G.M.")


class TestJednoslovneZkratky(unittest.TestCase):

    def test_tzv_se_sceli(self):
        v = veta(["Šlo", "o", "tzv", ".", "obrození"], pripojene={2})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertIn("tzv.", [t.form for t in out.tokens])
        self.assertEqual(n, 1)

    def test_zkratka_mimo_seznam_zustane(self):
        """Seznam je jazykové datum; co v něm není, se nescelí. Bezvýčtově to
        nejde — zkratka na konci věty vypadá stejně jako konec věty."""
        v = veta(["Bylo", "to", "xyz", ".", "tady"], pripojene={2})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)

    def test_zkratka_na_konci_vety_se_nesceli(self):
        """Tečka za poslední zkratkou ukončuje větu. Sloučit ji by znamenalo
        větu bez interpunkce."""
        v = veta(["Bylo", "to", "tzv", "."], pripojene={2})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)

    def test_velikost_pismen_nerozhoduje(self):
        v = veta(["Kostel", "Sv", ".", "Víta"], pripojene={1})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertIn("Sv.", [t.form for t in out.tokens])


class TestRadoveCislovky(unittest.TestCase):

    def test_dvacate_stoleti(self):
        v = veta(["ve", "20", ".", "století"], pripojene={1})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens], ["ve", "20.", "století"])
        self.assertEqual(n, 1)

    def test_tecka_na_konci_vety_se_nesceli(self):
        """ŘEZ, bez kterého měření nadhodnotilo vadu o 1 062 vět: `, 1985 .`
        je rok na konci věty, ne řadová číslovka (§ 13.1 koncepce)."""
        v = veta(["Vyšlo", "to", "1985", "."], pripojene={2})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens],
                         ["Vyšlo", "to", "1985", "."])
        self.assertEqual(n, 0)

    def test_datum(self):
        v = veta(["dne", "23", ".", "srpna", "1851"], pripojene={1})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens],
                         ["dne", "23.", "srpna", "1851"])

    def test_cislo_s_mezerou_pred_teckou_se_nesceli(self):
        """Bez SpaceAfter=No to není řadová číslovka."""
        v = veta(["bylo", "20", ".", "století"], pripojene=())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)


class TestCiselneSkupiny(unittest.TestCase):

    def test_oddelovac_tisicu(self):
        """UDPipe dá 30 000 jako DVA samostatné nummod:gov, takže AG-METRON
        vidí dvě čísla místo jednoho a naměří 30. conBond2 to má v etalonu
        jako doloženou mezeru (§ 3.4 koncepce)."""
        v = veta(["V", "úlu", "je", "30", "000", "dělnic"])
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertIn("30 000", [t.form for t in out.tokens])
        self.assertEqual(n, 1)

    def test_vicenasobny_oddelovac(self):
        v = veta(["Stálo", "to", "1", "250", "000", "korun"])
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertIn("1 250 000", [t.form for t in out.tokens])

    def test_desetinna_carka(self):
        """3,14 je tři tokeny: 3 | , | 14."""
        v = veta(["Hodnota", "je", "3", ",", "14", "metru"], pripojene={2, 3})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertIn("3,14", [t.form for t in out.tokens])

    def test_rok_a_dalsi_cislo_se_nesluci(self):
        """ŘEZ: slučují se jen skupiny PRÁVĚ TŘÍ číslic. Jinak by se
        `roku 1890 12 lidí` chovalo jako číselná skupina (§ 3.4)."""
        v = veta(["V", "roce", "1890", "zemřel"])
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)
        self.assertIn("1890", [t.form for t in out.tokens])

    def test_dve_cislice_po_mezere_se_nesluci(self):
        """30 00 není oddělovač tisíců — jsou to dvě čísla."""
        v = veta(["bylo", "30", "00", "kusů"])
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)

    def test_vypnuto_konfiguraci(self):
        pravidla = tokenize.Rules(
            abbreviations=PRAVIDLA.abbreviations, min_pairs=2,
            merge_number_groups=False, merge_decimal_comma=False,
        )
        v = veta(["je", "30", "000", "kusů"])
        out, n = tokenize.retokenize(v, pravidla)
        self.assertEqual(n, 0)


class TestNesjednocujeZnaky(unittest.TestCase):
    """Měření ukázalo, že sjednocení pomlček by nepomohlo (druh pomlčky
    hranice tokenů nemění) a něco by stálo (en-dash proti spojovníku nese
    informaci, na které stojí AG-BIO) — § 13.6 koncepce."""

    def test_pomlcky_zustavaji_rozlisene(self):
        v = veta(["Praha", "-", "Libeň", "–", "2011"])
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens],
                         ["Praha", "-", "Libeň", "–", "2011"])
        self.assertEqual(n, 0)

    def test_uvozovky_zustavaji(self):
        v = veta(["Řekl", "„", "Ahoj", "“"])
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)


class TestInvarianty(unittest.TestCase):

    def test_text_vety_se_nemeni(self):
        """Oprava mění hranice tokenů, NIKDY text. `source` je klíč cache;
        kdyby se změnil, cache by se rozpadla (§ 6 koncepce)."""
        v = veta(["R", ".", "U", ".", "R", ".", "je", "drama"],
                 pripojene={0, 1, 2, 3, 4})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(out.source, v.source)

    def test_id_jsou_souvisla_od_jedne(self):
        """Po sloučení se musí přečíslovat, jinak není CoNLL-U platný."""
        v = veta(["R", ".", "U", ".", "R", ".", "je"],
                 pripojene={0, 1, 2, 3, 4})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.id for t in out.tokens],
                         list(range(1, len(out.tokens) + 1)))

    def test_veta_bez_vady_projde_beze_zmeny(self):
        """Nejčastější případ. Kdyby se měnil, neplatí měření § 13.5."""
        v = veta(["Petr", "je", "v", "Praze"])
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)
        self.assertEqual(out.tokens, v.tokens)

    def test_slouceny_token_nese_space_after_posledniho(self):
        """Bez toho by se z tokenů složil text s mezerou navíc."""
        v = veta(["ve", "20", ".", "století"], pripojene={1, 2})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        slouceny = [t for t in out.tokens if t.form == "20."][0]
        self.assertFalse(slouceny.space_after)

    def test_slozeny_text_odpovida_zdroji(self):
        """Nejtvrdší invariant: po opravě musí z tokenů vzniknout týž text,
        jaký přišel. Jinak se ztratila nebo přibyla mezera."""
        v = veta(["V", "úlu", "je", "30", "000", "dělnic"])
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(conllu._slozit_text(out.tokens), out.source)

    def test_prazdna_veta(self):
        v = conllu.Sentence(source="", tokens=())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(out.tokens, ())
        self.assertEqual(n, 0)


class TestOtisk(unittest.TestCase):

    def test_otisk_se_meni_se_seznamem(self):
        """Verze tokenizéru je otisk pravidel, ne ruční číslo — ruční zastará
        v první chvíli, kdy někdo přidá zkratku a zapomene ho zvednout
        (§ 4 koncepce)."""
        a = tokenize.Rules(frozenset({"tzv"}), 2, True, True)
        b = tokenize.Rules(frozenset({"tzv", "např"}), 2, True, True)
        self.assertNotEqual(tokenize.fingerprint(a), tokenize.fingerprint(b))

    def test_otisk_je_stabilni_vuci_poradi(self):
        """Množina nemá pořadí; otisk se nesmí měnit mezi běhy."""
        a = tokenize.Rules(frozenset({"tzv", "např"}), 2, True, True)
        b = tokenize.Rules(frozenset({"např", "tzv"}), 2, True, True)
        self.assertEqual(tokenize.fingerprint(a), tokenize.fingerprint(b))

    def test_otisk_se_meni_s_prepinaci(self):
        """Vypnutí číselných skupin je změna tokenizace jako každá jiná."""
        a = tokenize.Rules(frozenset({"tzv"}), 2, True, True)
        b = tokenize.Rules(frozenset({"tzv"}), 2, False, True)
        self.assertNotEqual(tokenize.fingerprint(a), tokenize.fingerprint(b))

    def test_otisk_ma_dvanact_znaku(self):
        self.assertEqual(len(tokenize.fingerprint(PRAVIDLA)), 12)


class TestRulesZKonfigurace(unittest.TestCase):

    def test_from_config(self):
        from cb_udpipe import config
        pravidla = tokenize.Rules.from_config(config.load())
        self.assertIn("tzv", pravidla.abbreviations)
        self.assertEqual(pravidla.min_pairs, 2)
        self.assertTrue(pravidla.merge_number_groups)


if __name__ == "__main__":
    unittest.main()
