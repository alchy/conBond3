# Rozklad skóre — z čeho se odpověď skládá

Systém nikdy nevydá jen číslo. Každá odpověď se dá rozložit na **pojmenované
členy** a z nich přečíst, čím se rozhodlo — to je celý důvod, proč systém
stojí na pojmenovaných osách a ne na latentních.

```
./run-python cb_bond/scripts/rozklad-skore.py        # celý etalon
./run-python cb_bond/scripts/rozklad-skore.py 8      # prvních 8 otázek
```

---

## 1 · Jak se skóre sestavuje

Kandidát je **token ve větě**. Jeho skóre je prostý součet vážených členů:

```
skóre = meet + cover + topic + given + fit + spectral
```

Žádná brána, žádné `if`, žádný filtr — výsledkem každého členu je číslo,
ne rozhodnutí (princip 2). Jediné dva řezy v celé cestě jsou **θ** (mlčení)
a **ε** (dotaz) a stojí až úplně na konci, nad hotovým pořadím.

Váhy jsou `ScoreWeights`, tedy **páky, ne pravidla**: vypnout člen znamená
dát mu nulu, ne odstranit větev v kódu.

| váha | výchozí | co ovládá |
|---|---|---|
| `center` | 2,0 | jak moc se zdůrazňuje střed koše uvnitř `meet` |
| `cover` | 1,0 | pokrytí daných os |
| `topic` | 1,0 | tématická blízkost |
| `given` | **−3,0** | postih za ozvěnu otázky |
| `fit` | 0,0 | naučený člen — **zatím prázdné místo**, viz níže |
| `spectral` | 0,0 | latentní podobnost (§ 5/S2, zapíná se `spectral_k`) |

### Dvě patra: co řadí tokeny a co řadí věty

To je na skládání skóre nejdůležitější a v tabulce je to vidět na první
pohled:

| člen | úroveň | uvnitř věty |
|---|---|---|
| `meet` | **token** | mění se |
| `given` | **token** | mění se |
| `cover` | věta | konstantní |
| `topic` | věta | konstantní |
| `spectral` | věta | konstantní |

Tři členy vyberou VĚTU, dva pak uvnitř ní vyberou SLOVO. Kdo tohle plete,
diví se, proč mají všichni kandidáti téže věty stejné `cover`.

### Nad čím který člen počítá

Každý člen žije nad jiným vektorem — to není nedůslednost, to je celý
návrh:

```
q̃            pytel CELÉ otázky → semantická maska → saturace
             (jeden pytel na celou otázku: otázka nemá střed,
              roli nese pád — princip 5)

okno         řádky věty vážené harmonicky 1/(1+|o|) od kandidáta,
             saturované, JEDNOTKOVÉ

střed        řádek kandidáta, saturovaný, JEDNOTKOVÝ (zvlášť!)

slova q      co otázka TVRDÍ — WORD= os bez tázacích slov (QLEM=)
             a bez interpunkce; SUROVÉ, bez saturace

slova věty   WORD= osy věty bez interpunkce, surové
```

**Semantická maska** propouští jen `WORD=`, `LEM=`, `QLEM=`, `ANCHOR=`,
`QANCHOR=`, `Polarity=`, `CUSTOM=`. Strukturní osy (`UPOS=`, `DEPREL=`,
`Case=`, `SUBPOS=`, morfologické rysy) vypadnou úplně — sdílí je skoro
každá věta, takže by kosinus měřil podobnost gramatiky. Maskuje se PŘED
sečtením, aby nemohly nafouknout normu.

---

## 2 · Členy jednotlivě

### meet — setkání v uzlech

```
meet = q̃·(okno + (W_CENTER−1)·střed) / ‖q̃‖
     = cos(q̃, okno) + (W_CENTER−1)·cos(q̃, střed)
```

Měří, jak moc se otázka a okolí kandidáta potkávají v aktivovaných osách.
Obě strany se **šíří stejně**: otázka nese `QANCHOR=space:loc`, věta
`ANCHOR=space:loc`, a společnou souřadnici mají až o krok dál. Šířit jen
otázku znamená měřit setkání v místě, kam druhá strana nedošla.

Okno je **harmonické přes celou větu** — řádek ve vzdálenosti `o`
přispívá vahou `1/(1+|o|)`. Váha doznívá, takže okno nemá hranu; ořezat
ho na ±r tu hranu vrátí a stojí to bod na etalonu (10/30 proti 11/30).

Zdůraznění středu je **vlastní člen, ne násobek uvnitř okna**. Okno
i střed se normují na jednotkový vektor zvlášť, takže platí ta identita
nahoře. Kdo počítá `cos(q̃, okno + 2·střed)` nad surovým pytlem, trestá
středy s bohatou morfologií — norma součtu roste s tím, kolik os střed nese.

