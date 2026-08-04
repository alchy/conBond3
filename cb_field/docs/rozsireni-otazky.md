# Konzistentní návrh: NN nad polem, sebe-rozšíření otázky a gaussovský výstup

Iterace nápadů J. z 2026-08-04 do jednoho návrhu, kriticky
posouzeného. **Nic z kroků § 6 není zapnuté** — čekají na
odsouhlasení (vzor handover-implementace.md). Co už zapnuté a změřené
JE, je označeno.

## 1 · Cíl a měřítko úspěchu

Cílem je **vybrat kandidátní věty, které obsahují odpověď**. Učení
generuje vazby s maximálním záchytem vhodných kandidátů; NN toto
zobecňuje. Úspěch posílení = **validní věta mezi kandidáty**
(`sentence_hit`, top věty podle větné aktivace). Zobecnění se měří
na **odložených 30 % otázek** (deterministický vrstvený los), jejichž
loss řídí odvolání epochy; každý běh tiskne vylosované příklady
otázka → odpověď. *(Zapnuto a ověřeno: kouřový test odvolal epochu,
kde tréninkový loss klesal a validační stoupl.)*

## 2 · Architektura NN v pojmech pole

**Invariant (J., neporušitelný): NN se NIKDY netrénuje nad jinými
daty než metadaty z vertikál.** Konkrétní slovo světa se k učení
dostane jedině tak, že se samo stane vertikálou (promoce do custom
slotu). Hlídá to pojistkový test a výčet `LEARN_PREFIXES`; platí
i pro každý budoucí učicí mechanismus (vrátí-li se Hebb nad
strukturou, podléhá témuž pravidlu).

| vrstva | realizace | stav |
|---|---|---|
| **vstup** | osy UDPipe + ≤328 custom slotů; promoce = transparentní chování: selekt (graf, různých²/hran) → **přegenerování celého korpusu** (koše nesou aktivaci samy) → teprve trénink | zapnuto; přejímky 27/27 |
| **vazby L** | učené hrany registru; **metadatový model** — konkrétní slovo vstupuje do učení výhradně promocí; gradient = kontrastivní krok nad SUROVÝMI pytli (šíření pytlů před gradientem zavrženo: 22,9M hran, 0,43 → 0,17) | zapnuto |
| **hloubka** | k kroků šíření v + v·L s tanh mezi kroky; k=2 se s učením skládá **nadaditivně** (B 0,43 · D 0,40 · E 0,50 na 3 517 větách); k=3 už ne | zapnuto jako parametr, výchozí k=1 |
| **výstup** | čtení aktivačního pole klouzavým oknem; navrženo **gaussovské vypíchnutí** (§ 5D) | návrh |

Jedno pole, jedny váhy: token / okno / věta jsou jen čtení téhož
pole v různém rozlišení — gaussovský výstup do té rodiny zapadá jako
další čtení, ne nová mechanika.

## 3 · Sebe-rozšíření otázky o vztahové entity

Otázka si **sama** zajistí rozšíření svého koše: „Kolik se smí jezdit
po dálnici?" → pod-otázka „Co je to dálnice?" → definice → složení
celé výměny do koše otázky. Tím se **posílí — aktivuje oblast kolem
textu otázky**, ne bod.

Definici si systém opatří třístupňově, od nejlevnějšího zdroje:

1. **korpus/graf** — definiční věta už v poli je (kopulární vzor);
2. **slovník / Wikipedie autonomně** — lookup slova; definice jde
   standardní cestou (parse → korpus se zdrojem `slovnik` → graf);
   po prvním stažení zůstává v korpusu → offline-first platí, síť
   jen při prvním setkání se slovem;
3. **dialog** — teprve když nezná ani slovník (`needs_context`,
   mechanika kroku 4).

Rozšířením grafu se pak **pohledem na okolí uzlu** (1–2 skoky)
objeví vztahové entity pro koš; koš pod-otázky a definiční věty se
PŘIČTE vahou `W_EXPAND` (vážený člen, ne filtr).

### Sondy (naměřeno 2026-08-04, korpus 12 258 vět)

- **Definice jsou k dispozici**: kopulární vzor dává **218
  definovaných lemmat** (hudba → systém, opera → druh, galaxie →
  systém); wikipedické úvody jsou systematický zdroj.
