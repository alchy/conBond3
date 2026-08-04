# Zadání: cb_bond — jádro vazeb nad polem (stavba načisto)

Nový modul **cb_bond** je core systému. Staví se čistě, objektově,
podle README-MODULES.md, NAD modulem cb_field, který zůstává jako
hotový mezikrok (pole věty). Větev feature/field-templates je
referencí chování a zdrojem zmražených přejímek — kód se z ní
neopisuje.

## 1 · Proč se cb_bond staví

Systém má z otázky v přirozené češtině **vybrat kandidátní věty,
které obsahují odpověď** — nad korpusem, který roste (texty, slovník,
dialog), a s učením, které zobecňuje, ne memoruje.

Pole (cb_field) umí větu rozložit na vážené aktivace gramatiky
a slov. To na výběr věty nestačí, a každý důvod je naměřený:

- **Pytel ztrácí strukturu.** „Kde byl pokřtěn Ježíš?" — Jordán
  (2,088) a Galilej (2,068) jsou v pytli k nerozeznání, protože obě
  jsou „místo v téže větě". Strukturně je rozdíl triviální: Jordán
  visí na *pokřtěný*, Galilej na *přijít*. Proto **graf faktů**.
- **Osa roste se světem donekonečna.** Slovních vertikál přibývá
  s každým textem; NN potřebuje **pevnou vstupní dimenzi**. Proto
  **promoce**: omezený počet custom slotů, o které slova soutěží
  statistikou grafu, s přepočtem při růstu korpusu (a naměřenou
  stabilizací — výměny slotů řídnou).
- **Učení nad slovy memoruje.** Párové mosty slovo↔slovo se mezi
  otázkami nepřenášejí (naměřeno); model, který se učí jen nad
  metadaty vertikál, přenáší TYP otázky na nové otázky. Proto
  **invariant metadat** a promoce jako jediná brána slova do učení.
- **Otázka bývá chudší než odpověď.** „Kolik se smí jezdit po
  dálnici?" nenese *rychlost* ani *povolený*. Proto **expanze**:
  otázka si sama opatří definice (korpus → slovník → dialog)
  a vztahové vazby, čímž aktivuje OBLAST kolem svého textu.
- **Jeden token není odpověď.** Krátké degenerátní věty vyhrávaly
  normalizací; odpověď je věta, kde se souhlasné aktivace SHLUKUJÍ.
  Proto **gaussovské čtení pole** (vrchol vyhlazené aktivace).
- **Co systém dělá, musí být vidět.** Graf a jeho vizualizace jsou
  totéž — každá mutace se projeví deltou (viewBase2). Bez toho se
  chování nedá posuzovat jinak než čísly.

## 2 · Základní principy (neporušitelné)

1. **Učení výhradně nad metadaty z vertikál.** Konkrétní slovo
   vstupuje do učení jen promocí do custom slotu. (Pojistkový test:
   řádky slova nesou, učicí pytel je nepropustí.)
2. **Žádné filtry v datové cestě.** Rozvoj = uzel, vážená hrana,
   vážený člen skóre (klidně záporný). Jediné řezy: θ (NEVÍM)
   a ε (DOTAZ) na konečném skóre.
3. **Append-only osa + verze obsazení.** Sloupec znamená totéž
   navždy; výjimkou jsou custom sloty — jejich přeobsazení zvedá
   verzi osy, kterou nese každá cache i soubor; čtení s cizí verzí
   je hlasitá chyba (tichá záměna významu je nejhorší vada).
4. **Transparentní promoce.** Po selektu vertikál se přegeneruje
   celý korpus; koše nesou aktivaci CUSTOM= samy — stejnou cestou
   otázka i dialogová věta. Teprve potom trénink; trénink jen při
   změně osy.
5. **Poziční nezávislost pytle otázky.** Pytel je množina (roli
   nese pád); pozice zůstává jen v tom, KTERÁ věta fituje.
6. **Graf = jeho vizualizace.** Každá mutace i vysvícení jde
   emitorem delt; bez diváka se delta zahodí, systém nestojí.
7. **Offline-first fixace.** Korpusy, otázky i slovníková hesla
   žijí ve fixovaných JSON souborech; síť jen při prvním setkání.
   Jméno souboru je neprůhledný identifikátor.
8. **Determinismus.** Žádná náhoda bez semínka, žádný čas z hodin.
9. **Číslo bez protiváhy se neuvádí.** Přesnost × mlčení × dosah;
   tokenové a větné čtení vedle sebe.

