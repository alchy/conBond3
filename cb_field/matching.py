"""Propojení koše otázky s koši faktů — fáze 4a spec (README-PROPOJENI).

Koš je pytel (P-A): vektor koše = suma vektorů řádků okna, pořadí nehraje
roli. Skóre = spread(q)·spread(a) — bilineární forma s ručním W (axiomy
kotev). Tři východiska (P-F): ODPOVĚĎ / DOTAZ / NEVÍM. Každá odpověď
nese rozklad skóre po uzlech (P-D) — kde přesně se strany potkaly.
"""

from dataclasses import dataclass, field as dataclass_field
from typing import Optional

import numpy as np

from cb_field.corpus import Corpus
from cb_field.field import SentenceField
from cb_field.service import Representation
from cb_field.templates import default_centers

#: Práh skóre pro NEVÍM a odstup pro DOTAZ. Startovní hodnoty před
#: kalibrací na etalonu (registr prahů modulu); θ smí být 0, protože
#: bránu drží požadavek obsahu a dimenze, ne velikost součinu.
THETA = 0.0
EPSILON = 0.25

#: Vertikály, které vstupují do párovacích pytlů. Strukturní tvar
#: (UPOS/DEPREL/feats/SUBPOS) do propojení nepatří — sdílí ho každá
#: věta s každou a v součtu pytlů přehluší obsah i kotvy (naměřeno:
#: baseline 4a bez filtru — vítězila slovesa se skóre 17–30, kotvy
#: nesly 0.49). Tvar patří šablonám (identita), propojení nese obsah
#: a souřadnice.
MATCH_PREFIXES = ("WORD=", "LEM=", "QLEM=", "ANCHOR=", "QANCHOR=")

#: Nejméně sdílených obsahových slov, aby věta vůbec kandidovala.
#: Jedno slovo („Petr") pinovalo falešné odpovědi na nezodpověditelné
#: otázky — dvě sdílená slova znamenají, že věta mluví o tomtéž rámci.
MIN_SHARED_WORDS = 2

#: Jmenné druhy, jejichž řádek smí být kandidátem odpovědi.
_NOMINAL = frozenset({"NOUN", "PROPN", "PRON", "NUM"})


def candidate_centers(sentence: SentenceField) -> tuple:
    """Kandidátní středy odpovědí: jmenné řádky (jádra R1 + podměty
    a předměty). Sloveso hodnotou odpovědi není — naměřeno: slovesa
    procházela časovou branou přes vlastní Tense a vyhrávala nad
    skutečnými časovými výrazy. Odchylka od spec § 2 zapsaná jako páka.
    """
    centers = {i for i in default_centers(sentence)
               if sentence.tokens[i].upos in _NOMINAL}
    for i, token in enumerate(sentence.tokens):
        if token.upos in _NOMINAL and token.deprel.split(":")[0] in (
                "nsubj", "obj", "iobj"):
            centers.add(i)
    return tuple(sorted(centers))


def _content_words(sentence: SentenceField) -> set:
    """WORD vertikály obsahových slov (bez interpunkce a tázacích slov)."""
    words = set()
    for i, weights in enumerate(sentence.complete):
        if any(k.startswith("QANCHOR=") for k in sentence.metadata[i]):
            continue
        words.update(k for k in weights
                     if k.startswith("WORD=") and not k.startswith("WORD=PUNCT"))
    return words


@dataclass
class Candidate:
    """Jeden kandidát odpovědi: koš faktu se skóre a rozkladem."""

    sentence: SentenceField
    center: int
    score: float
    dimension_score: float
    shared_words: frozenset
    top_nodes: tuple          # ((vertikála, příspěvek), …) — rozklad P-D

    @property
    def token(self):
        return self.sentence.tokens[self.center]


@dataclass
class MatchResult:
    """Výsledek propojení: východisko + seřazení kandidáti."""

    outcome: str              # "odpoved" | "dotaz" | "nevim"
    candidates: list = dataclass_field(default_factory=list)

    @property
    def best(self) -> Optional[Candidate]:
        return self.candidates[0] if self.candidates else None


