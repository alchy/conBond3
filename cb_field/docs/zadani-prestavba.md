# Zadání přestavby — od main k větvi E, načisto a objektově

Zadání pro vývojáře: postavit funkcionalitu větve E (promoce + učení
+ hloubka; viz vetev-e.md) ČISTĚ od stavu posledního commitu na main
(`b447090` — pole věty: SentenceField, koše, aktivace, append-only
registr s vazbami, kukátko). Platí README-MODULES.md beze zbytku:
service/api oddělení, závislosti parametrem (§ 3), unittest bez běžící
služby (§ 13), format_version na uložených datech (§ 14), měření
s protiváhou. Větev feature/field-templates slouží jako REFERENCE
CHOVÁNÍ a zdroj zmražených přejímek — kód se z ní neopisuje.

## 0 · Co na main je a smí se použít

- `SentenceField` (věta → řádky aktivací → koše → matice; registr
  parametrem, otázkovost, přenos směru předložky).
- `VerticalRegistry` (append-only osa, vážené vazby s ochranou
  axiomů, `spread` = v + v·L, vectorize/unvectorize, save/load v1).
- `service.py` (expand_token, activations, kotvy, is_question),
  kukátko na pole (:42301).
- `cb_udpipe` (parser s trvalou cache), `cb_logger`.

## 1 · Neporušitelné invarianty (platí pro každý nový řádek)

1. **NN se NIKDY netrénuje nad jinými daty než metadaty z vertikál.**
   Konkrétní slovo vstupuje do učení výhradně promocí do custom
   slotu. Hlídá pojistkový test (řádky slova NESOU, pytel je
   nepropustí).
2. **Žádné filtry v datové cestě** — rozvoj = nový uzel, vážená
   hrana nebo vážený člen skóre (klidně záporný). Jediné řezy jsou
   θ (NEVÍM) a ε (DOTAZ) na konečném skóre.
3. **Append-only + verze osy.** Sloupec registru znamená totéž
   navždy; jedinou výjimkou je přeobsazení custom slotů, které zvedá
   `axis_version` — nese ji cache matic vět, pytle faktů i soubor na
   disku a čtení s cizí verzí je HLASITÁ chyba (tichá záměna významu
   je nejnebezpečnější vada návrhu).
4. **Transparentní promoce:** po selektu vertikál se přegeneruje
   celý korpus a koše nesou aktivaci CUSTOM= samy; teprve potom
   učení. Žádná zvláštní větev pro otázku či dialog — aktivaci dělá
   stavba pole nahlédnutím do osy.
5. **Poziční nezávislost pytle otázky** — pytel je množina; pozice
   zůstává jen v tom, KTERÁ věta fituje (roli nese pád).
6. **Cokoli se děje v grafu, se projeví v jeho vizualizaci** —
   každá mutace i vysvícení jde emitorem delt (viewBase2); bez
   diváka se delta zahodí, systém nestojí.
7. **Offline-first fixace:** korpus i slovníkové definice žijí ve
   fixovaných JSON souborech; síť jen při prvním setkání se slovem.
   Jméno souboru je neprůhledný identifikátor (žádné mapy klíčované
   doménou).
8. **Determinismus:** žádná náhoda bez semínka, žádný čas z hodin;
   dvojí zavolání = týž výsledek.
9. **Číslo bez protiváhy se neuvádí** (přesnost × NEVÍM × dosah;
   tokenové a větné čtení vedle sebe).

