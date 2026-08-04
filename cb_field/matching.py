"""Propojení koše otázky s koši faktů — čistě váhové (bez filtrů).

Koncept (spec P-B, P-F + zadání J.): všechno jsou váhy a součiny.
Kandidátem je KAŽDÝ token korpusu; žádná brána, žádný obsahový filtr,
žádné vylučování — co dřív řezaly filtry, dnes nesou vážené členy:

    skóre(a ve větě f) = cos(q̃, okno)                setkání v uzlech
                       + (W_CENTER−1) · cos(q̃, střed)  zdůraznění středu
                       + W_COVER · min_G s̃(f)        podnět: pokrytí
                       + W_FIT · cos(kotvy q, kotvy středu)  odpověď:
                                                   sedí střed do neznámé
                       + W_TOPIC · cos(slova q, slova f)   bonus tématu
                       + W_GIVEN · cos(slova q, slova středu)  postih za
                                                   odpověď slovem, které
                                                   otázka sama dala

kde q̃ i pytle faktů jsou tanh(spread(·)). Kosinové členy jsou čistý
SMĚR (−1…+1): délka věty nerozhoduje a členy jsou souměřitelné (krok 2
refaktoru, J.). Zdůraznění středu je vlastní člen schválně — ×W_CENTER
na surovém pytli by pod kosinem trestalo středy s bohatou morfologií
(norma roste o vše, co střed nese). IDF náplast je pryč (dluh D1):
roli protiváhy hubů převzala saturace, naměřeno 0,61 → 0,67 bez ní.

Pokrytí otázky (rozhodnutí J. 2026-08-04) vrací MOHUTNOST důkazu,
kterou kosinus zahodil a kterou potřebuje řez θ. Má povahu
NEJSLABŠÍHO ČLÁNKU, ne součtu: G jsou dané obsahové osy otázky
(WORD= řádků bez QLEM= — tázací osa je neznámá, ta se nekryje, ta se
odpovídá) a s̃(f) = tanh(spread(věta)). Naměřeno na etalonu: u každé
nezodpověditelné otázky je právě jedna kritická osa mrtvá (neznámé
sloveso, neznámá entita) a zbytek sedí — součtové varianty pokrytí
(q̃·okno/‖q̃‖², slova přes větu) proto NEoddělují (1 osa z N je malý
zlomek součtu, změřený překryv rozdělení), minimum odděluje: mrtvá
osa = člen ~0. Most z učení se počítá (spread před tanh), takže
parafráze pokrytí neztrácí — jen ho má úměrné síle mostu.

Po KAŽDÉM kroku šíření (v + v·L, registr) následuje tanh — aktivace se
saturují do −1…+1, tedy do rozsahu, který váhy už mají (P-B; rozhodnutí
J. 2026-08-03). Lineární systém huboval: uzel hierarchie posbíral stovky
přítoků a přehlušil obsah; saturace drží každý uzel u 1, takže o setkání
rozhoduje POČET sdílených uzlů, ne mohutnost přítoků jednoho hubu.

Jediné řezy v systému jsou θ (NEVÍM) a ε (DOTAZ) na konečném skóre.
Lineární trik spread(q)·spread(a) = q_eff·a tanh rozbíjí (a to je
záměr), proto se pytle faktů šíří explicitně — na otázce ale nezávisejí:
počítají se jednou na stav vazeb a drží se řídce v cache korpusu
(tanh nule nechává nulu).
"""

from dataclasses import dataclass, field as dataclass_field
from typing import Optional

import numpy as np

from cb_field.corpus import Corpus
from cb_field.field import SentenceField
from cb_field.service import Representation

#: Jediné řezy: práh skóre pro NEVÍM a odstup pro DOTAZ. Hodnoty jsou
#: přepočet měřítka po kosinové normalizaci (medián vítězných skóre
#: 4,90 → 1,113, poměr 0,227; θ = 2,0·0,227, ε = 0,25·0,227) — tedy
#: stejně nekalibrované jako předchůdci; kalibrace na oddělené sadě
#: je dluh D2 (docs/workflow.md).
THETA = 0.45
EPSILON = 0.057

