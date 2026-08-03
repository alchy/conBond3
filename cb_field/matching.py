"""Propojení koše otázky s koši faktů — čistě váhové (bez filtrů).

Koncept (spec P-B, P-F + zadání J.): všechno jsou váhy a součiny.
Kandidátem je KAŽDÝ token korpusu; žádná brána, žádný obsahový filtr,
žádné vylučování — co dřív řezaly filtry, dnes nesou vážené členy:

    skóre(a ve větě f) = spread(q)·spread(a)          setkání v uzlech
                       + W_TOPIC · obsah(q, f)        bonus tématu — celému
                                                      pytli, přičtený nakonec
                       + W_GIVEN · dané(střed, q)     záporná váha za odpověď
                                                      slovem, které otázka dala

Jediné řezy v systému jsou θ (NEVÍM) a ε (DOTAZ) na konečném skóre.
Rychlost drží algebra: spread(q)·spread(a) = q_eff·a, kde
q_eff = spread(q) + spread(q)·Lᵀ — otázka se rozšíří jednou, pytle
faktů zůstávají surové (řídké).
"""

from dataclasses import dataclass, field as dataclass_field
from typing import Optional

import numpy as np

from cb_field.corpus import Corpus
from cb_field.field import SentenceField
from cb_field.service import Representation

#: Jediné řezy: práh skóre pro NEVÍM a odstup pro DOTAZ. Kalibrováno
#: na etalonu (registr prahů modulu).
THETA = 2.0
EPSILON = 0.25

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


def _idf(corpus, registry, n):
    """Informační váha vertikál z korpusu: ln(N/df).

    Vertikála, kterou nese každá věta (quantity:sing, time:past), neváží
    skoro nic; vzácná (obsahové slovo, QANCHOR) váží hodně. Bez tohohle
    se uzly hierarchie stávají huby a každá otázka se potká s každou
    větou — naměřeno: šum ~11 bodů proti signálu ~1. Čistě váhová
    protiváha frekvence (týž princip jako NPMI u Hebba), žádný filtr.
    Aplikuje se PŘED šířením, aby huby dostaly jen zeslabené přítoky.
    """
    import math
    cache = getattr(corpus, "_idf_cache", None)
    if cache is not None and len(cache) >= n:
        return cache[:n]
    df = {}
    for sentence in corpus:
        seen = set()
        for weights in sentence.complete:
            for key in weights:
                if key.startswith(MATCH_PREFIXES):
                    seen.add(key)
        for key in seen:
            df[key] = df.get(key, 0) + 1
    total = max(len(corpus), 1)
    idf = np.zeros(n, dtype=np.float32)
    for i, key in enumerate(registry.keys()[:n]):
        if key.startswith(MATCH_PREFIXES):
            # +1 vyhlazení: váha smí zeslabit, nikdy zabít — v malém
            # korpusu by ln(N/df) vyšlo nula a vynulovalo by úplně vše
            idf[i] = 1.0 + math.log((1 + total) / (1 + df.get(key, 0)))
    corpus._idf_cache = idf
    return idf


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
    question.matrix(Representation.COMPLETE)
    for sentence in corpus:
        sentence.matrix(Representation.COMPLETE)

    n = len(registry)
    links = registry.link_matrix()
    semantic = _semantic_indices(registry, n) * _idf(corpus, registry, n)
    words = _word_block(registry, n)

    def padded(vector):
        out = np.zeros(n, dtype=np.float32)
        out[:len(vector)] = vector
        return out

    q_raw = padded(question.matrix(Representation.COMPLETE).sum(axis=0))         * semantic
    q_spread = q_raw + q_raw @ links
    q_eff = q_spread + q_spread @ links.T      # spread(q)·spread(a) = q_eff·a
    q_words = q_raw * words

    candidates = []
    r = corpus.r
    for sentence in corpus:
        matrix = sentence.matrix(Representation.COMPLETE)
        rows = [padded(matrix[i]) * semantic
                for i in range(len(sentence.tokens))]
        sentence_words = np.sum(rows, axis=0) * words
        topic = float(w_topic * (q_words @ sentence_words))
        for center in range(len(sentence.tokens)):
            bag = np.sum(rows[max(0, center - r):center + r + 1], axis=0) \
                + (W_CENTER - 1.0) * rows[center]
            contributions = q_eff * bag
            meet = float(contributions.sum())
            given = float(w_given * (q_words @ (rows[center] * words)))
            score = meet + topic + given
            order = np.argsort(-np.abs(contributions))[:top_nodes]
            candidates.append(Candidate(
                sentence=sentence, center=center, score=score,
                meet_score=round(meet, 3), topic_score=round(topic, 3),
                given_score=round(given, 3),
                top_nodes=tuple(
                    (registry.key(i), round(float(contributions[i]), 3))
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
