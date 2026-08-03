# cb-udpipe — implementační plán

> **Pro agentní pracovníky:** POVINNÁ PODDOVEDNOST: použij
> `superpowers:subagent-driven-development` nebo `superpowers:executing-plans`
> a postupuj úkol po úkolu. Kroky používají zaškrtávací pole (`- [ ]`).

**Cíl:** Modul, kterému se pošle věta a on vrátí kvalitní rozbor — s vlastní
opravou tokenizace a s trvalou cache rozborů po větách.

**Architektura:** Čtyři fáze (segmentace UDPipem → naše oprava tokenizace →
cache → dorozbor předtokenizovaného CoNLL-U). Doménová logika v `service.py`
bez HTTP, REST obálka v `api.py`, klient pro ostatní moduly v `client.py`.
UDPipe 2 běží jako vlastní proces vedle služby, ne jako import.

**Technologie:** Python 3.11, **pouze standardní knihovna** pro náš kód.
UDPipe 2 (vendorovaný, TensorFlow + transformers) je samostatný proces.

Návrh, ze kterého plán vychází: `koncepce.md`. Politika modulů:
`../../README-MODULES.md`.

## Globální omezení

Platí pro **každý** úkol; neopakují se u jednotlivých kroků.

- **Kód anglicky, docstringy a komentáře česky** (§ 17 politiky).
- **Docstring stojí POD hlavičkou funkce** a má čtyři části: proč, vstup,
  výstup, při chybě. Vysvětluje **proč**, ne co.
- **Náš kód nesmí importovat nic mimo standardní knihovnu** (§ 19 politiky).
  `import tensorflow` v `service.py` je chyba, i když je v `.venv`.
- **Žádné globální stavy.** Logger, konfigurace, stopa, čas i náhoda se
  předávají parametrem (§ 3 politiky).
- **Žádná cesta ani práh v kódu** — vše z konfigurace (§ 5 politiky).
- **`except: pass` je zakázaný.** Každá zachycená výjimka končí záznamem
  `result=error` s důvodem (§ 9 politiky).
- **Typové anotace na všem, co je vidět zvenčí.** Datové tvary jsou
  `dataclass`/`Enum`, ne slovníky s dohodou (§ 18 politiky).
- **Řádek do 88 znaků, odsazení čtyři mezery.**
- **Testy v `unittest`**, spouštěné `./run-python -m unittest discover -s cb_udpipe -t .`
- **Prázdno není chyba.** `empty` a `error` se nikde neslévají (`INV-9`).
- **Porty modulu:** 42200 REST API, 42201 vlastní instance UDPipe.
  Rozsah 42200–42299.
- **Verze modelu:** `cs_all-ud-2.17-251125`. Licence **CC BY-NC-SA**,
  do gitu nesmí.

---

## Struktura souborů

| soubor | za co odpovídá |
|---|---|
| `cb-udpipe.py` (kořen) | tenký spouštěč do `control.py` |
| `README-UDPIPE.md` (kořen) | vývojářské README — jak modul volat |
| `cb_udpipe/cb-udpipe-config.json` | konfigurace modulu |
| `cb_udpipe/config.schema.json` | schéma konfigurace |
| `cb_udpipe/config.py` | načtení, validace, rozbalení cest |
| `cb_udpipe/__init__.py` | veřejné API: `UdpipeClient`, `Token`, `Sentence`, výjimky |
| `cb_udpipe/conllu.py` | čtení a psaní CoNLL-U; datové typy `Token`, `Sentence` |
| `cb_udpipe/tokenize.py` | pravidla opravy tokenizace + otisk pravidel |
| `cb_udpipe/cache.py` | JSONL cache s indexem klíč → offset |
| `cb_udpipe/upstream.py` | HTTP klient k UDPipe serveru — jediné místo, které s ním mluví |
| `cb_udpipe/service.py` | orchestrace čtyř fází, souhrn, zdraví |
| `cb_udpipe/api.py` | REST vrstva nad `service.py`, žádná doménová logika |
| `cb_udpipe/client.py` | klient pro ostatní moduly; stejné signatury jako service |
| `cb_udpipe/control.py` | start/stop/restart/reload/status + hlídání procesu UDPipe |
| `cb_udpipe/scripts/fetch-models.sh` | pořízení modelu a RobeCzechu |

`conllu.py`, `tokenize.py` a `cache.py` jsou čisté funkce nad daty —
testovatelné bez běžícího UDPipe. To je záměr, ne náhoda: největší část logiky
modulu se tím dá měřit na zmražených datech.

---

## Úkol 1: Konfigurace a kostra

**Soubory:**
- Vytvoř: `cb_udpipe/cb-udpipe-config.json`
- Vytvoř: `cb_udpipe/config.schema.json`
- Vytvoř: `cb_udpipe/config.py`
- Vytvoř: `cb_udpipe/tests/__init__.py`
- Test: `cb_udpipe/tests/test_config.py`

**Rozhraní:**
- Poskytuje: `load(path: str | Path | None = None) -> dict[str, Any]`,
  `ConfigError`, `MODULE_DIR`, `DEFAULT_CONFIG_PATH`, `SUPPORTED_CONFIG_VERSION`.
  Vrácený slovník má klíč `_meta` s `path` (skutečně použitá cesta) a
  `fingerprint` (otisk obsahu).

- [ ] **Krok 1: Napiš konfiguraci**

`cb_udpipe/cb-udpipe-config.json`:

```json
{
  "config_version": 1,
  "service": {
    "host": "127.0.0.1",
    "port": 42200,
    "workers": 4,
    "request_timeout_s": 30,
    "max_request_bytes": 2097152
  },
  "runtime": {
    "pid_file": "run/service.pid",
    "port_file": "run/service.port",
    "stop_timeout_s": 20
  },
  "logging": {
    "endpoint": "http://127.0.0.1:42100",
    "level": "info",
    "methods": []
  },
  "module": {
    "upstream": {
      "host": "127.0.0.1",
      "port": 42201,
      "model": "cs_all-ud-2.17-251125",
      "model_dir": "data-persistent/models/cs_all-ud-2.17-251125.model",
      "hf_home": "data-persistent/models/hf",
      "vendor_dir": "vendor/udpipe2-src",
      "request_timeout_s": 600,
      "start_timeout_s": 120,
      "threads": 0,
      "warmup": true,
      "warmup_sentence": "Alois Jirásek se narodil 23. srpna 1851."
    },
    "tokenizer": {
      "mode": "rules",
      "abbrev_min_pairs": 2,
      "max_sentence_words": 1000,
      "merge_number_groups": true,
      "merge_decimal_comma": true,
      "abbreviations": [
        "tzv", "např", "tj", "mj", "tzn", "atd", "apod", "aj", "resp",
        "popř", "cca", "č", "r", "st", "sv", "kap", "obr", "tab", "roč",
        "s", "str", "stol", "vyd", "př", "n", "l", "cit", "čp", "min",
        "zn", "hod", "tis", "mil", "stř", "mudr", "judr", "phdr", "rndr",
        "ing", "prof", "doc", "csc", "mgr", "bc"
      ]
    },
    "cache": {
      "dir": "data-persistent/cache",
      "batch_sentences": 60
    },
    "log_objects": "miss"
  }
}
```

`abbreviations` je jazykové datum, ne kód (§ 3.2 koncepce). Seznam vznikl
sloučením 29 položek z jellyAI3 (`jellyai/text.py`) se zkratkami naměřenými
v korpusu conBondu2.

- [ ] **Krok 2: Napiš schéma**

`config.schema.json` popisuje tvar výše: typy, rozsahy (`port` 42200–42299,
`abbrev_min_pairs` minimum 2), povinné klíče, `additionalProperties: false`
na každé úrovni. Podporované klíče schématu drž na téže podmnožině, jakou umí
`cb_logger/config.py` (`type`, `properties`, `required`, `items`, `enum`,
`minimum`, `maximum`, `additionalProperties`) — validátor je vlastní, ne
knihovna.

