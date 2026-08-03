# cb-logger — jak je to koncipované

Proč logovátko vypadá takhle a ne jako `logging` ze standardní knihovny.
Každé rozhodnutí níž má uvedeno, z čeho plyne — ze zadání, z politiky modulů,
nebo z chyby naměřené při stavbě.

Návod k použití je v `prirucka.md`, přehled rozhraní v `../README.md`.

---

## 1 · Východisko: log není text, je to měření

Klasické logování zapisuje **věty pro člověka**. Když se pak chce vědět, kolikrát
něco selhalo, grepuje se podle řetězce — a ten se změní při první úpravě hlášky.

Tenhle systém stojí na tom, že **měření je základ hodnocení úspěšnosti**.
Z toho plyne, že log musí být od začátku spočitatelný, ne jen čitelný. Proto:

* záznam je **strukturovaný objekt**, ne řádek textu,
* výsledek je **typovaný výčet**, ne slovo v hlášce,
* logovátko samo počítá souhrn a nabízí ho na `GET /v1/summary`.

Souhrn není nadstavba nad logem. Je to důvod, proč log takhle vypadá.

---

## 2 · Dvě osy místo jedné

Klasické logování má jednu osu — `DEBUG < INFO < WARNING < ERROR < CRITICAL`.
Tady jsou dvě a každá odpovídá na jinou otázku:

```
                 jak hluboko se dívám          jak to dopadlo
                 ────────────────────          ──────────────
   metoda        log.info()  log.debug()       result=ok
                                               result=empty
                                               result=skipped
                                               result=error
```

**Proč to nejde sloučit.** `log.error()` slévá *„tohle je důležité"* s *„tohle
selhalo"*. A ta druhá věc se musí rozlišit od třetí, kterou severity neumí
vyjádřit vůbec — od **prázdného výsledku**.

Věta, ze které nevznikl atom, protože v ní žádný nebyl, je `empty`.
Věta, ze které nevznikl atom, protože spadl parser, je `error`.

Kdyby se slily, měření by odměnilo právě tu chybu, kterou má chytat: vrátit
prázdno je totiž nejlevnější způsob, jak nemít chybu. Tohle je nejdůležitější
rozhodnutí celého modulu a všechno ostatní se mu podřizuje — od typu v kódu
přes JSON schéma až po barvu v kukátku.

---

## 3 · Dva druhy logu, ne dva formáty téhož

Textový a objektový záznam nejsou dvě podoby jedné věci. Odpovídají na různé
otázky a čtou se různě:

| | textový záznam | objektový záznam |
|---|---|---|
| otázka | *co se stalo* | *jak vypadala data* |
| metoda | `log.info()`, `log.debug()` | `log.json()` |
| jednotka | řádek | celý objekt |
| čte se | souvisle, zajímá sled | po jednom, zajímá obsah |
| proud | `data-persistent/log.jsonl` | `data-persistent/objects/objects.jsonl` |
| kukátko | `:42101`, tabulka | `:42102`, rozbalitelné stromy |

**Proč dva proudy a ne jeden.** Pole po sítku má stovky bajtů, koš jednotky
kilobajtů. Kdyby tekly do téhož souboru jako textové záznamy, nešlo by přečíst
ani jedno: textový log by se utopil v datech a objekty by se ztratily mezi
řádky. A hlavně by nešlo mít dvě kukátka otevřená vedle sebe, což je přesně
způsob, jakým se používají.

**Proč objekt vůbec ukládat celý.** Zploštit strukturu do řetězce znamená přijít
o to, kvůli čemu se na ni člověk dívá. `str(pole)` v logu je k nepoužití;
rozbalitelný strom je nástroj.

---

## 4 · Modul má dvě tváře

```
service.py    doménová logika. Nezná HTTP, nezná cesty, nezná konfiguraci.
api.py        REST obálka. Rozbalí, zavolá, zabalí. Žádná logika.
client.py     to, co si naimportuje cizí modul. REST volání uvnitř.
```

Plyne to z rozporu, který se dal vyřešit jen takhle: zadání říká, že **každá
komponenta běží jako služba s REST API**, kdežto architektonický návrh říká, že
**jádro nesmí mít vstupně-výstupní vrstvu**.

Rozdělení na dvě tváře oba požadavky splní naráz. Týž kód jde volat v procesu
(rychle, z testu, z dávky) i po síti (z jiné služby) a **musí vrátit totéž** —
to hlídá zkouška `T-K3`, která tentýž vstup pošle oběma cestami do dvou
samostatných logovátek a porovná, co vypadne.

