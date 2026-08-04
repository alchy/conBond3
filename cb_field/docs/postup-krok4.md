# Postup krokem 4 — úplný záznam, včetně omylů a změn směru

Vzniklo na výslovné přání J. (2026-08-03): *„prosím všechny kroky, které
činíš, důkladně popiš, z důvodu, že došlo několikrát ke změně směru
a zanesení bloků do kódu."* Záznam je chronologický a nezamlčuje slepé
uličky — vada zapsaná jen v commitu se za půl roku „zjednoduší" zpátky.

Vysvětlivky: **blok** = tvrdé pravidlo (filtr, brána, strop), které
odřízne data dřív, než se dostanou k vahám. Bloky jsou v tomhle projektu
antivzor: zabraňují učení, protože vyhladoví trénink.

---

## 1 · Výchozí stav (před krokem 4)

Hotovo a změřeno: koše, vážené aktivace, kotvy, registr s vazbami,
šablony (T2 = 0,34 při r=1), viewer. Vše čistě váhové.

## 2 · Spec kroku 4 (README-PROPOJENI.md)

Zapsáno: skóre = qᵀ·W·a; síla propojení je učitelný koeficient; růstový
zákon (SLABÁ → učení vah, NEPŘESNÁ → nová obecná osa); zákaz konkrétna;
tři východiska ODPOVĚĎ / DOTAZ / NEVÍM; cíl je graf, párování je jen
aktivátor uzlů.

**Doplněno později** (J.): úniková páka r; DOTAZ jako aktivní učení;
P-A „koš je pytel" — pořadí se smí zatřást, proto vznikla osa `dir:`
a přenos směru z předložky na jádro.

## 3 · 4a — první implementace párování (a čtyři bloky, které jsem zanesl)

Baseline bez ladění dala 0,06. Následovaly čtyři iterace, každá
odstranila chybu — ale **tři z nich zavedly blok**:

| # | co jsem přidal | typ | důsledek |
|---|---|---|---|
| 1 | párovací pytle jen ze sémantických vertikál | **váha** (maska prefixů) | správně: tvar patří šablonám, ne propojení |
| 2 | dimenzní brána na řádku středu | **BLOK** | kandidát bez kotvy vypadl bez šance |
| 3 | jen jmenné kandidátní středy | **BLOK** | slovesa a příslovce nikdy nekandidovala |
| 4 | min. 2 sdílená obsahová slova | **BLOK** | celá věta zahozena před skórováním |
| 5 | vyloučení slov daných otázkou | **BLOK** | tvrdé místo záporné váhy |

Čísla vyskočila na 0,79 / 0,71. **Vypadalo to jako úspěch a bylo to
zavádějící**: bloky nesly práci, kterou měl dělat naučitelný model.

## 4 · 4b/4c — učení (napsáno, ale vyhladovělé)

`learning.py`: Hebb (NPMI ze souaktivací) + kontrastivní krok
(posílit otázka→správná, oslabit otázka→vítěz) + protiváha
(NEVÍM-správnost nesmí klesnout, jinak NEPŘIJATO).

Na testbedu 0,79 → 0,82. Na komplexních korpusech (2 912 vět)
0,37 → 0,42, přičemž **Hebb sám uškodil** (0,32) — 103 tisíc hran ze
surových souvýskytů utopilo signál.

## 5 · Pitva „Kdo pokřtil Ježíše?" — kde se to zlomilo

Data ukázala něco jiného, než jsme oba čekali:

```
otázka: pokřtil → VERB, lemma pokřtít  → WORD=VERB:pokřtít
fakt:   pokřtěn → ADJ,  lemma pokřtěný → WORD=ADJ:pokřtěný
průnik obsahu = 1 slovo < práh 2  →  věta VYPADLA před skórováním
```