- [ ] **Krok 3: Napiš padající test**

`cb_udpipe/tests/test_config.py`:

```python
class TestConfigLoad(unittest.TestCase):
    def test_vychozi_konfigurace_projde(self):
        """Konfigurace v repozitáři musí být platná — jinak modul nenastartuje."""
        cfg = config.load()
        self.assertEqual(cfg["config_version"], 1)
        self.assertEqual(cfg["service"]["port"], 42200)

    def test_neznamy_klic_je_chyba(self):
        """Tiché ignorování překlepu znamená, že běží jiné nastavení,
        než si člověk myslí (§ 5 politiky)."""
        with self._docasna({"config_version": 1, "sluzba": {}}) as p:
            with self.assertRaises(config.ConfigError) as e:
                config.load(p)
            self.assertIn("sluzba", str(e.exception))

    def test_chybejici_povinny_klic_je_chyba(self):
        with self._docasna({"config_version": 1}) as p:
            with self.assertRaises(config.ConfigError):
                config.load(p)

    def test_port_mimo_rozsah_modulu_je_chyba(self):
        """Rozsah 42200–42299 je vlastnictví modulu (§ 5 politiky);
        sáhnutí na cizí číslo je chyba konfigurace, ne provozu."""
        cfg = self._platna()
        cfg["service"]["port"] = 42100
        with self._docasna(cfg) as p:
            with self.assertRaises(config.ConfigError):
                config.load(p)

    def test_cesty_jsou_absolutni_a_vuci_modulu(self):
        """Relativní cesta se počítá vůči adresáři modulu, ne vůči
        pracovnímu adresáři procesu — jinak se chování mění podle toho,
        odkud se služba spustí."""
        cfg = config.load()
        self.assertTrue(Path(cfg["module"]["cache"]["dir"]).is_absolute())

    def test_meta_nese_pouzitou_cestu_a_otisk(self):
        """Bez zapsané cesty nikdo nezjistí, které nastavení běží."""
        cfg = config.load()
        self.assertTrue(cfg["_meta"]["path"].endswith("cb-udpipe-config.json"))
        self.assertEqual(len(cfg["_meta"]["fingerprint"]), 12)
```

- [ ] **Krok 4: Spusť test, musí spadnout**

Spusť: `./run-python -m unittest cb_udpipe.tests.test_config -v`
Očekávej: FAIL — `ModuleNotFoundError: cb_udpipe.config`

- [ ] **Krok 5: Napiš `config.py`**

Struktura odpovídá `cb_logger/config.py` (týž validátor, tytéž chybové hlášky).
Klíčové části:

```python
MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = MODULE_DIR / "cb-udpipe-config.json"
SCHEMA_PATH = MODULE_DIR / "config.schema.json"
SUPPORTED_CONFIG_VERSION = 1

#: Rozsah portů modulu (§ 5 politiky). Sáhnutí mimo je chyba konfigurace:
#: cizí port se pozná až tím, že se dva moduly poperou o totéž číslo.
PORT_RANGE = (42200, 42299)

#: Klíče, jejichž hodnota je cesta a rozbaluje se vůči adresáři modulu.
PATH_KEYS = (
    ("runtime", "pid_file"), ("runtime", "port_file"),
    ("module", "cache", "dir"), ("module", "upstream", "model_dir"),
    ("module", "upstream", "hf_home"), ("module", "upstream", "vendor_dir"),
)
```

`load()` provede: čtení JSON → kontrola `config_version` → validace proti
schématu → kontrola rozsahu portů (`service.port` i `module.upstream.port`) →
rozbalení cest na absolutní → doplnění `_meta`.

- [ ] **Krok 6: Spusť test, musí projít**

Spusť: `./run-python -m unittest cb_udpipe.tests.test_config -v`
Očekávej: PASS, 6 testů

- [ ] **Krok 7: Commit**

```bash
git add cb_udpipe/cb-udpipe-config.json cb_udpipe/config.schema.json \
        cb_udpipe/config.py cb_udpipe/tests/
git commit -m "cb-udpipe: konfigurace se schématem a validací při startu"
```

---

## Úkol 2: Čtení a psaní CoNLL-U

**Soubory:**
- Vytvoř: `cb_udpipe/conllu.py`
- Vytvoř: `cb_udpipe/tests/data/vzorek.conllu`
- Test: `cb_udpipe/tests/test_conllu.py`

**Rozhraní:**
- Poskytuje:
  ```python
  @dataclass(frozen=True)
  class Token:
      id: int
      form: str
      lemma: str | None = None
      upos: str | None = None
      xpos: str | None = None
      feats: dict[str, str] | None = None
      head: int | None = None
      deprel: str | None = None
      deps: str | None = None
      misc: dict[str, str] | None = None
      @property
      def space_after(self) -> bool: ...

  @dataclass(frozen=True)
  class Multiword:
      id: tuple[int, int]
      form: str
      misc: dict[str, str] | None = None

  @dataclass(frozen=True)
  class Sentence:
      source: str
      tokens: tuple[Token, ...]
      multiword: tuple[Multiword, ...] = ()
      sent_id: str | None = None

  def parse(text: str) -> list[Sentence]
  def write(sentences: Sequence[Sentence]) -> str
  ```

- [ ] **Krok 1: Zmraz testovací data**

`cb_udpipe/tests/data/vzorek.conllu` — skutečný výstup UDPipe pro tři věty:
`Alois Jirásek (23. srpna 1851 Hronov) byl spisovatel.`, `R.U.R. je drama.`
a jedna věta s víceslovným tokenem (`dělalas`). Data se **generují jednou
ručně a zmrazí do gitu** (§ 13 politiky) — data vyrobená za běhu testu
neřeknou, jestli se změnilo chování, nebo vstup.

- [ ] **Krok 2: Napiš padající test**

```python
class TestParse(unittest.TestCase):
    def test_vsech_deset_sloupcu(self):
        """conBond2 bral sedm z deseti a MISC vynechával — bez SpaceAfter
        nejde složit původní text (§ 5 koncepce)."""
        v = conllu.parse(VZOREK)[0]
        t = v.tokens[0]
        self.assertEqual(t.form, "Alois")
        self.assertEqual(t.upos, "PROPN")
        self.assertEqual(t.feats["Case"], "Nom")

    def test_feats_je_slovnik(self):
        """conBond2 měl ['Case=Nom', ...] a rozebíral to při každém čtení."""
        v = conllu.parse(VZOREK)[0]
        self.assertIsInstance(v.tokens[0].feats, dict)

    def test_podtrzitko_je_none_ne_retezec(self):
        """„Nemá hodnotu\" je stav, ne řetězec (INV-9)."""
        v = conllu.parse("# text = A\n1\tA\t_\t_\t_\t_\t_\t_\t_\t_\n\n")
        self.assertIsNone(v[0].tokens[0].lemma)

    def test_source_z_komentare_text(self):
        """Klíč cache pochází odtud (§ 4 koncepce)."""
        v = conllu.parse(VZOREK)[0]
        self.assertEqual(v.source, "Alois Jirásek (23. srpna 1851 Hronov) byl spisovatel.")

    def test_viceslovny_token_do_multiword(self):
        """conBond2 je tiše zahazoval testem isdecimal()."""
        v = [s for s in conllu.parse(VZOREK) if s.multiword][0]
        self.assertEqual(v.multiword[0].id, (1, 2))
        self.assertTrue(all(isinstance(t.id, int) for t in v.tokens))

    def test_m2_nespadne(self):
        """PAST: „²\".isdigit() je True, ale int() na tom spadne. Článek
        o betonu shodil stavbu korpusu na 86 článcích (conBond2). Správný
        predikát je isdecimal()."""
        rozsypany = "# text = m²\n²\tm²\t_\t_\t_\t_\t_\t_\t_\t_\n\n"
        self.assertEqual(conllu.parse(rozsypany), [])

    def test_prazdny_vstup_je_prazdny_seznam(self):
        """Ne výjimka — prázdno není chyba."""
        self.assertEqual(conllu.parse(""), [])

class TestWrite(unittest.TestCase):
    def test_round_trip(self):
        """Co se přečte, musí jít zapsat a znovu přečíst beze ztráty —
        na tom stojí 4. fáze rozboru (§ 2 koncepce)."""
        vety = conllu.parse(VZOREK)
        self.assertEqual(conllu.parse(conllu.write(vety)), vety)

    def test_zapis_nese_text_a_sent_id(self):
        """Podle sent_id se odpovědi 4. fáze párují na dotazy (§ 13.4)."""
        out = conllu.write(conllu.parse(VZOREK))
        self.assertIn("# text = ", out)
        self.assertIn("# sent_id = ", out)
```

