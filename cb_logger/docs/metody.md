# cb-logger — metody, jejich důvod a závislosti

Ke každé veřejné metodě: **co dělá**, **proč existuje** (co by se stalo, kdyby
nebyla) a **na čem závisí**. Závislosti jsou vytažené z AST, ne odepsané —
uvádí se jen volání do vlastního kódu modulu, ne do standardní knihovny.

Vývojáře, který modul jen volá, zajímá `../../README-LOGGER.md`. Tenhle soubor
je pro toho, kdo modul upravuje.

Čte se zdola nahoru: `record` a `objects` nezávisí na ničem, `control` na všem.

```
record ─┐
objects ─┼─→ service ─┬─→ api ────┐
config ──┘            ├─→ watch ──┼─→ control
                      └─→ client  ┘
```

---

## `record.py` — datový typ textového záznamu

Nezávisí na ničem z modulu. Je to základ, na kterém stojí zbytek.

### `Level` · `Result`

Dva výčty. `Level` je `info` nebo `debug` (jak hluboko se dívám), `Result` je
`ok`, `empty`, `skipped`, `error` (jak to dopadlo).

**Proč výčet a ne řetězec.** `"no error"`, `"bez chyby"`, `"OK"` a `"ok"` jsou
pro člověka totéž a pro souhrn čtyři různé věci. Za měsíc by každá komponenta
psala něco jiného a souhrn by přestal jít sečíst. Výčet to znemožní v okamžiku
zápisu, ne až při čtení.

**Proč dědí ze `str`.** Hodnota jde rovnou do JSON bez převodu a porovnání
s řetězcem z drátu funguje bez přemýšlení.

**Závisí na:** ničem.

### `LogRecord`

Jeden ověřený záznam, neměnný (`frozen=True`).

**Proč `frozen`.** Záznam je fakt o tom, co se stalo. Kdyby šel po vytvoření
změnit, mohl by ho směrovač nebo zapisovač cestou upravit a v souboru by
skončilo něco jiného, než co komponenta ohlásila.

**Proč nese `malformed` místo toho, aby špatný záznam nevznikl.** Viz
`from_wire` níž.

**Závisí na:** `Level`, `Result`.

### `LogRecord.to_json_object()`

Převede záznam na JSON objekt k zápisu.

**Proč vlastní metoda a ne `dataclasses.asdict`.** Ten by zapsal i pole
s hodnotou `None`, takže by každý řádek logu nesl sedm prázdných klíčů. Log se
čte očima a prázdné klíče jsou šum, který zakrývá to podstatné.

Pořadí klíčů je pevné schválně — dva řádky logu vedle sebe pak jde porovnat
okem, ne nástrojem. Jediná výjimka z vynechávání prázdných hodnot je `trace`:
chybějící stopa je měřitelná díra v řetězu doložení a musí být vidět.

**Závisí na:** ničem.

### `from_wire(raw, *, received_ts)`

Udělá z toho, co přišlo po drátě, ověřený `LogRecord`.

**Proč nikdy nevyhazuje výjimku.** Stojí na vstupu logovátka a dostává data od
cizích modulů. Kdyby na špatném tvaru spadla, ztratil by se záznam z komponenty,
která má zjevně problém — tedy ten nejcennější. Místo toho vrátí záznam
označený `malformed` s důvodem a s původním obsahem pod `raw`.

**Proč `received_ts` parametrem.** Funkce, která si sáhne na hodiny sama, nejde
deterministicky otestovat.

**Závisí na:** `Level`, `Result`, `LogRecord`.

---

## `objects.py` — datový typ objektového záznamu

Druhý druh logu. Nezávisí na `record.py` — jsou to nezávislé typy, protože
odpovídají na různé otázky.

### `ObjectRecord` · `ObjectRecord.to_json_object()`

Zalogovaný JSON objekt s hlavičkou (kdo, kdy, jaký štítek) a příznaky
`truncated` a `depth_limited`.

