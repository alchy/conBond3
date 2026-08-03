# Politika psaní modulů

Závazný předpis pro každý modul systému conBond3. Vznikl při stavbě prvního
modulu (`cb-logger`) a platí zpětně i dopředu: modul, který se od něj odchýlí,
není hotový.

Dokument neříká, **co** který modul dělá — to je věcí jeho vlastního README.
Říká, **jak** modul vypadá zvenčí, aby byl zaměnitelný, měřitelný a vypnutelný.

**Jak dokument číst:** § 0–3 jsou tvar modulu, § 4–7 jeho rozhraní ven,
§ 8–10 jeho chování za provozu, § 11–14 jak se ověřuje, § 15–20 jak se píše
a co ho uzavírá. Kdo zakládá nový modul, začne přílohou A — kontrolním seznamem.

---

## 0 · Z čeho politika plyne

Čtyři zásady zadání a jedna věta z návrhu, ze kterých je odvozeno všechno
ostatní. U každého pravidla dál v dokumentu má být poznat, ze které z nich plyne;
pravidlo, které neplyne z ničeho, do politiky nepatří.

| zásada | důsledek v politice |
|---|---|
| **Žádné monolity.** Komponenta je jednoduchá knihovna dělená podle funkcionality. | § 2 struktura · § 3 veřejné API · § 4 závislosti |
| **Měření je základ hodnocení úspěšnosti.** | § 11 měření · § 15 definice hotového |
| **Postupujeme po malých verifikovatelných kouscích.** | § 15 definice hotového · § 16 pořadí stavby |
| **Explicitní průchod je lepší než implicitní.** | § 3 předávání závislostí · § 5 konfigurace · § 6 logování |

A věta z `README-ARCHITECTURE_OVERVIEW.md` kap. 5, kterou politika **nesmí** porušit:
*jádro je importovatelná knihovna bez závislostí a bez vstupně-výstupní vrstvy;
server, CLI i prohlížeč jsou jen klienti.*

Odtud plyne nejdůležitější rozhodnutí celého dokumentu — § 1.

---

## 1 · Modul má dvě tváře, ne jednu

Zadání říká, že **každá komponenta běží jako služba s REST API**. Návrh říká, že
**jádro nesmí mít vstupně-výstupní vrstvu**. To si neodporuje, pokud se modul
rozdělí na dvě vrstvy, které se nesmějí prolnout:

```
service.py    doménová logika. Čistá funkce nad daty.
              Nezná HTTP, nezná sokety, nezná cesty k souborům.
              Testuje se přímo, bez spuštěné služby.

api.py        REST obálka nad service.py. Rozbalí požadavek, zavolá
              service.py, zabalí odpověď. Žádná logika navíc.
```

Pravidlo, které to drží: **`api.py` nesmí obsahovat jediné rozhodnutí o doméně.**
Když se v `api.py` objeví `if` nad obsahem dat, patří do `service.py`.

Důsledek, kvůli kterému to stojí za tu kázeň: týž modul jde použít dvěma
způsoby, aniž se změní řádek jeho logiky.

```
v procesu:   from cb_field.service import build_field
             pole = build_field(tokens, radius=2)

přes síť:    from cb_field.client import FieldClient
             klient = FieldClient(endpoint="http://127.0.0.1:42300")
             pole = klient.build_field(tokens, radius=2)
```

První cesta je rychlá a použije ji test i dávkové zpracování korpusu. Druhá je
provozní a použije ji jiná služba. **Obě musí vrátit totéž** — to je zkouška
`T-K3` v § 15.

### Import je celé rozhraní. REST nikdo nepíše dvakrát.

Modul nabízí svou funkcionalitu ostatním **importem `cb_<name>`**, a ten import
už REST volání obsahuje. Kdo modul používá, nepíše žádný HTTP kód, nesestavuje
URL a nerozbaluje JSON — zavolá funkci.

```python
import cb_udpipe

parser = cb_udpipe.UdpipeClient(endpoint=cfg["module"]["udpipe_endpoint"],
                                log=log, timeout_s=30)
rozbor = parser.parse(sentences=["Soňa odjela z Prahy."], trace=trace)
```

Za `parse()` je `POST /v1/parse`, ale volající to nemusí vědět. Tohle je smysl
celé služby: **REST se napíše jednou v modulu a nikdo další ho nepíše.**
Kdyby si každý klient skládal požadavky sám, změna kontraktu by se musela
opravit na deseti místech a devět z nich by se našlo za provozu.

Z toho plyne, co musí `client.py` umět, aby se dal takhle používat:

* **Podepsat se stejně jako `service.py`.** Táž jména funkcí, tytéž parametry.
  Rozdíl je jen v konstruktoru, kde se předá `endpoint`.
* **`endpoint` je nepovinný a klient si ho umí najít.** Adresu si deklaruje
  sama služba ve své konfiguraci a při běhu ji zapisuje do `run/service.port`;
  klient čte totéž, co čte `status`. Předaná adresa má vždycky přednost —
  slouží pro mluvení s jinou instancí. Odkud se adresa vzala, musí být vidět
  (`endpoint_source`), jinak se ladí jedna instance a běží druhá.

  ```python
  parser = UdpipeClient()                    # adresu si najde
  parser.endpoint_source                     # 'run/service.port (běžící služba)'
  parser = UdpipeClient(endpoint="http://jiny-stroj:42200")
  parser.endpoint_source                     # 'předáno'
  ```

  *Zapsáno po otázce „proč se píše adresa, když je port v konfiguraci?".
  Povinný `endpoint` znamená, že ho opisuje každý volající — a to je přesně
  ten druh duplikace, kvůli které se dvě místa rozejdou.*
* **Přeložit chyby na výjimky.** `503` od služby je výjimka s typem, ne
  slovník s klíčem `error`, který si volající musí pamatovat zkontrolovat.
* **Rozlišit prázdno od chyby.** Prázdný výsledek je normální návratová hodnota,
  chyba je výjimka. Kdyby obojí bylo `None`, přenese se `INV-9` do každého
  volajícího.

### Wrapper loguje sám

**Klient, který modul nabízí, loguje sám za sebe** — dostane `LogClient`
v konstruktoru a zapisuje každé volání ven: co poslal, co dostal, jak to
dopadlo, jak dlouho to trvalo.

Je to jediné místo, kde je vidět **obě strany hranice**. Služba zaznamená, že ji
někdo volal; klient zaznamená, že volal a co se vrátilo. Když se ty dva pohledy
rozejdou, je chyba mezi nimi — v síti, v serializaci, v timeoutu — a bez záznamu
z obou stran ji nikdo nenajde.

Součástí toho je i `trace`: klient ho dostane parametrem, pošle ho v požadavku
a použije ve svém záznamu. Tím řetěz doložení přejde přes hranici služby
nepřerušený.

Logovátko je z tohohle pravidla jediná výjimka — jeho klient neloguje svá
vlastní volání, jinak by se zacyklil (§ 6).

### Klient se ozve už při vytvoření, ne až při prvním volání

**Když se modul naimportuje a jeho služba neběží, pozná se to v okamžiku
vytvoření klienta** — ne za deset minut uprostřed zpracování korpusu.

Konstruktor klienta se proto zeptá služby na `GET /version` (§ 7) s krátkým
timeoutem a podle výsledku udělá jedno ze tří:

| situace | co se stane |
|---|---|
| služba odpoví | zaloguje se `result=ok` s verzí služby; klient je připravený |
| služba neodpoví | zaloguje se `result=error` s důvodem a **vyhodí se `ServiceUnavailable`** |
| služba odpoví, ale neumí požadovanou verzi rozhraní | zaloguje se `result=error` a vyhodí se `IncompatibleApi` |

```python
import cb_udpipe

# Tady, ne až u parse(), se ukáže, že služba neběží.
parser = cb_udpipe.UdpipeClient(endpoint="http://127.0.0.1:42200",
                                log=log, timeout_s=30)
```

```
cb_udpipe.ServiceUnavailable: modul cb-udpipe neodpovídá na
http://127.0.0.1:42200/version (spojení odmítnuto po 2.0 s).
Spusť ho: ./cb-udpipe.py start
```

Chybová hláška má povinně tři věci: **který modul**, **na jaké adrese** ho
klient hledal a **čím ho spustit**. Bez toho třetího si každý musí pamatovat
jméno ovládacího programu, a to je přesně ta drobnost, kvůli které se místo
spuštění služby hodinu hledá chyba v kódu.

Proč to stojí za jedno volání navíc při každém vytvoření klienta: **klient
vytvořený nad neběžící službou je tikající chyba.** Kdyby se výpadek ukázal až
u prvního `parse()`, spadne to uprostřed dávky, po hodině počítání a s polovinou
zapsaných výsledků. Jedno volání `GET /version` stojí jednotky milisekund
a `/version` je schválně bod bez závislostí, který odpoví, i když je služba
jinak nezdravá.

Z toho plyne, kde se klient vytváří: **jednou při startu**, ne v každé funkci.
Klient v cyklu znamená kontrolu služby v cyklu.

### Výjimka: logovátko nesmí shodit nikoho

`LogClient` se chová jinak, protože logovátko je **nepovinná závislost** (§ 4).
Když neběží, nevyhodí se nic — klient to ohlásí a pokračuje:

* napíše hlášku na chybový výstup ve stejném tvaru jako výše, včetně
  `./cb-logger.py start`,
* přepne se do spool režimu a záznamy ukládá na disk (§ 6),
* dál zkouší službu na pozadí a po jejím návratu spool odešle.

Rozdíl je záměrný a plyne z § 9: **nedostupné logovátko znamená degradaci,
nedostupná povinná závislost znamená typovanou chybu.** Kdyby padlé logovátko
shodilo celý systém, byla by nejméně důležitá součást zároveň nejkřehčí.

Který klient je v které kategorii, stojí v `README.md` modulu jako seznam
povinných a nepovinných závislostí (`K-7`).

