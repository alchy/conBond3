# Návrh systému, který se k odpovědi dopracuje

**Verze:** 2.2 — refaktor 1.0, rozhodnuté `Q-1`, pohledy nad daty, nálezy z konzultací
**Stav:** návrh před stavbou kostry
**Vzniká z:** `conBond` (graf, role, vztahy) + `conBond2` (aktivační pole, šablony, poctivost)
**Není:** refaktoring ani portace jednoho z nich

---

## Jak tento dokument číst

Dokument je rozdělen na šest částí a čtyři přílohy. Každá část odpovídá na jinou
otázku:

| část | otázka |
|---|---|
| **0 · Rámec** | Z čeho všechno plyne a co se nesmí porušit |
| **I · Architektura** | Z čeho se systém skládá |
| **II · Odvozování** | Jak se dopracuje k odpovědi a jak se na data dívá |
| **III · Učení** | Jak se zlepšuje |
| **IV · Provoz** | Jak běží |
| **V · Dodávka** | Jak se měří a v jakém pořadí se staví |

Vše, co má být citovatelné z kódu, testu nebo commitu, má **identifikátor**:

| prefix | význam | příklad |
|---|---|---|
| `INV-n` | invariant — nedotknutelná zásada | `INV-1` monotónnost |
| `SEAM-n` | šev — jediné místo, kde se smí lišit implementace | `SEAM-6` Hranovač |
| `AG-*` | subsystém (agent) | `AG-CHRONOS` |
| `C-n` | logická schopnost | `C-3` výroková dedukce |
| `M-n` | metrika | `M-1` dosah |
| `T-n` | třída zkoušky | `T-2` mlčí |
| `G-n` | mezera v návrhu 1.0 (příloha A) | `G-5` mřížka provenience |
| `Q-n` | otevřená otázka k rozhodnutí (příloha B) | `Q-3` odkud taxonomie |

**Pravidlo pro kód:** každý řez, práh a výjimka odkazuje na `INV-n` nebo `G-n`,
kvůli kterému vznikl. Bez odkazu je to magické číslo.

---

# ČÁST 0 · RÁMEC

## 1 · Účel a rozsah

Systém odpovídá na otázky nad korpusem a nad dialogem tak, že **každá odpověď
nese řetěz doložení** a **mlčení je platná odpověď**.

Co systém **je**:

* knihovna, která z textu vyrobí kódovaný popis světa a nad ním odvozuje,
* účastník rozhovoru, jehož paměť je rovnocenný zdroj pravdy vedle korpusu,
* **řešitel slovních úloh z výrokové logiky zadaných textem** — úlohu uchopí,
  zakóduje, vyřeší a vrátí odpověď v jazyce zadání (kap. 20),
* měřicí aparát, který o každém svém pravidle ví, z kolika dokladů vzniklo.

Co systém **není**:

* vyhledávač (vyhledávání je jen jedna operace nad kódem, ne cíl),
* generátor pravděpodobné odpovědi (číslo bez rozbalitelného zdůvodnění je
  hádání s desetinnou čárkou),
* zdroj faktů o světě mimo korpus, dialog a pravidla.

Podrobný seznam vědomých neúčastí je v kapitole 41.

## 2 · Věta, ze které všechno plyne

> **Rozumět textu znamená umět ho zakódovat tak, aby totéž vypadalo stejně.
> Všechno ostatní — vyhledání, odvození, vyloučení — je pak jedna operace nad
> tím kódem.**

Tři důsledky, které rozhodují o architektuře:

1. **Pravidlo nejde indukovat nad textem, jen nad referenčním jazykem.**
   Teprve kódování způsobí, že se dvě různé věty dají porovnat. Proto se
   `tchán = otec ∘ manžel` vyčetl z faktů sám, kdežto „kdo zemřel dřív, nemohl
   toho druhého znát" muselo být napsáno rukou — čas nebyl zakódovaný.
2. **Když se v jádře objeví `if` podle druhu dat, chybí šev.** Není to sloh, je
   to diagnostika. Každý takový `if` je jev, který ještě není kódovaný.
3. **Nula je nejnebezpečnější hodnota.** „Data to nemají" a „nepodařilo se
   zeptat" vypadají stejně. Systém musí ty dva stavy rozlišovat na úrovni typů,
   ne komentářů — a to napříč celým rozhraním, ne jen uvnitř (viz `G-17`).

A protějšek, který platí od kapitoly 23 dál:

> **Učit se znamená zpřesňovat kód, nikoli měnit pravdu.**

## 3 · Slovník pojmů

Bez tohoto slovníku se dokument nedá číst jednoznačně; v návrhu 1.0 chyběl
(`G-27`).

| pojem | význam |
|---|---|
| **aktivace** | atribut tokenu, který svítí — z rozboru, ze subsystému nebo z předchozí odpovědi |
| **vektor** | uspořádaná sada aktivací tokenu a jeho okolí, po průchodu sítkem |
| **vzor** | jeden konkrétní vektor — jak vypadá *tahle* věta |
| **šablona** | třída stejných vektorů — druh vět, které vypadají takhle |
| **matice** | vážené a doložené vztahy mezi šablonami (šablona otázky → šablony odpovědí) |
| **hrana** | predikát nad jmény s doložením: `uvěznit(kdo, kde) @ dokument:věta` |
| **entita** | scelené jméno se svými variantami a doložením |
| **rozměr** | osa, na kterou lze jev zakódovat (čas, místo, počet, zařazení); umí jen vylučovat |
| **arita** | kolik hodnot smí entita v dané roli mít — měřeno, ne zadáno |
| **provenience** | odkud tvrzení je: korpus, odvození, dialog, hypotéza |
| **řetěz doložení** | rozbalitelná cesta od odpovědi k větám, pravidlům a premisám |
| **doklad / navíc / spor** | trojice čísel při indukci pravidla; `navíc` **není** chyba |
| **dosah / zúžení** | je odpověď mezi kandidáty / je první (`M-1`, `M-2`) |
| **šev** | rozhraní, za kterým se smí lišit implementace, a jediné takové místo |
| **referenční jazyk** | množina predikátů, šablon, rozměrů a pravidel, v níž je svět zakódován |
| **etalon** | kurátorovaná sada otázek psaná rukou, včetně těch, na které je správná odpověď mlčení |

## 4 · Invarianty

Tohle není styl. Každý invariant je zapsaný po chybě, která bez něj vznikla.
Kód i testy na ně odkazují identifikátorem.

| id | invariant |
|---|---|
| **INV-1** | **Monotónnost.** Chybějící hrana znamená „nikdo se neptal", ne „neplatí". Kladné tvrzení z nepřítomnosti neplyne nikdy; záporné z **doložené** neslučitelnosti ano. |
| **INV-2** | **Každý závěr nese svůj řetěz.** Kandidát nese větu, odvozený fakt nese pravidlo a premisy, vyloučení nese osu a hodnoty. |
| **INV-3** | **Odvozené se nesmí splést s doloženým.** Ani v datech, ani ve formulaci odpovědi. |
| **INV-4** | **Mlčení je odpověď.** Stroj, který si vymyslí, je horší než stroj, který mlčí. Etalon má doménu, kde je správná odpověď mlčení. |
| **INV-5** | **Spor se hlásí, nepřepisuje.** Vybrat jednu z odporujících si hodnot a jet dál je tichá chyba — nejhorší druh. |
| **INV-6** | **Nejslabší důkaz potřebuje nejsilnější pole.** Role smí mluvit jen tam, kde agent není a kde je čím zúžit. |
| **INV-7** | **Práh se neohýbá po měření.** Když vyjde 16 dokladů proti prahu 20, pravidlo se nepřijme. Prahy žijí v registru (kap. 29), ne v hlavě. |
| **INV-8** | **Dvoustupňové měření.** Dosah i zúžení. Samotný dosah nic neznamená — vrátit všechno dá 100 %. |
| **INV-9** | **Nula se odlišuje od chyby.** „Nemá hodnotu" a „nepodařilo se získat" jsou různé typy, ne stejná nula. |
| **INV-10** | **Produkční báze se nikdy nemění přímo.** Každá naučená změna vzniká v experimentální kopii a povyšuje se měřením (kap. 26). |
| **INV-11** | **Statistický model smí pouze navrhovat.** Nikdy nerozhoduje o pravdivosti (kap. 27). |
| **INV-12** | **Odvolatelnost.** Co bylo přidáno, musí jít odebrat — včetně všeho, co se z toho odvodilo (kap. 14.4). |
| **INV-13** | **Každé měřítko má protiváhu.** Ke každému číslu, které jde zlepšit podvodem, patří druhé, které se tím podvodem zhorší (kap. 36.1). |
| **INV-14** | **Pohled nic nepřidává.** Odvozený pohled smí vybírat, spojovat a zobrazovat, nikdy zavést fakt, hranu ani pravidlo, které v bázi není (kap. 20.1). |

---

# ČÁST I · ARCHITEKTURA

## 5 · Knihovna, ne aplikace

Jádro je **importovatelná knihovna bez závislostí a bez vstupně-výstupní
vrstvy**. Server, prohlížeč, příkazová řádka i cizí program jsou jen klienti;
žádný z nich není zdroj pravdy.

```
jadro/          čistá knihovna — standardní knihovna jazyka a nic víc
  kodovani/     token → vektor · věta → hrana · entita → jméno
  abstrakce/    šablony · matice · pravidla · arita · graf
  odvozovani/   diagram · rozměry · tabulka · skládání
  jazyk/        profily z JSON
  uloziste/     rozhraní (SEAM-2), ne implementace

klienti/        server, CLI, REPL, notebook, viewBase — všechny volají totéž API
data/           korpusy, profily, etalony, báze — nikdy v kódu
```

Praktické důsledky, které se musí dodržet, jinak z toho knihovna není:

* **Žádné globální stavy.** Pole, znalost i rozhovor jsou objekty, které se dají
  vytvořit vedle sebe; dva korpusy v jednom procesu musí jít. To je zároveň
  podmínka souběhu (kap. 34) i experimentální vrstvy (kap. 26).
* **Žádné čtení cest z konstant.** Všechno přes `Config`, aby šel test ukázat na
  jinou složku než provoz. *(conBond2 na to doplatil: testy měřily proti
  pracovní kopii a tvrdily čísla z jiných dat.)*
* **Žádný tisk z jádra.** Log je šev; klient rozhodne, kam jde.
* **Parser je klient, ne závislost.** Jádro dostane hotové tokeny. Těžké
  knihovny (TensorFlow) patří k přípravě dat, ne k běhu odpovídání.
* **Deterministické API.** Táž data a táž otázka dají tutéž odpověď včetně
  pořadí kandidátů — jinak se nedá měřit. Pořadí při shodě skóre rozhoduje
  stabilní klíč, ne pořadí v paměti.
* **Serializovatelné výsledky.** Každý výstup jde do JSON beze ztráty, včetně
  řetězu doložení.

**Zkouška:** cizí program si naimportuje jádro, podá si vlastní tokeny a dostane
odpověď i s řetězem — bez serveru, bez souborů, bez sítě.

## 6 · Vícejazyčnost: všechno v JSON profilech

**V kódu nesmí být jediné slovo přirozeného jazyka.** Ani v podmínce, ani
v porovnání, ani v konstantě.

```
jazyk/cs.json     tázací tvary · role · spojky · měsíce · prázdná slova · šablony odpovědí
jazyk/en.json     totéž pro angličtinu
jazyk/de.json     …
```

Co všechno musí být v profilu, protože to dnes v kódu je nebo bylo:

| položka | příklad | stav v conBond2 |
|---|---|---|
| tázací tvar → typ | `kdy → Typ=cas` | ✓ v JSON |
| tázací tvar → role | `komu → komu_cemu` | ✓ v JSON |
| víceslovné tvary | `jako co → jako_co` | ✓ v JSON |
| deprel → role podle pádu | `obl + Dat → komu_cemu` | ✓ v JSON |
| role podle přísudku | `jmenovat: jak → koho_co` | ✓ v JSON |
| prázdná slova | předložky, spony | ✓ v JSON |
| role žádající jméno | `koho_co` chce NOUN | ✓ v JSON |
| předložka → role | `jako → jako_co` | ✓ v JSON |
| vztahová slovesa | `znát, setkat se` | ✓ v JSON |
| **základní vztahy** | `otec, matka, syn…` | ✗ v kódu |
| **prázdná slovesa** | `být, mít` | ✗ v kódu |
| **jmenné UPOS** | `PROPN` jako jméno osoby | ✗ v kódu |
| **pády přísudku** | `Nom, Ins` | ✗ v kódu |
| **značky jmen** | `NameType=Giv/Sur/Geo` | ✗ v kódu |
| **skládání jména** | příjmení přes `flat` | ✗ v kódu |
| **tvar odpovědi** | „upřesni prosím, koho myslíš" | ✗ v kódu |

Poslední řádek je podstatný a snadno se zapomene: **texty odpovědí jsou taky
jazyk.** Patří do profilu jako šablony s dosaditelnými místy, ne do f-stringů
v jádře.

Co zůstává univerzální a do profilu **nepatří**: geometrie pole (offsety,
odsazení), slučování stejných vektorů, monotónnost, skládání hran, pravidla
diagramu. To je logika, ne jazyk.

**Zkouška:** přidání jazyka je nový soubor v `jazyk/` a model parseru — ani jeden
řádek v jádře. **Protikladná zkouška:** `grep` na česká slova v `jadro/` nevrátí
nic (běží v CI, kap. 37).

> **Past, na kterou conBond2 narazil:** prohlížeč překládal **data**
> (`Trida=pomocny → Class=help`), takže výstup pole musí být označený `lang`
> a `translate="no"`. Jazyk profilu je jazyk textu, ne jazyk uživatelského
> rozhraní — jsou to dvě různé věci a smí se lišit.

## 7 · Dvě dědictví a co si z nich vzít

| | conBond | conBond2 |
|---|---|---|
| **základ** | graf entit a hran | aktivační pole tokenů |
| **abstrakce** | role, vztahy, pravidla | šablona = stejný vektor |
| **silné** | dosah, vzdálené vazby, dialog s tématem | poctivost, měřitelnost, švy |
| **slabé** | šlo vymyslet cestu odkudkoli kamkoli | pytel vět, žádné hrany |
| **co přenést** | graf, role, odvozování, paměť tématu | pole, šablony, monotónnost, etalon |

