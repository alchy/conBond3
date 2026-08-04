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
- **Měřené varianty členu setkání** (30 zodpověditelných otázek):
  vše 3/30 · jen metadata 2/30 · **jen slova 6/30** · vše s tématem ×3
  4/30. Směr „obsahová slova víc než gramatika" pomáhá, ale na 11/30
  nestačí.

Zadání členy skóre vypisuje, ale neurčuje, nad kterou reprezentací se
počítají a jak se normalizují; kód proto drží doslovný zápis ze zadání
(vše, včetně WORD=) a rozdíl se přiznává, místo aby se váhy ohýbaly,
dokud číslo nesedne. Kdo bude krok 3 dolaďovat, má tady změřený
výchozí bod a čtyři už vyloučené cesty.
