# Větev E pro vývojáře — promoce + učení + hloubka

Provozní konfigurace systému (rozhodnutí J. 2026-08-05). Tenhle
dokument vysvětluje, co se s polem děje od textu k odpovědi, co
přesně dělají tři vrstvy větve E a jak je z kódu použít. Všechna
čísla jsou naměřená (docs/mereni-nn.md).

## 1 · Cesta od textu k odpovědi

    text ──parse──► věty ──koše──► pole (matice vah)
                                     │
    graf faktů ◄──obsahová slova─────┤
        │ selekt vertikál            │
        ▼                            ▼
    PROMOCE ──přegenerování──► koše s CUSTOM= osami
                                     │
    otázka ──koš──► šíření po vazbách (HLOUBKA k)
                                     │
    UČENÍ (metadata) ──vazby──► matice L
                                     │
                 kosinová skóre ──► gaussovské vrcholy ──► věta

## 2 · Hloubka šíření k (`matching.SPREAD_STEPS`, výchozí 2)

Hloubka ŠÍŘENÍ AKTIVACE PO VAZBÁCH registru (matice L) při
párování: kolik skoků po hranách vazeb (axiomy, naučené hrany,
definice) aktivace udělá, než se koš otázky porovná s koši vět.
Každý krok je `v ← tanh(v + v·L)` — tanh po KAŽDÉM kroku (P-B).

Příklad, otázka „Kolik se smí jezdit po dálnici?":

    surový koš:  {QLEM=kolik, WORD=NOUN:dálnice, LEM=ADP:po, …}
    k=1 přidá:   QANCHOR=quantity → ANCHOR=quantity   (axiom)
                 WORD=dálnice → WORD=komunikace       (definice)
    k=2 přidá:   z komunikace dál na její vazby,
                 z ANCHOR=quantity do podřízených kotev

Platí pro OBĚ strany (otázku i pytle faktů v `_fact_bags`) — obě
musejí žít v témže poli. k=1 je jednovrstvá síť (jen přímí sousedé);
k=2 je druhá vrstva nad touž maticí — naučené hrany jsou
jednoskokové (otázka→typ) a druhý skok je zřetězí s vazbami faktů.
Proto se k=2 skládá s učením NADADITIVNĚ (samo +6,7 b, s učením
a promocí +20 b); k=3 už signál rozmělňuje. Volání:
`match(question, corpus, spread_steps=1)` pro staré chování.

Nezaměňovat s ostatními poloměry:

| parametr | čeho je to hloubka | výchozí |
|---|---|---|
| `SPREAD_STEPS` (k) | skoky po VAZBÁCH matice L při párování | 2 |
| `Corpus.r` | okno koše ve SLOVECH kolem středu | 1–2 |
| `Corpus.r_sentences` | přítok sousedních VĚT do koše | 0 |
| okolí uzlu při expanzi | skoky po hranách GRAFU FAKTŮ | 1–2 |
| hloubka expanze | generace pod-otázek („Co je to X?") | 1 |

## 3 · Promoce (`graph.py`, `promotion.py`)

Graf faktů (uzel = `UPOS:lemma` obsahového slova, hrana = závislost)
měří každému uzlu poměr různých sousedů k hranám. Skóre
`různých²/hran` odděluje nositele TVARU (rok 137, mít 132 — skoro
každá hrana jinam) od konkrétního světa (Hrabal — opakované hrany
do týchž míst). Prvních ≤328 uzlů obsadí CUSTOM= sloty registru.

**Transparentní chování:** po selektu se PŘEGENERUJE celý korpus
(`Corpus.regenerate()`) — každý koš, jehož token je promovaný, nese
aktivaci `CUSTOM=…` sám (slovní vrstva; METADATA zůstává bezeslovná).
Stejnou aktivaci dostane transparentně i otázka a dialogová věta,
protože ji dělá stavba pole nahlédnutím do osy registru. TEPRVE
POTOM jde učení. Příklad koše po promoci `NOUN:rok`:

    řádek „roku":  {UPOS=NOUN, Case=Gen, …, WORD=NOUN:rok,
                    CUSTOM=NOUN:rok}      ← přibylo přegenerováním