**Ani jeden neuměl to druhé.** conBond měl hrany, ale ne abstrakci nad tvarem
vět. conBond2 má šablony, ale odpovídá z pytle vět o osobě — a proto na „Kde byl
Jan uvězněn?" odpoví „Praha", protože Praha v tom pytli náhodou leží.

Celý tento návrh je to setkání.

## 8 · Tři zrna téhož kódu

Systém kóduje text na **třech zrnech** a na všech platí týž zákon: *stejné se
slučuje, rozdílné se rozlišuje, a co se slilo, nese své doložení.*

```
zrno        jednotka      abstrakce nad ním     co z toho plyne
─────────────────────────────────────────────────────────────────────
TOKEN       slovo         ŠABLONA               druh věty
            + aktivace    (stejný vektor)       „tohle je věta o narození"

VĚTA        tvrzení       HRANA                 fakt
            (kdo, co, čí) (predikát nad jmény)  „narodil(Jirásek, 1851)"

ENTITA      jméno         GRAF                  souvislost
            + doložení    (vážené sousedství)   „Hrabal ↔ Havel přes Koláře"
```

conBond2 má první řádek hotový, druhý vyrábí (`edges.py`, 163 hran) a třetí
používá jen na jednu otázku. **Nový systém je má propojit tak, že odpověď
prochází všemi třemi** (kap. 15).

## 9 · Vrstvy

```
┌─ PŘÍJEM ────────────────────────────────────────────────────────┐
│ text → jazyk → věty → rozbor → tokeny s aktivacemi              │
│ jediný klient parseru, zkratky scelené na jednom místě          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─ KÓDOVÁNÍ (referenční jazyk) ───────────────────────────────────┐
│ token   aktivace do vektoru, sítko rozhoduje co projde          │
│ věta    hrany (predikát, kdo, čí, doložení)                     │
│ entita  jméno scelené jedním pravidlem, varianty slité          │
│ rozměr  osy: čas, místo, počet, zařazení — každá jen ZNAČKUJE   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─ ABSTRAKCE ─────────────────────────────────────────────────────┐
│ šablony  slučování stejných vektorů                             │
│ matice   vážené vztahy mezi šablonami, s doložením              │
│ pravidla z definic (kopulová věta) i z faktů (indukce)          │
│ arita    kolik hodnot smí entita mít — MĚŘENO, ne zadáno        │
│ graf     vážené sousedství s doložením u každé hrany            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─ ODVOZOVÁNÍ ────────────────────────────────────────────────────┐
│ diagram  uzly = tvrzení a jejich negace, šipky = implikace      │
│          modus ponens · modus tollens · úplný rozbor            │
│ skládání term = base ∘ via, fixpoint                            │
│ rozměry  vylučují (nikdy nepotvrzují)                           │
│ tabulka  přiřazení s „právě jeden"                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─ ODPOVĚĎ ───────────────────────────────────────────────────────┐
│ druh · obsah · ŘETĚZ DOLOŽENÍ · míra jistoty · provenience      │
└─────────────────────────────────────────────────────────────────┘
```

## 10 · Subsystémy: pojmenovaní agenti, každý s jednou prací

Převzato z conBondu, kde se to osvědčilo — pojmenovaná věc se dá vypnout, změřit
a nahradit. Každý subsystém **jen značkuje**; rozhodování je jinde.

| id | oblast | práce |
|---|---|---|
| `AG-CHRONOS` | čas | datum, rok, událost narození a úmrtí, osa času |
| `AG-TOPOS` | místo | kde se to stalo; `NameType=Geo` proti `Giv/Sur` |
| `AG-METRON` | počet | kolik; a co počet **není** (řadové číslovky) |
| `AG-BIO` | životopis | definiční závorka: narození, úmrtí, místa |
| `AG-DRUH` | zařazení | jmenný přísudek — „kdo/co to je", i se záporem |
| `AG-SPEECH` | přímá řeč | kdo co komu řekl; rám uvozovací věty |
| `AG-MNEMOS` | paměť | co člověk řekl o sobě a o světě **v tomhle rozhovoru** |
| `AG-HERMES` | kanály | kudy odpověď ven — web, terminál, hlas, soubor |
| `AG-ROLES` | větné členy | 12 rolí z rozboru, tabulkou z profilu |
| `AG-NAMES` | jména | scelení, varianty, osoby proti dokumentům |
| `AG-KOREF` ✚ | koreference | zájmena a elipsy uvnitř textu (`G-11`) |

Pravidla, která platí pro každý z nich:

* **Jen značkuje.** Chronos řekne „tohle je čas", ne „tohle je odpověď".
* **Dá se vypnout.** A musí být měřitelné, co se tím ztratí.
* **Značka nese zdroj.** Aby šlo poznat, který subsystém se plete.
* **Mlčení je platný výstup.** Agent, který nic nenašel, není chyba (`INV-4`).

`AG-MNEMOS` stojí stranou: nepracuje s korpusem, ale s tím, co člověk řekl. Jeho
hrany mají jinou provenienci a jejich postavení řeší mřížka v kapitole 14.3 —
nikoli holé „přebíjejí".

## 11 · Švy

Jediná místa, kde se smí lišit implementace. Dnešních pět zůstává, čtyři
přibývají.

| id | šev | co za ním je | stav |
|---|---|---|---|
| `SEAM-1` | `ZdrojAktivaci` | odkud se berou atributy tokenu | ✓ |
| `SEAM-2` | `Uloziste` | odkud se čte a kam se píše | ✓ |
| `SEAM-3` | `SkladacVektoru` | jak se z okolí udělá vektor | ✓ |
| `SEAM-4` | `Slucovac` | kdy jsou dva vektory táž šablona | ✓ |
| `SEAM-5` | `Sitko` | co z kterého offsetu projde | ✓ |
| `SEAM-6` | `Hranovac` | jak se z věty stane hrana | dnes natvrdo |
| `SEAM-7` | `Rozmer` | jak se jev zakóduje na osu | čas hotov, místo ne |
| `SEAM-8` | `Jazyk` | tázací tvary, role, spojky, šablony odpovědí | dnes `cs.json` |
| `SEAM-9` ✚ | `Navrhovac` | statistický zdroj hypotéz (kap. 27) | chybí |

`SEAM-8` jako šev znamená, že angličtina je soubor, ne větev v kódu.
`SEAM-9` znamená, že dnešní síť jde vyměnit za jiný algoritmus bez zásahu do
architektury.

**Ke každému švu patří konformní testovací sada** — abstraktní testy, kterými
musí projít každá implementace za tím švem (`G-20`). Šev bez konformní sady je
jen jméno rozhraní.

## 12 · Identifikace věty: vzor, šablona, matice

Tohle je jádro odpovídání a conBond2 to nemá.

```
VZOR       jeden konkrétní vektor    jak vypadá TAHLE věta
ŠABLONA    třída stejných vektorů    druh vět, které vypadají takhle
MATICE     vztahy mezi šablonami     které druhy spolu souvisejí
```

### 12.1 Proč nestačí šablona sama

Otázka „Kde byl Jan uvězněn?" se přeloží na vzor. Ten se sotva kdy trefí na
šablonu **přesně** — otázka a odpověď mají jiný slovosled, jiný pád, jinou
osobu. Kdyby se hledala jen totožnost, systém by mlčel skoro vždy.

Proto matice: **šablona otázky ukazuje na šablony odpovědí**, a ten vztah se
buduje z dat, ne z pravidel.

```
Š(„Kde byl X uvězněn?")  ─┬─ 0,81 ─→  Š(„X byl uvězněn v <místo>")
                          ├─ 0,62 ─→  Š(„<místo>, kde X seděl")
                          └─ 0,44 ─→  Š(„X strávil ve vězení <čas>")
```

### 12.2 Jak matice vzniká

Tři nezávislé zdroje, každý s vlastní vahou a **vlastním doložením**:

1. **Sdílené kotvy.** Dvě šablony, jejichž věty opakovaně mluví o týchž entitách
   a týchž hodnotách, spolu souvisejí. Čistě pozorovatelné, bez jazykové
   znalosti.
2. **Společná hrana.** Šablona A vyrábí `uvěznit(kdo, kde)` a šablona B taky —
   pak jsou to dva způsoby, jak říct totéž. Hrana je společný jmenovatel různých
   formulací.
3. **Dialog.** Člověk potvrdí nebo opraví: „ne, tohle je o něčem jiném."
   Nejdražší zdroj, ale nejpřesnější — a musí být vidět, které vazby odtud
   pocházejí.

Matice je **řídká a vážená**, drží se jen nad prahem z registru (kap. 29)
a každá vazba nese počet dokladů. Bez počtu se nedá poznat vazba z tisíce vět od
vazby z jedné.

### 12.4 Proč slučování nesmí zůstat u přesné shody

Slučování stejných vektorů (`SEAM-4`) je dnes **totožnost**, a to má měřený
strop. Na sondě conBondu2 vyšel poměr šablon ke slovům takto:

```
r = 0   51/75 = 0,68      r = 2   75/75 = 1,00   ← každé slovo vlastní šablona
r = 1   71/75 = 0,95      r = 3   75/75 = 1,00
```

Od poloměru 2 se nesdílí nic. Příčina není v počtu atributů, ale v tom, že
**dlouhý diskrétní popis porovnávaný na přesnou shodu se rozpadne na samé
jednoprvkové třídy**. Ubrat atributy posune strop, neodstraní ho.

Řez vede jinudy: atributy dnes tvoří plochý seznam nezávislých bitů, ve
skutečnosti tvoří **svaz**. `Case=Nom` a `Case=Acc` jsou si blíž než `Case=Nom`
a `VerbForm=Inf`; `NOUN`, `PROPN` a `PRON` jsou jmenné; `obj`, `iobj` a `obl`
jsou argumenty. Když má šablona **metrickou strukturu** — dvě šablony jsou
shodné z 85 % — přestanou být drobné morfologické rozdíly fatální.

Tři důsledky pro tento návrh, každý s vlastním místem:

* **Hierarchie atributů patří do profilu jazyka** (`SEAM-8`) jako nadřazenost,
  ne do kódu jako `if`.
* **Váhy se měří, nezadávají** — informační zisk atributu je vlastnost dat
  (smyčka 3, kap. 21). `Gender` a `Case` rozlišují i tam, kde se rozlišovat
  nemá; `VerbForm`, `Aspect` a zařazení nesou význam.
* **Pole se nemusí porovnávat celé najednou.** Rozdělit je na nezávislé pohledy
  (syntaktický, morfologický, sémantický, lexikální), spočítat shodu v každém
  zvlášť a skládat až výsledky — táž zásada jako `INV-14`: pohled nepřidává, jen
  jinak čte. Je to otevřená otázka `Q-9`, ne rozhodnutí.

### 12.3 Co tím systém získá

```
dnes:   otázka → slova → věty, kde ta slova leží  (pytel)
nově:   otázka → vzor → šablony → věty toho DRUHU (třída)
```

Rozdíl je vidět přesně na tom selhání: v pytli vět o Nerudovi Praha leží. Ve
třídě vět o **věznění** Neruda není, a odpověď je mlčení.

## 13 · Rozbor: UDPipe jako lexikální nástroj

Systém si morfologii ani syntax nevymýšlí — dostane ji z **UDPipe 2**, který se
přebírá z conBondu2 i s ověřenou kombinací verzí.

```
model      cs_all-ud-2.17-251125          (další jazyky = další model)
běh        lokálně, offline, vlastní proces
klient     JEDEN v celém systému
```

Čtyři pravidla, každé zapsané po chybě:

1. **Jediný klient.** Klienti bývali dva a lišili se v tom, co dělají se
   zkratkami — korpus měl „R.U.R." rozsekané na tři tokeny a otázka scelené.
   Obojí dál fungovalo a jen mluvilo o jiném slově.
2. **Scelování na chokepointu.** Zkratky, spojovníky a víceslovná jména se řeší
   na jednom místě, ne v každém volajícím.
3. **Rozbor je klient jádra, ne jeho závislost.** Jádro dostane hotové tokeny.
   TensorFlow a transformers patří k přípravě dat; samotné odpovídání musí běžet
   bez nich.
4. **Neznámá aktivace se hlásí.** Tiše zakládat sloupce znamená, že si uživatel
   překlepem rozšíří atributový prostor, aniž o tom ví.

Model je **jazykový profil v jiné podobě**: přidat angličtinu znamená anglický
model plus `jazyk/en.json` — ani řádek v jádře.

**Výpadek UDPipe je definovaný stav, ne pád** (kap. 35.3): systém odpoví
„nepodařilo se rozebrat", nikoli prázdným polem (`INV-9`).

## 14 · Vstupní jazyk, normalizace a provenience

Kapitola vzniká proto, že návrh 1.0 tyhle věci požadoval, ale nenavrhoval
(`G-8`, `G-9`, `G-5`, `G-6`, `G-7`).

### 14.1 Tři vstupní varianty, dva profily

| kód | co to je | jak se řeší |
|---|---|---|
| `cs` | čeština s diakritikou | profil `cs.json` |
| `cs-x-nodia` | čeština bez diakritiky | **normalizace na `cs` před rozborem** |
| `en` | angličtina | profil `en.json` |

Doplnění diakritiky je **předzpracování v příjmu, ne schopnost jádra**. Je
jazykově závislé, takže patří k profilu a jeho slovníku, ne do kódu. Nejistá
místa se nesou dál jako varianty, ne jako rozhodnutí — a když varianta mění
entitu, systém se doptá (kap. 19).

Detekce jazyka je **klient**, ne jádro. Jádro dostane text i s určeným jazykem;
když si klient není jistý, pošle to jako otevřenou otázku, ne jako fakt.

### 14.2 Normalizace hodnot

Rozměry (`SEAM-7`) neumí porovnávat, dokud hodnoty nemají jednotný tvar:

* **datum a čas** — rozsahy, přibližnosti („kolem roku 1850", „ve 40. letech"),
  neúplná data (jen rok), letopočet před naším letopočtem,
* **počet** — číslovky slovem, rozsahy, řádové odhady,
* **jednotky** — převod na kanonickou jednotku, s poznámkou o zaokrouhlení,
* **jméno** — scelení variant jedním pravidlem (`AG-NAMES`).

Každá normalizace nese **původní tvar** vedle kanonického. Bez toho nelze
odpověď formulovat slovy textu a nelze zpětně poznat chybu převodu.

### 14.3 Mřížka provenience

