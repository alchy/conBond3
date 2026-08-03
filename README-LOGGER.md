# cb-logger — vývojářské README

Jak z kódu poslat něco do logu. Všechny ukázky jsou spustitelné a ověřené;
zkopíruj a jeď.

Tohle je jen to nejnutnější. Hloubka je v `cb_logger/docs/`:

| soubor | co v něm je |
|---|---|
| `docs/metody.md` | každá metoda: co dělá, proč existuje, na čem závisí |
| `docs/koncepce.md` | proč je logovátko postavené takhle a ne jako `logging` |
| `docs/prirucka.md` | otázky, které padly při stavbě, a pasti |
| `cb_logger/README.md` | rozhraní, porty, prahy, závislosti modulu |

---

## Než začneš

```bash
./cb-logger.py start        # služba musí běžet
./cb-logger.py status       # ověření + porty
```

| adresa | co tam je |
|---|---|
| `http://127.0.0.1:42100` | REST API |
| `http://127.0.0.1:42101` | kukátko na **textový** log |
| `http://127.0.0.1:42102` | kukátko na **JSON objekty** |

Když služba neběží, klient to řekne při vytvoření a **program poběží dál** —
logovátko nikoho neshodí.

---

## Tři druhy zápisu

```python
from cb_logger import LogClient, Result

log = LogClient(component="muj_modul")
```

| metoda | druh | odpovídá na otázku | kde to uvidíš |
|---|---|---|---|
| `log.info()` | text | *co se stalo* na hranici komponenty | `:42101` |
| `log.debug()` | text | *co se děje uvnitř* funkce | `:42101` |
| `log.json()` | objekt | *jak vypadala data* | `:42102` |

Víc metod není. Závažnost se nese v `result`, ne v názvu metody — `warn`
ani `critical` neexistují a proč, je v `docs/prirucka.md` § 2.

**Všechny parametry se pojmenovávají**, `method` nevyjímaje — poziční
argument neexistuje a `log.info("hláška")` skončí `TypeError`.

---

## 1 · `log.info()` — hranice komponenty

Nejkratší možný zápis:

```python
log.info(method="moje_metoda", result=Result.OK)
```

Se vším, co se hodí vyplnit:

```python
log.info(method="build_field", result=Result.OK,
         message="pole postaveno z celého korpusu",
         trace="q-7f3a91",
         input={"sentences": 97, "radius": 2},
         output={"rows": 4213},
         duration_ms=412)
```

V logu:

```json
{"ts": "2026-08-03T07:42:41.952Z", "level": "info", "component": "muj_modul",
 "method": "build_field", "trace": "q-7f3a91", "result": "ok",
 "message": "pole postaveno z celého korpusu",
 "input": {"sentences": 97, "radius": 2}, "output": {"rows": 4213},
 "duration_ms": 412}
```

| parametr | povinný | co do něj patří |
|---|---|---|
| `method` | **ano** | **jméno metody**, ne hláška — počítá se podle něj souhrn |
| `result` | **ano** | jak to dopadlo, viz výčet níž |
| `message` | ne | volný text pro člověka; v kukátku se čte jako první |
| `trace` | ne | identifikátor jednoho průchodu systémem |
| `input` · `output` | ne | **shrnutí**, ne celá data — počty, klíče, identifikátory |
| `duration_ms` | ne | jak dlouho to trvalo; měříš si sám |
| `version` | ne | verze dat a konfigurace, aby šly porovnat dva běhy |

---

## 2 · `log.debug()` — vnitřek funkce

Táž pole, jiná úroveň. Sem patří mezistavy, kandidáti a zamítnutí — to,
z čeho jde zpětně vysvětlit, jak artefakt vznikl.

```python
log.debug(method="signature", result=Result.EMPTY,
          message="žádný token neprošel sítkem",
          trace="q-7f3a91",
          input={"center": 29, "radius": 2})
```

**Výchozí chování je posílat všechno**, takže o debug nepřijdeš ani když
úroveň nenastavíš. Filtruje se až při výpisu — v kukátku přepínačem *úroveň*.

