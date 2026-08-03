# cb-udpipe — vývojářské README

Jak si z kódu nechat rozebrat českou větu. Všechny ukázky jsou spustitelné
a ověřené; zkopíruj a jeď.

Tohle je jen to nejnutnější. Hloubka je v `cb_udpipe/docs/`:

| soubor | co v něm je |
|---|---|
| `docs/koncepce.md` | proč je modul postavený takhle, včetně všech měření |
| `docs/metody.md` | každá metoda: co dělá, proč existuje, na čem visí |
| `docs/prirucka.md` | otázky ze stavby a pasti, do kterých se dá spadnout |
| `cb_udpipe/README.md` | rozhraní, porty, prahy, závislosti modulu |

---

## Než začneš

Jsou to **dvě věci** a snadno se slijí:

| co | co to je | jak se to dělá |
|---|---|---|
| **služba** | samostatný proces, který si sám provozuje UDPipe | `./cb-udpipe.py start` — **jednou na stroji** |
| **klient** | objekt ve tvém kódu, kterým se ptáš | `UdpipeClient(...)` — **jednou při startu programu** |

```bash
./cb-udpipe.py start        # služba musí běžet
./cb-udpipe.py status       # ověření + porty
```

| adresa | co tam je |
|---|---|
| `http://127.0.0.1:42200` | REST API — sem se ptá klient |
| `http://127.0.0.1:42201` | vlastní instance UDPipe 2 — sem sahá jen služba |

První start trvá **desítky sekund**: UDPipe načítá model o 357 MB a
předehřívá síť. Zastavení je `./cb-udpipe.py stop` a ukončí obojí.

---

## Inicializace: ano, uděláš si instanci

```python
from cb_udpipe import UdpipeClient

parser = UdpipeClient()
```

To je všechno. **Adresu psát nemusíš** — klient si ji najde sám, protože ji
deklaruje sama služba ve své konfiguraci a při běhu ji zapisuje do
`run/service.port`. Kde ji vzal, si můžeš ověřit:

```python
parser.endpoint            # 'http://127.0.0.1:42200'
parser.endpoint_source     # 'run/service.port (běžící služba)'
```

Předat ji můžeš, když mluvíš s **jinou** instancí — pak přebije výchozí:

```python
parser = UdpipeClient(endpoint="http://jiny-stroj:42200")
parser.endpoint_source     # 'předáno'
```

Klient si při vytvoření ověří, že služba běží a mluví jeho verzí rozhraní:

```python
parser.server_version["version"]      # '0.1.0'
parser.server_version["tokenizer"]    # '6247b8b7a5c8'
```

**Když služba neběží, dozvíš se to hned tady** — ne až u prvního rozboru:

```
modul cb-udpipe neodpovídá na http://127.0.0.1:1/version
(<urlopen error [Errno 61] Connection refused>).
Spusť ho: ./cb-udpipe.py start
```

Je to schválně: klient nad neběžící službou je tikající chyba. Kdyby se
výpadek ukázal až u prvního `parse()`, spadlo by to uprostřed dávky, po hodině
počítání a s polovinou zapsaných výsledků.

### Jednou při startu, pak parametrem

```python
# ANO — jeden klient, předávaný tomu, kdo ho potřebuje
def zpracuj_vetu(text, parser, trace=None):
    return parser.parse(text=text, trace=trace).sentences[0]

parser = UdpipeClient()                # jednou při startu
for veta in korpus:
    zpracuj_vetu(veta, parser, trace=trace)

# NE — klient v cyklu znamená kontrolu služby v cyklu
for veta in korpus:
    UdpipeClient().parse(text=veta)
```

V modulu, který má logovátko a vlastní konfiguraci:

```python
from cb_udpipe import from_config
parser = from_config(cfg, log=log)
```

`from_config` vezme adresu z `cfg["module"]["udpipe_endpoint"]`, když tam je;
když ne, použije výchozí. Adresa cizí služby patří do konfigurace **volajícího**
(politika § 4) — ale modul, který mluví s instancí u sebe doma, ji tam mít
nemusí.