#: Váhy členů skóre (páky, kalibrují se měřením):
#: W_TOPIC — bonus tématu: obsahový překryv otázky s celou větou,
#:           přičtený celému pytli nakonec (zadání J.).
#: W_GIVEN — záporná váha za střed, jehož slovo otázka sama uvádí
#:           (odpověď zaplňuje neznámou; místo vyloučení jen táhne dolů).
#: W_COVER — pokrytí otázky: mohutnost důkazu pro řez θ (viz hlavička).
#: W_FIT   — sedí střed do NEZNÁMÉ? Shoda poptávané souřadnice otázky
#:           (QANCHOR stéká šířením do ANCHOR) s kotvou středu.
#:           VÝCHOZÍ 0: samotné kotvy jsou na rozlišení odpovědi moc
#:           hrubé (space/time/quantity má kdeco) a kosinus nad nimi je
#:           skoro binární — naměřeno r=2: 0,94 → 0,85 při W_FIT=1.
#:           Člen zůstává jako páka; jeho pořádnou podobou je query
#:           basket (celý metadatový vzor koše odpovědi, ne jen kotva)
#:           — rozhodnutí J. 2026-08-04, postup-krok4 § 16.
W_TOPIC = 1.0
W_GIVEN = -3.0
W_COVER = 1.0
W_FIT = 0.0

#: Váhový profil koše kandidáta: střed × W_CENTER, okolí × 1. Bez
#: zdůraznění středu vyhrává soused odpovědi (veze totéž okno) —
#: je to táž páka jako „maskování středu" u šablon, jen obráceně:
#: identita vzoru střed maskuje, extrakce odpovědi ho zdůrazňuje.
W_CENTER = 2.0

#: Profil koše ve slovech: příspěvek řádku na vzdálenost d od středu
#: klesá jako 1/(1+d) — týž harmonický pokles jako u vět. Sliding
#: window dává tentýž fakt několika košům a liší je jen vzdálenost
#: odpovědi od středu (J. 2026-08-04); plochý profil je nerozlišil
#: a větší r pak škodilo (naměřeno: r=3 zhoršilo 0,94 → 0,91).
#: Vzdálenější slovo váží míň, ale nikdy nule — žádný strop, jen váha.

#: Přítok sousední VĚTY do koše na vzdálenost d vět: W_CONTEXT/(1+d).
#: Druhé r (r pro větu, zadání J. 2026-08-04) — souvislost nekončí
#: tečkou; co větu předchází a co po ní následuje, do koše patří,
#: jen slaběji. Pokles je harmonický: vzdálenější věta váží míň,
#: ale nikdy nule (žádný strop, jen váha).
W_CONTEXT = 0.5

#: Vertikály vstupující do párování. Strukturní tvar (UPOS/DEPREL/feats)
#: patří šablonám; v součinech pytlů by přehlušil obsah i kotvy
#: (naměřeno v baseline 4a).
MATCH_PREFIXES = ("WORD=", "LEM=", "QLEM=", "ANCHOR=", "QANCHOR=")


@dataclass
class Candidate:
    """Jeden kandidát odpovědi se skóre a rozkladem (P-D)."""

    sentence: SentenceField
    center: int
    score: float
    meet_score: float          # setkání v uzlech (kosinus, směr)
    cover_score: float         # pokrytí otázky — podnět (mohutnost)
    fit_score: float           # sedí střed do neznámé — odpověď
    topic_score: float         # bonus tématu (celé větě)
    given_score: float         # postih za dané slovo
    top_nodes: tuple           # rozklad: (vertikála, příspěvek)

    @property
    def token(self):
        return self.sentence.tokens[self.center]


@dataclass
class MatchResult:
    """Výsledek propojení: východisko + seřazení kandidáti."""

    outcome: str               # "odpoved" | "dotaz" | "nevim"
    candidates: list = dataclass_field(default_factory=list)

    @property
    def best(self) -> Optional[Candidate]:
        return self.candidates[0] if self.candidates else None


def _semantic_indices(registry, vector_len):
    mask = np.zeros(vector_len, dtype=np.float32)
    for i, key in enumerate(registry.keys()[:vector_len]):
        if key.startswith(MATCH_PREFIXES):
            mask[i] = 1.0
    return mask