def match(question: SentenceField, corpus: Corpus,
          theta: float = THETA, epsilon: float = EPSILON,
          top_nodes: int = 4) -> MatchResult:
    """Propojí koš otázky s koši faktů korpusu (ruční W — axiomy).

    Kandidují jen koše vět, které s otázkou sdílejí aspoň jedno obsahové
    slovo (otázka bez společného obsahu nemá o čem mluvit), a jen ty,
    jejichž příspěvek prochází aspoň jednou poptávanou souřadnicí
    (dimenzní brána, OR přes souřadnice otázky).

    Výstup: MatchResult; kandidáti seřazení podle skóre, každý s
    rozkladem na top uzly — odpověď bez rozkladu se nevydává (P-D).
    """
    registry = corpus.registry
    question.matrix(Representation.COMPLETE)
    matrices = [f.matrix(Representation.COMPLETE) for f in corpus]

    n = len(registry)
    links = registry.link_matrix()
    mask = np.array([1.0 if k.startswith(MATCH_PREFIXES) else 0.0
                     for k in registry.keys()], dtype=np.float32)

    def spread(vector):
        padded = np.zeros(n, dtype=np.float32)
        padded[:len(vector)] = vector
        padded *= mask
        return padded + padded @ links

    q_matrix = question.matrix(Representation.COMPLETE)
    q_bag = spread(q_matrix.sum(axis=0))
    q_words = _content_words(question)

    # poptávané souřadnice otázky (dimenze bez upřesnění)
    question_dims = set()
    for weights in question.metadata:
        for key in weights:
            if key.startswith("QANCHOR="):
                question_dims.add(key.split("=", 1)[1].split(":")[0])

    def center_anchors_dimension(sentence, center):
        """Brána: odpověď musí SAMA kotvit poptávanou souřadnici.

        Kontrola na řádku středu, ne na pytli — jinak bránou projde
        koš, jehož soused kotví cokoli (naměřeno v baseline). Přímé
        čtení klíčů: interpretovatelné bez algebry.
        """
        if not question_dims:
            return True
        for key in sentence.metadata[center]:
            if key.startswith("ANCHOR="):
                if key.split("=", 1)[1].split(":")[0] in question_dims:
                    return True
        # tolerance pro „kdo/co": podmět/předmět je entita i bez kotvy —
        # entity kotvu z Animacy nejde dát poctivě (UD ji značí jen
        # u maskulin) a typ=osoba přijde až s gazetteerem (krok 5)
        if "entity" in question_dims:
            token = sentence.tokens[center]
            if token.deprel.split(":")[0] in ("nsubj", "obj", "iobj"):
                return True
        return False

    candidates = []
    for sentence, matrix in zip(corpus, matrices):
        shared = q_words & _content_words(sentence)
        if len(shared) < MIN_SHARED_WORDS:
            continue
        # obsahový člen na úrovni věty: sdílená slova pinují fakt
        # k otázce, i když leží mimo okno kandidáta (vazby slovníku
        # ze starého pole). Váhy 0.7·0.7 za sdílené slovo.
        content_score = 0.49 * len(shared)
        for center in candidate_centers(sentence):
            if not center_anchors_dimension(sentence, center):
                continue
            # odpověď zaplňuje neznámou — nesmí být slovem, které otázka
            # sama uvádí („Kdy jel do Plzně?" nemůže odpovědět „Plzně")
            center_word = {k for k in sentence.complete[center]
                           if k.startswith("WORD=")}
            if center_word & q_words:
                continue
            left = max(0, center - corpus.r)
            bag = spread(matrix[left:center + corpus.r + 1].sum(axis=0))
            contributions = q_bag * bag
            dim_score = float(sum(
                contributions[registry.index(f"ANCHOR={d}")]
                for d in question_dims if f"ANCHOR={d}" in registry))
            score = float(contributions.sum()) + content_score
            if score < theta:
                continue
            order = np.argsort(-np.abs(contributions))[:top_nodes]
            candidates.append(Candidate(
                sentence=sentence, center=center, score=score,
                dimension_score=dim_score, shared_words=frozenset(shared),
                top_nodes=tuple((registry.key(i), round(float(
                    contributions[i]), 3)) for i in order
                    if contributions[i] != 0)))

    candidates.sort(key=lambda c: -c.score)
    if not candidates:
        return MatchResult(outcome="nevim")
    if len(candidates) > 1 and \
            candidates[0].score - candidates[1].score < epsilon:
        return MatchResult(outcome="dotaz", candidates=candidates)
    return MatchResult(outcome="odpoved", candidates=candidates)
