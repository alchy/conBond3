# cb-udpipe — metody

Každá veřejná metoda: co dělá, proč existuje, na čem visí. Kdo hledá, **jak**
modul volat, chce `../../README-UDPIPE.md`; kdo hledá **proč** je postavený
takhle, chce `koncepce.md`.

---

## `UdpipeClient` — rozhraní pro ostatní moduly

`cb_udpipe/client.py`. Tohle si naimportují ostatní moduly; REST je uvnitř
a volající ho nepíše.

### `UdpipeClient(*, endpoint, log=None, timeout_s=600, api="v1")`

Ověří **při vytvoření**, že služba běží a mluví naší verzí rozhraní.

*Proč existuje:* klient nad neběžící službou je tikající chyba. Kdyby se
výpadek ukázal až u prvního `parse()`, spadlo by to uprostřed dávky, po hodině
počítání a s polovinou zapsaných výsledků.

*Visí na:* `GET /version` běžící služby.

*Chyby:* `ServiceUnavailable` (hláška uvádí modul, adresu a příkaz ke
spuštění), `IncompatibleApi`.

### `parse(*, text, trace=None) -> ParseResult`

Rozebere text. Táž signatura i návratový typ jako `UdpipeService.parse` —
hlídá to zkouška shody tváří `T-K3`.

*Visí na:* `POST /v1/parse`.

*Chyby:* `ServiceUnavailable` (i když neběží UDPipe pod službou),
`RuntimeError` s typem chyby ze služby. Prázdný vstup **není** chyba.

### `tokenize_only(*, text, trace=None) -> list[Sentence]`

Jen segmentace a tokenizace, bez tagů. Řádově levnější: UDPipe při něm
nenačte síť (naměřeno 2,7 % času plného rozboru).

*Proč existuje:* volající, kterému stačí hranice vět nebo tokenů, nemá platit
za embeddingy.

*Do cache nezapisuje* — tokenizace bez tagů není rozbor.

### `health()`, `summary()`

Průchozí čtení `GET /v1/health` a `GET /v1/summary`.

---

## `UdpipeService` — doménová logika

`cb_udpipe/service.py`. Nezná HTTP; testuje se přímo, bez spuštěné služby.

### `parse(text, *, trace=None) -> ParseResult`

Čtyři fáze: segmentace UDPipem → naše oprava tokenizace → cache → dorozbor
předtokenizovaného CoNLL-U.

*Proč nelze přeskočit fázi 1 ani při plném zásahu cache:* segmentaci dělá
UDPipe, takže bez ní není známo, na které věty se cache ptát.

*Visí na:* `Upstream`, `tokenize.Rules`, `Cache`.

*Chyby:* propouští `UpstreamUnavailable` a `UpstreamError`. **Nikdy nevrací
prázdný výsledek místo chyby** — slil by se s platným prázdným rozborem.

### `tokenize_only(text, *, trace=None) -> list[Sentence]`

Jen fáze 1 a 2.

### `health() -> dict`

Stav pro `GET /v1/health` a pro `status`. UDPipe je povinná závislost, takže
jeho výpadek znamená `degraded`, ne `ok` — a musí to být vidět dřív, než na to
narazí první dotaz.

### `summary() -> dict`

Počty podle metody a výsledku plus stav cache. **Podíl `empty` není
chybovost** — chybovost je podíl `error`.

---

## `tokenize` — pravidla opravy

`cb_udpipe/tokenize.py`. Čistá funkce nad tokeny; testuje se bez UDPipe.

### `retokenize(sentence, rules) -> (Sentence, int)`

Opraví tokenizaci věty; druhá položka je počet sloučení.

*Pořadí pravidel je významné:* běh písmen s tečkami (`R.U.R.`) → jednoslovné
zkratky → řadové číslovky → číselné skupiny. Kdyby se řadové číslovky
zkoušely dřív, rozpadlo by se `n. l.`; kdyby číselné skupiny dřív než řadové,
sloučilo by se `20 . 000` špatně.