- [ ] **Krok 3: Spusť test, musí spadnout**

Spusť: `./run-python -m unittest cb_udpipe.tests.test_conllu -v`
Očekávej: FAIL — `ModuleNotFoundError`

- [ ] **Krok 4: Napiš `conllu.py`**

Klíčová rozhodnutí, každé s komentářem v kódu:

```python
def _je_cele_cislo(s: str) -> bool:
    """Dá se ten tvar přečíst jako celé číslo?

    NE `isdigit()`. Ten vrací True i pro „²", takže `int()` na něm spadne —
    a spadl: článek o betonu má „m²" a shodil stavbu korpusu na 86 článcích
    (conBond2, core/agents/base.py). `isdecimal()` je právě ten predikát,
    po kterém `int()` projde vždycky.
    """
    return s.isdecimal()
```

Rozbor pole `FEATS`/`MISC`: `Case=Nom|Gender=Fem` → dict; `_` → `None`.
Rozbor `ID`: `1` → token, `1-2` → `Multiword`, `1.1` → přeskočit (prázdný uzel).
`write()` vždy vypíše `# sent_id` a `# text`.

- [ ] **Krok 5: Spusť test, musí projít**

Spusť: `./run-python -m unittest cb_udpipe.tests.test_conllu -v`
Očekávej: PASS, 9 testů

- [ ] **Krok 6: Commit**

```bash
git add cb_udpipe/conllu.py cb_udpipe/tests/test_conllu.py cb_udpipe/tests/data/
git commit -m "cb-udpipe: čtení a psaní CoNLL-U se všemi deseti sloupci"
```

---

## Úkol 3: Pravidla opravy tokenizace

**Soubory:**
- Vytvoř: `cb_udpipe/tokenize.py`
- Test: `cb_udpipe/tests/test_tokenize.py`

**Rozhraní:**
- Spotřebovává: `conllu.Token`, `conllu.Sentence` (úkol 2)
- Poskytuje:
  ```python
  @dataclass(frozen=True)
  class Rules:
      abbreviations: frozenset[str]
      min_pairs: int = 2
      @classmethod
      def from_config(cls, cfg: dict) -> "Rules": ...

  def fingerprint(rules: Rules) -> str      # 12 hex znaků
  def retokenize(sentence: Sentence, rules: Rules) -> tuple[Sentence, int]
  ```
  Druhá položka návratu je počet sloučení — jde do logu a do souhrnu.

- [ ] **Krok 1: Napiš padající test**

Každý test odpovídá jednomu pravidlu z § 3 koncepce nebo jedné pasti
z předchozích projektů.

```python
class TestZkratky(unittest.TestCase):
    def test_rur_se_sceli(self):
        """R.U.R. je jeden pojem. UDPipe z něj dělá šest tokenů a rozbor
        pak označí poslední „R\" za podmět (§ 13.3 koncepce)."""
        v = _veta(["R", ".", "U", ".", "R", ".", "je", "drama"],
                  pripojene={0, 1, 2, 3, 4})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens], ["R.U.R.", "je", "drama"])
        self.assertEqual(n, 1)

    def test_jedina_iniciala_se_nesceli(self):
        """„K. Čapek\" je jméno, ne zkratka. Vyžadují se ≥2 páry
        (conBond normalize.py, jellyAI3 test_normalize.py)."""
        v = _veta(["K", ".", "Čapek"], pripojene={0})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens], ["K", ".", "Čapek"])
        self.assertEqual(n, 0)

    def test_pismena_s_mezerami_se_nesceli(self):
        """Výčtové odrážky „a . b .\" nejsou zkratka — běh vyžaduje
        těsně navazující tokeny (SpaceAfter=No)."""
        v = _veta(["a", ".", "b", "."], pripojene=set())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)

class TestJednoslovneZkratky(unittest.TestCase):
    def test_tzv_se_sceli(self):
        v = _veta(["Šlo", "o", "tzv", ".", "obrození"], pripojene={2})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertIn("tzv.", [t.form for t in out.tokens])

    def test_zkratka_mimo_seznam_zustane(self):
        """Seznam je jazykové datum; co v něm není, se nescelí."""
        v = _veta(["Bylo", "to", "xyz", ".", "tady"], pripojene={2})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)

class TestRadoveCislovky(unittest.TestCase):
    def test_dvacate_stoleti(self):
        v = _veta(["ve", "20", ".", "století"], pripojene={1})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens], ["ve", "20.", "století"])

    def test_tecka_na_konci_vety_se_nesceli(self):
        """ŘEZ, bez kterého měření nadhodnotilo vadu o 1 062 vět: „, 1985 .\"
        je rok na konci věty, ne řadová číslovka (§ 13.1 koncepce)."""
        v = _veta(["Vyšlo", "to", "1985", "."], pripojene={2})
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens], ["Vyšlo", "to", "1985", "."])
        self.assertEqual(n, 0)

class TestCiselneSkupiny(unittest.TestCase):
    def test_oddelovac_tisicu(self):
        """UDPipe dá „30 000\" jako DVA samostatné nummod:gov, takže
        AG-METRON vidí dvě čísla místo jednoho a naměří 30. conBond2 to má
        v etalonu jako doloženou mezeru (§ 3.4 koncepce)."""
        v = _veta(["V", "úlu", "je", "30", "000", "dělnic"], pripojene=set())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertIn("30 000", [t.form for t in out.tokens])
        self.assertEqual(n, 1)

    def test_vicenasobny_oddelovac(self):
        v = _veta(["Stálo", "to", "1", "250", "000", "korun"], pripojene=set())
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertIn("1 250 000", [t.form for t in out.tokens])

    def test_desetinna_carka(self):
        """„3,14\" je tři tokeny: 3 | , | 14."""
        v = _veta(["Hodnota", "je", "3", ",", "14", "metru"], pripojene={2, 3})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertIn("3,14", [t.form for t in out.tokens])

    def test_rok_a_dalsi_slovo_se_nesluci(self):
        """ŘEZ: slučují se jen skupiny PRÁVĚ TŘÍ číslic. Jinak by se
        „roku 1890 Praha\" chovalo jako číselná skupina (§ 3.4)."""
        v = _veta(["V", "roce", "1890", "zemřel"], pripojene=set())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)
        self.assertIn("1890", [t.form for t in out.tokens])

    def test_dve_cislice_po_mezere_se_nesluci(self):
        """„30 00\" není oddělovač tisíců — jsou to dvě čísla."""
        v = _veta(["bylo", "30", "00", "kusů"], pripojene=set())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)

class TestNesjednocujeZnaky(unittest.TestCase):
    def test_pomlcky_zustavaji_rozlisene(self):
        """En-dash proti spojovníku nese informaci, na které stojí AG-BIO:
        rozsah „1926 – 2011\" proti názvu „Praha - Libeň\". Sjednocení by ji
        zničilo, a k ničemu by nepomohlo — druh pomlčky hranice tokenů
        nemění (§ 13.6 koncepce)."""
        v = _veta(["Praha", "-", "Libeň", "–", "2011"], pripojene=set())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.form for t in out.tokens],
                         ["Praha", "-", "Libeň", "–", "2011"])
        self.assertEqual(n, 0)

    def test_uvozovky_zustavaji(self):
        v = _veta(["Řekl", "„", "Ahoj", "“"], pripojene=set())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)

class TestInvarianty(unittest.TestCase):
    def test_text_vety_se_nemeni(self):
        """Oprava mění hranice tokenů, NIKDY text. `source` je klíč cache;
        kdyby se změnil, cache by se rozpadla (§ 6 koncepce)."""
        v = _veta(["R", ".", "U", ".", "R", ".", "je", "drama"],
                  pripojene={0, 1, 2, 3, 4})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(out.source, v.source)

    def test_id_jsou_souvisla_od_jedne(self):
        """Po sloučení se musí přečíslovat, jinak je CoNLL-U neplatný."""
        v = _veta(["R", ".", "U", ".", "R", ".", "je"], pripojene={0,1,2,3,4})
        out, _ = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual([t.id for t in out.tokens], list(range(1, len(out.tokens)+1)))

    def test_veta_bez_vady_projde_beze_zmeny(self):
        """Nejčastější případ. Kdyby se měnil, neplatí měření § 13.5."""
        v = _veta(["Petr", "je", "v", "Praze"], pripojene=set())
        out, n = tokenize.retokenize(v, PRAVIDLA)
        self.assertEqual(n, 0)
        self.assertEqual(out.tokens, v.tokens)

class TestOtisk(unittest.TestCase):
    def test_otisk_se_meni_se_seznamem(self):
        """Verze tokenizéru je otisk pravidel, ne ruční číslo — ruční
        zastará v první chvíli, kdy někdo přidá zkratku (§ 4 koncepce)."""
        a = tokenize.Rules(frozenset({"tzv"}), 2)
        b = tokenize.Rules(frozenset({"tzv", "např"}), 2)
        self.assertNotEqual(tokenize.fingerprint(a), tokenize.fingerprint(b))

    def test_otisk_je_stabilni_vuci_poradi(self):
        """Množina nemá pořadí; otisk se nesmí měnit mezi běhy."""
        a = tokenize.Rules(frozenset({"tzv", "např"}), 2)
        b = tokenize.Rules(frozenset({"např", "tzv"}), 2)
        self.assertEqual(tokenize.fingerprint(a), tokenize.fingerprint(b))
```