**Všechny parametry se pojmenovávají**, `text` nevyjímaje — poziční argument
neexistuje a `parser.parse("věta")` skončí `TypeError`.

---

## Dva druhy volání

| metoda | co udělá | kdy ji chceš |
|---|---|---|
| `parse()` | plný rozbor: tokeny, značky, závislosti | skoro vždy |
| `tokenize_only()` | jen hranice vět a tokenů, bez značek | když ti stačí vědět, kde věta končí |

Rozdíl je v ceně: `tokenize_only()` vůbec nespustí neuronovou síť a stojí
**2,7 %** času plného rozboru (naměřeno).

---

## 1 · `parse()` — plný rozbor

```python
vysledek = parser.parse(text="Petr je v Praze.")
```

Se vším, co se hodí vyplnit:

```python
vysledek = parser.parse(
    text="Alois Jirásek se narodil 23. srpna 1851 v tzv. Hronově.",
    trace="q-7f3a91",
)

for veta in vysledek.sentences:
    print(veta.source)
    for t in veta.tokens:
        print(" ", t.form, t.lemma, t.upos, t.deprel, t.head)
```

Vypíše:

```
Alois Jirásek se narodil 23. srpna 1851 v tzv. Hronově.
  Alois     Alois     PROPN  nsubj      4
  Jirásek   Jirásek   PROPN  flat       1
  se        se        PRON   expl:pv    4
  narodil   narodit   VERB   root       0
  23.       23.       NUM    nummod     6
  srpna     srpen     NOUN   obl        4
  1851      1851      NUM    nummod     6
  v         v         ADP    case       10
  tzv.      tzv.      ADJ    amod       10
  Hronově   Hronov    PROPN  obl        4
  .         .         PUNCT  punct      4
```

Všimni si `23.` a `tzv.` — **jeden token, ne dva**. Bez opravy tokenizace by
z nich UDPipe udělal čtyři a datum by se rozpadlo.

| parametr | povinný | co do něj patří |
|---|---|---|
| `text` | **ano** | jedna nebo víc vět; segmentaci určí služba |
| `trace` | ne | identifikátor jednoho průchodu systémem |

### Co se vrací

```python
vysledek.sentences      # věty v pořadí vstupu
vysledek.cached         # kolik jich přišlo z cache
vysledek.parsed         # kolik se jich muselo rozebrat
vysledek.skipped        # věty přes mez serveru, s důvodem
```

U každé věty:

| pole | co v něm je |
|---|---|
| `source` | text věty tak, jak stál v dokumentu — **klíč cache** |
| `tokens` | tokeny se všemi deseti sloupci CoNLL-U |
| `multiword` | víceslovné tvary, když nějaké jsou |
| `from_cache` | přišla z cache, nebo se rozebírala? |
| `retokenized` | kolik oprav tokenizace v ní modul udělal |

### Co je na tokenu

Token je obyčejný objekt s atributy — **všechny se berou stejně**, tečkou:

```python
t = vysledek.sentences[0].tokens[0]      # ze věty „Šel pes do lesa…"

t.id        # 1
t.form      # 'Šel'          ← tvar, jak stojí v textu
t.lemma     # 'jít'          ← základní tvar
t.upos      # 'VERB'         ← slovní druh
t.xpos      # 'VpYS----R-AAI--'
t.feats     # {'Aspect': 'Imp', 'Gender': 'Masc', 'Number': 'Sing',
            #  'Polarity': 'Pos', 'Tense': 'Past', 'VerbForm': 'Part',
            #  'Voice': 'Act'}
t.head      # 0              ← id nadřazeného tokenu; 0 je kořen věty
t.deprel    # 'root'         ← jaký je to vztah k nadřazenému
t.deps      # None
t.misc      # None
```

