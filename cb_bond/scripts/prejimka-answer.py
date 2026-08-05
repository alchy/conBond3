#!/usr/bin/env python3
"""Přejímka kroku 4 — gaussovské čtení proti tokenovému.

Zadání žádá dvě věci: shluk musí porazit silnější osamělou špičku
(to hlídá jednotkový test) a krátký degenerát „Máš ženu?" nesmí
vyhrávat na 12 258 větách (to měří tenhle skript).

    ./run-python cb_bond/scripts/prejimka-answer.py

Měří se PROTIVÁHA, ne jedno číslo: kolikrát vyhrála krátká věta při
tokenovém a kolikrát při gaussovském čtení, a kolikrát vítězná věta
obsahuje lemma odpovědi.
"""

import json
import sys
from pathlib import Path

from cb_bond import AnswerField, Matcher
from cb_bond.config import corpus_dir
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

ETALON = Path("cb_field/tests/data/etalon-otazky-korpusy.jsonl")

#: Věta, na které se degenerát naměřil. Krátká, tázací, se silným
#: jediným tokenem — přesně tvar, který průměrová normalizace
#: zvýhodňovala.
DEGENERAT = "Máš ženu?"

#: Co je „krátká věta" pro účel téhle protiváhy.
KRATKA = 4


def main() -> int:
    korpus = corpus_dir()
    paths = sorted(korpus.glob("korpus-*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    parser = UdpipeClient()
    corpus = build_corpus(paths, parser, r=1)
    matcher = Matcher(corpus, spread_depth=1, theta=0.0)
    kratke = {i for i, pole in enumerate(corpus) if len(pole.tokens) <= KRATKA}
    degeneraty = [i for i, pole in enumerate(corpus)
                  if pole.source == DEGENERAT]

    rows = [json.loads(r) for r in ETALON.read_text(encoding="utf-8").
            splitlines() if r.strip()]

    token_kratke = gauss_kratke = token_degen = gauss_degen = 0
    token_zasah = gauss_zasah = 0
    zodpoveditelne = 0
    for radek in rows:
        pole_otazky = SentenceField.from_text(radek["otazka"], parser, r=1,
                                              registry=corpus.registry)
        vysledek = matcher.match(pole_otazky)
        if not vysledek.candidates:
            continue
        pole = AnswerField(vysledek)
        tokenova = vysledek.candidates[0].sentence
        vrcholy = pole.gaussian_peaks()
        gaussova = vrcholy[0][0]

        token_kratke += tokenova in kratke
        gauss_kratke += gaussova in kratke
        token_degen += tokenova in degeneraty
        gauss_degen += gaussova in degeneraty
        if radek["zodpoveditelna"]:
            zodpoveditelne += 1
            lemma = radek["odpoved_lemma"]
            token_zasah += lemma in {t.lemma for t in corpus[tokenova].tokens}
            gauss_zasah += lemma in {t.lemma for t in corpus[gaussova].tokens}

    print(f"korpus {len(corpus)} vět · krátkých (≤{KRATKA} tokenů) "
          f"{len(kratke)} · {DEGENERAT!r} na pozicích {degeneraty}")
    print(f"otázek {len(rows)}, z toho zodpověditelných {zodpoveditelne}\n")
    print(f"{'čtení':12} {'krátká věta':>12} {'degenerát':>11} "
          f"{'lemma ve vítězné větě':>23}")
    print(f"{'tokenové':12} {token_kratke:>12} {token_degen:>11} "
          f"{token_zasah:>19}/{zodpoveditelne}")
    print(f"{'gaussovské':12} {gauss_kratke:>12} {gauss_degen:>11} "
          f"{gauss_zasah:>19}/{zodpoveditelne}")

    chyby = []
    if gauss_degen:
        chyby.append(f"{DEGENERAT!r} vyhrálo {gauss_degen}x "
                     f"i pri gaussovskem cteni")
    if gauss_kratke > token_kratke:
        chyby.append("gaussovské čtení zvýhodňuje krátké věty víc "
                     "než tokenové")
    for chyba in chyby:
        print(f"\n← ROZDÍL: {chyba}")
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