Pomocná funkce `_veta(formy, pripojene)` staví `Sentence` s `SpaceAfter=No`
na indexech z `pripojene` a se `source` složeným z forem podle těchto mezer.

- [ ] **Krok 2: Spusť test, musí spadnout**

Spusť: `./run-python -m unittest cb_udpipe.tests.test_tokenize -v`
Očekávej: FAIL — `ModuleNotFoundError`

- [ ] **Krok 3: Napiš `tokenize.py`**

Pořadí pravidel je významné a patří do docstringu: **nejdřív běh písmen**
(`R.U.R.`), pak jednoslovné zkratky, pak řadové číslovky, nakonec číselné
skupiny. Kdyby se řadové číslovky zkoušely dřív, `n. l.` by se rozpadlo;
kdyby se číselné skupiny zkoušely dřív než řadové číslovky, `20 . 000`
by se sloučilo špatně.

`Rules` proto nese i `merge_number_groups` a `merge_decimal_comma` a obojí
vstupuje do otisku (`fingerprint`) — je to změna tokenizace jako každá jiná.

`fingerprint` = `sha256` z `json.dumps(sorted(abbreviations)) + min_pairs`,
prvních 12 hex znaků.

- [ ] **Krok 4: Spusť test, musí projít**

Spusť: `./run-python -m unittest cb_udpipe.tests.test_tokenize -v`
Očekávej: PASS, 12 testů

- [ ] **Krok 5: Commit**

```bash
git add cb_udpipe/tokenize.py cb_udpipe/tests/test_tokenize.py
git commit -m "cb-udpipe: pravidla opravy tokenizace (zkratky, řadové číslovky)"
```

---

## Úkol 4: Cache

**Soubory:**
- Vytvoř: `cb_udpipe/cache.py`
- Test: `cb_udpipe/tests/test_cache.py`

**Rozhraní:**
- Spotřebovává: `conllu.Sentence`, `conllu.Token` (úkol 2)
- Poskytuje:
  ```python
  CACHE_FORMAT_VERSION = 1

  class Cache:
      def __init__(self, *, path: Path, model: str, tokenizer: str): ...
      def get(self, source: str) -> Sentence | None: ...
      def put(self, sentence: Sentence, *, ts: str) -> None: ...
      def stats(self) -> dict[str, Any]: ...
      def close(self) -> None: ...
  ```
  `ts` se předává zvenčí — funkce, která si sama zavolá `time.time()`, nejde
  deterministicky otestovat (§ 3 politiky).

- [ ] **Krok 1: Napiš padající test**

```python
class TestCache(unittest.TestCase):
    def test_ulozi_a_vrati(self):
        c = cache.Cache(path=self.p, model="m", tokenizer="a91f3e")
        c.put(VETA, ts=TS)
        self.assertEqual(c.get(VETA.source), VETA)

    def test_neznama_veta_vrati_none(self):
        """None znamená „nemám\", ne chybu — volající pak větu rozebere."""
        c = cache.Cache(path=self.p, model="m", tokenizer="a91f3e")
        self.assertIsNone(c.get("Tuhle větu neznám."))

    def test_index_prezije_restart(self):
        """Index se staví při startu ze souboru; bez toho je cache po
        restartu prázdná, i když soubor má data."""
        c = cache.Cache(path=self.p, model="m", tokenizer="a91f3e")
        c.put(VETA, ts=TS); c.close()
        c2 = cache.Cache(path=self.p, model="m", tokenizer="a91f3e")
        self.assertEqual(c2.get(VETA.source), VETA)

    def test_jina_verze_tokenizeru_neni_zasah(self):
        """Kdyby se vrátil rozbor jiné tokenizace, byla by to tichá záměna
        dat — přesně to, co INV-9 a § 14 politiky zakazují (§ 4 koncepce)."""
        c = cache.Cache(path=self.p, model="m", tokenizer="stara")
        c.put(VETA, ts=TS); c.close()
        c2 = cache.Cache(path=self.p, model="m", tokenizer="nova")
        self.assertIsNone(c2.get(VETA.source))

    def test_nfc_normalizace_klice(self):
        """„ě\" zapsané dvěma kódovými body musí trefit tutéž větu.
        Totéž dělá sám server (unicodedata.normalize NFC)."""
        c = cache.Cache(path=self.p, model="m", tokenizer="a91f3e")
        c.put(VETA, ts=TS)
        rozlozene = unicodedata.normalize("NFD", VETA.source)
        self.assertIsNotNone(c.get(rozlozene))

    def test_poskozeny_radek_se_preskoci_a_spocita(self):
        """Po pádu procesu je rozbitý nejvýš poslední řádek. Tiše se
        nezahazuje — rostoucí číslo je signál, že něco padá (§ 7 koncepce)."""
        self.p.write_text('{"source": "A", "tokens": []}\n{"nedopsan\n',
                          encoding="utf-8")
        c = cache.Cache(path=self.p, model="m", tokenizer="a91f3e")
        self.assertEqual(c.stats()["corrupt"], 1)

    def test_zapis_je_pripis_ne_prepis(self):
        """Jeden velký JSON by se musel při každé větě přepsat celý;
        conBond2 to měl a při 70 MB to bolelo."""
        c = cache.Cache(path=self.p, model="m", tokenizer="a91f3e")
        c.put(VETA, ts=TS)
        velikost = self.p.stat().st_size
        c.put(VETA2, ts=TS)
        self.assertGreater(self.p.stat().st_size, velikost)

    def test_stats_nese_pocty(self):
        c = cache.Cache(path=self.p, model="m", tokenizer="a91f3e")
        c.put(VETA, ts=TS)
        s = c.stats()
        self.assertEqual(s["sentences"], 1)
        self.assertEqual(s["corrupt"], 0)
        self.assertEqual(s["format_version"], cache.CACHE_FORMAT_VERSION)
```

- [ ] **Krok 2: Spusť test, musí spadnout**

