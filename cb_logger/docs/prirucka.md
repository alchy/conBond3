# cb-logger — příručka pro vývojáře

Roste z dialogu při stavbě. Každá kapitola vznikla z otázky, která při práci
opravdu padla, a odpovídá na ni tím, co v tu chvíli skutečně fungovalo —
ne tím, co by mělo.

Rozcestník a přehled rozhraní je v `../README.md`, návrhová rozhodnutí
v `koncepce.md`. Tohle je to, co se do rozcestníku nevejde: jak se to volá
a kde jsou pasti.

---

## 0 · Nejkratší cesta: první řádek v logu

Tři řádky. Služba musí běžet (`./cb-logger.py start`).

```python
from cb_logger import LogClient, Result

log = LogClient(component="pokus")
log.info(method="prvni_radek", result=Result.OK)
log.close()
```

Co se tím zapsalo:

```json
{"ts": "2026-08-03T07:23:57.512Z", "level": "info", "component": "pokus",
 "method": "prvni_radek", "trace": null, "result": "ok"}
```

Tři věci na tom výstupu stojí za povšimnutí:

* **`result` je povinný**, protože bez něj by se nedalo počítat. Čtyři hodnoty:
  `ok`, `empty`, `skipped`, `error`.
* **`trace` je `null`** a zapsalo se to schválně. Chybějící stopa je měřitelná
  díra v řetězu doložení, ne detail k zamlčení — v souhrnu se počítá jako
  `without_trace`.
* **`close()` je potřeba.** Bez něj se poslední záznamy ztratí; zápis je
  asynchronní (viz past v kapitole 1).

Zkontrolovat, že to dorazilo:

```
curl -s http://127.0.0.1:42100/v1/summary
tail -1 cb_logger/data-persistent/log.jsonl
```

Nebo se dívat živě v prohlížeči na <http://127.0.0.1:42101>.

### Hláška pro člověka: `message`

> *Navrhuji, aby stopa byl prostě textový řetězec — prostě content logu
> (message). Je na každém, aby si tam dal co chce.*

Volné pole pro člověka přibylo — jmenuje se `message`:

```python
log.info(method="nacti_korpus", result=Result.OK,
         message="načteno 97 vět z Jiráskovy prózy")
```

**Ale `trace` to není a nesmí být.** Jsou to dvě věci s různou prací:

| pole | co v něm je | k čemu |
|---|---|---|
| `message` | volný text, cokoli chceš | aby to člověk přečetl |
| `method` | jméno metody | aby šel spočítat souhrn podle komponenta × metoda × result |
| `trace` | identifikátor průchodu | aby šlo vyfiltrovat, co se dělo při **jedné** otázce napříč moduly |

`trace` volný řetězec **už je** — nekontroluje se, dej tam co chceš. Kdyby do
něj ale každý dával vlastní hlášku, přestane jít složit jeden průchod ze sedmi
modulů, a to je jediný důvod, proč to pole existuje.

Totéž platí pro `method`: kdyby v něm byl volný text, byla by každá hláška
vlastní řádek souhrnu a měření by ztratilo smysl. *(Přesně tohle se stalo při
zkoušení — `log.debug(method="debug hlaska !")` udělalo z hlášky jméno metody. Odtud
`message`.)*

V kukátku se hláška ukazuje **před** shrnutím vstupu a výstupu, v barvě textu,
protože je to to, co člověk čte jako první. A dá se podle ní filtrovat.

### S vyplněnými poli

```python
log.info(method="build_field", result=Result.OK, trace="q-7f3a91",
         message="pole postaveno",
         input={"sentences": 97, "radius": 2},
         output={"rows": 4213},
         duration_ms=412)
```

`input` a `output` jsou v úrovni `info` **shrnutí, ne celý obsah** — počty,
klíče, identifikátory. Celá data patří do `log.json()` (kapitola 3).

---

## 1 · Jak si instanciuju logger?

> *Spustím si `./run-python cli` a ptám se — jak si instanciuju logger?*

### Krátká odpověď

```python
from cb_logger import LogClient, Result

log = LogClient(component="pokus")
log.info(method="prvni_pokus", result=Result.OK, trace="q-repl01",
         input={"co": "zkouším"}, output={"vysledek": 42})
log.close()
```

**Jeden povinný parametr.** `component` je jméno, pod kterým se záznamy objeví.
Adresu logovátka si klient najde sám (viz níž); předává se jen tehdy, když se
mluví s jinou instancí než s tou domácí.

### Co se stane při vytvoření

Konstruktor **není tichý** — zeptá se služby na `GET /version` a podle
odpovědi se rozhodne. Tři možné konce:

| situace | co se stane |
|---|---|
| služba odpoví a umí `v1` | `available` je `True`, klient je připravený |
| služba neodpoví | hláška na chybový výstup, `available` zůstane `False`, zápis jde do spoolu |
| služba odpoví, ale neumí `v1` | hláška o neshodě verzí, `available` zůstane `False` |

