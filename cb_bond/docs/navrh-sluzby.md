# Návrh: cb-bond jako služba a řídicí vrstva systému

Návrh k prohlédnutí, ne hotová věc. Popisuje, co dnešnímu cb_bondu chybí
proti README-MODULES.md, co z toho plyne za refaktor a jak zapadá nový
požadavek: cb-bond je **vrcholová služba**, jejíž rozhraní k člověku je
viewBase2 a která ověřuje a spouští služby pod sebou.

---

## 1 · Kde cb_bond dnes stojí

Modul je knihovna, ne služba. Proti příloze A politiky chybí **osm z jedenácti**
povinných částí:

| co | stav |
|---|---|
| `cb-<name>.py` v kořeni | **chybí** |
| `cb-bond-config.json` + `config.schema.json` + `config.py` | **chybí** |
| `service.py` (doménová logika jako jeden vstup) | **chybí** |
| `api.py` (REST nad service) | **chybí** |
| `client.py` (pro ostatní moduly) | **chybí** |
| `control.py` (start/stop/restart/reload/status) | **chybí** |
| `run/` (service.pid, service.port) | **chybí** |
| logování přes cb-logger | **chybí** |
| `docs/` trojice | je (a víc) |
| `tests/` | je (175 testů) |
| `README.md` + kořenové README | je |

### Tři věci, které bych opravil, i kdyby žádná služba nevznikala

**Veřejné API je příliš široké.** `__init__.py` vyváží **36 jmen**, mezi nimi
`saturate`, `LinkOperator`, `semantic_bag`, `learning_bag`, `kmen`,
`truncated_svd`, `NODE_UPOS`, `LEARN_PREFIXES`. To jsou ladicí vrstvy
a konstanty, ne pracovní úroveň. Politika § 3 říká, že co je v `__init__.py`,
to je smlouva — a smlouvu o `saturate` držet nechci.

**Pipeline se skládá ručně v každém skriptu.** Sedm z jedenácti skriptů
opakuje týchž patnáct řádků: postav korpus → postav graf → vytěž definice →
postav matcher → obal responderem. Kdo změní pořadí, změní měření. Tohle je
přesně `service.py`, který chybí.

**`matcher.py` má 602 řádků a tři různé věci.** Váhy a členy skóre, řídký
operátor vazeb (`LinkOperator`, `saturate` — to je S3, ne párování) a samotné
párování. `graphview.py` je zase skript schovaný v modulu: má `main()`
a pevný port.

### A jedna vada, kterou je potřeba opravit hned

`graphview.py` poslouchá na **portu 8080**. To je **cizí port** — mimo rozsah
projektu (README-MODULES § 5). cb-bond zatím v tabulce portů není vůbec.

---

## 2 · Cílová struktura

```
cb-bond.py                      tenké dveře → cb_bond/control.py

cb_bond/
    cb-bond-config.json         VŠECHNY páky systému na jednom místě
    config.schema.json          validuje se při startu
    config.py                   načtení a validace

    __init__.py                 ZÚŽENÉ API (~12 jmen)
    service.py                  doménová fasáda — jeden vstup do systému
    api.py                      REST nad service.py
    client.py                   BondClient pro ostatní moduly
    control.py                  start · stop · restart · reload · status
    stack.py                    ← NOVÉ: řízení služeb POD cb-bondem
    console.py                  ← NOVÉ: interaktivní okno ve viewBase2

    graph.py  recall.py  matcher.py  answer.py  relations.py
    dialog.py  training.py  promotion.py  spectral.py  benchmark.py
    linkops.py                  ← z matcher.py: LinkOperator + saturate
    window.py                   ← z graphview.py: zrcadlo + okna, bez main()

    run/                        service.pid · service.port (V REPOZITÁŘI —
                                stav procesu, ne data)
    docs/  scripts/  tests/

  DATA leží mimo repozitář (§ 11):
    /Users/j/Projects/conBondCorpus/cb_bond/persistent-registry/
                                             persistent-dictionary/
                                             persistent-benchmark/
```

### Porty

Tabulka portů v README-MODULES § 5 má volný rozsah 42400–42499. Navrhuju
zapsat do ní řádek:

