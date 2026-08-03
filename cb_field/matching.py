"""Propojení koše otázky s koši faktů — čistě váhové (bez filtrů).

Koncept (spec P-B, P-F + zadání J.): všechno jsou váhy a součiny.
Kandidátem je KAŽDÝ token korpusu; žádná brána, žádný obsahový filtr,
žádné vylučování — co dřív řezaly filtry, dnes nesou vážené členy:

    skóre(a ve větě f) = cos(q̃, okno)                setkání v uzlech
                       + (W_CENTER−1) · cos(q̃, střed)  zdůraznění středu
                       + W_TOPIC · cos(slova q, slova f)   bonus tématu
                       + W_GIVEN · cos(slova q, slova středu)  postih za
                                                   odpověď slovem, které
                                                   otázka sama dala

kde q̃ i pytle faktů jsou tanh(spread(·)). Každý člen je kosinus dvou
pytlů (−1…+1): délka věty nerozhoduje a členy jsou souměřitelné (krok 2
refaktoru, J.). Zdůraznění středu je vlastní člen schválně — ×W_CENTER
na surovém pytli by pod kosinem trestalo středy s bohatou morfologií
(norma roste o vše, co střed nese). IDF náplast je pryč (dluh D1):
roli protiváhy hubů převzala saturace, naměřeno 0,61 → 0,67 bez ní.

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
W_TOPIC = 1.0
W_GIVEN = -3.0

#: Váhový profil koše kandidáta: střed × W_CENTER, okolí × 1. Bez
#: zdůraznění středu vyhrává soused odpovědi (veze totéž okno) —
#: je to táž páka jako „maskování středu" u šablon, jen obráceně:
#: identita vzoru střed maskuje, extrakce odpovědi ho zdůrazňuje.
W_CENTER = 2.0

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
    meet_score: float          # setkání v uzlech
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

    Vrací seznam po větách: (widx, wvals, wnorm, středy), kde středy je
    seznam (idx, vals, cidx, cvals, cnorm) — jednotkový pytel okna
    s přičteným jednotkovým středem (viz komentář u zdůraznění) a slova
    středu s normou pro kosinové členy skóre.
    """
    key = (len(corpus), corpus.registry.link_version)
    cached = getattr(corpus, "_fact_cache", None)
    if cached is not None and cached[0] == key:
        return cached[1]

    matrices = [s.matrix(Representation.COMPLETE) for s in corpus]
    registry = corpus.registry           # růst registru je dokončen
    n = len(registry)
    links = registry.link_matrix()
    semantic = _semantic_indices(registry, n)
    words = _word_block(registry, n)
    r = corpus.r

    sentences = []
    for sentence, matrix in zip(corpus, matrices):
        rows = []
        for i in range(len(sentence.tokens)):
            row = np.zeros(n, dtype=np.float32)
            row[:matrix.shape[1]] = matrix[i]
            rows.append(row * semantic)
        sentence_words = np.sum(rows, axis=0) * words

        def saturated_unit(bag):
            """tanh(spread(pytel)) dělený svou normou — jednotkový pytel."""
            nz = np.nonzero(bag)[0]
            spread = bag if not len(nz) else bag + bag[nz] @ links[nz]
            out = np.tanh(spread)            # tanh po kroku šíření (P-B)
            norm = float(np.linalg.norm(out))
            return out / norm if norm else out

        widx = np.nonzero(sentence_words)[0]
        centers = []
        for center in range(len(rows)):
            window = saturated_unit(
                np.sum(rows[max(0, center - r):center + r + 1], axis=0))
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
            centers.append((idx, combined[idx],
                            cidx, cvals, float(np.linalg.norm(cvals))))
        wvals = sentence_words[widx]
        sentences.append((widx, wvals, float(np.linalg.norm(wvals)),
                          centers))

    corpus._fact_cache = (key, sentences)
    return sentences


def match(question: SentenceField, corpus: Corpus,
          theta: float = THETA, epsilon: float = EPSILON,
          w_topic: float = W_TOPIC, w_given: float = W_GIVEN,
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

    # Kosinová normalizace (rozhodnutí J. 2026-08-03): každý člen skóre
    # je kosinus dvou pytlů, tedy −1…+1 — délka věty ani mohutnost IDF
    # už nerozhodují a členy jsou navzájem souměřitelné.
    candidates = []
    for sentence, (widx, wvals, wnorm, centers) in zip(corpus,
                                                       fact_sentences):
        w_denominator = q_words_norm * wnorm
        topic = float(w_topic * (q_words[widx] @ wvals) / w_denominator) \
            if w_denominator else 0.0
        for center, (idx, vals, cidx, cvals, cnorm) \
                in enumerate(centers):
            contributions = q_sat[idx] * vals / q_norm if q_norm \
                else np.zeros(len(idx), dtype=np.float32)
            meet = float(contributions.sum())
            c_denominator = q_words_norm * cnorm
            given = float(w_given * (q_words[cidx] @ cvals)
                          / c_denominator) if c_denominator else 0.0
            score = meet + topic + given
            order = np.argsort(-np.abs(contributions))[:top_nodes]
            candidates.append(Candidate(
                sentence=sentence, center=center, score=score,
                meet_score=round(meet, 6), topic_score=round(topic, 6),
                given_score=round(given, 6),
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
