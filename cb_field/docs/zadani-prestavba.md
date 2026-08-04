# Zadání: cb_bond — jádro vazeb nad polem (stavba načisto)

Nový modul **cb_bond** je core systému. Staví se čistě, objektově,
podle README-MODULES.md, NAD modulem cb_field, který zůstává jako
hotový mezikrok (pole věty). Větev feature/field-templates je
referencí chování a zdrojem zmražených přejímek — kód se z ní
neopisuje. Všechny vzorky v tomhle zadání jsou REÁLNÁ data
a NAMĚŘENÉ hodnoty z reference.

## 1 · Proč se cb_bond staví

Systém má z otázky v přirozené češtině **vybrat kandidátní věty,
které obsahují odpověď** — nad korpusem, který roste (texty, slovník,
dialog), a s učením, které zobecňuje, ne memoruje.

Pole (cb_field) umí větu rozložit na vážené aktivace gramatiky
a slov. To na výběr věty nestačí, a každý důvod je naměřený:

- **Pytel ztrácí strukturu.** „Kde byl pokřtěn Ježíš?" — Jordán
  (2,088) a Galilej (2,068) jsou v pytli k nerozeznání. Strukturně
  je rozdíl triviální: Jordán visí na *pokřtěný*, Galilej na
  *přijít*. Proto graf faktů.
- **Osa roste se světem donekonečna**, NN chce pevnou vstupní
  dimenzi. Proto promoce: ≤328 custom slotů, o které slova soutěží
  statistikou grafu; s růstem korpusu se osa stabilizuje (výměny
  slotů 38 % → 16 % na stejný přírůstek).
- **Učení nad slovy memoruje** (párové mosty slovo↔slovo se mezi
  otázkami nepřenášejí — naměřeno). Proto invariant: učení jen nad
  metadaty vertikál; slovo jen promocí.