- **Živý lookup „Dálnice"**: po rozparsování definice visí na uzlu
  přímo `komunikace`, `povolený`, `zakázaný`; přes jeden skok
  `autostráda`, `pozemní`, `rychlostní`, `silnice`, `vozidlo`,
  `rychlost` — přesně entity, o které má expanze koš rozšířit.
- **Derivace (křest–křtít)**: překryv sousedství sám NESTAČÍ
  (zpěv×zpívat 0,09 ≈ náhodná dvojice 0,10; jen křtít×pokřtěný
  0,44); signál vznikne až složením se slovotvorným kmenem.
  Nadřazený pojem v sousedství není vůbec (dálnice×silnice 0,00) —
  hyponymie musí přijít z definičních vět.

### Smyčka expanze → promoce → trénink a její stabilizace

Rozšíření (definice, vazby na autostrádu, auta…) mění statistiku
grafu **poměrně značně** — po expanzi proto musí proběhnout **nová
identifikace vertikál a nový trénink** (atomický promoční cyklus,
který už existuje). Trénink se ale váže na ZMĚNU OSY: když selekt
vrátí týž cílový stav (rovnost stavů, žádný práh), cyklus
nepřeučuje. S počtem faktů se frekvence výměn slotů stabilizuje
a přeučování řídne samo.

**Naměřeno (2026-08-04):** výměny slotů na stejně velký přírůstek
korpusu klesají monotónně —

| vět v grafu | výměn slotů od minula |
|---|---|
| 3 064 | 124 (38 % osy) |
| 6 129 | 101 (31 %) |
| 9 193 | 77 (23 %) |
| 12 258 | **51 (16 %)** |

## 4 · Co je naměřeno vs. co je hypotéza

| tvrzení | stav |
|---|---|
| promoce vybírá obecné (jmen 3 %, pozice jmen sedí s referencí) | NAMĚŘENO |
| hloubka × učení nadaditivní (0,50) | NAMĚŘENO (3 517 vět) |
| plné šíření učicích pytlů škodí | NAMĚŘENO (zavrženo) |
| validační loss chrání zobecnění | NAMĚŘENO (kouřový test) |
| osa se s růstem faktů stabilizuje (přeučování řídne) | NAMĚŘENO (výměny 38 % → 16 % na přírůstek) |
| definice pokrývají potřebná slova | SONDA (218 lemmat; pokrytí vůči otázkám nezměřeno) |
| okolí uzlu = použitelné rozšíření koše | SONDA (dálnice); vliv na dosah NEZMĚŘEN |
| custom osy zlepšují samy o sobě | NEPOTVRZENO (C−B = 0) — hypotéza: projeví se až s expanzí a věnovaným učením |
| gaussovské čtení > harmonické 1/(1+d) | HYPOTÉZA — harmonický profil kdysi vyhrál nad plochým, Gauss ho musí porazit měřením |
| rozšíření koše zvýší záchyt kandidátních vět | HYPOTÉZA — hlavní přejímka kroku B |

## 5 · Kritické posouzení — napětí a jejich řešení

1. **Expanze × metadatový model.** Rozšíření přináší hlavně SLOVA
   (silnice, vozidlo), ale učení slova nevidí. Řešení konzistentní
   s pravidly: expanze slouží především PÁROVÁNÍ (záchyt kandidátů
   — přesně cílová metrika) a grafu; do učení z ní vstupuje
   metadatový stín + promované CUSTOM= osy. Pokud silnice/vozidlo
   stojí za učení, projdou promocí — brána je jedna a už existuje.
2. **Expanze × riziko záplavy.** Zaplavení pole už jsme jednou
   naměřili (22,9M hran). Pojistky: `W_EXPAND` (váha, ne větev),
   hloubka expanze 1, dosah v grafu 1–2 skoky s poklesem po skocích,
   protiváhy (přesnost × NEVÍM × dosah) a odvolání cyklu. Expanze
   se zapíná jako člen, který jde vypnout nezavoláním.
3. **Gauss × dnešní profil.** Oba jsou jádra čtení téhož pole.
   Harmonický profil 1/(1+d) je NAMĚŘENÁ hodnota (plochý profil
   škodil); Gauss nabízí učitelné σ a hladké vypíchnutí OBLASTI.
   Zavádět vedle, měřit vedle sebe (tokenové i větné čtení, § B5),
   nahradit jen po vítězství v číslech.