### cover — pokrytí daných os

```
cover = W_COVER · min přes DANÉ osy z tanh(spread(celá věta))
```

**Není to kosinus, je to mohutnost.** Pro každou osu, kterou otázka
tvrdí, se zjistí, jak silně ji věta nese; rozhoduje ta **nejslabší**.
Jedna chybějící osa stáhne člen na nulu, i kdyby ostatní byly plné.

Hodnoty vycházejí z vah aktivací a jsou čitelné: `tanh(0,7) = 0,604` je
jeden výskyt slovní osy, `tanh(1,4) = 0,885` dva, saturovaná jednička
mnoho. Osa, kterou korpus nezná vůbec, dá **přesnou nulu** — propast,
ne škála. Na tom stojí detekce mezery (krok 8) bez jakéhokoli prahu.

### topic — téma

```
topic = W_TOPIC · cos(slova otázky, slova věty)
```

Plný kosinus nad **surovými slovními bloky**, bez saturace. Slova otázky
jsou to, co otázka TVRDÍ — bez tázacího slova a bez interpunkce. Kdyby
v nich „kdo" zůstalo, téma by odměňovalo věty, které samy obsahují „kdo":
v Markově evangeliu tedy OTÁZKY, ne odpovědi (naměřeno — „Kdo pokřtil
Ježíše?" vyhrávalo „A kdo ti dal moc, abys to činil?").

### given — postih za ozvěnu

```
given = W_GIVEN · cos(slova otázky, slova STŘEDU)      W_GIVEN = −3,0
```

Kandidát, jehož slovo otázka sama uvádí, není odpověď: „Kdo pokřtil
Ježíše?" nemá odpovědět „Ježíš". Střed nese jedinou slovní osu, takže
kosinus s pytlem otázky je nenulový právě tehdy, když to slovo v otázce
je.

**Je to nejsilnější člen systému** a v rozkladu vítěze ho nikdy
neuvidíte — viz § 4.

### spectral — latentní podobnost (§ 5/S2)

```
spectral = W_SPECTRAL · cos(q·V_kᵀ, věta·V_kᵀ)
```

`V_k` je `k × všechny osy`; každý řádek je jedna latentní osa, tedy
vážená směs všech os najednou — slovních i metadatových. Otázka i věta
se do těch `k` dimenzí promítnou a porovnají.

Zaceluje mezeru, kterou pytel přejít neumí: slova, která spolu nikdy
nestojí ve větě a přesto patří k sobě. Naměřeno na 2 912 větách:
*Newton × Einstein* surově 0,00 → spektrálně 0,51.

Počítá se jen když si o to někdo řekne (`spectral_k`), přepočítává se
v promočním cyklu a **W_SPECTRAL = 0 dá bit po bitu dnešek**.

### fit — a kde je v rozkladu učení

**Nikde. A je to mezera, ne vlastnost.**

Člen `fit` je zatím prázdné místo: počítá doslova `W_FIT · 0.0`. Naučené
váhy do skóre nevstupují jako vlastní člen, ale **vazbami registru**,
které mění `spread` — a ten stojí uvnitř `meet` (přes `q̃`, okno i střed)
a uvnitř `cover` (přes saturované pytle vět).

Učení tedy skóre ovlivňuje, ale rozklad to nepřizná: přispěje do `meet`
a `cover`, kde se smíchá s tím, co tam bylo od začátku. Systém, který
stojí na tom, že každé rozhodnutí jde rozložit po pojmenovaných členech,
má **právě tenhle jeden příspěvek neviditelný**.

Spočítat ho lze — je to rozdíl mezi šířením se všemi vazbami a šířením
jen po axiomech:

```
naučený příspěvek = meet(všechny vazby) − meet(jen axiomy)
```

Stojí to druhou saturaci na kandidáta, tedy zhruba dvojnásobek času
`match()`. Dokud se to nedoplní, platí: **co v tabulce vidíte, je stav
bez viditelného učení**, a naučené hrany jsou schované v `meet`
a `cover`.

---

## 3 · Jak výstup číst

```
OK Kdo zformuloval zákon všeobecné gravitace?
     čeká Newton         → 'Newton'
     meet +1.25 · cover +0.60 · topic +0.89 · given -0.00 · spectral +0.85
     1. 2.19 < [Newton] Newton zformuloval zákon všeobecné gravitace.
     2. 2.01   [popisovat] Zákon všeobecné gravitace popisuje vzájemné…
     3. 1.66   [Einstein] Einstein zformuloval obecnou teorii relativity.
```