| modul | rozsah | základní port | další porty |
|---|---|---|---|
| `cb-bond` | 42400–42499 | **42400** REST API | 42401 viewBase2 (graf + konzole) |

Tím zmizí port 8080 a s ním riziko kolize s čímkoli jiným na stroji.

---

## 3 · Konfigurace: jediné místo, kde žijí páky

Během stavby se nasbíralo **osmnáct ručních konstant** a dnes jsou rozházené
v konstruktorech a výchozích hodnotách. Konfigurace je to místo, kam patří —
a zároveň se tím splní § 5 politiky.

Klíče jsou **anglicky** — politika § 17 to žádá u JSON konfigurace stejně
jako u kódu; česky jsou jen docstringy, komentáře a hlášky pro člověka.

```json
{
  "format_version": 1,
  "module": {
    "host": "127.0.0.1",
    "port": 42400,
    "view_port": 42401,
    "logger_endpoint": "http://127.0.0.1:42100",
    "udpipe_endpoint": "http://127.0.0.1:42200",
    "stop_timeout_s": 10,
    "start_dependencies": true
  },
  "data_root": "/Users/j/Projects/conBondCorpus",
  "corpus": {
    "directory": "corpus",
    "patterns": ["korpus-*.json"],
    "question_files": ["otazky-*.json"],
    "radius": 1,
    "sentence_radius": 0
  },
  "matching": {
    "spread_depth": 1,
    "top_k": 50,
    "theta": 0.0,
    "epsilon": 0.0,
    "weights": {"center": 2.0, "cover": 1.0, "topic": 1.0,
                "given": -3.0, "fit": 0.0, "spectral": 0.0},
    "spectral_k": 0,
    "graph_recall_depth": 2
  },
  "reading":   {"sigma": 1.5},
  "training":  {"learning_rate": 0.001, "margin": 0.2, "tolerance": 0.01,
                "max_epochs": 6, "validation_share": 0.3},
  "promotion": {"limit": 328, "usage_weight": 0.0},
  "relations": {"min_stem": 5, "min_stem_share": 0.75,
                "dictionary_store": "cb_bond/persistent-dictionary"},
  "state":     {"registry": "cb_bond/persistent-registry",
                "load_on_start": true, "save_on_accept": true},
  "seed": 328
}
```

**Proč to stojí za to:** dnes je „limit 328" na třech místech, `sigma=1.5` na
čtyřech a `lr` se během kalibrace měnilo v kódu. Registr prahů v README modulu
pak není soupis, ale opis. S konfigurací je jedno místo a `status` může vypsat
její otisk — takže jde poznat, že dvě měření běžela s jiným nastavením.

**`data_root` je JEDINÁ absolutní cesta.** Všechno ostatní je relativní vůči
ní, takže se celá instalace přenese změnou jednoho řádku a nikdo si datový
kořen nemůže vyrobit potichu za běhu (§ 11).

**Co do konfigurace NEPATŘÍ:** zmražené hodnoty přejímek (ty patří do skriptů,
protože jsou to testy) a `LEARN_PREFIXES` (to je invariant, ne nastavení —
kdyby šel změnit konfigurací, dal by se obejít pojistkový test).

---

## 4 · `service.py`: jeden vstup do systému

Dnes si každý skript skládá pipeline sám. Fasáda to sjednotí a stane se tím,
co obaluje `api.py`.

```python
class BondService:
    """Sestavený systém: korpus, graf, vztahy, párování, dialog."""

    def __init__(self, config, parser, log=None): ...
    def build(self) -> dict         # postaví vše; vrátí otisk (vět, hran, os)
    def ask(self, text) -> dict     # otázka → Reply + rozklad + kandidátní věty
    def context(self, text) -> dict # dialogové doplnění věty
    def train(self, entries) -> dict
    def promote(self) -> dict
    def state(self) -> dict         # vět, hran, os, axis_version, otisk konfigurace
```

Vrací **slovníky**, ne objekty modulu — to je totéž, co pak jde do JSON přes
`api.py` a do logu. Objekty (`Reply`, `MatchResult`) zůstávají uvnitř.

`build()` je drahý (2 912 vět ≈ 5 s, 12 258 ≈ 23 s), takže se dělá **jednou při
startu služby**, ne při dotazu. To je hlavní důvod, proč z toho vůbec služba
být má.