## 3 · Vztah k cb_field (mezikrok)

cb_field zůstává extrakční vrstvou a dorůstá jen o tři věci, které
jsou bytostně „pole":

1. `Corpus` + `corpusfile` — pole více vět nad sdíleným registrem,
   fixovaný JSON (bloky s původním textem, globální indexy vět,
   otázky s odkazem `corpus`), `Corpus.regenerate()`;
2. `VerticalRegistry.set_custom_axes()` + `axis_version` +
   `snapshot()/restore()` + save/load v2 — limitovaná část osy
   s verzí obsazení;
3. `SentenceField` — transparentní aktivace `CUSTOM=` při stavbě
   (nahlédnutím do osy; slovní vrstva, METADATA zůstává bezeslovná).

cb_bond na cb_field výhradně importuje; parser i registr se předávají
parametrem (§ 3, § 4 politiky). Na registru smí cb_bond volat jen
`link/unlink/get_link/spread/set_custom_axes/snapshot/restore`.

## 4 · Objektový návrh cb_bond

Pojmenování anglicky a vypovídající; docstringy česky. Metakód =
podpisy a kontrakty, ne implementace. Konstruktor vždy dostává
závislosti (corpus, parser, registry) parametrem.

### 4.1 · KnowledgeGraph — paměť faktů

    class KnowledgeGraph:
        """Uzly = UPOS:lemma obsahových slov (bez PRON), hrany =
        závislosti závislý→hlava mezi obsahovými uzly, se zdrojem
        text|dialog|dictionary. Každá mutace jde emitorem delt."""
        def __init__(self, emit: Callable | None = None)
        def add_sentence(self, sentence, source="text") -> int
        def node_stat(self, key) -> NodeStat      # occurrences, edges,
                                                  # neighbours, ratio
        def node_stats(self) -> dict
        def edges(self) -> tuple                  # (src, dst, deprel,
                                                  # weight, source)
        def statistics(self) -> GraphStatistics   # jen uzly s hranou
        def select_verticals(self, limit=328) -> tuple
            """Cílový stav custom slotů: skóre = distinct²/edges,
            deterministicky, celý stav (ne přírůstek)."""
        def illuminate(self, ranked_sentences, question_lemmas,
                       boost=2.0) -> dict
            """Vysvícení: věty rozsvítí uzly, lemata otázky znásobí
            jas rozsvícených, jeden krok záře po hranách. Emituje
            style delty."""

### 4.2 · Matcher — párování otázky s korpusem

    @dataclass(frozen=True)
    class ScoreWeights:
        center: float = 2.0     # zdůraznění středu (vlastní kosinový člen)
        cover: float = 1.0      # min přes dané osy — mohutnost důkazu
        topic: float = 1.0      # obsahový překryv s celou větou
        given: float = -3.0     # postih za odpověď slovem otázky
        fit: float = 0.0        # kotvy středu (přiznaná slepá ulička)

    class Matcher:
        """Čistě váhové párování: každý token korpusu kandiduje.
        Pytle se šíří k kroky po vazbách (tanh po každém kroku)
        a cachují na (růst, link_version, axis_version, r, k)."""
        def __init__(self, corpus, *, spread_depth: int = 2,
                     weights: ScoreWeights = ScoreWeights(),
                     theta: float = THETA, epsilon: float = EPSILON)
        def match(self, question) -> MatchResult
        def coverage(self, question) -> dict      # {osa: max přes věty};
                                                  # mrtvá osa = přesná 0
        def given_axes(self, question) -> list    # WORD= bez QLEM=

    class MatchResult:
        outcome: str            # answer | ask | silent
        candidates: list        # Candidate se skóre a LÍNÝM rozkladem
        def __and__(self, other) -> "MatchResult"   # AND: součin/min
        def __or__(self, other)  -> "MatchResult"   # OR: součet
        def __invert__(self)     -> "MatchResult"   # NOT: −skóre

### 4.3 · AnswerField — čtení téhož pole v různých rozlišeních

    class AnswerField:
        """Token, okno, věta i gaussovský vrchol jsou jen čtení
        jednoho pole — nic se nefiltruje."""
        def __init__(self, result: MatchResult)
        def tokens(self) -> list
        def spans(self, width=2) -> list
        def sentences(self) -> list               # normalizovaná aktivace
        def gaussian_peaks(self, sigma=1.5) -> list
            """Zvon na každém kandidátu; věta = nejvyšší vrchol
            vyhlazeného pole (shluk poráží osamělou špičku).
            Konvoluce full+řez (věta kratší než jádro)."""

