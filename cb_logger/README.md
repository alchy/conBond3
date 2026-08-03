# cb-logger

Sdílené logovátko systému conBond3. Jediný modul, na který smí importovat
kdokoli (`README-MODULES.md` § 4).

Podrobná dokumentace je v `docs/`; tenhle soubor je rozcestník.

## K čemu je

Sbírá od všech modulů dva druhy záznamů a nabízí je k prohlížení:

| druh | odpovídá na otázku | kukátko |
|---|---|---|
| **textový záznam** | *co se stalo* — komponenta, metoda, result, shrnutí | `:42101` |
| **objektový záznam** | *jak vypadala data* — celý JSON objekt jako strom | `:42102` |

Textový záznam se čte souvisle a zajímá u něj sled; objektový se čte po jednom
a zajímá u něj obsah. Proto dva proudy, dvě kukátka a dva porty.

## Ovládání

```
./cb-logger.py start   [--config PATH] [--foreground]
./cb-logger.py stop    [--timeout SEC]
./cb-logger.py restart
./cb-logger.py reload
./cb-logger.py status  [--json]
```

Návratové kódy: `0` uspěl · `1` selhal · `2` špatné argumenty nebo konfigurace ·
`3` služba neběží.

## Použití z jiného modulu

```python
from cb_logger import LogClient, Result

log = LogClient(component="field", endpoint=cfg["logging"]["endpoint"])

log.info(method="build_field", trace=trace, result=Result.OK,
         message="pole postaveno",
         input={"sentences": 97, "radius": 2},
         output={"rows": 4213}, duration_ms=412)

log.json(method="build_field", trace=trace, label="pole po sítku", obj=pole)

log.close()          # dopraví frontu; volá se explicitně při ukončení
```

Klient se vytváří **jednou při startu** a předává parametrem tomu, kdo loguje.
Klient v cyklu znamená kontrolu služby v cyklu.

## Porty

| port | co |
|---|---|
| 42100 | REST API |
| 42101 | kukátko na textový log |
| 42102 | kukátko na logované objekty |

Rozsah modulu je 42100–42199 (`README-MODULES.md` § 5).

## Rozhraní

| bod | co dělá |
|---|---|
| `GET /version` | verze modulu — **mimo** `/v1/`, viz níže |
| `GET /v1/health` | stav, počty, co je zapnuté |
| `GET /v1/config` | skutečně použitá konfigurace včetně cesty |
| `GET /v1/summary` | počty podle komponenta × metoda × result |
| `POST /v1/records` | `{"records": [ … ]}` — textové záznamy |
| `POST /v1/objects` | `{"objects": [ … ]}` — JSON objekty |
| `POST /v1/summary/reset` | vynuluje souhrn |

`/version` stojí mimo verzování schválně: kdo se ptá na verzi, ještě neví,
kterou verzi rozhraní má volat.

## Čtyři stavy

`ok` · `empty` · `skipped` · `error`

`empty` a `error` se **nesmí slít**. Věta, ze které nevznikl atom, protože
v ní žádný nebyl, je `empty`; věta, ze které nevznikl atom, protože spadl
parser, je `error`. Kdyby obojí bylo „nula atomů", měření by odměnilo právě
tu chybu, kterou má chytat.

## Závislosti

| závislost | povinná? | co při výpadku |
|---|---|---|
| žádná | — | — |

Logovátko samo nezávisí na ničem. **Naopak: pro ostatní moduly je nepovinnou
závislostí** — když neběží, jejich `LogClient` to ohlásí na chybový výstup,
přepne se do spool režimu a nechá je běžet. Kdyby padlé logovátko shodilo
systém, byla by nejméně důležitá součást zároveň nejkřehčí.

## Registr prahů

| id | hodnota | co ovlivňuje | odkud se vzala |
|---|---|---|---|
| `rotate_max_bytes` | 64 MiB | kdy se otočí soubor záznamů | odhad, dosud neměřeno na plném korpusu |
| `retention_days` | 30 | jak dlouho žijí otočené soubory | odhad; upravit, až bude znám denní objem |
| `max_object_bytes` | 256 KiB | strop na jeden logovaný objekt | odhad; pole jedné věty má stovky bajtů, koš jednotky kB |
| `max_depth` | 24 | nejhlubší ukládaná úroveň | odhad; nejhlubší dnešní struktura (koš → atom → sloty → tvar) má 5 |
| `buffer_records` | 200 | kolik posledních drží server pro nové okno | odhad |
| `window_records` | 1000 | strop okna v prohlížeči | odhad |
| `QUEUE_LIMIT` (klient) | 20 000 | kdy klient začne zahazovat nejstarší | odhad |

**Všechny hodnoty jsou zatím odhady, ne měření.** Až přes logovátko poteče
provoz z rozboru korpusu, nahradí se naměřenými čísly s datem a verzí dat
(`README-MODULES.md` § 5).

## Co modul vědomě neřeší

* **Dotazovací rozhraní nad uloženými záznamy.** `GET /v1/records` s filtrem
  podle stopy zatím není — kukátko čte živý proud a starší se hledají v JSONL
  souboru. Přidá se, až bude jasné, jak se ptát.
* **Autentizace.** Služby poslouchají na `127.0.0.1` a systém má jednoho
  lokálního uživatele.
* **Sdružování z víc strojů.** Jeden proces, jeden stroj.
* **Vlastní formát pro velké objemy.** Všechno je JSON a JSONL, dokud měření
  neukáže, že je to úzké hrdlo.

## Testy

```
./run-python -m unittest discover -s cb_logger -t .
```