def _anchor_indices(registry, vector_len):
    """Maska kotev (ANCHOR=…) — souřadnice, na kterou se otázka ptá.

    Tázací kotva otázky (QANCHOR=space) stéká šířením do ANCHOR=space,
    takže obě strany se potkávají v týchž sloupcích; maskou se z pytle
    vybere právě ta část, která nese SOUŘADNICI, ne obsah.
    """
    mask = np.zeros(vector_len, dtype=np.float32)
    for i, key in enumerate(registry.keys()[:vector_len]):
        if key.startswith("ANCHOR="):
            mask[i] = 1.0
    return mask


def _word_block(registry, vector_len):
    mask = np.zeros(vector_len, dtype=np.float32)
    for i, key in enumerate(registry.keys()[:vector_len]):
        if key.startswith("WORD=") and not key.startswith("WORD=PUNCT"):
            mask[i] = 1.0
    return mask


def _fact_bags(corpus):
    """Rozšířené a saturované pytle všech kandidátů — jednou na stav vazeb.

    Pytle faktů na otázce nezávisejí; počítají se při první otázce a pak
    jen při změně vazeb (link_version) nebo růstu korpusu. Drží se řídce:
    (indexy, hodnoty) na kandidáta — tanh nule nechává nulu. Růst
    registru o vertikály otázek cache neruší: nové sloupce mají ve
    starých větách nulovou aktivaci, gather přes staré indexy platí dál.

    Vrací seznam po větách: (widx, wvals, wnorm, sat_idx, sat_vals,
    středy), kde sat_* je saturované šíření CELÉ věty (pro pokrytí
    otázky) a středy je seznam (idx, vals, cidx, cvals, cnorm) —
    jednotkový pytel okna s přičteným jednotkovým středem (viz komentář
    u zdůraznění) a slova středu s normou pro kosinové členy skóre.
    """
    key = (len(corpus), corpus.registry.link_version,
           corpus.r, getattr(corpus, "r_sentences", 0))
    cached = getattr(corpus, "_fact_cache", None)
    if cached is not None and cached[0] == key:
        return cached[1]
    # Zmražení (učicí epocha): učení mění vazby po každé otázce a plná
    # přestavba všech pytlů po každé změně nesla celou cenu epochy.
    # Epocha běží nad pytli zmraženými při svém začátku (obnova jednou
    # na epochu); otázková strana šíří po ČERSTVÝCH vazbách vždy.
    if cached is not None and getattr(corpus, "_fact_cache_freeze",
                                      False) and cached[0][0] == key[0]:
        return cached[1]

    matrices = [s.matrix(Representation.COMPLETE) for s in corpus]
    registry = corpus.registry           # růst registru je dokončen
    n = len(registry)
    links = registry.link_matrix()
    semantic = _semantic_indices(registry, n)
    words = _word_block(registry, n)
    anchors = _anchor_indices(registry, n)
    r = corpus.r

    # Kontextové pytle vět (druhé r): surový pytel celé věty, ať ho
    # sousedé mohou přitéct do koše. Počítá se jednou na větu.
    r_sentences = getattr(corpus, "r_sentences", 0)
    documents = getattr(corpus, "documents", [None] * len(corpus))
    sentence_bags = []
    for sentence, matrix in zip(corpus, matrices):
        bag = np.zeros(n, dtype=np.float32)
        summed = matrix.sum(axis=0)
        bag[:len(summed)] = summed
        sentence_bags.append(bag * semantic)

    sentences = []
    for position, (sentence, matrix) in enumerate(zip(corpus, matrices)):
        rows = []
        for i in range(len(sentence.tokens)):
            row = np.zeros(n, dtype=np.float32)
            row[:matrix.shape[1]] = matrix[i]
            rows.append(row * semantic)
        sentence_words = np.sum(rows, axis=0) * words

        # Přítok sousedních vět téhož dokumentu, W_CONTEXT/(1+d)
        context = np.zeros(n, dtype=np.float32)
        for d in range(1, r_sentences + 1):
            for neighbour in (position - d, position + d):
                if 0 <= neighbour < len(sentence_bags) \
                        and documents[neighbour] is documents[position]:
                    context += (W_CONTEXT / (1 + d)) \
                        * sentence_bags[neighbour]

        def saturated_unit(bag):
            """tanh(spread(pytel)) dělený svou normou — jednotkový pytel."""
            nz = np.nonzero(bag)[0]
            spread = bag if not len(nz) else bag + bag[nz] @ links[nz]
            out = np.tanh(spread)            # tanh po kroku šíření (P-B)
            norm = float(np.linalg.norm(out))
            return out / norm if norm else out

        # Pokrytí otázky se hledá i v kontextu (zadání J.: „tam, kde
        # chybí" — dřív než se postaví synonymní vazba, sáhne se po
        # širším okně; co větě chybí, může nést soused).
        sentence_bag = np.sum(rows, axis=0) + context
        nz = np.nonzero(sentence_bag)[0]
        sentence_spread = sentence_bag if not len(nz) \
            else sentence_bag + sentence_bag[nz] @ links[nz]
        sentence_sat = np.tanh(sentence_spread)   # pro pokrytí otázky
        sat_idx = np.nonzero(sentence_sat)[0]

        widx = np.nonzero(sentence_words)[0]
        centers = []
        for center in range(len(rows)):
            window_bag = context.copy()
            for offset in range(-r, r + 1):
                j = center + offset
                if 0 <= j < len(rows):
                    window_bag += rows[j] / (1 + abs(offset))
            window = saturated_unit(window_bag)
            # Zdůraznění středu je vlastní kosinový člen: ×W_CENTER na
            # surovém pytli by pod kosinem střed s bohatou morfologií
            # trestalo — norma roste o všechno, co střed nese, čitatel
            # jen o to, co se potká s otázkou; a odpověď je z podstaty
            # to, co v otázce NENÍ (zaplňuje neznámou).
            combined = window \
                + (W_CENTER - 1.0) * saturated_unit(rows[center])
            idx = np.nonzero(combined)[0]
            center_words = rows[center] * words
            cidx = np.nonzero(center_words)[0]
            cvals = center_words[cidx]
            # Kotvy STŘEDU (souřadnice, kterou střed nabízí) — druhá
            # strana členu W_FIT. Šíření napřed, ať „v Brně" stekne
            # z dir:at do space; maska až po něm.
            center_anchor = saturated_unit(rows[center]) * anchors
            aidx = np.nonzero(center_anchor)[0]
            avals = center_anchor[aidx]
            centers.append((idx, combined[idx],
                            cidx, cvals, float(np.linalg.norm(cvals)),
                            aidx, avals, float(np.linalg.norm(avals))))
        wvals = sentence_words[widx]
        sentences.append((widx, wvals, float(np.linalg.norm(wvals)),
                          sat_idx, sentence_sat[sat_idx], centers))

    corpus._fact_cache = (key, sentences)
    return sentences