### 4.4 · ContrastiveTrainer — učení metadatového vztahu

    class ValidationSplit:
        def __init__(self, share=0.3, seed=328)
        def split(self, entries) -> (train, held_out)   # vrstvené,
                                                        # deterministické

    class ContrastiveTrainer:
        """Učí vztah otázka(meta) → věta(meta): fitující věta
        (answer_position, jinak nejvýš položená s lemmatem) proti
        nejlepší nefitující, obě gaussovským vrcholem, pytle CELÝCH
        vět. Hinge s relativní marží, Adam na hraně, meze ±1, axiomy
        chrání registr. Mlčení: vítěz nezodpověditelné pod medián
        správných vrcholů. Validační loss řídí odvolání epochy."""
        LEARN_PREFIXES = ("LEM=", "QLEM=", "ANCHOR=", "QANCHOR=",
                          "Polarity=", "CUSTOM=")     # NIKDY WORD=
        def __init__(self, corpus, parser, *,
                     split: ValidationSplit = ValidationSplit(),
                     eta=0.01, margin_ratio=0.2)
        def train(self, entries, max_epochs=10) -> TrainingReport
        def semantic_bag(self, sentence, rows) -> dict   # surový pytel,
                                                         # jen LEARN osy

    class TrainingReport:
        epochs: list      # loss, validation_loss, sentence_hits_train,
                          # sentence_hits_validation, silence, edges
        def converged(self) -> bool

    class ThresholdCalibrator:
        """θ/ε na trénovací sadě (nikdy na etalonu); merit =
        přesnost + mlčení. K1: kalibrovat na větných vrcholech."""
        def calibrate(self, corpus, entries, parser) -> Calibration

    def sentence_hit(result, lemma, top=3) -> bool
        """Úspěch posílení: validní věta mezi top gaussovskými."""

### 4.5 · PromotionCycle — atomická výměna vstupní vrstvy

    class PromotionCycle:
        """selekt → zápis custom slotů → přegenerování korpusu →
        trénink → měření s protiváhami → přijmout / vrátit bit po
        bitu. Beze změny osy se nepřeučuje (stabilizace)."""
        def __init__(self, measure: Callable, retrain: Callable,
                     limit=328)
        def run(self, corpus, graph) -> CycleOutcome
            # CycleOutcome: accepted, before, after, axis_changes,
            # retrained

### 4.6 · RelationMiner a DefinitionResolver — vztahové vazby

    class RelationMiner:
        def mine_definitions(self, corpus, registry) -> int
            """Kopulární vzor: root NOUN/PROPN v NOMINATIVU + nsubj
            + cop → vazba WORD=subjekt → WORD=predikát, zdroj
            definition, váha 0,7. Lokativní kopula definice není."""
        def mine_derivations(self, graph, registry,
                             around=None) -> int
            """Kmen (bez diakritiky, ≥5 znaků a ≥75 % kratšího
            lemmatu) × překryv sousedství; váha 0,7·(stem/2 +
            overlap/2). VÝHRADNĚ cíleně (around) — plošné nasazení
            zavrženo měřením (−3,3 b)."""

    class DefinitionResolver:
        """Tři zdroje definice, od nejlevnějšího: korpus (vazba už
        je) → slovník/Wikipedie (fixace do store, offline-first) →
        dialog. Stažené heslo jde standardní cestou: parse → korpus
        (zdroj dictionary) → graf → definiční vazba."""
        def __init__(self, corpus, graph, parser, *,
                     lookup=wikipedia_lookup, store: Path | None)
        def resolve(self, word_key) -> str    # corpus|dictionary|dialogue

### 4.7 · QuestionExpander a Responder — dialogová vrstva

    class QuestionExpander:
        """Sebe-rozšíření otázky: pro jmenné dané osy opatří definice
        (resolver) a spáruje cílené derivace kolem kmenů otázky;
        rozšíření koše pak dělá šíření po nových vazbách."""
        def __init__(self, resolver: DefinitionResolver,
                     miner: RelationMiner)
        def expand(self, question) -> Expansion
            # Expansion: definitions {osa: zdroj}, derivations: int

    class Responder:
        """Odpovídá VŽDY; mezeru ohlásí (needs_context + missing);
        věta uživatele jde stejnou cestou jako každý text."""
        def __init__(self, matcher: Matcher, graph: KnowledgeGraph,
                     expander: QuestionExpander | None = None)
        def gaps(self, question) -> list      # mrtvé osy (přesné nuly)
        def reply(self, question, *, expand=False) -> Reply
        def append_context(self, text, parser) -> SentenceField

