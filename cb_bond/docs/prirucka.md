# Příručka cb_bond — otázky ze stavby a pasti

## Otázky, které při stavbě padly

**Jak se pozná, že je pravidlo uzlu a hrany správně?** Zmraženými
přejímkami § 6 zadání. Na 2 912 větách se zkoušely čtyři varianty
a jen jedna sedla na 16 074 hran a 5 695 lemmat současně: uzly
NOUN/PROPN/VERB/ADJ/ADV/NUM (i zájmenná příslovce), hrana jen mezi
přímými sousedy, smyčka do součtu ano — do sousedství ne. Ostatní
varianty daly 15 202 až 16 233 hran. Čísla nejsou dekorace; jsou to
testy.

**Proč „5 695 lemmat", a ne 5 727 uzlů?** Zadání počítá **různá
lemmata**, ne klíče `UPOS:lemma`. Totéž lemma ve dvou slovních druzích
(*stát* jako VERB i NOUN) jsou dva uzly, ale jedno lemma. Přejímkový
skript to počítá stejně — kdo měří uzly, dostane 5 727 a bude si
myslet, že se něco pokazilo.

**Proč emitor, a ne metoda `draw()`?** Jádro nesmí mít I/O vrstvu
(README-MODULES § 1). Emitor je funkce v konstruktoru: v testu je to
`list.append`, v provozu `GraphMirror`. Graf o kreslítku neví nic.

**Proč `illuminate` počítá záři z ROZSVÍCENÍ, ne z průběžného jasu?**
Kdyby se zářilo z už zjasněných uzlů, bylo by to šíření do hloubky
a záleželo by na pořadí průchodu. Jeden průchod z rozsvícení je
deterministický a odpovídá výpočtu v zadání (Jordán 1,67, Galilej
1,20).

## Pasti

**Uzel s hranou ≠ uzel.** `nodes()` vrací i izolované uzly,
`statistics()` jen ty s hranou. Průměrný stupeň počítaný přes
`nodes()` vyjde tiše nižší — a nikdo si toho nevšimne, protože číslo
pořád vypadá rozumně.

**Hrany se sčítají s opakováním.** Přidat tutéž větu dvakrát znamená
dvojnásobek hranových instancí, ale týž počet různých sousedů — a tedy
poloviční `ratio`. Je to záměr (opakování je informace), ale kdo staví
graf z korpusu s duplicitami, dostane jiné skóre promoce.

**Zájmenná příslovce jsou v cb_field zavřená a tady otevřená.** Kdo
klasifikaci sjednotí „pro pořádek", rozejde graf s přejímkou o 121
hran. Je to vědomý rozdíl (koncepce § 3), ne nedopatření.

**Skript přejímky potřebuje data mimo git.** Korpusy 101–107 leží
v `cb_field/data-persistent/korpus/` (licence, viz ZDROJ.md). Bez nich
skript skončí s kódem 2 a řekne to — netváří se, že prošel.

## Krok 3: co sedí a co ne

**Sedí přesně.** Pokrytí otázky o křtu 1,000 / 0,604 / 0,885 —
hodnoty ze zadání do třetího místa. Mrtvá osa je **přesná nula**
(`WORD=NOUN:dálnice` v biblicko-fyzikálním korpusu), takže detekce
mezery pro krok 8 stojí na propasti, ne na prahu. Ověřeno i na vzorku
kroku 8: být 1,000 · omezený 0,604 · rychlost 0,604 · na 1,000 ·
dálnice 0,000 — celá pětice souhlasí.

Čísla dávají smysl: `tanh(0,7) = 0,604` je jeden výskyt slovní osy,
`tanh(1,4) = 0,885` dva, saturovaná jednička mnoho.

**NESEDÍ přesnost.** Zadání má baseline 0,3667 (11/30 etalonu),
naměřeno **0,10 (3/30)**. Mlčení 0 souhlasí. Co je o rozdílu známo:

- **Není to předvýběrem vět.** Při čtení CELÉHO korpusu (top_k = 2 912)
  vychází táž přesnost 3/30, přestože věta s lemmatem odpovědi je
  v shortlistu ve 30/30 případů. Ztrácí se ve skórování, ne v recallu.
- **Není to hloubkou ani pokrytím.** Pokrytí sedí a k=1 je zadané.
- **Není to definicí metriky.** Ověřeno proti referenci: přesnost je
  `SPRÁVNĚ / zodpověditelné`, kde SPRÁVNĚ znamená, že lemma nejlepšího
  TOKENU se rovná `answer_lemma` — přesně tak, jak se měří tady.
  (Reference to má v `evaluate.evaluate_corpus`; potvrzuje to i tabulka
  „přesnost@1 (zodpověditelné) 28/33 = 0,85" v jejím měření.)
- **Měřených sedm variant** (30 zodpověditelných otázek):

  | varianta členu setkání | přesnost |
  |---|---|
  | pytel okna, všechny osy (dnešní kód) | 3/30 |
  | pytel okna, jen metadata | 2/30 |
  | pytel okna, jen slovní osy | **6/30** |
  | pytel okna, téma ×3 | 4/30 |
  | maximum přes ŘÁDKY okna | **6/30** |
  | jen střed, okno vůbec | 4/30 |
  | čtení celého korpusu (bez předvýběru) | 3/30 |

Zadání členy skóre vypisuje, ale neurčuje, nad kterou reprezentací se
počítají a jak se normalizují; kód proto drží doslovný zápis ze zadání
(vše, včetně WORD=) a rozdíl se přiznává, místo aby se váhy ohýbaly,
dokud číslo nesedne.

**Kudy dál.** Nejlepší dvě varianty (6/30) míří stejným směrem —
obsahová slova a řádková struktura váží víc než sečtený pytel všech
os. Chybějící díl je nejspíš v tom, co zadání nepíše: jak přesně se
skládá pytel otázky a jak se členy normalizují. Než se to doplní,
nemá smysl na krok 3 stavět kalibraci θ (krok 10) — měřila by se
špatná křivka.