Návrh 1.0 měl na tomhle místě rozpor: `INV-5` říká „spor se hlásí, nepřepisuje",
zatímco MNEMOS „přebíjí korpus". Obojí zároveň nejde. Rozhodnutí:

```
úroveň   zdroj                     v konfliktu s nižší
──────────────────────────────────────────────────────
4        oprava od člověka         PŘEBÍJÍ, ale spor se ZAZNAMENÁ a je vidět
3        definice od člověka       přebíjí odvozené, ne doložené
2        doložené v korpusu        spor mezi dvěma doloženými = HLÁŠENÍ (INV-5)
1        odvozené pravidlem        ustupuje čemukoli doloženému
0        hypotéza                  nikdy nevstupuje do odpovědi (kap. 25)
```

Čtení: **přebití není přepsání.** Staré tvrzení nemizí, jen ustupuje; v detailu
odpovědi je vidět obojí i to, kdo a kdy přebil. Spor mezi dvěma zdroji **téže**
úrovně se nikdy neřeší tichou volbou.

### 14.4 Identita a odvolatelnost

MNEMOS a vzkazy předpokládají, že systém ví, s kým mluví. Návrh 1.0 to nikde
nezavádí (`G-6`). Minimum:

* **Účastník** je entita jako každá jiná, se svými variantami jména.
* **Fakt od člověka nese, čí je** a v jaké relaci vznikl.
* **Bez identity se nehádá.** „Mám rád knedlíky" bez známého mluvčího je otázka
  zpět, ne uložený fakt.

Odvolatelnost (`INV-12`) vyžaduje, aby každá odvozená hrana nesla **seznam
premis**. „Zapomeň, co jsem říkal o X" pak není mazání jednoho záznamu, ale
uzavření tranzitivního obalu — a odvozené hrany, které přišly o premisu,
zanikají spolu s ní.

### 14.5 Úložiště

`SEAM-2` je rozhraní; za ním musí být implementace se čtyřmi vlastnostmi
(`G-1`, `G-2`, `G-3`):

* **Snímek.** Celý stav báze jde zmrazit a obnovit — bez toho není
  experimentální vrstva (kap. 26) ani reprodukovatelné měření.
* **Verze schématu.** Uložený stav nese verzi; načtení staršího je buď migrace,
  nebo jasné odmítnutí, nikdy tiché přeskočení neznámých polí.
* **Verze dat.** Korpus, profil a etalon mají identifikátor, který se objeví
  v každém naměřeném čísle. Číslo bez verze dat není měření.
* **Záloha a obnova.** Popsaný postup, ne implicitní kopie adresáře.

Formát je otevřená otázka `Q-2`; požadavky výše platí pro každou volbu.

### 14.6 Odvozování: líné, nebo materializované

Rozhodnutí, které v návrhu 1.0 chybělo a na kterém visí výkon, odvolatelnost
i experimentální vrstva (`Q-1`). Řez nevede podle vrstvy, ale **podle
provenience premis**.

```
úroveň premis          režim              kde odvozené žije
──────────────────────────────────────────────────────────────────────
2  vše doložené v korpusu   MATERIALIZOVANÉ   oddělená odvozená vrstva
1  odvozené z korpusu       MATERIALIZOVANÉ   táž vrstva, dál ve fixpointu
3–4 cokoli z dialogu        LÍNÉ              nikde; počítá se na dotaz
0  hypotéza                 neodvozuje se     do odpovědi nevstupuje
```

**Pravidlo jednou větou:** *odvozuje se dopředu právě tehdy, když jsou všechny
premisy z korpusu; jakmile mezi ně vstoupí věta z dialogu, počítá se to až na
dotaz.*

**Proč korpus dopředu.** Ten průchod už v návrhu je, jen se mu neříká
materializace: trojice `doklad / navíc / spor` (`C-2`) se nedá spočítat jinak
než tak, že se pravidlo projede přes celý korpus a výsledek porovná s doloženými
hranami. Dnes se výsledek po změření zahodí. Nechat si ho stojí navíc jen místo
a vyřeší tím tři věci naráz:

* **smyčka 2** (kap. 21) má nad čím pracovat — učit se lze jen nad tím, co je
  zakódované,
* **spor** (`INV-5`) vyskočí při učení, tedy tam, kde ho lze nahlásit; při línem
  odvozování by se ozval jen tehdy, kdyby se někdo náhodou zeptal zrovna na to,
* **odpověď se nepočítá dvakrát** — fixpoint `praděd` běží při učení, ne při
  každém dotazu.

**Proč dialog líně.** Fakt od člověka je krátkodobý, opravitelný a musí být
odvolatelný do dalšího tahu (`INV-12`). Materializace by z každého „zapomeň, co
jsem říkal o X" udělala kaskádu; při línem počítání zmizí odvozené samo, protože
nikdy neexistovalo. Objem je navíc nepatrný, takže fixpoint nad desítkami faktů
je zdarma.

**Vlastnosti odvozené vrstvy.** Odvozené hrany jsou *odvozenina, ne stav*:

* žijí ve **vlastní vrstvě**, ne mezi doloženými — tím je `INV-3` splněný
  fyzicky, ne disciplínou,
* nesou **index premis**, aby šly zneplatnit adresně,
* smějí se **kdykoli zahodit a přepočítat**; snímek báze je nemusí obsahovat,
  protože doložené hrany plus pravidla jsou totéž s menší entropií,
* **přepočet je součást povýšení** v experimentální vrstvě (kap. 26) — mimo něj
  se produkční odvozená vrstva nemění (`INV-10`),
* **hloubka fixpointu má registrovaný práh** (kap. 29), stejný pro oba režimy.

**Co se materializuje mimo hrany.** Matice šablon, graf entit a indexy pole jsou
měřené artefakty — stavějí se při příjmu a jsou součástí snímku, protože jejich
přepočet je drahý a jejich vstup (korpus) se mění zřídka. Naproti tomu **rozměry
a arita se dopředu jen měří, ale vyhodnocují se líně**: změřit, že otcovství je
jednohodnotové, stojí jeden průchod; vypsat všechny vyloučené dvojice by stálo
*n²* a skoro nikdy se na ně nikdo nezeptá. **Diagram (`C-3`, `C-4`) a přiřazovací
tabulky (`C-7`) jsou vždy líné** — úloha vzniká z otázky a do báze nepatří.

### 14.7 Zmínka jako atomická jednotka

Mezi textem a entitou musí stát třetí objekt, jinak fakt nese jméno a patří
všem, kdo se tak jmenují. Doloženo měřením z conBondu: `bydlet{kdo: Josef}`
patřilo **všem osmnácti Josefům** a tatáž díra působila tři různé poruchy —
slití 27 Karlů do jedné osoby, váhy nositelů v poměru 1:1 a zúžení podle otázky,
které nezúžilo nic. Tři poruchy, jedna příčina.

```
ZMÍNKA    výskyt jména na konkrétním místě (dokument, věta, povrch)
          NEMĚNNÉ POZOROVÁNÍ — text se nemění, tedy ani zmínka
ENTITA    uzel s trvalým identifikátorem
          HYPOTÉZA nad zmínkami — smí se přepočítat, aniž se hne text
```

**Fakt nese odkaz na zmínku, ne jméno.** Bez toho se váha nositele, překryv
sousedů ani zúžení podle otázky nedají spočítat poctivě — počítaly by se přes
aliasy a všem jmenovcům by vyšly stejné.

**Rozřešení má tři stavy, ne dva** (`resolved` / `ambiguous` / `unresolved`).
Kdyby existovalo jen „navázáno / nenavázáno", muselo by se u dvou stejně dobrých
kandidátů jedno tiše vybrat — a to je `INV-5`. Ke každému rozřešení patří
**doklad** (odkud to plyne: diskurz, dokument, rozpad jména), protože rozřešení
je nejlepší známé vysvětlení, ne pravda; bez dokladu ho nelze přepočítat při
změně pravidel.

**Sloučení entit je hrana, ne přepis.** `A --same_as--> B` se přidá, uzel se
nikdy nemaže. Jinak zmizení uzlu nejde odlišit od rozbité stavby a identita
přestane být vratná. Zánik uzlu má proto **čtyři vysvětlení, ne dvě**: sloučeno ·
zrušeno · bez opory v datech · **nevysvětleno**. Teprve tím dostane poslední
kategorie ostrý význam — uzel zmizel, ale fakty ho dál nesou.

---

# ČÁST II · ODVOZOVÁNÍ A ODPOVÍDÁNÍ

## 15 · Zákon skládání

```
šablona  řekne  KTERÉ VĚTY se ptáme        (druh)
hrana    řekne  CO se v nich tvrdí         (obsah)
graf     řekne  KTERÁ z nich patří k otázce (zaměření)
```

Na příkladu, na kterém conBond2 selhal:

```
Kde byl Jan uvězněn?
  šablona:  věty tvaru „<osoba> byl uvězněn v <místo>"
  hrany:    uvěznit(kdo, kde) — žádná s Janem
  graf:     hrana Jan–Praha u události věznění neexistuje
  ⇒ MLČENÍ, a je to správná odpověď
```

conBond2 odpoví „Praha", protože se ptá jen na to, jestli slovo leží ve stejném
dokumentu.

## 16 · Logické schopnosti

Seřazeno podle toho, co která potřebuje. **Všechny vracejí řetěz doložení**
(`INV-2`) — bez toho je odvozování jen rychlejší způsob, jak si vymyslet
odpověď.

### C-1 · Přímý zásah
Šablona najde věty téhož druhu, hrana z nich vytáhne tvrzení.
*Potřebuje:* šablony, hrany. *Vrací:* větu.