Kontrolní pokus s vypnutým filtrem: systém odpověděl **Jan** správně —
role uhrál (agent pasiva „od Jana" nese `dir:from` + `entity`).
Lámalo se to na **slovotvorbě**, ne na rolích ani na r.

## 6 · Zásadní korekce J. — a co z ní plyne

> „proč učíme NN na příkladech? protože jinak různé tvary metadat
> nespárujeme — proto je tam ta aktivační NN část… prosím když
> přinášíš vlastní řešení — přinášej řešení, která neblokují vývoj!"

Trefa. Kontrastivní krok **je** ten most (VERB↔ADJ), ale moje bloky ho
vyhladověly: věta se nikdy nestala kandidátem, takže se pár do učení
nedostal. **Filtr bránil právě tomu, co měl řešit.**

Následoval přepis `matching.py` — kandidátem je **každý token**, bloky
nahradily vážené členy:

```
skóre = spread(q)·spread(a)            setkání v uzlech
      + W_TOPIC · obsah(q, věta)       bonus tématu celému pytli (nakonec)
      + W_GIVEN · dané(střed, q)       záporná váha místo vyloučení
```

Jediné řezy v systému: **θ** (NEVÍM) a **ε** (DOTAZ) na konečném skóre.
Rychlost drží algebra: `spread(q)·spread(a) = q_eff·a`.

**Doklad, že to bylo správně:** na téže otázce si systém po 3 krocích
učení postavil hranu `WORD=VERB:pokřtít → WORD=ADJ:pokřtěný` (0,0735,
zdroj etalon) a odpověď se překlopila `přišel → Jana`.

## 7 · Dva zbytky mého starého reflexu (přiznané)

1. **Strop kandidátů** (`top_candidates=8`) — zase vyhladověl učení:
   správná odpověď nebyla v osmičce, takže se most neměl z čeho učit.
   Odstraněno; parametr slouží jen ke zkrácení výpisu.
2. **IDF váha** — přidal jsem ji proti tomu, aby uzly hierarchie
   fungovaly jako huby. Je to váha, ne blok (nikdy nezabíjí, po
   vyhlazení `1 + ln((1+N)/(1+df))`), ale je to **moje** heuristika:
   kandidát na nahrazení naučenými koeficienty, až učení dozraje.

## 8 · Oprava učení: gradient marže na rozdílu pytlů

Bez bloků je „špatný" kandidát obvykle **soused ve stejné větě** —
pytle sdílejí většinu klíčů. Původní krok (zvlášť +a⁺, zvlášť −a⁻) na
nich vyráběl šum: 0,21 → 0,00 (protokol NEPŘIJAL).

Nově `ΔW = η · q ⊗ (a⁺ − a⁻)` s normalizací délkou — učí se jen to,
**čím se kandidáti liší**. Výsledek 0,24, protiváha drží → PŘIJATO.

## 9 · Korekce J. k tréninku

> „pro to učení je potřeba na složitější věty více otázek. učíme
> souvislosti ne jen ‚Kde je kočka?' → ‚Kočka je na střeše.' to by
> zvládl grep"

Vznikla oddělená trénovací sada `trenink-otazky-korpusy.jsonl`
(35 otázek): parafráze, které **neopisují** větu — „Kdo objevil
gravitaci?" proti „Newton zformuloval zákon", „Čím je způsoben příliv?"
proti „Měsíc způsobuje příliv", „Kdo je autorem Principií?" proti
„Newton napsal knihu". Trénink a měření jsou od sebe oddělené; padá tím
dřívější mez „laděno a měřeno na témže etalonu".

K tomu výpisy z učení po epochách: **loss** (hinge marže: kolik chybí,
aby správná odpověď vedla), trefy na tréninku, počet korekcí a hran.

## 10 · Poučení, která platí dál

1. **Blok je vždy podezřelý.** Když zlepší číslo, zeptej se, co jsi
   tím vypnul — obvykle učení.
2. **Vysoké číslo z bloků je horší než nižší z vah**, protože
   negeneralizuje a blokuje další vývoj.
3. **Učení se musí mít z čeho učit**: každý strop (kandidátů, prahů,
   kategorií) mu ubírá trénovací signál.
4. **Trénink ≠ měření**, a otázky nesmí opisovat věty — jinak měříme
   grep.
5. **Negativní výsledek se zapisuje**: Hebb na velkém korpusu uškodil;
   je to fakt do protokolu, ne důvod ho tiše vypnout.

## 11 · Otevřené a nedodělané (poctivý stav)

- θ a ε po přepisu **nejsou kalibrované** (θ = 2.0 je startovní číslo);
  na testbedu bez bloků je baseline 0,21 a učení zvedá na 0,24.
- Čísla z éry bloků (0,79 / 0,82 / 0,42) **nejsou srovnatelná** s čísly
  po přepisu — jiná mechanika, jiný režim.
- IDF váha čeká na nahrazení naučenými koeficienty (§ 7.2).
- Dvojité r (r_words × r_sentences) ze zadání J. je **rozebrané, ale
  nepostavené** — pořadí bylo přehodnoceno ve prospěch odblokování
  učení.
- Kalibrace Hebba (min_count, práh NPMI, typy hran) po jeho negativním
  výsledku.

## 12 · Refaktor učení, kroky 1+2: tanh + kosinus (2026-08-04)

Provedení závazného pořadí z workflow § D5. Mechanika:

- **tanh po každém kroku šíření** (matching): aktivace se saturují do
  −1…+1, rozsahu vah (P-B). Lineární trik spread(q)·spread(a) = q_eff·a
  tím padá — pytle faktů se šíří explicitně a drží se řídce v cache
  korpusu (klíč: růst korpusu × verze vazeb; tanh nule nechává nulu).
- **kosinová normalizace**: každý člen skóre je kosinus dvou pytlů.
  Zdůraznění středu je vlastní člen `(W_CENTER−1)·cos(q̃, střed)` —
  ×W_CENTER na surovém pytli by pod kosinem správné středy TRESTALO:
  norma roste o všechno, co střed nese, čitatel jen o setkání s otázkou,
  a odpověď je z podstaty to, co v otázce není. Naměřeno: s hrubým
  zdůrazněním 0,03, s vlastním členem 0,61.
- **IDF náplast odstraněna** (dluh § 11): roli protiváhy hubů převzala
  saturace. Naměřeno: bez IDF 0,67, s IDF 0,61 — předpověď z rozhodnutí
  („odstraní huby i potřebu IDF náplasti") potvrzena.
- **θ = 0,45 · ε = 0,057**: jen přepočet měřítka (medián vítězných
  skóre 4,90 → 1,11, poměr 0,227), kalibrace na oddělené sadě zůstává
  dluhem.
- Učicí pytle dostaly týž profil středu (W_CENTER) jako koš v match():
  gradient se počítá nad geometrií, kterou optimalizuje — bez toho se
  odpověď ležící v okně obou kandidátů v rozdílu pytlů vyruší.
- Soupeřem kontrastu je nejlepší ŠPATNÝ kandidát (ne vítěz): když
  vítězí správná s malým odstupem (DOTAZ), kontrast proti vítězi by
  byl správná proti sobě.

| testbed (40 otázek) | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| lineárně bez filtrů (§ 11) | 0,21 | 0,00 |
| tanh + kosinus, bez IDF | **0,67** | 0,00 |

Protiváha drží (NEVÍM-správnost neklesla). SLABÁ spadla na 0 — zbylé
chyby zodpověditelných jsou DOTAZ (11×), tedy malé odstupy; přesně na
ně míří kroky 3 (relativní marže) a 4 (Adam).

**Poctivý nález ke kosinu:** normalizace zahodila MOHUTNOST důkazu, na
které stál řez θ — top-skóre zodpověditelných (1,06–1,58) a
nezodpověditelných (1,17–1,51) se dnes překrývají, NEVÍM neumí nic
odmítnout (FALEŠNÁ 3, DOTAZ-nezodp. 4). Není to regres (poctivá
baseline měla NEVÍM též 0,00), ale kalibrace θ sama nepomůže — chybí
člen nesoucí mohutnost. Kandidát: učení (4c) zvedne zodpověditelným
setkání, nebo nový vážený člen; rozhodnutí patří J.

## 13 · Refaktor učení, kroky 3+4: relativní marže + Adam (2026-08-04)

- **Relativní marže** (krok 3): marže = 0,2 × |skóre soupeře| — přenos
  staré proporce (1,0 / medián 4,9), žádné nové číslo od oka. Soupeř =
  nejlepší špatný kandidát. Učí se KAŽDÉ porušení marže, i tenká
  správná výhra; splněná marže = nulový loss a žádný krok, takže
  „korekcí 0" je skutečná konvergence.
- **Adam** (krok 4): momenty (m, v, t) na hranu, řídce, bez frameworku;
  β₁=0,9 · β₂=0,999 · ε=1e-8. Druhý moment přebírá normalizaci délky
  pytle (ruční `scale` zrušen). **η = 0,01** odvozeno z rozsahu vah:
  s η = 0,15 Adam divergoval (loss 0,40 → 0,53, trefy 16 → 8);
  s 0,03 přestřeluje (naměřeno, zapsáno u konstanty).
- **Odvolání epochy**: korekce nespadnou na nulu (marže není pro
  všechny otázky splnitelná najednou) a U-křivka lossu má minimum
  (~5. epocha), za nímž další epochy rozvracejí, co jiné otázky
  postavily. Epocha, která loss zhoršila, se odvolá (`registry.unlink`,
  vazby zpět) a trénink končí na minimu. Bez odvolání: eval 0,64;
  s ním 0,79.

| testbed, protokol 4b+4c | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (tanh+kosinus) | 0,67 | 0,00 |
| po 4b (Hebb) | 0,45 | 0,00 |
| po 4c (Adam, konec epocha 5) | **0,79** | 0,00 |

Výrok: PŘIJATO. Loss čitelný (0,32 → 0,20), trefy na tréninku 16 → 24
z 33, DOTAZ 11 → 6. Hebb dál škodí (dluh D4: má běžet až nad
strukturou). Pozn.: na testbedu je trénink = etalon (horní odhad, jiná
sada zatím není) — generalizaci měří korpusy s oddělenou sadou.

## 14 · Člen pokrytí otázky (2026-08-04, rozhodl J.)

Zadání J. po nálezu „kosinus zahodil mohutnost důkazu" (§ 12): vrátit
mohutnost jako vážený člen — pokrytí otázky.

**Slepé uličky (změřeno, obě NEoddělují):** součtové pokrytí
`(q̃·okno)/‖q̃‖²` i slovní `(slova q · slova věty)/‖slova q‖²` —
u každé nezodpověditelné otázky etalonu je právě JEDNA kritická osa
mrtvá (neznámé sloveso: parkovat/letět/odjet; neznámá entita:
Alois/Ostrava) a zbytek sedí dobře; jedna osa z N je v součtu malý
zlomek, rozdělení se překrývala celá.

**Řešení: nejslabší článek.** cover = W_COVER · min přes DANÉ obsahové
osy otázky (WORD= řádků bez QLEM= — tázací osa je neznámá, ta se
nekryje, ta se odpovídá) nad tanh(spread(věta)). Mrtvá osa = člen ~0.
Most z učení se počítá (spread před tanh) — parafráze pokrytí neztrácí,
jen ho má úměrné síle mostu. Po větě, ne po okně (uvnitř věty ranking
neruší, jako topic).

**Oprava reprezentace po cestě:** parser dává „Kolik" v otázce
PronType=Dem,Ind (žádné Int) → QLEM/QANCHOR mechanismus neměl za co
chytit a „kolik" padalo do daných os (falešná mrtvá osa i pro správnou
větu). Oprava: tázací čtení = Int od parseru NEBO členství v tabulce
INTERROGATIVE_ANCHORS, pokud parser tázací/vztažný výklad vůbec
nenabídl — vlastní tabulka přebíjí parserovo mlčení, ne jeho verdikt.

| testbed | přesnost@1 | rozdělení top-skóre (zodp. × NEzodp.) |
|---|---|---|
| bez pokrytí | 0,67 | 1,06–1,58 × 1,17–1,51 (překryv celý) |
| s pokrytím (baseline) | **0,85** | 1,73–2,45 × 1,46–1,75 (pruh 0,02) |
| s pokrytím po 4c | **0,97** | 1,94–3,06 × 1,82–2,61 (překryv zpět) |

Pokrytí pomohlo i rankingu (0,67 → 0,85 bez učení — věta nesoucí
všechny dané osy poráží generický vzor) a stabilizovalo učení: loss
klesá monotónně 0,25 → 0,08 přes všech 10 epoch, žádné odvolání epochy,
trefy 32/33.

**Otevřené (pro J.):** (a) učení na testbedu zvedá i nezodpověditelné —
generické mosty (kde→bydlet) slouží všem; na téže sadě se učí grep,
korpusová sada parafrází je stavěná líp. (b) θ zůstal 0,45 (od oka
z přepočtu) — kam posadit řez a na čem ho kalibrovat (trénovací sadě
chybí nezodpověditelné otázky) je designové rozhodnutí; před učením
by řez ~1,8 dělil skoro čistě, po učení ne.

## 15 · Korpusy po refaktoru: Hebb blokuje, mlčení funguje (2026-08-04)

Finální protokol nad komplexními korpusy (oddělené sady: trénink 23
zodp. + 10 nezodp. parafrází, etalon 40 otázek; zmražené epochy,
argpartition — epocha ~1 min místo ~20).

**Protokol s Hebbem: NEPŘIJATO.** Baseline s pokrytím 0,43 → po 4b
(Hebb, 103k hran) 0,17 → po 4c jen 0,20. Hebbův šum zvedá i vstupní
loss kontrastivní fáze (0,87 vs 0,64 bez něj) a 4c se z trosek na
tvrdé sadě nezvedne. Kalibrace θ zdegenerovala (trénink 1/23 →
optimum je mlčet vždy: θ=2,92, etalon 0,07/0,90). Dluh D4 v akci —
Hebb nad surovými souvýskyty nemá v přejímací cestě co dělat.

**Ablace bez Hebba:** 4c neškodí (etalon 0,43 = baseline) a na
tréninku se učí (trefy 1 → 6/23, loss 0,64 → 0,45, konec odvoláním
6. epochy). Mosty jsou ale párové (slovo↔slovo) a mezi otázkami se
nepřenášejí — generalizace čeká na obecnější osy (sloty/role krok 3,
typ krok 5), přesně podle stropu pytlů z § dřívějších měření.
Učení mlčení se nepohnulo (ticho 0/10): reference (medián správných)
je na tvrdé sadě nízko a krok η=0,01 × ~5 epoch nestačí na vzdálenost
~1 bodu skóre — na testbedu, kde jsou vzdálenosti menší, funguje.

**Kalibrované θ=2,125 (trénink, bez Hebba): etalon 0,33 / 1,00,
FALEŠNÁ 0.** První poctivý provozní bod na komplexním textu: systém
odpovídá na třetinu zodpověditelných a NIKDY falešně; směna 3
správných odpovědí za 10/10 správných mlčení proti θ od oka
(0,43/0,00, FALEŠNÁ 5).

| korpusy, etalon 40 otázek | přesnost@1 | NEVÍM-správnost | FALEŠNÁ |
|---|---|---|---|
| baseline s pokrytím, θ=0,45 | 0,43 | 0,00 | 5 |
| po 4b+4c (s Hebbem), θ=0,45 | 0,20 | 0,00 | 3 |
| po 4c bez Hebba, θ=0,45 | 0,43 | 0,00 | 5 |
| po 4c bez Hebba, θ=2,125 (kalibr.) | 0,33 | **1,00** | **0** |

**Otevřené (pro J.):**
1. Vyřadit 4b (Hebb) z přejímací cesty protokolu? (D4: „až nad
   strukturou“ — dnes prokazatelně blokuje.)
2. Kalibrace θ na čistě tvrdé trénovací sadě degeneruje k „mlč vždy“
   (přesnost na tréninku ~0,1). Kalibrační podmnožina potřebuje i
   případy, které systém umí — trénink mostů tvrdé, kalibrace řezu
   smíšené?
3. Učení mlčení na korpusech potřebuje buď víc epoch/větší η pro
   záporný směr, nebo cíl vázaný na pokrytí (mrtvá osa už je člen).

## 16 · Obrat: query basket místo odpovídače (2026-08-04, J.)

Zadání J. mění cíl kroku 4: **nehledáme přímou odpověď**. Otázka má
učením vést k *optimálnímu koši odpovědi* (query basket metadata)
a ten se teprve fituje na fakty; k odpovědi se systém nemusí dostat
přímo, může být ukázána **logickými operacemi** nad koši. Vedle
metadat otázky do toho vstupují **data o logických vazbách** (Bartlová:
Metody řešení slovních úloh pomocí logiky — šipkový diagram = graf
implikací, Vennovy diagramy = průniky košů). Spec: `docs/query-basket.md`.

Proč to sedí na naměřené: párové mosty (WORD=X ↔ WORD=Y) se mezi
otázkami NEPŘENÁŠEJÍ (§ 15: trénink 1 → 6/23, etalon beze změny).
Query basket je typový profil (podpis otázky), takže naučené platí pro
každou další otázku téhož druhu — tudy vede generalizace.

**Dnešní W_FIT je slepá ulička v malém**: člen „sedí střed do neznámé"
jsem postavil jen z kotev a kotvy jsou moc hrubé (space/time/quantity
má kdeco), kosinus nad nimi je skoro binární. Naměřeno r=2: 0,94 →
0,85 při W_FIT=1; 0,3 pomohlo na r=1 (0,85 → 0,88) a uškodilo na r=2.
Výchozí hodnota proto 0 — člen zůstává jako páka, ale jeho pořádnou
podobou je celý metadatový vzor koše, ne jedna kotva.

**Mřížka dvojitého r** (korpusy, etalon 40, bez učení, θ=0,45):

| r_slovo \ r_věta | 0 | 1 | 2 |
|---|---|---|---|
| 1 | 0,43 | 0,43 | 0,43 |
| 2 | **0,47** | 0,47 | 0,40 |
| 3 | 0,47 | 0,40 | 0,37 |

Testbed (nezávislé věty): r=1 0,85 · **r=2 0,94** · r=3 0,88 · r=4 0,85.
Závěr: r_slovo=2 je optimum na obou sadách (potvrzeno i odhadem J.);
kontext vět dnes nepomáhá — pytel se rozředí dřív, než přinese fakt.
Až query basket umí operovat nad koši, má r_věta co obsluhovat
(odvození přes hranice vět); dnes je to jen širší pytel.

## 17 · Typová konzistence jako falzifikační kritérium (2026-08-04, J.)

> „správně postavenou logikou, pokud se objeví stejný typ otázky, pak
> musí systém vždy najít dle této metody odpověď; pokud ne, jde
> o velikost testovací a znalostní báze"

Kritérium jde měřit přímo: otázky se seskupí podle **tázacího podpisu**
(QLEM + QANCHOR) a uvnitř skupiny musí být výsledek konstantní. Rozptyl
uvnitř typu je buď díra v metodě, nebo malá báze — a rozdíl mezi tím
poznáme pitvou konkrétního případu.

Testbed (r=2, 33 zodpověditelných, 6 typů):

| typ | uvnitř typu | |
|---|---|---|
| kdy / odkud / kdo / kolik | 7/7 · 5/5 · 5/5 · 1/1 | KONZISTENTNÍ |
| kde | 9/10 | rozptyl |
| kam | 4/5 | rozptyl |

**Obě výjimky mají logickou příčinu, ne datovou:**

1. *Kde bydlí Petr?* — správná („Petr bydlí v Liberci", 2,406) prohrála
   o **0,008** s „Dům, kde bydlí Petr, stojí na kopci". Systém sám
   vyhlásil DOTAZ, takže se nespletl, jen nerozhodl. Konkurence je
   VZTAŽNÉ „kde" proti tázacímu — mechanismus QLEM/QANCHOR ho rozlišuje
   v reprezentaci, ale v pytli obě věty nesou týž obsah a rozdíl se
   utopí.
2. *Kam jela Marie?* — vyhrálo „do Prahy" z věty **„Marie nejela do
   Prahy."** Negace se v párování ztratí: lemma „jet" je pro „jela"
   i „nejela" totéž a Polarity mezi párovacími vertikálami vůbec není
   (MATCH_PREFIXES = WORD/LEM/QLEM/ANCHOR/QANCHOR). Systém tedy nemá
   jak poznat, že věta tvrdí opak.

Druhý případ je přímá objednávka na logické vazby z § 16: **negace
musí do párování vstoupit jako vážený člen** (Polarity=Neg zápornou
vahou), ne jako filtr vět. Je to zároveň ukázka, proč J. míří na
operace mezi koši — NOT není jen doplněk výrazu, je to i vlastnost,
kterou nese samotný fakt v korpusu.

Závěr k tezi: na testbedu drží. Ze šesti typů jsou čtyři konzistentní
a oba rozptyly ukazují na chybějící mechaniku (negace, konkurence
vztažného „kde"), ne na malou bázi — přesně to falzifikační kritérium
mělo odhalit.

**Zpřesnění J. (tamtéž):** determinismus platí **podmíněně** — *„pokud
jsou nalezeny vzory předkládání faktů, pak pokud jsme na nějakém
takovém vzoru učeni, je to deterministické."* Konstantní výsledek se
tedy nemá čekat od typu otázky samotného, ale od **dvojice
(typ otázky × vzor předkládání faktu)**. Vzory předkládání jsou
šablony z kroku 2 (`templates.py`: signatura, kanonizace, TemplateBank),
takže obě patra se tu potkávají: query basket drží typ otázky, šablona
drží tvar faktu, a učení je nad jejich dvojicí.

Odtud plyne i výklad obou rozptylů výš: „Kde bydlí Petr?" prohrálo
s větou *jiného vzoru* (vztažná věta s „kde" uvnitř nominální fráze),
na kterém systém učen nebyl — dvojice (typ kde × vzor vztažné věty)
prostě neexistuje. Není to náhoda ani šum; je to nepokrytá buňka
mřížky typ × vzor. Měřit se proto má pokrytí té mřížky, ne jen
úspěšnost po typech — a T2 (podíl faktů sdílejících šablonu) je 0,34
při r=1, takže dvě třetiny faktů dnes žádný sdílený vzor nemají.

## 18 · Dosah r jako jediná legitimní příčina nenalezení (2026-08-04, J.)

> „matchnout správnou odpověď (v rámci metadat) neumíme jen tehdy, kdy
> je mimo naše r vět. jinak by měla být vždy v kandidátech."

Změřeno na testbedu: pro každou zodpověditelnou otázku se hledá, zda
koš správné odpovědi obsahuje aspoň jedno **dané** slovo otázky (tedy
zda podnět a odpověď padnou do jednoho koše), a na kterém místě
kandidát skončí.

| r | v dosahu a v top 3 | mimo dosah r | v dosahu, ale hluboko |
|---|---|---|---|
| 1 | 8/33 | 25/33 | 0 |
| 2 | **33/33** | **0** | 0 |

Teze platí doslova: při r=2 **není jediná odpověď mimo dosah** a všechny
jsou v první trojce. Zbylé chyby tedy nejsou o dosahu ani o kandidatuře,
ale výhradně o pořadí mezi několika málo vážnými kandidáty — a to je
práce pro váhy a query basket, ne pro širší okno.

Zároveň je to druhé, nezávislé zdůvodnění r=2 (první bylo přesností):
r=1 nechává dvě třetiny odpovědí bez podnětu v koši a systém je trefuje
jen díky členům přes celou větu (téma, pokrytí) — tedy náhradou za
dosah, ne dosahem samotným.

## 19 · Typ z okolí pomohl málo — a ukazuje proč (2026-08-04)

Řetěz J. *kde → místo ← řeka* je v reprezentaci doložitelný: „Jordánu"
má ANCHOR=space z NameType=Geo, „řece" jen dir:at z předložky. Chybí
tedy hrana obecné jméno → dimenze. `learn_types()` ji učí z textu
(NPMI nad dvojicí slovo × kotva v koši, jen dimenze bez dir:*).

Korpusy r=2, 549 typových hran z 2 298 doložených dvojic:

| | přesnost@1 | vada | mimo dosah |
|---|---|---|---|
| baseline | 0,50 | 4 | 6 |
| po typech | 0,50 | 4 | 6 |

Pořadí vadných se posunulo (Nazareto 10 → 6, Čapek 87 → 59, řeka
1159 → 912), ale **žádná vada nezmizela** a přesnost se nehnula.

**Proč: typ sám nerozlišuje.** Hranu ke space dostane každé slovo,
které opakovaně stojí v koši s místní kotvou — a to je v souvislém
textu spousta slov (549 hran). Aktivace se tedy přelije do „místa"
u všech kandidátů okolí najednou; „řeka" se posune, ale spolu s ní
i její sousedé. Typ je nutná podmínka (bez něj se odpověď s otázkou
vůbec nepotká), ne dostatečná.

Co z toho plyne pro další krok: rozlišit musí **kombinace** — „je to
místo" ∧ „je v koši s podnětem otázky (křtít)". Přesně to je query
basket: cílený metadatový vzor, ne jednotlivá osa. Dnešní skóre umí
členy jen SČÍTAT, takže dvě slabé shody dají totéž co jedna silná;
konjunkce (součin) uvnitř skóre chybí — a je to táž mechanika, kterou
už mají AND/OR/NOT v `query.py`, jen zatím nad výsledky, ne uvnitř.

## 20 · Metadata aktivují, ale nevybírají (2026-08-04)

Otázka J.: *„bylo něco aktivováno? bylo mezi tou aktivací, co jsme
hledali?"* — a je to správná otázka; přesnost@1 na ni neodpovídá.

Testbed r=2, párování BEZ slovních os (jen LEM/QLEM/ANCHOR/QANCHOR/
Polarity), 1 006 kandidátů:

| | jen metadata | se slovy |
|---|---|---|
| správná má nenulovou aktivaci | **33/33** | 33/33 |
| medián pořadí správné | 83 | 1 |
| v top 10 | 2/33 | 33/33 |

**Metadata aktivují spolehlivě** — hledané je pokaždé mezi aktivovaným,
v horních ~8 % pole. Co nedělají, je VÝBĚR: „být místem po slovese
v minulém čase" splňuje v korpusu ~80 dalších uzlů a pytel je od sebe
neodliší. Slova aktivaci nepřidávají (ta je stejná i bez nich), přidávají
ADRESU — řeknou, ve které z těch osmdesáti to je.

Dřívější čtení („jen meta neodpoví nikdy, tedy slova jsou nutná") bylo
špatné: neselhala aktivace, selhal výběr. Oprava směru podle J.:
*„chceme aktivace nad textem, kandidáta vybereme grafem"* — pole se
rozsvítí, ale vybírat má graf (vzor, role, vazby), ne součet v pytli.
Zvýšení W_FIT ani W_CENTER nepomohlo (0/33 při obou), protože oba jen
převáží členy uvnitř téhož součtu; výběr potřebuje jinou operaci, ne
jinou váhu — konjunkci vzoru, ne sumu.

## 21 · Kontext vět rozšiřuje dosah, ale ne výběr (2026-08-04)

Nová trénovací sada (120 otázek, z toho 12 mezivětných) poprvé dala
druhému r co obsluhovat. Nejdřív bylo nutné opravit metriku:
`reach_report` prohlížel jen okno slov uvnitř věty, takže mezivětná
otázka byla „mimo dosah" z definice a vliv r_sentences nešlo změřit
(vracel identická čísla pro r_věta 0/1/2 — vada měření, ne mechaniky).

Po opravě, korpusy r_slovo=2:

| r_věta | sada | v top 3 | mimo dosah | **vada** |
|---|---|---|---|---|
| 0 | mezivětné (4) | 0 | 4 | 0 |
| 1 | mezivětné (4) | 0 | 3 | **1** |
| 0 | jednovětné (71) | 4 | 39 | 28 |
| 1 | jednovětné (71) | 5 | **14** | **52** |
| 2 | mezivětné (4) | 0 | 2 | 2 |
| 2 | jednovětné (71) | 6 | **10** | **55** |

**Mechanismus dosahu funguje**: přítok sousední věty snížil „mimo
dosah" z 39 na 14, tedy ve 25 případech podnět do koše skutečně
dorazil. **Výběr ale ne**: vady vzrostly z 28 na 52 — skoro každá
otázka, kterou kontext přivedl do dosahu, hned propadla mimo top 3.
Čistý zisk v top 3 je jedna otázka na krok (4 → 5 → 6), zatímco dosah
se rozšíří o desítky (39 → 14 → 10 mimo dosah) a vady rostou s ním
(28 → 52 → 55). Poměr je tedy zhruba 1 : 25 ve prospěch kandidátů,
kteří se do hry dostanou a hned propadnou.

Diagnóza je táž jako v § 20, jen doložená z druhé strany: koš dostane
podnět, ale spolu s ním celý zbytek sousední věty, a součet v pytli
mezi tím nerozliší. Rozšiřovat dosah bez schopnosti vybírat vyrábí
kandidáty, ne odpovědi.

Poznámka k tvrdosti sady: jednovětné otázky z TRÉNOVACÍ sady jsou
mnohem tvrdší než etalon (28 vad proti 4), protože sítko z nich
vyhodilo všechno, co opisuje větu — zbyly samé parafráze. Etalon
dosud lichotil.
