# ZADÁNÍ — conBond4: logické porozumění textu nad vztahy, množinami a identitou

**Stav:** koncept k diskusi. Architektura (moduly, služby, API) se tu záměrně
neřeší — dokument vytěžuje PRINCIPY: jaké textové závislosti nést, jakou
logikou nad nimi zpracovávat otázky (i složené a logické problémy) a proč.
**Vychází z:** zkušenost conBond3 (HANDOVER.md, INTERPRETATION_IR.md) a
z reálných dialogů 10.–11. 8. 2026, které opakovaně narazily na tytéž zdi.
**Vztah k conBond3:** nový koncept, ne úprava — ale přenáší invarianty a
metodiku, které se prokázaly, a jeho akceptační úlohy jsou právě ty dialogy,
na kterých conBond3 selhal nebo musel poctivě odmítnout.

---

## 0 · Jedna věta

Systém, který textu rozumí tak, že z něj staví **vztahy mezi identitami a
množinami**, umí nad nimi **počítat logiku množin a modelů**, a každou
odpověď umí **vysvětlit jako cestu v grafu** — v dialogu s člověkem, který
ho tímtéž dialogem učí.

## 1 · Co chceme, proč, a co ne

**Co chceme.** Porozumění postavené na čtyřech stavebních kamenech:
reifikovaný **vztah** (vztah je uzel s rolemi, může být argumentem jiného
vztahu), **group** (množina výčtem i popisem, s algebrou AND/OR/NOT),
**identita** (anonymní uzel entity, na který se zmínky vážou měkce a
odvolatelně) a **graf** jako společný nosič znalosti, kontextu i statistické
blízkosti. Komunikačním cílem je **vysvětlování vztahů a datových vazeb**
člověku — odpověď není skóre, ale důvod.

**Cílem NENÍ umět odpovědět na všechno.** Cílem je, aby nic významového
nebylo zadrátované: pevné zůstává jen malé uzavřené jádro operací
(algebra groups, role vztahů, `⊆`, komparátory, modální dotazy) — a
**vztahy I logické operace nad nimi vznikají dialogem**: fakta, pravidla,
můstky mezi vztahy (dialog A v § 6.12), mapování slov na operace
z menu, výjimky přes `NOT`. Systém, který řekne NEVÍM, ale dá se
dvěma větami doučit chybějící článek, je cennější než systém, který
odpoví na vše mělce.

**Proč.** Zkušenost conBond3 ukázala, že výroková vrstva s plochými
relacemi narazí vždy na stejných pět zdí:

1. *Příslovce a okolnosti děje* — „Petr rychle jede po dálnici" šlo
   reprezentovat jen složeným jménem relace (`jet_rychle`, `jet_po`), čímž
   se ztratila logická vazba mezi `jet_po` a `jet`. Chybí **reifikace**.
2. *Koordinace* — „k přepravě nákladů a osob" muselo být poctivě odmítnuto.
   Chybí **group**.
3. *Výčtové otázky* — „Jaké znáš spisovatele?" nemá v pravdivostní logice
   vůbec operaci. Chybí **algebra množin**.
4. *Identita* — entita pojmenovaná lemmatem vedla k nesmyslu „auto je
   auto"; „Hrabal" vs. „Bohumil Hrabal" a „člověk"/„lidé" se nescelí.
   Chybí **vrstva zmínka → entita**.