Spusť: `./run-python -m unittest cb_udpipe.tests.test_cache -v`

- [ ] **Krok 3: Napiš `cache.py`**

Index je `dict[str, int]` (NFC klíč → offset řádku). Při startu se soubor
čte po řádcích, u každého se zapamatuje offset **před** čtením. Záznam
s jiným `tokenizer` se do indexu nezakládá. Zápis: `open(mode="a")`,
`write` + `flush` + `os.fsync`.

- [ ] **Krok 4: Spusť test, musí projít**

Spusť: `./run-python -m unittest cb_udpipe.tests.test_cache -v`
Očekávej: PASS, 8 testů

- [ ] **Krok 5: Commit**

```bash
git add cb_udpipe/cache.py cb_udpipe/tests/test_cache.py
git commit -m "cb-udpipe: JSONL cache s indexem klíč→offset"
```

---

## Úkol 5: Klient UDPipe serveru

**Soubory:**
- Vytvoř: `cb_udpipe/upstream.py`
- Test: `cb_udpipe/tests/test_upstream.py`

**Rozhraní:**
- Poskytuje:
  ```python
  class UpstreamUnavailable(Exception): ...
  class UpstreamError(Exception): ...

  class Upstream:
      def __init__(self, *, endpoint: str, timeout_s: float, log=None): ...
      def models(self) -> dict[str, Any]: ...
      def tokenize(self, text: str, *, trace: str | None = None) -> str: ...
      def tag_and_parse(self, conllu_text: str, *, trace=None) -> str: ...
  ```
  Obě metody vracejí syrový CoNLL-U. `tokenize` posílá `tokenizer=""`,
  `tag_and_parse` posílá `tagger=""` a `parser=""` **bez** `tokenizer`.

- [ ] **Krok 1: Napiš padající test**

Testy běží proti zabudovanému `http.server`, který vrací zmražené odpovědi —
žádný běžící UDPipe.

```python
class TestUpstream(unittest.TestCase):
    def test_tokenize_posila_tokenizer_bez_taggeru(self):
        """Fáze 1 nesmí poslat tagger ani parser — server by načetl síť
        a spočítal embeddingy, což je celý rozdíl mezi levným a drahým
        voláním (§ 2 koncepce)."""
        u = upstream.Upstream(endpoint=self.url, timeout_s=5)
        u.tokenize("Petr je v Praze.")
        self.assertIn("tokenizer=", self.server.posledni_telo)
        self.assertNotIn("tagger=", self.server.posledni_telo)

    def test_tag_and_parse_neposila_tokenizer(self):
        """Fáze 4 posílá hotové CoNLL-U. Kdyby šel `tokenizer`, server by
        segmentoval znovu a naše oprava by se zahodila."""
        u = upstream.Upstream(endpoint=self.url, timeout_s=5)
        u.tag_and_parse("# text = A\n1\tA\t_\t_\t_\t_\t_\t_\t_\t_\n\n")
        self.assertIn("tagger=", self.server.posledni_telo)
        self.assertNotIn("tokenizer=", self.server.posledni_telo)

    def test_nedostupna_sluzba_je_typovana_chyba(self):
        """Nikdy prázdná odpověď — ta by se slila s platným prázdným
        výsledkem (INV-9)."""
        u = upstream.Upstream(endpoint="http://127.0.0.1:1", timeout_s=1)
        with self.assertRaises(upstream.UpstreamUnavailable):
            u.tokenize("A")

    def test_hlaska_nese_adresu_a_navod(self):
        """Chybová hláška má povinně tři věci: který modul, na jaké adrese
        a čím ho spustit (§ 1 politiky)."""
        u = upstream.Upstream(endpoint="http://127.0.0.1:1", timeout_s=1)
        with self.assertRaises(upstream.UpstreamUnavailable) as e:
            u.tokenize("A")
        self.assertIn("127.0.0.1:1", str(e.exception))
        self.assertIn("./cb-udpipe.py start", str(e.exception))

    def test_dlouhy_vstup_projde(self):
        """PAST z conBondu i jellyAI3: inline `-F data=` ořezával vstup
        na ~485 znaků a bible ztrácela 95 % textu. Posíláme
        x-www-form-urlencoded, ale test je levný a past stála dva projekty
        hodně času."""
        u = upstream.Upstream(endpoint=self.url, timeout_s=5)
        dlouhy = "Petr je v Praze. " * 200
        u.tokenize(dlouhy)
        self.assertIn(urllib.parse.quote_plus("Praze"), self.server.posledni_telo)
        self.assertGreater(len(self.server.posledni_telo), 2000)

    def test_nfc_normalizace_vstupu(self):
        """Server si vstup normalizuje sám; děláme to i my, aby klíč cache
        odpovídal tomu, co se poslalo (§ 4 koncepce)."""
        u = upstream.Upstream(endpoint=self.url, timeout_s=5)
        u.tokenize(unicodedata.normalize("NFD", "Soňa"))
        self.assertIn(urllib.parse.quote_plus("Soňa"), self.server.posledni_telo)
```

- [ ] **Krok 2: Spusť test, musí spadnout**

- [ ] **Krok 3: Napiš `upstream.py`**

Tělo požadavku je `urllib.parse.urlencode`, odpověď JSON s klíčem `result`.
`urllib.error.URLError` → `UpstreamUnavailable`, HTTP 4xx/5xx → `UpstreamError`
s tělem hlášky serveru.

- [ ] **Krok 4: Spusť test, musí projít**

Očekávej: PASS, 6 testů

- [ ] **Krok 5: Commit**

```bash
git add cb_udpipe/upstream.py cb_udpipe/tests/test_upstream.py
git commit -m "cb-udpipe: klient UDPipe serveru, jediné místo s HTTP ven"
```

---

## Úkol 6: Doménová logika

**Soubory:**
- Vytvoř: `cb_udpipe/service.py`
- Test: `cb_udpipe/tests/test_service.py`

**Rozhraní:**
- Spotřebovává: `conllu`, `tokenize`, `cache`, `upstream` (úkoly 2–5)
- Poskytuje:
  ```python
  @dataclass(frozen=True)
  class ParsedSentence:
      source: str
      tokens: tuple[Token, ...]
      multiword: tuple[Multiword, ...]
      from_cache: bool
      retokenized: int

  @dataclass(frozen=True)
  class ParseResult:
      sentences: tuple[ParsedSentence, ...]
      cached: int
      parsed: int
      skipped: tuple[dict, ...]

  class UdpipeService:
      def __init__(self, config: dict, *, upstream=None, log=None,
                   clock=None): ...
      def parse(self, text: str, *, trace=None) -> ParseResult: ...
      def tokenize_only(self, text: str, *, trace=None) -> list[Sentence]: ...
      def health(self) -> dict[str, Any]: ...
      def summary(self) -> dict[str, Any]: ...
      def close(self) -> None: ...
  ```
  `upstream` a `clock` se dají podstrčit — testy tím běží bez UDPipe.

- [ ] **Krok 1: Napiš padající test**

