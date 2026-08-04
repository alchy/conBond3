# Query basket — dotaz jako metadatový koš, který umí operovat

Zadání J. (2026-08-04), doslova:

> „my zde nehledáme přímou odpověď. systém by se měl na základě učení
> (položená otázka) dostat k optimálnímu koši odpovědi (query basket
> metadata). query basket metadata pak slouží fitu faktu ve znalostním
> korpusu."

> „k odpovědi systém nemusí dojít přímo, ale může mu být ukázána skrze
> logické operace, cílem je, aby query basket nad jednotlivými baskety
> uměl logicky operovat"

## 1 · Co se tím mění

Dosud (4a–4c) byl řetěz **otázka → skóre → token**: pytel otázky se
násobil s pytli kandidátů a vyhrál nejlepší token. Odpovídač.

Nově je řetěz **otázka → query basket → fit nad korpusem → odpověď**:

1. Z otázky se (učením) odvodí **query basket**: BEZESLOVNÝ metadatový
   vzor koše, který má odpověď splňovat — jaké kotvy, jaké gramatické
   vertikály, co tam naopak být nesmí (záporné váhy).
2. Query basket se přiloží na koše znalostního korpusu (fit).
3. Odpověď je výsledek — a nemusí padnout z jednoho koše: query basket
   umí nad koši **logicky operovat** (průnik, sjednocení, negace), tedy
   odpověď může být ukázána složením několika košů.

Proč je to správný směr, a ne komplikace: dnešní mosty z učení jsou
párové (WORD=X ↔ WORD=Y) a mezi otázkami se **nepřenášejí** — naměřeno
na korpusech (trénink 1 → 6/23, etalon beze změny 0,43). Query basket
je naopak **typový**: co se naučí na jedné otázce („kde" hledá koš
s ANCHOR=space a dir:at v nominální skupině), platí pro každou další
otázku téhož typu. Tudy vede generalizace, kterou pytlové párování
nemá odkud vzít.

## 2 · Metadata, ne slova

Query basket žije v METADATA reprezentaci (§ registr: bezeslovná
matice je primární, WORD= jen v COMPLETE). Slova zůstávají adresou
podnětu — čeho se otázka týká; vzor odpovědi je gramatický a kotevní.
Tím se drží zákaz konkrétna: do vzoru smí jen to, co roste s gramatikou,
ne se světem.

## 3 · Logické operace vahami, ne větvením

Operace se dělají týmž mechanismem jako všechno ostatní — vahou se
znaménkem (§ registr):

| operace | provedení | čtení |
|---|---|---|
| A ∧ B | součin aktivací (obě musí svítit) | koš splňuje obojí |
| A ∨ B | součet (stačí jedna) | koš splňuje aspoň jedno |
| ¬A | záporná váha | koš, kde A svítí, je horší |

Žádné `if`, žádná brána: výsledkem operace je aktivace, ne rozhodnutí.
Řez zůstává jediný a až na konci (θ pro NEVÍM, ε pro DOTAZ).

## 4 · Jak se query basket učí

Startuje z axiomů (kotvy: „kde" → ANCHOR=space, „kolik" → quantity —
tabulka INTERROGATIVE_ANCHORS) a učí se kontrastivně, ale na jiné
úrovni než dnes: z dvojice (otázka, správná odpověď) se posiluje to,
co má koš správné odpovědi a koš vítěze ne — jenže **v metadatovém
profilu typu otázky**, ne v hraně mezi dvěma slovy. Adam a relativní
marže platí beze změny; mění se, co je učený parametr.

Typ otázky = její tázací podpis (QLEM + QANCHOR sada). Profilů je tedy
řádově tolik, kolik je druhů otázek — ne kolik je dvojic slov.

## 5 · Logické vazby z textu (co vstupuje vedle metadat)

> „do transformeru vstupují metadata otázky a data o logických vazbách"
> — J., s odkazem na Bartlová, H.: *Metody řešení slovních úloh pomocí
> logiky* (PedF UK 2014, vedoucí J. Novotná).

Práce probírá metody řešení slovních úloh výrokové logiky: tabulka
pravdivostních hodnot, Quineův algoritmus (stromová reprezentace),
Booleova algebra, **šipkový diagram** (Šedivý; pro úlohy s implikacemi)
a **Vennovy diagramy** (pro množinové vztahy). Dvě z nich jsou pro
conBond přímo použitelné, protože už mají tvar, který systém drží:

- **šipkový diagram = graf implikací.** Uzly jsou tvrzení, šipky
  implikace. To je přesně registr: uzel = vertikála, hrana = vazba
  doložená v textu. Implikace je *orientovaná* hrana — a orientaci
  registr umí (L není symetrická).
- **Vennův diagram = průnik košů.** Množina = koš s danou vertikálou;
  průnik = součin aktivací, sjednocení součet, doplněk záporná váha.

Odtud plyne, co má do query basketu vstupovat vedle metadat otázky:
**typované logické vazby vytěžené z textu** — implikace („jestliže …
pak", „každý … je"), konjunkce („a", „zároveň"), disjunkce („nebo"),
negace („ne", „žádný"), ekvivalence („právě tehdy"). Jsou to hrany se
zdrojem (jako axiom/hebb/etalon), jen nesou typ spojky; váha dál nese
sílu a znaménko.

Odpověď na slovní úlohu se pak nečte, **odvozuje**: query basket pustí
aktivaci po implikačních hranách (šipkový diagram) a průniky/doplňky
udělá součinem a zápornou vahou (Vennův diagram). Tím je naplněné
„k odpovědi systém nemusí dojít přímo, může mu být ukázána skrze
logické operace" — a zůstává to čitelné, protože každý krok odvození
je hrana s pojmenovanými konci.

Pozn. k pořadí: typované spojky mají smysl teprve nad query basketem,
který umí operovat. Nejdřív profil a jeho fit, pak spojky, pak
odvozování — jinak by vznikly hrany, které nemá kdo použít.

## 6 · Algebra košů (zobecnění, J. 2026-08-04)

> „máme koše otázek i odpovědí, máme logické operátory mezi koši
> a závislosti mezi koši. lze naučit závislosti pomocí nového koše.
> lze použít operátory mezi jednotlivými koši (takový NOT je též pěkný,
> AND — kombinace dvou otázkových košů)"

Koš přestává být jen výřezem věty a stává se **univerzální jednotkou**:

| co | je koš | k čemu
|---|---|---|
| otázka | ano | co se ptáme (podnět + neznámá) |
| odpověď | ano | co odpovídá (fakt v korpusu) |
| **závislost** | **ano** | vazba mezi dvěma koši, a **učí se** |

Poslední řádek je to podstatné: závislost se nereprezentuje jen jako
hrana mezi vertikálami, ale může dostat **vlastní koš** — uzel, do
kterého teče aktivace a který má své vertikály a váhy. Hrana se tím
reifikuje do uzlu a učí se týmž mechanismem jako všechno ostatní
(Adam, relativní marže, ochrana axiomů). Graf tak roste o uzly, které
nesou vztah, ne jen o uzly, které nesou slovo.

Operátory pak nejsou nad tvrzeními, ale **mezi koši**:

- **NOT(A)** — obrácené znaménko aktivací: koš „co tam nemá být".
  Není to filtr; je to koš jako každý jiný, jen se zápornými vahami,
  takže se s ním dá dál počítat i učit.
- **AND(A, B)** — součin po vertikálách: svítí, co je v obou. Kombinace
  dvou **otázkových** košů dá složenou otázku („kdo" ∧ „kdy"), aniž by
  ji někdo musel předem definovat.
- **OR(A, B)** — součet: stačí jeden.

Vlastnost, na které záleží: výsledek operace je zase koš, takže se dá
řetězit, uložit do registru jako uzel a učit. Tím se z odpovídače
stává počítadlo nad grafem — a odvození zůstává čitelné, protože každý
mezikrok je pojmenovatelný koš.

## 7 · Co je hotové a co ne

Hotové: bezeslovná reprezentace, kotvy a jejich hierarchie, koše
s dvojitým r (slovo × věta), kontrastivní učení s Adamem, relativní
marží a odvoláním epochy, kalibrace θ, pokrytí otázky (podnět).

Nehotové (v tomto pořadí):
1. `QueryBasket`: metadatový profil per tázací podpis + jeho fit na
   koše korpusu (nahradí hrubý W_FIT, který kotvami samotnými
   nefunguje — naměřeno r=2: 0,94 → 0,85).
2. Učení profilu místo párových hran (kontrastivně, tytéž mechaniky).
3. Logické operace nad koši (∧ součin, ∨ součet, ¬ záporná váha)
   a skládání odpovědi z víc košů.

Měřítko úspěchu je generalizace na oddělené sadě, ne číslo na
tréninku: párové mosty ji dnes nedávají, typový profil ji dát musí.