**Proč nemá `result`.** Objekt není výsledek volání, je to pohled na data —
otázka „jak to dopadlo" u něj nedává smysl. Kdo chce obojí, pošle dva záznamy
se stejnou stopou.

**Závisí na:** ničem.

### `from_wire(raw, *, received_ts, max_object_bytes, max_depth)`

Totéž co u textového záznamu, plus dvě meze.

**Proč meze.** Zalogovat celý korpus by udělalo záznam, který nikdo neotevře,
a zaplnilo disk. A strom hlubší než pár desítek úrovní se v kukátku nedá
rozbalit. Objekt přes strop se **uloží oříznutý a označený, ne zahozený** —
chybějící záznam není nic.

**Vedlejší užitek oříznutí hloubky.** Zvládne i strukturu, která odkazuje sama
na sebe; `json.dumps` by se na ní zacyklil.

**Závisí na:** `ObjectRecord`.

---

## `config.py` — načtení a ověření konfigurace

### `load(path=None)`

Načte konfiguraci, ověří ji proti schématu, převede relativní cesty na
absolutní a doplní `_meta` s cestou a otiskem.

**Proč se validuje při startu a ne při prvním použití.** Služba, která
nastartovala se špatnou konfigurací, je horší než služba, která nenastartovala.
Chyba v nastavení by se projevila až za hodinu uprostřed dávky, a to na místě,
které s příčinou nesouvisí.

**Proč vrací slovník a ne objekt `Config`.** Hodnoty se předávají funkcím po
jedné. Objekt, ze kterého si funkce sama tahá, co potřebuje, schová závislost
před čtenářem signatury.

**Proč `_meta` s otiskem.** Každé naměřené číslo nese verzi konfigurace, jinak
jsou dvě čísla nesrovnatelná. Verze v souboru se mění zřídka, hodnoty často —
otisk pozná i změnu, u které nikdo číslo nezvýšil.

**Proč vlastní validátor místo `jsonschema`.** Kód modulů nesmí mít závislosti.
Validátor zvládá jen tu část JSON Schema, kterou naše schémata používají, a na
cokoli jiného **hlasitě upozorní** — nikdy tiše neprojde. Nedostatečný
validátor, který mlčí, je horší než žádný.

**Závisí na:** `ConfigError`.

### `ConfigError`

Vlastní typ výjimky, aby ovládací program poznal neplatnou konfiguraci od
ostatních chyb a vrátil návratový kód `2` místo obecné jedničky.

---

## `service.py` — doménová logika

Nezná HTTP, nezná sokety, nečte konfiguraci ze souboru. Dostane hotové hodnoty
a pracuje nad nimi, takže se celá otestuje bez spuštěné služby.

### `now_iso()`

Aktuální čas v ISO 8601 s milisekundami, v UTC.

**Proč UTC.** Log ze dvou dnů kolem přechodu na letní čas by v místním čase
obsahoval hodinu, která se opakuje, a hodinu, která neexistuje. Řadit takový
log podle času nejde.

**Proč milisekundy.** V jednom průchodu vznikne během sekundy klidně sto
záznamů; bez nich by se nedaly seřadit.

**Proč je to funkce a ne metoda služby.** Je to jediné místo, které sahá na
hodiny, a volá se z okraje systému, ne z logiky.

**Závisí na:** ničem.

### `route(record, routing)`

Čistá funkce záznam → cesta k souboru. Pravidla shora dolů, první shoda
vyhrává.

**Proč čistá funkce a ne `if` v zapisovači.** Dělení proudu se dodatečně zavádí
špatně: přibyl by `if` pro komponentu, pak druhý pro úroveň, pak třetí pro
velikost — a z toho vzniká kód, který se nedá vyměnit. Takhle je jediné místo,
kde se rozhoduje kam, a testuje se bez zapisování.

**Proč podmínky v pravidle platí současně (A, ne NEBO).** Kdyby platilo NEBO,
nešlo by zúžit pravidlo na debug záznamy jedné komponenty — a to je
nejčastější potřeba.