```python
class TestParse(unittest.TestCase):
    def test_ctyri_faze(self):
        """Cache zásah znamená, že se dorozbor nezavolá vůbec."""
        s = _service(upstream=FakeUpstream())
        s.parse("Petr je v Praze.")            # naplní cache
        s.upstream.reset()
        r = s.parse("Petr je v Praze.")        # druhý průchod
        self.assertEqual(r.cached, 1)
        self.assertEqual(r.parsed, 0)
        self.assertEqual(s.upstream.pocet_tag_and_parse, 0)

    def test_smiseny_vstup(self):
        """Věta A z cache, věta B na dorozbor — jedním voláním jdou jen
        ty chybějící."""
        s = _service(upstream=FakeUpstream())
        s.parse("Petr je v Praze.")
        r = s.parse("Petr je v Praze. Jan je v Brně.")
        self.assertEqual((r.cached, r.parsed), (1, 1))

    def test_prazdny_vstup(self):
        """T-K2: prázdno není chyba a není to výmysl."""
        s = _service(upstream=FakeUpstream())
        r = s.parse("")
        self.assertEqual(r.sentences, ())
        self.assertEqual(s.summary()["parse"]["empty"], 1)

    def test_dlouha_veta_se_preskoci_s_duvodem(self):
        """Mez serveru je 1000 slov. Přeskočená věta musí být vidět jako
        přeskočená s důvodem, ne jako tichá díra."""
        s = _service(upstream=FakeUpstream(dlouha_veta=True))
        r = s.parse("slovo " * 1200)
        self.assertEqual(r.skipped[0]["reason"], "sentence_too_long")
        self.assertEqual(s.summary()["parse"]["skipped"], 1)

    def test_tokenizace_se_promitne_do_vysledku(self):
        """Kvůli tomuhle modul existuje (§ 1 koncepce)."""
        s = _service(upstream=FakeUpstream())
        r = s.parse("R.U.R. je drama.")
        self.assertIn("R.U.R.", [t.form for t in r.sentences[0].tokens])
        self.assertEqual(r.sentences[0].retokenized, 1)

    def test_nedostupny_upstream_probubla(self):
        """Povinná závislost → typovaná chyba, nikdy prázdný výsledek."""
        s = _service(upstream=FakeUpstream(nedostupny=True))
        with self.assertRaises(upstream.UpstreamUnavailable):
            s.parse("Petr je v Praze.")

    def test_summary_pocita_podle_metody_a_stavu(self):
        s = _service(upstream=FakeUpstream())
        s.parse("Petr je v Praze.")
        self.assertEqual(s.summary()["parse"]["ok"], 1)

    def test_health_hlasi_nedostupny_upstream(self):
        s = _service(upstream=FakeUpstream(nedostupny=True))
        h = s.health()
        self.assertFalse(h["upstream"]["available"])
        self.assertEqual(h["status"], "degraded")
```

- [ ] **Krok 2: Spusť test, musí spadnout**

- [ ] **Krok 3: Napiš `service.py`**

`parse()` implementuje čtyři fáze z § 2 koncepce. Dorozbor jde po dávkách
`batch_sentences`. Věty delší než `max_sentence_words` se z dávky vyjmou
**před** odesláním a zapíší do `skipped` — jinak by server vrátil chybu
na celou dávku kvůli jedné větě.

- [ ] **Krok 4: Spusť test, musí projít**

Očekávej: PASS, 8 testů

- [ ] **Krok 5: Commit**

```bash
git add cb_udpipe/service.py cb_udpipe/tests/test_service.py
git commit -m "cb-udpipe: doménová logika — čtyři fáze rozboru"
```

---

## Úkol 7: REST vrstva

**Soubory:**
- Vytvoř: `cb_udpipe/api.py`
- Vytvoř: `cb_udpipe/__init__.py`
- Test: `cb_udpipe/tests/test_api.py`

**Rozhraní:**
- Poskytuje: `make_api_server(service, *, host, port, config) -> ApiServer`,
  `__version__ = "0.1.0"`, `__api__ = ["v1"]`

- [ ] **Krok 1: Napiš padající test**

```python
class TestApi(unittest.TestCase):
    def test_version_mimo_v1(self):
        """Kdo se ptá na verzi, ještě neví, kterou verzi rozhraní volat."""
        r = self._get("/version")
        self.assertEqual(r["module"], "cb-udpipe")
        self.assertEqual(r["api"], ["v1"])
        self.assertIn("tokenizer", r)

    def test_parse_vraci_vety_s_tokeny(self):
        r = self._post("/v1/parse", {"text": "R.U.R. je drama."})
        self.assertIn("R.U.R.", [t["form"] for t in r["sentences"][0]["tokens"]])

    def test_prazdny_vstup_je_200_ne_404(self):
        """Prázdný výsledek není chyba (§ 7 politiky)."""
        status, r = self._post_raw("/v1/parse", {"text": ""})
        self.assertEqual(status, 200)
        self.assertEqual(r["sentences"], [])

    def test_chybejici_klic_je_400_s_typem(self):
        status, r = self._post_raw("/v1/parse", {"txt": "A"})
        self.assertEqual(status, 400)
        self.assertEqual(r["error"]["type"], "invalid_request")

    def test_nedostupny_upstream_je_503_a_rekne_ktery(self):
        status, r = self._post_raw("/v1/parse", {"text": "A"})
        self.assertEqual(status, 503)
        self.assertEqual(r["error"]["type"], "upstream_unavailable")
        self.assertIn("cb-udpipe", r["error"]["message"])

    def test_prilis_velke_telo_je_413(self):
        status, r = self._post_raw("/v1/parse", {"text": "x" * 3_000_000})
        self.assertEqual(status, 413)

    def test_vystup_je_vzdy_objekt_ne_pole(self):
        """Do objektu jde přidat klíč, aniž se rozbijí klienti."""
        r = self._get("/v1/summary")
        self.assertIsInstance(r, dict)

    def test_determinismus(self):
        """Táž data a týž požadavek dají tutéž odpověď včetně pořadí."""
        a = self._post("/v1/parse", {"text": "Petr je v Praze. Jan je v Brně."})
        b = self._post("/v1/parse", {"text": "Petr je v Praze. Jan je v Brně."})
        self.assertEqual(a, b)
```

- [ ] **Krok 2: Spusť test, musí spadnout**

- [ ] **Krok 3: Napiš `api.py` a `__init__.py`**

`api.py` nesmí obsahovat **jediné rozhodnutí o doméně** (§ 1 politiky):
rozbalí požadavek, zavolá `service`, zabalí odpověď. Když se v něm objeví `if`
nad obsahem dat, patří do `service.py`.

- [ ] **Krok 4: Spusť test, musí projít**

Očekávej: PASS, 8 testů

- [ ] **Krok 5: Commit**

```bash
git add cb_udpipe/api.py cb_udpipe/__init__.py cb_udpipe/tests/test_api.py
git commit -m "cb-udpipe: REST vrstva bez doménové logiky"
```

---

## Úkol 8: Řízení služby a procesu UDPipe

**Soubory:**
- Vytvoř: `cb_udpipe/control.py`
- Vytvoř: `cb-udpipe.py` (kořen projektu, `chmod +x`)
- Vytvoř: `cb_udpipe/scripts/fetch-models.sh`
- Test: `cb_udpipe/tests/test_control.py`

**Rozhraní:**
- Poskytuje: `main(argv) -> int` s příkazy `start`, `stop`, `restart`,
  `reload`, `status`. Návratové kódy `0` uspěl, `1` selhal,
  `2` špatné argumenty nebo konfigurace, `3` služba neběží.

- [ ] **Krok 1: Napiš padající test**

```python
class TestControl(unittest.TestCase):
    def test_status_na_nebezici_sluzbu_vraci_3(self):
        self.assertEqual(control.main(["status", "--config", self.cfg]), 3)

    def test_status_uvadi_port_i_u_nebezici_sluzby(self):
        """status je první příkaz, který člověk zavolá, když něco nefunguje
        — musí z něj být poznat, kam se má připojit (§ 12 politiky)."""
        control.main(["status", "--config", self.cfg])
        self.assertIn("42200", self.out.getvalue())

    def test_chybejici_model_je_2_s_navodem(self):
        """Služba nenastartuje a řekne, který soubor chybí a který skript
        ho pořídí (§ 19 politiky)."""
        kod = control.main(["start", "--config", self.cfg_bez_modelu])
        self.assertEqual(kod, 2)
        self.assertIn("fetch-models.sh", self.err.getvalue())

    def test_spatna_konfigurace_je_2_ne_1(self):
        self.assertEqual(control.main(["start", "--config", self.cfg_vadny]), 2)

    def test_stop_na_nebezici_sluzbu_vraci_3(self):
        self.assertEqual(control.main(["stop", "--config", self.cfg]), 3)

    def test_osirely_pid_se_prepise_ne_zamlci(self):
        """Proces s tím PID neexistuje → soubor je po spadlé službě."""
        Path(self.pid_file).write_text("999999")
        control.main(["status", "--config", self.cfg])
        self.assertIn("osiřel", self.out.getvalue())
```

