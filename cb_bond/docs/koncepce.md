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


## 11 · Skórování podle kroku 3b: každý člen nad jiným vektorem

Doplněk zadání (commit cab983e), bez kterého se baseline nedal
zopakovat. Klíč je, že členy skóre **nežijí nad týmž vektorem** —
každý měří něco jiného a nad jinou reprezentací.

**Semantická maska.** Do pytle jde jen to, co roste s významem:
`WORD=`, `LEM=`, `QLEM=`, `ANCHOR=`, `QANCHOR=`, `Polarity=`,
`CUSTOM=`. Strukturní osy (`UPOS=`, `DEPREL=`, `Case=`, `SUBPOS=`,
morfologické rysy) vypadnou ÚPLNĚ — sdílí je skoro každá věta, takže
by kosinus měřil podobnost gramatiky. Maskuje se PŘED sečtením, aby
strukturní osy nemohly nafouknout normu.

**Pytel otázky je jeden na celou otázku.** Ne po řádcích: otázka nemá
střed, na kterém by záleželo — roli nese pád, ne pozice (princip 5).
`q_words` se bere ze surového pytle, saturovaný slouží setkání.

**Okno kandidáta je harmonické.** Řádek ve vzdálenosti `o` přispívá
vahou `1/(1+|o|)` — sousedství doznívá, místo aby končilo hranou.
Okno i střed se saturují a normují na JEDNOTKOVÝ vektor zvlášť.

**Zdůraznění středu je vlastní člen, ne násobek.** Odtud identita,
kterou musí každá přestavba zachovat:

    meet = q̃·(okno + (W_CENTER−1)·střed) / ‖q̃‖
         = cos(q̃, okno) + (W_CENTER−1)·cos(q̃, střed)

Kdo počítá `cos(q̃, okno + 2·střed)` nad surovým pytlem, trestá středy
s bohatou morfologií — norma součtu roste s tím, kolik os střed nese.

**Pokrytí není kosinus, je to mohutnost.** Minimum přes dané osy nad
`tanh(spread(celá věta))`. Je to tedy člen VĚTNÝ: pro všechny
kandidáty téže věty stejný, takže **řadí věty**, kdežto `meet`
a `given` řadí tokeny uvnitř věty. Dvě různé práce, dva různé členy.

**Nosný je postih, ne setkání.** Naměřeno ablací: bez `given` je
přesnost 0/30 a samotné setkání také 0/30. Bez postihu za střed,
jehož slovo otázka sama uvádí, vyhrává vždycky ozvěna otázky.

## 12 · Definice se pozná pádem rootu, ne kopulí

„Gravitace **je** síla" a „Muž **byl** ve vězení" mají tutéž kopuli.
Rozdíl nese PÁD rootu: nominativ říká, CO věc je, lokativ říká, KDE
byla. Kdo vzor postaví na přítomnosti kopule, nasype si do osy vazby
typu muž→vězení a šíření je pak roznese po celém korpusu.

**Definiens smí být i vlastní jméno.** „Jméno té hvězdy je Pelyněk."
je definice jako každá jiná. Naměřeno: bez PROPN v rootu dá korpus
91 vazeb místo zmražených 94, a ty tři chybějící jsou právě
jméno→Pelyněk, pán→Kristus, život→Kristus.

**Vazba na sebe sama se nezakládá.** „Trpasličí galaxie je malá
galaxie." má definiční tvar, ale obě strany nesou totéž lemma —
vazba by byla smyčka v ose a šíření by aktivaci zesilovalo samo ze
sebe. Je to táž úvaha jako u smyček v grafu (§ 4), jen o patro výš.

Mimochodem, i ta druhá varianta by dala 94: kdyby se smyčky
připustily a PROPN ne. Rozhodl obsah, ne shoda čísla — smyčky
(galaxie→galaxie, motor→motor) nenesou informaci, kdežto
jméno→Pelyněk ano.

## 13 · Derivace nikdy plošně

*rychlost* a *rychlostní* pytel nespojí (jsou to různá lemmata), kmen
ano. Ale kmen spojí i *naléhavý* s *náledí*, když se nehlídá délka —
proto ≥5 znaků po složení diakritiky A ZÁROVEŇ ≥75 % kratšího lemmatu.
Diakritika se skládá pryč, protože *kámen* a *kamení* jsou totéž slovo.

Plošné nasazení dalo 11 268 vazeb a stálo baseline 3,3 bodu: vazby
mezi vším, co si je náhodou podobné, jsou šum. Proto `around=` —
těží se jen kolem slov otázky a její expanze. Naměřeno pro
{dálnice, kámen, rychlost}: 10 vazeb místo tisíců.