| atribut | co v něm je |
|---|---|
| `id` | pořadí ve větě, od jedné |
| `form` | tvar, jak stojí v textu |
| `lemma` | základní tvar (`lesa` → `les`) |
| `upos` | slovní druh: `NOUN`, `VERB`, `ADJ`, `PROPN`, `PUNCT`… |
| `xpos` | podrobná značka pražského tagsetu |
| `feats` | **slovník** mluvnických rysů: pád, číslo, rod, čas… |
| `head` | `id` nadřazeného tokenu; `0` znamená kořen věty |
| `deprel` | vztah k nadřazenému: `nsubj`, `obj`, `amod`, `case`… |
| `deps` | rozšířené závislosti; obvykle `None` |
| `misc` | **slovník** poznámek, hlavně `SpaceAfter` |

`feats` a `misc` jsou slovníky, ne seznamy řetězců — `t.feats["Case"]`, ne
rozebírání `"Case=Nom"`. Když je token nemá, jsou `None`; „nemá hodnotu" je
stav, ne prázdný slovník.

Navíc je tam `space_after`, ze kterého se skládá původní text zpátky:

```python
veta.tokens[0].space_after     # True    ← za „Šel" je mezera
veta.tokens[-2].space_after    # False   ← před tečkou mezera není
veta.tokens[-2].misc           # {'SpaceAfter': 'No'}
```

### Víceslovné tvary

Některá česká slova jsou v textu jeden tvar, ale dva tokeny:

```python
v = parser.parse(text="Abys to věděl.")
v.sentences[0].multiword
# (Multiword(id=(1, 2), form='Abys', misc=None),)
```

`Abys` = `Aby` + `bys`. V `tokens` jsou oba tokeny, v `multiword` je zapsané,
že v textu stálo jedno slovo. Bez toho by text z tokenů nešel složit zpátky.

---

## 2 · `tokenize_only()` — jen hranice

Když ti stačí vědět, kde končí věta a kde token:

```python
vety = parser.tokenize_only(text="R.U.R. je drama. Petr spí.")
print(len(vety), [t.form for t in vety[0].tokens])
```

```
2 ['R.U.R.', 'je', 'drama', '.']
```

Oprava tokenizace se dělá i tady. Značky (`upos`, `deprel`, `head`) jsou
`None` — nikdo je nepočítal, a proto je to levné.

**Do cache se nezapisuje.** Tokenizace bez značek není rozbor a uložit ji by
znamenalo, že příští `parse()` vrátí větu bez značek.

---

## Co modul opravuje

Kvůli tomuhle vznikl. Změřeno na korpusu: **17,6 % vět** vypadá po opravě
jinak.

| v textu | UDPipe sám | přes cb-udpipe |
|---|---|---|
| `R.U.R. je drama.` | `R . U . R .` | `R.U.R.` |
| `ve 20. století` | `20 \| .` | `20.` |
| `tzv. obrození` | `tzv \| .` | `tzv.` |
| `30 000 dělnic` | `30 \| 000` | `30 000` |
| `hodnota 3,14` | `3 \| , \| 14` | `3,14` |

Poslední dva řádky nejsou kosmetika: z `30 000` dělá UDPipe **dvě samostatná
čísla**, takže vrstva, která počítá, naměří `30`.

**Text věty se nikdy nemění**, jen hranice tokenů. `source` zůstává tím, co
stálo v dokumentu — je to klíč cache.

Co modul **nedělá**: nescelovává jména (`Karel Čapek` jsou správně dva tokeny)
a nevykládá význam (že levá půle životopisné závorky je narození, je práce
`AG-BIO`, ne tokenizéru).

---

## Cache

Rozbory se pamatují napořád. Klíčem je **text věty + model + verze
tokenizéru**; druhý průchod týmiž daty je **26× rychlejší**.

```python
prvni = parser.parse(text="Petr je v Praze.")
druhy = parser.parse(text="Petr je v Praze.")
print(prvni.sentences[0].from_cache, druhy.sentences[0].from_cache)
```

