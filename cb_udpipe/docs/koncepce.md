# cb-udpipe — jak je to koncipované

Proč je modul postavený takhle a ne jinak. Každé rozhodnutí níž má uvedeno,
z čeho plyne — ze zadání, z politiky modulů (`README-MODULES.md`), z návrhu
systému (`README-ARCHITECTURE_OVERVIEW.md`), nebo z chyby naměřené v conBondu,
conBondu2 či jellyAI3.

Návod k použití je v `prirucka.md`, popis metod v `metody.md`, přehled rozhraní
v `../README.md`.

**Stav:** návrh před stavbou. Čísla označená *(neměřeno)* jsou odhady; čísla
označená **(změřeno 2026-08-03)** pocházejí z měření popsaných v § 13.

---

## 1 · K čemu modul je

> **Pošle se věta, dostane se kvalitní rozbor.**

Dvě práce, které to obnáší, a obě jsou jádro modulu:

1. **Perfektně tokenizovat** — připravit UDPipe co nejlepší podmínky.
2. **Zavolat UDPipe a výsledek si pamatovat** — cache rozborů po větách.

Kdyby byl modul jen klientem UDPipe, byla by to funkce o pěti řádcích a
nepotřebovala by službu, port ani perzistentní data. Obojí výše je důvod, proč
je to modul.

### Proč tokenizace, když ji UDPipe umí

Umí, ale špatně — a je to **doložené měřením na korpusu conBondu2**
(26 051 vět, § 13.1):

| vada | vět | podíl |
|---|---|---|
| řadová číslovka rozsekaná (`20 . století`, `1 . vyd`) | 1 129 | 4,3 % |
| jednoslovná zkratka (`tzv .`, `např .`, `sv .`) | ~1 100 | 4,2 % |
| iniciály a víceznakové zkratky (`T . G .`, `n . l .`) | 173 | 0,7 % |

Zhruba **každá jedenáctá věta**. Přitom `20. století` a `n. l.` jsou časové
údaje, tedy přesně to, oč systému jde.

**Segmentace na věty je naproti tomu spolehlivá** (§ 13.2) — tečka ve zkratce
ani v řadové číslovce větu neroztrhne. Proto se segmentace nechává UDPipe a
opravuje se jen tokenizace uvnitř věty.

### Cache má druhého odběratele, a ten rozhoduje o jejím tvaru

Cache neslouží jen k zrychlení. Je to **rostoucí sbírka rozebraných českých vět
se svým zdrojem** — tedy to, z čeho se dá jednou trénovat vlastní model. Proto:

* ukládá se **všech deset sloupců** CoNLL-U, ne jen ty dnes potřebné (§ 5),
* klíč nese **verzi tokenizéru i modelu** (§ 4), aby šlo poznat, čím rozbor vznikl.

Co se do cache nezapíše, se nedá dopočítat jinak než pustit rozbor znovu.

---

## 2 · Tok rozboru: tokenizace → oprava → cache → dorozbor

```
vstup: "Alois Jirásek (23. srpna 1851 Hronov) byl spisovatel."

1 · SEGMENTACE     POST /process   data=<text>&tokenizer=
    a hrubá        síť se nenačte → čistý C++ tokenizér (§ 13.3)
    tokenizace     → # text = …                     ← klíč cache
                     Alois · Jirásek · ( · 23 · . · srpna …

2 · OPRAVA         naše pravidla (§ 3)
    tokenizace     → Alois · Jirásek · ( · 23. · srpna …

3 · CACHE          klíč = (text věty, model, verze tokenizéru)
                   HIT  → tokeny z disku, konec
                   MISS → do fronty

4 · DOROZBOR       POST /process   data=<CoNLL-U>&tagger=&parser=
                   bez `tokenizer` → server čte vstup jako CoNLL-U,
                   segmentace i tokenizace jsou dané vstupem

5 · ZÁPIS          append do <model>.jsonl + doplnění indexu
```

### Proč je první fáze levná

Není to odhad, je to vlastnost serveru. `vendor/udpipe2-src/udpipe2_server.py`
má v metodě `predict`:

```python
def predict(self, sentences, tag, parse, writer):
    if tag or parse:
        self._network.load()
        …compute_embeddings…
```

Požadavek jen s `tokenizer` a **bez** `tagger`/`parser` síť vůbec nenačte a
embeddingy nepočítá. Je to čistý C++ tokenizér z UDPipe 1.

### Proč čtvrtá fáze posílá CoNLL-U, a ne text

Dva důvody, oba doložené:

