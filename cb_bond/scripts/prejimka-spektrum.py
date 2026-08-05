#!/usr/bin/env python3
"""Přejímka § 5/S2 — spektrální člen.

Zadání žádá tři věci a skript měří všechny:

  1. člen je VYPNUTELNÝ — W_SPECTRAL = 0 dá bit po bitu dnešek,
  2. zvedne `sentence_hit` (větné čtení),
  3. přesnost ani mlčení na etalonu NEKLESNOU.

    ./run-python cb_bond/scripts/prejimka-spektrum.py

Měří se na 2 912 větách, etalon 40 otázek (30 zodpověditelných).
"""

import json
import sys
from pathlib import Path

from cb_bond import Matcher, ScoreWeights
from cb_bond.training import sentence_hit
from cb_bond.config import corpus_dir
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

ETALON = Path("cb_field/tests/data/etalon-otazky-korpusy.jsonl")


def main() -> int:
    korpus = corpus_dir()
    paths = sorted(korpus.glob("korpus-1*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    parser = UdpipeClient()
    corpus = build_corpus(paths, parser, r=1)
    etalon = [json.loads(r) for r in ETALON.read_text(encoding="utf-8").
              splitlines() if r.strip()]
    zodpoveditelne = [r for r in etalon if r["zodpoveditelna"]]
    pole = {r["otazka"]: SentenceField.from_text(r["otazka"], parser, r=1,
                                                 registry=corpus.registry)
            for r in etalon}

    def zmer(k, w):
        matcher = Matcher(corpus, spread_depth=1, theta=0.0, spectral_k=k,
                          weights=ScoreWeights(spectral=w))
        presne = veta = mlceni = 0
        for radek in etalon:
            vysledek = matcher.match(pole[radek["otazka"]])
            mlceni += vysledek.outcome == "silent"
            if not radek["zodpoveditelna"]:
                continue
            presne += bool(vysledek.best and
                           vysledek.best.lemma == radek["odpoved_lemma"])
            veta += sentence_hit(vysledek, radek["odpoved_lemma"], corpus,
                                 top=3)
        return presne, veta, mlceni

    bez = zmer(0, 0.0)
    vypnuty = zmer(200, 0.0)
    zapnuty = zmer(200, 1.0)

    print(f"{'konfigurace':34} {'přesnost':>9} {'věta top3':>10} {'mlčení':>7}")
    print(f"{'člen nepočítán (dnešek)':34} {bez[0]:>6}/30 {bez[1]:>7}/30 "
          f"{bez[2]:>7}")
    print(f"{'spočítán, ale W=0':34} {vypnuty[0]:>6}/30 {vypnuty[1]:>7}/30 "
          f"{vypnuty[2]:>7}")
    print(f"{'zapnutý (k=200, W=1)':34} {zapnuty[0]:>6}/30 "
          f"{zapnuty[1]:>7}/30 {zapnuty[2]:>7}")

    chyb = 0
    print()
    for popis, sedi in [
            ("vypnutý člen nemění NIC", vypnuty == bez),
            ("věta v top3 STOUPLA", zapnuty[1] > bez[1]),
            ("přesnost neklesla", zapnuty[0] >= bez[0]),
            ("mlčení nekleslo", zapnuty[2] >= bez[2])]:
        chyb += not sedi
        print(f"  {popis:34} {'OK' if sedi else '← ROZDÍL'}")
    return 1 if chyb else 0


if __name__ == "__main__":
    sys.exit(main())
