"""Detekce mezery a dialog — krok 4 handoveru.

Není to nová mechanika: `cover` v párování už dnes počítá nejslabší
danou osu a mrtvá osa dává nulu — signál v poli je, jen se utopí ve
skóre. Tady se vytahuje na povrch: `fact_gaps()` řekne, které osy
otázky korpus vůbec nemá; `reply()` odpoví a zároveň chybějící osy
ohlásí; `append_context()` připojí větu od uživatele.

Práh není potřeba (naměřeno 4. 8. 2026): mrtvá osa dává PŘESNĚ nulu,
protože v registru vůbec není, zatímco pokryté osy začínají na 0,604.
Mezi tím je propast, ne škála.

Věta od uživatele jde stejnou cestou jako každý text, jen se zdrojem
`dialog` — žádná zvláštní větev. Pak se na ni vztahuje všechno ostatní
(koše, promoce, učení) bez výjimek, a přitom jde kdykoli zjistit,
odkud je, a případně ji odebrat.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from cb_field.corpus import Corpus
from cb_field.field import SentenceField
from cb_field.graph import FactGraph
from cb_field.matching import Candidate, _fact_bags, match


def given_axes(question: SentenceField) -> list:
    """Dané obsahové osy otázky: WORD= řádků bez QLEM=, bez opakování.

    Tázací osa je neznámá — ta se nekryje, ta se odpovídá. Táž definice
    jako u pokrytí v match(); tady nad klíči, ne indexy, protože mezera
    je právě osa, kterou korpus (a možná ani registr) nemá.
    """
    axes = []
    for row_weights in question.complete:
        if any(key.startswith("QLEM=") for key in row_weights):
            continue
        for key in row_weights:
            if key.startswith("WORD=") and not key.startswith("WORD=PUNCT") \
                    and key not in axes:
                axes.append(key)
    return axes


def axis_coverage(question: SentenceField, corpus: Corpus) -> dict:
    """Pokrytí daných os otázky korpusem: {osa: max přes věty}.

    Hodnota věty je saturované šíření celé věty — týž pytel, nad kterým
    match() počítá pokrytí (nejslabší článek); tady se z něj čte
    maximum přes korpus: stačí jediná věta, která osu nese.
    """
    bags = _fact_bags(corpus)
    registry = corpus.registry
    coverage = {}
    for key in given_axes(question):
        if key not in registry:
            coverage[key] = 0.0        # mrtvá osa: v registru vůbec není
            continue
        axis = registry.index(key)
        best = 0.0
        for _w, _wv, _wn, sat_idx, sat_vals, _centers in bags:
            j = int(np.searchsorted(sat_idx, axis))
            if j < len(sat_idx) and sat_idx[j] == axis:
                best = max(best, float(sat_vals[j]))
        coverage[key] = best
    return coverage


def fact_gaps(question: SentenceField, corpus: Corpus) -> list:
    """Osy otázky, které korpus vůbec nemá — přesné nuly pokrytí."""
    return [key for key, value in axis_coverage(question, corpus).items()
            if value == 0.0]


@dataclass
class Reply:
    """Odpověď s ohlášením mezery — vidí se, kam systém sáhl."""

    best: Optional[Candidate]
    outcome: str               # odpoved | dotaz | nevim | needs_context
    missing: list              # chybějící osy (prázdné = pokryto)


def reply(question: SentenceField, corpus: Corpus,
          graph: FactGraph | None = None) -> Reply:
    """Odpoví VŽDY, i při mezeře — a chybějící osy ohlásí.

    Při experimentu je kandidát užitečnější než mlčení (vidíš, kam
    systém sáhl) a nic se nezakrývá: chybějící osa je vypsaná. Čisté
    mlčení je jednořádková změna na volající straně.

    graph: zatím se nečte; náhled (krok 6) po něm ukáže hrany, po
    kterých aktivace šla.
    """
    gaps = fact_gaps(question, corpus)
    result = match(question, corpus)   # hledá se vždy
    return Reply(best=result.best,
                 outcome="needs_context" if gaps else result.outcome,
                 missing=gaps)


def append_context(text: str, corpus: Corpus, graph: FactGraph,
                   parser) -> SentenceField:
    """Připojí větu od uživatele — stejnou cestou jako každý text,
    jen se zdrojem dialog (dokument korpusu i hrany grafu)."""
    field = corpus.add_text(text, parser, document="dialog")
    graph.add_sentence(field, source="dialog")
    return field