## 14 · Systém odpovídá vždycky a při mezeře se zeptá

`reply()` vrací nejlepšího kandidáta i tehdy, když hlásí
`needs_context`. Mlčet naslepo je horší než odpovědět a přiznat, oč se
rozhodnutí opírá — člověk pak vidí, kde se láme.

**Mezera je přesná nula, ne práh.** Osa, kterou korpus zná jen slabě,
má tanh(0,7) = 0,604; osa, kterou nezná vůbec, má 0,000. Mezi tím je
propast, ne škála, takže se mezera pozná bez kalibrace a nedá se
„skoro" splnit. (Práh detekce mezery je v zadání mezi zavrženými
cestami — tohle je důvod.)

**Ptá se na JEDNU věc.** Naměřený průběh nad biblicko-fyzikálním
korpusem: být 1,000 · omezený 0,604 · rychlost 0,604 · na 1,000 ·
dálnice 0,000. Jediná mezera je *dálnice*; *rychlost* systém zná
z fyziky, takže se na ni neptá.

**Dialogová věta jde standardní cestou.** Táž stavba pole, týž
registr, týž graf — liší se jen zdroj hrany (`dialog`), aby šlo
poznat, odkud fakt přišel. Naměřeno: věta uživatele přidá do grafu
9 hran (dálnice→silnice nsubj, rychlost→stanovený, 130→stanovený…)
a pokrytí *dálnice* stoupne z 0,000 na 0,604, čímž se východisko
překlopí na `answer`.

## 15 · Opatřování definic je offline-first

Pořadí je dané principem 7: korpus → úložiště na disku → slovník ze
sítě (a fixace) → dialog s člověkem. Vyhledávač i úložiště se předávají
parametrem, takže jádro samo na síť nesahá a testy ji nepotřebují.
Co se jednou fixovalo, platí z disku — síť se volá jen při PRVNÍM
setkání se slovem.

## 16 · Promoce: pořadí kroků je podstata, ne detail

    1. before = measure          4. corpus.regenerate()   ← TEPRVE TEĎ
    2. snap = registry.snapshot()   koše nesou CUSTOM=
    3. selekt → set_custom_axes   5. retrain  6. after  7. horší? → restore

Krok 4 **před** krokem 5 je celá transparentnost promoce: koše si
aktivaci `CUSTOM=` přidají samy nahlédnutím do osy, takže učení už
vidí hotový stav. Kdyby se trénovalo dřív, učilo by se nad osou, která
ještě neexistuje — a stejnou aktivaci dostane transparentně i otázka
a dialogová věta, protože ji dělá stavba pole, ne zvláštní kód.

**Beze změny osy se nepřeučuje ani neměří podruhé.** Trénink i měření
jsou drahé a neměly by co nového vidět; cyklus proto vrátí
`retrained=False`. Odtud plyne, že s růstem korpusu řídne sám od sebe
(naměřená stabilizace výměn 38 % → 16 % na přírůstek).

**Stačí JEDNA horší metrika.** Promoce, která zvedne přesnost a srazí
dosah, není zlepšení — je to výměna, o které nikdo nerozhodl. Shoda
projde: vratná je promoce pořád.

**Návrat je bit po bitu.** Snapshot nese vazby, obsazení i verzi; klíče
se nevracejí, protože osa je append-only a přečíslování indexů by
zneplatnilo všechny matice, které si někdo drží. Naměřeno na 2 912
větách: po vráceném cyklu je otisk registru shodný (32 vazeb, prázdné
obsazení, verze 0) a v koších nezbyla ani jedna `CUSTOM=` aktivace.