Ověřit to jde hned:

```python
>>> log.available
True
>>> log.server_version
{'module': 'cb-logger', 'version': '0.1.0', 'api': ['v1'],
 'config_version': 1, 'python': '3.11.15'}
```

**Proč se to zjišťuje hned a ne až u prvního zápisu.** Klient vytvořený nad
neběžící službou je tikající chyba. Kdyby se výpadek ukázal až u prvního
`info()`, spadlo by to uprostřed dávky, po hodině počítání a s polovinou
zapsaných výsledků. Jedno volání `/version` stojí jednotky milisekund
a `/version` je schválně bod bez závislostí, který odpoví, i když je služba
jinak nezdravá — rozliší tedy *„neběží"* od *„běží, ale něco jí chybí"*.

Když služba neběží, vypadá to takhle a **program pokračuje**:

```
modul cb-logger neodpovídá na http://127.0.0.1:42100/version
(<urlopen error [Errno 61] Connection refused>).
Spusť ho: ./cb-logger.py start
```

Hláška má povinně tři věci — který modul, na jaké adrese ho klient hledal
a čím ho spustit. To třetí je tam proto, že bez něj si každý musí pamatovat
jméno ovládacího programu, a to je přesně ta drobnost, kvůli které se místo
spuštění služby hodinu hledá chyba v kódu.

### `close()` a konec procesu

Zápis je asynchronní: záznam jde do fronty v paměti a odesílá ho vlákno na
pozadí každých 500 ms nebo po 200 záznamech.

**Proč asynchronně.** Podrobná stopa vyrobí na plném korpusu statisíce záznamů.
Synchronní HTTP volání na každý z nich by udělalo z nejcennější části logu tu
nejdražší věc v systému a někdo by ji vypnul.

```python
log.close()        # dopraví frontu a zastaví vlákno; vrátí počet neodeslaných
log.flush()        # dopraví frontu, klient běží dál
```

Obojí vrací **počet neodeslaných záznamů**, ne výjimku — volá se to při ukončení
procesu, kdy už výjimka nemá kam bublat.

**Když na `close()` zapomeneš, o data nepřijdeš.** Klient si registruje pojistku
na konec procesu, která frontu dopraví sama. `close()` zůstává jediná *řízená*
cesta (a jediná, která ti vrátí počet neodeslaných), ale zapomenout na ni není
ztráta dat.

> **Zapsáno po chybě.** Původně pojistka nebyla a `log.info(...)` následované
> koncem skriptu neuložilo nic. První oprava přes `atexit` nestačila: dívala se
> jen do fronty, jenže odesílací vlákno si záznam vyzvedne během mikrosekund
> a drží ho v rozpracované dávce — fronta je pak prázdná, ale odesláno není nic.
> Teprve počitadlo rozpracovaných záznamů (`_pending`) to zavřelo. Při `kill -9`
> se pojistka nespustí; proti tomu je spool a víc udělat nejde.

### Kde klienta vyrobit

**Jednou při startu, ne v každé funkci.** Klient v cyklu znamená kontrolu
služby v cyklu — a při každém vytvoření jedno volání `/version` navíc.

Dál se předává parametrem tomu, kdo loguje. Ne globálem, ne modulovou
proměnnou:

```python
# ANO — ze signatury je vidět, co funkce potřebuje
def build_field(tokens, radius, log, trace):
    log.info(method="build_field", trace=trace, result=Result.OK,
             input={"tokens": len(tokens), "radius": radius},
             output={"rows": len(rows)})
    return rows

# NE — odkud LOG je a kdo ho podstrčí v testu?
def build_field(tokens):
    LOG.info(...)
```

Cena je delší signatura. Zisk je, že u každé funkce jde z hlavičky přečíst,
co ovlivňuje její chování — a to je podmínka, aby šla změřit.

### Endpoint je nepovinný

> *Proč při instancializaci musím zadat endpoint? Když služba běží, mělo by to
> být maximálně volitelné.*

Oprávněná námitka, tak se to změnilo. Tohle stačí:

```python
log = LogClient(component="pokus")
```

Adresu **deklaruje sama služba** — je v její konfiguraci a skutečně přidělený
port si zapisuje do `run/service.port`. Klient jen přečte totéž, co čte
`./cb-logger.py status`. Není to hledání služby po síti ani hádání; je to dotaz
na jediné místo, které odpověď zná.

Pořadí je od nejjistějšího:

| pořadí | zdroj | proč |
|---|---|---|
| 1 | `run/service.port` | skutečný port běžící služby; jediná cesta k číslu, když je v konfiguraci nula |
| 2 | `service.port` z `cb-logger-config.json` | zamýšlený port, když služba neběží |
| 3 | `http://127.0.0.1:42100` | poslední záchrana, když se nedá přečíst ani konfigurace |