*Invariant:* **text věty se nikdy nemění**, jen hranice tokenů. `source` je
klíč cache.

### `Rules.from_config(config) -> Rules`

Seznam zkratek je jazykové datum (`SEAM-8` návrhu), ne kód — angličtina má
jiné. Zkratky se srovnají na malá písmena, aby `Sv.` i `sv.` trefily tutéž
položku.

### `fingerprint(rules) -> str`

Otisk pravidel, dvanáct hexadecimálních znaků. Je součástí klíče cache.

*Proč otisk a ne ruční číslo:* ruční verze zastará v první chvíli, kdy někdo
přidá zkratku a zapomene ji zvednout. Otisk je stabilní vůči pořadí zkratek —
množina pořadí nemá.

---

## `Cache` — trvalá paměť rozborů

`cb_udpipe/cache.py`. JSONL na disku, index klíč → offset v paměti.

### `Cache(*, directory, model, tokenizer)`

Při vytvoření přečte soubor a postaví index. Záznam s **jiným otiskem
tokenizéru** se do indexu nezaloží, ale v souboru zůstane: změna pravidel
cache neznehodnotí.

### `get(source) -> Sentence | None`

`None` znamená „nemám", ne chybu. Klíč se normalizuje na NFC — totéž dělá sám
server.

### `put(sentence, *, ts)`

Připsání na konec plus `fsync`. `ts` se předává zvenčí, aby šla funkce
deterministicky otestovat.

*Proč ne atomický zápis přes `os.replace`:* to je celý soubor, ne řádek.
Pojistka je jinde — po pádu je rozbitý nejvýš poslední řádek a ten se při
startu přeskočí a započítá jako `corrupt`.

### `stats() -> dict`

Počet vět, poškozených řádků, velikost, model a tokenizér.

---

## `conllu` — čtení a psaní

`cb_udpipe/conllu.py`. Čistá funkce nad textem.

### `parse(text) -> list[Sentence]`

Bere **všech deset sloupců**. `FEATS` a `MISC` jsou slovníky, prázdná hodnota
je `None`. Víceslovné tvary jdou do `multiword`, prázdné uzly (`1.1`) se
přeskakují.

*Nikdy nevyhazuje na rozsypaném řádku:* vstup přichází ze sítě a jediná vadná
věta nesmí shodit celou dávku.

### `write(sentences) -> str`

Přesný protějšek `parse`. Na tom stojí fáze 4: výstup téhle funkce se posílá
zpátky serveru.

---

## `Upstream` — klient UDPipe serveru

`cb_udpipe/upstream.py`. Jediné místo modulu, které s ním mluví.

### `tokenize(text, *, trace=None) -> str`

Posílá **jen** `tokenizer`. Server má v `predict()` podmínku `if tag or parse`,
takže bez taggeru a parseru vůbec nenačte síť.

### `tag_and_parse(conllu_text, *, trace=None) -> str`

**Neposílá `tokenizer`**, takže server čte vstup jako CoNLL-U a segmentaci
nemění. Bez toho by se naše oprava zahodila a věty by se navíc mohly slepit.

### `models() -> dict`

Nejlevnější dotaz, který nesahá na data. Používá ho `control.py` k čekání na
start a `service.health()` ke zjištění dostupnosti.

---

## `control` — ovládání

`cb_udpipe/control.py`. Volá se z `./cb-udpipe.py`.

### `main(argv) -> int`

Pět příkazů, návratové kódy `0`/`1`/`2`/`3`.

`start` zvedne nejdřív UDPipe, počká na `/models`, teprve pak naši službu.
Data se kontrolují **před** spuštěním a hlásí se **všechna** chybějící
najednou — dozvědět se to na dvakrát znamená dvakrát čekat.

`status` uvádí **oba porty** i u neběžící služby a pozná osiřelý PID soubor
po spadlé službě.