**Co promoce sama o sobě dělá.** Bez učení klesla přesnost 0,3333 →
0,30 a cyklus se vrátil — což souhlasí s referencí, kde je C−B = 0
(„sloty si zatím nevydělaly na přesnost"). Proto zadání zavádí užitek
otázkám jako vážený člen selektu; to je páka, kterou se to má zlomit.

## 17 · Zrcadlo: co graf umí, obrázek musí unést

Princip 6 říká, že graf a jeho vizualizace jsou totéž. V praxi to
znamená tři překlady, protože obrázek má jiná omezení než data —
a všechna tři se ukázala až při běhu proti skutečnému oknu:

**Typ uzlu se musí zavést napřed.** viewBase odmítne uzel
s nedefinovaným typem. Zrcadlo si typ zavede samo při prvním setkání;
jinak by ingest spadl uprostřed, jakmile se objeví nový slovní druh.

**`source` znamená jinde něco jiného.** V deltě grafu je to
provenience (text × dictionary × dialog), ve viewBase ZDROJOVÝ UZEL
hrany. Do okna proto chodí jako `origin`.

**Hrana je v obrázku neorientovaná a jen jednou.** Graf počítá hranové
instance s opakováním (16 074 na 2 912 vět) a orientaci nese v deprelu;
viewBase klíčuje dvojici nesetříděně a duplicitu odmítá výjimkou.
Dedup proto patří do kresby, ne do dat — kdo by ho dal do grafu,
rozbil by skóre promoce, které na opakování stojí.

Naměřeno proti skutečnému oknu: Jordán dostane `glow` 1,67, Galilej
1,20 — tytéž hodnoty, které vypočítá `illuminate`, doputují až do
metadat uzlu, a s nimi i čitelné `sousede = "ADJ:pokřtěný (obl)"`
a `stupen = 1`.

## 18 · Spektrální člen: spojité zobecnění vedle pojmenované osy

S2 ze zadání. Zaceluje mezeru, kterou pytel neumí přejít: slova, která
spolu nikdy nestojí ve větě, a přesto patří k sobě. Spektrum je spojí
přes SDÍLENÝ KONTEXT.

Ověřeno na vzorku ze zadání (4 věty × 5 os) — singulární hodnoty
2,885 · 1,681 · 0,922 · 0, cos(smět, povolený) surově 0,00, při k=1
1,00, při k=2 zpátky 0,00. A na 2 912 větách: *Newton × Einstein*
surově 0,00 → spektrálně 0,51, ačkoli spolu nikdy nestojí ve větě.

**Proč jen vážený člen.** V latentním prostoru není nic přesně nula —
naměřeno: otázka o dálnici má surově přesnou nulu u 1 971 z 2 912 vět,
latentně u nuly. Na té přesné nule ale stojí detekce mezery (§ 14),
takže latentní osy nesmějí osu nahradit. Přidávají jedno přiznané
číslo do rozkladu, nic víc.

**k je páka s dvojím oknem.** Naměřeno na 2 912 větách:

| dvojice | k=5 | k=20 | k=50 | k=200 |
|---|---|---|---|---|
| Newton × Einstein | +0,98 | +0,86 | +0,92 | +0,51 |
| z × od (obě „from") | +0,72 | +0,77 | −0,27 | −0,32 |
| od × do (OPAČNÉ) | +0,61 | −0,07 | −0,02 | −0,00 |

Obsahová slova snesou velké k; gramatické rozdíly žijí kolem k=20
a při k=5 se slijí i protiklady. Na etalonu vyšel výsledek stejně pro
k ∈ {20, 50, 200} a W ∈ {0,5; 1; 2} — člen je zatím slabý proti
ostatním, takže na jeho nastavení nezáleží tolik jako na tom, že vůbec
je.

**Co doopravdy zvedl.** Zadání předpovídalo třídu *smět ↔ povolený*
(dálnice), ale ta se na biblicko-fyzikálním korpusu změřit nedá —
*dálnice* v něm není. Naměřený zisk je jinde: otázka „Kde se narodil
Karel Čapek?" (typ *most: elipsa podmětu*), kde věta s odpovědí
podmět neopakuje. Spektrální člen tam přispěl 0,864, druhý nejvíc po
`meet`, a dostal správnou větu do top-3.

**Zamítnuta náhodná inicializace vah.** Naměřeno: náhodné váhy ±0,20
na učených hranách zvednou přesnost z 11/30 na 12–14/30 (pět semínek
z pěti lepších než nula). Je to ale chudá aproximace téhož —
náhodná projekce místo spektra — a stojí to průhlednost, rozdíl mezi
naučenou nulou a chybějící vazbou, a rozptyl stejně velký jako zisk.
S2 dělá totéž řízeně a deterministicky.

## 19 · Předvýběr patří grafu, ne pytli

Graf jsme postavili v kroku 2, ověřili na 16 074 hranách — a k odpovídání
ho nepoužívali. Sloužil jen promoci a kreslení. Přitom je to on, kdo nese
**strukturu**: když se rozsvítí *Ježíš* a *pokřtěný*, záře po hranách
dojde k *Jordánu*, protože na *pokřtěném* opravdu visí. Pytel vidí jen
množinu slov a Jordán s Galilejí jsou v něm k nerozeznání — což je přesně
věta z § 1 zadání, kvůli které graf vznikl.

Naměřeno (117 tréninkových otázek, jejichž odpověď v korpusu je):

| předvýběr | top-50 | top-200 | věta v top-3 (etalon) |
|---|---|---|---|
| kosinus slov otázky | 37/117 | 58/117 | 17/30 |
| GraphRecall depth=1 | 49/117 | 67/117 | 19/30 |
| **GraphRecall depth=2** | **53/117** | 69/117 | **22/30** |
| GraphRecall depth=3 | 53/117 | 70/117 | 22/30 |

Hloubka 2 je provozní bod: třetí skok už nepřidá nic. Je to táž mez jako
u `spread_depth` — signál se dál jen rozmělní.

**Skóre věty je MAXIMUM ze záře jejích uzlů, ne součet.** Součet by
zvýhodnil dlouhé věty; je to týž degenerát, kvůli kterému je čtení
gaussovské (naměřeno: max 25/30, součet 23/30).

**Záře se ale při šíření SČÍTÁ.** Uzel, ke kterému vede cesta od víc
lemat otázky, je nosnější než uzel dosažený jednou cestou. Sečíst při
šíření a maximovat při čtení věty není nedůslednost — je to dvojí
otázka: „jak silně tenhle uzel svítí" proti „jak dobře na tuhle větu
sedí otázka".

## 20 · Stop slova do grafu nepatří — naměřeno

Otázka stála takhle: má být graf zaplněný předložkami a spojkami, nebo
bez nich? Odpověď je monotónní a nemilosrdná (recall na 117 otázkách):

| graf | uzlů | hran | recall |
|---|---|---|---|
| obsahová slova (dnešek) | 5 781 | 15 953 | **54/117** |
| + předložky | 5 829 | 18 409 | 48/117 |
| + předložky a spojky | 5 879 | 20 511 | 47/117 |
| + zájmena a pomocná slovesa | 5 939 | 25 085 | 27/117 (etalon **0/30**) |

Mechanismus je jasný: zavřená slova jsou rozcestí, která leží na KAŽDÉ
cestě. Podíl `1/hran` sice omezí, kolik jednotlivá hrana předá, ale při
dvou skocích přes ně dojde záře odevšad všude a rozdíl mezi větami
zmizí. Přidat je znamená vyrobit si graf, ve kterém svítí všechno —
tedy nic.

Je to nezávislé potvrzení rozhodnutí z kroku 2 (`NODE_UPOS` bez
zavřených tříd), které tehdy padlo kvůli shodě s přejímkou 16 074 hran.

## 21 · Měřicí protokol: ramena, ne jedno číslo

Krok 10. Šest ramen nad TÝMŽ korpusem, aby šlo poznat, co který díl
přidal. Naměřeno (2 912 vět, supervize 120, etalon 40):

| rameno | co měří | přesnost | mlčení | věta |
|---|---|---|---|---|
| A | baseline, hloubka 1, bez učení | **0,3667** | 0,00 | 24/30 |
| B | + kontrastivní učení | 0,3667 | 0,00 | 24/30 |
| D | hloubka 2 na čistém baselinu | 0,3667 | 0,00 | 24/30 |
| C | promoční cyklus nad B | **0,4000 PŘIJATO** | 0,00 | 24/30 |
| E | hloubka 2 nad C | 0,3667 | 0,00 | 24/30 |
| F | θ = 2,539 (kalibrované) | 0,0667 | **1,00** | 24/30 |

**A sedí na zmraženou hodnotu § 6** (`Matcher baseline k=1 · 0,3667 ·
mlčení 0`) — jinou cestou než reference, ale na totéž číslo.

**Promoce poprvé vydělala.** C zvedlo přesnost o jednu otázku
(0,3667 → 0,4000) a cyklus se přijal. V referenci byl rozdíl C−B nula
(„sloty si zatím nevydělaly na přesnost"); s předvýběrem grafem se to
otočilo.

**Hloubka 2 tady nepomáhá.** D i E dávají 0,3667, kdežto reference měla
E 0,467. Skládá se to jinak, protože předvýběr už dělá graf: hloubka
šíření po vazbách registru dodává něco, co graf dodal dřív a lépe.

**F je provozní bod, ne vítěz.** Kalibrované θ zvedne mlčení na 1,00
a přesnost srazí na 0,0667. Systém raději mlčí, než aby tipoval — a je
to rozhodnutí, ne měření.

**θ kalibrované na tréninku přenáší špatně.** Nad supervizí vyšlo
0,0133/1,0, tedy prakticky „mlč vždycky": tréninkové otázky jsou
parafráze, tedy těžší než etalon, a práh vybraný na těžší sadě umlčí
i to, co by na lehčí prošlo. Kalibrovat se přesto musí tam — jinak by
se práh vybíral podle testu, který má měřit.