- **Otázka bývá chudší než odpověď** („Kolik se smí jezdit po
  dálnici?" nenese *rychlost*). Proto sebe-rozšíření otázky
  o definice a vztahy — aktivace OBLASTI kolem textu otázky.
- **Jeden token není odpověď** (krátké degeneráty „Máš ženu?"
  vyhrávaly normalizací). Proto gaussovské čtení: odpověď je věta,
  kde se souhlasné aktivace shlukují.
- **Co systém dělá, musí být vidět** — graf a jeho vizualizace jsou
  totéž (delty do viewBase2 při každé mutaci).

## 2 · Základní principy (neporušitelné)

1. **Učení výhradně nad metadaty z vertikál**; konkrétní slovo jen
   promocí do custom slotu (pojistkový test).
2. **Žádné filtry v datové cestě** — jen uzly, vážené hrany, vážené
   členy skóre; jediné řezy θ (NEVÍM) a ε (DOTAZ) na konci.
3. **Append-only osa + verze obsazení** custom slotů; čtení s cizí
   verzí je hlasitá chyba.
4. **Transparentní promoce**: selekt → přegenerování korpusu (koše
   nesou CUSTOM= samy) → teprve trénink; trénink jen při změně osy.
5. **Poziční nezávislost pytle otázky** (roli nese pád).
6. **Graf = jeho vizualizace** (emitor delt na každé mutaci).
7. **Offline-first fixace** v JSON; jméno souboru bez významové
   váhy; síť jen při prvním setkání se slovem.
8. **Determinismus** (semínka, žádný čas z hodin).
9. **Číslo bez protiváhy se neuvádí**; tokenové a větné čtení vedle
   sebe.

## 3 · Vztah k cb_field (mezikrok)

cb_field dorůstá o tři „polní" věci a pak API zamrzá: (1) `Corpus`
+ `corpusfile` + `regenerate()`, (2) registr: `set_custom_axes` /
`axis_version` / `snapshot()` / save v2, (3) `SentenceField`
aktivuje `CUSTOM=` nahlédnutím do osy (slovní vrstva). cb_bond na
cb_field importuje; na registru smí volat jen link/unlink/get_link/
spread/set_custom_axes/snapshot/restore. Parser vždy parametrem.

---

# 4 · Kroky stavby: objekty, metody, reálné vzorky

## Krok 1 · Corpus a fixovaný JSON (v cb_field)

**Objekty a metody** (jména: korpus je posloupnost polí; soubor je
fixace — proto `CorpusFile`, ne „dataset"):

    class Corpus:
        def add_sentence(sentence, document=None) -> SentenceField
        def add_text(text, parser, document=None) -> SentenceField
        def add_document(text, parser, document=None) -> list
        def regenerate() -> None
            # přestaví všechna pole z tokenů proti AKTUÁLNÍ ose
            # (bez parsování); dokumentové markery se zachovávají

    @dataclass CorpusBlock:   sentences: tuple; text: str | None
    @dataclass CorpusQuestion: text; sentence: int|None;
                               answer_lemma: str|None; answerable: bool
    @dataclass CorpusFile:    path; blocks; questions; corpus: str|None

    def load_corpus_file(path) -> CorpusFile      # validace formátu
    def add_to_corpus(corpus, corpus_file, parser) -> tuple  # pozice
    def build_corpus(paths, parser, r, r_sentences) -> Corpus
    def etalon_entries(corpus_file, positions) -> list
        # otázky ve tvaru etalonu vč. answer_position (zemní pravda
        # na úrovni VĚTY)

**Reálný vzorek** (korpus-001.json, zkráceno):

    {"format_version": 1, "language": "cs",
     "blocks": [
       {"topic": "Dálnice a silniční síť",
        "text": "…celý odstavec…",
        "sentences": [
          "Nejvyšší povolená rychlost na dálnici v Česku je sto
           třicet kilometrů za hodinu.",        ← globální index 12
          …]}],
     "questions": [
       {"text": "Kolik kilometrů za hodinu činí nejvyšší povolená
                 rychlost na dálnici v Česku?",
        "sentence": 12, "answer_lemma": "třicet", "answerable": true}]}

Co uvnitř: `add_to_corpus` parsuje blok VCELKU (pole `text` má
přednost — věta vytržená z odstavce se dělí jinak: reference
„In: Válka." + „cz [online]." se spojením rozpadla 6→5 vět) a rozpad
se rovná položkám počtem i zněním, jinak ValueError s adresou bloku.
Otázkový soubor s `"corpus": "korpus-201.json"` nese jen questions;
indexy se validují proti odkazovanému souboru. `etalon_entries`
vrátí `{"otazka": …, "odpoved_lemma": "třicet", "zodpoveditelna":
true, "answer_position": <pozice věty 12 v kombinovaném korpusu>}`.

**Přejímka:** převod 7 referenčních txt = 2 912 vět; rekonstrukce
z JSON dá týž otisk grafu (krok 2); rozjeté číslování se odmítne.

## Krok 2 · KnowledgeGraph (paměť faktů)

**Objekty a metody** (jména: graf ZNÁ fakta — proto KnowledgeGraph;
`illuminate` = rozsvítit, přesně to dělá):

    class NodeStat:
        occurrences: int      # kolikrát byl token uzlem
        edges: int            # hranové instance (s opakováním)
        neighbours: dict      # soused → počet
        distinct -> int;  ratio -> distinct/edges

    class KnowledgeGraph:
        def __init__(emit=None)                  # princip 6
        def add_sentence(sentence, source="text") -> int
        def node_stat(key) -> NodeStat
        def edges() -> tuple                     # (src,dst,deprel,w,source)
        def statistics() -> dict                 # jen uzly s hranou
        def select_verticals(limit=328) -> tuple # skóre distinct²/edges
        def illuminate(ranked_sentences, question_lemmas,
                       boost=2.0) -> dict        # {uzel: jas}

**Reálný vzorek — stavba** („V těch dnech přišel Ježíš z Nazareta
v Galileji a byl v Jordánu pokřtěn od Jana."):

    uzly (8):  den, přijít, Ježíš, Nazareto, Galilej, Jordán,
               pokřtěný, Jan          (V, těch, z, a, byl, od → nejsou:
                                       nese je gramatika; PRON také ne)
    hrany (7): Ježíš --nsubj--> přijít     den --obl--> přijít
               Nazareto/Galilej --obl--> přijít
               pokřtěný --conj--> přijít
               Jordán --obl--> pokřtěný    Jan --obl:arg--> pokřtěný
    NodeStat(přijít) = occurrences 1 · edges 5 · distinct 5 · ratio 1,0

**Reálný vzorek — select_verticals** (korpus 2 912 vět): rok
162 různých/191 hran → 162²/191 = **137,4** (1. místo); mít 131,6;
moci 96,3; hranice 328. místa **12,1**; Praha 19., Karel 35., Ježíš
45., Hrabal mimo; jmen 11 (3 %). Vrací se CELÝ cílový stav —
promoce je vratná.

**Reálný vzorek — illuminate** (kandidát = věta o křtu, váha 1,0;
lemata otázky {pokřtěný, Ježíš}, boost 2):

    rozsvícení: všech 8 uzlů = 1,0
    posílení:   pokřtěný ×2 = 2,0 · Ježíš ×2 = 2,0
    záře po hranách (podíl hrany na sousedových hranách):
      Jordán  = 1,0 + 2,0·(1/3) = 1,67   (soused pokřtěný, 3 hrany)
      Galilej = 1,0 + 1,0·(1/5) = 1,20   (soused přijít, 5 hran)
    → Jordán ZJASNÍ nad Galilejí — přesně rozdíl, který pytel nevidí

**Přejímka:** 16 074 hran · 5 695 lemmat s hranou · stupeň 5,6 ·
rok 0,85 · Ježíš 0,54; izolovaný uzel se nepočítá; illuminate:
Jordán > Galilej.

## Krok 3 · Matcher (párování)

**Objekty a metody** (jména: Matcher páruje; ScoreWeights jsou
páky, ne pravidla):

    @dataclass(frozen=True) ScoreWeights:
        center=2.0  cover=1.0  topic=1.0  given=-3.0  fit=0.0

    def saturate(v, links, steps):
        for _ in range(steps): v = tanh(v + v·L)   # tanh po KAŽDÉM kroku

    class Matcher:
        def __init__(corpus, *, spread_depth=2,
                     weights=ScoreWeights(), theta, epsilon)
        def given_axes(question) -> list     # WORD= řádků bez QLEM=
        def coverage(question) -> dict       # {osa: max tanh(spread(věty))}
        def match(question) -> MatchResult
        # pytle faktů cache na (růst, link_version, axis_version,
        # r, r_sentences, spread_depth); rozklad skóre LÍNÝ
        # (ScoreDecomposition — počítal se pro 58k kandidátů,
        # četl ho jen vítěz; 60 % času match)

    class MatchResult:
        outcome: answer|ask|silent ; candidates
        __and__/__or__/__invert__     # logika košů vahami:
        # AND = součin kladných / min (dvě záporná nesmí dát kladné),
        # OR = součet, NOT = obrácené znaménko; kdo & ~kdy

**Reálný vzorek — členy skóre** (otázka „Kde byl pokřtěn Ježíš?",
kandidát Jordán ve větě o křtu):

    skóre = cos(q̃, okno)                        setkání v uzlech
          + (2−1)·cos(q̃, střed)                 zdůraznění středu
          + 1·min(1,000; 0,604; 0,885) = 0,604  pokrytí: nejslabší
                                                DANÁ osa (být,
                                                pokřtěný, Ježíš)
          + 1·cos(slova q, slova věty)          téma
          − 3·cos(slova q, slova středu)        Jordán v otázce není
                                                → postih 0; kandidát
                                                „Ježíš" by ho dostal

**Reálný vzorek — hloubka** (otázka o dálnici, po kroku 7):

    k=1: {kolik→ANCHOR=quantity (axiom), dálnice→komunikace (definice)}
    k=2: navíc z komunikace na její vazby, z quantity do podkotev
    naměřeno: hloubka se s učením a promocí skládá NADADITIVNĚ
    (B 0,30 · D 0,33 · E 0,467); k=3 už rozmělňuje

**Přejímka (bitově):** 2 912 vět, k=1, bez učení → přesnost 0,3667 ·
mlčení 0 · dosah 10/19/1; coverage křtu: 1,000/0,604/0,885; mrtvá
osa (dálnice bez definice) = PŘESNÁ 0 — propast, ne škála.

## Krok 4 · AnswerField (čtení pole)

**Objekt a metody** (jméno: odpověď JE pole; token/okno/věta/vrchol
jsou jen čtení):

    class AnswerField:
        def __init__(result)
        def tokens() / spans(width=2) / sentences()
        def gaussian_peaks(sigma=1.5) -> [(věta, vrchol, index)]

**Reálný vzorek — proč Gauss** (jádro σ=1,5, normované: k0=0,267,
k1=0,213, k2=0,109):

    dlouhá věta, shluk aktivací 1,0+1,0+1,0 na pozicích 11–13:
        vyhlazený vrchol = 1·k1 + 1·k0 + 1·k1 = 0,69
    „Máš ženu?" — osamělá špička 1,5:
        vyhlazený vrchol = 1,5·k0 = 0,40
    → shluk poráží silnější špičku; průměrová normalizace volila
    naopak (naměřený degenerát na 12k korpusu)

Pozor na konvoluci: mode="same" vrací délku DELŠÍHO pole — u věty
kratší než jádro použít full + řez, jinak vrchol ukáže mimo větu.

**Přejímka:** test shluk 3×1,0 > špička 1,5; „Máš ženu?" nevyhrává.

## Krok 5 · ContrastiveTrainer (učení)

**Objekty a metody** (jména: trénink je kontrastivní; split hlídá
zobecnění; hit = zásah cíle):

    class ValidationSplit:  __init__(share=0.3, seed=328)
        def split(entries) -> (train, held_out)   # vrstvené
    class ContrastiveTrainer:
        LEARN_PREFIXES = (LEM=, QLEM=, ANCHOR=, QANCHOR=,
                          Polarity=, CUSTOM=)     # NIKDY WORD=
        def semantic_bag(sentence, rows) -> dict  # surový pytel
        def train(entries, max_epochs=10) -> TrainingReport
    def sentence_hit(result, lemma, top=3) -> bool
    class ThresholdCalibrator: calibrate(...) -> {theta, presnost,
                                                  mlceni, merit}

**Reálný vzorek — jeden učicí krok** (otázka „Kde byl pokřtěn
Ježíš?"):

    q_bag (meta, pozičně nezávislý):
        {QLEM=ADV:kde 0,7 · QANCHOR=space 0,7 · Polarity=Pos …}
        — WORD=PROPN:Ježíš v pytli NENÍ (invariant 1)
    fitující věta  = nejvýš položená s lemmatem Jordán
                     (answer_position má přednost, když je)
    soupeř         = nejvýš položená BEZ něj
    vrcholy (gauss): correct 0,69 · rival 0,55
    hinge: marže = 0,2·|0,55| = 0,11
           loss  = max(0, 0,11 + 0,55 − 0,69) = 0  → marže splněna,
           žádný krok (proto „korekcí 0" = skutečná konvergence)
    při porušení: gradient = q_bag ⊗ (bag(fitující) − bag(soupeře)),
    pytle CELÝCH vět bez zdůrazněného středu; Adam na hraně, meze ±1,
    axiomy chrání registr; hrana např. QLEM=ADV:kde → CUSTOM=…

**Reálný vzorek — validace řídí konec** (skutečný běh):

    epocha 1: loss 0,205 · valid 0,122 · věta V 28/50
    epocha 2: loss 0,414 · valid 0,378
    → epocha 2 ODVOLÁNA (validační loss stoupl), vazby vráceny

Mlčení: vítěz nezodpověditelné otázky se vede pod medián správných
vrcholů epochy. Zavržené (nezkoušet): šíření pytlů maticí (22,9M
hran, 0,43→0,17), WORD= v pytlích, kontrast tokenových oken.

**Přejímka:** pojistkový test invariantu; bez soupeřící věty se
neučí; kouřový test odvolání.

## Krok 6 · PromotionCycle (výměna vstupní vrstvy)

**Objekt a metody:**

    class PromotionCycle:
        def __init__(measure, retrain, limit=328)  # závislost parametrem
        def run(corpus, graph) -> CycleOutcome
            # accepted, before, after, axis_changes, retrained

**Reálný vzorek — průchod:**

    1. before = measure(corpus)          # {presnost:0,267, mlceni:0,…}
    2. snap = registry.snapshot()
    3. target = graph.select_verticals() # 328 klíčů, rok…dílo
       registry.set_custom_axes(CUSTOM=…)  → axis_version 0→1
       (beze změny osy: return accepted, retrained=False — naměřená
        stabilizace 38→31→23→16 % výměn na přírůstek)
    4. corpus.regenerate()               # transparentní aktivace:
       řádek „roku": {UPOS=NOUN, Case=Gen, …, WORD=NOUN:rok}
                   → {…, WORD=NOUN:rok, CUSTOM=NOUN:rok}
    5. retrain(corpus)                   # krok 5
    6. after = measure(corpus)
    7. kterákoli metrika klesla → restore(snap) + regenerate()
       (bit po bitu vč. verzí — cache z doby před cyklem znovu platí)

**Přejímka:** stará matice se odmítne použít; po uvolnění vertikály
nezůstanou hrany; rollback bit po bitu; bez promoce beze změny čísel.

## Krok 7 · RelationMiner + DefinitionResolver + QuestionExpander

**Objekty a metody** (jména: miner těží vztahy z dat; resolver
OPATŘUJE definici; expander rozšiřuje otázku):

    class RelationMiner:
        def mine_definitions(corpus, registry) -> int
        def mine_derivations(graph, registry, around=None) -> int
    class DefinitionResolver:
        def __init__(corpus, graph, parser, *, lookup, store)
        def resolve(word_key) -> corpus|dictionary|dialogue
    class QuestionExpander:
        def __init__(resolver, miner)
        def expand(question) -> Expansion    # {definice…, derivací n}

**Reálný vzorek — definice** („Gravitace je síla působící mezi
tělesy."): root *síla* NOUN v NOMINATIVU + nsubj *gravitace* + cop
*je* → vazba `WORD=NOUN:gravitace → WORD=NOUN:síla` (0,7,
definition). Lokativní kopula („Muž byl ve vězení" — root v lokálu)
definice NENÍ. Na 12 258 větách: **94 vazeb** (foton→částice,
elektromotor→stroj, Isaac→fyzik).

**Reálný vzorek — resolver, slovo dálnice:**

    1. korpus: definiční vazba není → dál
    2. Wikipedie: „Dálnice (ze slov dálková silnice, zastarale
       autostráda) je rychlostní komunikace pro motorová silniční
       vozidla…" → parse → korpus (zdroj dictionary) → graf →
       vazba dálnice→komunikace; heslo se PŘIPÍŠE do store JSON
       (offline-first: příště platí bod 1)
    3. (kdyby nebylo) dialog: needs_context

**Reálný vzorek — derivace, cíleně:** kmen bez diakritiky ≥5 znaků
a ≥75 % kratšího lemmatu × překryv sousedství:

    rychlost(8) × rychlostní(10): kmen 8 → strength 8/10 = 0,8
    váha = 0,7·(0,8/2 + překryv/2) = 0,28   (překryv 0 — kmen sám)
    naléhavý × náledí: kmen po složení diakritiky jen 4 → ŽÁDNÝ pár
    plošně NIKDY: 11 268 vazeb v L stálo baseline 3,3 bodu;
    around={kmeny slov otázky a její expanze}

**Přejímka:** 94 definic; dálnice→komunikace živě; rychlost–
rychlostní vznikne po ingestu definice; kámen↔kamení ano,
naléhavý↔náledí ne.

## Krok 8 · Responder (dialogová vrstva)

**Objekt a metody:**

    class Responder:
        def __init__(matcher, graph, expander=None)
        def gaps(question) -> list        # mrtvé osy (přesné nuly)
        def reply(question, *, expand=False) -> Reply
            # odpovídá VŽDY; Reply(best, outcome, missing)
        def append_context(text, parser) -> SentenceField
            # věta uživatele standardní cestou, zdroj dialog

**Reálný vzorek — celý průběh** (naměřeno do puntíku):

    q: Jak je omezena rychlost na dálnici?
       coverage: být 1,000 · omezený 0,604 · rychlost 0,604 (fyzika!)
                 · na 1,000 · dálnice 0,000  ← jediná mezera
    a: needs_context, missing=[WORD=NOUN:dálnice]  (ptá se na JEDNU
       věc — rychlost zná)
    u: Dálnice je silnice pro motorová vozidla, kde je stanovena
       rychlost na 130 km/h.
    → append_context: korpus +1 věta (dialog) · graf +9 hran
      (dálnice→silnice nsubj, rychlost→stanovený, 130→stanovený…)
    q znovu: dálnice 0,604 → outcome answer

**Přejímka:** přesně tenhle průběh; nezodpověditelná osa = přesná 0.

## Krok 9 · GraphMirror (viewBase2)

**Objekt a metody:**

    class GraphMirror:
        def __init__(window)              # GraphWindow viewBase2
        def emit(delta) -> None           # předává se KnowledgeGraph

**Reálný vzorek — delty:**

    {"op":"node", "id":"PROPN:Jordán"}
    {"op":"edge", "src":"PROPN:Jordán", "dst":"ADJ:pokřtěný",
     "deprel":"obl", "source":"text"}       # smyčky se NEkreslí
                                            # (viewBase je odmítá)
    {"op":"style", "id":"PROPN:Jordán", "glow":1.67}
    metadata uzlu: sousede = "ADJ:pokřtěný (obl)" · stupen = 1

Instalace VÝHRADNĚ `pip install 'viewbase @ git+https://github.com/
alchy/viewBase2#subdirectory=python'`; verze frontendu se ověřuje
otiskem bundle v index.html (starý projekt viewBase je k ledu —
jiné API, jednou už podvrhl starou generaci). Spuštění:
`./run-python -m cb_bond.graphview` (:8080).

## Krok 10 · BenchmarkProtocol (měření)

**Objekt:** `BenchmarkProtocol.run()` — ramena nad TÝMŽ korpusem:

    A baseline → B trénink → D hloubka (čistý) → C promoční cyklus
    (rozhodne sám) → E hloubka nad C → F kalibrované θ
    + vylosované příklady (semínko 328) + uložení přijatého stavu

**Reálný vzorek — výstup** (12 258 vět, 240 otázek supervize):

    A 0,267 · B 0,300 · D 0,333 · C 0,300 PŘIJATO · E 0,467
    F (θ=2,494): 0,233 / mlčení 1,00     ← provozní bod je krok K1
    věta v kandidátech: trénink 46/115 · validace 24–28/50
    příklad: ✓ „Kolem čeho obíhá Měsíc?" → Země [answer]
             věta: „Měsíc obíhá kolem Země."

Supervize: trenink-otazky-korpusy.jsonl (120) + otazky-201/202
(2×60, corpus-reference → answer_position přes offsety); etalon 40
NIKDY do tréninku.

---

## 5 · Zmražené přejímky (souhrn — nová stavba je musí zopakovat)

| co | hodnota |
|---|---|
| graf 2 912 vět | 16 074 hran · 5 695 lemmat · stupeň 5,6 · rok 0,85 · Ježíš 0,54 |
| select_verticals | rok 137,4 · hranice 12,1 · Hrabal mimo · jmen ≤10 % |
| Matcher baseline k=1 | 0,3667 · 0 · 10/19/1 — bitově |
| coverage křtu | 1,000 / 0,604 / 0,885; mrtvá osa přesná 0 |
| mine_definitions 12 258 vět | 94 (gravitace→síla, foton→částice) |
| gaussian_peaks | shluk 0,69 > špička 0,40 |
| trainer | odvolání epochy dle validace; bez soupeřící věty nic |
| PromotionCycle | rollback bit po bitu; beze změny osy nepřeučuje |
| dialog dálnice | mezera právě dálnice; po doplnění 0,604 → answer |
| větev E | ≥ 0,467 · 0 · 10 · 0; věta na validaci ≥ 24/50 |

Zavržené (nezkoušet znovu): šíření učicích pytlů maticí · WORD=
v učení · plošné derivace · kmen 3–4 znaky · promoce poměr×n/(n+1)
· práh detekce mezery.

## 6 · Data k převzetí a definice hotového

Data: data-persistent/korpus/101–107, 201, 202, 301–326 (mimo git,
fetch + ZDROJ.md); tests/data/korpus/001–003 + otazky-201/202;
trenink JSONL 120; etalon 40 (nikdy trénink). Hotovo = unittest přes
./run-python bez služby (atrapy, zmražené tokeny), přejímky § 5
prošly, service/api oddělení, format_version všude, měřicí reporty
s protiváhami, dokumentace jádra (vzor vetev-e.md). K1–K8
(handover-kvalita.md) až NAD hotovým cb_bond.
