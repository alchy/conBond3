"""Klient UDPipe serveru — jediné místo, které s ním mluví.

Testy běží proti podstrčenému HTTP serveru ze standardní knihovny, ne proti
skutečnému UDPipe: ten potřebuje model 357 MB a TensorFlow. Co se ověřuje, je
**tvar požadavku** — a právě na něm stojí rozdíl mezi levným a drahým voláním.
"""

import json
import threading
import unicodedata
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cb_udpipe import upstream

CONLLU = ("# sent_id = 1\n# text = Petr spí.\n"
          "1\tPetr\t_\t_\t_\t_\t_\t_\t_\t_\n"
          "2\tspí\t_\t_\t_\t_\t_\t_\t_\tSpaceAfter=No\n"
          "3\t.\t_\t_\t_\t_\t_\t_\t_\t_\n\n")


class FakeUdpipe(ThreadingHTTPServer):
    """Server, který se tváří jako UDPipe 2 a pamatuje si poslední požadavek."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.posledni_telo = ""
        self.posledni_cesta = ""
        self.stav = 200
        self.telo_odpovedi = json.dumps({"model": "cs", "result": CONLLU})
        self._vlakno = threading.Thread(target=self.serve_forever, daemon=True)
        self._vlakno.start()

    @property
    def endpoint(self) -> str:
        return "http://127.0.0.1:%d" % self.server_address[1]

    def zastav(self):
        self.shutdown()
        self.server_close()


class _Handler(BaseHTTPRequestHandler):

    def do_POST(self):
        delka = int(self.headers.get("Content-Length", 0))
        self.server.posledni_telo = self.rfile.read(delka).decode("utf-8")
        self.server.posledni_cesta = self.path
        self._odpoved()

    def do_GET(self):
        self.server.posledni_cesta = self.path
        self._odpoved()

    def _odpoved(self):
        telo = self.server.telo_odpovedi.encode("utf-8")
        self.send_response(self.server.stav)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(telo)))
        self.end_headers()
        self.wfile.write(telo)

    def log_message(self, format, *args):
        """Server nepíše do stderr — testy mají zůstat čitelné."""


class ZakladUpstream(unittest.TestCase):

    def setUp(self):
        self.server = FakeUdpipe()
        self.addCleanup(self.server.zastav)

    def klient(self, **kw):
        kw.setdefault("endpoint", self.server.endpoint)
        kw.setdefault("timeout_s", 5)
        return upstream.Upstream(**kw)

    def parametry(self) -> dict:
        return dict(urllib.parse.parse_qsl(self.server.posledni_telo,
                                           keep_blank_values=True))


class TestTvarPozadavku(ZakladUpstream):

    def test_tokenize_posila_tokenizer_bez_taggeru(self):
        """Fáze 1 nesmí poslat tagger ani parser: server má v predict()
        podmínku `if tag or parse`, takže bez nich vůbec nenačte síť
        a nepočítá embeddingy. To je celý rozdíl mezi levným a drahým
        voláním (§ 2 koncepce)."""
        self.klient().tokenize("Petr spí.")
        p = self.parametry()
        self.assertIn("tokenizer", p)
        self.assertNotIn("tagger", p)
        self.assertNotIn("parser", p)

    def test_tag_and_parse_neposila_tokenizer(self):
        """Fáze 4 posílá hotové CoNLL-U. Kdyby šel `tokenizer`, server by
        segmentoval znovu a naše oprava tokenizace by se zahodila."""
        self.klient().tag_and_parse(CONLLU)
        p = self.parametry()
        self.assertNotIn("tokenizer", p)
        self.assertIn("tagger", p)
        self.assertIn("parser", p)

    def test_cesta_je_process(self):
        self.klient().tokenize("A")
        self.assertEqual(self.server.posledni_cesta, "/process")

    def test_data_se_posilaji_v_tele(self):
        self.klient().tokenize("Petr spí.")
        self.assertEqual(self.parametry()["data"], "Petr spí.")

    def test_nfc_normalizace_vstupu(self):
        """Server si vstup normalizuje sám; děláme to i my, aby klíč cache
        odpovídal tomu, co se poslalo (§ 4 koncepce)."""
        self.klient().tokenize(unicodedata.normalize("NFD", "Soňa"))
        self.assertEqual(self.parametry()["data"], "Soňa")

    def test_dlouhy_vstup_projde_cely(self):
        """PAST z conBondu i jellyAI3: inline `-F data=` ořezával vstup na
        ~485 znaků a bible tím ztrácela 95 % textu. Posíláme
        x-www-form-urlencoded, takže se nás to netýká — ale test je levný
        a ta past stála dva projekty hodně času."""
        dlouhy = "Petr je v Praze. " * 200
        self.klient().tokenize(dlouhy)
        self.assertEqual(self.parametry()["data"], dlouhy)
        self.assertGreater(len(self.parametry()["data"]), 3000)


class TestVysledek(ZakladUpstream):

    def test_vraci_syrove_conllu(self):
        """Vrací se to, co přišlo v klíči `result` — rozbor na tokeny dělá
        `conllu.parse`, ne tenhle modul."""
        self.assertEqual(self.klient().tokenize("Petr spí."), CONLLU)

    def test_prazdny_vysledek_neni_chyba(self):
        """Prázdný vstup dá prázdný CoNLL-U a to je platný stav (INV-9)."""
        self.server.telo_odpovedi = json.dumps({"result": ""})
        self.assertEqual(self.klient().tokenize(""), "")

    def test_models_vraci_slovnik(self):
        self.server.telo_odpovedi = json.dumps({"models": {"czech": []},
                                                "default_model": "czech"})
        self.assertIn("models", self.klient().models())


class TestChyby(ZakladUpstream):

    def test_nedostupna_sluzba_je_typovana_chyba(self):
        """Nikdy prázdná odpověď — ta by se slila s platným prázdným
        výsledkem (INV-9, § 9 politiky)."""
        k = upstream.Upstream(endpoint="http://127.0.0.1:1", timeout_s=1)
        with self.assertRaises(upstream.UpstreamUnavailable):
            k.tokenize("A")

    def test_hlaska_nese_adresu_a_navod(self):
        """Chybová hláška má povinně tři věci: který modul, na jaké adrese
        ho klient hledal a čím ho spustit. Bez toho třetího si každý musí
        pamatovat jméno ovládacího programu (§ 1 politiky)."""
        k = upstream.Upstream(endpoint="http://127.0.0.1:1", timeout_s=1)
        with self.assertRaises(upstream.UpstreamUnavailable) as e:
            k.tokenize("A")
        zprava = str(e.exception)
        self.assertIn("cb-udpipe", zprava)
        self.assertIn("127.0.0.1:1", zprava)
        self.assertIn("./cb-udpipe.py start", zprava)

    def test_chyba_serveru_je_upstream_error(self):
        self.server.stav = 500
        self.server.telo_odpovedi = "něco se pokazilo"
        with self.assertRaises(upstream.UpstreamError):
            self.klient().tokenize("A")

    def test_prilis_dlouha_veta_je_vlastni_chyba(self):
        """Server vrací 400 s textem o větě delší než 1000 slov. Rozlišuje
        se, protože volající na to reaguje jinak: větu přeskočí s důvodem
        a zbytek dávky pošle dál (§ 11 koncepce)."""
        self.server.stav = 400
        self.server.telo_odpovedi = (
            "During tokenization, sentence longer than 1000 words was found, "
            "aborting.\n")
        with self.assertRaises(upstream.SentenceTooLong):
            self.klient().tokenize("slovo " * 1200)

    def test_nevalidni_json_je_upstream_error(self):
        self.server.telo_odpovedi = "tohle není JSON"
        with self.assertRaises(upstream.UpstreamError):
            self.klient().tokenize("A")

    def test_odpoved_bez_klice_result_je_chyba(self):
        """Chybějící `result` není prázdný rozbor — je to jiný protokol,
        než jaký čekáme, a slít to s prázdnem by byla tichá chyba."""
        self.server.telo_odpovedi = json.dumps({"model": "cs"})
        with self.assertRaises(upstream.UpstreamError):
            self.klient().tokenize("A")


class TestLogovani(ZakladUpstream):

    def test_loguje_obe_strany_volani(self):
        """Klient je jediné místo, kde je vidět obě strany hranice. Když se
        rozejdou, je chyba mezi nimi — v síti, v serializaci, v timeoutu —
        a bez záznamu z obou stran ji nikdo nenajde (§ 1 politiky)."""
        log = FakeLog()
        self.klient(log=log).tokenize("Petr spí.", trace="q-1")
        zaznam = [z for z in log.zaznamy if z["method"] == "tokenize"]
        self.assertTrue(zaznam)
        self.assertEqual(zaznam[0]["trace"], "q-1")
        self.assertEqual(zaznam[0]["result"], "ok")

    def test_loguje_i_chybu(self):
        self.server.stav = 500
        log = FakeLog()
        with self.assertRaises(upstream.UpstreamError):
            self.klient(log=log).tokenize("A", trace="q-2")
        self.assertEqual(log.zaznamy[-1]["result"], "error")

    def test_bez_loggeru_funguje(self):
        """Logovátko je nepovinná závislost (§ 9 politiky)."""
        self.assertEqual(self.klient(log=None).tokenize("A"), CONLLU)


class FakeLog:
    """Zaznamenává volání místo odesílání do logovátka."""

    def __init__(self):
        self.zaznamy = []

    def info(self, **kw):
        self.zaznamy.append({**kw, "level": "info"})

    def debug(self, **kw):
        self.zaznamy.append({**kw, "level": "debug"})

    def json(self, **kw):
        self.zaznamy.append({**kw, "level": "json"})


if __name__ == "__main__":
    unittest.main()