Kde se adresa vzala, je vždycky vidět:

```python
>>> log.endpoint
'http://127.0.0.1:42100'
>>> log.endpoint_source
'run/service.port (běžící služba)'
```

To druhé je tam schválně. Bez něj se snadno stane, že se ladí jedna instance
a běží druhá — a nic na tom není poznat.

**Předaný `endpoint` má vždycky přednost** a v `endpoint_source` se objeví jako
`předáno`. Modul, který má v konfiguraci vlastní `logging.endpoint`, si ho
předá; výchozí hodnota je pro toho, kdo žádnou nemá.

**Jak to sedí k „explicitnímu průchodu".** Pravidlo z `README-MODULES.md` § 3 míří na
skryté globály a stav, který nejde v testu podstrčit — ne na to, aby se vše
opisovalo ručně. Explicitní znamená *jde vidět, co se stalo*, ne *musíš to
napsat*. Proto je adresa nepovinná, ale její původ je v `stats()`.

---

## 2 · Mám metody podle severity? `log.warn`, `log.critical`?

> *Tedy mám metody podle severity — log.info, log.warn, log.critical,
> log.error? Je to tak?*

**Není.** Metody jsou dvě a jdou podle **úrovně pohledu**, ne podle závažnosti.
Závažnost se předává parametrem `result`.

```python
log.info(method="build_field", result=Result.OK, …)     # hranice komponenty
log.debug(method="signature",  result=Result.EMPTY, …)  # vnitřek funkce
```

Klasické logování má jednu osu — `DEBUG < INFO < WARNING < ERROR < CRITICAL`.
Tenhle systém má **dvě, a schválně**:

| osa | metoda / parametr | odpovídá na otázku |
|---|---|---|
| **úroveň** | `info` / `debug` | jak hluboko se právě dívám |
| **výsledek** | `result=` | jak to dopadlo |

```
              result=ok      result=empty    result=skipped   result=error
info      →   běžný chod    nic nenašel    přeskočeno      selhalo
debug     →   mezistav      kandidát 0     podmínka ne     výjimka uvnitř
```

### Proč to není jedna osa

Protože `log.error()` slévá dvě různé věci: *„tohle je důležité, ukaž to"*
a *„tohle selhalo"*. A ta druhá se v tomhle systému musí rozlišovat od třetí,
kterou severity neumí vyjádřit vůbec — **prázdného výsledku**.

Věta, ze které nevznikl atom, protože v ní žádný nebyl, je `empty`.
Věta, ze které nevznikl atom, protože spadl parser, je `error`.

V klasickém logování je obojí buď `INFO` (a chyba zapadne), nebo `WARNING`
(a normální stav vypadá jako problém). Kdyby se slily, měření by odměnilo
právě tu chybu, kterou má chytat — vrátit prázdno je totiž nejlevnější způsob,
jak nemít chybu.

Filtrování, kvůli kterému severity existuje, tím neztrácíš:

```python
souhrn["by_method"]["field.build_field"]["error"]   # kolikrát to selhalo
souhrn["malformed"]                                  # kolik záznamů je vadných
```

a v kukátku na `:42101` je na to tlačítko **jen vadné**.

### Kam tedy patří „varování"

Není pátá hodnota, a je to záměr. Případy, které by v klasickém logu byly
`WARNING`, mají v tomhle systému své místo:

| situace | kam patří |
|---|---|
| povedlo se, ale záložní cestou | `result=ok`, a čím se to povedlo, jde do `output` — z toho se počítá **spotřeba signálu** |
| podmínka nesplněna, přeskakuji | `result=skipped` s důvodem v `output` |
| data si odporují | `result=error` — spor se hlásí, nepřepisuje |
| služba nemůže pokračovat | **neloguje se**, ale nenastartuje nebo vrátí `503` |

To poslední je podstatné: `CRITICAL` je v klasickém logování obvykle poslední
věta procesu, který přesto běží dál. Tady takový stav nemá kde vzniknout —
špatná konfigurace shodí start, nedostupná povinná závislost vrátí typovanou
chybu. Zalogovat „kritické" a jet dál je přesně ta tichá chyba, které se
politika brání.

### Kde se filtruje: na logovátku, ne u tebe

**Výchozí chování je posílat všechno.** Když úroveň nenastavíš, `log.debug()`
dorazí do logovátka stejně jako `log.info()` a filtruje se až při výpisu —
v kukátku přepínačem *úroveň* a v souhrnu.

> *Pokud vývojář zapomene nastavit loglevel, tak přijde o data? Asi bychom to
> měli spíš brát vše a filtrovat pak až na endpointu loggeru při výpisu.*