### `state()` je to, co uvidí člověk ve `status`

*(Požadavek J., 5. 8. 2026: „status by měl vypsat i statistiky typu 16 074
hran, 5 695 lemmat atp.")*

U loggeru i udpipe `status` říká nejen že služba běží, ale **co v sobě má** —
kolik záznamů, kolik vět v cache. U cb-bondu je ta otázka nejzajímavější ze
všech tří, protože obsah hlavy se mění učením a promocí. Bez čísel se nedá
poznat, jestli běží model, který se učil, nebo čerstvě postavený.

```
cb-bond      BĚŽÍ     127.0.0.1:42400  pid 71203
             zdraví   ok
             verze    modul 0.7.0 · konfigurace 1
             korpus   2 912 vět · 7 souborů · rádius 1
             graf     16 074 hran · 5 695 lemmat · stupeň 5.6
             osy      6 671 celkem · 328 vlastních (verze 12)
             vazby    1 204 naučených · práh 0.02
             služby   cb-logger BĚŽÍ 42100 · cb-udpipe BĚŽÍ 42200
             viewBase http://127.0.0.1:42401
             data     /Users/j/Projects/conBondCorpus
             config   …/cb_bond/cb-bond-config.json  otisk a3f1c2e94b07
```

Odkud čísla jsou: **od běžící služby**, ne z vlastního počítání. Kdyby si je
`status` spočítal sám, trvalo by pět vteřin a ukázal by, co by v hlavě bylo,
kdyby se postavila znovu — ne co v ní je. To je přesně ta třída vady, kterou
politika § 11 zakazuje u měření: měřit něco jiného, než co se tvrdí.

Když služba **neběží**, čísla se nevymýšlejí. `status` vypíše, co by stavěl
(cesty a páky z konfigurace), a řekne, že obsah hlavy nezná:

```
cb-bond      NEBĚŽÍ   měl by běžet na 127.0.0.1:42400
             korpus   <data_root>/corpus  ·  vzory korpus-1*.json  (nenačteno)
             data     /Users/j/Projects/conBondCorpus
             config   …/cb_bond/cb-bond-config.json
```

---

## 5 · `stack.py`: cb-bond jako řídicí vrstva

Nový požadavek. cb-bond je vrcholová služba, takže při startu ověří, co běží
pod ním, a co neběží, spustí.

```python
DEPENDENCIES = (
    Dependency("cb-logger", "./cb-logger.py", "http://127.0.0.1:42100"),
    Dependency("cb-udpipe", "./cb-udpipe.py", "http://127.0.0.1:42200"),
)

class ServiceStack:
    """Ověří a spustí služby pod cb-bondem, v pořadí závislostí."""

    def check(self) -> list                # [(name, running, port, note)]
    def ensure(self, start=True) -> list   # co bylo potřeba spustit
    def report(self) -> str                # lidsky čitelný přehled
```

**Pravidla, která bych do toho zadrátoval:**

Cizí službu spouští **jejím vlastním ovládacím programem** (`./cb-udpipe.py
start`), ne importem jejího vnitřku. Logika řízení patří tomu modulu; kdyby ji
cb-bond duplikoval, existovala by dvakrát a rozešla by se.

Pořadí je dané závislostmi: logger první (loguje do něj i start ostatních),
pak udpipe. Zastavování v opačném pořadí.

**Nespouští se mlčky.** Politika § 9 chce hlasitou chybu místo tichého
obcházení, ale tady je spuštění to, co člověk chce — takže se udělá a **oznámí**:

```
$ ./cb-bond.py start
cb-bond    kontroluji služby pod sebou…
           cb-logger  NEBĚŽÍ → spouštím… OK (127.0.0.1:42100)
           cb-udpipe  BĚŽÍ      (127.0.0.1:42200)
           stavím korpus: 2 912 vět · 16 074 hran · 6 671 os (5 s)
cb-bond    BĚŽÍ     127.0.0.1:42400  pid 71203
           viewBase 127.0.0.1:42401
```

**Spouštění závislostí je VÝCHOZÍ chování** (rozhodnutí J.): `start` nejdřív
zvedne logger, pak udpipe, a teprve až obojí odpovídá, instanciuje jejich
klienty. Pořadí není libovolné — udpipe do loggeru loguje už při vlastním
startu, takže obrácené pořadí by první záznamy zahodilo.

`--no-deps` to vypne pro případ, kdy si člověk služby řídí sám.

---

## 6 · viewBase2 jako rozhraní k člověku

Dnes je `graphview.py` skript, který si sám staví korpus a sám servíruje.
Nově je to okno služby.

```
cb_bond/window.py     GraphMirror (dnešní mirror.py) + stavba oken
cb_bond/console.py    interaktivní prompt: text → BondService.ask → odpověď
```

Konzole je tenká: přečte řádek, zavolá `service.ask(text)`, vypíše odpověď
i **rozklad skóre** a nechá v grafu rozsvítit uzly kandidátních vět. Tím se
konečně naplní princip 6 — člověk vidí, proč systém odpověděl, aniž by četl
kód.

Oken jsou **čtyři**, ne jedno — rozpis a proč v § 13. Konzole navíc umí
`:context <věta>` (dialogové doplnění) a `:state`, jinak by se dialogová
vrstva z kroku 8 nedala vyzkoušet jinak než skriptem.

---

## 7 · Logování — hlasitě, do loggeru i na konzoli

**Rozhodnutí J.:** logovat extenzivně, a to na obě strany. Do cb-loggeru
strukturovaně (pro pozdější rozbor), na konzoli lidsky (pro člověka, který
se právě dívá). Obojí má říct **co se děje a proč**, ne jen že se něco děje.

Platí to hlavně pro dlouhé operace — `corpus parse` nad 12 258 větami běží
minuty a mlčící proces vypadá jako zaseknutý (naměřeno na `trenink-vah.py`,
kde to bylo přesně tak).

```
$ ./cb-bond.py corpus build
cb-bond    datový kořen /Users/j/Projects/conBondCorpus
           37 souborů korpusu · 12 258 vět
           stavím pole (r=1)…            2 912/12 258   14 s
           …
           graf: 5 781 uzlů · 16 074 hran
           těžím definice…               94 vazeb
           načítám registr registry-3.json (axis_version 3)
           přegeneruji koše proti ose…   12 258 vět     8 s
cb-bond    hotovo, stav uložen do persistent-registry/registry-3.json
```

Tentýž průběh jde do loggeru jako záznamy s `trace` jednoho běhu, takže se
z něj dá zpětně složit, co se dělo — a `duration_ms` u každého kroku řekne,
kde se čas ztratil.

### Co se loguje



Každá metoda `BondService` udělá jeden záznam s povinnou čtveřicí
(component/method/input/output) plus `trace`, který se razí **na vstupu dotazu**
a protáhne se přes párování, čtení i dialog. Klient se předává parametrem (§ 3),
takže služba jde spustit i bez loggeru (jen bez logu).

Na `info`: `ask` (otázka, výsledek, východisko, doba), každý krok `build`
(stavba pole, graf, definice, načtení registru, přegenerování), `train`
(epocha po epoše), `promote` (přijato/vráceno a proč), start a stop
závislostí. Na `debug`: rozklad skóre po členech a naučené hrany — objemné,
ale při ladění právě to člověk chce.

---

## 8 · Refaktor: co se kam přesune

| odkud | kam | proč |
|---|---|---|
| `matcher.py`: `LinkOperator`, `saturate` | `linkops.py` | je to S3 (řídká reprezentace), ne párování |
| `graphview.py`: `main()`, port, otisk bundle | `control.py` + `window.py` | skript v modulu; port patří konfiguraci |
| `mirror.py` | `window.py` | zrcadlo a okna jsou jedna věc |
| stavba pipeline ze 7 skriptů | `service.py` | duplicita, která rozhoduje o měření |
| konstanty z konstruktorů | `config.py` | § 5 politiky |
| 36 jmen v `__init__.py` | ~12 | ladicí vrstvy nejsou smlouva |
| **22 česky pojmenovaných funkcí** | anglická jména | politika § 17; **jen jména tříd, metod a souborů** — proměnné zůstávají |

### Jazykový dluh

Politika § 17 žádá **kód anglicky, docstringy a komentáře česky**. Rozsah
téhle úpravy je vědomě omezený na **jména tříd, metod, funkcí a souborů**;
lokální proměnné (`vety`, `jas`, `hranice`, `pytel`) zůstávají, jak jsou —
přejmenovat je by byl velký diff bez užitku a riziko záměny při čtení
diffu proti věcným změnám.

Dnešní cb_bond porušuje pravidlo na **22 místech** — skoro všechno jsou
privátní pomocníci, ale jedno jméno je veřejné:

| soubor | česky pojmenované |
|---|---|
| `graph.py` | `_je_uzel`, `_uzel`, `_hrana`, `_delta` |
| `matcher.py` | `_jednotkovy`, `_radky_vety`, `_kandidat`, `_priprav`, `_vektor` |
| `mirror.py` | `_rozloz` |
| `recall.py` | `_zar`, `_vety_uzlu`, `_priprav` |
| `relations.py` | **`kmen`** (veřejné!), `_definicni_dvojice`, `_prekryv_sousedstvi` |
| `spectral.py` | `_zarovnej` |
| `training.py` | `_zmeny_vah`, `_rozdil_pytlu`, `_je_axiom`, `_mez`, `_median` |

`kmen` je v `__all__`, takže jeho přejmenování na `stem` je změna veřejného
API — udělat se má **při zúžení `__init__.py`** (krok 8), ne dřív, aby se
nelámalo dvakrát. Privátní pomocníky jde přejmenovat kdykoli; jsou to
mechanické změny, které testy okamžitě odhalí.

Rozsah je malý (22 jmen ve 2 754 řádcích) a stojí za to ho splatit teď, než
přibude služba s dalšími soubory.

**Co se nemění:** `graph.py`, `recall.py`, `answer.py`, `relations.py`,
`training.py`, `promotion.py`, `spectral.py`, `benchmark.py`. Ty jsou v pořádku
a mají testy — refaktor se jich nedotkne, aby zůstaly platné přejímky.

Navrhované zúžené API:

```python
__all__ = [
    "BondService",                                    # pracovní úroveň
    "KnowledgeGraph", "GraphRecall",                  # graf
    "Matcher", "MatchResult", "ScoreWeights",         # párování
    "AnswerField",                                    # čtení
    "Responder", "Reply",                             # dialog
    "ContrastiveTrainer", "PromotionCycle",           # smyčky
    "BenchmarkProtocol",                              # měření
    "__version__",
]
```

Zbytek zůstane importovatelný přes podmoduly (`cb_bond.matcher.saturate`) —
kdo si sáhne, ví, že sahá pod kapotu.

---

## 9 · Pořadí stavby (podle § 16)

1. ✅ **konfigurace** — `cb-bond-config.json`, schéma, `config.py`, test na
   odmítnutí vadné konfigurace
2. ✅ **`service.py`** — fasáda nad hotovým jádrem (`build`, `ask`, `state`,
   `health`); skripty čtou cesty z konfigurace přes `corpus_dir()`
3. ✅ **`stack.py`** — kontrola a spouštění služeb pod sebou
4. ✅ **`control.py` + `cb-bond.py`** — `start`/`stop`/`restart`/`status`,
   stavové soubory, `status` s datovým kořenem i statistikami obsahu.
   Zbývá `corpus` (status/parse/build/validate) a `reload`.
5. ✅ **`api.py` + `client.py`** — REST kontrakt a klient.
   Zbývá test parity (v procesu == přes síť).
6. **`window.py` + `console.py`** — viewBase2 jako rozhraní; s tím přesun
   grafu z portu **8080** na 42401
7. **logování** — protažení `trace` skrz službu. `LogClient` už visí
   (`component="bond"`, metody `build` a `ask`).
8. **zúžení `__init__.py`** až nakonec, aby refaktor nebolel dvakrát

Po každém kroku běží celý balík testů i přejímky — hodnoty jako 16 074 hran,
pokrytí 1,000/0,604/0,885 a dialog o dálnici se **nesmí hnout**.

### REST kontrakt, jak vznikl

```
GET  /version      modul, verze, verze rozhraní — odpovídá i nezdravé službě
GET  /v1/health    'ok' vs 'degraded' (běží, ale systém nepostavený)
GET  /v1/state     vět · souborů · hran · lemmat · uzlů · stupeň ·
                   os · vlastních os (+verze) · vazeb (+verze)
GET  /v1/config    cesta, otisk, verze konfigurace
POST /v1/ask       {"text": …, "top": 5} → odpověď, rozklad, věty, osy
```

Dvě věci, které se v tom kontraktu lámou o § 9:

**`/v1/ask` na nepostavený systém je `503 not_built`, ne prázdná
odpověď.** Prázdná by se slila s platným „nevím" — a mlčení systému je
platný výsledek, kdežto nepostavená hlava je porucha.

**`lemmas` a `nodes` jsou dvě různá čísla** (5 695 proti 5 727):
`NOUN:vedení` a `VERB:vedení` jsou dva uzly, ale jedno lemma. Přejímka
§ 6 zmrazila lemmata, takže `state()` vrací obojí pod vlastním jménem.
Kdyby vracel jen jedno pod jménem toho druhého, rozdíl by nikdo nehledal
v definici.

---

## 10 · Rozhodnutí (J., 2026-08-05)

Všech pět otázek zodpovězeno; odpovědi zapracované výše i níže.

| otázka | rozhodnutí |
|---|---|
| provozní korpus | `/Users/j/Projects/conBondCorpus` — **mimo repozitář** |
| ukládání stavu | ANO, registr se ukládá; `build()` ho načte, přegeneruje koše a **ověří `axis_version`** — při neshodě to hlasitě řekne a stav NENAČTE |
| start závislostí | **výchozí chování**: nejdřív logger, pak udpipe, pak teprve instanciace |
| okna viewBase2 | **čtyři** — graf · dialog · top 5 vět · použité vertikály |
| rozklad přes REST | ANO, `ask` ho vrací |

Navíc: cb-bond dostane příkaz **`corpus`** vedle start/stop/status/restart.

---

## 11 · Data mimo repozitář — vědomá odchylka od § 19

**Rozhodnutí J.:** kód a data se oddělí. Data žijí v
`/Users/j/Projects/conBondCorpus/`, členěná podle modulu a povahy.

Politika dnes říká opak, a to výslovně:

> *„**Všechno běží z projektového adresáře.** Modul nesmí sahat mimo repozitář
> ani do domovského adresáře — cesty jsou v konfiguraci a míří dovnitř."*
> — README-MODULES § 19

Odchylka má dobré důvody (verzování gitu, přenos aplikace, licencovaná data
mimo repozitář z principu), ale **je to změna politiky, ne rozhodnutí jednoho
modulu** — § 19 to o sdílených pravidlech říká přímo. Navrhuju proto § 19
upravit takto, aby zůstalo zachované to, co pravidlo chránilo:

**Co pravidlo chránilo a musí platit dál:** modul nesmí sahat do domovského
adresáře ani do cizí cesty *uhodnuté za běhu*. Datový kořen je **jediná cesta
v konfiguraci**, všechno ostatní je relativní vůči němu — takže se přenese
změnou jednoho řádku a nikdo si ho nemůže vyrobit potichu.

**Co se mění:** ten kořen smí ležet mimo repozitář.

**Co z toho plyne pro `status`:** musí datový kořen vypsat, stejně jako vypisuje
port a cestu ke konfiguraci. Jinak člověk hledá chybu v datech, která služba
vůbec nečte.

### Navržená struktura datového adresáře

Dnes tam leží 37 souborů korpusu naplocho. Návrh členění podle modulu a povahy:

```
/Users/j/Projects/conBondCorpus/
    corpus/                      ZDROJ — dnešní korpus-*.json a otazky-*.json
        korpus-101…107.json
        korpus-201, 202.json
        korpus-301…326.json
        otazky-201, 202.json

    cb_field/
        persistent-verticals/    registr vertikál (save/load, v2)
        persistent-corpora/      původní txt, ze kterých korpusy vznikly

    cb_bond/
        persistent-registry/     stav registru po učení a promoci
            registry-<axis_version>.json
            latest.json          → symlink nebo kopie posledního přijatého
        persistent-dictionary/   fixovaná hesla ze slovníku (offline-first)
        persistent-benchmark/    reporty ramen A–F s otiskem konfigurace

    cb_udpipe/
        persistent-models/       modely UDPipe (CC BY-NC-SA, mimo git)
        persistent-cache/        trvalá cache rozborů

    cb_logger/
        persistent-log/          log.jsonl a rotace
```

**Proč `persistent-<co>` a ne `data-persistent/<co>`:** jméno adresáře pak nese
i povahu obsahu, takže `ls` v modulovém adresáři řekne, co se ukládá, bez
otevírání. A prefix drží pohromadě to, co přežívá restart, oproti tomu, co je
běhový stav (`run/` zůstává **v repozitáři** — PID a port nejsou data, jsou to
stav procesu a mají zmizet s ním).

**Registr se verzuje `axis_version`.** Promoce mění osu a stará matice se s ní
nesmí potkat (princip 3); jméno souboru to nese, takže se nedá načíst cizí stav
omylem. `latest.json` ukazuje na poslední PŘIJATÝ — vrácený cyklus se neuloží.

**Načtení stavu má závazné pořadí** (rozhodnuto):

```
build():  postav korpus  →  načti registr  →  corpus.regenerate()
                         →  ověř axis_version souboru proti paměti
                         →  neshoda? HLASITĚ říct a stav NENAČÍST
```

`regenerate()` je nutný, protože registr nese custom sloty, ale koše je musí
aktivovat samy (transparentní promoce, § 16). Bez něj by registr sliboval
`CUSTOM=` osy, které v polích nesvítí — a to je tichá neshoda, tedy nejhorší
druh.

---

## 12 · Příkaz `corpus`

Vedle pěti povinných příkazů (§ 12) dostane cb-bond ještě jeden, protože
stavba korpusu je drahá a dnes ji dělá každý skript sám.

```
./cb-bond.py corpus status      co je v datovém kořeni: soubory, vět, otisk
./cb-bond.py corpus parse       projde korpusy parserem a naplní cache UDPipe
./cb-bond.py corpus build       postaví korpus + graf a uloží stav registru
./cb-bond.py corpus validate    formát, 1 položka = 1 věta, answer_lemma
```

`validate` je to, co dnes umí `./run-python -m cb_field.corpusfile` — patří sem,
aby se člověk nemusel učit dvě cesty.

Všechny čtyři **logují extenzivně** do loggeru i na konzoli (§ 7): co dělají,
nad kolika soubory, jak dlouho a proč. Dlouhá mlčící operace vypadá jako
zaseknutá — naměřeno.

`parse` je oddělený schválně: naplnit cache je jednorázová drahá operace
(12 258 vět), po které je `build` rychlý. Dnes to dělá první spuštění
libovolného skriptu, což je nemilé překvapení.

---

## 13 · Čtyři okna viewBase2

Rozhodnuto: ne jedno okno, ale čtyři — každé odpovídá na jinou otázku.

```
┌─ GRAF ────────────────┐  ┌─ DIALOG ──────────────────────────┐
│ uzly a hrany faktů,   │  │ > Kde byl pokřtěn Ježíš?          │
│ po dotazu se rozsvítí │  │ [Jordán] V těch dnech přišel      │
│ kandidátní věty       │  │          Ježíš z Nazareta…        │
└───────────────────────┘  └───────────────────────────────────┘

┌─ TOP 5 VĚT ───────────────────────┐  ┌─ VERTIKÁLY ──────────┐
│ 1. [Jordán]  V těch dnech přišel… │  │ QLEM=ADV:kde    0,7  │
│ 2. [Galilej] Když byl Jan uvěz…   │  │ QANCHOR=space   0,7  │
│ 3. [Jan]     A kázal: Za mnou…    │  │ WORD=ADJ:pokřtěný    │
│ 4. …                              │  │ ANCHOR=space:loc     │
│ 5. …                              │  │ …                    │
└───────────────────────────────────┘  └──────────────────────┘
      obnovuje se po KAŽDÉ otázce
```

Konvence `[slovo] Věta` je v dialogu i v top 5 stejná — kandidátní slovo
v hranatých závorkách, za ním věta, ze které je.

**Okno vertikál je to, co dnes nikde vidět není.** Ukazuje osy, které se
dotazu opravdu účastnily — tedy proč se která věta rozsvítila. Je to lidsky
čitelná podoba toho, co `rozklad-skore.py` vypisuje do terminálu.

---

## 14 · Hierarchie a závislosti

### Služby za běhu — kdo koho startuje

```
                          ČLOVĚK
                             │
                    ./cb-bond.py start
                             │
              ┌──────────────▼───────────────┐
              │          cb-bond             │  ← vrcholová služba
              │  42400 REST · 42401 viewBase │
              │  ┌────────────────────────┐  │
              │  │  ServiceStack          │  │  ověří a spustí, co chybí
              │  └───────┬────────────────┘  │
              └──────────┼───────────────────┘
                         │ spouští VLASTNÍM ovládacím programem
              ┌──────────┴───────────┐
              ▼                      ▼
     ┌─────────────────┐    ┌──────────────────┐
     │    cb-logger    │    │    cb-udpipe     │
     │  42100 REST     │◄───┤  42200 REST      │  udpipe loguje do loggeru
     │  42101 · 42102  │    │  42201 UDPipe    │
     └─────────────────┘    └──────────────────┘
              ▲                      ▲
              └──────────────────────┴─── cb-bond loguje a parsuje

     pořadí startu:   cb-logger → cb-udpipe → cb-bond
     pořadí zastavení: obráceně (a jen s --all; jinak cb-bond padá sám)
```

### Moduly a import — směr šipky je „závisí na"

```
   cb_bond ─────────────► cb_field ─────────────► cb_udpipe
      │   (Corpus, SentenceField,   (Token, UdpipeClient)
      │    VerticalRegistry)                 │
      │                                      ▼
      └──────────────────────────────────► cb_logger
                (LogClient — sdílený modul, smí do něj kdokoli)

   cb_bond ─────────────► viewbase        (jen window.py a console.py;
                          (GraphWindow)    jádro na něm NEZÁVISÍ)

   ŽÁDNÁ šipka nevede zpátky — cykly hlídá test nad AST (§ 4).
```

### Uvnitř cb_bondu — co na čem stojí

```
                        ┌───────────────┐
   REST ────────────────►    api.py     │
                        └───────┬───────┘
   viewBase2 ──► console.py ────┤
                 window.py ─────┤
                        ┌───────▼───────┐
   skripty ─────────────►  service.py   │  ← JEDINÝ vstup do systému
                        └───────┬───────┘
        ┌───────────────┬───────┼────────┬──────────────┐
        ▼               ▼       ▼        ▼              ▼
   ┌─────────┐   ┌───────────┐ ┌──────┐ ┌──────────┐ ┌───────────┐
   │ graph   │   │ recall    │ │dialog│ │ training │ │ benchmark │
   │ .py     │◄──┤ .py       │ │ .py  │ │ .py      │ │ .py       │
   └────┬────┘   └───────────┘ └───┬──┘ └────┬─────┘ └─────┬─────┘
        │                          │         │             │
        │        ┌─────────────────▼─────────▼─────────────▼──┐
        │        │              matcher.py                    │
        │        └──────┬──────────────────┬──────────────────┘
        │               ▼                  ▼
        │        ┌─────────────┐   ┌──────────────┐
        └───────►│ linkops.py  │   │ spectral.py  │
                 │ (S3)        │   │ (S2)         │
                 └─────────────┘   └──────────────┘
                        │
                        ▼
              ┌───────────────────┐
              │ answer.py         │  ← čtení pole (gauss)
              │ relations.py      │  ← definice a derivace
              │ promotion.py      │  ← výměna vstupní vrstvy
              └───────────────────┘

   config.py ──► čte všechno výše (páky), sám nezávisí na ničem
   stack.py  ──► nezávisí na jádře; mluví jen s cizími ovládacími programy
```

**Dvě věci, které z obrázku plynou a stojí za pohlídání:**

`stack.py` **nesmí** importovat jádro ani naopak — je to řízení procesů, ne
doména. Kdyby se propletlo, nešlo by cb-bond spustit bez postaveného korpusu
a `status` by trval dvacet sekund.

`window.py` a `console.py` jsou **jediná** místa, která smějí importovat
`viewbase`. Jádro (graph, matcher, recall) na kreslítku nezávisí a testy si
vystačí s atrapou — to platí dnes a má platit dál.
