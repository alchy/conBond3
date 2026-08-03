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