```
False True
```

Změna pravidel tokenizace cache **neznehodnotí**: staré záznamy zůstanou
platné pro svou verzi a nové se doplní vedle nich. Proto je verze tokenizéru
součástí klíče.

Soubor je čitelný očima, jeden JSON objekt na řádek:

```bash
head -1 cb_udpipe/data-persistent/cache/cs_all-ud-2.17-251125.jsonl \
  | python3 -m json.tool | head -20
```

---

## Stopa (`trace`)

Drží pohromadě jeden průchod systémem. Vyfiltrováním logu podle ní vznikne
příběh jedné otázky napříč moduly:

```
trace q-7f3a91
  udpipe    parse        ok      2 věty, 1 z cache
  udpipe    retokenize   ok      3 sloučení
  field     build_field  ok      13 řádků
```

* **Razí ji vstupní bod** průchodu. Modul ji nikdy nevyrábí, jen předává dál.
* **Tvar** `<prefix>-<8 hex>`: `q-` dotaz, `b-` dávka, `i-` načtení korpusu,
  `t-` test.
* **Chybějící stopa není chyba**, ale je to měřitelná díra v řetězu.

---

## Když něco nefunguje

```python
from cb_udpipe import ServiceUnavailable, IncompatibleApi
```

| situace | co se stane |
|---|---|
| služba neběží | `ServiceUnavailable` **při vytvoření klienta**; hláška uvádí adresu i příkaz ke spuštění |
| služba běží, UDPipe pod ní ne | `ServiceUnavailable` při volání |
| služba mluví jinou verzí rozhraní | `IncompatibleApi` při vytvoření |
| prázdný vstup | **není chyba** — vrátí se prázdný seznam vět |
| věta přes 1000 slov | přeskočí se s důvodem ve `skipped`, zbytek dávky projde |

**Prázdný výsledek a chyba se nikdy neslévají.** Kdyby se slily, přenesl by se
ten problém do každého volajícího: „nemám odpověď" a „nepodařilo se zeptat"
jsou různé stavy.

---

## Kontrola, že to funguje

```bash
./cb-udpipe.py status
curl -s http://127.0.0.1:42200/v1/summary    | python3 -m json.tool
curl -s http://127.0.0.1:42200/v1/cache/stats | python3 -m json.tool
```

```bash
curl -s -X POST http://127.0.0.1:42200/v1/parse \
  -H 'Content-Type: application/json' \
  -d '{"text":"R.U.R. je drama Karla Čapka."}' | python3 -m json.tool
```

Stav klienta a služby z Pythonu:

```python
parser.health()["status"]            # 'ok' nebo 'degraded'
parser.health()["cache"]["sentences"]
parser.summary()["parse"]            # {'ok': 3, ...}
```

---

## Nejčastější omyly

| omyl | co se stane | jak správně |
|---|---|---|
| klient v cyklu | kontrola služby při každém průchodu | jeden klient při startu, předávaný parametrem |
| poziční argument | `TypeError` | všechny parametry se pojmenovávají: `parse(text=…)` |
| čekat, že `parse` vrátí větu | vrací `ParseResult` | věty jsou ve `vysledek.sentences` |
| brát `feats` jako seznam | `TypeError` | je to slovník: `t.feats["Case"]` |
| spoléhat na `sent_id` | není zaručené napříč průchody | pořadí ve `sentences` odpovídá vstupu |
| scelovat jména v cb-udpipe | není to jeho práce | `Karel Čapek` jsou dva tokeny; entity řeší vrstva nad ním |
| měřit zrychlení nad plnou cache | vyjde 1,0× | před měřením smaž cache, viz `scripts/mereni.py` |
| `stop` a hned `start` | port se nestihne uvolnit | použij `./cb-udpipe.py restart` |
| čekat, že se rozdělí věta po `R.U.R.?` | zůstane jedna věta | známá mez: segmentace běží před opravou, viz `docs/koncepce.md` § 3.4b |