Testy startu celé služby (včetně UDPipe) sem **nepatří** — vyžadovaly by
model 357 MB. Ověřují se v úkolu 12 jako měření, ne jako jednotkový test.

- [ ] **Krok 2: Spusť test, musí spadnout**

- [ ] **Krok 3: Napiš `control.py`, `cb-udpipe.py` a `fetch-models.sh`**

`start` v pořadí: konfigurace → model → UDPipe na 42201 → čekání na
`GET /models` → naše služba → `GET /version` → `GET /v1/health`.
`stop` v opačném pořadí.

Prostředí procesu UDPipe (§ 9 koncepce):
```python
prostredi = {
    "HF_HOME": str(hf_home),
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "TOKENIZERS_PARALLELISM": "false",
}
```

`fetch-models.sh` umí zkopírovat model z conBondu2 (`--from-conbond2 CESTA`)
a ověří kontrolní součet. Stahování z LINDATu je v `README.md` modulu jako
popsaný ruční postup — URL bez ověření do skriptu nepatří.

- [ ] **Krok 4: Spusť test, musí projít**

Očekávej: PASS, 6 testů

- [ ] **Krok 5: Commit**

```bash
chmod +x cb-udpipe.py cb_udpipe/scripts/fetch-models.sh
git add cb-udpipe.py cb_udpipe/control.py cb_udpipe/scripts/ \
        cb_udpipe/tests/test_control.py
git commit -m "cb-udpipe: řízení služby včetně vlastního procesu UDPipe"
```

---

## Úkol 9: Klient pro ostatní moduly a shoda tváří

**Soubory:**
- Vytvoř: `cb_udpipe/client.py`
- Modifikuj: `cb_udpipe/__init__.py` (přidej `UdpipeClient`, výjimky)
- Test: `cb_udpipe/tests/test_parity.py`

**Rozhraní:**
- Poskytuje:
  ```python
  class ServiceUnavailable(Exception): ...
  class IncompatibleApi(Exception): ...

  class UdpipeClient:
      def __init__(self, *, endpoint: str | None = None, log=None,
                   timeout_s: float = 600, api: str = "v1"): ...
      def parse(self, *, text: str, trace=None) -> ParseResult: ...
      def tokenize_only(self, *, text: str, trace=None) -> list[Sentence]: ...
  ```

- [ ] **Krok 1: Napiš padající test (T-K3 a T-K4)**

```python
class TestParita(unittest.TestCase):
    def test_v_procesu_a_pres_sit_daji_totez(self):
        """T-K3 — jinak modul nejde použít dvěma způsoby a celé rozdělení
        na service/api ztrácí smysl (§ 1 politiky)."""
        v_procesu = self.service.parse("R.U.R. je drama Karla Čapka.")
        pres_sit = self.client.parse(text="R.U.R. je drama Karla Čapka.")
        self.assertEqual(pres_sit, v_procesu)

    def test_klient_selze_pri_vytvoreni_ne_pri_volani(self):
        """T-K4 — klient nad neběžící službou je tikající chyba; ukázala by
        se uprostřed dávky s polovinou zapsaných výsledků (§ 1 politiky)."""
        with self.assertRaises(client.ServiceUnavailable) as e:
            client.UdpipeClient(endpoint="http://127.0.0.1:1")
        zprava = str(e.exception)
        self.assertIn("cb-udpipe", zprava)
        self.assertIn("127.0.0.1:1", zprava)
        self.assertIn("./cb-udpipe.py start", zprava)

    def test_nekompatibilni_api_je_vlastni_vyjimka(self):
        with self.assertRaises(client.IncompatibleApi):
            client.UdpipeClient(endpoint=self.url, api="v99")

    def test_klient_loguje_obe_strany(self):
        """Klient je jediné místo, kde je vidět obě strany hranice.
        Když se rozejdou, je chyba mezi nimi (§ 1 politiky)."""
        log = FakeLog()
        c = client.UdpipeClient(endpoint=self.url, log=log)
        c.parse(text="Petr je v Praze.", trace="t-1")
        self.assertTrue(any(z["method"] == "parse" and z["trace"] == "t-1"
                            for z in log.zaznamy))

    def test_smazane_run_je_neskodne(self):
        """T-K4 — run/ nesmí přežít restart a jeho smazání nesmí nic
        pokazit (§ 2 politiky)."""
        shutil.rmtree(self.run_dir)
        self.assertIsNotNone(self.client.parse(text="Petr je v Praze."))
```

- [ ] **Krok 2: Spusť test, musí spadnout**

- [ ] **Krok 3: Napiš `client.py`**

Konstruktor volá `GET /version` s krátkým timeoutem. Hláška o nedostupnosti
má povinně tři věci: modul, adresu, příkaz ke spuštění.

- [ ] **Krok 4: Spusť test, musí projít**

Očekávej: PASS, 5 testů

- [ ] **Krok 5: Commit**

```bash
git add cb_udpipe/client.py cb_udpipe/__init__.py cb_udpipe/tests/test_parity.py
git commit -m "cb-udpipe: klient pro ostatní moduly, T-K3 a T-K4"
```

---

## Úkol 10: Napojení na logovátko

**Soubory:**
- Modifikuj: `cb_udpipe/service.py` (záznamy na hranicích)
- Modifikuj: `cb_udpipe/client.py` (záznamy obou stran)
- Test: `cb_udpipe/tests/test_logging.py`

- [ ] **Krok 1: Napiš padající test**

```python
class TestLogovani(unittest.TestCase):
    def test_ctyri_stavy_se_neslevaji(self):
        """empty a error se nikde neslévají — jinak měření odmění právě
        tu chybu, kterou má chytat."""
        s = _service(log=self.log, upstream=FakeUpstream())
        s.parse("")
        z = [x for x in self.log.zaznamy if x["method"] == "parse"]
        self.assertEqual(z[0]["result"], "empty")

    def test_stopa_prochazi_vsemi_zaznamy(self):
        """Bez společné stopy nejde z logu složit jeden průchod."""
        s = _service(log=self.log, upstream=FakeUpstream())
        s.parse("Petr je v Praze.", trace="q-7f3a91")
        self.assertTrue(all(z["trace"] == "q-7f3a91" for z in self.log.zaznamy))

    def test_modul_stopu_nikdy_nerazi(self):
        """Kdyby si ji razil každý modul, rozpadne se řetěz na tolik kusů,
        kolik je modulů — a to je horší než žádná stopa."""
        s = _service(log=self.log, upstream=FakeUpstream())
        s.parse("Petr je v Praze.")
        self.assertTrue(all(z["trace"] is None for z in self.log.zaznamy))

    def test_log_objects_miss_loguje_jen_nove(self):
        """Logovat cache zásah jako objekt znamená psát podruhé to, co už
        v cache leží (§ 10 koncepce)."""
        s = _service(log=self.log, upstream=FakeUpstream(),
                     log_objects="miss")
        s.parse("Petr je v Praze.")
        prvni = len(self.log.objekty)
        s.parse("Petr je v Praze.")
        self.assertEqual(len(self.log.objekty), prvni)

    def test_log_objects_off_neloguje_nic(self):
        s = _service(log=self.log, upstream=FakeUpstream(), log_objects="off")
        s.parse("Petr je v Praze.")
        self.assertEqual(self.log.objekty, [])

    def test_retokenized_loguje_jen_zasahy(self):
        """Ladicí režim pravidel § 3: ukáže přesně věty, do kterých modul
        zasáhl, a nic jiného."""
        s = _service(log=self.log, upstream=FakeUpstream(),
                     log_objects="retokenized")
        s.parse("Petr je v Praze.")
        self.assertEqual(self.log.objekty, [])
        s.parse("R.U.R. je drama.")
        self.assertEqual(len(self.log.objekty), 1)

    def test_nedostupne_logovatko_neshodi_modul(self):
        """Nepovinná závislost → degradace, ne pád (§ 9 politiky)."""
        s = _service(log=RozbityLog(), upstream=FakeUpstream())
        self.assertIsNotNone(s.parse("Petr je v Praze."))
```