**Závisí na:** ničem.

### `Writer.write(records)`

Zapíše dávku dvojic (cesta, záznam) do JSONL.

**Proč bere dávku a ne jeden záznam.** Klient posílá po dávkách a zápis celé
dávky pod jedním zámkem je řádově levnější než zamykat u každého řádku.

**Proč drží otevřené popisovače.** Zápis do logu je krátké a časté volání.
Otevřít a zavřít soubor u každého záznamu by z logování udělalo to nejdražší
v systému a někdo by ho vypnul.

**Proč `flush` hned po dávce.** Nedopsaný řádek v systémové vyrovnávací paměti
je při pádu procesu ztracený — a to zrovna ten poslední, který obvykle říká,
co se stalo.

**Závisí na:** `LogRecord.to_json_object`, vnitřní rotaci.

### `Writer.write_objects(records)`

Totéž pro objektové záznamy.

**Proč vlastní metoda a ne společná se `write`.** Obojí zapisuje JSONL, ale
objektový záznam má jiný typ a společná metoda by musela mít parametr „co to
je". `if` podle druhu dat je diagnostika chybějícího švu; tady je levnější mít
dvě metody než jednu s odbočkou.

**Závisí na:** `ObjectRecord.to_json_object`, `Writer.write` (sdílí rotaci).

### `Writer.close()`

Zavře popisovače. Volá se explicitně při ukončení.

**Závisí na:** ničem.

### `Summary.add(record)` · `.snapshot()` · `.flush()` · `.reset()`

Počty podle komponenta × metoda × result, plus `malformed` a `without_trace`.

**Proč to počítá logovátko a ne někdo nad ním.** Souhrn není nadstavba nad
logem — je to důvod, proč log vypadá, jak vypadá. Kdyby se počítal až dodatečně
z uložených souborů, byl by drahý a nikdo by se na něj nedíval.

**Proč `flush` zapisuje atomicky** (do dočasného souboru a přejmenovat). Přímý
zápis po pádu procesu zanechá poloviční JSON, který už nikdo nepřečte — a přišlo
by se tím o celé měření, ne o poslední vteřinu.

**Proč `reset` jen explicitně.** Souhrn, který se občas sám vynuluje, je horší
než žádný, protože se na jeho čísla spoléhá.

**Proč se nesouhlasná verze formátu odsune stranou** místo tichého začátku od
nuly: začít od nuly by vypadalo jako čerstvý start, zatímco data existují.

**Závisí na:** `Result` (klíče počtů).

### `LoggerService.accept(records, *, received_ts)`

Přijme dávku textových záznamů, uloží je a započítá.

**Proč nikdy neodmítne kvůli obsahu.** Záznam se posílá právě tehdy, když se
něco děje. Špatně tvarovaný se uloží označený, ne zahodí.

**Proč vrací počty místo výjimky.** Volající je asynchronní klient; výjimka by
neměla kam bublat.

**Závisí na:** `record.from_wire`, `route`, `Writer.write`, `Summary.add`,
`_publish`.

### `LoggerService.accept_objects(records, *, received_ts)`

Totéž pro objekty. Vlastní proud, vlastní buffer, vlastní odběratelé.

**Proč oddělený proud.** Pole po sítku má stovky bajtů, koš jednotky kilobajtů.
Kdyby tekly do téhož souboru jako textové záznamy, nešlo by přečíst ani jedno.

**Závisí na:** `objects.from_wire`, `Writer.write_objects`, `_publish_object`.

### `subscribe()` / `unsubscribe()` / `recent()` a jejich objektové dvojče

Přihlášení k živému proudu a kruhový buffer posledních N záznamů.

**Proč to má služba a ne kukátko.** Kukátko je zákazník, ne součást — čte
tentýž proud jako kdokoli jiný a nemá vlastní cestu k datům. Kdyby sahalo do
souborů přímo, nešlo by vypnout a rozešlo by se s tím, co vidí ostatní.