Chceš-li ušetřit síť a disk, je to vědomé rozhodnutí:

```python
log = LogClient(component="muj_modul", level="info")   # debug nikam nedorazí
log = LogClient(component="muj_modul", level="info",
                methods=("signature",))                # …kromě téhle metody
```

Kolik se zahodilo, řekne `log.stats()["filtered_by_level"]`. Nenulové číslo
u klienta, kterému nic nechodí, je odpověď na otázku „proč se nic neloguje".

---

## 3 · `log.json()` — celý objekt

Když potřebuješ vidět **data**, ne větu o nich. Pole po sítku, koš atomů,
matice šablon — struktury, které se do řádku nevejdou.

```python
log.json(method="build_field", label="pole po sítku", obj={
    "radius": 2,
    "rows": [
        {"tvar": "Soňa",   "lemma": "Soňa",  "upos": "PROPN", "pad": "Nom",
         "deprel": "nsubj", "head": 2, "typ": "osoba"},
        {"tvar": "odjela", "lemma": "odjet", "upos": "VERB",  "pad": None,
         "deprel": "root",  "head": None, "typ": "?"},
        {"tvar": "Prahy",  "lemma": "Praha", "upos": "PROPN", "pad": "Gen",
         "deprel": "obl",   "head": 2, "typ": "misto"},
    ],
})
```

Na `http://127.0.0.1:42102` je z toho rozbalitelný strom.

| parametr | povinný | co do něj patří |
|---|---|---|
| `method` | **ano** | jméno metody, ve které objekt vznikl |
| `obj` | **ano** | cokoli serializovatelného do JSON |
| `label` | ne | jméno v kukátku („pole po sítku", „koš věty 4") |
| `kind` | ne | zařazení pro filtrování; když chybí, použije se `label` |
| `trace` | ne | táž stopa jako u textového záznamu |

**Nemá `result`** — objekt není výsledek volání, je to pohled na data, takže
otázka „jak to dopadlo" u něj nedává smysl. Chceš-li obojí, jsou to dva
záznamy se stejnou stopou:

```python
log.info(method="build_field", trace=trace, result=Result.OK, output={"rows": len(pole)})
log.json(method="build_field", trace=trace, label="pole po sítku", obj=pole)
```

**Dvě meze.** Objekt nad 256 kB se uloží jako náhled, hlubší než 24 úrovní
se ořízne. Ani jedno není chyba — v záznamu je příznak `truncated` nebo
`depth_limited` a kukátko to označí.

---

## Výčet výsledků

Čtyři hodnoty a **žádná další**. Tohle je nejdůležitější rozhodnutí celého
logovátka, protože na něm stojí měření.

```python
from cb_logger import Result

Result.OK        # "ok"
Result.EMPTY     # "empty"
Result.SKIPPED   # "skipped"
Result.ERROR     # "error"
```

| result | kdy | je to chyba? |
|---|---|---|
| `OK` | proběhlo, výsledek je | ne |
| `EMPTY` | proběhlo, výsledek je prázdný | **ne** — platný stav |
| `SKIPPED` | podmínka nesplněna, přeskakuji | ne |
| `ERROR` | nepodařilo se | ano |

### Na příkladech z rozboru vět

```python
# Věta se rozebrala, vznikly atomy.
log.info(method="build_basket", result=Result.OK, trace=trace,
         input={"veta": 4}, output={"atomu": 3})

# Věta se rozebrala, ale žádný atom v ní nebyl. NENÍ to chyba.
log.info(method="build_basket", result=Result.EMPTY, trace=trace,
         message="věta nemá žádný střed",
         input={"veta": 5}, output={"atomu": 0})

# Věta se přeskočila, protože nesplnila podmínku. Důvod musí být vidět.
log.info(method="build_basket", result=Result.SKIPPED, trace=trace,
         message="věta nemá sloveso ani jmenný přísudek",
         input={"veta": 6})

# Parser spadl. Tohle je chyba.
log.info(method="build_basket", result=Result.ERROR, trace=trace,
         message="UDPipe vrátil neplatný CoNLL-U",
         input={"veta": 7})
```