- [ ] **Krok 2: Spusť test, musí spadnout**

- [ ] **Krok 3: Doplň logování**

Metody na hranicích: `parse`, `tokenize`, `retokenize`, `cache_lookup`,
`upstream`. `duration_ms` se měří a předává explicitně.

- [ ] **Krok 4: Spusť test, musí projít**

Očekávej: PASS, 7 testů

- [ ] **Krok 5: Commit**

```bash
git add cb_udpipe/service.py cb_udpipe/client.py cb_udpipe/tests/test_logging.py
git commit -m "cb-udpipe: napojení na logovátko, textově i objektově"
```

---

## Úkol 11: Vendorovaný UDPipe a model

**Soubory:**
- Vytvoř: `cb_udpipe/vendor/` (git submodul `https://github.com/ufal/udpipe.git`)
- Modifikuj: `requirements.txt` (odkomentuj sekci cb-udpipe)
- Modifikuj: `.gitignore` (přidej `cb_udpipe/vendor/udpipe2-src/models-*`)
- Vytvoř: `ZDROJ.md` (kořen projektu)

- [ ] **Krok 1: Přidej submodul a závislosti**

```bash
git submodule add https://github.com/ufal/udpipe.git cb_udpipe/vendor/udpipe2-src
```

V `requirements.txt` odkomentuj (verze jsou ověřená kombinace z conBondu2):

```
tensorflow==2.21.0
tf_keras==2.21.0
transformers==4.49.0
ufal.udpipe==1.4.0.1
ufal.morphodita==1.11.3.3
ufal.chu_liu_edmonds==1.0.3
```

- [ ] **Krok 2: Pořiď model**

```bash
cb_udpipe/scripts/fetch-models.sh --from-conbond2 ../conBond2
./run-python --check
```

- [ ] **Krok 3: Zapiš licence do `ZDROJ.md`**

```markdown
| co | odkud | licence |
|---|---|---|
| UDPipe 2 (zdrojáky) | github.com/ufal/udpipe | MPL 2.0 |
| cs_all-ud-2.17-251125 | LINDAT/CLARIN, hdl.handle.net/11234/1-6046 | CC BY-NC-SA |
| RobeCzech | ufal/robeczech-base | dle ÚFAL |
```

- [ ] **Krok 4: Ověř, že nic licencovaného nevstoupilo do gitu**

```bash
git status --porcelain | grep -E '\.model|models/|hf/' && echo "CHYBA" || echo "čisté"
```

- [ ] **Krok 5: Commit**

```bash
git add .gitmodules cb_udpipe/vendor requirements.txt .gitignore ZDROJ.md
git commit -m "cb-udpipe: vendorovaný UDPipe 2, závislosti, licence"
```

---

## Úkol 12: Měření, dokumentace, uzavření

**Soubory:**
- Vytvoř: `cb_udpipe/README.md`
- Vytvoř: `README-UDPIPE.md` (kořen)
- Vytvoř: `cb_udpipe/docs/metody.md`
- Vytvoř: `cb_udpipe/docs/prirucka.md`
- Vytvoř: `cb_udpipe/tests/data/mereni.jsonl` (zmražený vzorek vět)
- Vytvoř: `cb_udpipe/scripts/mereni.py`

- [ ] **Krok 1: Zmraz měřicí vzorek**

500 vět z korpusu conBondu2 do `tests/data/mereni.jsonl`. **Zmražené v gitu**
(§ 11 politiky): sada, která se přepočítává při každém běhu, tiše zmenší sama
sebe, když ji chyba připraví o položky — a pak pochválí právě tu chybu, kterou
má chytat.

- [ ] **Krok 2: Napiš měřicí skript**

`scripts/mereni.py` změří a vypíše s verzí dat a konfigurace:

| co | proč |
|---|---|
| podíl cache zásahů při druhém průchodu | důvod, proč modul existuje |
| doba tokenizace : doba dorozboru | **na tom stojí dvoufázový postup** (§ 2 koncepce) |
| podíl vět, kterým oprava změnila tokenizaci | očekávání ~9 % (§ 13.1) |
| velikost cache na větu | z toho plyne, jestli je někdy potřeba strop |
| doba předehřátí | údaj o stroji |

- [ ] **Krok 3: Protiváha — shoda cache s čerstvým rozborem**

```python
def test_cache_se_shoduje_s_cerstvym_rozborem(self):
    """Podíl zásahů jde nafouknout volnějším klíčem. Protiváha: u vzorku
    vět se porovná, co vrátila cache, s tím, co vrátí UDPipe teď.
    Rozdíl je chyba klíče, ne remíza (§ 13 koncepce)."""
```

- [ ] **Krok 4: Spusť měření a zapiš čísla**

```bash
./cb-udpipe.py start
./run-python cb_udpipe/scripts/mereni.py > cb_udpipe/docs/mereni-$(date +%Y-%m-%d).md
```

Naměřená čísla nahradí odhady v § 14 koncepce (registr prahů) a doplní se
do `README.md` modulu jako `K-6`.

- [ ] **Krok 5: Napiš dokumentaci**

`cb_udpipe/README.md` (`K-7`): co modul dělá, proč tak, co vědomě neřeší,
registr prahů s naměřenými čísly, **povinné a nepovinné závislosti**
(UDPipe povinná → `503`; logovátko nepovinné → degradace).

`README-UDPIPE.md` v kořeni: ukázky volání — **každá musí být spustitelná**
(§ 2 politiky). Ukázka, která se rozejde s kódem, je horší než žádná.

`docs/metody.md`: každá veřejná metoda — co dělá, proč existuje, na čem visí.
`docs/prirucka.md`: otázky, které padly při stavbě, a pasti.

- [ ] **Krok 6: Ověř celou definici hotového**

```bash
./run-python -m unittest discover -s cb_udpipe -t . -v
./cb-udpipe.py start && ./cb-udpipe.py status && ./cb-udpipe.py stop
```

Zkontroluj `K-1` až `K-8` z § 15 politiky. Sedm z osmi není sedm osmin
hotového modulu, je to nehotový modul.

- [ ] **Krok 7: Doplň modul do politiky**

`README-MODULES.md` § 5 už `cb-udpipe` v tabulce portů má — ověř, že sedí
(42200 REST, 42201 UDPipe), a doplň řádek do § 4, **pokud** se z modulu stane
sdílený. Zatím sdílený není: importuje na něj jen ten, kdo potřebuje rozbor.

- [ ] **Krok 8: Commit**

```bash
git add cb_udpipe/README.md README-UDPIPE.md cb_udpipe/docs/ \
        cb_udpipe/scripts/mereni.py cb_udpipe/tests/data/mereni.jsonl
git commit -m "cb-udpipe: měření, dokumentace, modul hotový podle K-1..K-8"
```

---

## Kontrola pokrytí návrhu

| sekce koncepce | úkol |
|---|---|
| § 1 k čemu modul je | 6, 12 |
| § 2 čtyři fáze | 5, 6 |
| § 3 pravidla tokenizace | 3 |
| § 4 klíč cache + verze tokenizéru | 3 (otisk), 4 (klíč) |
| § 5 všech deset sloupců | 2 |
| § 6 hranice modulu | 3 (co se nedělá), 7 (MISC projde) |
| § 7 cache na disku | 4 |
| § 8 co modul nabízí ven | 7, 9 |
| § 9 provoz UDPipe | 8, 11 |
| § 10 co se loguje | 10 |
| § 11 chybové stavy | 2 (`m²`), 5 (dlouhý vstup), 6, 7 |
| § 12 model místo pravidel | 3 (šev `mode`), 12 (měření) |
| § 13 měření | 12 |
| § 14 registr prahů | 1 (konfigurace), 12 (naměřená čísla) |
| § 15 co neřeší | dokumentace v 12 |
| § 16 licence | 11 |