---

## 2 · Struktura modulu

Každý modul je adresář `cb_<name>/` v kořeni projektu a obsahuje přesně tyhle
soubory. Chybějící soubor není zjednodušení, je to nehotový modul.

Ovládací program leží v **kořeni projektu**, aby šel spustit rovnou
(`./cb-logger.py status`). Všechno ostatní je v podadresáři modulu.

```
cb-<name>.py                  ovládací program v kořeni — tenký spouštěč do control.py
README-<NAME>.md              vývojářské README — jak modul volat z kódu

cb_<name>/
    cb-<name>-config.json     konfigurace modulu — první soubor v adresáři
    config.schema.json        schéma konfigurace — validuje se při startu
    config.py                 načtení a validace konfigurace

    __init__.py               veřejné API modulu — jen to, co smí ven (§ 3)
    service.py                doménová logika, bez HTTP a bez cest
    api.py                    REST vrstva nad service.py
    client.py                 klient pro ostatní moduly (volá REST)
    control.py                start · stop · restart · reload · status

    data-persistent/          perzistentní data modulu — co přežije restart
    run/                      běhový stav — PID, port, rozdělaná fronta
    scripts/                  pořizovací skripty pro velká data (§ 19)
    docs/
        koncepce.md           proč je modul postavený takhle a ne jinak
        metody.md             každá metoda: co dělá, proč existuje, na čem visí
        prirucka.md           otázky, které padly při stavbě, a pasti
    tests/
        data/                 zmražená testovací data
        test_service.py       logika bez služby
        test_api.py           REST kontrakt
        test_control.py       pět příkazů řízení
        test_parity.py        v procesu == přes síť  (T-K3)
    README.md                 co modul dělá, proč tak, a co vědomě neřeší
```

Konfigurace stojí v adresáři jako první schválně: je to první věc, kterou modul
při startu čte, a první věc, kterou má člověk otevřít, když chce vědět, co modul
umí. Modul si nese svou konfiguraci s sebou — zkopírovat adresář znamená
zkopírovat i nastavení.

### Tři dokumenty, tři čtenáři

| soubor | pro koho | co v něm je |
|---|---|---|
| `README-<NAME>.md` v kořeni | **vývojář, který modul volá** | ukázky použití, výčty hodnot, nejčastější omyly |
| `cb_<name>/README.md` | kdo modul udržuje | rozhraní, porty, prahy, závislosti, co modul neřeší |
| `cb_<name>/docs/` | kdo se ptá proč | návrhová rozhodnutí, naměřená čísla, příručka |

Adresář `docs/` má **pevnou trojici souborů**, aby se hledalo v každém modulu
stejně: `koncepce.md` (proč je modul postavený takhle a ne jinak — u každého
rozhodnutí, z čeho plyne), `metody.md` (každá veřejná metoda: co dělá, proč
existuje, na čem visí) a `prirucka.md` (otázky, které padly při stavbě, a pasti,
do kterých se dá spadnout). Modul smí přidat další soubor; tyhle tři vynechat
nesmí.

Vývojářské README stojí **v kořeni** schválně: kdo modul jen používá, nemá
důvod chodit do jeho adresáře, a `ls` v kořeni mu ukáže, co všechno jde volat.
Jméno nese modul, protože v kořeni bydlí vedle sebe.

**Každá ukázka v něm musí být spustitelná.** Ukázka, která se rozejde s kódem,
je horší než žádná — vývojář ji zkopíruje, ono to spadne, a příště tomu
souboru nevěří.

### Data si drží každý modul sám

**Perzistentní data modulu leží v `cb_<name>/data-persistent/`.** Žádný sdílený
datový adresář, žádné psaní do cizího modulu. Logger tam má své záznamy, UDPipe
tam bude mít svůj model, pole tam bude mít svá pole.

```
cb_logger/data-persistent/    záznamy logu, souhrny
cb_udpipe/data-persistent/    model, mezipaměť rozborů
cb_<name>/data-persistent/    … stejná konvence u každého modulu
```

Vedle toho `cb_<name>/run/` na běhový stav, který restart **nemá** přežít:
PID, skutečný port, rozdělaná fronta. Rozdíl je záměrný a používá ho `T-K4`:
smazání `run/` musí být neškodné, smazání `data-persistent/` je ztráta dat.

Proč to není jeden sdílený `data/` v kořeni: modul, který píše jen k sobě, jde
zkopírovat, zazálohovat i smazat jako celek, a při hledání chyby je hned vidět,
čí data to jsou. *(V conBond2 byl sdílený `data/` s devíti podadresáři a nešlo
z něj poznat, který kód který soubor vlastní.)*

### Pomlčka se spouští, podtržítko se importuje

Python neumí naimportovat balík, jehož adresář obsahuje pomlčku — `import
cb-logger` je syntaktická chyba. Odtud pravidlo, které platí bez výjimky:

| tvar | co to je | příklad |
|---|---|---|
| `cb-<name>` s **pomlčkou** | co se spouští a nastavuje | `cb-logger.py`, `cb-logger-config.json` |
| `cb_<name>` s **podtržítkem** | co se importuje | `cb_logger/`, `import cb_logger` |

Rozdíl jednoho znaku má i druhý užitek: ovládací program `cb-logger.py`
a balík `cb_logger/` se nemohou srazit ve jméně, což by se u dvou stejně
pojmenovaných věcí v jednom adresáři stalo.

Větší modul smí `service.py` rozdělit na víc souborů (`service/` jako balík).
Ostatní soubory zůstávají po jednom — jsou to rozhraní, a rozhraní má být
na jednom místě.

**Kdy soubor rozdělit:** když přestane jít přečíst najednou. Velký soubor je
signál, že modul dělá víc věcí, a pak je odpověď obvykle nový modul, ne nový
soubor.

---

## 3 · Veřejné API a předávání závislostí

`__init__.py` je jediné místo, kterým se z modulu leze ven. Co v něm není,
je vnitřek a smí se kdykoli změnit.

```python
# cb_logger/__init__.py
"""Sdílené logovátko. Ostatní moduly z něj berou LogClient a Result."""

from cb_logger.client import LogClient
from cb_logger.record import Result, Level

#: Verze modulu; roste s každou změnou chování. Čte ji `GET /version`.
__version__ = "0.1.0"
#: Verze rozhraní, které služba obsluhuje. Při přechodu na v2 tu chvíli stojí obě.
__api__ = ["v1"]

__all__ = ["LogClient", "Result", "Level", "__version__", "__api__"]
```

**`__version__` a `__api__` žijí v `__init__.py`, ne v konfiguraci.** Verze
popisuje kód, a kdyby stála v konfiguraci, rozešla by se s ním při první
úpravě — přesně ta tichá vada, kterou § 14 loví.

### Explicitní průchod