**Proč kruhový buffer.** Nově otevřené okno by jinak začínalo u prázdna
a čekalo, až něco přiteče.

**Proč odběratel, který spadne, se odhlásí.** Zavřená záložka nesmí ovlivnit
zápis ani ostatní okna.

**Závisí na:** ničem.

### `LoggerService.summary()` · `.reset_summary()` · `.health()`

Čtecí body pro REST a pro `status`.

**Proč `health` hlásí i to, co je vypnuté.** Systém s vypnutou částí není tentýž
systém a měření to musí vědět.

**Závisí na:** `Summary.snapshot`, u resetu `now_iso` a `Summary.reset`.

### `LoggerService.note_error()` · `.flush()` · `.close()`

Zapamatování poslední chyby pro `health`, uložení souhrnu, řízený úklid.

**Proč `note_error`.** Poslední chyba se objeví ve `status` — jinak by se o ní
člověk dozvěděl jen z logu, který v tu chvíli nemusí jít zapisovat.

**Závisí na:** `Summary.flush`, `Writer.close`.

---

## `client.py` — to, co si importují ostatní moduly

### `default_endpoint()`

Zjistí, kde logovátko běží, a řekne, odkud to ví.

**Proč to není magie.** Adresu služby deklaruje sama služba ve své konfiguraci
a skutečně přidělený port si zapisuje do `run/service.port`. Tahle funkce čte
totéž co `status`. Bez ní by každý volající opisoval adresu, kterou modul už
zná — a při změně portu by se opisy rozešly.

Pořadí: `run/service.port` (skutečný) → konfigurace (zamýšlený) → zabudovaná
hodnota. Vrací i **odkud**, protože bez toho se ladí jedna instance a běží
druhá.

**Závisí na:** `config.DEFAULT_CONFIG_PATH` (jen cesta, ne `load` — nečitelná
konfigurace nesmí bránit logování).

### `LogClient.__init__(...)`

Postaví klienta a **hned se zeptá služby na `/version`**.

**Proč se dostupnost zjišťuje hned.** Klient vytvořený nad neběžící službou je
tikající chyba — ukázala by se uprostřed dávky, po hodině počítání a s polovinou
zapsaných výsledků.

**Proč se z toho nevyhazuje výjimka.** Logovátko je nepovinná závislost. Kdyby
padlé logovátko shodilo systém, byla by nejméně důležitá součást zároveň
nejkřehčí.

**Proč registruje pojistku na konec procesu.** Odesílací vlákno je démon
a odesílá po dávkách; kdo skončí dřív než za `flush_interval_ms`, přišel by
o všechno, co zapsal. *(Naměřeno: `log.info(...)` a konec skriptu = nula
záznamů.)*

**Závisí na:** `default_endpoint`, `Level`.

### `LogClient.info(...)` · `LogClient.debug(...)`

Zápis textového záznamu na dvou úrovních.

**Proč dvě metody a ne pět podle závažnosti.** Závažnost je v `result`.
`log.error()` slévá „tohle je důležité" s „tohle selhalo", a to druhé se musí
rozlišit od třetího — od prázdného výsledku, který severity neumí vyjádřit
vůbec.

**Proč jsou všechny parametry pojmenované včetně `method`.** Dokud byl poziční,
skončila v něm hláška. Takový zápis projde, ale rozbije měření: souhrn se počítá
podle komponenta × metoda × result, takže by každá hláška byla vlastní řádek.

**Proč výchozí úroveň posílá všechno.** Kdo úroveň nenastavil, si nevybral —
a nevybráním se nemá přicházet o data. Filtruje se až při výpisu.

**Závisí na:** `_enqueue` → `now_iso`.

### `LogClient.json(...)`

Zápis celého objektu.

**Proč vlastní metoda a ne parametr u `info`.** Je to jiný druh logu, ne jiný
formát téhož: jiný proud, jiné kukátko, jiná otázka. Parametr by znamenal, že
polovina ostatních parametrů nedává smysl.