4. **Custom osy zatím nic nevydělaly** (C−B = 0). Kritický pohled:
   promoce dnes vybírá obecná slova, která pytel stejně nese přes
   WORD= v párování — přidaná hodnota custom osy je v (a) učení,
   kam WORD= nesmí, (b) stabilní dimenzi pro NN, (c) budoucí typy
   vztahů. Přejímkou promoce tedy nesmí být okamžitý zisk přesnosti,
   ale neškodnost + růst záchytu po zapojení expanze a učení.
5. **Málo otázek zůstává úzkým hrdlem.** 174 otázek na trénink
   + validaci je řád pod potřebou zobecnění; expanze signál násobí
   (otázka + definice), ale neřeší počet. Cesta: další dávky
   agentních otázek nad fixovanými korpusy (levné, opakovatelné)
   a dialog jako značený zdroj.
6. **Offline-first × autonomní lookup.** Vyřešeno konvencí: lookup
   jen při prvním setkání, výsledek fixovaný v korpusu (zdroj
   `slovnik`), reprodukovatelnost drží pořizovací skript a otisky.

## 6 · Kroky k odsouhlasení

- **A · Definiční hrany** — kopulární vzor jako vztahová vazba
  subjekt → predikátové jméno (zdroj `definice`) v registru.
  Přejímka: ~218 vazeb z korpusu; `dálnice → silnice` z dialogu;
  bez zapnutí žádná změna čísel.
- **B · Expanze koše otázky** — `expand_question` (tři zdroje
  definic, okolí uzlu 1–2 skoky, `W_EXPAND`). Přejímka: na etalonu
  vzroste `sentence_hit`/dosah, přesnost ani NEVÍM neklesnou; příklad
  z § 3 projde end-to-end.
- **C · Trénink nad rozšířeným košem** — učicí vztah je definován
  takto (J. 2026-08-04): do učení vstupuje **koš ROZŠÍŘENÉ otázky**
  (meta složené z více basketů — otázka + definice + okolí grafu),
  správná odpověď už v korpusu existuje jako **meta věty nebo vět,
  které fitují** (větná granularita, ne tokenové okno — dnešní
  kontrast oken se zdůrazněným středem se tím mění a musí se
  přeměřit). NN učení vytváří **vztah otázka(meta) → odpověď(meta)**
  za předpokladu **poziční nezávislosti dat v rámci pytle otázky**
  — pytel je množina, pořadí slov otázky nehraje roli (robustnost
  vůči parafrázi); pozice zůstává jen v tom, KTERÁ věta fituje,
  ne kde v ní. Kontrast: fitující věta (věty) proti nejlepší
  nefitující. Validace 30 % rozhoduje. Přejímka: validační
  `sentence_hit` po učení s expanzí ≥ bez ní; větný kontrast
  nesmí shodit tokenové čtení pod dnešek (obě čísla vedle sebe).
- **D · Gaussovský výstup** — čtení pole jádrem N(centrum, σ) vedle
  1/(1+d); σ kalibrovat. Přejímka: větná přesnost ≥ dnešní větné
  čtení; obě čísla vedle sebe.
- **E · Derivační vazby** — kmen × překryv sousedství jako vážená
  hrana (křtít–pokřtěný 0,44). Přejímka: neškodí; zvedne záchyt na
  otázkách přes slovní druh (křest/křtít).
- **F · Růst otázek** — agentní dávky otázek k fixovaným korpusům
  (formát s `answer_position`), cíl ≥ 500 otázek. Přejímka: validační
  křivky se stabilizují (menší rozptyl mezi semínky).
- **G · Smyčka expanze → promoce → trénink** — po každé dávce
  expanzí proběhne selekt vertikál; **přeučuje se jen při změně
  cílového stavu osy** (rovnost stavů, žádný práh — mění to sémantiku
  cyklu, proto k odsouhlasení). Cyklus hlásí počet výměn slotů;
  přejímka: klesající křivka výměn (naměřený trend 38 % → 16 %
  pokračuje) a žádné přeučení bez změny osy.

## 7 · Otevřená rozhodnutí (J.)

1. `W_EXPAND` a pokles váhy po skocích v grafu.
2. Pořadí zapínání: doporučuji A → B (jen párování) → D → C → E → F,
   každý krok s vlastní přejímkou a možností vrátit.
3. Dělení rozpočtu 328 slova × typy vztahů (trvá z handoveru).
4. Kdy smí lookup na síť (jen interaktivně? i při dávkovém běhu?).
