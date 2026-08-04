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

**Sedí přesně.** Pokrytí otázky o křtu 1,000 / 0,604 / 0,885 a mrtvá
osa jako **přesná nula** (`WORD=NOUN:dálnice` v biblicko-fyzikálním
korpusu). Souhlasí i celá pětice ze vzorku kroku 8. Čísla dávají
smysl: `tanh(0,7) = 0,604` je jeden výskyt slovní osy, `tanh(1,4) =
0,885` dva.

Sedí i přejímka S1: čtení top-50 vět dá **touž přesnost** jako čtení
celého korpusu (2 912 vět) — předvýběr nic neztrácí.

**Dvě čísla, ne jedno.** Přejímkové 0,3667 je SPRÁVNĚ **s řezem**
(top-1 lemma a zároveň outcome „odpoved"); totéž **bez řezu** je
0,4667 (14/30), rozdíl jsou tři otázky spadlé do DOTAZ/NEVÍM. Kdo
měří s `theta=0`, poměřuje se se 14/30.

**Kde se přesnost ztrácela (vyřešeno).** Původní stavba hledala chybu
v členu *setkání* a sedm jeho variant skončilo mezi 2/30 a 6/30.
Ablace ukázala, že to bylo hledání na špatném místě — nosné jsou
`given` a `cover`, ne `meet`:

| konfigurace | reference | tady |
|---|---|---|
| plné skóre | 14/30 | 11/30 |
| bez tématu (topic=0) | 12/30 | 11/30 |
| bez zdůraznění středu (center=1) | 9/30 | 8/30 |
| bez pokrytí (cover=0) | 7/30 | 9/30 |
| bez postihu daného (given=0) | **0/30** | **0/30** |
| jen setkání | **0/30** | **0/30** |

Obě nulové hodnoty sedí přesně, a jsou to ty nejtvrdší: **bez postihu
−3 za střed, jehož slovo otázka sama uvádí, vyhrává vždycky ozvěna
otázky.** Proto se žádná varianta setkání nemohla k referenci
přiblížit — chyba byla jinde, než kam mířilo hledání.

**Co po doplnění kroku 3b zbývá.** Přesnost stoupla z 3/30 na 11/30
proti referenčním 14/30. Šest chyb je „pořadí 1" — správná odpověď
těsně druhá (např. „Kolem čeho obíhá Země?": měsíc 2,25 před slunce
2,13). Rozdíl je tedy v měřítku členů, ne v jejich skladbě.

Poslední zavřená mezera byla vlastní nedůslednost: harmonická váha
1/(1+|o|) existuje proto, aby okno NEMĚLO hranu, ale ořezával jsem ho
na ±r, čímž se hrana vrátila. Okno přes celou větu dá 11/30 místo
10/30. Ořez na ±3 dá totéž co celá věta — dozvuk za třetí pozicí už
váží málo, ale hrana tam být nesmí.

## Krok 5: co učení udělalo a co ne

Naměřeno na 2 912 větách, 120 otázkách supervize (validace 30 %,
semínko 328), etalon 40 stranou:

| | před učením | po učení |
|---|---|---|
| přesnost@1 | 11/30 | 11/30 |
| věta v top-3 | 20/30 | **21/30** |

Učení tedy zvedlo VĚTNÉ čtení, ne tokenové — což dává smysl, protože
učicí vztah je otázka(meta) → věta(meta). Validační loss klesla 0,1194
→ 0,1193 a hned se ustálila: po první epoše je marže u většiny otázek
splněna, takže korekce ustanou samy (21 korekcí, 920 hran na epochu).

**Pozor na míchání dvou sad.** V etalonu jsou DVĚ otázky, které stojí
i v tréninkové sadě: „Kdo pokřtil Ježíše?" a „Kolem čeho obíhá
Slunce?". Etalon má být od tréninku oddělený (§ 7 zadání), takže je to
vada dat, ne kódu — přejímka kroku 5 ji hlásí a končí nenulově.
Naměřených čísel se to zatím nedotýká (obě otázky systém stejně
netrefí), ale s lepším skórováním by je nadhodnocovalo.


## Tázací slovo do tématu a postihu nepatří

Nedůslednost, kterou odhalil rozbor úplně špatných odpovědí: z pokrytí
jsem interpunkci vyloučil, ale ze slovního pytle otázky (členy `topic`
a `given`) ne — a s ní tam zůstávalo i tázací slovo.

Důsledek byl naměřitelný: `topic` odměňoval věty, které samy obsahují
„kdo" nebo „kde" — v Markově evangeliu tedy OTÁZKY, ne odpovědi.
„Kdo pokřtil Ježíše?" vyhrávalo „A kdo ti dal moc, abys to činil?",
„Kdo je autorem Války s mloky?" vyhrávalo „Vím, kdo jsi.".

Po opravě (`Matcher.question_words` = táž množina os jako `given_axes`)
se **přesnost nezměnila** (11/30 před i po) a změnili se tři vítězové
z osmi špatných, žádný na správného. Ablace ale sedí líp: bez pokrytí
9/30 proti dřívějším 4/30 (reference 7/30).

Opravuje se to i tak: dvě pravidla pro totéž („co otázka tvrdí") jsou
o jedno víc, než kolik jich má být, a příště by se rozešla.

## Když učení nedává smysl, podívej se na váhy

`./run-python cb_bond/scripts/trenink-vah.py` — vypíše, mezi
kterými vrstvami se učilo a které hrany o tom rozhodly. Návod ke čtení
je v `trenink-vah.md`; nejkratší verze: **znaménko je důležitější
než velikost**, `QLEM → ANCHOR` má být mezi prvními třemi, a `WORD=`
tam nesmí být vůbec.

Dvě naměřené pasti, které tenhle pohled odhalil:

**Odvolání epochy bez tolerance neučí vůbec.** Epocha srazila trénink
0,1144 → 0,0950 a validaci zhoršila o 0,00006 — a odvolala se. Šest
stotisícin je šum v poslední cifře, ne zhoršení. Odvolání proto snáší
1 % relativně (`ContrastiveTrainer.tolerance`).

**Cache matcheru musí nést `link_version`, ne počet vazeb.** Učení mění
VÁHY existujících hran, takže počet zůstane stejný a cache by dál
vracela zastaralé pytle — validace by se pak měřila na stavu, který už
neplatí. Zadání to předepisuje (`cache na (růst, link_version,
axis_version, …)`) a chybělo to.


## Okno přes celou větu je kvadratické — pamatuj si řádky

Harmonické okno sahá přes celou větu, takže naivně se každý řádek
maskuje znovu pro každého kandidáta: u dvacetislovné věty 400 průchodů
místo 20. Naměřeno profilem — **68 % času `match()`**. `Matcher` proto
drží pytle řádků po větách (`_radky_vety`) a maže je s cache.

Po zapamatování: **31 ms na otázku místo 78**, tedy 2,5×. Celý běh
učení (6 epoch × 85 otázek + validace) spadl pod minutu.


## Nejužší místo systému je PŘEDVÝBĚR, ne učení

Naměřeno na 120 tréninkových otázkách (2 912 vět):

| | počet |
|---|---|
| lemma odpovědi JE někde v korpusu | 117 / 120 |
| věta s ním se dostane do top-50 | **37 / 117 (32 %)** |
| do top-200 | 58 / 117 (50 %) |
| do top-1000 | 68 / 117 (58 %) |

Data tedy nechybí — chybí je najít. Dokud se správná věta nedostane
mezi kandidáty, nemá trenér co kontrastovat a otázka se do učení
nezapočítá vůbec (viz `skorovano`/`preskoceno`).

Změřené varianty řazení předvýběru (věta v top-50 ze 117):

| varianta | zásah |
|---|---|
| kosinus celého saturovaného pytle (původní) | 31 |
| **jen slova, která otázka TVRDÍ** | **37** |
| pokrytí — nejslabší daná osa | 9 |
| pokrytí + půl tématu | 37 |

Pokrytí samo je nepoužitelné: u drtivé většiny vět je nula (je to
propast, ne škála), takže neřadí, jen dělí na dvě hromady. Zavedena
varianta podle tvrzení — týž princip jako u členů `topic` a `given`.

Širší shortlist pomáhá učení víc než přesnosti: top-200 zdvojnásobí
počet otázek, ze kterých se dá učit (20 → 38 z 85), a větné čtení
zvedne o bod (21 → 22/30), ale přesnost@1 se nehne a běh je 3× delší.