Přesně tak, a bylo to opraveno. Původně měl klient výchozí úroveň `info`
a debug zahazoval u volajícího — kdo úroveň nenastavil, přišel o data, aniž by
se to kdekoli dozvěděl. Je to stejná úvaha jako u špatně tvarovaných záznamů,
které se taky přijímají místo zahazování: **chybějící záznam není nic**,
kdežto uložený jde kdykoli odfiltrovat.

Zahazování u zdroje zůstává jako **vědomé rozhodnutí** pro toho, kdo chce
ušetřit síť a disk:

```python
log = LogClient(component="field", level="info")     # debug nikam nedorazí
log = LogClient(component="field", level="info",
                methods=("signature",))              # …kromě téhle metody
```

Že se něco zahazuje, je vidět:

```python
>>> log.stats()["level"]
'info'
>>> log.stats()["filtered_by_level"]
1
```

Nenulové `filtered_by_level` u klienta, kterému nic nechodí, je odpověď na
otázku „proč se nic neloguje" — a je to jediný důvod, proč to počitadlo
existuje.

### Kdyby to nestačilo

Pátá hodnota je změna výčtu `Result` a schématu, ne nová metoda — a udělám ji rád,
až bude jasné **jaké rozhodnutí by se podle něj dělalo jinak**. Stav, podle
kterého se nikdo nerozhoduje, nikdo nenastavuje konzistentně a za měsíc
znamená u každé komponenty něco jiného.

---

## 3 · Jak zaloguju JSON objekt?

> *Tyhle jsou všechny textové. Pro zalogování JSON bych měl mít `log.json()`.*

Přesně tak, a jmenuje se to tak:

```python
log.json(method="build_field", trace=trace, label="pole po sítku", obj=pole)
```

Je to **druhý druh logu**, ne jiný formát toho prvního. Textový záznam
odpovídá na otázku *co se stalo*; tenhle na otázku *jak vypadala data* —
pole po sítku, koš atomů, matice šablon.

| | `log.info()` / `log.debug()` | `log.json()` |
|---|---|---|
| jednotka | řádek | celý objekt |
| povinné | `result=` | `obj=` |
| proud | `data-persistent/log.jsonl` | `data-persistent/objects/objects.jsonl` |
| kukátko | `:42101` tabulka | `:42102` rozbalitelné stromy |
| souhrn | ano, po stavech | ne, jen počet ve zdraví |

**Nemá `result`**, a je to schválně. Objekt není výsledek volání, je to pohled
na data — otázka „jak to dopadlo" u něj nedává smysl. Když chceš zaznamenat
obojí, jsou to dva záznamy se stejnou stopou:

```python
log.info(method="build_field", trace=trace, result=Result.OK, output={"rows": len(pole)})
log.json(method="build_field", trace=trace, label="pole po sítku", obj=pole)
```

**`label` je jméno v kukátku** — „pole po sítku", „koš věty 4". Bez něj by
šlo poznat jen komponentu a metodu, a to u modulu, který loguje tři různé
struktury, nestačí. Když chybí, použije se jméno metody.

`kind` je volitelné zařazení pro filtrování (`field`, `basket`, `template`);
když chybí, použije se `label`.

**Dvě meze, o kterých se ví.** Objekt přes 256 kB se uloží jako náhled
s poznámkou o původní velikosti; hlubší než 24 úrovní se ořízne značkou
`… hlouběji než max_depth`. Ani jedno není chyba — v záznamu je příznak
`truncated` nebo `depth_limited` a kukátko to označí. Vedlejší užitek:
oříznutí hloubky zvládne i strukturu, která odkazuje sama na sebe.

**Úroveň se ho netýká.** `log.json()` projde i při `level="info"` — objekt
není debug, je to jiný druh logu, ne jiná upovídanost.

---

## 4 · V modulu: `from_config`

V REPL se `endpoint` napíše natvrdo, protože je to jednorázová zkouška.
V modulu se bere z konfigurace, jinak by byla adresa služby v kódu:

```python
from cb_logger import from_config

log = from_config(cfg, component="field")
```

Čte blok `logging` z konfigurace volajícího modulu — endpoint, úroveň,
zúžení na metody, velikost dávky, adresář spoolu. Existuje proto, že by jinak
každý modul opisoval osm parametrů a při první změně by se opisy rozešly.

### Co si zkusit hned

```python
>>> log.stats()
{'component': 'pokus', 'endpoint': 'http://127.0.0.1:42100',
 'available': True, 'queued': 0, 'dropped': 0, 'undelivered': 0,
 'spool': None}
```

`queued` je fronta, `dropped` jsou zahozené při přetečení, `undelivered` ty,
co se nepodařilo doručit ani do spoolu. Rostoucí `dropped` znamená, že systém
loguje rychleji, než logovátko stíhá; rostoucí `undelivered` znamená, že se
nedá zapisovat ani na disk.