**Proč neořezává u klienta.** Klient neví, jaké stropy služba má; ořezat dvakrát
podle různých mezí by dalo záznam, o kterém nikdo neví, co v něm chybí.

**Závisí na:** `now_iso`.

### `LogClient.flush(timeout_s)` · `LogClient.close(timeout_s)`

Dopravení fronty a řízené ukončení.

**Proč vrací počet místo výjimky.** Volá se při ukončení procesu, kdy už výjimka
nemá kam bublat.

**Proč `flush` čeká i na rozpracovanou dávku, ne jen na frontu.** Odesílací
vlákno si záznam vyzvedne během mikrosekund a drží ho v lokální dávce; fronta je
pak prázdná, ale odesláno není nic. *(Naměřeno: první pojistka se dívala jen do
fronty a záznam se ztrácel nahodile.)*

**Závisí na:** `_pending`.

### `LogClient.stats()`

Stav klienta pro `health` volajícího modulu.

**Proč existuje.** Odpovídá na otázku „proč mi nic nechodí" bez čtení kódu:
`endpoint_source` řekne, s kterou instancí klient mluví, `filtered_by_level`
kolik se zahodilo kvůli úrovni, `dropped` kolik přeteklo, `undelivered` kolik
se nepodařilo uložit ani do spoolu.

**Závisí na:** `_pending`.

### `from_config(config, *, component)`

Postaví klienta z bloku `logging` konfigurace volajícího modulu.

**Proč existuje.** Každý modul by jinak opisoval osm parametrů a při první
změně by se opisy rozešly.

**Závisí na:** `LogClient`.

---

## `api.py` — REST obálka

**Nesmí obsahovat jediné rozhodnutí o doméně.** Když se tu objeví `if` nad
obsahem dat, patří do `service.py`.

### `ApiHandler.do_GET()` · `do_POST()`

Obsluha čtecích a zapisovacích bodů.

**Proč `/version` stojí mimo `/v1/`.** Kdo se ptá na verzi, ještě neví, kterou
verzi rozhraní má volat. Kdyby žilo pod `/v1/`, klient by musel znát verzi, aby
zjistil verzi.

**Proč poslední záchyt výjimky.** Neošetřená výjimka v obsluze by zavřela
spojení bez odpovědi a volající by viděl výpadek sítě místo chyby.

**Závisí na:** `LoggerService.accept`, `.accept_objects`, `.health`,
`.summary`, `.reset_summary`, `now_iso`.

### `ApiHandler.log_message()`

Umlčí výchozí výpis na chybový výstup.

**Proč.** `BaseHTTPRequestHandler` po každém požadavku píše řádek na stderr.
U logovátka, které jich obsluhuje statisíce, by to zaplavilo terminál i soubor.

### `make_api_server(service, config)`

Postaví server, ale **nespustí ho**.

**Proč nespuštěný.** Volající si potřebuje přečíst skutečně přidělený port dřív,
než začne obsluhovat — podstatné, když je v konfiguraci nula.

**Závisí na:** `ApiServer`.

---

## `watch.py` a `watch_objects.py` — kukátka

### `send_stream_headers(handler)`

Hlavičky nekonečného SSE proudu.

**Proč `Transfer-Encoding: chunked`.** Odpověď HTTP/1.1 musí mít buď
`Content-Length`, nebo být dělená na kusy. Nekonečný proud délku znát nemůže.
*(Naměřeno: stránka se neaktualizovala živě, přestože server odesílal —
odpověď byla neplatná a prohlížeč čekal na něco, co nikdy nepřišlo.)*

**Závisí na:** ničem.

### `write_chunk(handler, telo)`

Zapíše jeden kus dělené odpovědi a vytlačí ho na soket.

**Proč `flush`.** Bez něj by data zůstala v zápisové vyrovnávací paměti a živý
proud by nebyl živý.

**Závisí na:** ničem.

### `WatchHandler.do_GET()` / `ObjectWatchHandler.do_GET()`

Stránka na `/`, živý proud na `/stream`.

