#!/usr/bin/env python3
"""Vypíše, jak systém odpověděl a ČÍM se rozhodl — po pojmenovaných členech.

Pro každou otázku etalonu: tři nejlepší věty gaussovským čtením a rozklad
skóre vítěze na členy `meet`, `cover`, `topic`, `given`, `spectral`.

    ./run-python cb_bond/scripts/rozklad-skore.py            # celý etalon
    ./run-python cb_bond/scripts/rozklad-skore.py 8          # prvních 8

Nic se neučí ani neukládá — postaví se korpus, vytěží definice a cílené
derivace, spočítá spektrum a odpovídá se. Návod ke čtení výstupu je
v `docs/rozklad-skore.md`.

Značky ve výpisu:

    OK   trefeno (lemma vítěze == očekávané)
    --   zodpověditelná otázka, netrefena
    sv   svod — otázka je NEzodpověditelná, systém měl mlčet
    <    věta nese očekávané lemma
"""

import json
import sys
from pathlib import Path

from cb_bond import (AnswerField, KnowledgeGraph, Matcher, RelationMiner,
from cb_bond.config import corpus_dir
                     ScoreWeights)
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

ETALON = Path("cb_field/tests/data/etalon-otazky-korpusy.jsonl")
SPECTRAL_K = 200


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    limit = int(argv[0]) if argv else None

    korpus = corpus_dir()
    paths = sorted(korpus.glob("korpus-1*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    parser = UdpipeClient()
    print("stavím korpus…", file=sys.stderr, flush=True)
    corpus = build_corpus(paths, parser, r=1)
    graf = KnowledgeGraph()
    for pole in corpus:
        graf.add_sentence(pole)

    etalon = [json.loads(r) for r in ETALON.read_text(encoding="utf-8").
              splitlines() if r.strip()][:limit]
    otazky = {r["otazka"]: SentenceField.from_text(
        r["otazka"], parser, r=1, registry=corpus.registry) for r in etalon}

    miner = RelationMiner()
    definic = miner.mine_definitions(corpus, corpus.registry)
    okoli = {t.lemma for pole in otazky.values() for t in pole.tokens
             if t.upos != "PUNCT"}
    derivaci = miner.mine_derivations(graf, corpus.registry, around=okoli)
    print(f"  {len(corpus)} vět · {definic} definic · {derivaci} derivací "
          f"· spektrum k={SPECTRAL_K}", file=sys.stderr, flush=True)

    matcher = Matcher(corpus, spread_depth=1, theta=0.0,
                      spectral_k=SPECTRAL_K,
                      weights=ScoreWeights(spectral=1.0))

    for radek in etalon:
        vysledek = matcher.match(otazky[radek["otazka"]])
        ceka = radek["odpoved_lemma"]
        if not radek["zodpoveditelna"]:
            znacka = "sv"
        elif vysledek.best and vysledek.best.lemma == ceka:
            znacka = "OK"
        else:
            znacka = "--"
        rozklad = vysledek.best.decomposition()
        print(f"\n{znacka} {radek['otazka']}")
        print(f"     čeká {ceka!s:14} → {vysledek.best.lemma!r}")
        print("     " + " · ".join(f"{jmeno} {hodnota:+.2f}"
                                   for jmeno, hodnota in rozklad.items()
                                   if hodnota or jmeno in ("cover", "given")))
        for poradi, (veta, vrchol, _) in enumerate(
                AnswerField(vysledek).gaussian_peaks()[:3], 1):
            nejlepsi = next(k for k in vysledek.candidates
                            if k.sentence == veta)
            nese = ceka and ceka in {t.lemma for t in corpus[veta].tokens}
            print(f"     {poradi}. {vrchol:.2f} {'<' if nese else ' '} "
                  f"[{nejlepsi.lemma}] {corpus[veta].source[:64]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
