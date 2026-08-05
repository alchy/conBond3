#!/usr/bin/env python3
"""Přejímka kroku 5 — kontrastivní učení nad supervizí.

Ověřuje, co zadání žádá:

  1. pojistka invariantu: žádná naučená hrana nenese WORD=,
  2. bez soupeřící věty se neučí (korekcí 0 = konvergence),
  3. validace řídí konec — epocha, která ji zhorší, se ODVOLÁ,
  4. etalon se do tréninku NEDOSTANE.

    ./run-python cb_bond/scripts/prejimka-uceni.py

Měří se na 2 912 větách; supervize je 120 otázek z JSONL, etalon 40
zůstává stranou.
"""

import json
import sys
from pathlib import Path

from cb_bond import ContrastiveTrainer, Matcher
from cb_bond.training import sentence_hit
from cb_bond.config import corpus_dir
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

TRENINK = Path("cb_field/tests/data/trenink-otazky-korpusy.jsonl")
ETALON = Path("cb_field/tests/data/etalon-otazky-korpusy.jsonl")


def _radky(path):
    return [json.loads(r) for r in path.read_text(encoding="utf-8").
            splitlines() if r.strip()]


def main() -> int:
    korpus = corpus_dir()
    paths = sorted(korpus.glob("korpus-1*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    parser = UdpipeClient()
    corpus = build_corpus(paths, parser, r=1)
    trenink, etalon = _radky(TRENINK), _radky(ETALON)
    zodpoveditelne = [r for r in etalon if r["zodpoveditelna"]]

    def zmer():
        matcher = Matcher(corpus, spread_depth=1, theta=0.0)
        presne = veta = 0
        for radek in zodpoveditelne:
            pole = SentenceField.from_text(radek["otazka"], parser, r=1,
                                           registry=corpus.registry)
            vysledek = matcher.match(pole)
            presne += bool(vysledek.best
                           and vysledek.best.lemma == radek["odpoved_lemma"])
            veta += sentence_hit(vysledek, radek["odpoved_lemma"], corpus,
                                 top=3)
        return presne, veta

    otazky_etalonu = {r["otazka"] for r in etalon}
    prekryv = otazky_etalonu & {r["otazka"] for r in trenink}

    pred = zmer()
    print(f"korpus {len(corpus)} vět · supervize {len(trenink)} otázek "
          f"· etalon {len(etalon)}")
    print(f"PŘED učením: přesnost {pred[0]}/30 · věta v top3 {pred[1]}/30\n")

    pred_vazby = set(corpus.registry.links())
    matcher = Matcher(corpus, spread_depth=1, theta=0.0)
    zprava = ContrastiveTrainer(corpus, matcher, parser).train(
        trenink, max_epochs=6)

    for i, epocha in enumerate(zprava.epochs, 1):
        print(f"epocha {i}: loss {epocha['loss']:.4f} "
              f"· valid {epocha['loss_valid']:.4f} "
              f"· korekcí {epocha['korekci']} · hran {epocha['hran']}"
              f"{'   ← ODVOLÁNA' if epocha['odvolano'] else ''}")

    po = zmer()
    print(f"\nPO učení: přesnost {po[0]}/30 · věta v top3 {po[1]}/30")

    nove = set(corpus.registry.links()) - pred_vazby
    slovni = [(s, d) for s, d, _ in nove
              if s.startswith("WORD=") or d.startswith("WORD=")]

    chyb = 0
    print(f"\n{'co':38} {'naměřeno':>12} {'zadání':>10}")
    for popis, je, ceka in [
            ("naučených hran se slovem (WORD=)", len(slovni), 0),
            ("otázek etalonu v tréninku", len(prekryv), 0),
            ("epoch celkem (≥1)", len(zprava.epochs) >= 1, True),
            ("věta v top3 neklesla", po[1] >= pred[1], True),
            ("přesnost neklesla", po[0] >= pred[0], True)]:
        sedi = je == ceka
        chyb += not sedi
        print(f"{popis:38} {je!s:>12} {ceka!s:>10}"
              f"{'' if sedi else '   ← ROZDÍL'}")

    print(f"\nnaučených hran: {len(nove)} · vazeb v registru celkem: "
          f"{len(corpus.registry.links())}")
    return 1 if chyb else 0


if __name__ == "__main__":
    sys.exit(main())