### C-2 · Skládání vztahů
`tchán = otec ∘ (manžel | manželka)`, fixpoint (`praděd` až po `dědovi`).
Pravidla ze **dvou zdrojů**: definiční věta („Tchán je otec manžela") a
**indukce z faktů** — kde se složená cesta opakovaně kryje s doloženou hranou,
je to pravidlo.
*Potřebuje:* hrany, slučování jmen. *Vrací:* řetěz hran.

Tři čísla, ne jedno skóre:

```
doklad   složená cesta trefila doloženou hranu
navíc    cesta dala hranu, kterou korpus nedokládá   ← NENÍ chyba
spor     cesta si odporuje s doloženou hranou
```

`navíc` není chyba, protože pole je monotónní (`INV-1`). Kdyby vstupovalo do
rozhodování, každé pravidlo by nad neúplným korpusem propadlo.

### C-3 · Výroková dedukce (šipkový diagram)
Uzly jsou tvrzení a jejich negace, šipky implikace.

```
modus ponens   p ⇒ q, p platí    ⇒ q platí
modus tollens  p ⇒ q, q neplatí  ⇒ p neplatí
```

Modus tollens je ten podstatný — dopředným čtením se z úlohy vyčte polovina.
Spor se **hlásí, nepřepisuje** (`INV-5`).

### C-4 · Úplný rozbor případů
Když není dáno nic a přesto něco plyne. Vyzkoušet všechna ohodnocení je úplné
tam, kde je propagace jen rychlá; cenou je 2^n, takže strop z konfigurace
a poctivé „neumím" místo hodinového počítání.

### C-5 · Vylučování rozměrem

```
čas       intervaly se nepřekrývají  ⇒ NE     překrývají se  ⇒ nic
místo     v týž čas jinde            ⇒ NE     totéž místo    ⇒ nic
počet     tři ≠ dvacet               ⇒ NE     shoda          ⇒ nic
zařazení  ryba a savec se vylučují   ⇒ NE     obojí zvíře    ⇒ nic
```

**Rozměr umí vyvracet, ne potvrzovat.** Pravá strana je vždycky prázdná. A rozměr
sám netvrdí, která značka znamená „nemožné" — jen dvojici označí, a **rozhodne
měření** nad doloženými dvojicemi. Jinak je to zapečený axiom o patro níž.

### C-6 · Výlučnost atributu (arita)
Kolik hodnot smí entita mít, se **měří z dat**: nemá-li v korpusu nikdo dva otce,
je otcovství jednohodnotové. Tvrzení si tím nese vlastní okolí — z
`otec(Karel, Petr)` plyne `¬otec(kdokoli jiný, Petr)`, aniž to kdo psal.

Jedinečnost sedí na **druhém konci hrany**: jedno dítě má jednu matku, jedna
matka může mít dětí kolik chce.

### C-7 · Přiřazovací úlohy
„Právě jeden" je součin, a takový uzel diagram nemá. Vlastní struktura: tabulka
osob × kategorií s omezeními `je / není / spolu / nikdy`. Vrací **všechna**
řešení — úloha se dvěma vypadá při vracení prvního jako vyřešená.

### C-8 · Odstupňované tvrzení
Dnešní systém odpovídá {ano, ne, nevím}. To je poctivé, ale je to podlaha.
Přibývá **`podepřeno`**: víc nezávislých cest, spočítaných, s řetězem.

```
doložené    věta to říká                     TVRZENÍ
odvozené    pravidlo to složí, s řetězem     TVRZENÍ
podepřené   n nezávislých cest               PREFERENCE, ne tvrzení
vyloučené   rozměr to vylučuje               TVRZENÍ
nevím       nic z toho                       PŘIZNÁNÍ
```

Podmínka, bez které to sklouzne do hádání: **podepřená odpověď se musí lišit
slovy**, ne jen v detailu, a musí jít rozbalit na svůj řetěz.

### C-9 · Abdukce
„Co by to vysvětlovalo?" — z `q` a `p ⇒ q` navrhnout `p`. Je to neplatný úsudek
a musí být **označený jako hypotéza** (kap. 25). Cena je v tom, že navrhne, co
ověřit — ne v tom, že odpoví.

### C-10 · Defeasibilita a specifičnost
„Ptáci létají; tučňák ne." Obecné pravidlo platí, dokud ho nepřebije
konkrétnější. Specifičnost = **hloubka ve svazu podtříd**, výjimky = záporné
hrany (`Typ=druh_ne`).

Tohle je schopnost, která chybí na úlohy typu „Kde bys našel lišku?" —
`liška ⊂ divoké zvíře ⇒ obvykle žije v přirozeném prostředí`, a „kurník" je
výjimka, ne protipříklad.

**Nevyřešeno:** odkud svaz podtříd je (`G-10`, `Q-3`). Bez odpovědi na to je
`C-10` nespustitelná.

### C-11 · Kódování úlohy z volného textu
Najít v zadání atomární výroky, vyloučit ty „navíc", zapsat složené výroky
spojkami. Dnes se úloha zadává ručně — tohle je ta chybějící část (kap. 20.4).
*Potřebuje:* šablony, `AG-ROLES`, profil spojek. *Vrací:* zadání v referenčním
jazyce, i s tím, které slovo se stalo kterým výrokem.

### C-12 · Negace složených výroků
De Morgan a spol.: `¬(p ∧ q) ⇔ ¬p ∨ ¬q`, `¬(p ⇒ q) ⇔ p ∧ ¬q`,
`¬(p ⇔ q) ⇔ (p ∧ ¬q) ∨ (q ∧ ¬p)`, `¬∀x p(x) ⇔ ∃x ¬p(x)`.

Šev tu vede přesně: **pravidla negace jsou logika a patří do jádra**, kdežto
**tvary negace jsou jazyk** („není pravda, že", předpona `ne-`, záměna „je" za
„není") a patří do profilu (`SEAM-8`). Bez toho řezu by se do jádra vrátila
čeština.

### C-13 · Třídy a kvantifikované výroky
„Všichni A jsou B", „někteří A jsou B", a co z toho plyne. Vennův diagram je
**svaz podtříd nakreslený**, takže tohle je táž struktura jako `C-10` viděná
z druhé strany.

Podstatné je, co se z něj **nedá** vyčíst: z „všechny lichoběžníky jsou
čtyřúhelníky" a „všechny rovnoběžníky jsou čtyřúhelníky" **neplyne** vztah mezi
lichoběžníky a rovnoběžníky. Prázdná oblast je doložená neslučitelnost, oblast
bez značky je `INV-1` — nevím, ne neplatí.

### C-14 · Sebereferenční ohodnocení mluvčích
Úlohy typu „padouši a poctivci": pravdivost výroku je svázaná s typem toho, kdo
ho vyslovil — `mluvčí je pravdomluvný ⇔ jeho výrok platí`.

Rám poskytuje `AG-SPEECH` (kdo co komu řekl), samotná ekvivalence je **kódovací
pravidlo v profilu úlohy, ne větev v jádře**. Tím se schopnost přidává daty,
což je zkouška, že kap. 2 bod 2 platí i tady.

## 17 · Aproximace

Systém se nesmí zastavit na tom, co je doložené. Musí umět **přiblížit se** —
a přiznat, že se přiblížil.

| způsob | jak | míra |
|---|---|---|
| **tvarová** — přes šablonu | nejbližší šablona v matici místo přesné shody; „Kde se narodil X?" a „X pochází z <místo>" nejsou totéž, ale odpověď leží ve stejném poli | váha v matici |
| **skládaná** — přes vztah | chybí-li přímá hrana, složí se z existujících: `tchán = otec ∘ manžel` | délka řetězu a nejslabší článek |
| **typová** — přes zařazení | co platí o třídě, platí obvykle o členu | vzdálenost ve svazu; přebíjí ji konkrétnější pravidlo (`C-10`) |

Všechny tři vracejí **odstupňované tvrzení** (`C-8`), ne holé „ano" — a formulace
se musí lišit slovy, ne jen v detailu.

## 18 · Tvar odpovědi

Každá odpověď je záznam s pěti povinnými poli:

```
druh          doložené · odvozené · podepřené · vyloučené · nevím · doptání
obsah         věta v jazyce vstupu, ze šablon profilu (SEAM-8)
řetěz         rozbalitelné doložení až k větám a premisám      (INV-2)
míra          podle druhu; nikdy holé číslo bez řetězu
provenience   úroveň z mřížky 14.3, s tím kdo a kdy
```

**Zdůvodnění je výchozí, ne volitelné.** Pod každou odpovědí je sbalená
informace o zdroji dat a rozhodovací metodě; rozbalení ukáže celý řetěz. Ve
webové konzoli lze zobrazení vypnout — **obsah odpovědi se tím nemění**, jen se
skryje. Vypnutí zdůvodnění nikdy nezmění, co systém odpoví.

### 18.1 Řetěz má druhy — nevynucovat jeden fakt

`INV-2` žádá řetěz, ne jeden zdroj. Vynutit vazbu odpověď → jeden fakt je
**falešná jednoduchost**: mnoho poctivých odpovědí je syntéza a mačkat ji do
jednoho záznamu znamená vyrobit fakt, který v textu nikdy nestál.

```
JEDEN FAKT        odpověď ← jeden doložený fakt
SLOŽENÁ      odpověď ← {tvrzení₁, tvrzení₂, …} + pravidlo, které je spojilo
JEN DOLOŽENÍ odpověď ← úsek textu, ze kterého ještě není vytažen fakt
```

Třetí stav není chyba, je to přiznání: *doklad mám, atomizaci ne*. Odlišuje se
od `nevím` (nemám nic) — jsou to různé budoucí úkoly.

Měří se proto **pokrytí vysvětlením**, ne podíl odpovědí s jedním faktem:

```
M-8  pokrytí vysvětlením = jeden fakt + složená + jen doložení / všechny odpovědi
     cíl 100 %; NIKOLI 100 % odpovědí s jediným faktem
```

Pozor na pojmy: *determinismus* je vlastnost běhu (kap. 5 — táž data a táž
otázka dají tutéž odpověď), *vysvětlitelnost* je vlastnost odpovědi. Návrh 1.0
je slučoval pod jeden nadpis (`G-26`).

## 19 · Dialog s člověkem

Systém není vyhledávač s okénkem. Rozhovor je **rovnocenný zdroj pravdy** vedle
korpusu (s postavením podle mřížky 14.3) a musí umět všechno, co člověk
v rozhovoru běžně dělá.

### 19.1 Co má rozumět

```
OTÁZKA NA OBSAH      Kde se narodil Hrabal?          → pole
OTÁZKA NA VZTAH      Je Krakatit dílo?               → znalost
OTÁZKA NA SOUVISLOST Mohl Čapek znát Němcovou?       → graf + rozměr
TVRZENÍ              Krakatit je román.              → nová hrana
OPRAVA               Ne, Jan byl uvězněn v Machaeru. → úroveň 4, spor se zapíše
DEFINICE             Tchán je otec manžela.          → nové pravidlo
OSOBNÍ FAKT          Mám rád knedlíky.               → mnemos, s identitou
VZKAZ                Vyřiď Jindrovi, že přijdu.      → schránka
NAVÁZÁNÍ             Čí?  ·  A kdy?  ·  A on?        → elipsa z tématu
METAOTÁZKA           Odkud to víš?  ·  Co víš o X?   → řetěz doložení
SPOLEČENSKÉ          Dobrý den. · Děkuju.            → odpověď, ne rozbor
```

### 19.2 Zapamatování faktu od uživatele

Co člověk řekne o sobě nebo o světě, se uloží s vlastní proveniencí. Tři
vlastnosti, které to musí mít:

1. **Má postavení, ne přednost.** Oprava ustupuje jen doloženému sporu, který se
   zaznamená a je vidět. Staré se nemaže.
2. **Ví, čí to je.** Bez identity (kap. 14.4) se fakt neukládá — systém se radši
   zeptá, než hádá.
3. **Je odvolatelné.** „Zapomeň, co jsem říkal o X" musí jít, včetně všeho, co
   se z toho odvodilo (`INV-12`).

Naučené hrany vstupují do **téhož** odvozování jako korpusové: pravidla z faktů,
arita i diagram na ně platí stejně. To je celý smysl jednoho referenčního jazyka.

### 19.3 Vyřizování vzkazů

Vzkaz je fakt s **adresátem a časem doručení**. Systém ho přijme, potvrdí
a doručí, až se adresát ozve.

```
uloz:    „Vyřiď Jindrovi, že přijdu v pátek."
         → vzkaz(od=já, komu=jindra, co=…, kdy=…)
doruc:   Jindra se přihlásí → „Máš vzkaz od Honzy: …"
```

Zásada, která to drží při zemi: **vzkaz se nedoručuje odhadem.** Když není jisté,
kdo je „Jindra", systém se doptá — stejně jako u jmen v korpusu. Špatně doručený
vzkaz je horší než nedoručený.

Čas doručení je systémový čas s časovým pásmem, ne textový čas z `AG-CHRONOS`;
jsou to dvě různé osy a nesmí se sloučit (`G-9`).

### 19.4 Metaotázky jsou plnohodnotné

„Odkud to víš?" musí umět odpovědět vždycky, protože každá odpověď nese řetěz.
To není luxus — je to jediná obrana proti tomu, aby se odvozené vydávalo za
doložené (`INV-3`).

```
Kde se narodil Hrabal?  →  Židenice
Odkud to víš?           →  věta 14 dokumentu bohumil_hrabal, agent Bio,
                           definiční závorka, `Udal=narozeni`
```

### 19.5 Elipsa bez zvláštního mechanismu

Navazující otázka nemá vlastní mechanismus — **předchozí odpověď se stane
aktivací** a zúží pole jako každý jiný signál. Ověřeno: „Kdo je Ježíš?" → „Syn
Boží"; „Čí?" pak svítí slovy `syn` a `boží` a pole klesne z 557 vět na 34.

Podmínka: doplňuje se **jen** u otázky, která sama nic nenese. Jinak by si
předchozí odpověď táhla do všech dalších otázek.

**A tady je měřená mez, kterou návrh 1.0 nezná.** Když navazující otázka nese
vlastní slova, ale ne vlastní entitu, elipsa přestane fungovat — a to opačně,
než by člověk čekal:

| doptání | co svítí po tahu | odkud přišla odpověď |
|---|---|---|
| „Co napsal?" | `čapek, karel` | ✓ z Čapka |
| „Co za **díla** napsal?" | `napsat, dílo` | ✗ od jiného autora |
| „Jak se **jmenovala celým jménem**?" | `jmenovat, jméno` | ✗ z jiného textu |

Změřeno: odpověď přišla ze stejného dokumentu **2 z 6**. Příčina není chybějící
paměť tématu — téma systém má. Příčina je, že **téma a otázka leží v jednom
pytli a sčítají se**, takže čím přesněji se člověk doptá, tím jistěji si téma
utopí vlastními slovy.

Z toho plyne konstrukční pravidlo: **téma je omezení, ne další signál.** Při
doptání bez vlastní entity se jím zúží množina uvažovaných dokumentů *před*
výběrem; do skóre nevstupuje. A protikladná podmínka: téma nesmí přežít, když
člověk odejde jinam.

Čtyři varianty, které se v conBondu zkusily jako *signál v pořadí*, byly všechny
zamítnuty měřením (2/6 → 2/6, jedna 3/6 za cenu propadu etalonu o třináct
řádků). Poučení je obecné: **fokus a zarovnání otázky si konkurují**, a přidávat
další pozici do řadicí kaskády je hádání. Buď filtr před kaskádou, nebo učení
vah na doložených tazích — nic mezi.

Poznámka k volbě nástroje: vektorový popis by tuhle vadu nevyřešil, jen by tytéž
dvě věci mísil jinak. Chybí **separace**, ne kapacita.

## 20 · Pohledy nad daty

### 20.1 Uložené proti odvozenému

Systém má dvě třídy objektů a jejich rozlišení rozhoduje o tom, co je část
programu a co není:

```
ULOŽENÉ    dokument · věta · zmínka · entita · hrana · šablona · pravidlo
           vzniká příjmem a učením, leží v bázi, nese provenienci

ODVOZENÉ   POHLED — vzniká výpočtem nad uloženým a neukládá se
           profil entity · vyprávění · osa času · cesta A→B · srovnání ·
           řešení logické úlohy · boolovský výběr vzorů · okna /view
```

> **`INV-14` — pohled nic nepřidává.** Pohled nesmí zavést fakt, hranu ani
> pravidlo, které v bázi není. Smí jen vybírat, spojovat a zobrazovat.
> Potřebuje-li pohled něco, co v datech není, je to **nález o datech**, ne
> důvod to do pohledu dopsat.

Z toho plyne pravidlo, které rozhoduje o členění kódu:

**Pohled není součást programu, je to způsob čtení téhož kódu.** Nemá vlastní
bázi, vlastní pravidla ani vlastní jazyk. Kdyby je měl, přestal by být pohledem
a stal by se druhým systémem vedle prvního — se dvěma místy, kde může být chyba,
a s `if` podle toho, který se právě použil (kap. 2, důsledek 2).

Praktický důsledek pro adresáře: v `jadro/` **nevzniká složka na pohledy**.
Výpočet pohledu je funkce nad uloženými objekty; kde má vzniknout výstup, je
věcí klienta (kap. 5, kap. 32).

### 20.2 Boolovské operace nad vzory

Šablona je třída vektorů, tedy **množina**. Nad množinami platí algebra a ta se
nikam neprogramuje — je to totéž vybírání, jen zapsané spojkami:

```
Š(A) ∩ Š(B)   věty, které patří do obou tříd
Š(A) ∪ Š(B)   věty některé z tříd
Š(A) \ Š(B)   věty první třídy, které nejsou v druhé
¬Š(A)         doplněk v poli  ← jediný, který potřebuje pozornost
```

Doplněk je `INV-1` v jiném hávu: `¬Š(A)` znamená „věty, které do třídy A
nepadly", **ne** „věty, o kterých je doloženo, že do A nepatří". První je
operace nad polem, druhé je tvrzení o světě. Pohled smí to první a nikdy z toho
nesmí udělat druhé.

Táž algebra platí o patro výš — nad hranami, rozměry a šablonami v matici.
Průnik zúží, sjednocení rozšíří, rozdíl vyloučí. **Není to nová schopnost, je
to zápis toho, co `C-1`–`C-7` dělají.** Boolovský výběr proto nemá vlastní
`C-n`: je to jazyk, kterým se pohledy skládají, ne další motor pod nimi.

### 20.3 Logická úloha je pohled, ne modul

Referenční rámec: **Bartlová, H. (2014): *Metody řešení slovních úloh pomocí
logiky.* Bakalářská práce, PedF UK.** Práce popisuje šest metod řešení úloh
z výrokové logiky a každou předvádí na řešených příkladech se známou odpovědí.
V dokumentu se na ni odkazuje jako **[B]** s číslem kapitoly.

**Řešení logické úlohy není samostatná část programu.** Je to pohled, ve kterém
se totéž kódování promítne na pravdivostní osu: atomární výrok je uzel, spojka
je hrana, ohodnocení je průchod. Tabulka, strom, diagram a Vennův obrazec jsou
čtyři způsoby, jak tentýž průchod nakreslit — ne čtyři motory.

Dva důvody, proč to trvat na tomhle stojí za to:

* **Kdyby to byl modul, měl by vlastní zadání.** Vznikl by druhý formát „úloha",
  druhý parser, druhá pravidla negace — a systém by měl dvě verze téhož, které
  se rozejdou tiše (přesně vada, kterou v conBondu způsobili dva klienti
  parseru, kap. 13).
* **Slovní úloha je nejpřísnější zkouška věty z kapitoly 2.** Nemá korpus, za
  který by se dalo schovat: buď je zadání zakódované správně, nebo úloha
  nevyjde. A odpověď je známá dopředu, takže se nedá vydávat ukázka za výsledek
  (kap. 42).

Za pozornost stojí terminologická shoda: [B, 1.2] popisuje etapu transformace
jako převod slovně zadaného problému do vhodného znakového systému a ten systém
nazývá **referenčním jazykem**. To je přesně pojem, na kterém stojí celý tento
návrh. Didaktika řešení úloh a architektura tohoto systému mluví o téže věci.

### 20.4 Tři etapy jako tři čtení téhož

[B, 1.2] přebírá od Novotné trojici etap. Ani jedna nepotřebuje nový aparát:

```
UCHOPOVÁNÍ    najít objekty a vztahy, vyloučit ty „navíc"
              → příjem a kódování (kap. 9), AG-ROLES, šablony

TRANSFORMACE  atomární výroky, složené výroky, spojky, negace
              → C-11 kódování · C-12 negace · referenční jazyk (kap. 2)

NÁVRAT        odpověď větou v kontextu zadání
              → tvar odpovědi (kap. 18), šablony z profilu (SEAM-8)
```

Nejsnáz se zapomene na **návrat**. Systém, který vrátí ohodnocení `a=0, b=1,
c=1`, úlohu nevyřešil — odpověď zní „pachatelem je žák C" a musí nést řetěz
k větám zadání, ne k řádkům tabulky.

### 20.5 Metody jako pohledy

| metoda | [B] | čím je v systému | stav |
|---|---|---|---|
| tabulka pravdivostních hodnot | 4.1 | pohled: úplný rozbor (`C-4`) | ✓ |
| Quineův algoritmus | 4.2 | tentýž rozbor s částečným vyhodnocením | ✚ nové |
| Booleova algebra | 4.3 | jiný zápis téhož; nepřidává schopnost | ✗ neděláme |
| šipkový diagram | 4.4 | pohled: výroková dedukce (`C-3`) | ✓ |
| Vennovy diagramy | 4.5 | pohled: svaz podtříd (`C-13`, `C-10`) | ✚ nové |
| úvaha typu ZEBRA | 4.6 | pohled: přiřazovací tabulka (`C-7`) | ✓ |
| úvaha o mluvčích | 4.6 | kódovací pravidlo v profilu (`C-14`) | ✚ nové |

Tři poznámky, protože nejde jen o doplnění seznamu:

**Quineův algoritmus je lék na 2^n.** Místo vyčerpání všech ohodnocení se výrok
vyhodnocuje po částech nad stromem a větev se uzavře, jakmile je hodnota jistá.
Vedlejší produkt je cennější než rychlost: algoritmus sám ukáže, na kterých
proměnných **nezáleží**. To je nový tvar odpovědi — „postaví se divadlo, na kině
nezáleží" je poctivější než vyjmenovat obě varianty a tvrdit, že jsou dvě řešení.
Do `C-8` proto přibývá hodnota `nezáleží`, která není totéž co `nevím`: první je
tvrzení, druhé přiznání.

**Vennův diagram je svaz podtříd nakreslený.** Prázdná oblast je doložená
neslučitelnost, oblast bez značky je `INV-1`. Příklad [B, 4.5] s lichoběžníky
a rovnoběžníky je učebnicová ukázka monotónnosti: úsudek není *nesprávný ve
smyslu opačného tvrzení*, on jen **neplyne** — a systém, který na to řekne „ne",
lže stejně jako ten, který řekne „ano".

**Booleovu algebru vědomě neděláme.** Je to týž výpočet zapsaný jinak — tedy
druhý kalkul k udržování, a `if` podle toho, který se právě použil.

### 20.6 Který výpočet je hlavní

Volba mezi metodami je volba **strategie výpočtu pohledu**, ne volba modulu:

```
HLAVNÍ    C-3 šipkový diagram     roste přírůstkově a řetěz z něj padá sám;
                                  pro úlohy s implikacemi a se známou hodnotou
ZÁLOŽNÍ   C-4 s Quinem            když není dáno nic a je nutná volba hodnoty;
                                  vrací i „nezáleží"
ORÁKULUM  C-4 plná tabulka        pomalá, ale zjevně správná — jen v testech
```

Plná tabulka se z produkční cesty nevyhazuje, **přesouvá se do zkoušek**: je to
nezávislý výpočet, proti kterému se dají rychlé cesty ověřit. Pomalá a zjevně
správná implementace vedle rychlé a chytré je nejlevnější orákulum, jaké systém
může mít.

### 20.7 Co k tomu ještě chybí

* **`C-11` je skutečná mezera.** Zkoušky (kap. 39.3) dnes hlásí „zadání
  z volného textu ✗" — úloha se zadává ručně. Bez `C-11` je celý pohled jen
  kalkulačka, do které někdo ručně přepíše výroky.
* **Zadání bez jednoznačného řešení je platný výstup.** [B, 4.4] má příklad,
  kde správná odpověď zní, že se to z daných informací rozhodnout nedá. To je
  `INV-4` v čisté podobě a patří do etalonu jako doména mlčení.
* **Zadání s více řešeními vrací všechna** (`C-7`), a odpověď musí říct, že jsou
  víc než jedno — vrátit první je tichá chyba.
* **Spor v zadání se hlásí** (`INV-5`). Úloha, jejíž podmínky nejdou splnit,
  není úloha bez řešení; je to vadné zadání a systém to má rozlišit.

### 20.8 Zkoušky

Práce [B] obsahuje **14 řešených příkladů se známou odpovědí**. To je hotová
kurátorovaná sada, kterou nikdo nepsal s ohledem na tento systém — přesně to,
co kap. 36.2 žádá.

```
scripts/etalon_ulohy.py   14 úloh z [B], každá se čtveřicí T-1…T-4
```

Navíc jedna zkouška, kterou pohledy umožňují a jinde v systému obdobu nemá:

```
T-11  KŘÍŽOVÁ SHODA POHLEDŮ
      tatáž úloha spočítaná přes C-3 a přes C-4 musí dát tutéž odpověď
      včetně počtu řešení; rozdíl je chyba v jednom z výpočtů, ne remíza
```

Tahle zkouška má obecnější platnost než logické úlohy: **dva pohledy na táž
data si nesmějí odporovat.** Kde odporují, je chyba v pohledu, ne v datech —
protože pohled nic nepřidává (`INV-14`).

### 20.9 Hranice

Rozsah je **výroková logika a třídy**, ne predikátová logika obecně. Do rozsahu
nepatří slovní úlohy aritmetické a algebraické, které [B, 1.1] uvádí jako jinou
třídu úloh — ty vyžadují počítání, ne kódování vztahů. Modální a vícehodnotové
logiky jsou mimo rozsah celého systému: stojí na tom, že tvrzení je doložené,
odvozené, vyloučené, nebo neznámé, a to je jiná osa než stupně pravdivosti.

---

# ČÁST III · UČENÍ A EVOLUCE

## 21 · Čtyři smyčky učení

```
1. Z FAKTŮ NA PRAVIDLA
   kde se složená cesta opakovaně kryje s doloženou hranou, je to pravidlo
   doklad / navíc / spor — a `navíc` NENÍ chyba, pole je monotónní

2. Z PRAVIDEL NA FAKTY
   odvozená hrana je vstup dalšího odvozování i dalšího učení
   ⇒ vrstva se zavírá sama na sebe

3. Z DAT NA MÍRY
   arita, výlučnost rozměru, váhy v matici — všechno MĚŘENO, nikdy zadáno

4. Z DIALOGU NA VŠECHNO
   člověk potvrdí, opraví, doplní — s postavením podle mřížky 14.3
```

Smyčka 2 je ta, kvůli které to celé stojí za to: text říká, že Věra je manželka
Karla a Karel otec Lucie. Že je Věra matka Lucie, neříká **nikde** — a přesto to
plyne, a je to nový fakt, nad kterým se dá učit dál.

**Co učení nesmí:**

* **Nepřepisovat doložené.** Naučené pravidlo smí odvozovat, ne měnit to, co
  v textu stojí.
* **Nepřijímat pod prahem.** Pravidlo ze tří dokladů je náhoda. A práh se
  neohýbá po měření (`INV-7`).
* **Neztrácet, odkud to je.** Každá naučená hrana nese pravidlo, premisy a počet
  dokladů — jinak ji nejde vzít zpátky, až se ukáže špatná (`INV-12`).

## 22 · Systém se učí vlastní referenční jazyk

Dosud byl referenční jazyk považován za návrh autora systému. To je dobrý
začátek, ne konečný stav.

> **Stejně jako se systém učí pravidla, musí se učit i jazyk, ve kterém jsou
> pravidla vyjádřena.**

Referenční jazyk není pevná množina predikátů, šablon a rozměrů. Je to nejlepší
známý popis světa, který se může zpřesňovat. Systém proto nikdy nehledá pouze
nové znalosti — hledá lepší způsob, jak stávající znalosti popsat.

Předmětem učení tedy nejsou jen fakta, pravidla a vztahy, ale také **šablony,
predikáty, rozměry, struktura grafu a způsob abstrahování**.

Lepší reprezentace je taková, která

* vysvětlí více dat,
* potřebuje méně výjimek,
* vede ke kratším odvozovacím řetězům,
* zachovává úplný řetěz doložení.

## 23 · Meta-učení

Dnešní učení mění znalostní bázi. Nově přibývá ještě jedna úroveň.

```
text  →  fakta  →  pravidla  →  referenční jazyk  →  architektura
```

Architektura se stává objektem měření stejně jako pravidla. Systém proto
průběžně měří:

* které šablony jsou příliš obecné,
* které šablony jsou zbytečně jemné,
* které predikáty se překrývají,
* které rozměry vznikají opakovanými podmínkami,
* které části grafu jsou informačně chudé.

**Tyto informace nikdy přímo nemění běžící systém.** Vznikají jen jako návrhy
další evoluce. Stejně jako pravidlo vzniká z opakovaného pozorování, může vzniknout
i návrh nové architektury.

### 22.1 Atribut je objekt, ne příznak

Aby šlo měřit referenční jazyk, musí být jeho stavební kameny **popsatelné**.
Dnes je `Case=Nom` bit; má to být záznam s vlastnostmi:

```
id                Case=Nom
skupina           morfologie          ← hierarchie, ne plochý seznam (12.4)
nadřazený         Case
zdroj             rozbor · profil · odvození · dialog · návrh modelu
jistota           0,99                ← rozbor není neomylný
informační zisk   0,41                ← MĚŘENO, smyčka 3 (kap. 21)
stabilita         0,28                ← jak často se u téže entity mění
podobné           Acc, Dat, Voc
výskyt            23 % ve faktech · 4 % v otázkách
```

Tím se **atributy samy stanou znalostní bází**: dají se nad nimi měřit překryvy,
odvozovat váhy, sledovat přínos a rozhodovat, které vyřadit. To je přesně to, co
kapitola 22 žádá — architektura jako objekt měření.

Zásada, která to drží při zemi: **nepřidávat atributy, dokud slučování nemá
metriku** (12.4). Bez ní každý nový sloupec zvyšuje jedinečnost a zobecnění
klesá — přidávání by problém zhoršilo, ne zlepšilo.

## 24 · Evoluce reprezentace

Největší část učení nespočívá v přidávání nových faktů, ale v hledání
jednodušší reprezentace. Systém proto průběžně navrhuje nové šablony, rozdělení
či sloučení stávajících, nové predikáty, nové rozměry a nové typy hran.

Každý návrh musí projít stejným měřením jako pravidlo. Bez měření se nikdy
nestává součástí referenčního jazyka.

> **Nová reprezentace se nepřijímá proto, že je elegantní, ale proto, že lépe
> vysvětluje data.**

## 25 · Hypotézy jako první třída

Každé učení začíná hypotézou. Hypotéza není znalost — je to návrh, který čeká na
ověření, a **do odpovědi nikdy nevstupuje** (úroveň 0 v mřížce 14.3).

Každá hypotéza nese: zdroj · počet pozorování · počet potvrzení · počet sporů ·
datum vzniku · způsob vzniku.

Hypotéza se může týkat faktu, pravidla, šablony, vztahu mezi šablonami, nového
predikátu i nového rozměru. Teprve po dosažení prahu (registr, kap. 29) se může
stát součástí systému. Do té doby zůstává oddělená od produkčních znalostí.

## 26 · Experimentální vrstva

Produkční znalostní báze je neměnná (`INV-10`). Každá naučená změna vzniká
nejprve mimo ni.

```
produkční model
        │
        ▼
experimentální kopie          ← vyžaduje snímek úložiště (14.5)
        │
        ▼
nové šablony · pravidla · predikáty · rozměry
        │
        ▼
měření                        ← na etalonu, s verzí dat
        │
        ├── horší → zahodit
        └── lepší → povýšit
```

Povýšení je zapsaná událost s naměřenými čísly, ne tichá záměna. Tím zůstává
zachována reprodukovatelnost všech výsledků.

### 26.1 Porovnání dvou staveb

Snímky se neporovnávají po bajtech — u desetitisíců záznamů to řekne „liší se"
a nic víc. Porovnávají se **po záznamech**, se třemi třídami změny:

```
STAV     rozhodnutí se změnilo        (doložené → nejednoznačné)
UZEL     identita se změnila          (ukazuje jinam)
DŮVOD    týž výsledek, jiný doklad    ← nejcennější a nejtišší
```

Změna **důvodu** je časný signál: odpověď zůstane stejná, ale cesta k ní je
jiná — a to obvykle chybě předchází. Kdo měří jen výsledek, uvidí ji až jako
regresi.

Otisky vstupů se porovnávají zvlášť, takže zpráva neřekne jen *co* se změnilo,
ale **který vstup za to může** (rozbor, mapování rolí, resolver, prahy).

### 26.2 Verzování otiskem, ne číslem

Ruční číslo verze pravidla zastará v první chvíli, kdy někdo pravidlo upraví
a zapomene ho zvednout — přesně ten druh tiché vady, kterou celý návrh loví.
**Otisk obsahu zastarat nemůže.**

A bez časové známky: soubor patří do gitu, takže by známka dělala rozdíl při
každé stavbě a přestalo by být vidět, co se skutečně změnilo. *Kdy* řekne
historie commitu; *z čeho* neřekne nic jiného — a jen to druhé se dá použít
k rozhodnutí.

## 27 · Statistické modely: hranice, která se nesmí posunout

> **Primárně se identifikuje nad grafem a vzory. Každý statistický model smí
> pouze navrhovat hypotézy — nikdy nerozhoduje o pravdivosti** (`INV-11`).

Platí stejně pro neuronové sítě, embeddingy, jazykové modely, klasifikátory
i clustering. Všechny sedí za `SEAM-9`.

**Kde model smí být:**

* **Návrh definice vzoru.** Šablony vznikají slučováním stejných vektorů, což je
  přesné, ale křehké — jediná odlišná aktivace udělá druhou třídu. Model umí
  navrhnout, které vektory patří k sobě, tedy pomoct s definicí šablony a
  s vazbami v matici.
* **Návrh kandidátů** na sloučení jmen, na synonymní predikáty, na chybějící
  hrany.

```
model navrhne:    Š(„Kde byl X uvězněn?") ~ Š(„X strávil ve vězení …")
symbolika ověří:  kolik dvojic to doloží · kolik protipříkladů
rozhodne:         práh, ne důvěra
```

**Kde model být nesmí:**

* **V odpovědi.** Odpověď musí nést řetěz doložení, a z modelu řetěz nevypadne.
* **V rozhodnutí o pravdivosti.** Tvrzení platí, protože je doložené nebo
  odvozené, ne protože to model odhadl s vysokou pravděpodobností.
* **Jako náhrada rozboru.** Morfologie a závislosti přicházejí z UDPipe, což je
  nástroj s definovaným výstupem, ne s odhadem.

Výstup modelu vstupuje do stejného měřicího aparátu jako všechno ostatní —
`doklad / navíc / spor`, práh, protipříklady. Co projde, je pravidlo se svým
doložením; co neprojde, se zahodí. Díky `SEAM-9` jde dnešní síť vyměnit za jiný
algoritmus, aniž se změní architektura.

**Zkouška, že hranice drží:** vypnutím modelu systém zhloupne, ale nezačne lhát.
Odpovědí bude míň, ne víc špatných.

## 28 · Kritérium kvality systému

Cílem není maximalizovat počet znalostí ani přesnost jedné odpovědi. Cílem je
postupně vytvářet **jednodušší referenční jazyk**.

Lepší systém je ten, který vysvětlí více dat, vytvoří méně konfliktů, potřebuje
méně pravidel, používá méně výjimek, zachová vysvětlitelnost a zachová
monotónnost.

Počet uložených znalostí není měřítkem inteligence. Měřítkem je kvalita
reprezentace.

> **Systém se neučí odpovědi. Učí se stále lepší způsob, jak svět zakódovat.
> Odpovědi jsou pouze důsledkem tohoto kódování.**

---

# ČÁST IV · PROVOZ

## 29 · Konfigurace a registr prahů

Konfigurační soubor mění chování systému: zapíná a vypíná funkcionality, určuje
cestu ke znalostní bázi a k datům, mění porty API, úroveň a cestu logů.

Tři pravidla:

* **Žádná cesta ani práh v kódu.** Vše přes `Config` — jinak test měří proti
  provozním datům (kap. 5).
* **Konfigurace se validuje při startu**, ne při prvním použití. Neznámý klíč je
  chyba, ne tiché ignorování.
* **Vypnutá funkcionalita je viditelná v odpovědi i v logu.** Systém s vypnutým
  agentem není tentýž systém a měření to musí vědět.

**Registr prahů** je samostatná část konfigurace a `INV-7` bez něj nejde
dodržet. Každý práh má:

```
id · hodnota · co ovlivňuje · datum měření · verze dat · číslo, ze kterého vzešel
```

Práh bez zdůvodnění je magické číslo; s ním je to záznam měření. Změna prahu je
změna konfigurace se zápisem, ne editace řádku.

## 30 · Logování a pozorovatelnost

Systém umí logovat od prvního dne, ve dvou úrovních:

| úroveň | co z ní musí být jasné |
|---|---|
| **obvyklá** | která komponenta knihovny se volala, s jakým vstupem a s jakým výsledkem |
| **debug** | co se děje uvnitř funkcí — mezistavy pole, kandidáti, zamítnutí |

Doplňky, které v návrhu 1.0 chyběly (`G-18`):

* **Identifikátor dotazu** prochází celým zpracováním, aby šlo z logu složit
  jeden průchod.
* **Log nese verzi dat a verzi profilu.** Bez toho se nedají porovnat dva běhy.
* **Metriky provozu:** počet dotazů, podíl mlčení, podíl doptání, doba odpovědi,
  velikost pole. Podíl mlčení je zdravotní ukazatel, ne chybovost.
* **Zdraví služby** pro `status` (kap. 31): dostupnost UDPipe, načtená báze,
  verze, poslední chyba.
* **Spotřeba signálu.** U každé vrstvy, která vyrábí mezivýsledek, se měří,
  v kolika procentech ho následující vrstva **opravdu použila** místo záložní
  cesty. Nulová spotřeba je chyba stavby, ne vlastnost dat. *(V conBondu se
  diskurzní rozřešení počítalo a zahazovalo měsíce; uložením téhož mezivýsledku
  stoupla navázatelnost ze 74 % na 81,6 %, aniž se napsal nový algoritmus.)*
* **Log nikdy nevzniká v jádře** (kap. 5) — jádro hlásí událost, klient
  rozhoduje, kam jde.

## 31 · API a služba

### 31.1 Konzumované API

`UDPipe 2`, stavěné a provozované lokálně (kap. 13). Jediný klient v systému.

### 31.2 Poskytované API

Vlastní dotazovací a chatovací **REST API**, ke kterému se připojuje frontend.
Minimální kontrakt, který návrh 1.0 nespecifikoval (`G-12`):

| skupina | co obsahuje |
|---|---|
| **dotaz** | otázka → odpověď podle kap. 18, včetně řetězu |
| **rozhovor** | relace, historie, identita účastníka (14.4) |
| **znalost** | přidání tvrzení, definice, opravy; odvolání |
| **doložení** | rozbalení řetězu, „odkud to víš" |
| **pohledy** | data pro vizualizaci (kap. 32) |
| **zdraví** | verze, stav závislostí, načtená data |

Pravidla kontraktu:

* **Verzovaná cesta** (`/v1/…`). Nekompatibilní změna je nová verze, ne tichá
  úprava.
* **Chyba má typ, ne jen text.** Odlišuje se „nemá odpověď" (platný výsledek,
  `INV-4`) od „nepodařilo se odpovědět" (chyba, `INV-9`). Tohle je jediné místo,
  kde se kapitola 2 bod 3 láme do praxe (`G-17`).
* **Limity jsou součástí kontraktu**: největší vstup, časový strop na dotaz,
  strop pro `C-4` (2^n).
* **Odpověď je serializovatelná beze ztráty** (kap. 5) — totéž JSON, jaké vrací
  knihovna.

### 31.3 Chování služby

Systém umí běžet jako služba a zvládá tradiční `systemctl` chování:
**start, stop, restart, reload, status**.

* `reload` znovu načte konfiguraci a profily **bez ztráty rozhovorů**; když to
  u některé změny nejde, řekne to a nechá běžet staré nastavení.
* `status` odpovídá z metrik zdraví (kap. 30), ne jen „běží".
* `stop` dokončí rozpracované dotazy nebo je zamítne s typovanou chybou — nikdy
  nevrací prázdnou odpověď (`INV-9`).

## 32 · Vizualizace: viewBase jako zákazník, ne součást

Systém musí být vidět. Ne logem, ale obrazem toho, čím právě myslí.

`viewBase` (Canvas, TerminalWindow) se připojuje **přes veřejné API jako kdokoli
jiný** — o vnitřnostech neví nic. Kdyby sahala do dat přímo, nešla by vypnout,
a přesně to se na stroji bez displeje dělá.

```
/view doc    DOKUMENTY korpusu a jejich blízkosti
             po tahu se rozsvítí ten, ze kterého odpověď přišla
             stabilní mapa — mění se pomalu

/view word   ROZSVÍCENÁ SLOVA pole a jejich vodivosti
             uzly vznikají a hasnou s každým tahem
             ⇒ je vidět, čím stroj právě myslí, ne jen kde to našel

/view vzor   ŠABLONY a MATICE vztahů mezi nimi       (nové, klíčové)
             která šablona ukazuje na kterou a jak silně;
             po tahu se zvýrazní cesta otázka → šablona → věty
             Jediné okno, ze kterého je poznat, jestli systém větu
             IDENTIFIKOVAL, nebo ji jen našel podle slov.

/view graf   ENTITY a hrany s doložením               (nové)
             cesta, po které odpověď přišla, zvýrazněná
```

Plus dvě okna: **DIALOG** s promptem a **AKTIVACE** bez promptu (režim, počet
kandidátů, zdroj, řetěz).

Zásada: **vizualizace se bez stroje vědomě nespustí.** Prázdné okno je horší než
jasná hláška.

## 33 · Bezpečnost a soukromí

Kapitola v návrhu 1.0 chyběla úplně (`G-13`), přitom MNEMOS a vzkazy pracují
s osobními údaji a REST API je otevřené rozhraní.

* **Identita a autorizace.** Kdo se ptá, určuje, co vidí ze svých MNEMOS faktů
  a ze svých vzkazů. Bez identity se osobní fakty neukládají (14.4).
* **Oddělení osobní a korpusové báze.** Osobní fakty jdou vyexportovat a smazat
  jedním úkonem, včetně odvozeného (`INV-12`).
* **Limity a kvóty** na dotaz i na relaci — strop `C-4` je bezpečnostní opatření
  stejně jako výkonové.
* **Vstup se nedůvěřuje.** Text z dialogu je data, ne instrukce; nic v něm
  nesmí měnit konfiguraci ani prahy.
* **Licencovaná data se nedostanou ven z povolené hranice** (kap. 40).

Rozsah opatření závisí na `Q-4` — jeden lokální uživatel a víc uživatelů přes síť
nejsou tentýž systém.

## 34 · Výkon, souběh a škálování

Návrh 1.0 neuvádí žádný strop (`G-14`, `G-15`). Minimální rozhodnutí:

* **Výchozí měřítko** je dnešní korpus (26 051 vět). Cílové měřítko je otevřená
  otázka `Q-5` a rozhoduje o volbě úložiště.
* **Rozpočet odpovědi.** Na dotaz je časový strop z konfigurace; překročení je
  poctivé „neumím v čase", ne delší čekání (`INV-4`).
* **Souběh.** Služba obsluhuje víc dotazů zároveň. Čtení báze je souběžné, zápis
  učení probíhá v experimentální kopii (`INV-10`), takže odpovídání nikdy nečeká
  na učení.
* **Indexace.** Pole, matice a graf potřebují indexy; jejich stavba je součást
  příjmu, ne prvního dotazu.
* **Výkon se měří spolu se správností** (kap. 36). Zrychlení, které zhorší
  zúžení, není zrychlení.

## 35 · Běhové prostředí a odolnost

### 35.1 Backend

Python **3.11 nebo 3.12** ve vlastním `.venv`, kvůli kompatibilitě UDPipe,
TensorFlow a dalších ML knihoven.

### 35.2 Balení a závislosti

* **Jádro nemá závislosti.** Ostatní balíky jsou volitelné skupiny (`parser`,
  `server`, `ml`, `dev`), aby odpovídání běželo bez ML vrstvy (kap. 13).
* **Závislosti se přišpendlují.** Reprodukovatelné měření vyžaduje
  reprodukovatelnou instalaci.
* **Instalace a spuštění mají popsaný postup**, který je zároveň testem
  (kap. 37).

### 35.3 Chování při výpadku

Ke každé závislosti patří definovaný degradovaný režim (`G-16`):

```
UDPipe nedostupný     příjem a dotaz hlásí typovanou chybu; báze zůstává čitelná
báze nenačtená        služba startuje, status to hlásí, dotazy se odmítají
profil chybí          start selže hlasitě; systém bez jazyka není systém
model za SEAM-9 chybí učení navrhuje méně; odpovídání beze změny (kap. 27)
```

Ani jeden režim nesmí vypadat jako prázdná odpověď (`INV-9`).

---

# ČÁST V · MĚŘENÍ A DODÁVKA

## 36 · Měření

Nový systém musí mít od prvního dne to, co má conBond2:

```
test/core.py            jádro, bez modelu a bez korpusu
scripts/etalon.py       kurátorované otázky psané rukou + scénáře
scripts/etalon_*.py     cizí sady, ať se neměří jen na svém
scripts/diagram.py      logické úlohy se známým řešením
```

### 36.1 Definice metrik

Návrh 1.0 metriky používal, ale nedefinoval (`G-19`):

| id | metrika | definice |
|---|---|---|
| `M-1` | **dosah** | podíl otázek, kde je správná odpověď mezi vrácenými kandidáty |
| `M-2` | **zúžení** | podíl otázek, kde je správná odpověď první |
| `M-3` | **správné mlčení** | podíl otázek bez odpovědi v datech, kde systém mlčel |
| `M-4` | **konfabulace** | podíl otázek bez odpovědi v datech, kde systém odpověděl |
| `M-5` | **správné doptání** | podíl nejednoznačných otázek, kde se systém zeptal |
| `M-6` | **ohlášený spor** | podíl odporujících si vstupů, kde systém spor nahlásil |
| `M-7` | **doba odpovědi** | medián a 95. percentil |
| `M-8` | **pokrytí vysvětlením** | podíl odpovědí s doloženým druhem řetězu (kap. 18.1) |
| `M-9` | **odděleni ti, kdo se oddělit mají** | podíl doložených dvojic různých entit, které nesplynuly |
| `M-10` | **spotřeba signálu** | podíl případů, kdy vrstva použila mezivýsledek předchozí (kap. 30) |

Pravidla počítání, bez nichž jsou čísla nesrovnatelná:

* **Remíza se počítá jako neúspěch v `M-2`.** Jinak se zúžení nafoukne.
* **Každé číslo nese verzi dat, profilu a konfigurace** (kap. 14.5).
* **`M-1` se nikdy neuvádí samostatně** (`INV-8`) — vrátit všechno dá 100 %.
* **`M-4` se sleduje proti `M-1`.** Rostoucí dosah spolu s rostoucí konfabulací
  není zlepšení.
* **Každé měřítko má protiváhu** (`INV-13`). Ke každému číslu, které jde
  zlepšit podvodem, patří druhé, které se tím podvodem zhorší:

```
zlepším podvodem…                 …a tohle to okamžitě ukáže
──────────────────────────────────────────────────────────────
dosah (vrátit všechno)            M-2 zúžení
navázanost (sloučit jmenovce)     M-9 oddělení
pokrytí vysvětlením (mlčet)       M-1 dosah
zúžení (odpovídat jistě)          M-4 konfabulace
```

* **Sada protivah se nesmí přepočítávat při stavbě.** Doložené dvojice, které
  nesmějí splynout, patří **zmrazené do gitu** — kdyby vznikaly znovu při každém
  běhu, chyba, která uzly ztratí, by sadu tiše zmenšila a měřítko by pochválilo
  právě tu chybu, kterou má chytat.

### 36.2 Zásady měření

* **Kurátorovaná sada je nenahraditelná.** Generované otázky mají odpověď
  z konstrukce a nikdy neřeknou, jestli systém pozná, že neví.
* **Vícetahové scénáře.** Že naučené má jaké postavení, je vidět až tehdy, když
  se systém nejdřív něco naučí.
* **Brána se měří taky.** Otázka, která neprojde do pole, nemá odpověď, i kdyby
  ji pole mělo. Stalo se to při každém přidání nové cesty.
* **Měřit až po stavbě.** Vrstva postavená a měřená až potom skončila přiznáním,
  že ukázka byla vydávána za výsledek.

**Výchozí stav k porovnání:** 40 otázek, dosah 85 %, první 65 %, scénáře 2/2.

## 37 · Testovací matice

Ke každé schopnosti (`C-n`) patří čtveřice zkoušek. Chybí-li kterákoli, není ta
schopnost hotová.

| id | zkouška | co ověřuje |
|---|---|---|
| `T-1` | **UMÍ** | správný vstup → správná odpověď |
| `T-2` | **MLČÍ** | chybějící data → přiznání, ne výmysl (`INV-4`) |
| `T-3` | **DOPTÁ SE** | nejednoznačný vstup → otázka zpět, ne volba |
| `T-4` | **OHLÁSÍ SPOR** | odporující si vstup → hlášení, ne tichý výběr (`INV-5`) |

Dnešní etalon má domény přesně kvůli tomu — `zápory` měří mlčení a bez ní by se
vylepšování dosahu odměňovalo i tehdy, když roste konfabulace.

Nad rámec etalonu (`G-20`, `G-23`, `G-24`):

* `T-5` **konformní sada švu** — každá implementace za `SEAM-n` prochází touž
  sadou.
* `T-6` **regrese** — jednou opravená chyba má trvalý test s odkazem na `INV-n`.
* `T-7` **jazyková čistota** — `grep` na slova přirozeného jazyka v `jadro/`
  vrací prázdno (kap. 6).
* `T-8` **licence** — kontrola, že do repozitáře nevstoupila licencovaná data
  (kap. 40).
* `T-9` **výkon** — `M-7` proti rozpočtu z kap. 34.
* `T-10` **instalace** — čisté prostředí, popsaný postup, projde dotaz naprázdno.
* `T-11` **křížová shoda pohledů** — tatáž úloha spočítaná přes `C-3` a přes
  `C-4` dá tutéž odpověď včetně počtu řešení (kap. 20.8). Obecněji: dva pohledy
  na táž data si nesmějí odporovat (`INV-14`).
* `T-12` **směr závislostí z importů** — test přečte importy z AST a spadne na
  tom, který míří proti směru vrstev (kap. 5). *Levnější než fyzické rozdělení
  do balíčků a zajistí totéž; balíčky mohou přijít kdykoli potom.*
* `T-13` **pojistka proti vakuu** — test, který hlídá jev spouštěný jen za
  určitých podmínek, musí navíc **tvrdit, že se ty podmínky v jeho sondách
  opravdu vyskytnou**. Jinak zticha přestane hlídat cokoli a nikdo si toho
  nevšimne.
* `T-14` **pokrytí × přesnost u každého nového odhadu** — nová heuristika se
  nepřijímá podle pokrytí, ale podle ručně přečteného vzorku. *(Změřeno na
  okně scény v conBondu: okno 1 → 141 nálezů bez chyby, okno 3 → 270 nálezů
  s přesností 6/8, okno 5 → 338 s přesností 6/10. Širší okno přidalo víc
  špatných hodnot než správných odpovědí; špatná hodnota je sebejistě špatný
  fakt, chybějící je jen stav.)*

## 38 · Dokumentace jako součást, ne příloha

> **Každá metoda má vysvětlení alespoň principiální, a u každého řezu stojí, po
> jaké naměřené chybě vznikl.**

* **Docstring vysvětluje PROČ, ne co.** Co dělá kód, je vidět z kódu.
* **U každé konstanty a prahu stojí, odkud se vzal** — a odkazuje do registru
  prahů (kap. 29).
* **Chyba se zapisuje do kódu, ne jen do commitu.** Řez, který vznikl proto, že
  systém odpověděl „ve svých prózách" na otázku po rodišti, to musí mít napsané
  u sebe — jinak ho někdo za půl roku „zjednoduší".
* **Příručka s diagramy volání** pro každý průchod: příjem, stavba, dotaz,
  dialog, učení.
* **Spustitelné ukázky** vedle textu: `scripts/diagram.py` ukáže krok za krokem,
  co se v odvozování děje. Ukázka, kterou lze spustit, nezastará.

## 39 · Pořadí stavby

Podle závislostí, ne podle atraktivnosti.

### 39.1 Krok nula: scaffold dřív než cokoli jiného

Nejdřív se navrhne a postaví **kostra**: adresáře, švy jako abstraktní třídy
s konformními sadami, prázdné profily, `Config` s registrem prahů, log,
testovací běh a **jedna zkouška, která projde skrz naprázdno** — text dovnitř,
prázdná odpověď ven, ale celou cestou.

Teprve do hotové kostry se vkládají vrstvy. Důvod je praktický: v obou
předchozích projektech vznikly nejhorší vazby tam, kde se vrstva přidávala do
něčeho, co pro ni nemělo místo — odtud „odpovídač nesahá na šablony".

Tři zásady, které platí u každého kroku a všechny tři jsou zapsané po chybě:

* **Žádný objekt bez odběratele.** Vrstva se nestaví dopředu „protože bude
  potřeba". Fakt dostane identifikátor, teprve až ho někdo použije. Postavená
  vrstva bez odběratele je složitost bez užitku a nikdo ji později netroufne
  odstranit.
* **Měřidlo dřív než schopnost.** Etalon odpovědí neuměří všechno: porovnává-li
  se podřetězcem, projde i odpověď, která jen zopakuje jméno entity a nic
  neřekne. Kde měřidlo chybí, staví se dřív než kód.
* **Nejdřív roztřídit selhání, potom stavět.** *(Měřeno v conBondu: navrhované
  pořadí schopností se po roztřídění devatenácti chyb obrátilo — plánovač
  víceskokových dotazů neřešil ani jednu, kdežto extrakce dvanáct. Roztřídění
  stálo hodinu a ušetřilo modul.)*

### 39.2 Kroky a jejich definice hotového

Každý krok je hotový, teprve když má všechny čtyři zkoušky `T-1`–`T-4`,
naměřené číslo na etalonu a zápis v dokumentaci (`G-21`).

| krok | obsah | hotovo, když |
|---|---|---|
| **0** | kostra knihovny + jazykový profil | průchod naprázdno projde, `T-7` prochází |
| **1** | příjem a kódování tokenů (z conBond2 beze změny) | pole se shoduje s conBond2 na témž korpusu |
| **2** | **hrany z vět** (`SEAM-6`) | hrany na etalonu, `T-1`–`T-4` |
| **3** | jména: scelení, varianty, osoby vs dokumenty | doptání funguje, `M-5` |
| **4** | **šablony a matice do odpovídací cesty** | „Kde byl Jan uvězněn?" **mlčí** |
| **5** | graf zaměřený na hranu, ne na spoluvýskyt | `M-2` neklesne, `M-4` klesne |
| **6** | diagram jako společný tvar odpovědi | `scripts/diagram.py` prochází |
| **7** | rozměry: čas hotov, místo a počet dopsat | `C-5` na všech čtyřech osách |
| **8** | pravidla z definic i z faktů, arita | `doklad/navíc/spor` v etalonu |
| **9** | odstupňovaná tvrzení a abdukce | `C-8` se liší slovy, `C-9` označena jako hypotéza |
| **10** | defeasibilita a specifičnost | až po rozhodnutí `Q-3` |
| **11** | slovní úlohy z logiky: `C-11`–`C-14` | 14 úloh z [B] projde, `T-11` prochází |

**Kroky 2–4 rozhodují o tom, jestli systém odpoví „Praha", nebo mlčí.** Zbytek je
nadstavba, která bez nich stojí na písku.

### 39.3 Zkoušky, které mají po stavbě projít

```
✓ hotovo v conBond2   ◐ částečně   ✗ chybí
```

**Fakt z jedné věty**
```
✓ Kdy se narodil Alois Jirásek?     23. srpna 1851 Hronov
✓ Jako co pracoval Alois Jirásek?   učitel
✓ S kým se přátelil Bohumil Hrabal? s Jiřím Kolářem
```

**Poctivé mlčení**
```
✓ Kdy se narodil Sherlock Holmes?   o něm korpus nic neví
✓ S kým se oženil Bohumil Hrabal?   mlčí — text o tom nemluví
✗ Kde byl Jan uvězněn?              dnes „Praha"; má mlčet
```

**Zápor jako fakt**
```
✓ Kdo je Božena Němcová?            NE „realistkou" (věta říká, že není)
◐ Proč není realistkou?             důvod je v téže větě, role `proc`
```

**Doptání**
```
✓ Kdo je Novák?                     upřesni: Arne · Bohumil · Ivo
✓ Kdo je Čapek?                     upřesni: Josef · Karel
✗ Kdo byl Jan?                      dnes Neruda; má nabídnout i Křtitele
```

**Vztah a vzdálenost**
```
✓ Mohl Karel Čapek znát Boženu Němcovou?   ne — životy se nepřekrývají
✓ Znal se Hrabal s Havlem?                 nevím, ale vede cesta …
✗ Kdo je bratr Karla Čapka?                hrana existuje, nepoužívá se
```

**Odvozený fakt**
```
✓ (na vztahovém textu) děd, strýc, teta — věty, které nikde nestojí
✗ Kdo je Petrův tchán?                    v dialogu nezapojeno
```

**Výroková úloha**
```
✓ věštkyně, vnuk, večírek     (Bartlová, kap. 4.4)
✓ milovníci umění             (přiřazovací tabulka)
✗ zadání z volného textu      dnes se úloha zadává ručně
```

**Učení dialogem**
```
✓ „Božena Němcová je spisovatelka."  → přijato, úroveň 3
◐ „Tchán je otec manžela."           → pravidlo z definice, mimo dialog
✗ „Ne, Jan byl uvězněn v Machaeru."  → oprava faktu za běhu, úroveň 4
```

**Návaznost**
```
✓ Kdo je Ježíš? → Syn Boží;  Čí? → z Boha
   (předchozí odpověď se stane aktivací — elipsa bez zvláštního mechanismu)
```

## 40 · Data, jádro dat a licence

Nic se nesbírá znovu. K dispozici je:

```
z conBond2   korpus 26 051 vět s rozborem, agenty a koreferencí
             etalon 40 kurátorovaných otázek + scénáře
             jazykový profil cs.json
             vertikály (300 sloupců pole)
z literatury 14 řešených úloh z výrokové logiky (Bartlová 2014) jako etalon
z conBond    etalon 95 otázek (tři režimy včetně `clarify`)
             dialogové scénáře
             slovník synonym (1016 skupin)
             tabulka vztahů jako odvozovací pravidla
             graf entit s vahami podle větného členu
```

### 40.1 Co je datové jádro

Rozdělení, které musí padnout při návrhu, ne až při stavbě:

| jádro (bez něj systém nefunguje) | znalostní data (vyměnitelná) |
|---|---|
| seznam českých jmen a příjmení | korpus |
| synonyma | etalony |
| rodinné vztahy (bratranec, švagr, sestřenice…) | naučená pravidla |
| jazykové profily | osobní fakty (MNEMOS) |

Jádro dat se verzuje s kódem; znalostní data se verzují samostatně a jejich
verze se objevuje v měření (kap. 36.1).

### 40.2 Licence

* Wikipedie — **CC BY-SA 4.0**, přenáší se s údajem o zdroji.
* Ekumenický překlad Bible — **autorský, do veřejného repozitáře nesmí**
  (jen Kralická).
* Zdroje se vedou v `ZDROJ.md` a přenášejí se s daty.
* **Kontrola je automatická** (`T-8`), ne slib. Slib jednou selže.

## 41 · Co vědomě neděláme

* **Šíření aktivace po hranách.** conBond ho měl; pole se tím **rozšiřuje**
  a my ho potřebujeme zúžit. Z paměti tématu se přebírá jen `reinforce`
  a `decay`.
* **Pravděpodobnostní skóre bez řetězu.** Číslo, které nejde rozbalit na
  doložení, je hádání s desetinnou čárkou.
* **Doplňování chybějících faktů ze světa.** Systém smí odvozovat jen z toho, co
  má — z korpusu, z dialogu, z pravidel. Když neví, řekne to.
* **Druhý logický kalkul.** Booleova algebra ([B, 4.3]) je týž výpočet zapsaný
  jinak. Dva kalkuly znamenají dvě místa, kde může být chyba, a `if` podle toho,
  který se právě použil.
* **Predikátová, modální a vícehodnotová logika.** Rozsah je výroková logika
  a třídy (kap. 20.9). Stupně pravdivosti jsou jiná osa než
  doložené / odvozené / vyloučené / nevím.
* **Aritmetické a algebraické slovní úlohy.** Vyžadují počítání, ne kódování
  vztahů; je to jiná třída úloh.
* **Jeden benchmark jako cíl.** CommonsenseQA je konstruovaná proti vyhledávání
  v grafu (distraktory pocházejí z téhož okolí téhož pojmu), takže měří hlavně
  to, co nám chybí. Užitečná jako zátěž, ne jako meta.

## 42 · Čeho se vyvarovat

Zapsáno z chyb, které se během jednoho dne staly víckrát.

* **Neměřit šablonu jako ranker.** Byla vyzkoušena jako řadič kandidátů, vyšla
  hůř, a bylo to uzavřeno jako „nefunguje". Špatná otázka: šablona má kandidáty
  **matchnout**, ne mezi nimi vybírat.
* **Neladit váhy, když chybí struktura.** Půlhodina ladění skóre entit, remíz
  a rozšíření skončila třemi vrácenými opravami — a dvě z nich si vzájemně
  vypnuly účinek.
* **Nespoléhat na jeden signál napříč jeho platností.** `Ent=` je jméno
  dokumentu; u životopisu je to i osoba, u biblické knihy ne. Bez toho řezu
  vzniklo `poslat(bible 1 korintským, timoteo)`.
* **Místa propojí všechno.** Praha stojí v tisících vět, takže přes ni vede cesta
  od každého ke každému a vypadá to jako nález. Rozbor přitom místo od člověka
  odlišuje sám.
* **Měřit dřív než stavět.** Vrstva postavená a měřená až potom skončila
  přiznáním, že ukázka byla vydávána za výsledek.

---

# PŘÍLOHA A · Chybějící doporučení v návrhu 1.0

Seznam toho, co návrh buď vůbec neřešil, nebo požadoval bez návrhu řešení.
Sloupec **kde** ukazuje, kde je to v této verzi doplněné.

## A.1 Data a stav

| id | co chybělo | proč to bolí | kde |
|---|---|---|---|
| `G-1` | formát a životní cyklus úložiště | kap. 22 (experimentální vrstva) bez snímků nejde postavit | 14.5 |
| `G-2` | verzování schématu a migrace | naměřené číslo bez verze dat není měření | 14.5, 36.1 |
| `G-3` | záloha a obnova | naučené znalosti jsou po incidentu nenahraditelné | 14.5 |
| `G-4` | studený start s prázdnou bází | první běh je nedefinovaný stav | 35.3 |

## A.2 Provenience, identita, konflikt

| id | co chybělo | proč to bolí | kde |
|---|---|---|---|
| `G-5` | mřížka priorit zdrojů | „spor se hlásí, nepřepisuje" a „MNEMOS přebíjí korpus" si přímo odporovaly | 14.3 |
| `G-6` | model identity uživatele | MNEMOS i vzkazy ji předpokládají, nikde nevzniká | 14.4 |
| `G-7` | mechanismus odvolání | „musí jít zapomenout" bez seznamu premis nejde splnit | 14.4 |

## A.3 Jazyk a normalizace

| id | co chybělo | proč to bolí | kde |
|---|---|---|---|
| `G-8` | návrh detekce jazyka a doplnění diakritiky | v původní kap. 11 jako požadavek bez místa v architektuře | 14.1 |
| `G-9` | normalizace čísel, dat, jednotek, rozsahů | rozměry nemohou porovnávat nesrovnané hodnoty | 14.2 |
| `G-10` | zdroj svazu podtříd pro defeasibilitu | `C-10` bez taxonomie není spustitelná | 16 (`C-10`), `Q-3` |
| `G-11` | koreference jako vrstva | v datech se zmiňuje, v architektuře chyběla | 10 (`AG-KOREF`) |

## A.4 Provoz

| id | co chybělo | proč to bolí | kde |
|---|---|---|---|
| `G-12` | kontrakt API (endpointy, verze, chyby, limity) | „systém má REST API" není zadání | 31.2 |
| `G-13` | bezpečnost, autorizace, soukromí | osobní fakty na otevřeném rozhraní | 33 |
| `G-14` | souběh a zamykání při učení | služba obsluhuje víc dotazů, učení mění stav | 34 |
| `G-15` | výkonový rozpočet, strop dat, indexy | žádné číslo, proti kterému by šlo měřit | 34 |
| `G-16` | degradace při výpadku závislosti | UDPipe dolů dnes znamená nedefinované chování | 35.3 |
| `G-17` | promítnutí „nula ≠ chyba" do rozhraní | princip byl v kap. 0, ale nikde v API | 31.2 |
| `G-18` | metriky a zdraví služby | `systemctl status` nemá co říct | 30 |

## A.5 Měření a dodávka

| id | co chybělo | proč to bolí | kde |
|---|---|---|---|
| `G-19` | formální definice metrik | dosah a zúžení se používaly bez definice, remízy nedořešeny | 36.1 |
| `G-20` | konformní testy švů | šev bez sady je jen jméno rozhraní | 11, 37 (`T-5`) |
| `G-21` | definice hotového pro každý krok stavby | pořadí bez kritérií nezabrání „vypadá to hotově" | 39.2 |
| `G-22` | registr prahů | `INV-7` (práh se neohýbá) bez registru nejde dodržet | 29 |
| `G-23` | automatická kontrola licencí | zákaz v textu jednou selže na lidské chybě | 37 (`T-8`), 40.2 |
| `G-24` | regresní a výkonnostní testy | etalon sám nechytí návrat staré chyby | 37 |
| `G-25` | rizikový registr | nic neříká, co může projekt zabít | příloha B |

## A.6 Řešení logických úloh

Návrh 1.0 měl schopnosti 4.3, 4.4 a 4.7, ale ne rámec, do kterého patří —
nepojmenoval, že jsou to **pohledy**, ne moduly (kap. 20).

| id | co chybělo | proč to bolí | kde |
|---|---|---|---|
| `G-30` | etapa návratu do kontextu zadání | vrátit ohodnocení `a=0, b=1` není vyřešená úloha | 20.4 |
| `G-31` | pravidla negace složených výroků | bez De Morgana neprojde polovina zadání | `C-12` |
| `G-32` | kvantifikované výroky a třídy | „všichni / někteří" jsou v úlohách běžné | `C-13` |
| `G-33` | úlohy o pravdomluvných a lživých mluvčích | vyžadují svázání pravdivosti s mluvčím | `C-14` |
| `G-34` | částečné vyhodnocení místo 2^n | strop dnes znamená „neumím" tam, kde by šlo odpovědět | 20.5 |
| `G-35` | odpověď „na této proměnné nezáleží" | jinak se z jednoho řešení stanou dvě | `C-8`, 20.5 |
| `G-36` | pomalá referenční implementace jako orákulum | rychlé cesty nemají proti čemu se ověřit | 20.6 |

## A.7 Dokument sám

| id | co chybělo | kde |
|---|---|---|
| `G-26` | číslování: chyběla kap. 14, pořadí 7b → 7d → 7c → 7e, dva stylové režimy, kap. 26 jiným formátem; „determinismus" popisoval vysvětlitelnost | celá struktura, 18 |
| `G-27` | slovník pojmů | 3 |
| `G-28` | duplikace: síť (7e vs 23), učení (2c vs 18–22), monotónnost na třech místech, „kdo systém opravuje…" třikrát | 21, 27, 4 |
| `G-29` | redakční komentář uvnitř specifikace („Tohle je podle mě nejlepší cesta…") | odstraněno |

---

# PŘÍLOHA B · Otevřené otázky a rizika

## B.1 Otázky, které musí padnout před krokem 0

| id | otázka | na čem to visí |
|---|---|---|
| ~~`Q-1`~~ | **rozhodnuto** (14.6): korpus dopředu, dialog líně; řez vede podle provenience premis | — |
| `Q-2` | Jaký formát úložiště? (soubor / SQLite / grafová báze) | snímky, souběh, měřítko |
| `Q-3` | Odkud svaz podtříd — z korpusu, z ručního jádra dat, z externího zdroje? | `C-10`, krok 10 |
| `Q-4` | Jeden lokální uživatel, nebo víc uživatelů přes síť? | rozsah kap. 33 |
| `Q-5` | Cílové měřítko korpusu — desetitisíce, nebo miliony vět? | `Q-2`, indexy, `C-4` |
| `Q-6` | Je matice šablon součástí produkční báze, nebo se přepočítává z korpusu? | `Q-1`, doba startu |
| `Q-7` | Jak se verzuje referenční jazyk, když se ho systém učí (kap. 22)? Je to artefakt v gitu, nebo stav v bázi? | reprodukovatelnost, kap. 26 |
| `Q-8` | Přesný seznam jádra dat (40.1) — co konkrétně tam patří a co ne | krok 0 |

## B.2 Rizika

| riziko | projev | protiopatření |
|---|---|---|
| **Krok 4 se odloží** | systém odpovídá z pytle vět a vypadá to dobře na dosahu | `M-4` v každém měření, „Kde byl Jan uvězněn?" jako přejímací zkouška |
| **Prahy se ohnou** | čísla se zlepší, aniž se zlepší systém | registr prahů se zápisem měření (29), `INV-7` |
| **Model se vplíží do odpovědi** | odpovědí přibude, řetězy zeslábnou | zkouška z kap. 27: vypnutí modelu ubere odpovědi, nepřidá chyby |
| **Jazyk proteče do jádra** | angličtina se stane větví, ne souborem | `T-7` v CI |
| **Meta-učení požere kapacitu** | staví se kap. 22–26 dřív než krok 4 | pořadí v 39.2 je závazné |
| **Etalon se přizpůsobí systému** | roste číslo, ne schopnost | kurátorovaná sada se rozšiřuje jen o otázky psané před měřením |

---

# PŘÍLOHA C · Rejstřík

**Invarianty** `INV-1` monotónnost · `INV-2` řetěz · `INV-3` odvozené ≠ doložené ·
`INV-4` mlčení · `INV-5` spor · `INV-6` nejslabší důkaz · `INV-7` práh ·
`INV-8` dvoustupňové měření · `INV-9` nula ≠ chyba · `INV-10` produkční báze ·
`INV-11` model jen navrhuje · `INV-12` odvolatelnost

**Švy** `SEAM-1` ZdrojAktivaci · `SEAM-2` Uloziste · `SEAM-3` SkladacVektoru ·
`SEAM-4` Slucovac · `SEAM-5` Sitko · `SEAM-6` Hranovac · `SEAM-7` Rozmer ·
`SEAM-8` Jazyk · `SEAM-9` Navrhovac

**Schopnosti** `C-1` přímý zásah · `C-2` skládání · `C-3` dedukce ·
`C-4` úplný rozbor · `C-5` vylučování rozměrem · `C-6` arita · `C-7` přiřazování ·
`C-8` odstupňované tvrzení · `C-9` abdukce · `C-10` defeasibilita ·
`C-11` kódování úlohy · `C-12` negace složených výroků · `C-13` třídy
a kvantifikátory · `C-14` sebereferenční ohodnocení

**Metriky** `M-1` dosah · `M-2` zúžení · `M-3` správné mlčení · `M-4` konfabulace ·
`M-5` doptání · `M-6` ohlášený spor · `M-7` doba odpovědi

**Zkoušky** `T-1` umí · `T-2` mlčí · `T-3` doptá se · `T-4` ohlásí spor ·
`T-5` konformita švu · `T-6` regrese · `T-7` jazyková čistota · `T-8` licence ·
`T-9` výkon · `T-10` instalace · `T-11` křížová shoda metod

---

# PŘÍLOHA D · Co se v refaktoru změnilo

## D.1 Proti návrhu 1.0

**Struktura.** Z 26 kapitol se dvěma číslovacími a stylovými režimy vzniklo šest
částí a čtyři přílohy. Doplněna chybějící kapitola (v 1.0 chyběla 14), srovnáno
pořadí (1.0 mělo 7b → 7d → 7c → 7e), sjednocen styl nadpisů.

**Sloučeno.** Neuronová síť (1.0 kap. 7e) + role statistických modelů
(1.0 kap. 23) → kap. 27. Učení (1.0 kap. 2c) + 1.0 kapitoly 18–22 → část III.
Monotónnost, popsaná na třech místech, → `INV-1` s odkazy.

**Přesunuto.** Nedotknutelné zásady z prostředka dokumentu (1.0 kap. 6) dopředu
jako `INV-1`–`INV-12`, protože se na ně odkazuje od začátku. Zkoušky schopností
(1.0 kap. 5) k pořadí stavby, kde slouží jako kritéria hotového.

**Odstraněno.** Redakční komentář uvnitř specifikace a trojí opakování věty „kdo
systém opravuje, dělá to proto, aby ho opravil" — zůstala jednou, v kap. 14.3,
kde je z ní pravidlo.

**Doplněno.** Slovník (kap. 3), mřížka provenience (14.3), identita (14.4),
úložiště (14.5), normalizace (14.2), bezpečnost (33), výkon a souběh (34),
odolnost (35.3), kontrakt API (31.2), registr prahů (29), definice metrik (36.1),
rozšířená testovací matice (37), definice hotového u každého kroku (39.2),
`SEAM-9`, `AG-KOREF`, přílohy A–D.

**Opraveno věcně.** Rozpor mezi `INV-5` a „MNEMOS přebíjí korpus" — vyřešen
mřížkou 14.3, kde přebití není přepsání. Kapitola nazvaná „Determinismus"
popisovala vysvětlitelnost; obojí je rozděleno (kap. 5 a 18).

## D.2 Revize 2.1

**Rozhodnuto `Q-1`.** Přibyla kap. 14.6: odvozuje se dopředu právě tehdy, když
jsou všechny premisy z korpusu; jakmile mezi ně vstoupí věta z dialogu, počítá
se to až na dotaz. Odvozené hrany žijí ve vlastní vrstvě s indexem premis a jsou
kdykoli zahoditelné.

**Rozšířen rozsah** o slovní úlohy z výrokové logiky (kap. 1, nová kap. 20),
s rámcem podle Bartlové (2014). Odtud nové schopnosti `C-11` kódování úlohy
z textu, `C-12` negace složených výroků, `C-13` třídy a kvantifikátory,
`C-14` sebereferenční ohodnocení mluvčích; nová zkouška `T-11`; nový krok 11
v pořadí stavby; nové mezery `G-30`–`G-36` v příloze A.6.

**Nová hodnota v `C-8`:** `nezáleží` — tvrzení, že na proměnné nezáleží, není
totéž co přiznání `nevím`.

**Rozhodnuto o motorech** (20.4): hlavní je šipkový diagram, záložní Quineovo
částečné vyhodnocení, plná pravdivostní tabulka se přesouvá z produkční cesty
do zkoušek jako orákulum.

**Doplněno do „co vědomě neděláme"** (kap. 41): druhý logický kalkul (Booleova
algebra), predikátová a neklasické logiky, aritmetické slovní úlohy.