def match(question: SentenceField, corpus: Corpus,
          theta: float = THETA, epsilon: float = EPSILON,
          w_topic: float = W_TOPIC, w_given: float = W_GIVEN,
          w_cover: float = W_COVER, w_fit: float = W_FIT,
          top_nodes: int = 4, top_candidates: int | None = None
          ) -> MatchResult:
    """Propojí otázku s korpusem — čistě váhami, bez filtrů.

    Výstup: MatchResult s kandidáty seřazenými podle skóre; každý nese
    rozklad (setkání + téma + postih) — odpověď bez rozkladu se
    nevydává. Východiska: skóre < θ → NEVÍM; odstup < ε → DOTAZ.
    """
    registry = corpus.registry
    question_matrix = question.matrix(Representation.COMPLETE)
    fact_sentences = _fact_bags(corpus)

    n = len(registry)
    links = registry.link_matrix()
    semantic = _semantic_indices(registry, n)
    words = _word_block(registry, n)

    q_raw = np.zeros(n, dtype=np.float32)
    summed = question_matrix.sum(axis=0)
    q_raw[:len(summed)] = summed
    q_raw *= semantic
    qnz = np.nonzero(q_raw)[0]
    q_spread = q_raw if not len(qnz) else q_raw + q_raw[qnz] @ links[qnz]
    q_sat = np.tanh(q_spread)              # tanh po kroku šíření (P-B)
    q_norm = float(np.linalg.norm(q_sat))
    q_words = q_raw * words
    q_words_norm = float(np.linalg.norm(q_words))
    # Poptávaná souřadnice: QANCHOR otázky stekl šířením do ANCHOR,
    # takže se maskou vybere právě to, na co se otázka ptá.
    q_anchor = q_sat * _anchor_indices(registry, n)
    q_anchor_norm = float(np.linalg.norm(q_anchor))

    # Dané obsahové osy otázky (pro pokrytí): WORD= řádků bez QLEM= —
    # tázací osa je neznámá, ta se nekryje, ta se odpovídá.
    given_axes = []
    for row_weights in question.complete:
        if any(key.startswith("QLEM=") for key in row_weights):
            continue
        for key in row_weights:
            if key.startswith("WORD=") and not key.startswith("WORD=PUNCT"):
                given_axes.append(registry.index(key))

    # Kosinová normalizace (rozhodnutí J. 2026-08-03): každý člen skóre
    # je kosinus dvou pytlů, tedy −1…+1 — délka věty ani mohutnost IDF
    # už nerozhodují a členy jsou navzájem souměřitelné.
    candidates = []
    for sentence, (widx, wvals, wnorm, sat_idx, sat_vals, centers) \
            in zip(corpus, fact_sentences):
        w_denominator = q_words_norm * wnorm
        topic = float(w_topic * (q_words[widx] @ wvals) / w_denominator) \
            if w_denominator else 0.0
        # Pokrytí otázky: nejslabší DANÁ osa nad saturovaným šířením
        # věty. Osa mimo nosnou množinu věty = 0 (searchsorted).
        cover = 0.0
        if given_axes:
            weakest = min(
                float(sat_vals[j]) if j < len(sat_idx)
                and sat_idx[j] == axis else 0.0
                for axis, j in ((a, int(np.searchsorted(sat_idx, a)))
                                for a in given_axes))
            cover = w_cover * weakest
        for center, (idx, vals, cidx, cvals, cnorm,
                     aidx, avals, anorm) in enumerate(centers):
            contributions = q_sat[idx] * vals / q_norm if q_norm \
                else np.zeros(len(idx), dtype=np.float32)
            meet = float(contributions.sum())
            c_denominator = q_words_norm * cnorm
            given = float(w_given * (q_words[cidx] @ cvals)
                          / c_denominator) if c_denominator else 0.0
            a_denominator = q_anchor_norm * anorm
            fit = float(w_fit * (q_anchor[aidx] @ avals)
                        / a_denominator) if a_denominator else 0.0
            score = meet + cover + topic + given + fit
            # top-K bez plného řazení: po Hebbovi mají rozšířené pytle
            # tisíce os a argsort × 58k kandidátů stál hodiny (naměřeno
            # samplem); argpartition je O(n)
            magnitude = -np.abs(contributions)
            if len(contributions) > top_nodes:
                part = np.argpartition(magnitude, top_nodes)[:top_nodes]
            else:
                part = np.arange(len(contributions))
            order = part[np.argsort(magnitude[part])]
            candidates.append(Candidate(
                sentence=sentence, center=center, score=score,
                meet_score=round(meet, 6), cover_score=round(cover, 6),
                fit_score=round(fit, 6),
                topic_score=round(topic, 6), given_score=round(given, 6),
                top_nodes=tuple(
                    (registry.key(int(idx[i])),
                     round(float(contributions[i]), 6))
                    for i in order if contributions[i] != 0)))

    candidates.sort(key=lambda c: -c.score)
    if top_candidates is not None:      # jen zkrácení výpisu, ne řez
        candidates = candidates[:max(top_candidates, 2)]
    if not candidates or candidates[0].score < theta:
        return MatchResult(outcome="nevim", candidates=candidates)
    if len(candidates) > 1 and \
            candidates[0].score - candidates[1].score < epsilon:
        return MatchResult(outcome="dotaz", candidates=candidates)
    return MatchResult(outcome="odpoved", candidates=candidates)
