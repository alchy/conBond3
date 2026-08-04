# Koncepce cb_bond — proč je to postavené takhle a ne jinak

Rozhodnutí, která se v kódu nedají přečíst, a naměřená čísla, ze
kterých plynou. Zadání celé stavby je v `zadani.md`; tady stojí, co se
při stavbě rozhodlo a proč.

---

## 1 · Graf existuje proto, že pytel ztrácí strukturu

Na otázku „Kde byl pokřtěn Ježíš?" jsou v pytli aktivací Jordán
(2,088) a Galilej (2,068) k nerozeznání — dvě místa, obě v téže větě.
Strukturně je rozdíl triviální: **Jordán visí na *pokřtěný*, Galilej
na *přijít***. Graf ten rozdíl drží a `illuminate` z něj dělá číslo
(1,67 proti 1,20).

Odtud plyne všechno ostatní: uzly jsou obsahová slova, hrany jsou
doložené závislosti, a záře se šíří úměrně tomu, jak výlučná ta vazba
pro souseda je.

## 2 · Hrana vzniká jen mezi přímými sousedy

Nabízí se odvozovat hranu i přes gramatické slovo v cestě („nového"
visí na zájmenu *něco*, to na slovese *vidět* — spojit je?). **Zkoušeno
a zamítnuto měřením:** graf 2 912 vět měl s odvozováním 15 975 hran
místo zmražených 16 074 a *rok* vyšel 163/192 místo 162/191. Přímá
závislost je doklad; odvozená vazba je domněnka, která posunula
statistiku, o kterou se opírá promoce.

Kopulu to nebolí: v „Gravitace **je** síla" visí kopula na *síle*, ne
mezi uzly — definiční vazba proto vzniká přímo a krok 7 na ni může
stavět.

## 3 · Zájmenná příslovce jsou uzly, i když v cb_field jsou zavřená

*tam*, *tehdy*, *tak* patří v cb_field k zavřeným třídám (dostávají
`LEM=`), protože tam nesou gramatický rys. V grafu nesou **fakt**:
„bydlí **tam**" je vztah místa. Bez nich má graf 15 953 hran místo
16 074 — rozdíl je naměřený, ne dohadovaný.

Je to jediné místo, kde se cb_bond od klasifikace cb_fieldu vědomě
liší; proto to stojí tady a ne jen v komentáři.

## 4 · Smyčka se počítá, ale nekreslí

Táž vertikála dvakrát v jedné větě („pes → psa") dá závislost na sebe
sama. Je to doložený jev, takže do součtu hran patří — bez ní je součet
15 953 místo 16 074. Do sousedství ale nejde (soused sám sobě není)
a nekreslí se: viewBase smyčky odmítá.

## 5 · Skóre promoce: různých² / hran

Slot je **pojmenovaný neuron vstupní vrstvy**, ne cache častých slov.
Skóre `distinct²/edges` žádá dvě věci najednou: mnoho různých sousedů
(uzel je rozcestí) A neopakovat se do týchž míst. *Rok* má 162 různých
sousedů na 191 hran → 137,4 a je první; *Hrabal* se do 328 nevejde.

Druhá mocnina v čitateli je to, co dělá rozdíl mezi „rozcestím"
a „častým slovem": lineární poměr by zvýhodnil uzly s málo hranami,
kde je poměr triviálně 1,0.

## 6 · Užitek otázkám je vážený člen, ne filtr

Čistě korpusová statistika plave se žánrem: po záplavě Nového zákona
vystoupala hranice limitu z 12,1 na 41,9 a slova, která otázky opravdu
potřebují (*rychlost* 33,8, *smět* 41,7), vypadla těsně pod ni.

    skóre = distinct²/edges × (1 + W_USAGE · doklady v supervizi)

Násobek, ne přerovnání: základ zůstává korpusový a uzel bez dokladů si
nepohorší. Filtr by porušil princip 2 (žádné filtry v datové cestě).

## 7 · Emitor delt se předává parametrem

Princip 6 zadání říká, že graf a jeho vizualizace jsou totéž. Kdyby si
graf kreslítko vytvářel sám, byla by z toho závislost jádra na I/O
(zakázáno README-MODULES § 1) a testy by potřebovaly běžící službu.
Emitor je proto obyčejná funkce v konstruktoru; bez ní graf mlčí.

## 8 · Setkání se měří až po šíření OBOU stran

Otázka nese `QANCHOR=space:loc`, věta `ANCHOR=space:loc`; společnou
souřadnici mají až o krok dál, v `ANCHOR=space`. Šířit jen otázku
znamená měřit setkání v místě, kam druhá strana nedošla — členy pak
měří podobnost gramatiky, ne významu. Proto se saturuje i okno a střed
kandidáta, týmž `spread_depth`.

Související past, na kterou se přišlo testem: pytel se nesmí saturovat
sám v sobě. Když to `_pytel` dělal a `match` šířil znovu, běžela otázka
v hloubce 2, když měla v 1 — a `spread_depth` přestal být pákou, kterou
si člověk nastavuje.

## 9 · Interpunkce není kandidát

Tečka odpovědí být nemůže. Není to filtr v datové cestě (princip 2):
skórování všech ostatních tokenů zůstává bez výjimky, jen se neměří
skóre u znaku, který nemůže být odpovědí. Bez toho se „." objevovala
na druhém místě a jen ředila pořadí.

## 10 · Odpověď je pole; token, okno, věta a vrchol jsou jen čtení

Čtyři metody `AnswerField` nejsou čtyři algoritmy — je to týž field
skóre, přečtený v různé hrubosti. Který je správný, závisí na otázce,
ne na kódu.

Gaussovské čtení řeší naměřený degenerát: krátká věta se silným
jediným tokenem („Máš ženu?") vyhrávala, protože průměrová normalizace
dělí délkou. Zvon to řeší tvarem, ne prahem — shluk 1,0+1,0+1,0 dá
vrchol 0,69, kdežto osamělá špička 1,5 jen 0,40.

**Naměřená protiváha** na 12 258 větách (40 otázek etalonu): při
tokenovém čtení je vítězem krátká věta (≤4 tokeny) v 15 případech ze
40, při gaussovském v **nule**. Zásah lemmatu ve vítězné větě zůstává
3/30 u obou — Gauss opravuje délkový degenerát, ne skórování; to je
mez kroku 3 (viz prirucka.md).

Poloměr jádra je `int(3σ)`: za třemi sigmami nese zvon pod 1,2 % hmoty
a jen by prodlužoval konvoluci. Při σ=1,5 to dá 9 vzorků a hodnoty
k0 = 0,267 · k1 = 0,213 — přesně ty ze zadání.