| značka | co znamená |
|---|---|
| `OK` | trefeno — lemma vítěze se rovná očekávanému |
| `--` | zodpověditelná otázka, netrefena |
| `sv` | svod: otázka je NEzodpověditelná, systém měl mlčet |
| `<` | ta věta nese očekávané lemma |

Čísla u vět jsou **gaussovské vrcholy** (krok 4), ne součty skóre —
proto se pořadí vět může lišit od pořadí tokenů.

---

## 4 · Tři věci, které z rozkladu vyskočily

### cover je binární spínač a předpovídá selhání

Nabývá +0,60, nebo +0,00 — nikdy nic mezi. A ta nula bezchybně označuje
otázky, které systém nezvládá:

```
Kde se narodil Einstein?         cover +0,00
Kdy zemřel Newton?               cover +0,00
Kde se dávali lidé křtít?        cover +0,00
Kdo pokřtil Ježíše?              cover +0,00
Kdo je autorem Války s mloky?    cover +0,00
Kde se narodil Karel Čapek?      cover +0,00
Čím byl Newton?                  cover +0,00
```

Sedm z devíti nejhorších případů má `cover` nulu — **systém předem ví,
že na tu otázku nemá.** Dnes se to nikde nevyužívá; kdyby ano, bylo by to
poctivé „nevím" místo náhodné odpovědi. Je to nejlevnější zlepšení, které
v systému leží.

### given je neviditelný a přitom nejsilnější

U vítěze je vždycky `−0,00`, a to není chyba: postih srazí kandidáta,
jehož slovo otázka uvádí, takže takový kandidát **nikdy nevyhraje**. Jeho
práce je vidět jen na tom, kdo nevyhrál.

Ablace to potvrdila tvrdě — bez něj je přesnost **0/30**:

| konfigurace | reference | tady |
|---|---|---|
| plné skóre | 14/30 | 11/30 |
| bez tématu | 12/30 | 11/30 |
| bez zdůraznění středu | 9/30 | 8/30 |
| bez pokrytí | 7/30 | 9/30 |
| **bez postihu daného** | **0/30** | **0/30** |
| jen setkání | **0/30** | **0/30** |

Bez postihu vyhraje vždycky ozvěna otázky. Nejsilnější člen systému je
ten, který v rozkladu vítěze nikdy neuvidíte.

### spectral zvedá hladinu, nerozlišuje

Přispívá stabilně 0,64–0,87 skoro u všech otázek. To vysvětluje, proč byl
výsledek necitlivý na `k` i `W` — člen zatím spíš zvedá celou hladinu, než
aby řadil. Rozdíl udělal právě tam, kde ostatní členy mlčely: u „Kde se
narodil Karel Čapek?" (typ *most: elipsa podmětu*) je `cover` 0,00, ale
`spectral` +0,87, a to dostalo správnou větu do top-3.

---

## 5 · Naměřený stav (2 912 vět, etalon 40 otázek)

| předvýběr | přesnost@1 | věta v top-3 | mlčení |
|---|---|---|---|
| kosinus slov otázky | 11/30 | 21/30 | 0 |
| **grafem (depth=2)** | 11/30 | **24/30** | 0 |
| grafem + spektrum | 11/30 | 24/30 | 0 |

Předvýběr grafem zvedl VĚTNÉ čtení o tři otázky a přesnosti se nedotkl
— což dává smysl: graf vybírá věty, výběr slova uvnitř věty dělají
`meet` a `given`. Pokrytí zůstalo beze změny (1,000 / 0,604 / 0,885),
protože se počítá nad celým korpusem, ne nad shortlistem.

Nejčastější vzorec chyby: **správná věta první, špatné slovo z ní.**

```
Kam se přestěhovala rodina?    čeká Nymburk  → prožít
  1. 2.63 < V srpnu 1919 se čtyřčlenná rodina přestěhovala do Nymburka…
Kam šel v sobotu?              čeká synagóga → učit
  1. 2.46 < Když přišli do Kafarnaum, hned v sobotu šel do synagógy a učil.
Kdy obdržel Einstein cenu?     čeká 1921     → rok
  1. 2.32 < Einstein obdržel Nobelovu cenu roku 1921.
```

Systém tedy **rozumí větě, ne roli**. Když je odpověď hlavní jméno věty,
trefí ji; když je to příslovečné určení („do Nymburka", „roku 1921"),
najde správnou větu a vybere z ní špatné slovo. Rozlišit roli uvnitř věty
umí jen `meet` a `given` — a to jsou přesně ty dva token-úrovňové členy.
Tam vede další práce.