## 2 · Cílová architektura (moduly a zodpovědnosti)

    corpus.py      Corpus: věty nad sdíleným registrem; r, r_sentences,
                   documents (hranice kontextu); regenerate()
    corpusfile.py  fixovaný JSON: CorpusFile/CorpusBlock/CorpusQuestion,
                   load/validace/build_corpus/etalon_entries
    graph.py       FactGraph + NodeStat; promote_verticals; light_up;
                   emitor delt
    matching.py    pytle, saturace, hloubka k, členy skóre, masky,
                   ScoreDecomposition (líný rozklad), match()
    query.py       čtení pole: sentence_activation, span, gaussian_peaks,
                   AND/OR/NOT
    learning.py    kontrastivní učení nad metadaty, split_etalon,
                   sentence_hit, kalibrace θ
    promotion.py   atomický promoční cyklus
    relations.py   definiční hrany, cílené derivace, ensure_definition
    dialog.py      fact_gaps, reply, append_context, expand_question
    graphview.py   projekce do viewBase2 (instalace VÝHRADNĚ
                   z github.com/alchy/viewBase2#subdirectory=python)
    measure_*.py   spustitelné přejímky (graf, dialog, nn)

Vazby: corpus → field/registry; matching → corpus; learning →
matching+query; promotion → graph+corpus+registry; dialog →
matching+relations; nic necyklí. Parser a registr se VŽDY předávají
parametrem.

## 3 · Etapy stavby — každá s zmraženou přejímkou

Referenční čísla jsou naměřená na fixovaných datech; slouží jako
přejímka nové stavby („když se čísla rozejdou, je chyba
v implementaci, ne v konceptu").

### E1 · Corpus a fixovaný JSON

    class Corpus:
        def __init__(self, registry=None, r=1, r_sentences=0)
        def add_sentence(self, sentence, document=None) -> SentenceField
        def add_text(self, text, parser, document=None) -> SentenceField
        def regenerate(self) -> None    # přestaví pole z tokenů
                                        # proti aktuální ose (bez parsování)

Formát JSON (format_version 1): blocks[{topic, text?, sentences[]}],
questions[{text, sentence|null, answer_lemma|null, answerable}],
volitelně corpus="jméno.json" (otázky k cizímu souboru). Klíčové
kontrakty:
- blok se parsuje VCELKU (text má přednost před join položek — věta
  vytržená z odstavce se dělí jinak); rozpad se rovná položkám
  počtem i zněním, jinak hlasitá chyba s adresou;
- globální index věty = pořadí přes bloky; blok = dokument.

**Přejímka E1:** převod referenčních 7 txt korpusů dá 2 912 vět;
rekonstrukce z JSON bitově táž (otisk grafu níže); validátor odmítne
soubor s rozjetým číslováním.

### E2 · Graf faktů

    CONTENT_UPOS = {NOUN, PROPN, VERB, ADJ, ADV, NUM}   # bez PRON
    class FactGraph:
        def __init__(self, emit=None)   # emitor delt (§ invariant 6)
        def add_sentence(self, sentence, source="text") -> int
        # uzel „UPOS:lemma"; hrana závislý→hlava jen mezi obsahovými;
        # NodeStat: occurrences, edges (instance), neighbours, ratio
        def node_stats(self) -> dict
        def stats(self) -> dict         # jen uzly s hranou

**Přejímka E2 (korpus 2 912 vět):** 16 074 hranových instancí;
5 695 různých lemmat s hranou (5 727 klíčů UPOS:lemma); stupeň 5,6;
průměr různých 4,6; rok 162/191/0,85 · Ježíš 60/111/0,54 · mít
185/260 · říci (UPOS-klíč) 178/308. Izolovaný uzel se nepočítá;
PRON není uzel.

### E3 · Promoce a atomický cyklus

    def promote_verticals(graph, limit=328) -> tuple
        # skóre = různých²/hran; CELÝ cílový stav; deterministicky
    registry.set_custom_axes(target)    # jen CUSTOM=…; uvolněné sloupce
        # = díry (None; key() a unvectorize na díře = ValueError);
        # vertikála odchází I S HRANAMI; axis_version++ při změně
    registry.snapshot() / restore(s)    # bit po bitu vč. verzí

    def promotion_cycle(corpus, graph, measure, retrain, limit=328):
        before = measure(corpus); snap = registry.snapshot()
        changes = registry.set_custom_axes(CUSTOM+promote_verticals(...))
        if beze změny osy: return prijato=True, preuceni=False
        corpus.regenerate()             # transparentní aktivace CUSTOM=
        retrain(corpus); after = measure(corpus)
        if kterákoli metrika klesla: restore(snap); corpus.regenerate()

Aktivace CUSTOM= při stavbě pole: token, jehož `CUSTOM=UPOS:lemma`
je v registru, dostane tuto vertikálu do SLOVNÍ vrstvy (METADATA
zůstává bezeslovná) s vahou slovní vertikály.

**Přejímka E3:** top 328 obsahuje rok/mít/moci/stát/začít/dílo;
Hrabal mimo; jmen ≤ 10 %; hranice (2 912 vět) 12,1; stará matice se
odmítne použít; po uvolnění nezůstanou hrany; rollback bit po bitu;
bez promoce se nezmění žádné číslo. Stabilizace: výměny slotů na
stejný přírůstek korpusu klesají (naměřeno 38→31→23→16 %).

### E4 · Párování (matching)

Členy skóre kandidáta (kosiny, −1…+1; váhy = páky):

    skóre = cos(q̃, okno) + (W_CENTER−1)·cos(q̃, střed)
          + W_COVER · min přes DANÉ osy otázky z tanh(spread(věta))
          + W_TOPIC · cos(slova q, slova věty)
          + W_GIVEN · cos(slova q, slova středu)      # záporná páka
    (W_CENTER=2, W_COVER=1, W_TOPIC=1, W_GIVEN=−3, W_FIT=0)

    def saturate(v, L, steps=SPREAD_STEPS):   # SPREAD_STEPS = 2 (větev E)
        for _ in range(steps): v = tanh(v + v·L)   # tanh po KAŽDÉM kroku

Dané osy = WORD= řádků bez QLEM= (tázací osa se nekryje, ta se
odpovídá). Pytle faktů se cachují na (len, link_version,
axis_version, r, r_sentences, steps); profil okna 1/(1+d); přítok
sousedních vět W_CONTEXT/(1+d) jen uvnitř dokumentu. Rozklad skóre
(top_nodes) je LÍNÝ (ScoreDecomposition — počítal se pro 58k
kandidátů a četl ho jen vítěz; ~60 % času match). MATCH_PREFIXES =
WORD/LEM/QLEM/ANCHOR/QANCHOR/Polarity/CUSTOM (bez PUNCT).

**Přejímka E4 (2 912 vět, k=1, bez učení):** přesnost 0,3667 ·
mlčení 0 · dosah 10/19/1 — bitově. Ježíš question coverage: být
1,000 · pokřtěný 0,604 · Ježíš 0,885.

### E5 · Čtení pole (query)

    sentence_activation(result)         # kladné aktivace / počet
    gaussian_peaks(result, sigma=1.5)   # zvon N(centrum,σ) na kandidátu,
        # věta = nejvyšší VRCHOL vyhlazeného pole; full-konvoluce
        # s řezem (věta kratší než jádro!)
    AND/OR/NOT                          # váhami: součin kladných /
                                        # min, součet, obrácené znaménko

**Přejímka E5:** shluk 3×1,0 v dlouhé větě porazí špičku 1,5
v krátké (průměrová normalizace preferuje degenerát — dokumentovat
testem); „Máš ženu?" nevyhrává.

### E6 · Učení

    LEARN_PREFIXES = (LEM=, QLEM=, ANCHOR=, QANCHOR=, Polarity=, CUSTOM=)
    def split_etalon(entries, share=0.3, seed=328)  # vrstvené, determ.
    def sentence_hit(result, lemma, top=3)          # věta v kandidátech
                                                    # (gaussovské čtení)
    def train_on_etalon(corpus, entries, parser, ...):
        # VĚTNÝ kontrast: fitující věta (answer_position, jinak nejvýš
        # položená s lemmatem) × nejlepší nefitující; vrcholy gauss;
        # pytle CELÝCH vět bez středu; hinge s rel. marží 0,2·|soupeř|;
        # Adam na hraně, meze ±1, axiomy chrání registr;
        # mlčení: vítěz nezodpověditelné pod medián správných vrcholů;
        # VALIDAČNÍ loss (30 %) řídí odvolání epochy;
        # bez soupeřící věty se neučí
    def calibrate_theta(corpus, entries, parser)    # jen trénink; K1:
                                                    # přejít na věty

Zavržené varianty (nezkoušet znovu): šíření učicích pytlů maticí
(22,9M hran, 0,43→0,17); WORD= v pytlích s útlumem synonym; plošné
derivace v L (−3,3 b).

**Přejímka E6:** pojistkový test invariantu 1; kouřový test — epocha,
která zlepší trénink a zhorší validaci, se odvolá.

### E7 · Vztahové vazby a expanze

    definition_links(corpus, registry)      # kopulární vzor, root
        # NOUN/PROPN v NOMINATIVU + nsubj + cop → WORD=subj → WORD=pred,
        # zdroj definice, váha 0,7 (lokativní kopula NENÍ definice)
    derivation_links(graph, registry, around=None)
        # kmen (bez diakritiky, ≥5 znaků a ≥75 % kratšího lemmatu)
        # × překryv sousedství; váha 0,7·(kmen/2+překryv/2); JEN cíleně
    ensure_definition(word_key, corpus, graph, parser, lookup, store)
        # korpus → Wikipedie (fixace do store JSON) → dialog
    expand_question(question, corpus, graph, parser)
        # jmenné dané osy → definice; derivace kolem kmenů otázky;
        # rozšíření koše pak dělá šíření (jen matice)

**Přejímka E7:** 94 definičních vazeb na korpusu (gravitace→síla,
foton→částice); dálnice→komunikace ze živého lookupu; po ingestu
definice vznikne rychlost–rychlostní; žádná plošná derivace.

### E8 · Dialog

    fact_gaps(question, corpus)     # mrtvá osa = PŘESNÁ nula (propast,
                                    # ne škála — práh není potřeba)
    reply(question, corpus, graph)  # odpovídá VŽDY; needs_context+missing
    append_context(text, ...)       # věta uživatele standardní cestou,
                                    # zdroj dialog

**Přejímka E8:** „Jak je omezena rychlost na dálnici?" hlásí právě
WORD=NOUN:dálnice (rychlost zná z fyziky); po doplnění pokrytí 0,604
a východisko odpoved; v grafu hrany se zdrojem dialog.

### E9 · Vizualizace (viewBase2)

    FactGraph(emit=viewbase_emitter(window))
    # delty: node / edge (bez smyček — viewBase je odmítá) / style
    # (glow); uzly nesou metadata sousede („ADJ:pokřtěný (obl)"),
    # stupen; light_up: věty rozsvítí uzly, lemata otázky znásobí jas
    # rozsvícených, jeden krok záře po hranách (Jordán > Galilej)
    ./run-python -m cb_field.graphview     # :8080; verzi frontendu
    # ověřovat otiskem bundle v index.html

### E10 · Měřicí protokol

measure_nn: ramena A (baseline) / B (učení) / D (hloubka na čistém)
/ C (promoční cyklus — rozhodne sám) / E (hloubka nad C) / F
(kalibrované θ); tiskne vylosované příklady (semínko 328) a ukládá
přijatý stav E (registr s verzí osy). Supervize = JSONL sada +
otázkové soubory s corpus-referencí (offsety → answer_position).

**Cílová čísla větve E (12 258 vět, 240 otázek):** E ≥ 0,467 ·
mlčení 0 · dosah 10 · vad 0; s tokenovým θ 0,233/1,00 (provozní bod
je krok K1). Věta v kandidátech na validaci ≥ 24/50.

## 4 · Data (převzít, nefixovat znovu)

- fixované korpusy: data-persistent/korpus/korpus-101…107 (převod
  původních), 201 vesmír, 202 hudba, 301…326 NZ — mimo git, pořizují
  fetch skripty (ZDROJ.md, licence);
- tests/data/korpus: korpus-001…003 (vlastní texty s otázkami),
  otazky-201/202 (60+60 s indexy vět);
- tests/data: trenink-otazky-korpusy.jsonl (120), etalon-otazky-
  korpusy.jsonl (40 — NIKDY do tréninku), testbed.

## 5 · Definice hotového

- unittest přes ./run-python, bez běžící služby (atrapy parseru,
  zmražené tokeny v testech — vzor stávajících test_*);
- všechny přejímky E1–E10 prošly na fixovaných datech;
- měřicí skripty zapisují reporty do docs/ s protiváhami;
- žádný modul necyklí, závislosti parametrem, format_version na
  všem uloženém;
- dokumentace: príručka větve (vzor vetev-e.md) + tenhle dokument
  aktualizovaný o odchylky (zapsané, ne zamlčené).

## 6 · Co NEstavět (vědomě odloženo)

Kroky K1–K8 handoveru kvality (kalibrace θ/ε na větách, hygiena
korpusu, expanze v reply, ≥500 otázek, promoce×žánr, křivky σ/limit,
DeriNet, typy vztahů) — přijdou až nad čistou stavbou.