Praktický zisk: `service.py` se testuje bez spuštěné služby, takže 196 zkoušek
běží za deset sekund. Kdyby všechno šlo přes HTTP, běžely by minuty a nikdo by
je nespouštěl.

---

## 5 · Zápis je asynchronní, a je to cena za použitelný debug

Klient nesmí zdržet ani shodit toho, kdo loguje.

```
zápis → fronta v paměti → vlákno na pozadí → dávka → POST /v1/records
                                  ↓ služba nedostupná
                          run/log-spool/<component>.jsonl
```

**Proč.** Debug úroveň vyrobí na plném korpusu statisíce záznamů. Synchronní
HTTP volání na každý z nich by z nejcennější úrovně logu udělalo tu nejdražší
věc v systému a někdo by ji vypnul. Vypnutý debug znamená, že se stopa nedá
zpětně přečíst, a tím padá `P8` — každý artefakt musí být vysvětlitelný.

**Cena.** Konec procesu bez `close()` znamená ztrátu toho, co zbylo ve frontě.
Naměřeno při stavbě: 7 záznamů ve službě před zápisem, 7 po zápisu bez
`close()`. Je to popsané v příručce a je to jediná past, kterou modul má.

**Co se dělá s výpadkem.** Nedostupné logovátko není chyba volajícího. Klient
napíše hlášku, přepne se do spool režimu a pokračuje; po návratu služby spool
odešle. Kdyby padlé logovátko shodilo systém, byla by nejméně důležitá součást
zároveň nejkřehčí.

---

## 6 · Nedostupnost se pozná při vytvoření klienta

Konstruktor se ptá na `GET /version` a podle odpovědi nastaví `available`.

**Proč ne až u prvního zápisu.** Klient vytvořený nad neběžící službou je
tikající chyba — ukázala by se uprostřed dávky, po hodině počítání a s polovinou
zapsaných výsledků. Jedno volání stojí jednotky milisekund.

**Proč zrovna `/version`.** Je to jediná neverzovaná cesta a jediný bod bez
závislostí: odpoví, i když je služba jinak nezdravá. Rozliší tedy *„neběží"*
od *„běží, ale něco jí chybí"*. A stojí mimo `/v1/` proto, že kdo se ptá na
verzi, ještě neví, kterou verzi rozhraní má volat.

U logovátka se z toho **nevyhazuje výjimka** — je to nepovinná závislost.
U ostatních modulů, kde je závislost povinná, se vyhazuje `ServiceUnavailable`
s hláškou, která povinně říká který modul, na jaké adrese a čím ho spustit.

---

## 7 · Špatný záznam se přijme a označí

Když přijde záznam, který neodpovídá schématu, logovátko ho **nezahodí
a nevrátí chybu**. Uloží ho s příznakem `malformed`, důvodem v češtině
a původním obsahem pod `raw`.

**Proč.** Záznam se posílá právě tehdy, když se něco děje. Odmítnout ho znamená
přijít o stopu od komponenty, která má zjevně problém — tedy o tu nejcennější.
A volající se to stejně nedozví, protože zápis je asynchronní.

**Aby to nebylo svolení k rozpadu.** `malformed` se počítá zvlášť v souhrnu,
takže rostoucí číslo je chyba ve volajícím a je ji poznat bez čtení logu.
Směrovač na něj smí mít pravidlo a odklonit ho stranou.

Totéž platí pro objekty, jen se přidávají dvě meze: objekt přes 256 kB se uloží
jako náhled s poznámkou o původní velikosti, hlubší než 24 úrovní se ořízne
značkou. Ani jedno není chyba — je to mez, o které se ví, a je označená.
Vedlejší užitek: oříznutí hloubky zvládne i cyklickou strukturu, na které by
serializace zamrzla.

---

## 8 · Stopa drží průchod pohromadě

`trace` je identifikátor **jednoho průchodu systémem**, ne relace a ne HTTP
požadavku.

**Problém, který řeší.** Odpověď na jednu otázku projde sedmi moduly, v každém
udělá desítky záznamů, a všechny komponenty zapisují do jednoho proudu naráz.
Bez společného identifikátoru je log posloupnost vět bez odstavců.

```
trace q-7f3a91
  cb-ingest    receive        ok       1 věta
  cb-udpipe    parse          ok       9 tokenů
  cb-field     build_field    ok       13 řádků
  cb-templates match          empty    žádná šablona nesedí   ← tady to končí
  cb-answer    compose        empty    mlčení
```