**Proč fronta okna zahazuje nejstarší místo vyhození výjimky.** Vyhozením by se
okno tiše odhlásilo právě ve chvíli, kdy se nejvíc děje. Pomalý prohlížeč má
přijít o staré záznamy, ne systém o výkon.

**Proč se posílá komentář, když nic neteče.** Drží spojení proti prostředníkům,
kteří tiché spojení zavírají, a hlavně dá zapisovači šanci poznat, že prohlížeč
zmizel.

**Závisí na:** `LoggerService.subscribe`/`recent` (resp. objektové dvojče),
`send_stream_headers`, `write_chunk`, `LoggerService.note_error`.

### `make_watch_server()` / `make_object_watch_server()`

Postaví server kukátka, nebo `None`, když je vypnuté.

**Proč `None` a ne výjimka.** Na stroji bez displeje je kukátko zbytečný port.
Že je vypnuté, hlásí `health` — vypnutá funkcionalita musí být poznat.

**Závisí na:** příslušný `*WatchServer`.

---

## `control.py` — ovládání služby

### `main(argv)`

Zpracuje argumenty, načte konfiguraci, provede příkaz.

**Proč se konfigurace načítá tady, před příkazem.** Služba s neplatným
nastavením vůbec nenaběhne a `status` na ni nesahá zbytečně.

**Závisí na:** `config.load`, `cmd_start`, `cmd_stop`, `cmd_reload`,
`cmd_status`.

### `cmd_start(config, *, foreground, config_path)`

Spustí službu a **počká, až odpoví**.

**Proč se čeká.** Jinak by `start` vracel nulu i pro službu, která za vteřinu
spadne.

**Proč `start` na běžící službu není chyba.** Kdo ho volá, obvykle jen chce, aby
běžela — a ona běží.

**Proč se bez `--foreground` spouští přes vlastní ovládací program.** Existuje
tak jediná cesta ke spuštění služby a nemůže se rozejít.

**Závisí na:** `_serve`, `_wait_for_version`, `_running_pid`.

### `cmd_stop(config, *, timeout)`

`SIGTERM`, počkat, pak `SIGKILL`.

**Proč se vedle `os.kill(pid, 0)` zkouší i `waitpid`.** Ukončený potomek zůstane
zombie, dokud ho rodič nesklidí, a na zombie `os.kill` pořád uspěje. *(Naměřeno:
`stop` trval 20,05 s místo desetin — přesně `stop_timeout_s`.)*

**Závisí na:** `_running_pid`, `_wait_for_exit`, `_cleanup_runtime`.

### `cmd_reload(config)`

Pošle `SIGHUP`; služba znovu načte konfiguraci.

**Proč se služba nerestartuje sama, když něco změnit nejde.** Zahodila by
rozdělaná spojení, o kterých volající neví. Řekne to a nechá běžet staré.

**Závisí na:** `_running_pid`.

### `cmd_status(config, *, jako_json)`

Stav služby **včetně portu**.

**Proč se port uvádí i u neběžící služby.** Je to první příkaz, který člověk
zavolá, když něco nefunguje. Bez portu hledá chybu v běžící službě, zatímco
běží s jiným nastavením, než si myslí.

**Závisí na:** `_running_pid`, `_port`, `_http_get`.

### `_serve(config)`

Postaví službu, obsluhuje a řízeně skončí.

**Proč hlavní vlákno čeká na událost a obsluha běží vedle.** Volat `shutdown()`
přímo z obsluhy signálu by zamrzlo, protože `serve_forever` běží v témž vlákně,
které signál obsluhuje.

**Závisí na:** `LoggerService`, `make_api_server`, `make_watch_server`,
`make_object_watch_server`, `_SelfLog`, `_write_runtime`.

### `_SelfLog`

Vlastní log logovátka.

**Proč existuje.** Logovátko nemůže logovat samo do sebe, zacyklilo by se. Je to
jediné místo v systému, kde se loguje jinak.

**Závisí na:** `now_iso`.