1. **Jinak by se opravená tokenizace zahodila.** Kdyby se poslal text, server by
   ho tokenizoval znovu — po svém.
2. **Tokenizér při dávce občas slepí dvě věty.** conBond2, `scripts/ukazka.py`:
   *„dávkou je tokenizér občas slepí a čísla vět by přestala odpovídat
   označení."* Když je vstup CoNLL-U, segmentace je dána vstupem a stát se to
   nemůže.

---

## 3 · Pravidla opravy tokenizace

Všechna jsou **pravidlová a deterministická**. Model se zatím nepoužívá (§ 12).

### 3.0 Zásada: co uděláme my, nemusí dělat každý nad námi

> **Co jde udělat deterministicky nad jednou větou, bez znalosti světa, a co by
> jinak muselo dělat každé vyšší patro zvlášť — to udělá cb-udpipe.**

Důvod je týž, proč modul vzniká: tokenizace je **chokepoint**. Když se oprava
udělá tady, projde jí korpus i dotaz a nemají se jak rozejít. Když se nechá na
vyšších vrstvách, udělá ji každá jinak — a přesně na to conBond2 doplatil, když
měl dva klienty UDPipe a jen jeden scelovával zkratky:

> „Korpus tedy mohl mít „R.U.R." rozsekané na tři tokeny a otázka scelené;
> obojí by dál fungovalo a jen mluvilo o jiném slově."

Zásada má ale **dvě hranice**, bez kterých by modul postupně pohltil všechno:

1. **Nesmí zahodit informaci.** Co modul změní, nese původní tvar (návrh,
   kap. 14.2: *„Každá normalizace nese původní tvar vedle kanonického."*).
2. **Nesmí vykládat.** Že `23.` je jeden token, je tvar. Že je to datum
   narození, je výklad — a ten patří `AG-BIO` (§ 6).

**Zkouška, jestli něco pod zásadu spadá:** *Pomůže to měřitelně? A ztratí se
tím něco?* Obojí se má zodpovědět měřením, ne úvahou. § 13.6 ukazuje případ,
kde odpověď na první otázku vyšla „ne" a na druhou „ano" — a pravidlo proto
nevzniklo.

### 3.1 Tečkované zkratky a iniciály

Bezvýčtový vzor, převzatý z conBondu (`core/normalize.py`) a jellyAI3
(`jellyai/normalize.py`), kde je v obou stejný:

```
běh ≥2 těsně navazujících párů ⟨jednopísmenný token⟩⟨tečka⟩
```

Tři podmínky, každá zapsaná po chybě v některém z předchozích projektů:

* **≥2 páry.** Jediná iniciála `K.` běh netvoří — `K. Čapek` je jméno, ne
  zkratka. (jellyAI3, `test_normalize.py`)
* **Těsné navazování.** Ověřuje se přes `SpaceAfter=No`, ne mezerou v textu.
  Písmena oddělená mezerami (výčtové odrážky `a . b .`) se neslučují.
* **Jen písmena.** `[^\W\d_]`, aby se nechytly číslice.

**Rozdíl proti conBondu2:** ten tečky *maže* (`R.U.R.` → `RUR`,
`core/tvrzeni.py`). Tady se tokeny **slučují se zachováním teček**, protože
`R.U.R.` je správný povrch a cache má nést text tak, jak stojí v korpusu.

### 3.2 Jednoslovné zkratky

Výčtový seznam, protože bezvýčtově je odlišit nelze — `sv.` na konci věty je
zkratka i konec věty zároveň. Seznam se přebírá z jellyAI3
(`jellyai/text.py`, 29 položek) a rozšiřuje o zkratky naměřené v korpusu
conBondu2 (§ 13.1): `cit.`, `čp.`, `vyd.`, `str.`, `stol.`, `roč.`, `obr.`

**Seznam patří do jazykového profilu, ne do kódu** (`SEAM-8` návrhu, kap. 6).
Je to slovník jazyka; angličtina má jiný.

### 3.3 Řadové číslovky

Číslice následovaná těsnou tečkou (`SpaceAfter=No` na číslici) se slučuje.

**Řez, bez kterého by to bylo špatně:** tečka, která je **poslední token věty**,
se neslučuje — tam ukončuje větu. Bez toho řezu měření nadhodnotilo výskyt vady
o 1 062 vět (§ 13.1); `, 1985 .` je rok na konci věty, ne řadová číslovka.

### 3.4 Číselné skupiny a desetinná čísla

UDPipe rozsekává čísla psaná s oddělovačem tisíců i desetinnou čárkou:

```
30 000       → 30 | 000
1 250 000    → 1 | 250 | 000
3,14         → 3 | , | 14
```

Slučuje se: **číslice, mezera (obyčejná i nezlomitelná), tři číslice** —
opakovaně; a **číslice, čárka, číslice** bez mezer.

Že to není kosmetika, je změřeno (§ 13.6): UDPipe dá `30` a `000` jako **dva
samostatné `nummod:gov`**, oba visící na počítaném jméně. `AG-METRON` tedy vidí
dvě čísla místo jednoho a naměří `30`. conBond2 to má v etalonu jako doloženou
mezeru:

> `„Kolik dělnic je v úlu při hlavní snůšce?"` — *„'30 000' je rozdělené na dva
> tokeny, návěska je jen na '30'"*

Tohle je učebnicový případ zásady 3.0: pomůže to měřitelně a nic se tím
neztratí, protože původní text nese `SpaceAfter=No` a dá se z tokenů složit zpět.

**Řez:** slučují se jen skupiny **právě tří číslic**. `V roce 1890 zemřel` se
sloučit nesmí — `1890` je rok a následující slovo s ním nesouvisí. Bez toho řezu
by se `12 345 678 lidí` sloučilo správně, ale `roku 1890 Praha` taky.

### 3.5 Co se vědomě nedělá

* **Nescelují se víceslovná jména.** `Karel Čapek` zůstávají dva tokeny — je to
  správně podle UD a scelení je práce entitní vrstvy. conBond na tom má
  rozsáhlý měřený zápis: *„44 flat dvojic z 2002 má neshodný pád a vzorek je
  BEZ VÝJIMKY dvojice podmět+adresát/předmět"* (`core/registry.py`).
* **Nepřepisuje se text.** Datum se nenormalizuje na `1851-08-23` **v textu**;
  normalizovaná hodnota patří do `MISC` jako anotace (§ 6).
* **Nesjednocují se pomlčky, uvozovky ani nezlomitelné mezery.** Zdálo by se, že
  právě tohle zásada 3.0 žádá — conBond to má v matici tvarů dat jako
  `NEPOKRYTO` s poznámkou *„jiná tokenizace znamená jiný rozbor a jinou (nebo
  žádnou) odpověď"*. **Měření to ale nepotvrdilo a ukázalo cenu** (§ 13.6):
  druh pomlčky hranice tokenů nemění vůbec, takže by to nepomohlo — a en-dash
  proti spojovníku nese informaci, kterou `AG-BIO` používá k rozlišení rozsahu
  `1926 – 2011` od názvu `Praha - Libeň`. Sjednocení by ji zničilo.
  Nezlomitelná mezera je v korpusu prakticky nepřítomná (1 věta z 5 990) a
  tokenizaci taky nerozbíjí. **Neděláme to proto, že by to nebylo naše, ale
  proto, že by to nepomohlo a něco by to stálo.**

---

## 4 · Klíč cache: věta, model **a verze tokenizéru**

```
klíč = (text věty, jméno modelu, verze tokenizéru)
```

Model je v názvu souboru, verze tokenizéru v záznamu. Důvod pro obojí je stejný:
**rozbor bez nich není určený.** Kdyby se změnila pravidla § 3 a klíč to nenesl,
cache by tiše vracela rozbory jiné tokenizace — přesně ta záměna, kterou `INV-9`
a § 14 politiky zakazují.

**Verze tokenizéru je otisk pravidel, ne ruční číslo** (návrh, kap. 26.2): sestaví
se ze seznamu zkratek a z čísla verze algoritmu. Ruční číslo zastará v první
chvíli, kdy někdo přidá zkratku a zapomene ho zvednout.

Změna pravidel tím cache **neznehodnotí** — staré záznamy zůstanou platné pro
svou verzi a nové se doplní. To je podmínka toho, aby se pravidla dala vyvíjet
(§ 1: cache je hodnota, ne odpad).

**Normalizace klíče** je NFC, totéž co dělá sám server
(`unicodedata.normalize("NFC", params["data"])`). Nic víc — srovnávat velikost
písmen nebo mezery by znamenalo vracet rozbor jiné věty, než o kterou se
volající ptal.

---

## 5 · Ukládá se všech deset sloupců

```json
{"id": 4, "form": "23.", "lemma": "23.", "upos": "NUM", "xpos": "Cn-------------",
 "feats": {"NumType": "Ord"}, "head": 5, "deprel": "nummod:gov",
 "deps": null, "misc": {"SpaceAfter": "No"}}
```

conBond2 bral sedm sloupců z deseti (`core/ingest.py`) a `MISC` vynechával
úplně — tedy i `SpaceAfter=No`, bez kterého se z tokenů nedá složit původní
text. Bralo se to, co bylo zrovna potřeba; tady se bere všechno, protože cache
je dlouhodobá sbírka (§ 1) a chybějící sloupec se pozná až za půl roku.

**`feats` a `misc` jsou slovníky, ne seznamy řetězců.** Prázdná hodnota je
`null`, ne `"_"` — „nemá hodnotu" je stav, ne řetězec (`INV-9`).

**Víceslovné tokeny** (`1-2 dělalas`) a prázdné uzly (`5.1`) se ukládají v poli
`multiword`, ne mezi tokeny. conBond2 je tiše zahazoval testem `isdecimal()`.

---

## 6 · Hranice modulu

cb-udpipe **tokenizuje a rozebírá**. Nedělá:

* **scelování víceslovných jmen a entit** — entitní vrstva (§ 3.4),
* **výklad významu** — `AG-BIO`, `AG-CHRONOS` a spol. z návrhu, kap. 10.

Rozdíl mezi tokenizací a výkladem je pro tenhle modul zásadní, protože se snadno
slije. Ukázkou je životopisná závorka:

```
Alois Jirásek (23. srpna 1851 Hronov – 12. března 1930 Praha) byl spisovatel.
               └─ narození ────────┘   └─ úmrtí ──────────┘
```

**Co je práce cb-udpipe:** `23.` má být jeden token, ne dva. Tečka.

**Co práce cb-udpipe není:** že levá půle je narození a pravá úmrtí. To je
výklad konstrukce a patří `AG-BIO`, který na to má v conBondu2 rozsáhlý měřený
zápis včetně čtyř pastí (nedefiniční závorka, hranice 16 tokenů, „ne každá
pomlčka dělí", místo vs. příjmení).

### Anotace v MISC je cesta, přepis textu ne

Modul smí do `MISC` přidat vlastní anotaci a **ověřeně projde rozborem beze
změny** (§ 13.4):

```
4   23.   NUM   Date=1851-08-23|Src=cb-udpipe
```

Naproti tomu **vkládat do textu slova, která tam nestála** („narozen", „zemřel")
se nesmí ze dvou důvodů: `# text` je klíč cache, takže by se změnou textu
rozpadla, a hlavně by to do dat vložilo tvrzení, které v korpusu není — `INV-3`,
odvozené se nesmí splést s doloženým.

Vrstva nad námi si `Event=birth` přečte stejně snadno jako slovo „narozen", ale
nikdo si to nesplete s tím, co je doloženo.

---

## 7 · Cache na disku: JSONL a index v paměti

```
cb_udpipe/data-persistent/cache/cs_all-ud-2.17-251125.jsonl

{"source":"…","model":"…","tokenizer":"a91f3e","tokens":[…],
 "multiword":[],"ts":"…","format_version":1}
```

**JSONL, ne jeden JSON objekt.** Zadání říká „json objekt s klíčem zdroje a
klíčem výstupu" a JSONL to splňuje — každý řádek je takový objekt. Rozdíl je
v tom, že jde připisovat na konec; jeden velký objekt by se musel při každé nové
větě přepsat celý. conBond2 měl obdobu (`data/raw/_tokeny.json`) a při 70 MB to
už bolelo.

**Index** se staví při startu: `text věty → offset řádku`. V paměti jsou jen
klíče (26 tisíc vět ≈ 3 MB *(neměřeno)*), tokeny se čtou `seek`em při zásahu.

**Zápis** je append plus `fsync`. Atomický zápis přes `os.replace` (§ 8 politiky)
tu nejde — to je celý soubor, ne řádek. Po pádu je rozbitý nejvýš poslední
řádek; ten se při startu přeskočí a započítá do souhrnu jako `cache_corrupt`.

**Cache se neuklízí.** Její obsah je hodnota, ne odpad (§ 1).

---

## 8 · Co modul nabízí ven

```python
from cb_udpipe import UdpipeClient

parser = UdpipeClient(endpoint=cfg["module"]["udpipe_endpoint"], log=log)
vety = parser.parse(text="Alois Jirásek (23. srpna 1851) byl spisovatel.", trace=trace)

vety[0].tokens[3].form       # "23."   ← opravená tokenizace
vety[0].source               # "Alois Jirásek (23. srpna 1851) byl spisovatel."
vety[0].from_cache           # True
```

| bod | co dělá |
|---|---|
| `GET /version` | verze modulu i tokenizéru, mimo `/v1/` |
| `GET /v1/health` | stav, dostupnost UDPipe, načtený model, velikost cache |
| `GET /v1/config` | skutečně použitá konfigurace včetně cesty |
| `GET /v1/summary` | počty podle metoda × result |
| `POST /v1/parse` | `{"text": …, "trace": …}` → věty s tokeny, `cached`, `parsed` |
| `POST /v1/tokenize` | jen segmentace a tokenizace, bez tagů — levné |
| `GET /v1/cache/stats` | počet vět, velikost, poškozené řádky, rozpad podle verzí |

---

## 9 · Provoz vlastní instance UDPipe

Modul provozuje UDPipe 2 jako **vlastní proces vedle sebe** (§ 19 politiky), ne
jako import. Hranice vede po procesu: to, že v `.venv` leží TensorFlow,
neznamená, že si ho smí naimportovat `service.py`.

```
./cb-udpipe.py start
  1 · ověří konfiguraci
  2 · ověří model            → jinak exit 2 se jménem souboru a fetch skriptem
  3 · zvedne UDPipe na 42201 → HF_HOME dovnitř modulu, HF_HUB_OFFLINE=1
  4 · počká, až odpoví
  5 · zvedne naši službu na 42200
```

**Offline natvrdo.** UDPipe si pro embeddingy sahá na RobeCzech přes
HuggingFace; bez `HF_HUB_OFFLINE=1` by si ho stáhl do `~/.cache`. V conBondu2 to
při prvním spuštění bez sítě spadlo — přesně ta závislost na okolí, které se
zbavujeme.

**Předehřátí** (`module.warmup`) pošle při startu jednu větu, aby líné načtení
sítě (v conBondu2 přes 5 s plus 4,7 s na první embeddingy) nedopadlo na první
skutečný dotaz.

---

## 10 · Co se loguje

**Textově** na hranicích: `parse`, `tokenize`, `retokenize`, `cache_lookup`,
`upstream`. Stavy podle logovátka: `empty` = vstup neobsahoval větu (není
chyba), `skipped` = věta přes 1000 slov, `error` = UDPipe neodpověděl nebo přišel
rozsypaný CoNLL-U.

**Objektově** do kukátka na `:42102` přes `log.json()`. Vypínatelné, protože na
plném korpusu je to 26 tisíc objektů:

| `module.log_objects` | co se loguje |
|---|---|
| `off` | nic |
| `miss` | jen věty, které se skutečně rozebíraly ← **výchozí** |
| `all` | každý rozbor včetně cache zásahů |
| `retokenized` | jen věty, kterým oprava změnila tokenizaci |

Poslední hodnota je tam kvůli ladění pravidel § 3: ukáže přesně ty věty, do
kterých modul zasáhl, a nic jiného.

---

## 11 · Chybové stavy

| situace | co udělá |
|---|---|
| UDPipe neběží | `503`, typ `upstream_unavailable`, v těle čím ho spustit |
| model chybí při startu | start selže, `exit 2`, jméno souboru + fetch skript |
| věta přes 1000 slov | `skipped` s důvodem; ostatní věty dávky projdou |
| tělo nad `max_request_bytes` | `413` — náš strop je nižší než serverový (4 MB) |
| rozsypaný CoNLL-U | `error`, nikdy prázdný seznam |
| prázdný vstup | `200` a `empty` |
| poškozený řádek cache | přeskočí se, do souhrnu jako `cache_corrupt` |

Dvě pasti z předchozích projektů, obě s vlastním regresním testem:

> `int(c[0])` spadlo na tokenu `²`, protože `"²".isdigit()` je `True`, ale
> `int()` na tom spadne. Článek o betonu má `m²` a shodil stavbu celého korpusu
> na 86 článcích. *(conBond2, `core/agents/base.py`)*

Správný predikát je `isdecimal()` a v `conllu.py` je na jednom místě.

> Data se posílají PŘES SOUBOR, NE inline: inline `-F data=…` ořezává velký
> vstup na ~485 znaků — past, kvůli které bible ztrácela 95 % textu.
> *(conBond, `core/annotate.py`; totéž v jellyAI3)*

Nás se netýká přímo (posíláme `application/x-www-form-urlencoded`, ne
`multipart`), ale test na dlouhý vstup je levný a tahle past stála dva projekty
hodně času.

---

## 12 · Model místo pravidel: zatím ne

Zadání zvažuje natrénovat malý model, který by s tokenizací pomohl. Pravidla
§ 3 jsou první krok a model druhý, v tomhle pořadí ze tří důvodů:

1. **Jevy jsou pravidelné.** Řadová číslovka je číslo a tečka; zkratka je běh
   písmen s tečkami. Kde stačí pravidlo, je model dražší způsob téhož.
2. **Není na čem trénovat.** Trénovací data pro tokenizér jsou ručně opravené
   tokenizace — a ty zatím nikde nejsou. **Cache je bude vyrábět** (§ 1): až
   v ní bude dost vět, dá se z nich vzorek ručně opravit a model natrénovat.
3. **Nejdřív je potřeba vědět, kde pravidla selhávají.** Bez toho by se model
   učil to, co už umí `if`.

Až model přijde, sedí za **švem** — `module.tokenizer: "rules" | "model"` — a
přijme se **měřením proti pravidlům**, ne dojmem. Verze tokenizéru je v klíči
cache (§ 4) právě proto, aby šly obě varianty porovnat na týchž větách.

Sem patří i `INV-11` návrhu: statistický model smí navrhovat, ne rozhodovat
o pravdivosti. Tokenizace není tvrzení o světě, takže model tu není vyloučen —
ale výsledek se měří stejně jako každé pravidlo.

---

## 13 · Měření, o která se návrh opírá

Provedeno 2026-08-03 proti běžící instanci UDPipe 2 s modelem
`cs_all-ud-2.17-251125` a korpusu conBondu2 (26 051 vět).

### 13.1 Četnost vady tokenizace

| vada | vět | podíl |
|---|---|---|
| řadová číslovka uprostřed věty | 1 129 | 4,3 % |
| jednoslovná zkratka uprostřed věty | ~1 100 | 4,2 % |
| iniciály a víceznakové zkratky | 173 | 0,7 % |

Nejčastější: `1. vyd` 108×, `20. století` 84×, `19. století` 49×, `např.` 179×,
`tzv.` 162×, `n. l.` 30×, `T. G.` 22×.

**Řez, který měření opravil:** tečka jako poslední token věty se nepočítá.
Bez něj vyšlo 7,6 % místo 4,3 % — 1 062 případů byly roky na konci věty.

### 13.2 Segmentace je spolehlivá

Devět vzorků (`R.U.R.`, `28. 3. 1592`, `500 př. n. l.`, závorkové datum,
`ve 40. letech`) — všechny zůstaly **jednou větou**. Tečka ve zkratce ani
v řadové číslovce větu neroztrhne.

### 13.3 Vlastní tokenizace nezhoršuje rozbor, zlepšuje ho

```
R.U.R. je drama Karla Čapka.

UDPipe:    R · . · U · . · R · .     „R" NOUN nsubj   ← podmětem je písmeno
vlastní:   R.U.R.                    „R.U.R." PROPN nsubj
```

U data totéž: `23.` jako jeden token dostal `nummod:gov` místo `nummod`.

### 13.4 Anotace v MISC projde beze změny

Odesláno `Date=1851-08-23|Zdroj=vlastni`, vráceno nedotčené. Totéž `# sent_id`
a `# text` — proto se odpovědi 4. fáze párují na dotazy podle `sent_id`.

### 13.5 Riziko „vlastní tokenizace se rozejde s modelem" — vyvráceno

conBond (`docs/dil-8.html`) i jellyAI3 (`docs/dil-8.html`) tuhle variantu
zamítly **shodnou formulací a bez měření**:

> „Vyčlenit vlastní normalizaci před UDPipe. *Riziko:* vlastní tokenizace se
> rozejde s tou, na které je UDPipe model natrénovaný."

Změřeno na 200 větách korpusu (653 vět po segmentaci). Porovnány značky
tokenů, **kterých se oprava nedotkla** — tam se případný rozpad projeví:

| | próza (83 vět) | bibliografie (570 vět) |
|---|---|---|
| sloučeno opravou | 92 tokenů | 784 tokenů |
| beze změny hranic | 1 424 tokenů | 5 119 tokenů |
| z nich změnilo UPOS | 1 (**0,07 %**) | 21 (0,41 %) |
| z nich změnilo deprel | 8 (**0,56 %**) | 121 (2,36 %) |
| z nich změnilo hlavu | 15 (**1,05 %**) | 239 (4,67 %) |

**Závěr: na próze je vedlejší dopad pod jedno procento u značek a okolo jednoho
procenta u závislostí, kdežto opravených vět je zhruba každá jedenáctá.** Riziko
se nepotvrdilo a přínos je řádově větší než cena.

Dvě poznámky k poctivosti měření, obě posunuly čísla dolů:

* **Bibliografie se počítá zvlášť.** conBond2 změřil, že 57 % „vět" korpusu nemá
  slovesný kořen a je to bibliografie (`Praha : Academia , 1985 .`). Na té je
  rozbor nestabilní bez ohledu na naši opravu; smíchané dohromady vyšlo
  9,46 % změněných hlav místo 1,05 %.
* **Hlava se porovnává podle textové pozice, ne formy.** Sloučený token má jinou
  formu (`4` → `4.`), ale je to pořád tentýž token na témž místě. Porovnávání
  podle formy hlásilo změnu tam, kde žádná nebyla.

Zbylé skutečné změny v próze se soustředí do dvou vět (věta o antarktických
údolích a o značení betonů) — je to pár konkrétních vět, ne plošný jev.

### 13.7 Měření hotového modulu

Provedeno 2026-08-03 na zmraženém vzorku 500 vět (`tests/data/mereni.jsonl`,
náhodný výběr z korpusu conBondu2 se semínkem 20260803, poměr vět s vadou
odpovídá korpusu). Model `cs_all-ud-2.17-251125`, tokenizér `6247b8b7a5c8`,
konfigurace `b5d85137bd39`. Úplná data v `mereni-2026-08-03.json`.

| co | naměřeno | co to znamená |
|---|---|---|
| vět s opravou tokenizace | **17,6 %** (176 z 998) | vyšší než odhad ze § 13.1 — ten počítal jen tři vzory, tady se sečetly všechny |
| oprav celkem | 273 | některé věty mají oprav víc |
| **podíl tokenizace na čase** | **2,7 %** | ⇐ **na tomhle stojí dvoufázový postup** |
| podíl zásahů (2. průchod) | 100 % | klíč funguje |
| zrychlení druhým průchodem | **26×** (39,1 s → 1,5 s) | důvod, proč modul existuje |
| cache na větu | 2 747 B | 26 tisíc vět ≈ 70 MB |
| **neshod cache proti čerstvému rozboru** | **0** | ⇐ protiváha k podílu zásahů |
| poškozených řádků | 0 | |
| přeskočených vět | 0 | žádná nepřesáhla mez serveru |

**Nejdůležitější řádek je poměr fází.** Tokenizace stojí **2,7 %** času, který
zabere dorozbor — tedy zhruba **třicetkrát méně**. Předpoklad, na kterém stojí
§ 2, tím platí s velkou rezervou: i kdyby se cache netrefila vůbec, stojí
segmentační fáze navíc necelá tři procenta.

**Druhý nejdůležitější je nula neshod.** Podíl zásahů jde nafouknout volnějším
klíčem, takže sám o sobě nic neznamená. Nula neshod proti čerstvému rozboru
říká, že klíč (text + model + verze tokenizéru) je správně úzký.

Zrychlení se měří **jen od studené cache**. Druhý běh nad plnou cache vrátí
1,0×, protože z ní bere i „první" průchod; není to vlastnost modulu, ale
artefakt měření a `scripts/mereni.py` na to upozorňuje v docstringu.

**Jednotný interpret.** První kolo měření proběhlo za stavu, kdy služba běžela
na Pythonu 3.14.6 (systémový, přes shebang) a měřicí skript na 3.11.15
(projektový, přes `./run-python`). Měřilo se tedy proti něčemu jinému, než se
tvrdilo — táž třída vady, na kterou doplatil conBond2 u testů měřících proti
pracovní kopii. Ovládací program se teď přepíná na projektový interpret sám
(politika, § 19) a čísla výše jsou z opakovaného měření na 3.11.15. Změnila se
jen doba prvního průchodu (41,6 → 39,1 s, tedy v rámci šumu); podíl oprav,
poměr fází i nula neshod vyšly totožně, protože rozbor dělá UDPipe, který
běžel správně po celou dobu.

### 13.6 Sjednocení znaků: nepomohlo by a něco by stálo

Zásada 3.0 vede k otázce, jestli nesjednotit pomlčky, uvozovky a nezlomitelné
mezery. Změřeno ve dvou krocích a odpověď je **ne**.

**Jak často to v korpusu je** (5 990 bloků textu):

| znak | výskytů | vět |
|---|---|---|
| en-dash `–` | 2 789 | typografická pomlčka v 35,7 % vět |
| spojovník `-` | 2 365 | |
| uvozovky `„` / `“` | 2 513 / 2 499 | 11,4 % vět |
| nezlomitelná mezera | 0 | 1 věta má soft hyphen (0,0 %) |

**Mění druh znaku tokenizaci?** Ne:

```
Žil v letech 1890–1938 v Praze.    → 1890 | – | 1938
Žil v letech 1890-1938 v Praze.    → 1890 | - | 1938
Žil v letech 1890 – 1938 v Praze.  → 1890 | – | 1938
Datum 9.<NBSP>ledna 1890.          → 9 | . | ledna | 1890
```

Hranice tokenů jsou ve všech případech totožné. Nezlomitelná mezera tokenizaci
nerozbila. **Sjednocení by tedy nepomohlo ničemu.**

**A co by stálo:** en-dash proti spojovníku nese informaci, na které stojí
`AG-BIO` v conBondu2:

> „( 21. prosince 1926 Praha - Libeň – 26. února 2011 Praha )" má pomlčky dvě
> a ta první je uvnitř názvu čtvrti; vzalo se to za dělič a z Libně se stalo
> místo úmrtí. **Dlouhá pomlčka má přednost: rozsah dat se sází en-dashem,
> kdežto spojovník uvnitř „Praha - Libeň" odděluje části názvu.**

Sjednocení obou na jeden znak by tohle rozlišení zničilo — a byla by to ztráta
informace, kterou zásada 3.0 výslovně zakazuje.

**Kam měření vedlo místo toho:** k číselným skupinám (§ 3.4), kde vyšlo obojí
opačně. UDPipe dá `30 000` jako **dva samostatné `nummod:gov`**:

```
V úlu je 30 000 dělnic.

UDPipe:   30 NUM nummod:gov head=dělnic
          000 NUM nummod:gov head=dělnic     ← dvě čísla místo jednoho
vlastní:  30 000 NUM nummod:gov head=dělnic
```

Tam pomoc měřitelná je a nic se neztrácí.

---

## 14 · Registr prahů

Hodnoty *(neměřeno)* jsou odhady a nahradí se naměřenými čísly s datem a verzí
dat (§ 5 politiky).

| id | hodnota | co ovlivňuje | odkud se vzala |
|---|---|---|---|
| `batch_sentences` | 60 | vět v jednom dorozboru | conBond2 `Prijem.rozebrat` — „jedno volání na celý článek je pro UDPipe moc a jedno na větu zbytečně pomalé" |
| `abbrev_min_pairs` | 2 | kolik párů ⟨písmeno⟩⟨.⟩ tvoří zkratku | conBond `normalize.py` a jellyAI3 — pod 2 by se chytila iniciála `K. Čapek` |
| `max_request_bytes` | 2 MiB | strop na požadavek | polovina serverového stropu, ať chyba vznikne u nás |
| `max_sentence_words` | 1000 | kdy se věta přeskočí | mez serveru, ne naše volba |
| `request_timeout_s` | 600 | strop na volání UDPipe | conBond2 `core/ingest.Rozbor` |
| `upstream_start_timeout_s` | 120 | čekání na start UDPipe | *(neměřeno)* — načtení modelu 357 MB |

Naměřené hodnoty, které prahy potvrzují nebo upravují (§ 13.7):

| co | naměřeno | důsledek pro práh |
|---|---|---|
| doba rozboru 500 vět | 41,6 s | `request_timeout_s` 600 s má velkou rezervu; ponechán |
| nejdelší věta ve vzorku | pod mezí | `max_sentence_words` se v 500 větách neuplatnil |
| cache na větu | 2 747 B | plný korpus ≈ 70 MB, strop zatím není potřeba |

---

## 15 · Co modul vědomě neřeší

* **Scelování jmen a entit** — entitní vrstva (§ 3.4, § 6).
* **Výklad konstrukcí** (narození/úmrtí ze závorky) — `AG-BIO` (§ 6).
* **Sjednocení pomlček, uvozovek a nezlomitelných mezer** — skutečná mezera,
  v conBondu vedená jako `NEPOKRYTO`, ale patří k čištění korpusu.
* **Doplňování diakritiky.** conBond to označuje za „nejpodceňovanější past";
  je to předzpracování v příjmu, jazykově závislé (návrh, kap. 14.1).
* **Detekci jazyka** — rozhoduje volající.
* **Víc modelů zároveň** — jedna instance, jeden model.
* **Dotazovací rozhraní nad cache** — kdo potřebuje vidět dovnitř, otevře JSONL.

---

## 16 · Licence

| co | licence | důsledek |
|---|---|---|
| UDPipe 2 zdrojáky | MPL 2.0 | ve `vendor/`, s údajem o zdroji |
| model `cs_all-ud-2.17-251125` | **CC BY-NC-SA** | **nekomerční**, do gitu nesmí |
| RobeCzech | dle ÚFAL | totéž — mimo git |

Kontrola, že licencovaná data nevstoupila do repozitáře, je automatická
(`T-8`, návrh kap. 37), ne slib.