### `EMPTY` není `ERROR`

Věta bez atomu, protože v ní žádný nebyl, je `EMPTY`. Věta bez atomu, protože
spadl parser, je `ERROR`. Podíl `EMPTY` proto **není chybovost** — chybovost je
podíl `ERROR`.

Proč na tom tolik záleží: `docs/koncepce.md` § 2.

---

## Stopa (`trace`)

Drží pohromadě **jeden průchod systémem**. Vyfiltrováním logu podle ní vznikne
celý příběh jedné otázky napříč moduly:

```
trace q-7f3a91
  cb-ingest    receive        ok       1 věta
  cb-udpipe    parse          ok       9 tokenů
  cb-field     build_field    ok       13 řádků
  cb-templates match          empty    žádná šablona nesedí   ← tady to končí
  cb-answer    compose        empty    mlčení
```

* **Razí ji vstupní bod** průchodu. Modul ji nikdy nevyrábí, jen předává dál.
* **Tvar** `<prefix>-<8 hex>`: `q-` dotaz, `b-` dávka, `i-` načtení korpusu,
  `t-` test.
* **Není to `message`.** Volný text patří do `message`.
* **Chybějící stopa není chyba**, ale počítá se jako `without_trace`.

---

## Ukončení

```python
log.close()     # dopraví frontu a zastaví vlákno; vrátí počet neodeslaných
log.flush()     # dopraví frontu, klient běží dál
```

Zápis je asynchronní. **Když na `close()` zapomeneš, o data nepřijdeš** —
klient má pojistku na konec procesu. Při `kill -9` se nespustí; proti tomu je
spool.

---

## Kde klienta vyrobit

**Jednou při startu, ne v každé funkci.** Klient v cyklu znamená kontrolu
služby v cyklu.

Dál se předává parametrem tomu, kdo loguje — ne globálem:

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

V modulu se klient staví z konfigurace, aby adresa služby nebyla v kódu:

```python
from cb_logger import from_config

log = from_config(cfg, component="field")
```

---

## Kontrola, že to funguje

```bash
curl -s http://127.0.0.1:42100/v1/summary          # počty po výsledcích
tail -1 cb_logger/data-persistent/log.jsonl        # poslední textový záznam
tail -1 cb_logger/data-persistent/objects/objects.jsonl
```

Nebo živě v prohlížeči na `:42101` a `:42102`. Obě kukátka posouvají nejnovější
záznam dolů; jakmile odroluješ nahoru, autoscroll se vypne a vpravo dole se
objeví tlačítko zpět.

Stav klienta:

```python
>>> log.stats()
{'component': 'muj_modul', 'endpoint': 'http://127.0.0.1:42100',
 'endpoint_source': 'run/service.port (běžící služba)', 'available': True,
 'level': 'vše', 'queued': 0, 'filtered_by_level': 0, 'dropped': 0,
 'undelivered': 0, 'spool': None}
```

| klíč | co znamená rostoucí číslo |
|---|---|
| `filtered_by_level` | debug se zahazuje u tebe, protože `level="info"` |
| `queued` | logovátko nestíhá nebo neběží |
| `dropped` | fronta přetekla — logujete rychleji, než stíhá odcházet |
| `undelivered` | nedá se zapsat ani do spoolu |

---

## Nejčastější omyly

| omyl | co se stane | jak správně |
|---|---|---|
| hláška do `method` | každá hláška je vlastní řádek souhrnu a měření ztratí smysl | do `method` jméno metody, text do `message` |
| hláška ve `trace` | přestane jít složit jeden průchod z víc modulů | text do `message`, stopa zůstane spojkou |
| `ERROR` místo `EMPTY` | chybovost roste, i když se nic nepokazilo | prázdný výsledek je `EMPTY` |
| celá data v `input` | log naroste tak, že se v něm nedá hledat | shrnutí do `input`, celá data do `log.json()` |
| klient v cyklu | kontrola služby při každém průchodu | jeden klient při startu, předávaný parametrem |