5. *Propady* — když formální vrstva nevěděla, mlčela, a odpovídal
   statistický retrieval bez vztahu k naučenému („Kdo je Hrabal?" →
   „planetka"). Chybí **společný substrát**, kde statistika navrhuje
   v týchž strukturách, ve kterých logika rozhoduje.

**Co nechceme (hranice v1).** Plnou predikátovou logiku (algebra množin =
monadická logika, ta je rozhodnutelná — to je vědomá volba, viz § 6.3),
plnou temporální logiku (čas a místo ANO jako role dějů s uspořádáním a
obsažením — § 3.6; perzistence stavů a kauzalita z následnosti NE),
aritmetiku nad rámec počítání známých prvků, vícevětné dokumenty jako
vstup (systém je dialogový; logický problém se zadává posloupností
tvrzení), a plnou koreferenci napříč dlouhým textem (zájmena řeší
aktivace kontextu, ne diskurzní teorie).

## 2 · Mapa vrstev zpracování odpovědi

Posloupnost, kterou projde každá promluva. Vrstvy V1–V6 jsou pořadí
zpracování; U a G jsou průřezové.

```
V0  PROMLUVA        věta od člověka; tah dialogu (tvrzení / otázka / odpověď na doptání)
V1  ZÁVISLOSTI      morfologie + závislostní strom od vnějšího parseru;
                    výstupem NENÍ jeden strom, ale kandidátní rozbory
V2  ČTENÍ           strukturální vzory nad stromem → kandidátní struktury
                    (kdo je podmět, co je okolnost, kde je koordinace);
                    kaskáda výběru: tvrdé filtry → konzistence → vzory → doptání
V3  IDENTITA        zmínky → uzly (entita / group); měkké „označuje";
                    aktivace grafu jako kontext; doptání při nejednoznačnosti
V4  STAVBA          reifikované vztahy + groups + role místa a času +
                    polarita + způsob (mood);
                    tvrzení → kandidátní znalost, otázka → formální dotaz
V5  LOGIKA          operace nad bází: pravdivost, algebra groups, prostor
                    modelů, výčet, definice, proč — podle druhu otázky
V6  ODPOVĚĎ         verdikt + VYSVĚTLENÍ (podgraf/cesta → čeština);
                    poctivé nevím; doptání jako plnohodnotná odpověď

U   UČENÍ (napříč)  fakta, pravidla, vzory čtení, assigny, scelení —
                    všechno data s proveniencí, statusem a odvolatelností
G   GRAF (napříč)   tvrdé hrany nesou pravdivost, měkké jen blízkost;
                    aktivace = kontext dialogu; záchranná síť všech propadů
```

**Zásada propadů:** žádná vrstva nesmí selhat tiše. Každý propad má tři
poctivé cesty: (a) níže položená vrstva **navrhne** kandidáty a výše
položená rozhodne, (b) **doptání** člověka (a jeho odpověď je anotace —
učení), (c) **odmítnutí s důvodem**. Tichá volba, která mění význam, není
cesta nikdy.

Zbytek dokumentu doplňuje tento scaffold: § 3 stavební kameny reprezentace
(co ve vrstvách teče), § 4 graf, § 5 vrstvy V1–V4, § 6 logika otázek (V5,
jádro zadání), § 7 učení, § 8 odpověď, § 9 invarianty, § 10 měření.

**Meta‑notace ukázek** (v celém dokumentu):

```
(e17)                      anonymní uzel entity (id bez významu)
group{a, b, c}             množina výčtem
group[x | podmínka(x)]     množina popisem (intenzionální)
vztah(jméno · role:x · …)  reifikovaný vztah — uzel s rolemi
zmínka„…"                  úsek promluvy s proveniencí (věta, tokeny)
─označuje→                 měkká vazba zmínky na uzel (hypotéza, odvolatelná)
patří_do, ⊆                členství prvku, podmnožina
AND OR NOT                 algebra nad groups (průnik, sjednocení, rozdíl)
ANO / NE / NEVÍM           verdikty;  MOŽNÁ / NUTNĚ / NEMOŽNÉ  modální
```

---

## 3 · Stavební kameny reprezentace

### 3.0 Zásada skladebnosti — jedna algebra, žádné roztříštěné if/then

**Co chceme.** Všechny objekty reprezentace tvoří **jeden termový jazyk**
s uzavřenou sadou konstruktorů a jedním rekurzivním vyhodnocením:

```
term := uzel                         (entita, místo, čas, instance vztahu)
      | group{term, term, …}         (výčtem — členy jsou LIBOVOLNÉ termy)
      | group[x | podmínka(x)]       (popisem)
      | term AND term | term OR term | term NOT term
      | restrikce(term · role:term)  (zúžení podle role/vlastnosti)
```

Z toho plyne bez zvláštních případů: **groups groups** —
`group{group(náklad), group(osoba)}` je platný term (koordinace tříd);
**složené výrazy** — `group(A) NOT group(B) AND group(C)` se skládá volně
(s explicitními závorkami při renderování, ať člověk vidí uzávorkování);
a **algebra nad vztahy** — typ vztahu (jet, obsahovat) je group svých
reifikovaných instancí, takže `vztah() AND/NOT vztah()` je táž operace
nad jiným druhem členů.

**Proč.** Zkušenost conBond3: každá konstrukce řešená zvláštní větví kódu
(kopule zvlášť, sloveso zvlášť, pasivum zvlášť…) znamenala, že se tytéž
schopnosti dodělávaly třikrát a mezery zůstávaly tam, kam žádná větev
nedosáhla. Skladebnost uchopitelná **vzorem** znamená: nová schopnost se
přidá jako konstruktor nebo pravidlo vyhodnocení JEDNOU a platí pro
všechny objekty. Zároveň je to podmínka testovatelnosti — orákulum
(enumerace modelů) se píše proti termové gramatice, ne proti výčtu
speciálních případů.

**Jak (meta).** Vyhodnocení je strukturální rekurze nad termem; každý
konstruktor má jedno pravidlo. Mez výrazivosti (§ 6.3, I‑13) se hlídá na
gramatice termů, ne v kódu jednotlivých větví.

```
„Kteří spisovatelé, kteří nejsou básníci, žili v Praze?"
   (group(spisovatel) NOT group(básník))
   AND group[x | ∃ r ∈ group(žít): role kdo:x, kde:(e_praha)]
   — tři konstruktory, jedno vyhodnocení, žádný zvláštní případ

„jízdy po dálnici, které nebyly rychlé"
   restrikce(group(jet) · kudy:(e_dalnice)) NOT restrikce(group(jet) · jak:rychle)
   — táž algebra, členy jsou instance vztahů
```

### 3.1 Entita — anonymní uzel identity

**Co chceme.** Identita je uzel bez vnitřního významu (`(e17)`). Nikdy se
nejmenuje lemmatem; všechno lidsky čitelné na ní visí přes vztahy.

**Proč.** Nesmysl „chybí vědět: auto je auto" v conBond3 vznikl přímo
z toho, že entita nesla jméno své třídy. Jmenovci („dva Hrabalové") a
přejmenování dokazují, že jméno nemůže být klíč identity. Oddělení identity
od popisu je podmínka scelování i oprav omylů.

**Jak (meta).** Uzel vzniká, když je potřeba referent (nová jednotlivina
v tvrzení, doptaná instance v otázce). Zánik neexistuje — jen odpojení
vazeb. Kanonické zobrazení pro člověka = nejdelší potvrzené jméno.

### 3.2 Zmínka a měkké „označuje"

**Co chceme.** Zmínka je nezpochybnitelná kotva: úsek promluvy s proveniencí
(která věta, které tokeny). Vazba `zmínka ─označuje→ uzel` je **hypotéza**
se statusem (hypotéza → potvrzeno → odvoláno) a proveniencí. **Tvrzení se
kotví na zmínku**, ne přímo na entitu.

**Proč.** Když se ukáže, že „tenhle Hrabal byl jiný Hrabal", převáže se
jedna měkká hrana a znalost se přestěhuje s ní — nic se destruktivně
nepřepisuje. Tvrdý assign by omyl v identitě proměnil v chirurgii báze.
Totéž se v conBond3 osvědčilo u naučených jazykových vzorů (odvolání maže
mapování, ne operaci) — zde se týž životní cyklus zobecňuje na identitu.

**Jak (meta).**

```
zmínka„Hrabal" (věta 12, token 3)
   ─označuje→ (e17)          [hypotéza; evidence: jméno + aktivace kontextu]
(e17) ─jmenuje_se→ group{„Hrabal", „Bohumil Hrabal", „B. Hrabal"}
tvrzení T31: vztah(být · kdo:zmínka„Hrabal" · co:group(spisovatel))
             — vyhodnocuje se PŘES označuje, tedy o (e17)
```

### 3.3 Group — množina výčtem i popisem, v otevřeném světě

**Co chceme.** Group má dvě podoby: **výčtem** (`group{e17, e33}`) a
**popisem** (`group[x | vztah(obsahovat · kdo:x · co:group(vitamín))]`).
Obě jsou uzly grafu. Členem group smí být **libovolný term** (§ 3.0) —
tedy i group (`group{group(náklad), group(osoba)}` — skupina skupin,
přirozený tvar koordinace tříd) a i instance vztahu. Základní operace:
členství (`patří_do`), podmnožina (`⊆`), algebra `AND / OR / NOT` volně
skládaná, výčet známé extenze, mohutnost známé extenze.

**Proč.** Groups pohlcují tři dnešní slepé uličky najednou: koordinaci
(„náklady a osoby" = group), výčtové otázky („Jaké znáš spisovatele?" =
extenze group) a doptání instance/třída (instance = prvek, třída = group —
z ad‑hoc dialogu se stává množinová otázka). Popisové groups navíc nesou
pravidla: „Ovoce obsahuje vitamíny" je vztah nad group, ne pravidlo
s proměnnou v cizí syntaxi.

**Jak (meta) — disciplína otevřeného světa.** Extenze group v bázi je
**dolní odhad**: „znám tyto prvky; zda jsou všechny, nevím." Z toho plynou
tři povinnosti: (1) výčet se hlásí jako „znám", ne „existují právě";
(2) `NOT` je bezpečný jen nad known‑extenzí a odpověď to musí říct;
(3) univerzální tvrzení („každé ovoce…") se ověřuje pravidlem/modely, ne
projitím známých prvků.

```
group(ovoce): známí členové {citron, pomeranč, jablko}
„Kolik je druhů ovoce?"  →  „Znám tři. Jestli jsou všechny, nevím."
```

### 3.4 Vztah — reifikace a role; vztah(vztah)

**Co chceme.** Vztah je uzel s pojmenovanými rolemi:
`vztah(jet · kdo:(e_petr) · kudy:(dálnice) · jak:rychle)`. Role vznikají
strukturálně (podmět, předmět, předložka/pád, příslovce), ne ze seznamu
slov. Vztah smí být argumentem jiného vztahu: `vztah(chtít · kdo:(e_petr)
· co:vztah(mít · kdo:(e_petr) · co:…))`.

**Proč.** Reifikace řeší najednou: okolnosti děje (dnes ztracené nebo
zakleté do jmen `jet_po`), logickou vazbu mezi „jede po dálnici" a „jede"
(role navíc nemění jádro vztahu — vyplývání je zadarmo), a hlavně otevírá
propoziční postoje, modalitu, „protože" a nepřímou řeč — vše jsou vztahy
nad vztahy, které dnes potřebují zvláštní mechanismy mimo objektový jazyk.

**Jak (meta).**

```
„Petr rychle jede po dálnici."
  V4:  R1 = vztah(jet · kdo:(e_petr) · kudy:(e_dalnice) · jak:rychle)
„Jede Petr po dálnici?"   → hledám vztah jet s rolemi kdo:(e_petr),
  kudy:(e_dalnice); R1 je má (jak:rychle navíc nevadí) → ANO
„Jede Petr?"              → hledám jet s kdo:(e_petr) → R1 → ANO
„Jede Petr pomalu?"       → role jak:pomalu na R1 není a rychle≠pomalu
                            → NEVÍM (bez znalosti neslučitelnosti), nebo NE
                            (je-li rychle/pomalu deklarováno neslučitelné)
```

**Typ vztahu = group jeho instancí.** `group(jet)` je množina všech
reifikovaných jízd; tím se na vztahy vztahuje celá algebra z § 3.0
(`restrikce`, `AND/NOT`) bez jediného zvláštního případu — „jízdy po
dálnici, které nebyly rychlé" je běžný term.

Pozor na hranici: skládání vztahů je výrazově silné a obecná algebra relací
je nerozhodnutelná. Zadání proto žádá **předem narýsovanou a strojově
hlídanou mez** (jako kap. 41 v conBond3): role jsou konečné, vnořování
vztahů povolené do hloubky 1 (postoje o faktech; mez je modifikovatelný
parametr — § 12/3), kvantifikace zůstává na úrovni groups (§ 6.3).

### 3.5 Jména a scelení

**Co chceme.** Jména entity/group tvoří group povrchových tvarů
(`jmenuje_se`); scelení dvou uzlů je měkký vztah `totožný(e17, e31)`
s evidencí, dotazy čtou přes uzávěr ekvivalence, kanonický reprezentant
deterministicky.

**Proč.** „Hrabal"/„Bohumil Hrabal" i „člověk"/„lidé" jsou týž problém —
více jmen jednoho uzlu — a jedna jmenná vrstva ho řeší pro entity i
třídy. Měkkost scelení: špatné scelení otráví inferenci, špatné oddělení
znamená jen „vím méně" — proto **výchozí je oddělenost, sceluje se na
evidenci** a rozpad scelení je odvolání hrany, ne oprava báze.

### 3.6 Prostor a čas — místa a děje v čase, párované na fakta

**Co chceme.** Dvě veličiny jako plnoprávné termy: **místo** a **čas**.
Děj (instance vztahu) se na ně páruje **rolemi**: `kde/kam/odkud/kudy`
pro prostor, `kdy` pro čas. Fakta se tím dělí na **generická** (bez
časoprostorových rolí — „Ovoce obsahuje vitamíny", platí obecně) a
**epizodická** (ukotvené děje — „Petr jel včera do Prahy"). Obojí jsou
tytéž struktury, liší se jen přítomností rolí — žádný zvláštní druh
objektu.

**Proč.** Bez času a místa nejde mluvit o dějích, jen o vlastnostech —
a dialog o světě je hlavně o dějích. Zároveň zkušenost velí nekupovat
plnou temporální logiku: stačí dvě disciplíny, které se **vejdou do už
zavedených vzorů** (§ 3.0), takže nepřidávají roztříštěné if/then:

- **Prostor = hierarchie obsažení.** Místa jsou uzly, `⊆` mezi nimi je
  táž podmnožinová relace jako u groups (Praha ⊆ Česko ⊆ Evropa).
  Prostorové usuzování je pak algebra, kterou už máme: děj v Praze je
  dějem v Česku, protože role `kde` se čte přes `⊆`.
- **Čas = uspořádaná osa.** Hodnoty role `kdy` jsou body/intervaly na
  ose s uspořádáním; primitivní predikáty `před / po / během / překrývá`
  jsou rozhodnutelné porovnání intervalů. Kalendářní jména („včera",
  „v roce 1965") jsou jen jména intervalů — jmenná vrstva § 3.5 platí
  i tady.

**Jak (meta).** Párování na fakta: čas a místo jsou role na uzlu vztahu,
takže dotazy v prostoru a čase jsou `restrikce` termy — filtrování groups
instancí podle rolí čtených přes `⊆` (prostor) a přes intervalové
predikáty (čas). Minulý čas věty navrhne `kdy: před(teď)` jako výchozí
ukotvení (jen návrh — jazyk navrhuje); „teď" je tah dialogu, ne hodiny
stroje (determinismus, I‑4).

```
„Petr jel včera do Prahy."
  R7 = vztah(jet · kdo:(e_petr) · kam:(e_praha) · kdy:(včera))
       (e_praha) ⊆ (e_cesko) ⊆ (e_evropa);  (včera) = interval na ose

„Byl včera Petr v Česku?"
  restrikce(group(jet) · kdo:(e_petr) · kdy⊆(včera) · kam⊆(e_cesko))
  → R7 vyhovuje (Praha ⊆ Česko) → ANO — „jel do Prahy a Praha je v Česku"

„Co dělal Petr včera?"
  výčet: group[r | role kdo:(e_petr) AND kdy(r) během (včera)]
  → „Jel do Prahy. Jestli něco dalšího, nevím."   (otevřený svět, I‑11)

„Jel Petr do Prahy před návštěvou Brna?"
  kdy(R7) před kdy(R9)?  — porovnání intervalů; bez ukotvení → NEVÍM
  + „chybí vědět: kdy byl v Brně"
```

**Obecné veličiny a komparátory.** Vzor „uspořádaná osa" z času platí pro
každou měřitelnou veličinu (rychlost, délka, hmotnost…): hodnota
s jednotkou je bod na ose dané veličiny. Číselné literály jsou
**počítatelné primitivy** (rozpoznání „130" a porovnání dvou čísel je
mechanické a deterministické); jednotka je jméno osy — porovnávat lze jen
na téže ose. Nad osou existuje **uzavřené menu komparátorů**
`≤ < = > ≥ ≠` — a jazyk se na ně **mapuje učením v dialogu**, přesně
podle vzoru, který se osvědčil u modality v conBond3: dialog učí, KTERÉ
slovo spouští KTERÝ existující komparátor („nejvýše/omezení/nesmí
překročit" → `≤`, „aspoň/minimálně" → `≥`), nikdy nevyrábí nový. Omezení
(„nejvýše 130 km/h") je pak interval povolených hodnot — constraint, nad
kterým fungují modální dotazy (§ 6.7). Aritmetika (převody jednotek,
počítání s hodnotami) zůstává za hranicí v1 — v mezích je jen porovnání
a příslušnost do intervalu.

```
! Rychlost se měří v km/h.            → veličina „rychlost", osa s jednotkou
! „Omezená rychlost" znamená, že se nesmí jet rychleji.
   → mapování [hypotéza, dialog]: omezení(V) ⇒ rychlost děje ≤ V
   → systém ověří čtení: „Tedy: omezení 130 km/h dovoluje 90, ale ne 150?"
! Ano.                                → mapování potvrzeno
   — sémantika ≤ je pevná (menu); naučené je jen SLOVO → KOMPARÁTOR
```

Každou veličinovou doménu obsluhuje **specialista** za jednotnou smlouvou
(rozpoznat hodnotu, normalizovat, uspořádat, porovnat, pojmenované
intervaly, render): „Chronos" pro čas, „Topos" pro prostor, další pro
míry — dodávají jen primitivní predikáty své osy, algebra zůstává jedna
(rozhodnutí § 12/6).

**Hranice v1:** párování a dotazování ano (role, obsažení, pořadí,
intervaly); plná temporální LOGIKA ne — žádná perzistence stavů („když
byl v Praze v poledne, byl tam i v jednu?" → NEVÍM), žádná kauzalita
z časové následnosti (po tom ≠ proto). Obě zúžení jsou zapsaná a
odmítají se s důvodem, ne tiše.

### 3.7 Meta‑kód: zápis, který roste učením

**Co chceme.** Vnitřní reprezentace je **textový meta‑kód** — deklarativní
jazyk nad termovou gramatikou § 3.0, interpretovaný pevným jádrem. Vše
naučené je řádek kódu s proveniencí; báze znalostí JE program. Klíčové
rozlišení: **učením se mění program, nikdy jazyk.** Gramatika a interpret
jsou malé pevné jádro (verzované, změna jen vědomým rozhodnutím — I‑13);
učení smí řádky přidávat a odvolávat, nikdy předefinovat konstruktory
nebo vyhodnocení.

**Proč.** (1) *Persistence = zdrojový kód*: čitelná, diffovatelná,
verzovatelná — „ukaž, co ses naučil" je výpis programu, ne dump.
(2) *Deterministické přehrání*: žurnál dialogu + pevný interpret ⇒ týž
program ⇒ tytéž odpovědi — základ měření i ladění. (3) *Jednotnost místo
if/then* (§ 3.0 dotažené do konce): znalost, jazykové vzory i dialogový
protokol jsou tři programy v JEDNOM jazyce, ne tři mechanismy. conBond3
tenhle princip nakousl (vzory jako JSON s proveniencí, kb.json) — tady se
povyšuje na nosnou formu.

**Jak (meta).** Konvence zápisu (rozhodnutí J.): klíčová slova, role,
operace a anotace **anglicky** — jako identifikátory v kódu; **lexikální
materiál z dialogu** (lemmata, jména, pojmenování veličin) zůstává
českými daty — přejmenovat „auto" na „car" by falšovalo provenienci;
**komentáře česky**. A tvrdé syntaktické pravidlo, aby česká data jasně
vynikla nad definicí struktur: **co je v uvozovkách, je naučený jazyk;
co je bez uvozovek, je struktura.** Nic českého se nesmí objevit bez
uvozovek, nic strukturního v uvozovkách — na první pohled (i pro
zvýrazňovač syntaxe) je vidět, co je pevné jádro a co vyrostlo dialogem.
Identifikátory uzlů (`e17`, `a1`) jsou neprůhledná id; lidsky čitelná
přípona (`e_filip`) je jen pohodlí bez významu. Tři vrstvy programu nad
jedním jádrem:

```
# ONTO — znalostní program (fakta, pravidla, identita)
entity e17.
name e17 {"Hrabal", "Bohumil Hrabal"}.                @dialog(t12, confirmed)
member e17 group("spisovatel").                       @dialog(t12)
group DP := group("prostředek") AND property("dopravní").
rule r4: for r in group("jezdit"):
    (rel:"omezení" · of:via(r) · limit:V)  =>  measure(r,"rychlost") <= V.
                                                      @confirmed(t31)
rule p1b: (rel:"létat" · who:(group("pták") NOT group{e_tucnak})).
                                                      @revision(k7)

# LEX — jazykový program (učená mapování; nikdy nová sémantika)
reading "obsahovat" [Sg×Pl] -> roles(who:1, what:2).  @annotation(t9)
word    "nejvýše"   -> comparator(<=).                @confirmed(t30)
role    "kudy" ~ prep("po")+Loc.                      @hypothesis

# DIA — dialogový automat (deklarativní stavy doptání)
state awaiting_reference(mention, candidates):
    ask "Myslíš {candidates}?"          # otázky člověku se renderují česky
    answer -> attach_assign(mention)                  # odpověď = anotace
state awaiting_rule_confirmation(rule):
    ask "Mám z toho usoudit: {rule}?"
    yes -> attach(rule);  no -> remember_rejection
```

Interpret je **stratifikovaný**: čte LEX, aby rozuměl větě; čte ONTO, aby
odpověděl; čte DIA, aby vedl rozhovor. Učicí operace (z doptání, anotací,
oprav konfliktů) smí jen `attach` / `revoke` řádky — kód smí generovat
kód (potvrzená hypotéza zapíše pravidlo), ale nikdy měnit interpret.
Meta‑kód NENÍ obecný programovací jazyk: žádné smyčky ani rekurze
v uživatelském prostoru, jen deklarace — terminace je zaručená konstrukcí
(mez rozhodnutelnosti, I‑13).

**Rozhraní kód ↔ graf.** Meta‑kód nevolá graf přes API — **každý řádek JE
delta grafu**: `entity` zakládá uzel, `member`/`name` tvrdou hranu,
`relation` reifikovaný uzel s hranami rolí, `rule`/`constraint` pravidlový
uzel. Z toho plynou čtyři vlastnosti rozhraní:

1. **Adresovatelnost hran:** každý řádek má id výroku (`s41`, `p3`, `r1`)
   — „sáhnout na hranu" = odkázat se na výrok, který ji postavil
   (`revoke(s44)`), a vysvětlení odpovědi je seznam id výroků, které se
   použily (§ 8: render skutečně použité struktury).
2. **Identifikace uzlů:** v uloženém kódu VŽDY neprůhledným id (`a1`).
   Popisem (`restrict(group("auto") · owned_by:e_filip)`) se uzel smí
   určit jen v OKAMŽIKU zápisu — rozřešení proběhne při `attach` a do
   faktu se uloží výsledné id (`@resolved:a1`). Popis se do faktu
   neukládá, jinak by význam driftoval: kdyby si Filip zítra koupil
   druhé auto, včerejší „Filipovo auto je modré" nesmí změnit referent.
3. **Celé rozhraní jsou čtyři operace:** `attach(výrok) → id` (jediný
   zápis; rozřeší popisy), `revoke(id, důvod)` (jediné mazání — hrana
   zůstává v historii), `eval(term) → uzly/verdikt` (čtení; otázky
   nepíší nic), `inspect(id) → okolí + provenience` (pro vysvětlení
   a UI — klik na uzel v okně grafu vypíše řádky kódu, které ho
   postavily; kruh kód ↔ graf ↔ člověk se uzavírá).
4. **Měkká vrstva do kódu nepatří:** spoluvýskyty a aktivace se počítají
   za běhu z žurnálu a korpusu — jsou to odvozené statistiky, ne výroky;
   smí se kešovat, ale `attach`/`revoke` na ně nesáhne (I‑8).

```
s40: entity a1.                                @instantiate(t1)
s41: member a1 group("auto").                  @presuppose(t1)
s44: member a1 group("modrý").                 @stated(t2, resolved:a1)
s45: name a1 +{"Ford"}.                        @assign(t4, confirmed)

inspect(a1) → { s40, s41, s44, s45, r1 }       # proč uzel existuje a co nese
revoke(s44, "oprava: bylo červené")            # sáhnutí na konkrétní hranu
```

**Rizika řečená předem:** bujení gramatiky (každá feature „jen jeden nový
konstruktor") — proto změny gramatiky jen rozhodnutím a s verzí v hlavičce
každého souboru; a dvojí pravda (graf v paměti × kód na disku) — proto
**kód je jediný zdroj pravdy**, běhový graf je jeho deterministické
vyhodnocení/index, kdykoli znovu sestavitelné.

**Meta‑ukázka: program rostoucí dialogem** (spojuje dialogy F a A —
u každého tahu je vidět, CO přesně se připsalo a s jakou proveniencí):

```
%% conbond4-metacode v0.1         # verze gramatiky — mění se jen rozhodnutím
%% journal: dialog-2026-08-11     # přehrání žurnálu ⇒ týž program (I-16)

# ——— t1   ! „Filip má auto."
entity e_filip.                                @mention(t1, "Filip")
entity a1.                                     @instantiate(t1, "auto" neurčitě)
member a1 group("auto").                       @presuppose(t1)
relation r1 = (rel:"mít" · who:e_filip · what:a1).      @stated(t1)

# ——— t2   ! „Filipovo auto je modré."
#   určitý popis restrict(group("auto") · owned_by:e_filip) → jediný a1
member a1 group("modrý").                      @stated(t2, resolved:a1)

# ——— t3   ! „Filip má Ford."
#   zmínka „Ford" bez uzlu i skupiny → nic se nepřipisuje;
#   DIA → awaiting_reference("Ford", candidates:{a1, new})
#   >>> „Ford neznám. Je to to modré auto, co Filip má, nebo něco dalšího?"

# ——— t4   ! „Je to to auto."
name a1 +{"Ford"}.                             @assign(t4, confirmed)

# ——— t5   ? „Co je Ford?"
#   dotaz NIC nepřipisuje (I-12); vyhodnocení: „Ford"→a1, okolí(a1)
#   >>> „Ford je auto — modré, a má ho Filip."

# ——— t10  ! „Dálnice má omezenou rychlost na 130 km/h."
quantity "rychlost" axis(km/h).                # doména měr (specialista)
value v130 = 130 km/h.                         # číselný literál = primitiv
relation r7 = (rel:"omezení" · of:group("dálnice")
               · quantity:"rychlost" · limit:v130).     @stated(t10)
# LEX (naučeno dřív):  word "omezená rychlost" -> comparator(<=).   @t8

# ——— t11  ? „Jak rychle může jezdit auto po dálnici?"
#   dedukce z ONTO: auto⊆DP, (rel:"jezdit" · who:DP · via:group("dálnice"))
#   — ale r7 mluví o dálnici, ne o jízdách → MEZERA
#   DIA → awaiting_rule_confirmation
#   >>> „Mám usoudit: co jede po místě s omezením V, jede nejvýše V?"

# ——— t12  ! „Ano."
rule p3: for r in group("jezdit"):
    (rel:"omezení" · of:via(r) · limit:V) => measure(r,"rychlost") <= V.
                                               @confirmed(t12)
#   >>> „Nejvýše 130 km/h."     [důvod: auto⊆DP, jezdí po dálnici, r7, p3
#                                — řetěz se renderuje, § 8]

# ——— t20  konflikt k7: „Tučňák nelétá." × odvození z p1 („Ptáci létají.")
revoke p1.                                     @revision(k7, choice:narrow)
rule p1b: (rel:"létat" · who:(group("pták") NOT group{e_tucnak})).
                                               @revision(k7)
#   staré p1 zůstává v historii s odvoláním — nic se nemaže, jen neplatí
```

Za povšimnutí: jediné operace učení jsou `attach` (nový řádek) a
`revoke` (zneplatnění s důvodem); otázky nepíší nic; každý řádek nese
`@provenienci` s tahem; a celý stav systému v kterémkoli okamžiku je
tenhle soubor — nic víc.

---

## 4 · Graf — nosný substrát

**Co chceme.** Jeden multigraf: uzly = entity, groups, vztahy, zmínky.
Hrany dvou disciplín: **tvrdé** (členství, podmnožina, role vztahů, jména,
označuje/totožný se statusem) nesou pravdivost; **měkké** (spoluvýskyt,
tematická blízkost, následnost zmínek v dialogu) nesou jen **aktivaci**.
Aktivace: zmínka vstříkne energii, šíří se po hranách, vyhasíná **po tazích
dialogu** (ne po čase — determinismus). Stav aktivace = kontext rozhovoru.

**Proč.** V conBond3 stál graf vedle logiky (retrieval) a formální vrstva
ho nečetla — proto „Kdo je Hrabal?" odpovídalo „planetka" i po naučení
faktu. Společný substrát dává statistice roli, kterou invarianty dovolují:
navrhovat a řadit v týchž strukturách, ve kterých tvrdá vrstva rozhoduje.
A vysvětlení je zadarmo: každé rozhodnutí grafu je cesta nebo podgraf,
který jde vyrenderovat člověku — systém neukazuje skóre, ukazuje mapu.

**Jak (meta) — graf jako záchranná síť propadů:**

```
propad čtení      → vyhrává čtení, jehož vztahová signatura v grafu existuje
                    nebo spojuje aktivované uzly
propad jména      → kandidáty řadí aktivace (naposledy zmíněné uzly)
propad odpovědi   → místo mlčení okolí uzlu: „nevím, jestli X, ale o citronu
                    vím: patří do ovoce, ovoce obsahuje vitamíny…"
propad ukotvení   → nové tvrzení se věší do aktivního podgrafu
propad identity   → kandidáti na totožný = sdílená jména + překryv okolí;
                    evidence scelení = ten sdílený podgraf (ukazatelná)
```

**Guard tesaný do kamene:** pravdivost nikdy neteče po měkké hraně a
aktivace nikdy nezvyšuje jistotu tvrzení — blízkost není důkaz. Měkká
vrstva smí jen řadit a navrhovat; rozhoduje tvrdá vrstva, nebo doptání.

**UI důsledek:** okno grafu zobrazuje skutečný znalostně‑identitní graf;
rozsvícení = aktivace. Člověk vidí kontext, kterým systém právě myslí.

---

## 5 · Od textu ke struktuře (V1–V4)

### 5.1 Závislosti: kandidátní rozbory, ne jeden strom

**Co chceme.** Parser je vnější orákulum morfologie a syntaxe, ale jeho
výstup se bere jako **návrh**. Kde je rozbor tvarově nejednoznačný, pracuje
se s množinou kandidátních čtení.

**Proč.** Reálná zeď z dialogů: „Obsahuje citron vitamíny?" dostal od
parseru rozbor **bez podmětu** (nominativ = akuzativ, oba nominály `obj`).
Žádná logika nad špatným stromem nezachrání význam; jediná poctivá cesta
je generovat čtení a vybírat — nebo se doptat.

### 5.2 Kaskáda výběru čtení

**Co chceme.** Deterministickou kaskádu, kde každé patro umí říct PROČ:

```
generátor kandidátních čtení   (kombinatorický: záměny rolí, přijatelné stromy)
  → tvrdé filtry               (shoda podmět–přísudek: číslo/rod; pádová mřížka)
  → konzistence s bází         (signatury známých vztahů; aktivované uzly)
  → naučené vzory čtení        (z uživatelských anotací; data, odvolatelná)
  → [volitelný ranker]         (učený, jen řadí; nikdy netvoří strukturu)
  → doptání                    (malý rozdíl skóre → otázka; odpověď = anotace)
```

**Proč.** Morfologie češtiny nese tvrdé signály, které jeden vybraný strom
zahazuje: v příkladu výše je „obsahuje" singulár a „vitamíny" plurál —
vitamíny nemohou být podmět; případ je vyřešen bez jakéhokoli učení.
Statistika (vzory, ranker) je až za tvrdými filtry a bází, protože
dialogový objem anotací jsou desítky, ne tisíce — strukturní vzory
s renaming testy generalizují lépe a jsou auditovatelné. Ranker, pokud
vůbec, jen řadí kandidáty a jeho volba se ukazuje.

**Meta‑ukázka:**

```
„Obsahuje citron vitamíny?"
čtení A: vztah(obsahovat · kdo:citron · co:vitamíny)
čtení B: vztah(obsahovat · kdo:vitamíny · co:citron)
filtr shody: sloveso Sing, „vitamíny" Plur ⇒ B padá        [PROČ: shoda čísla]
V5 dál pracuje s A; kdyby obě přežily → „Čtu to jako: citron obsahuje
vitamíny — správně?" a odpověď se uloží jako vzor čtení.
```

### 5.3 Rozřešení zmínek (identita v běhu dialogu)

**Co chceme.** Tutéž kaskádu pro zmínky: kandidátní uzly podle jmen
(včetně částečné shody „Hrabal" ⊆ „Bohumil Hrabal" a singulár/plurál) →
tvrdé filtry (vlastní jméno → entita, obecné jméno → group; rod/číslo) →
aktivace grafu → konzistence tvrzení s kandidátem → doptání.

**Proč.** Zájmena („on", „to") jsou v tomto pohledu jen maximálně
nejednoznačné zmínky — koreference přestává být zvláštní feature a stává se
krajním případem téže kaskády, kde rozhoduje skoro jen aktivace. A dnešní
doptání „instance, nebo třída?" dostává čistou formulaci: zmínka „auto"
kandiduje buď na novou anonymní entitu s **presupozicí členství**
(kdo se ptá na „konkrétní auto", jeho auto‑ství nezpochybňuje — poučení
z opravy „auto je auto"), nebo na group samotnou.

Zvláštní síla kaskády: **určité popisy**. „Filipovo auto", „to modré
auto" jsou termy `restrikce(group(auto) · vlastník:(e_filip))` — rozřeší
se na už zavedený uzel, je‑li známý kandidát jediný; při více kandidátech
doptání („které z jeho dvou aut?"); při žádném podle kontextu buď nová
instance, nebo „o žádném Filipově autě nevím". Neurčitá zmínka
v tvrzení („Filip má auto") naopak **instanciuje** nový anonymní prvek
množiny — viz dialog F (§ 6.12).

### 5.4 Stavba struktury

**Co chceme.** Z vybraného čtení a rozřešených zmínek vzniká struktura:
predikace → uzel vztahu s rolemi; přívlastky podmětu → popis podmětu
(u group do podmínky, u entity fakt — poučení z „Dopravní prostředek je
určen…"); koordinace → group; polarita a způsob (oznamovací/tázací) →
mood struktury. Co stavba neunese, je odmítnutí s důvodem.

**Meta‑ukázka (koordinace, dnes nemožná):**

```
„Dopravní prostředek je určen k přepravě nákladů a osob."
group_DP = group[x | x patří_do group(prostředek) AND x má_vlastnost dopravní]
R = vztah(určit · co:group_DP · k:vztah(přeprava · čeho:group{group(náklad),
                                                             group(osoba)}))
```

---

## 6 · Logika otázek (V5) — jádro zadání

### 6.0 Zásady společné všem otázkám

- **Otázka nikdy nemění bázi.** Čtecí operace; i presupozice žijí v kopii.
- **NEVÍM ≠ NE ≠ chyba.** Trojhodnotová disciplína se přenáší beze změny;
  u groups se rozšiřuje o „známá extenze je dolní odhad".
- **Každý verdikt nese důvod** (cestu/podgraf/protipříklad) nebo chybějící
  premisy („chybí vědět: …").
- **Doptání je odpověď.** Nejednoznačná otázka nedostane hádanou odpověď,
  ale volbu — a volba systému něco naučí.
- **Konflikt v bázi se u dotčené otázky hlásí**, nepřepisuje a neskrývá.

### 6.1 Pravdivostní otázky (jednoduché)

**Co chceme.** „Je/má/dělá X Y?" → existuje (nebo plyne) příslušný vztah?
Verdikt ANO/NE/NEVÍM + důvod.

**Jak (meta).** Otázka se přeloží na vzor vztahu s rolemi; hledá se přímé
tvrzení, odvození přes pravidla (vztahy nad groups + členství), nebo
protipříklad. Role navíc v bázi nevadí (viz § 3.4 — „jede rychle po
dálnici" odpovídá i na „jede po dálnici?").

```
„Obsahuje citron vitamíny?"
e_c patří_do group(citron) ⊆ group(ovoce)
R: vztah(obsahovat · kdo:group(ovoce) · co:group(vitamín))
⇒ ANO.  Důvod: citron → ovoce → obsahuje vitamíny   (cesta, 2 hrany)
```

### 6.2 Složené otázky: a / nebo / negace / alternativa

**Co chceme.** Spojky uvnitř otázky jako logické operace nad dílčími
dotazy — včetně **alternativní otázky**, jejíž odpověď není ANO/NE, ale
vybraný člen.

**Proč.** Složená otázka je nejčastější přirozený tvar („Je citron ovoce a
obsahuje vitamíny?") a v conBond3 existovala jen jako konjunkce atomů
z jedné predikace. Zde se skládá obecně, protože každý dílčí dotaz je
samostatně vyhodnotitelná struktura.

**Jak (meta).**

```
„Je citron ovoce a obsahuje vitamíny?"
   Q1 ∧ Q2;  Q1=ANO, Q2=ANO ⇒ ANO (oba důvody)
   Q1=ANO, Q2=NEVÍM ⇒ NEVÍM + „jistě vím: je ovoce; nevím: vitamíny"
   — částečná odpověď je povinná; holé NEVÍM by zahodilo známou půlku.

„Je citron ovoce, nebo zelenina?"          (alternativní otázka)
   vyhodnoť oba členy; právě jeden ANO ⇒ odpověz členem: „Ovoce."
   oba NEVÍM ⇒ NEVÍM; oba ANO ⇒ hlásit (podezření na konflikt/nesoulad)

„Není citron zelenina?"                    (negativní otázka)
   vyhodnoť jádro bez negace a odpověz k jádru: „Citron zelenina není."
   (odpovídat „ano/ne" na zápornou otázku je v češtině dvojznačné —
    systém odpovídá celou větou, ne částicí)
```

### 6.3 Kvantifikované otázky = algebra groups

**Co chceme.** „Každý/nějaký/žádný" jako množinové testy: `⊆`, neprázdný
průnik, prázdný průnik. To je páteř logiky slov: **booleovská algebra nad
groups odpovídá monadické predikátové logice, a ta je rozhodnutelná** —
sylogistika je pak triviální důsledek.

**Proč.** Rozhodnutelnost drží metodiku conBond3: enumerace konečných
modelů zůstává orákulem, proti kterému se všechno měří. A přirozené
usuzování typu „Každé A je B, žádné B není C ⇒ žádné A není C" dostává
přímou, vysvětlitelnou reprezentaci.

**Jak (meta).**

```
„Obsahuje každé ovoce vitamíny?"   group(ovoce) ⊆ group[x | obsahovat(x, vitamín)]
   — ověřuje se pravidlem/modely (arbitrární instance), NE projitím
     známých prvků (otevřený svět!)
„Obsahuje nějaké ovoce hořčík?"    průnik neprázdný? známý prvek ⇒ ANO+příklad;
   žádný známý a nic to nevynucuje ⇒ NEVÍM („neznám žádný, ale nemohu vyloučit")
„Žádný pták není savec?"           group(pták) AND group(savec) = ∅ ?
   — ANO jen s pravidlem/constraintem; prázdný známý průnik nestačí

Sylogismus:
   „Každý spisovatel je člověk. Hrabal je spisovatel. Je Hrabal člověk?"
   (e17) patří_do group(spisovatel) ⊆ group(člověk) ⇒ ANO, cesta 2 hrany
```

### 6.4 Výčtové a početní otázky

**Co chceme.** „Kteří/jaké/co všechno…?" → extenze group (i složené
algebrou); „Kolik…?" → mohutnost známé extenze. Vždy s otevřeně‑světovou
doložkou.

**Proč.** Reálná otázka z dialogů („Jaké znáš spisovatele?") neměla
operaci. „Znáš" je přitom přesně poctivá sémantika: výčet známého.

**Jak (meta).**

```
„Jaké znáš spisovatele?"        extenze group(spisovatel) → „Hrabala. Víc neznám."
„Kteří spisovatelé nejsou básníci?"
   group(spisovatel) NOT group(básník) — POZOR otevřený svět:
   „Z těch, které znám: Hrabal — nevím o něm, že je básník."
   (rozdíl „nevím, že je" × „vím, že není" se musí v odpovědi rozlišit)
„Kolik druhů ovoce znáš?"       |extenze| → „Tři: citron, pomeranč, jablko."
```

### 6.5 Definiční a srovnávací otázky

**Co chceme.** „Kdo/co je X?" → okolí uzlu (členství, vlastnosti, vztahy)
vyrenderované do češtiny; „Co mají společného X a Y?" → průnik popisů.

**Proč.** Definiční otázky se v conBond3 dodělaly na konci jako výčet
literálů; zde jsou přirozený případ „odpověď = podgraf". Srovnání je
množinová operace nad okolími — další případ, kdy algebra groups pokrývá
běžnou komunikační potřebu.

**Jak (meta).**

```
„Kdo je Hrabal?"      okolí (e17): patří_do spisovatel; napsal Postřižiny
                      → „Spisovatel; napsal Postřižiny."
„Co mají společného citron a pomeranč?"
   popis(e_c) AND popis(e_p) → „Oba jsou ovoce. Jestli něco dalšího, nevím."
```

### 6.6 Vztahové řetězce

**Co chceme.** Otázky, jejichž odpověď je cesta: „Čí je…?", „Kde je…?",
„Přes co souvisí X s Y?". Řetězení vztahů je ale **jen po pravidlech**,
nikdy volnou asociací.

**Proč.** Cesta v grafu je sugestivní a právě proto nebezpečná: z „Praha
je hlavní město Česka" a „Česko je v Evropě" plyne „Praha je v Evropě"
jen díky pravidlu o hlavních městech — bez něj je odpověď NEVÍM + nabídka
řetězu jako hypotézy. Tady se láme rozdíl mezi tvrdou hranou (smí nést
inferenci) a měkkou (smí jen navrhnout).

```
„Je Praha v Evropě?"
   bez pravidla: NEVÍM + „vím: Praha je hlavní město Česka, Česko je
   v Evropě — mám z toho usoudit, že co je hlavním městem země, je v ní?"
   → potvrzení člověka = nové pravidlo (učení doptáním)
```

### 6.7 Modální otázky

**Co chceme.** „Může/musí/nemůže" zůstávají **dotazy nad prostorem
modelů** (∃M/∀M/¬∃M), ne operátory objektového jazyka — guard z conBond3
se přenáší doslova, včetně `grounded` („plyne to" × „nic tomu nebrání").

```
„Může být citron zelenina?"
   constraint ovoce ∦ zelenina + citron⊆ovoce ⇒ NEMOŽNÉ → „Ne."
   bez constraintu ⇒ MOŽNÁ, negrounded → „Nic, co vím, tomu nebrání."
```

### 6.8 Proč a proč ne

**Co chceme.** „Proč X?" → derivační cesta s proveniencí („protože …,
doloženo: dialog 11. 8."); „Proč nevíš?" → chybějící premisy („chybí
vědět: …", bez duplicit). Vysvětlení je renderovaný podgraf, tj. tatáž
struktura, kterou systém skutečně použil — ne dodatečná racionalizace.

### 6.9 Logické problémy (více vět)

**Co chceme.** Úloha zadaná posloupností tvrzení + otázka → constraint
model nad groups a vztahy → prostor modelů: jediné vyhovující rozložení =
odpověď; více rozložení = NEVÍM + co by rozhodlo; žádné = konflikt zadání.

**Proč.** Toto je lakmus logického porozumění (úlohy Bartlové v conBond3):
nejde o vyhledání, ale o eliminaci nad konečnou doménou. Groups + vztahy
s kardinalitními omezeními na to stačí a enumerace modelů zůstává orákulem
i vysvětlením (protipříklad je ukazatelný model).

**Jak (meta).**

```
„Petr, Pavel a Jana mají každý jedno zvíře: psa, kočku a papouška.
 Petr nemá psa. Jana má papouška. Kdo má psa?"

G_os = group{e_petr, e_pavel, e_jana};  G_zv = group{pes, kočka, papoušek}
C1: vztah(mít) je bijekce G_os ↔ G_zv          (každý právě jedno, různá)
C2: NOT vztah(mít · kdo:e_petr · co:pes)
C3: vztah(mít · kdo:e_jana · co:papoušek)
prostor modelů: C3 fixuje Janu; C2 vyřadí Petra u psa ⇒ Petr:kočka,
Pavel:pes — jediný model.
→ „Psa má Pavel. Jana má papouška (řekls to), Petr psa nemá, takže na
   něj zbyla kočka — a pes tak zbývá na Pavla."
   (vysvětlení = eliminační postup, ne jen výsledek)
```

### 6.10 Otázky v prostoru a čase

**Co chceme.** „Kde…?", „Kdy…?", „Co se stalo potom?", „Co dělal X během
Y?" — dotazy nad epizodickými fakty (§ 3.6) jako `restrikce` termy: filtr
groups instancí podle rolí, čtený přes obsažení míst a pořadí intervalů.
Odpověď na „kde/kdy" je hodnota role (nebo nejužší známé místo/interval);
výčtové tvary nesou otevřeně‑světovou doložku.

**Proč.** Párování dějů na místo a čas je k ničemu, když se na ně nedá
ptát; a naopak — právě tyhle otázky drží dialog o světě pohromadě.
Důležitá je asymetrie generického a epizodického: „Obsahuje citron
vitamíny?" se ptá na generické pravidlo (čas nehraje roli), „Jel Petr do
Prahy?" na epizodu (bez časového okna se odpovídá „aspoň jednou vím o…").

**Jak (meta).**

```
„Kde byl Petr včera?"     group[r | kdo:(e_petr), kdy⊆(včera)] → role kam/kde
                          → „V Praze (jel tam). Jestli i jinde, nevím."
„Kdy jel Petr do Prahy?"  → hodnota role kdy R7 → „Včera."
„Co se stalo pak?"        → děje s kdy PO kdy(posledního aktivního děje),
                          seřazené osou; nic známého → „Nevím o ničem dalším."
„Byl Petr v Evropě?"      → kam⊆(e_evropa) přes Praha⊆Česko⊆Evropa → ANO
```

### 6.11 Navazující otázky a elipsa v dialogu

**Co chceme.** „A minerály?" po „Obsahuje citron vitamíny?" doplní
chybějící část z **aktivního vztahu** (poslední dotazovaná struktura);
„A on?" rozřeší zájmeno aktivací. Když aktivace nedává jednoznačné
doplnění → doptání, ne hádání.

```
Q1: vztah(obsahovat · kdo:e_c · co:group(vitamín))     → ANO
„A minerály?"  → kopie Q1 s co:group(minerál)           → NEVÍM
„A pomeranč?"  → kopie s kdo:e_p                        → ANO (přes ovoce)
```

### 6.12 Průvodní dialogy: učení a dedukce z neúplných poskládaných dat

Pět dialogů od začátku do konce — každý skládá odpověď z tvrzení, která
jednotlivě odpověď nenesou, a každý dokládá jiný princip. Jsou to zároveň
kandidáti akceptační sady (§ 10). Zápis: `!` tvrzení člověka, `?` otázka,
`→` odpověď systému, odsazené bloky jsou meta‑stopa.

**Dialog A — řetěz s chybějícím můstkem (a veličinou).**

```
! Auto je dopravní prostředek.
      group(auto) ⊆ group_DP,  group_DP = group[x | x∈prostředek AND dopravní(x)]
! Dopravní prostředek slouží k přesunu nákladů nebo osob.
      vztah(sloužit · kdo:group_DP
            · k:vztah(přesun · čeho:(group(náklad) OR group(osoba))))
      — „nebo" je OR-group; z disjunkce neplyne žádný konkrétní člen!
! Dopravní prostředek jezdí po dálnici.
      vztah(jezdit · kdo:group_DP · kudy:group(dálnice))
! Dálnice má omezenou rychlost na 130 km/h.
      vztah(omezení · čeho:group(dálnice) · veličina:rychlost · nejvýše:130 km/h)
      — zatím fakt O DÁLNICI; o jízdách neříká nic

? Jak rychle může jezdit auto po dálnici?
→ (doptání reference: „auta obecně" — třída)
      dedukce, co jde: auto ⊆ DP (řekls) ; DP jezdí po dálnici (řekls)
        ⇒ auta jezdí po dálnici        [dědičnost přes ⊆]
      MEZERA: omezení mluví o dálnici, ne o jízdách — můstek v datech není
→ „Nevím přímo. Vím: auto je dopravní prostředek, ty jezdí po dálnici
   a dálnice má omezenou rychlost 130 km/h. Mám z toho usoudit obecné
   pravidlo: co jede po místě s omezenou rychlostí, nesmí jet rychleji
   než to omezení?"
! Ano.
      constraint [potvrzeno, dialog]: ∀ r ∈ group(jezdit):
        omezení(kudy(r)) = V  ⇒  rychlost(r) ≤ V
      — komparátor ≤ je z uzavřeného menu (§ 3.6); dialog naučil jen
        mapování „omezení" → ≤, ne jeho sémantiku
→ „Nejvýše 130 km/h. Rychleji ne — auto je dopravní prostředek, ty jezdí
   po dálnici, dálnice má omezení 130 km/h a potvrdil jsi, že omezení
   místa omezuje jízdu. Pomaleji nic nezakazuje."
      — modální otázka NAD VELIČINOU: odpověď je mez (supremum povolených
        hodnot z constraintu), ne ANO/NE; srov. § 6.7 a § 3.6

? Slouží auto k přesunu osob?
→ „Nevím jistě — slouží k přesunu nákladů NEBO osob; kterému z toho
   konkrétně, z řečeného neplyne."
      — z disjunkce se nesmí tiše vybrat člen
```

Dokládá: dědičnost vztahů přes `⊆`; **chybějící můstek se nehádá — stane
se hypotézou k potvrzení** (doptání = učení, § 6.6); modální otázka nad
veličinou vrací mez; disjunkce v datech nedává konjunktivní odpovědi.

**Dialog B — co z poskládaných dat NEPLYNE.**

```
! Citron je ovoce.
! Ovoce obsahuje vitamíny.
! Vitamín C je vitamín.
? Obsahuje citron vitamín C?
      lákavý (chybný) řetěz: citron⊆ovoce, ovoce obsahuje vitamíny,
      C∈vitamín ⇒ „citron obsahuje C"? NEPLATÍ: vztah ke group(vitamín)
      není vztah ke KAŽDÉMU členu („nějaké vitamíny", ne „každý vitamín")
→ „Nevím. Vím, že citron obsahuje vitamíny (nějaké — je ovoce); zda
   právě vitamín C, z toho neplyne. Rozhodlo by: ‚citron obsahuje
   vitamín C', nebo ‚ovoce obsahuje každý vitamín'."
? Obsahuje citron nějaký vitamín?
→ „Ano — je ovoce a ovoce obsahuje vitamíny."
```

Dokládá: dedukce z neúplných dat znamená i **vědět, co neplyne** —
distributivita vztahu na členy cíle je tvrzení (Tot), ne default.

**Dialog C — sylogistický řetěz a svědek.**

```
! Každý spisovatel je člověk.          group(spisovatel) ⊆ group(člověk)
! Žádný stroj není člověk.             group(stroj) AND group(člověk) = ∅
! Hrabal je spisovatel.
! Hrabal napsal Postřižiny.
? Je Hrabal stroj?
→ „Ne — je spisovatel, každý spisovatel je člověk a žádný stroj člověk
   není."                               [⊆ zřetězené s disjunktností]
? Napsal Postřižiny spisovatel?
→ „Ano — Hrabal."                       [existence se dokládá svědkem]
? Napsal Postřižiny i nějaký stroj?
→ „Nevím. Znám jednoho autora — Hrabala, a ten stroj není; že ji nenapsal
   i nějaký stroj, vyloučit neumím."    [otevřený svět: absence ≠ neexistence]
```

**Dialog D — prostor a čas složené na fakta.**

```
! Petr jel v pondělí do Prahy.     R7(jet · kdo:e_p · kam:e_praha · kdy:pondělí)
! V úterý jel Petr do Brna.        R8(… · kam:e_brno · kdy:úterý)
! Praha je v Česku.  ! Brno je v Česku.
? Byl Petr v pondělí v Česku?
→ „Ano — jel do Prahy a Praha je v Česku."      [kam ⊆ přes obsažení míst]
? Kam jel Petr dřív — do Prahy, nebo do Brna?
→ „Do Prahy — pondělí je před úterým."          [alternativa nad osou času]
? Byl Petr ve středu v Česku?
→ „Nevím — o středě žádný děj neznám. (Že by tam zůstal, nepředpokládám —
   trvání stavů neumím.)"                        [hranice v1 řečená nahlas]
```

**Dialog E — rozpor a výjimka bez default logiky.**

```
! Ptáci létají.                    vztah(létat · kdo:group(pták))
! Tučňák je pták.
? Létá tučňák?
→ „Ano — je pták a ptáci létají."               [zatím: plyne z pravidla]
! Tučňák nelétá.
→ „To si odporuje s tím, co plyne z ‚Ptáci létají' + ‚Tučňák je pták'.
   Mám obecné pravidlo odvolat, nebo zúžit (létají ptáci kromě tučňáka)?"
      — konflikt se HLÁSÍ, nepřepisuje (I-3); obě opravy jsou legální termy
! Zúžit.
      pravidlo převázáno: vztah(létat · kdo:(group(pták) NOT group(tučňák)))
      [staré odvoláno s proveniencí; výjimka = algebra NOT, žádná default logika]
! Vrabec je pták.
? Létá vrabec?
→ „Ano — je pták a ptáci kromě tučňáka létají."
? Létá tučňák?
→ „Ne — řekls to; a z pravidla už pro něj nic neplyne."
```

Dokládá: konflikt jako stav s nabídkou oprav; **výjimky unese samotná
algebra groups** (`NOT`), bez nemonotónní logiky — a po opravě systém
odpovídá konzistentně včetně vysvětlení, PROČ se pravidlo na tučňáka
nevztahuje.

**Dialog F — instance z množiny, vršení popisu a neznámé jméno.**

```
! Filip má auto.
      „auto" NEURČITĚ → instanciace: nový anonymní uzel (a1),
      (a1) patří_do group(auto);  vztah(mít · kdo:(e_filip) · co:(a1))
! Filipovo auto je modré.
      „Filipovo auto" = určitý popis: restrikce(group(auto) ·
      co_má:(e_filip)) → jediný známý kandidát (a1)
      → vlastnost modrý se VRŠÍ na (a1) — táž identita, druhá věta
      (kdyby Filip měl auta dvě → doptání „které?")
! Filip má Ford.
      zmínka„Ford" nemá uzel ani skupinu — tiše se nezakládá NIC:
→ „Ford neznám. Patří do nějaké skupiny, kterou znám? Je to to modré
   auto, co Filip má, nebo něco dalšího?"
      kandidáti na rozřešení: (a1) [aktivace + sdílený vlastník] × nový uzel
! Je to to auto.
      jmenuje_se(a1) += „Ford"        [assign potvrzen, dialog]
? Co má Filip?
→ „Modré auto Ford."
      výčet vztahů mít(kdo:(e_filip)) → (a1); odpověď = SYNTÉZA
      nashromážděného popisu uzlu (členství + vlastnost + jméno),
      ne echo jedné věty (§ 6.5, § 8)
? Co je Ford?
      zmínka„Ford" se rozřeší přes jmenuje_se na (a1)
      → definiční otázka (§ 6.5): ČÍM je = členství, pak vlastnosti a vztahy
→ „Ford je auto — modré, a má ho Filip."
      — jméno naučené jedním doptáním hned funguje OBĚMA směry:
        v syntéze odpovědi („modré auto Ford") i v rozřešení otázky
        („Co je Ford?"); věta „Ford je auto" nebyla nikdy vyřčena,
        plyne z jmenuje_se(a1) + (a1) ∈ group(auto)

Alternativní větev:  ! „Ford je jiné auto."
      → nový uzel (a2) ∈ group(auto), jmenuje_se „Ford"
? Co má Filip?   → „Dvě auta: jedno modré a jedno jménem Ford."
```

Dokládá: neurčitá zmínka **instanciuje** anonymní prvek množiny (proto
identita ≠ jméno — uzel žije dřív, než má jméno); určitý popis se
rozřešuje na zavedený uzel a znalost se na něm **vrší napříč větami**;
neznámé jméno vede na doptání po členství/totožnosti, nikdy na tiché
založení; a odpověď na „Co má X?" je složený popis uzlu — přesně to
„vysvětlování datových vazeb", které je cílem konceptu.

---

## 7 · Učení z dialogu (U)

**Co chceme.** Čtyři druhy učení, všechny jako **data s proveniencí,
statusem a odvolatelností**: (1) znalost — tvrzení → vztahy/členství/
pravidla/constrainty; (2) vzory čtení — z anotací při doptání (§ 5.2);
(3) identita — assigny a scelení (§ 3.2, 3.5); (4) pravidla vyžádaná
systémem — potvrzené hypotézy z § 6.6. Jazyk a statistika **navrhují**,
o pravdivosti rozhoduje jádro a člověk.

**Proč.** Kruh „doptání = sběr anotací za provozu" se v conBond3 osvědčil
(vzory modality, volby instance/třída) a je levnější i bezpečnější než
ofline trénink: každá naučená položka má autora, důvod a cestu zpět.

**Meta‑ukázka anotační smyčky:**

```
systém: „Čtu to jako: citron obsahuje vitamíny — správně?"
člověk: „ano"
→ vzor čtení (signatura: obsahovat + Sing/Plur + slovosled) [potvrzeno, dialog]
příště táž struktura → bez doptání, s odkazem na vzor v provenienci
```

## 8 · Odpověď a vysvětlení (V6)

**Co chceme.** Odpověď má vždy tři části: **verdikt** (nebo výčet/člen/
doptání), **důvod** (cesta/podgraf/protipříklad/chybějící premisy) a
**poctivostní doložku**, kde je namístě („znám tři; jestli všechny,
nevím"). Renderování z podgrafu do češtiny je samostatná úloha se
šablonami odděleně od logiky (jazyk v profilech, ne v kódu) — a je to
JEDINÝ výstupní kanál: co nejde vyrenderovat z reálné struktury, nesmí
se říct. Složené termy se renderují vždy strukturovaně (odsazený výpis
se zjevným uzávorkováním + podgraf v okně grafu — § 12/7); věta je jen
pro jednoduché verdikty.

**Proč.** Cíl konceptu je vysvětlování vazeb; vysvětlení vyrobené jinak
než z použité struktury by bylo lhaní o vlastním myšlení. Zkušenost:
i primitivní renderování („petr jet ins auto") bylo užitečné, protože
bylo pravdivé — hezčí čeština je vylepšení, pravdivost je podmínka.

## 9 · Invarianty

Přenesené z conBond3 (prokázané praxí):

- I‑1 Tiché zjednodušení měnící význam je nepřípustné: struktura, nebo
  odmítnutí s důvodem — nikdy hádání.
- I‑2 Jazyk a statistika navrhují; o pravdivosti rozhoduje jádro (INV‑11).
- I‑3 Konflikt se hlásí, nepřepisuje; NEVÍM ≠ NE ≠ chyba.
- I‑4 Determinismus: žádné hodiny, žádná neseedovaná náhoda, kanonická
  pořadí; vyhasínání aktivace po tazích, ne po čase.
- I‑5 Provenience všude: tvrzení → zmínka → tokeny; naučené → kdo/kdy/proč.
- I‑6 Modalita jen jako dotaz nad modely, nikdy operátor objektového jazyka.
- I‑7 Doptání je plnohodnotný tah dialogu a zdroj učení.

Nové pro conBond4:

- I‑8 Pravdivost nikdy neteče po měkké hraně; aktivace nezvyšuje jistotu.
- I‑9 Identita ≠ jméno: entita je anonymní uzel; jména jsou popis.
- I‑10 Vazby identity (označuje, totožný) jsou hypotézy se statusem a
  odvolatelností; výchozí je oddělenost, sceluje se na evidenci.
- I‑11 Extenze group je dolní odhad (otevřený svět); výčty a NOT to musí
  říkat.
- I‑12 Otázka nemění bázi; presupozice žijí v kopii.
- I‑13 Výrazová mez (rozhodnutelnost) je narýsovaná předem a strojově
  hlídaná; rozšíření jen vědomým rozhodnutím.
- I‑14 Vysvětlení se renderuje výhradně ze skutečně použité struktury.
- I‑15 Pevné jádro je malé a uzavřené (algebra, role, komparátory,
  modální dotazy); všechno významové nad ním — vztahy, pravidla, můstky,
  mapování jazyka, výjimky — vzniká dialogem jako data s proveniencí.
- I‑16 Učením se mění program, nikdy jazyk: gramatika meta‑kódu a
  interpret jsou verzované pevné jádro; učení jen přidává a odvolává
  řádky. Meta‑kód je jediný zdroj pravdy; běhový graf je jeho
  deterministické vyhodnocení.

## 10 · Měření úspěchu

- **Akceptační dialogy:** zmražené reálné dialogy z conBond3 seancí
  (citron/vitamíny, Hrabal, doprava, ovoce) — právě ty, kde conBond3
  selhal nebo odmítl — plus sada logických úloh (Bartlová, sylogismy,
  eliminace § 6.9). Úloha projde, když odpověď obsahuje správný verdikt
  I správný důvod.
- **Generalizační disciplína (§60 conBond3):** každý vzor a schopnost
  musí projít renaming testem (přejmenuj entity/relace — chování stejné;
  u identitní vrstvy je to přímo test korektnosti) a unseen testem
  (strukturálně nové věty nepoužité při implementaci).
- **Orákulum:** enumerace konečných modelů pro algebru groups a constraint
  úlohy; nezávislá naivní implementace vedle optimalizované (metodika tří
  orákul).
- **Poctivost propadů:** měřit podíl tichých chyb (nesmí existovat) vs.
  odmítnutí s důvodem vs. doptání; a podíl doptání, která vedla k naučení.
- **Učitelnost (hlavní metrika):** ne „na kolik otázek umí odpovědět",
  ale „kolik tahů dialogu potřebuje, aby se naučil odpovídat správně" —
  na NEVÍM navazuje otázka „a co ti chybí?", jejíž zodpovězení člověkem
  musí schopnost doplnit (dialogy § 6.12 jsou přesně tenhle test).
- **Přehratelnost:** žurnál dialogu + pevný interpret ⇒ týž meta‑kód ⇒
  tytéž odpovědi (§ 3.7). Akceptační dialogy se ukládají i s očekávaným
  výsledným programem — diff kódu je diff naučeného.

## 11 · Vědomé hranice v1 (rekapitulace)

Bez plné predikátové logiky (mez = algebra groups + vnořené vztahy
s konečnými rolemi), čas a prostor jen jako role dějů s uspořádáním,
intervaly a obsažením (bez perzistence stavů a kauzality z následnosti),
bez aritmetiky nad rámec mohutnosti známých extenzí, bez vícevětných
dokumentů (dialog je jednotka), koreference jen aktivací, generování
češtiny šablonami (ne volný jazyk). Každá hranice je zapsaná a strojově
hlídaná — je to čára, ne mezera.

## 12 · Rozhodnutí k dříve otevřeným otázkám (J., 11. 8. 2026)

1. **Role vztahu — hybrid.** Strukturální jádro uzavřené (kdo/co
   z podmětu a předmětu — bez něj nejde psát algebra restrikcí),
   okolnosti povrchově podle předložky/pádu (nehádá se sémantika,
   INV‑11), ekvivalence rolí („kudy" × „po čem") se učí dialogem jako
   odvolatelná data.
2. **Neslučitelnosti — škály.** Antonyma jsou intervaly na ose veličiny
   (rychle/pomalu na ose rychlosti); neslučitelnost i vyplývání počítá
   osa. Doptání zůstává mechanismem pro vlastnosti, které na žádné ose
   neleží.
3. **Vnoření vztah(vztah) — hloubka 1, modifikovatelná.** Mez je
   parametr hlídaný na gramatice termů (§ 3.0); zvyšuje se vědomým
   rozhodnutím, nikdy implicitně rozšířením kódu.
4. **Ranker čtení — až na důkaz.** Kaskáda od prvního dne loguje, které
   patro rozhodlo; ranker se přidá, až podíl doptání nepokrytých vzory
   přestane klesat (vzory saturovaly).
5. **Iniciativa — plná proaktivita.** Systém smí sám nabízet hypotézy
   (můstková pravidla při NEVÍM, scelení identity, členství neznámých
   jmen), kdykoli má evidenci. Pojistky: nabídka je vždy označená
   HYPOTÉZA s evidencí, nikdy tiché tvrzení; každá jde odmítnout a
   odmítnutí se pamatuje (nenabízet znovu totéž); člověk může iniciativu
   ztlumit pokynem v dialogu.
6. **Čas — hybrid + specializované domény veličin.** Interní osa je
   abstraktní uspořádání; kalendář je profil („pondělí < úterý"), plné
   datum se ukotví, jen když ho věta nese; „teď" = tah dialogu.
   Slovesný čas navrhne `kdy` jen u epizodických dějů, jako hypotéza
   čtení. Nově: každou veličinovou doménu obsluhuje **specialista**
   („Chronos" pro čas, „Topos" pro prostor, další pro rychlost/míry) za
   JEDNOTNOU smlouvou: rozpoznat hodnotu v textu, normalizovat,
   uspořádat, porovnat, pojmenované intervaly, render. Specialista
   dodává jen primitivní predikáty své osy — termová algebra zůstává
   jedna (§ 3.0, I‑15); žádný specialista nesmí přidat zvláštní případ
   do vyhodnocení. (Vnitřní stavba specialistů je architektura — mimo
   tento dokument.)
7. **Renderování — složené termy vždy strukturovaně.** Jednoduchý
   verdikt větou; složený term (algebra, restrikce) vždy odsazeným
   výpisem se zjevným uzávorkováním a v okně grafu jako rozklikatelný
   podgraf — uzávorkování se ukazuje, neschovává.