**Kdo ji razí.** Vstupní bod průchodu — obsluha dotazu, příkaz v CLI, dávkový
skript. Modul stopu nikdy nevyrábí, jen ji předává. Kdyby si ji razil každý
modul, rozpadl by se řetěz na tolik kusů, kolik je modulů, a to je horší než
žádná stopa, protože to vypadá, že funguje.

**Předává se explicitně** — parametrem uvnitř procesu, klíčem v těle požadavku
přes REST. Žádné `contextvars`, žádné hlavičky, které se cestou ztratí.
Chybějící stopa se počítá v souhrnu jako `without_trace`: je to měřitelná díra
v řetězu, ne chyba.

---

## 9 · Kukátka jsou zákazníci, ne součást

Obě stránky se ke službě **přihlašují jako odběratelé** a čtou tentýž proud
jako kdokoli jiný. Nemají vlastní cestu k datům.

**Proč to takhle.** Kdyby sahaly do souborů přímo, nešly by vypnout — a přesně
to se dělá na stroji bez displeje. A rozešly by se s tím, co vidí ostatní.

Z toho plynou tři vlastnosti: stránky jsou **soběstačné** (žádný framework, nic
ze sítě, funguje bez internetu), **jen čtou** (ze stránky nejde nic zapsat ani
smazat) a **filtrují v prohlížeči**, ne na serveru — dokud je to jeden proud,
je to levnější než dotazovací rozhraní, které zatím nestavíme.

Živý proud jde přes Server-Sent Events. Je to obyčejné HTTP, zvládne ho
standardní knihovna a prohlížeč si po výpadku spojení obnoví sám.

**Dvě čísla, která se snadno slijí.** `buffer_records` je kolik posledních drží
server, aby nově otevřené okno nezačínalo u prázdna; `window_records` je kolik
jich drží okno v prohlížeči, než začne odsouvat nejstarší. To první se platí
pamětí serveru jednou, to druhé platí každá otevřená záložka. Bez druhého
stropu by stránka nechaná otevřená přes noc narostla o statisíce řádků
a prohlížeč by se zadrhl — zrovna ve chvíli, kdy se něco děje.

---

## 10 · Co drží souhrn

`GET /v1/summary` počítá podle **komponenta × metoda × result** a ukládá se na
disk, takže **přežije restart**. Čísla, která mizí při každém restartu, se
nedají použít k hodnocení systému.

Vedle počtů po stavech nese dvě věci navíc:

* `malformed` — kolik záznamů přišlo ve špatném tvaru; roste jen chybou
  ve volajícím,
* `without_trace` — kolik záznamů nemá stopu; rostoucí podíl znamená, že někdo
  přestal předávat parametr.

Vynuluje se jen explicitním voláním. Samo se nevynuluje nikdy — souhrn, který
se občas sám vynuluje, je horší než žádný, protože se na jeho čísla spoléhá.

---

## 11 · Co je vědomě jinak než v `logging`

| standardní `logging` | tady | proč |
|---|---|---|
| pět úrovní závažnosti | dvě úrovně + čtyři stavy | severity neumí odlišit prázdno od chyby |
| `getLogger(__name__)` z globálu | klient se předává parametrem | globál nejde podstrčit v testu a nejdou mít dva vedle sebe |
| formátovaný řetězec | strukturovaný objekt | log musí být spočitatelný, ne jen čitelný |
| handlery a formattery | směrovač jako čistá funkce | jedno místo, kde se rozhoduje kam; testuje se bez zapisování |
| zápis na místě | fronta a dávka | statisíce debug záznamů by jinak logování zabily |
| chybný zápis vyhodí | chybný zápis se uloží označený | stopa je nejcennější právě u komponenty, která má problém |

---

## 12 · Čeho se modul vědomě nedotýká

* **Dotazovací rozhraní nad uloženými záznamy.** `GET /v1/records` s filtrem
  podle stopy zatím není. Kukátko čte živý proud, starší se hledají v JSONL.
  Přidá se, až bude jasné, jak se ptát — ne dřív.
* **Warning a critical.** Pátá hodnota je změna výčtu a schématu, ne nová metoda,
  a udělá se, až bude jasné, jaké rozhodnutí by se podle něj dělalo jinak.
  Výsledek, podle kterého se nikdo nerozhoduje, znamená za měsíc u každé komponenty
  něco jiného.
* **Autentizace, síť, víc strojů.** Jeden lokální uživatel, `127.0.0.1`.
* **Jiný formát než JSON.** Všechno je JSON a JSONL, dokud měření neukáže, že
  je to úzké hrdlo. Pak se to vymění za číslo, ne za dojem.