### 4.8 · GraphMirror — živé zrcadlo (viewBase2)

    class GraphMirror:
        """Překlad delt KnowledgeGraph na objektové API viewBase2
        (ensure_node / ensure_edge bez smyček / update_node). Uzly
        nesou metadata sousedů s deprel a stupeň. Instalace VÝHRADNĚ
        z github.com/alchy/viewBase2#subdirectory=python; verze
        frontendu se ověřuje otiskem bundle."""
        def __init__(self, window)            # GraphWindow viewBase2
        def emit(self, delta) -> None         # předává se KnowledgeGraph

    # spuštění: ./run-python -m cb_bond.graphview   (:8080)

### 4.9 · BenchmarkProtocol — měření

    class BenchmarkProtocol:
        """Ramena nad týmž korpusem: baseline / trénink / hloubka /
        promoční cyklus / složení / kalibrované θ. Supervize = JSONL
        + otázkové soubory s corpus-referencí (offsety →
        answer_position). Tiskne vylosované příklady (semínko);
        ukládá přijatý stav (registr s verzí osy)."""
        def run(self) -> BenchmarkReport

## 5 · Zmražené přejímky (naměřeno; nová stavba je musí zopakovat)

| co | hodnota |
|---|---|
| KnowledgeGraph na 2 912 větách | 16 074 hran · 5 695 lemmat s hranou · stupeň 5,6 · rok 162/191/0,85 · Ježíš 60/111/0,54 |
| select_verticals | top 328 s rok/mít/moci/stát/začít/dílo · Hrabal mimo · jmen ≤ 10 % · hranice 12,1 |
| Matcher baseline (2 912 vět, k=1, bez učení) | přesnost 0,3667 · mlčení 0 · dosah 10/19/1 — bitově |
| coverage („Kde byl pokřtěn Ježíš?") | být 1,000 · pokřtěný 0,604 · Ježíš 0,885; mrtvá osa = přesná 0 |
| mine_definitions (12 258 vět) | 94 vazeb (gravitace→síla, foton→částice); lokativy nic |
| gaussian_peaks | shluk 3×1,0 porazí špičku 1,5; „Máš ženu?" nevyhrává |
| trainer | epocha zlepšující trénink a zhoršující validaci se odvolá; bez soupeřící věty se neučí |
| PromotionCycle | rollback bit po bitu; beze změny osy nepřeučuje; stará matice se odmítne |
| větev E (12 258 vět, 240 otázek) | přesnost ≥ 0,467 · mlčení 0 · dosah 10 · vad 0; věta v kandidátech na validaci ≥ 24/50 |
| dialog (dálnice) | mezera právě WORD=NOUN:dálnice; po doplnění 0,604 a odpoved |

Zavržené varianty (nezkoušet znovu): šíření učicích pytlů maticí
(22,9M hran, 0,43→0,17) · WORD= v učicích pytlích (i s útlumem) ·
plošné derivace v L (−3,3 b) · kmen 3–4 znaky (19–33k šumu) ·
promoce skórem poměr×n/(n+1) (saturuje) · práh pro detekci mezery
(mrtvá osa je přesná nula).

## 6 · Data k převzetí a definice hotového

Data (nefixovat znovu): data-persistent/korpus/korpus-101…107, 201,
202, 301…326 (mimo git, fetch skripty, ZDROJ.md); tests/data/korpus/
korpus-001…003 + otazky-201/202; trenink-otazky-korpusy.jsonl (120);
etalon-otazky-korpusy.jsonl (40 — NIKDY do tréninku).

Hotovo = unittest přes ./run-python bez běžící služby (atrapy,
zmražené tokeny), všechny přejímky § 5 prošly, měřicí reporty
s protiváhami v docs/, service/api oddělení, format_version na všem
uloženém, dokumentace jádra (vzor vetev-e.md). Kroky K1–K8
(handover-kvalita.md) se staví až NAD hotovým cb_bond.