**Závislost se předává parametrem. Nikdy se nebere z globálu, z modulového
stavu ani z prostředí uvnitř funkce.** Toto pravidlo je v zadání i v návrhu
(kap. 5, „žádné globální stavy") a je to nejčastěji porušovaná zásada, protože
implicitní cesta je vždycky kratší na napsání a dražší na dohledání.

```python
# ANO — vidím ze signatury, co funkce potřebuje
def build_field(tokens, radius, log, trace):
    log.info(method="build_field", trace=trace,
             input={"tokens": len(tokens), "radius": radius},
             output={"rows": len(rows)}, result=Result.OK)
    return rows

# NE — logger z globálu, stopa z contextvars, poloměr z konstanty
def build_field(tokens):
    LOG.info(...)              # odkud LOG je?
    trace = current_trace()    # kdo ho tam dal?
    radius = RADIUS            # a kdo tohle změní pro test?
```

Co z toho konkrétně plyne:

* **Logger se předává.** Žádný `logging.getLogger()`, žádná modulová proměnná.
  Kdo loguje, dostal klienta v parametru nebo v konstruktoru své třídy.
* **Stopa se předává.** `trace` je normální parametr, který prochází voláním.
  Žádné `contextvars`, žádné thread-local. Když stopa v signatuře chybí, je
  vidět, že tudy řetěz nevede — a to je informace, ne nepohodlí.
* **Konfigurace se předává.** Funkce dostane hodnotu, ne cestu k souboru
  a ne objekt `Config`, ze kterého si ji vytáhne sama.
* **Adresa služby se předává.** Klient dostane `endpoint` v konstruktoru.
  Žádné hledání služby za běhu.
* **Čas a náhoda se předávají.** Funkce, která si sama zavolá `time.time()`
  nebo `random`, nejde deterministicky otestovat. Kdo je potřebuje, dostane je
  parametrem.

Cena je delší signatura. Zisk je, že u každé funkce jde z hlavičky přečíst,
co ovlivňuje její chování — a přesně to je podmínka, aby šla změřit.

---

## 4 · Závislosti mezi moduly

Bez tohoto pravidla se z komponent stane monolit rozházený do adresářů.

### Modul zná jiný modul jen zvenčí

```python
# ANO — přes veřejné API a klienta
from cb_udpipe import UdpipeClient
parser = UdpipeClient(endpoint=cfg["module"]["udpipe_endpoint"])

# NE — sáhnutí do vnitřku cizího modulu
from cb_udpipe.service import _parse_conllu_block
from cb_udpipe.api import HANDLERS
```

Import z cizího modulu smí mířit **jen na jména z jeho `__init__.py`**. Co
v `__init__.py` není, neexistuje. Sáhnutí dovnitř obchází šev a ten pak přestane
být šev — nejde vyměnit implementace za ním, protože někdo spoléhá na vnitřek.

### Sdílené moduly

Sdílený modul je ten, na který smí importovat kdokoli. **Seznam je konečný
a je tady:**

| modul | co poskytuje | smí importovat |
|---|---|---|
| `cb-logger` | `LogClient`, `Result`, `Level` | kdokoli |

Rozšíření seznamu je změna téhle politiky, ne rozhodnutí jednoho modulu.
Sdílený modul má tvrdší povinnost: **nesmí importovat nic z nesdílených modulů**,
jinak vznikne cyklus.

### Zákaz cyklů

Modul A závisí na B, nebo B na A. Nikdy obojí. Cyklus se pozná testem, který
přečte importy z AST a spadne na hraně mířící proti směru. *(Levnější než
fyzické rozdělení do balíčků a zajistí totéž; balíčky mohou přijít kdykoli
potom.)*

Když se cyklus objeví, je to skoro vždy signál, že společná část patří do
třetího modulu, ne že se má povolit výjimka.

### Volání jiné služby

Adresa cizí služby je v konfiguraci volajícího, ne v kódu a ne v konfiguraci
volaného. Modul se nikoho neptá, kde služba běží — dostal to v nastavení (§ 3).

**Povinná a nepovinná závislost se rozlišují.** Nepovinná (logger) při výpadku
znamená degradaci, povinná (parser pro rozbor) typovanou chybu — viz § 9.
Které jsou které, stojí v README modulu.

---

## 5 · Konfigurace

Jeden soubor na modul, jméno podle konvence, uvnitř adresáře modulu:

```
cb_<name>/cb-<name>-config.json
```

Čtyři pravidla, všechna čtyři zapsaná po chybě:

1. **Žádná cesta ani práh v kódu.** Všechno z konfigurace. *(conBond2 na to
   doplatil: testy měřily proti pracovní kopii a tvrdily čísla z jiných dat.)*
2. **Validuje se při startu, ne při prvním použití.** Neznámý klíč je chyba,
   ne tiché ignorování. Chybějící povinný klíč je chyba. Služba, která
   nastartovala se špatnou konfigurací, je horší než služba, která nenastartovala.
3. **Cesta ke konfiguraci je explicitní.** `--config PATH`, nebo výchozí
   `cb_<name>/cb-<name>-config.json` vůči kořeni repozitáře. **Skutečně použitá
   cesta se vypíše při startu a zaloguje** — jinak nikdo nezjistí, které
   nastavení vlastně běží.
4. **Vypnutá funkcionalita je vidět v odpovědi i v logu.** Systém s vypnutou
   částí není tentýž systém a měření to musí vědět.

### Povinné klíče

Každý konfigurační soubor má tenhle základ; modul si přidává vlastní klíče
pod `module`.

```json
{
  "config_version": 1,
  "service": {
    "host": "127.0.0.1",
    "port": 42100,
    "workers": 4,
    "request_timeout_s": 30,
    "max_request_bytes": 4194304
  },
  "logging": {
    "endpoint": "http://127.0.0.1:42100",
    "level": "info",
    "batch_size": 200,
    "flush_interval_ms": 500,
    "spool_dir": "run/log-spool",
    "payload": "summary",
    "methods": []
  },
  "runtime": {
    "pid_file": "run/service.pid",
    "port_file": "run/service.port",
    "stop_timeout_s": 20
  },
  "module": {
  }
}
```

`config.schema.json` popisuje tenhle tvar včetně typů, rozsahů a povinnosti.
Validace proti němu běží ve `config.py` při startu a v testu.

### Rozsahy portů

**Každý modul dostane celou stovku.** Základní port je celá stovka a je to ten,
na kterém poslouchá REST API. Potřebuje-li modul portů víc, bere si je ze svého
rozsahu vzestupně — nikdy z cizího.

| modul | rozsah | základní port | další porty |
|---|---|---|---|
| `cb-logger` | 42100–42199 | **42100** REST API | 42101 kukátko na text · 42102 kukátko na objekty |
| `cb-udpipe` | 42200–42299 | **42200** REST API | 42201 vlastní instance UDPipe |
| `cb-field` | 42300–42399 | **42300** REST API | — |
| *volné* | 42400–42499 | 42400 | |

Rezerva se hodila hned u prvního modulu, a hned dvakrát: `cb-logger` potřebuje
vedle REST API listener pro kukátko na textový log a **další** pro kukátko na
logované JSON objekty. Kdyby měl přidělené jedno číslo, sáhl by po prvním
volném — a to by bylo cizí.

Tahle tabulka je **jediný zdroj pravdy o portech** a doplňuje se ve chvíli, kdy
modul vzniká — ne až když se dva moduly poperou o totéž číslo. Skutečná hodnota
žije v konfiguraci modulu (`service.port`); tabulka říká, která hodnota tam má
být.

Proč stovka a ne jedno číslo: modul, který dnes potřebuje jeden port, jich za
půl roku potřebuje tři (vlastní instance cizího nástroje, druhý listener pro
metriky, ladicí kanál). Když má rezervu, přidá si port doma. Když ji nemá, sáhne
na první volné číslo — a to bude cizí.

Rozsah 42100+ je zvolený tak, aby nekolidoval s ničím zavedeným ani
s předchozími projekty (conBond2 drží 9000 a 9010).

**Port `0` znamená „přidělí systém"** a používají ho testy, aby neobsazovaly
pevná čísla. Skutečně přidělený port si služba zapíše do `run/service.port`
(§ 12), odkud ho test i `status` přečtou.

Relativní cesty se počítají **vůči adresáři modulu**, ne vůči pracovnímu
adresáři procesu. Jinak by se chování měnilo podle toho, odkud se služba spustí,
a to je chyba, kterou nikdo nehledá na správném místě.

### Registr prahů

Práh, který ovlivňuje chování systému, nesmí být holé číslo. Žije v konfiguraci
pod `module` a v `README.md` modulu má záznam:

```
id · hodnota · co ovlivňuje · datum měření · verze dat · číslo, ze kterého vzešel
```

Práh bez zdůvodnění je magické číslo; se zdůvodněním je to záznam měření. Změna
prahu je změna konfigurace se zápisem, ne editace řádku. Prahy se **neohýbají
po měření** — když vyjde 16 dokladů proti prahu 20, pravidlo se nepřijme.

---

## 6 · Logování

Logovátko je sdílený modul. Každý ostatní modul do něj loguje přes klienta,
kterého dostane importem a předá dál parametrem (§ 3).

### Záznam

Čtyři pole jsou povinná ze zadání — komponenta, metoda, vstup-výstup, stav.
Zbytek je nutný k tomu, aby se z logu dal složit jeden průchod.

```json
{
  "ts": "2026-08-03T14:22:41.183Z",
  "level": "info",
  "component": "field",
  "method": "build_field",
  "trace": "q-7f3a91",
  "input":  {"sentences": 97, "radius": 2},
  "output": {"rows": 4213, "templates": 0},
  "result": "ok",
  "duration_ms": 412,
  "version": {"config": "a91f3e", "data": "cs_all-ud-2.17-251125"}
}
```

| pole | proč tam je |
|---|---|
| `component` | která komponenta se volala — ze zadání |
| `method` | která metoda — ze zadání |
| `input` · `output` | s jakým vstupem a s jakým výsledkem — ze zadání |
| `result` | jak to dopadlo — ze zadání, typovaný výčet níže |
| `trace` | identifikátor průchodu; bez něj nejde z logu složit jeden dotaz |
| `level` | `info` nebo `debug` — dvě úrovně, viz níže |
| `ts` · `duration_ms` | kdy a jak dlouho; `duration_ms` živí metriku doby odpovědi |
| `version` | verze konfigurace a dat; bez ní se nedají porovnat dva běhy |

### Stopa (`trace`): co to je a co řeší

**Problém.** Odpověď na jednu otázku projde sedmi moduly a v každém udělá desítky
záznamů. Do jednoho proudu přitom zapisují všechny komponenty naráz a služba je
vícevláknová, takže se záznamy z různých otázek prokládají. Bez společného
identifikátoru je log **posloupnost vět bez odstavců** — jde přečíst, ale nejde
z něj složit, co se dělo při té jedné otázce, na kterou systém odpověděl špatně.

A přesně to je nejčastější úloha: *„proč systém na otázku Kde byl Jan uvězněn?
odpověděl Praha?"* Odpověď leží v tom, co udělal `cb-field` s okny, co
`cb-templates` se šablonami a co `cb-inference` s kandidáty — ve třech modulech,
třech vláknech a stovkách cizích záznamů mezi tím.

**Řešení.** `trace` je identifikátor **jednoho průchodu systémem**, který se razí
na začátku a předává se všude beze změny. Vyfiltrováním logu podle něj vznikne
celý příběh jedné otázky, v pořadí a napříč moduly.

```
trace q-7f3a91
  cb-ingest    receive        ok       1 věta
  cb-udpipe    parse          ok       9 tokenů
  cb-field     build_field    ok       13 řádků
  cb-templates match          empty    žádná šablona nesedí   ← tady to končí
  cb-answer    compose        empty    mlčení
```

**Co stopa není.** Není to identifikátor relace — rozhovor žije déle a obsahuje
mnoho průchodů. Není to ani identifikátor HTTP požadavku — jeden průchod jich
udělá několik, jak přechází mezi službami. Je to jedna otázka, jedna dávka,
jedno načtení korpusu.

**Kdo ji razí.** Vstupní bod, který průchod začíná: obsluha dotazu na serveru,
příkaz v CLI, dávkový skript. **Modul stopu nikdy nevyrábí** — jen ji přebírá
a předává dál. Kdyby si ji razil každý modul, rozpadne se řetěz na tolik kusů,
kolik je modulů, a je to horší než žádná stopa, protože to vypadá, že funguje.

**Tvar.** `<prefix>-<8 hex>`, kde prefix říká druh průchodu:

| prefix | druh průchodu |
|---|---|
| `q-` | dotaz uživatele | 
| `b-` | dávkové zpracování |
| `i-` | načtení a rozbor korpusu |
| `t-` | běh testu |

Osm hexadecimálních znaků dá dost prostoru na to, aby se dvě stopy nepotkaly,
a je to pořád krátké na to, aby se dalo přečíst a opsat. Prefix je tam proto,
aby šlo jedním pohledem odlišit průchod z dotazu od průchodu z dávky, aniž se
musí dohledávat, odkud stopa vznikla.

**Jak se předává.** Explicitně (§ 3) — parametrem funkce uvnitř procesu, klíčem
v těle požadavku přes REST (§ 7). Žádné `contextvars`, žádné hlavičky, které se
někde po cestě ztratí.

**Když chybí.** Záznam bez stopy se uloží s `trace: null` a počítá se
v `/v1/summary`. Není to chyba, ale je to měřitelná díra v řetězu: rostoucí podíl
záznamů bez stopy znamená, že někde v systému někdo přestal parametr předávat.

**Co vědomě neděláme.** Žádné vnořené úseky (span), žádný strom volání, žádné
rodičovské identifikátory. Plochý seznam záznamů se společnou stopou stačí na
všechno, co dnes potřebujeme, a je čitelný bez nástroje. Až přestane stačit,
přibude pole `parent`, ne nový systém.

### Výsledek je typovaný výčet, ne text

Tohle je nejdůležitější rozhodnutí celého logovátka. „Nemá hodnotu"
a „nepodařilo se získat" vypadají v logu stejně, pokud se nerozliší typem —
a je to nejnebezpečnější záměna v celém systému (`INV-9`).

| result | význam | je to chyba? |
|---|---|---|
| `ok` | proběhlo, výsledek je | ne |
| `empty` | proběhlo, výsledek je prázdný | **ne** — platný stav |
| `skipped` | podmínka nesplněna, nese `reason` | ne |
| `error` | nepodařilo se, nese `reason` | ano |

`empty` a `error` se **nesmí** slít. Věta, ze které nevznikl atom, protože v ní
žádný nebyl, je `empty`. Věta, ze které nevznikl atom, protože spadl parser, je
`error`. Kdyby obojí bylo „nula atomů", měření by odměnilo právě tu chybu, kterou
má chytat.

`skipped` s důvodem je požadavek kroku 1 (`S3`): přeskočená věta musí být ve
stopě vidět jako přeskočená s důvodem, ne jako tichá díra.

### Dvě úrovně

| úroveň | co z ní musí být jasné |
|---|---|
| `info` | která komponenta se volala, s jakým vstupem a s jakým výsledkem |
| `debug` | co se děje uvnitř funkcí — mezistavy, kandidáti, zamítnutí |

Úroveň `debug` je schválně rozsáhlá. Každý artefakt musí být zpětně
vysvětlitelný: z jakých řádků vznikl, kterou hranou se naplnil který slot, proč
padl do dané šablony. **Optimalizace, která stopu zneprůhlední, je zakázaná.**

### Verbose se zapíná v konfiguraci modulu

Každý modul má úroveň logování ve **své vlastní** konfiguraci, ne v jedné
společné. Ladí se vždycky jeden modul; zapnout `debug` všem znamená utopit ten
hledaný záznam mezi statisíci cizích.

```json
"logging": {
  "level": "info",          // "info" nebo "debug"
  "payload": "summary",     // "summary" nebo "full" — kolik obsahu do záznamu
  "methods": []             // prázdné = celý modul; jinak jen vyjmenované metody
}
```

* `level: "debug"` zapne podrobnou stopu celého modulu.
* `methods: ["build_field", "signature"]` ji zúží na vyjmenované metody. Zbytek
  modulu zůstane na `info`. Tohle je nejužitečnější režim při hledání chyby
  a zároveň jediný, který jde nechat zapnutý na velkém korpusu.
* `payload: "full"` přidá do záznamu celý vstup a výstup místo shrnutí. Odděleně
  od `level` schválně — často je potřeba vidět víc záznamů, ne delší záznamy.

Úroveň jde změnit i za běhu přes `POST /v1/level` a příkazem `reload`, aby se
kvůli zapnutí ladění nemusela restartovat služba a ztratit tím právě ten stav,
který se hledá. **Změna úrovně se sama zaloguje** — jinak nikdo zpětně nepozná,
proč jsou v jednom úseku záznamy hustší.

Výchozí stav je `info` + `summary`. Modul, který se dodává se zapnutým `debug`,
je nedodělaný.

### Co se do vstupu a výstupu píše

`input` a `output` jsou v úrovni `info` **shrnutí, ne celý obsah**: počty, klíče,
identifikátory. Celý obsah jde do logu jen v úrovni `debug`, a jen když to
konfigurace dovolí (`logging.payload: "full"`).

Důvod je dvojí a oba jsou praktické. Log s celými korpusovými daty naroste tak,
že se v něm nedá hledat, a zároveň se do něj dostane všechno, co bylo ve vstupu —
včetně toho, co tam z korpusu být nemá.

### Volání z kódu

Explicitní, bez dekorátorů a bez magie:

```python
from cb_logger import LogClient, Result

log = LogClient(component="field",
                endpoint=cfg["logging"]["endpoint"],
                level=cfg["logging"]["level"])

log.info(method="build_field", trace=trace,
         input={"sentences": len(sentences), "radius": radius},
         output={"rows": len(rows)},
         result=Result.OK, duration_ms=412)

log.debug(method="signature", trace=trace,
          input={"center": 29}, output=None,
          result=Result.EMPTY)
```

Kdo chce měřit dobu, změří ji sám a předá ji — je to jeden řádek navíc a je
z něj vidět, co se měří.

### Doprava záznamů

Klient **nesmí zdržet ani shodit toho, kdo loguje.** Debug úroveň vyrobí na
plném korpusu statisíce záznamů; synchronní HTTP volání na každý z nich by
udělalo z nejcennější úrovně logu nepoužitelnou.

```
zápis → fronta v paměti → vlákno na pozadí → dávka → POST /v1/records
                                    ↓ služba nedostupná
                       cb_<volající>/run/log-spool/*.jsonl
```

* Dávkuje se po `batch_size` záznamech nebo po `flush_interval_ms`.
* Když je logovátko nedostupné, klient píše do záložního souboru a **pokračuje**.
  Nedostupné logovátko nesmí zastavit systém.
* Návrat do provozu odešle záložní soubor. Neodeslané záznamy se nezahazují.
* Fronta má strop. Při přetečení se **zahazují nejstarší** záznamy a zapíše se
  o tom jeden záznam se `result=error` a počtem zahozených. Tiché přetečení by
  udělalo z logu nespolehlivý zdroj, aniž by to bylo vidět.
* `close()` na klientu dopraví zbytek fronty. Volá se explicitně při ukončení.

### Jeden proud teď, směrování později

Záznamy ze všech komponent jdou zatím **do jednoho proudu**. Je to nejjednodušší
tvar, který funguje, a dokud není naměřeno, že vadí, dělit se nebude.

Logovátko se ale píše tak, aby dělení šlo zapnout konfigurací a ne přepsáním:
zápis prochází **směrovačem**, který ze záznamu vybere cíl. Výchozí pravidlo
posílá všechno do jednoho souboru; přidáním pravidel se proud rozdělí podle
zdroje, aniž se sáhne na kód.

```json
"routing": {
  "default": "data-persistent/log.jsonl",
  "rules": []
}
```

```json
"routing": {
  "default": "data-persistent/log.jsonl",
  "rules": [
    { "component": "field",  "to": "data-persistent/field/log.jsonl" },
    { "level": "debug",      "to": "data-persistent/debug/log.jsonl" },
    { "malformed": true,     "to": "data-persistent/malformed.jsonl" }
  ]
}
```

Pravidla se vyhodnocují shora dolů, první shoda vyhrává, žádná shoda znamená
`default`. Směrovač je čistá funkce záznam → cesta, takže se testuje bez
zapisování (`T-K1`).

Proč to připravit teď, když se to zatím nepoužije: **dělení proudu se dodatečně
zavádí špatně.** Kdyby se zápis psal rovnou do jednoho souboru, přibyl by později
`if` v zapisovači, pak druhý pro úroveň, pak třetí pro velikost — a z toho vzniká
přesně ten druh kódu, který se nedá vyměnit. Směrovač s prázdným seznamem
pravidel stojí pár řádků a je to jediné místo, kde se rozhodne kam.

To není v rozporu s „žádný objekt bez odběratele" (§ 16): odběratel existuje,
je jím výchozí pravidlo. Nestaví se druhá cesta pro budoucnost — staví se jedna
cesta na správném místě.

### Špatně tvarovaný záznam se přijme, ale označí

Když přijde záznam, který neodpovídá schématu — neznámý stav, chybějící
komponenta, nečitelný typ — logovátko ho **nezahodí a nevrátí chybu**. Uloží ho
a viditelně označí:

```json
{
  "ts": "2026-08-03T14:22:41.183Z",
  "component": "field",
  "method": "build_field",
  "result": "hotovo",
  "malformed": true,
  "malformed_reason": "state 'hotovo' není z výčtu ok|empty|skipped|error",
  "raw": { … původní záznam beze změny … }
}
```

Důvod, proč přijmout místo odmítnout: **záznam se posílá právě tehdy, když se
něco děje.** Odmítnout ho znamená přijít o stopu přesně v okamžiku, kdy je
nejcennější — a volající se to stejně nedozví, protože zápis je asynchronní
(§ 6, doprava záznamů). Špatně tvarovaný záznam v logu je informace; chybějící
záznam není nic.

Aby to nebylo tiché svolení k rozpadu výčtu výsledků, platí k tomu tři věci:

* **`malformed` je vidět v `/v1/summary`** jako vlastní počet. Rostoucí číslo je
  chyba ve volajícím a je ji poznat bez čtení logu.
* **Původní záznam se ukládá celý** pod `raw`, aby šlo dohledat, co vlastně
  přišlo.
* **Směrovač na něj smí mít pravidlo** a odklonit ho stranou, takže hlavní proud
  zůstane čistý.

### Sledovací stránka

Logovátko vystavuje na druhém portu (§ 5) **jednoduchou stránku, na které jde
zápis do logu sledovat živě v prohlížeči**. Je to nejlevnější způsob, jak vidět,
čím systém právě prochází, aniž se musí grepovat soubor.

Pravidla, aby z toho nebyl další systém k údržbě:

* **Jedna soběstačná stránka.** Žádný framework, žádné stahování z internetu,
  všechen styl a skript uvnitř. Stránka musí fungovat na stroji bez sítě.
* **Jen čte.** Ze stránky nejde nic zapsat ani smazat. Je to okno, ne ovládání.
* **Živě přes Server-Sent Events.** Prohlížeč drží jedno spojení a záznamy
  přitékají, jak vznikají. Bez websocketů — SSE je obyčejné HTTP a zvládne ho
  standardní knihovna.
* **Filtrování v prohlížeči**, ne na serveru: podle komponenty, úrovně, stavu
  a stopy. Server posílá vše, stránka schovává. Dokud je to jeden proud, je to
  levnější než dotazovací rozhraní — a to zatím nestavíme.
* **`malformed` a `error` jsou vidět na první pohled.** Když se v proudu objeví
  špatně tvarovaný záznam, nemá zapadnout mezi ostatní.
* **Okno má strop, a je v konfiguraci.** Dvě různá čísla, která se snadno
  slijí: `buffer_records` je kolik posledních záznamů drží **server**, aby nově
  připojený prohlížeč nezačínal u prázdna; `window_records` je kolik jich drží
  **okno v prohlížeči**, než začne odsouvat nejstarší. Bez druhého stropu by
  stránka nechaná otevřená přes noc narostla o statisíce řádků a prohlížeč by
  se zadrhl — zrovna ve chvíli, kdy se něco děje a člověk se na ni dívá.
* **Vypnutelná konfigurací.** Na stroji bez displeje je to zbytečný port; když
  se vypne, musí to být vidět v `GET /v1/health` (§ 5, vypnutá funkcionalita).

Stránka je zákazník logovátka, ne jeho součást — čte tentýž proud jako kdokoli
jiný a nemá vlastní cestu k datům. Kdyby sahala do souborů přímo, nešla by
vypnout a rozešla by se s tím, co vidí ostatní.

### Souhrn přežije restart

`/v1/summary` se průběžně ukládá do `data-persistent/` a po startu se načte.
Čísla, která mizí při každém restartu, se nedají použít k hodnocení systému —
a „měření je základ hodnocení úspěšnosti" je zásada, ne přání.

Souhrn nese od kdy se počítá a jde vynulovat explicitním voláním; samo se
nevynuluje nikdy.

### Logovátko neloguje samo do sebe

Jediná výjimka z celé politiky. Logovátko by se zacyklilo, proto své vlastní
provozní události píše do prostého souboru `cb_logger/run/self.log` s rotací
podle velikosti. Tenhle soubor je jediné místo v systému, kde se loguje jinak.

---

## 7 · REST kontrakt

Cesta je verzovaná: `/v1/…`. Nekompatibilní změna je nová verze, ne tichá úprava.

### Povinné body každé služby

| bod | co dělá |
|---|---|
| `GET /version` | verze modulu — **neverzovaná cesta**, viz níže |
| `GET /v1/health` | stav závislostí, načtená data, poslední chyba — z tohohle odpovídá `status` |
| `GET /v1/config` | skutečně použitá konfigurace včetně cesty, ze které se načetla |
| `GET /v1/summary` | počty podle metoda × result — základ měření (§ 11) |

Vlastní body modulu jdou vedle nich.

### `/version` stojí mimo verzování schválně

Je to jediná cesta bez `/v1/` prefixu, a je to záměr: **kdo se ptá na verzi,
ještě neví, kterou verzi rozhraní má volat.** Kdyby `/version` žilo pod `/v1/`,
klient by musel znát verzi, aby zjistil verzi.

```json
GET /version
{
  "module": "cb-logger",
  "version": "0.1.0",
  "api": ["v1"],
  "config_version": 1,
  "python": "3.11.15"
}
```

| klíč | k čemu je |
|---|---|
| `module` | jméno modulu tak, jak se jmenuje jeho ovládací program |
| `version` | verze modulu; roste s každou změnou chování |
| `api` | které verze rozhraní služba **právě obsluhuje**; při přechodu na `v2` tu chvíli stojí obě |
| `config_version` | verze schématu konfigurace (§ 14) |
| `python` | interpret, na kterém služba běží — jedno `.venv` má být všude stejné a tohle to ověří |

`/version` musí odpovědět i tehdy, když je služba jinak nezdravá — nemá žádné
závislosti a nesahá na data. Je to nejlevnější zkouška, že proces vůbec žije,
a `control.py` ji používá jako první krok po `start`, ještě před `/v1/health`.

### Pravidla

* **Vstup i výstup je vždy JSON objekt.** Ne pole, ne holý řetězec, ne číslo —
  objekt se složenými závorkami. Důvod je praktický: do objektu jde přidat klíč,
  aniž se rozbijí stávající klienti, kdežto pole ani skalár rozšířit nejdou.
  Seznam se tedy posílá jako `{"records": [...]}`, ne jako `[...]`.

  ```json
  požadavek   { "sentences": ["Soňa odjela z Prahy."], "radius": 2 }
  odpověď     { "rows": [...], "count": 8 }
  ```

* **Chyba má typ, ne jen text.** Odlišuje se „nemá výsledek" (platný výsledek)
  od „nepodařilo se" (chyba). Je to totéž rozlišení jako `empty` proti `error`
  v logu a je to jediné místo, kde se `INV-9` láme do praxe.

  ```json
  { "error": { "type": "invalid_config", "message": "…", "detail": {…} } }
  ```

* **Prázdný výsledek není chyba.** Vrací se `200` s prázdným obsahem a příznakem,
  ne `404` a ne `500`.
* **Limity jsou součástí kontraktu**, ne překvapení: největší vstup
  (`max_request_bytes`), časový strop na požadavek (`request_timeout_s`).
* **Odpověď je serializovatelná beze ztráty.** Totéž JSON, jaké vrací knihovna
  v procesu.
* **Determinismus.** Táž data a týž požadavek dají tutéž odpověď včetně pořadí
  položek. Při shodě skóre rozhoduje stabilní klíč, ne pořadí v paměti. Bez
  toho se nedá měřit.
* **Stopa prochází sítí.** Volající posílá `trace` v těle požadavku; služba ji
  použije ve všech svých záznamech. Bez toho se řetěz přeruší na každé hranici
  služby a `P8` přestane platit napříč systémem.

### Návratové kódy

| kód | kdy |
|---|---|
| `200` | proběhlo — včetně prázdného výsledku |
| `400` | vstup je špatně (neplatný JSON, chybí klíč, špatný typ) |
| `413` | vstup je nad `max_request_bytes` |
| `500` | chyba na naší straně |
| `503` | nedostupná závislost; tělo říká **která** |

### Čím se REST staví

Standardní knihovna (`http.server.ThreadingHTTPServer`). Žádný framework.
Provozní backend nesmí potřebovat nic mimo standardní knihovnu — těžké knihovny
(TensorFlow, transformers) patří k přípravě dat, ne k běhu služby.

---

## 8 · Souběh a stav

Služba je vícevláknová, takže `service.py` běží současně ve víc vláknech.

* **Bez sdíleného měnitelného stavu.** Funkce v `service.py` pracují nad tím,
  co dostaly parametrem. Modulová proměnná, do které se za běhu zapisuje, je
  chyba — v jednovláknovém testu projde a v provozu se rozpadne.
* **Když stav být musí**, je uzavřený v objektu, který si volající vytvoří, a
  přístup k němu chrání zámek. Dva takové objekty musí jít mít vedle sebe
  v jednom procesu — je to podmínka souběhu i pozdější experimentální vrstvy.
* **Zápis do `data-persistent/` je atomický.** Zapiš do dočasného souboru
  v témže adresáři a přejmenuj (`os.replace`). Přímý zápis do cílového souboru
  po pádu procesu zanechá poloviční JSON, který už nikdo nepřečte.
* **Jeden modul, jedna instance.** `start` na běžící službu ji nespustí podruhé;
  PID soubor je zámek. Dva procesy nad týmž `data-persistent/` je ztráta dat.
* **Práce, která trvá dlouho, se nedělá v obsluze požadavku.** Buď se rozdělí na
  dávky, nebo dostane vlastní bod a vrací průběh. Požadavek, který běží déle než
  `request_timeout_s`, je z pohledu volajícího výpadek.

---

## 9 · Odolnost: chování při chybě

* **Každé volání ven má timeout z konfigurace.** Volání bez timeoutu není
  pomalé, je zamrzlé — a zamrzlá služba se hledá hůř než spadlá.
* **Nedostupnost se pozná při vytvoření klienta, ne při prvním volání** (§ 1).
  Klient nad neběžící službou je tikající chyba; ukáže se uprostřed dávky
  a s polovinou zapsaných výsledků.
* **Opakovat se smí jen idempotentní operace**, s exponenciálním odstupem
  a stropem počtu pokusů, obojí z konfigurace. Opakovaný zápis, který není
  idempotentní, vyrobí data dvakrát.
* **Nepovinná závislost vypadne → degradace.** Nedostupné logovátko znamená
  spool a běh dál (§ 6), ne pád. Že se degraduje, musí být vidět v `/v1/health`.
* **Povinná závislost vypadne → typovaná chyba `503`** s uvedením, která to je.
  Nikdy prázdná odpověď — to by se slilo s platným prázdným výsledkem.
* **`except: pass` je zakázaný.** Každá zachycená výjimka končí záznamem
  `result=error` s důvodem. Tichá chyba je nejhorší druh chyby, protože měření
  ji ukáže jako úspěch.
* **Chyba se nepřepisuje na prázdno a spor se nepřepisuje na výběr.** Když se
  dvě data neshodnou, ohlásí se to; vybrat jedno a jet dál je tichá chyba.
* **Start selže hlasitě.** Špatná konfigurace, nedostupná povinná závislost nebo
  nečitelná data znamenají, že služba nenaběhne a řekne proč. Služba, která
  naběhla napůl, je horší než služba, která nenaběhla.
* **Ukončení je řízené.** `SIGTERM` dokončí rozpracované požadavky do
  `stop_timeout_s`, dopraví frontu logu a teprve pak skončí.

---

## 10 · Bezpečnost

Zatím jeden lokální uživatel, žádná autentizace. Právě proto musí platit:

* **Služby poslouchají na `127.0.0.1`, ne na `0.0.0.0`.** Vystavení do sítě je
  vědomá změna konfigurace, ne výchozí stav. Bez autentizace je otevřený port
  otevřený vstup.
* **Limity jsou obrana, ne kosmetika.** `max_request_bytes` a `request_timeout_s`
  platí i pro volání z vlastního systému; modul, který věří vlastnímu klientovi,
  spadne na první chybě v tom klientovi.
* **Vstup se validuje i od svých.** Cizí modul není důvěryhodnější než síť —
  je to jen jiný zdroj špatných dat.
* **Do logu nejdou tajemství ani celé osobní údaje.** Úroveň `info` nese shrnutí
  (§ 6); celý obsah jen v `debug` a jen když to konfigurace dovolí.
* **Modul nesahá mimo repozitář.** Žádné psaní do domovského adresáře, žádné
  absolutní cesty do systému. Cesty jsou v konfiguraci a míří dovnitř projektu.
* **Do repozitáře nevstupují licencovaná data.** Co se nesmí šířit, se stahuje
  skriptem a je v `.gitignore`.

---

## 11 · Měření

Měření není příloha modulu, je to podmínka jeho přijetí.

* **Měřidlo dřív než schopnost.** Kde měřidlo chybí, staví se dřív než kód.
  *(Zapsáno po chybě: etalon porovnávaný podřetězcem propustil odpověď, která
  jen zopakovala jméno entity a nic neřekla.)*
* **Každý modul vystavuje `GET /v1/summary`** s počty podle metoda × result.
  Rozložení `ok / empty / skipped / error` je nejlevnější zdravotní ukazatel,
  jaký systém má, a plyne z logu zadarmo.
* **Podíl `empty` není chybovost.** U některých modulů je vysoký podíl `empty`
  správný výsledek. Chybovost je podíl `error`.
* **Spotřeba signálu.** Vyrábí-li modul mezivýsledek pro další vrstvu, měří se,
  v kolika procentech ho ta vrstva **opravdu použila** místo záložní cesty.
  Nulová spotřeba je chyba stavby, ne vlastnost dat. *(V conBondu se diskurzní
  rozřešení počítalo a zahazovalo měsíce; uložením téhož mezivýsledku stoupla
  navázatelnost ze 74 % na 81,6 %, aniž se napsal nový algoritmus.)*
* **Každé měřítko má protiváhu.** Ke každému číslu, které jde zlepšit podvodem,
  patří druhé, které se tím podvodem zhorší. Číslo bez protiváhy se neuvádí.
* **Každé číslo nese verzi dat a konfigurace.** Bez toho jsou dvě čísla
  nesrovnatelná.
* **Měří se až po stavbě, na zmražených datech.** Sada, která se přepočítává při
  každém běhu, tiše zmenší sama sebe, když ji chyba připraví o položky — a pak
  pochválí právě tu chybu, kterou má chytat.

---

## 12 · Ovládání služby

Ovládací program je samostatný spustitelný soubor `cb-<name>.py` v kořeni
projektu. Je tenký — zpracuje argumenty a zavolá `control.py` v modulu. Logika
řízení je v modulu, ne ve skriptu; skript v kořeni je jen dveře.

```
./cb-logger.py start   [--config PATH] [--foreground]
./cb-logger.py stop    [--timeout SEC]
./cb-logger.py restart [--config PATH]
./cb-logger.py reload
./cb-logger.py status
```

| příkaz | co musí udělat |
|---|---|
| `start` | ověří konfiguraci **před** spuštěním, spustí službu, zapíše PID, počká na `GET /version` a pak na `GET /v1/health`, a teprve pak ohlásí úspěch |
| `stop` | pošle `SIGTERM`, nechá dokončit rozpracované požadavky do `stop_timeout_s`, pak `SIGKILL`; uklidí PID |
| `restart` | `stop` a `start`; když služba neběžela, chová se jako `start` |
| `reload` | znovu načte konfiguraci a data **bez ztráty stavu**; co znovu načíst nejde (třeba změna portu), řekne to a nechá běžet staré nastavení |
| `status` | odpoví z `GET /v1/health`, ne jen „běží" — a **vždy uvede port** |

### Co musí říct `status`

Nestačí „běží / neběží". `status` je první příkaz, který člověk zavolá, když
něco nefunguje, a musí z něj být poznat, **kam se má připojit** — nebo kam by se
připojil, kdyby služba běžela.

```
$ ./cb-logger.py status
cb-logger    BĚŽÍ     127.0.0.1:42100  pid 64515   od 14:02:11 (3h 20m)
             zdraví   ok
             verze    modul 0.1.0 · konfigurace 1
             záznamy  128 431 (ok 127 902 · empty 502 · skipped 0 · error 27)
             config   cb_logger/cb-logger-config.json
```

```
$ ./cb-logger.py status
cb-logger    NEBĚŽÍ   měl by běžet na 127.0.0.1:42100
             config   cb_logger/cb-logger-config.json
             pozn.    osiřelý run/service.pid (pid 61044 neexistuje)
exit 3
```

Port se u běžící služby bere z `run/service.port` (skutečný, což je podstatné,
když je v konfiguraci `0`), u neběžící z konfigurace jako **zamýšlený**. Uvádí
se vždycky, včetně cesty ke konfiguraci, ze které vyšel — jinak člověk hledá
chybu v běžící službě, zatímco běží s jiným nastavením, než si myslí.

Strojově čitelný tvar téhož vrací `--json`; obsahem je týž objekt jako
`GET /v1/health` plus port, PID a cesta ke konfiguraci.

### Návratové kódy

Ovládání se volá ze skriptů a z testů, takže kódy musí být spolehlivé.

| kód | význam |
|---|---|
| `0` | příkaz uspěl (`status`: služba běží a je zdravá) |
| `1` | příkaz selhal |
| `2` | špatné argumenty nebo neplatná konfigurace |
| `3` | služba neběží (`status`), nebo `stop` na neběžící službu |

### Stavové soubory

```
cb_<name>/run/service.pid     PID běžící služby
cb_<name>/run/service.port    skutečný port, na kterém služba poslouchá
```

`service.port` je tam schválně: když je v konfiguraci port `0`, přidělí ho
systém a jinak by ho nikdo nezjistil. Testy se na něj spoléhají, aby nemusely
obsazovat pevná čísla.

`start` na už běžící službu není chyba — vypíše, že běží, a vrátí `0`.
Osiřelý PID soubor po spadlé službě se pozná (proces s tím PID neexistuje nebo
je to jiný program) a přepíše, ne zamlčí.

### Spuštění na popředí

`--foreground` nechá službu běžet v terminálu bez odpojení. Je to výchozí režim
pro vývoj a pro testy — bez něj se test řízení píše špatně.

---

## 13 · Testování

* **Testy se píšou v `unittest` ze standardní knihovny.** Žádný `pytest`,
  žádná testovací závislost — testovací závislost má tendenci se stát provozní.
* **Spouští se přes `./run-python`, nikdy přímo `python`** (§ 19):

  ```
  ./run-python -m unittest discover                      celý projekt
  ./run-python -m unittest discover -s cb_<name> -t .    jeden modul
  ```

  `./run-python` ověří verzi interpretu, doinstalované závislosti a postaví
  `PYTHONPATH` na kořen projektu. Spuštění systémovým `python` je chyba, která
  se neprojeví hláškou, ale divným výsledkem — proto je to jediná povolená
  cesta.
* **Test nepotřebuje běžící službu**, kromě `test_api.py`, `test_control.py`
  a `test_parity.py`. Ty si službu spustí samy na portu `0` a po sobě ji uklidí.
* **Test si ukazuje na vlastní dočasný adresář.** Nikdy nesahá na provozní
  `data-persistent/`. Cesty jsou v konfiguraci právě proto, aby to šlo (§ 5).
* **Testy jsou deterministické.** Žádná náhoda bez semínka, žádný čas z hodin —
  obojí se předává parametrem (§ 3). Test, který občas selže, se za měsíc
  vypne.
* **Testovací data jsou zmražená v gitu**, v `tests/data/`. Data generovaná při
  běhu testu neřeknou, jestli se změnilo chování, nebo vstup.
* **Regrese.** Jednou opravená chyba dostane trvalý test s odkazem na pravidlo,
  kvůli kterému vznikl.
* **Pojistka proti vakuu.** Test, který hlídá jev spouštěný jen za určitých
  podmínek, musí navíc tvrdit, že se ty podmínky v jeho vzorku opravdu vyskytly.
  Jinak zticha přestane hlídat cokoli a nikdo si toho nevšimne.
* **Pokrytí není cíl.** Cíl jsou čtyři zkoušky `T-K1`–`T-K4` (§ 15). Sto procent
  pokrytí bez `T-K2` je modul, který na prázdný vstup lže.

---

## 14 · Verzování a kompatibilita

Verzuje se to, co může někdo jiný číst: rozhraní, konfigurace, uložená data.

| co | jak |
|---|---|
| **REST** | cesta `/v1/…`. Přidat klíč do objektu smí kdykoli; odebrat nebo přejmenovat znamená `/v2/`. |
| **konfigurace** | `config_version` v souboru. Nekompatibilní změna zvýší číslo a start selže s hláškou, co přenastavit. |
| **uložená data** | každý soubor v `data-persistent/` nese `format_version`. Čtečka umí předchozí verzi, nebo řekne, že neumí — nikdy nehádá. |
| **modul** | `version` na `GET /version` (§ 7), aby šlo poznat, co běželo. |

**Tiché mlčky funkční čtení starých dat je horší než hlasité odmítnutí.** Data
načtená podle špatného předpokladu vyrobí čísla, která vypadají správně.

---

## 15 · Definice hotového modulu

Modul je hotový, teprve když má **všech osm** položek. Sedm z osmi není
sedm osmin hotového modulu, je to nehotový modul.

| id | co |
|---|---|
| `K-1` | `service.py` bez HTTP a bez cest; testuje se přímo |
| `K-2` | `config.schema.json` a validace při startu; neznámý klíč je chyba |
| `K-3` | všech pět příkazů řízení funguje a vrací správné návratové kódy |
| `K-4` | `GET /version`, `/v1/health`, `/v1/config`, `/v1/summary` odpovídají |
| `K-5` | loguje se čtyřmi výsledky; `empty` a `error` se nikde neslévají |
| `K-6` | naměřené číslo na vlastním testbedu, se zapsanou verzí dat a konfigurace |
| `K-7` | `README.md` — co dělá, proč tak, co vědomě neřeší, registr prahů, povinné a nepovinné závislosti |
| `K-8` | čtyři zkoušky `T-K1`–`T-K4` procházejí |

### Čtyři zkoušky každého modulu

| id | zkouška | co ověřuje |
|---|---|---|
| `T-K1` | **UMÍ** | správný vstup → správný výstup |
| `T-K2` | **PŘIZNÁ PRÁZDNO** | vstup bez výsledku → `empty`, ne výmysl a ne `error` |
| `T-K3` | **SHODA TVÁŘÍ** | `service.py` v procesu a `client.py` přes síť dají totéž (§ 1) |
| `T-K4` | **PŘEŽIJE VÝPADEK** | klient nad neběžící službou selže **při vytvoření** typovanou chybou se jménem modulu, adresou a příkazem ke spuštění (§ 1); nepovinná závislost degraduje místo pádu; smazané `run/` je neškodné |

`T-K2` je nejdůležitější a nejčastěji chybí. Modul, který na prázdný vstup
vrátí `error`, rozbije měření všem nad sebou.

---

## 16 · Pořadí stavby modulu

### Nejdřív scaffold, potom funkcionalita

Platí to na dvou úrovních a na obou je to závazné.

**V projektu:** dřív než se postaví první schopnost, stojí kostra — adresáře,
ovládací programy, konfigurace se schématem, logovátko a **jeden průchod
naprázdno**: požadavek dovnitř, prázdná odpověď ven, ale celou cestou. Teprve
do hotové kostry se vkládají vrstvy.

**V modulu:** dřív než `service.py` umí cokoli užitečného, existují všechny
soubory z § 2 a modul jde spustit, zeptat se ho na zdraví a zastavit ho. První
`service.py` smí vracet prázdný výsledek — ale vrací ho správným tvarem, se
správným stavem a se záznamem v logu.

Důvod je zapsaný po chybě: *v obou předchozích projektech vznikly nejhorší vazby
tam, kde se vrstva přidávala do něčeho, co pro ni nemělo místo.* Vrstva vložená
do hotové kostry si musí sednout do připraveného tvaru; vrstva, kolem které se
kostra teprve dostavuje, si tvar ohne k obrazu svému.

Praktický důsledek: **prázdný modul, který projde `T-K1`–`T-K4`, je lepší výchozí
stav než poloviční modul, který umí jednu věc a nejde ovládat.**

### Pořadí uvnitř modulu

Postupujeme po malých verifikovatelných kouscích. U modulu to znamená tohle
pořadí — každý krok končí něčím spustitelným.

```
1. config.schema.json + config.py     →  test: neplatná konfigurace neprojde
2. service.py, nejmenší užitečná část →  test: T-K1 a T-K2 v procesu
3. api.py + version/health/config/summary →  curl vrátí verzi a zdraví
4. control.py + cb-<name>.py          →  start · status · stop v terminálu
5. client.py                          →  test: T-K3 shoda tváří
6. odolnost                           →  test: T-K4 výpadek
7. měření + README                    →  K-6, K-7
```

Kroky 1 a 2 jsou schválně před 3. Modul, který umí odpovídat dřív, než umí
odmítnout špatnou konfiguraci, se ladí přes HTTP místo přes test.

Dvě zásady k pořadí, obě zapsané po chybě:

* **Žádný objekt bez odběratele.** Část modulu se nestaví dopředu „protože bude
  potřeba". Postavená vrstva bez odběratele je složitost bez užitku a nikdo ji
  později netroufne odstranit.
* **Nejdřív roztřídit selhání, potom stavět.** *(Měřeno v conBondu: navrhované
  pořadí schopností se po roztřídění devatenácti chyb obrátilo — plánovač
  víceskokových dotazů neřešil ani jednu, kdežto extrakce dvanáct. Roztřídění
  stálo hodinu a ušetřilo modul.)*

---

## 17 · Jazyk kódu a dokumentace

**Kód je anglicky. Vysvětlivky jsou česky.**

| co | jazyk |
|---|---|
| jména modulů, souborů, tříd, funkcí, proměnných | anglicky |
| klíče v JSON konfiguraci | anglicky |
| pole REST API a hodnoty výčtů | anglicky |
| docstringy | česky |
| komentáře | česky |
| README, README-MODULES.md, chybové hlášky pro člověka | česky |

### Docstring vysvětluje PROČ, ne co

Co kód dělá, je vidět z kódu. Docstring má říct, proč to tak je — a u každého
řezu, prahu a výjimky, po jaké naměřené chybě vznikl. Docstring stojí **pod**
hlavičkou funkce a má čtyři části: proč, vstup, výstup, a co se stane při chybě.

```python
def flush(self, timeout_s: float = 5.0) -> int:
    """Dopraví frontu do logovátka; vrátí počet neodeslaných záznamů.

    Proč vrací počet místo výjimky: volá se při ukončení procesu, kdy už
    výjimka nemá kam bublat. Neodeslané záznamy skončí ve spool souboru
    a odešlou se při dalším startu — ztratit se nesmí, protože debug stopa
    je jediný způsob, jak zpětně vysvětlit, jak artefakt vznikl.

    Vstup:
        timeout_s: kolik sekund čekat na odeslání. Výchozích 5 s vzešlo
            z měření: dávka 200 záznamů na místní smyčce odchází do 40 ms,
            takže 5 s je stonásobná rezerva a zároveň strop, který nezdrží
            ukončení procesu natolik, aby to někdo obešel kill -9.

    Výstup:
        Počet záznamů, které se nepodařilo odeslat a leží ve spool souboru.
        Nula znamená, že fronta je prázdná a spool taky.

    Při chybě:
        Nevyhazuje. Nedostupné logovátko je degradace, ne selhání volajícího
        (§ 9); záznamy zůstanou ve spoolu a vrátí se jejich počet.
    """
```

**Chyba se zapisuje do kódu, ne jen do commitu.** Řez, který vznikl proto, že
systém odpověděl špatně, to musí mít napsané u sebe — jinak ho někdo za půl roku
„zjednoduší".

### Přirozený jazyk v kódu

V jádře nesmí být slovo přirozeného jazyka jako **data** — tázací tvary, role,
spojky, texty odpovědí patří do jazykových profilů v JSON, ne do podmínek
a f-stringů. Anglické identifikátory tomu nevadí; hlídací test hledá slova
ze seznamu v jazykovém profilu, ne „česky vypadající" jména.

---

## 18 · Styl kódu

* **Typové anotace na všem, co je vidět zvenčí.** Veřejné funkce, metody
  a datové typy je mají povinně. Uvnitř funkce podle uvážení.
* **Datové tvary jsou typy, ne slovníky s dohodou.** Záznam logu, stav, výsledek
  — `dataclass` nebo `Enum`. Slovník s domluvenými klíči je typ, o kterém neví
  editor ani test.
* **Funkce dělá jednu věc.** Když se do jejího jména vejde „a", jsou to dvě
  funkce.
* **Žádná funkce bez jasného výstupu.** Funkce, která něco vrátí *a* zároveň
  změní, co dostala, se používá špatně dřív nebo později.
* **Konstanty nahoře souboru** a u každé odkaz, odkud se vzala — do konfigurace
  nebo do registru prahů (§ 5). Číslo uprostřed kódu je magické číslo.
* **Řádek do 88 znaků, odsazení čtyři mezery.** Dlouhý řádek se v recenzi
  nečte.
* **Jednopísmenná jména jen pro indexy** v krátkých cyklech.
* **Podtržítko na začátku znamená vnitřek.** Co je `_takhle`, nesmí nikdo mimo
  soubor volat, a do `__init__.py` to nepatří.

---

## 19 · Prostředí a ukládání

* **Jedno `.venv` pro celý projekt**, Python 3.11. Moduly si nezakládají vlastní.
* **Do prostředí se vstupuje jedině přes `./run-python` v kořeni.** Zaručí
  správný interpret, ověří závislosti proti `requirements.txt` (výsledek si
  cachuje otiskem, takže běžné spuštění nestojí nic navíc) a dá kořen projektu
  na `PYTHONPATH`, aby `import cb_<name>` fungoval odkudkoli. `./run-python`
  bez argumentů vypíše stav prostředí, `--check` vynutí kontrolu závislostí.
* **Ovládací program se sám přepne na projektový interpret.** Shebang
  `#!/usr/bin/env python3` vezme **první** `python3` z PATH, což je systémový
  interpret — a služba by pak běžela na jiné verzi než testy a než měření,
  které se proti ní pouští.

  ```python
  #!/usr/bin/env python3
  import os, sys
  from pathlib import Path

  KOREN = Path(__file__).resolve().parent
  VENV_PYTHON = KOREN / ".venv" / "bin" / "python"

  if VENV_PYTHON.is_file() and \
          Path(sys.executable).resolve() != VENV_PYTHON.resolve():
      os.execv(str(VENV_PYTHON),
               [str(VENV_PYTHON), str(Path(__file__).resolve())] + sys.argv[1:])
  ```

  *Zapsáno po chybě: `./cb-udpipe.py start` zvedl službu na Pythonu 3.14.6,
  zatímco `./run-python` a všechny testy běžely na 3.11.15. Měření se pak
  pouštělo proti něčemu jinému, než se tvrdilo — táž třída vady, na kterou
  doplatil conBond2 u testů měřících proti pracovní kopii.*

  Chybějící `.venv` se nechá být: kód modulů vystačí se standardní knihovnou
  a spustit se má i tam, kde prostředí ještě není postavené.
* **Kód našich modulů vystačí se standardní knihovnou.** `service.py`, `api.py`,
  `client.py` i `control.py` nesmějí potřebovat nic z venv.
* **Vendorované nástroje smějí mít závislosti** a nesou si je do sdíleného
  `.venv`. UDPipe 2 potřebuje TensorFlow a transformers; běží ale jako **vlastní
  proces vedle naší služby**, ne jako import v našem kódu.

Rozdíl je podstatný a snadno se stírá: to, že v `.venv` leží TensorFlow, ještě
neznamená, že si ho smí naimportovat `service.py`. Hranice vede po procesu.
Kdyby ji někdo překročil, přestane platit, že se modul dá spustit a otestovat
bez cizího nástroje — a `T-K3` ztratí smysl.

### Vendorované nástroje

Nástroj, který modul provozuje, žije uvnitř modulu:

```
cb_udpipe/
    vendor/               zdrojáky nástroje, tak jak přišly
    data-persistent/
        models/           váhy a tokenizéry
```

Modul takový nástroj **spouští a hlídá sám** — `cb-udpipe.py start` zvedne
nejdřív nástroj (port z vlastního rozsahu, § 5), počká, až odpoví, a teprve pak
naši službu. `stop` je ukončí v opačném pořadí. Že nástroj neběží, se pozná
v `GET /v1/health` jako nedostupná **povinná** závislost, tedy `503` (§ 9).

### Velká binární data nejsou v gitu, ale je jasný postup, jak je získat

Váhy, modely a jiná velká binární data **do repozitáře nepatří** — git s nimi
neumí zacházet, `diff` na nich nic neřekne a historie by narostla o stovky
megabajtů, které nikdo nikdy nebude potřebovat zpětně.

To ale neznamená „stáhni si to nějak". Modul, který velká data potřebuje, má
tři věci a všechny tři jsou povinné:

1. **Skript, který je pořídí** — `cb_<name>/scripts/fetch-<co>.sh`. Jeden příkaz,
   žádná ruční práce, ověření kontrolního součtu po stažení.
2. **Zápis v `README.md` modulu**: co se stahuje, odkud, jak je to velké, jakou
   to má licenci a čím se to spustí.
3. **Odmítnutí startu, když data chybí.** Služba nenastartuje a řekne, který
   soubor chybí a **který skript ho pořídí**.

```
cb-udpipe: chybí model
  očekáváno:  cb_udpipe/data-persistent/models/cs_all-ud-2.17-251125.model
  pořídíš:    cb_udpipe/scripts/fetch-models.sh
exit 2
```

**Nástroj se nikdy nestahuje za běhu.** Stahování je samostatný krok, který
udělá člověk vědomě, ne vedlejší účinek prvního dotazu. *(V conBond2 si UDPipe
bez tohohle sahal na HuggingFace do `~/.cache` a při prvním spuštění bez sítě
spadl — tedy přesně ta závislost na okolí, které se zbavujeme.)*

Do `.gitignore` patří cesta k datům, ne k celému `data-persistent/` — adresář
sám v repozitáři zůstává s `.gitkeep`, aby po `git clone` existoval.
* **Všechno běží z projektového adresáře.** Modul nesmí sahat mimo repozitář
  ani do domovského adresáře — cesty jsou v konfiguraci a míří dovnitř.

```
conBond3/
    cb-logger.py          ovládání modulu logger
    cb-udpipe.py          ovládání modulu udpipe
    cb-<name>.py          … jeden na modul, všechny v kořeni

    cb_logger/            modul logger
        cb-logger-config.json
        data-persistent/
        run/
        docs/
        tests/
        …
    cb_udpipe/            modul udpipe
    cb_<name>/            … jeden adresář na modul

    .venv/                jediné virtuální prostředí
    README-MODULES.md            tahle politika
```

Kořen projektu tak na první pohled říká, co všechno je služba: každý
`cb-*.py` je jedna a vedle něj stojí její adresář.

### Ukládání

**Cokoli se ukládá, ukládá se zatím jako JSON objekty.** Žádné `pickle`, žádná
databáze, žádný binární formát. Platí to pro konfiguraci, pro logy, pro pole,
šablony, atomy i koše.

Důvody, proč to na začátku stojí za pomalejší čtení velkých souborů:

* **Vidět do dat bez nástroje.** Soubor jde otevřít v editoru a přečíst; při
  hledání chyby je to rozdíl mezi minutou a hodinou.
* **`git diff` něco říká.** Změna v datech je vidět jako změna, ne jako jiný
  binární blob.
* **Není vazba na verzi Pythonu ani na třídy.** `pickle` se rozejde s kódem
  a rozbité `pickle` se čte hůř než rozbité cokoli.

Proudové zápisy (logy, dávky záznamů) se ukládají jako **JSONL** — jeden JSON
objekt na řádek. Je to pořád JSON, ale jde připisovat na konec a číst po
částech, aniž se načte celý soubor.

Až měření ukáže, že formát je úzké hrdlo, vymění se — ale za číslo, ne za dojem,
a výměna se schová za rozhraní úložiště, ne za `if` v kódu.

---

## 20 · Čeho se u modulu vyvarovat

| past | proč je to past |
|---|---|
| logika v `api.py` | modul přestane jít použít v procesu a `T-K3` ztratí smysl |
| globální logger nebo konfigurace | nejde podstrčit v testu, nejde mít dva vedle sebe |
| import do vnitřku cizího modulu | obchází se veřejné API a šev přestane být šev |
| `except: pass` | tichá chyba je nejhorší druh chyby; chybí `result=error` s důvodem |
| prázdná odpověď místo typované chyby | slije se „nemá výsledek" s „nepodařilo se" (`INV-9`) |
| práh natvrdo v kódu | magické číslo, které se po měření ohne |
| volání ven bez timeoutu | služba nezhavaruje, ale zamrzne — a to se hledá hůř |
| klient vytvořený v cyklu | kontrola služby se dělá pořád dokola místo jednou při startu |
| chybová hláška bez návodu, čím službu spustit | hodina hledání chyby v kódu místo jednoho příkazu |
| synchronní log na každý záznam | debug úroveň se stane nepoužitelnou a někdo ji vypne |
| celý obsah dat v úrovni `info` | log naroste tak, že se v něm nedá hledat |
| sdílený stav v `service.py` | v testu projde, v provozu se rozpadne |
| přímý zápis do cílového souboru | pád procesu zanechá poloviční JSON |
| test na provozních datech | měří se něco jiného, než se tvrdí |
| „dočasně to udělám takhle" | dočasné řešení bez testu je trvalé řešení bez testu |

---

## Příloha A · Kontrolní seznam nového modulu

Když zakládám modul `cb-<name>`:

```
[ ] cb-<name>.py                v kořeni, spustitelný, chmod +x
[ ] cb_<name>/                  adresář modulu (podtržítko — importuje se)
[ ] cb_<name>/cb-<name>-config.json     s config_version, service, logging, runtime, module
[ ] cb_<name>/config.schema.json        validuje výše uvedené
[ ] cb_<name>/config.py                 validace při startu, neznámý klíč = chyba
[ ] cb_<name>/__init__.py               jen veřejná jména, __all__
[ ] cb_<name>/service.py                bez HTTP, bez cest, bez globálů
[ ] cb_<name>/api.py                    /version, /v1/health, /v1/config, /v1/summary + vlastní
[ ] cb_<name>/client.py                 endpoint z konstruktoru, timeout z konfigurace,
                                        loguje sám, stejné signatury jako service.py,
                                        v konstruktoru ověří GET /version a selže s návodem
[ ] cb_<name>/control.py                start, stop, restart, reload, status
                                        status uvádí port i u neběžící služby
[ ] cb_<name>/data-persistent/          .gitkeep
[ ] cb_<name>/run/                      v .gitignore
[ ] cb_<name>/scripts/                  fetch skripty pro velká data (§ 19)
[ ] cb_<name>/docs/koncepce.md          proč takhle a ne jinak
[ ] cb_<name>/docs/metody.md            každá metoda: co, proč, na čem visí
[ ] cb_<name>/docs/prirucka.md          otázky ze stavby a pasti
[ ] cb_<name>/tests/data/               zmražená testovací data
[ ] cb_<name>/tests/test_service.py     T-K1, T-K2
[ ] cb_<name>/tests/test_api.py         REST kontrakt, návratové kódy
[ ] cb_<name>/tests/test_control.py     pět příkazů, návratové kódy 0/1/2/3
[ ] cb_<name>/tests/test_parity.py      T-K3
[ ] testy běží přes ./run-python -m unittest discover -s cb_<name> -t .
[ ] cb_<name>/README.md                 co, proč, co neřeší, prahy, závislosti
[ ] zápis do tabulky rozsahů portů v § 5 — celá stovka, základní port na stovce
[ ] zápis do § 4, pokud je modul sdílený
[ ] naměřené číslo v docs/ s datem, verzí dat a verzí konfigurace

Pořadí: nejdřív celý scaffold výše, teprve pak funkcionalita (§ 16).
Prázdný modul, který projde T-K1–T-K4, je hotový scaffold.
```