Celý cyklus je atomický a vratný:

    from cb_field.promotion import promotion_cycle
    outcome = promotion_cycle(corpus, graph, measure=…, retrain=…)
    # snapshot → selekt → set_custom_axes (axis_version++)
    # → regenerate → retrain → measure → horší? → návrat bit po bitu
    # outcome["preuceni"] == False, když se osa nezměnila (stabilizace:
    # výměny slotů klesají 38 % → 16 % na přírůstek korpusu)

Přeobsazení sloupce hlídá `registry.axis_version` — nese ho cache
matic vět, pytle faktů i soubor na disku; čtení s cizí verzí osy je
hlasitá chyba, ne tichá záměna významu.

## 4 · Učení (`learning.py`)

**Invariant (neporušitelný): NN se NIKDY netrénuje nad jinými daty
než metadaty z vertikál.** Konkrétní slovo se k učení dostane jedině
promocí (CUSTOM=). Učicí pytel nese kotvy, Polarity, LEM/QLEM
zavřených tříd a CUSTOM= — WORD= nikdy (hlídá pojistkový test).

**Větný kontrast:** učicí vztah je `otázka(meta) → věta(meta)`.
Fitující věta (answer_position z etalonu, jinak nejvýš položená věta
s očekávaným lemmatem) se učí PROTI nejlepší nefitující; obě se
čtou gaussovským vrcholem (§ 5) a jejich pytle jsou CELÉ věty bez
zdůrazněného středu — **poziční nezávislost**: pozice zůstává jen
v tom, KTERÁ věta fituje, ne kde v ní odpověď leží (roli nese pád,
čeština si to může dovolit). Bez soupeřící věty se neučí.

**Zobecnění hlídá validace:** 30 % otázek se odloží (deterministický
vrstvený los, semínko 328) a jejich loss řídí odvolání epochy —
epocha, která zlepšila trénink a zhoršila validaci, se vrací.
Úspěch posílení = `sentence_hit`: validní věta mezi top kandidáty.

    from cb_field.learning import train_on_etalon
    stats = train_on_etalon(corpus, entries, parser)
    # stats["epochy"][i]: loss (trénink), loss_valid, veta_trenink,
    # veta_validace, ticho, korekci, hran

Mechanika kroku: kontrastivní hinge s relativní marží na vrcholech,
Adam na hraně, meze ±1, axiomy chrání registr. Mlčení se učí vedením
vítěze nezodpověditelné otázky pod medián správných vrcholů.

## 5 · Výstup: gaussovské čtení (`query.gaussian_peaks`)

Na každém kandidátu sedí zvon N(centrum, σ); zvony se sčítají
a věta se čte podle nejvyššího VRCHOLU vyhlazeného pole. Shluk
souhlasných aktivací tak poráží osamělou špičku — krátká věta
s jedním silným tokenem („Máš ženu?") už nevyhrává normalizací.
Token/span/věta/gauss jsou jen různá ČTENÍ téhož pole.

## 6 · Vztahové vazby a expanze otázky (`relations.py`, `dialog.py`)

- `definition_links`: kopulární vzor s nominativem („Gravitace je
  síla…") → vazba `WORD=gravitace → WORD=síla`, zdroj `definice`
  (94 čistých na korpusu). Expanzi pak dělá šíření (k) — žádný
  zvláštní kód.
- `derivation_links(around=…)`: kmen (≥5 znaků, ≥75 % kratšího
  lemmatu, bez diakritiky) × překryv sousedství. JEN CÍLENĚ kolem
  otázky — plošné nasazení stálo baseline 3,3 b (zavrženo měřením).
- `expand_question(question, corpus, graph, parser)`: pro jmenné osy
  otázky opatří definici (korpus → Wikipedie s fixací na disk →
  dialog) a spáruje cílené derivace; koš rozšíří šíření po nových
  vazbách.

## 7 · Jak větev E spustit

    ./run-python -m cb_field.measure_nn      # plný protokol, ukládá
                                             # přijatý stav E do
                                             # data-persistent/registr-e.json
    ./run-python -m cb_field.graphview       # živý graf (viewBase2,
                                             # :8080; delty za běhu)

Výchozí čísla větve E (12 258 vět, 240 otázek supervize): přesnost
0,467 · mlčení 0 · dosah 10 · vad 0; s tokenovým θ 0,233/1,00 —
kalibrace na větné úrovni je krok K1 handoveru kvality.
