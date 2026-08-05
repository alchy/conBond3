#!/usr/bin/env python3
"""Měřicí protokol — ramena A–F nad TÝMŽ korpusem (krok 10).

    ./run-python cb_bond/scripts/protokol.py            # 2 912 vět
    ./run-python cb_bond/scripts/protokol.py vse        # celý korpus

POZOR, tenhle skript UČÍ a PROMUJE — mění registr korpusu, který si
postaví. Nic se neukládá na disk, ale běh trvá minuty a ramena na sebe
navazují, takže se nedá přerušit v půlce a číst mezivýsledek.

Supervize je 120 otázek z JSONL; etalon 40 se do tréninku NEDOSTANE
a měří se na něm každé rameno. θ se kalibruje nad SUPERVIZÍ — kdyby
se hledalo nad etalonem, vybíralo by se podle testu, který má měřit.
"""

import json
import sys
import time
from pathlib import Path

from cb_bond import (ArmResult, BenchmarkProtocol, ContrastiveTrainer,
                     GraphRecall, KnowledgeGraph, Matcher, PromotionCycle,
                     ThresholdCalibrator, sentence_hit)
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

TRENINK = Path("cb_field/tests/data/trenink-otazky-korpusy.jsonl")
ETALON = Path("cb_field/tests/data/etalon-otazky-korpusy.jsonl")


def _radky(path):
    return [json.loads(r) for r in path.read_text(encoding="utf-8").
            splitlines() if r.strip()]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    vzor = "korpus-*.json" if argv and argv[0] == "vse" else "korpus-1*.json"

    korpus = Path("cb_field/data-persistent/korpus")
    paths = sorted(korpus.glob(vzor))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    parser = UdpipeClient()
    print(f"stavím korpus z {len(paths)} souborů…", file=sys.stderr,
          flush=True)
    corpus = build_corpus(paths, parser, r=1)
    graf = KnowledgeGraph()
    for pole in corpus:
        graf.add_sentence(pole)
    recall = GraphRecall(graf, corpus, depth=2)
    trenink, etalon = _radky(TRENINK), _radky(ETALON)
    zodpoveditelne = [r for r in etalon if r["zodpoveditelna"]]
    print(f"  {len(corpus)} vět · {len(graf.edges())} hran · supervize "
          f"{len(trenink)} · etalon {len(etalon)}", file=sys.stderr,
          flush=True)

    pole_otazek = {}

    def pole(text):
        if text not in pole_otazek:
            pole_otazek[text] = SentenceField.from_text(
                text, parser, r=1, registry=corpus.registry)
        return pole_otazek[text]

    def matcher(depth, theta=0.0):
        return Matcher(corpus, spread_depth=depth, theta=theta,
                       graph_recall=recall)

    def vysledky(radky, depth):
        m = matcher(depth)
        return [m.match(pole(r["otazka"])) for r in radky]

    def measure(label, depth, pozn=""):
        t0 = time.time()
        presne = veta = mlcelo = nezodp = 0
        for radek, vysledek in zip(etalon, vysledky(etalon, depth)):
            if radek["zodpoveditelna"]:
                presne += bool(vysledek.best and vysledek.best.lemma
                               == radek["odpoved_lemma"])
                veta += sentence_hit(vysledek, radek["odpoved_lemma"],
                                     corpus, top=3)
            else:
                nezodp += 1
                mlcelo += vysledek.outcome == "silent"
        rameno = ArmResult(label, round(presne / len(zodpoveditelne), 4),
                           round(mlcelo / nezodp, 2) if nezodp else 0.0,
                           veta, len(zodpoveditelne), pozn)
        print(f"  {rameno}   ({time.time() - t0:.0f} s)", file=sys.stderr,
              flush=True)
        return rameno

    def train():
        print("  učím…", file=sys.stderr, flush=True)
        zprava = ContrastiveTrainer(corpus, matcher(1), parser).train(
            trenink, max_epochs=6)
        print(f"    epoch {len(zprava.epochs)} · ponecháno "
              f"{zprava.trained_epochs}", file=sys.stderr, flush=True)

    def promote():
        print("  promuji…", file=sys.stderr, flush=True)
        cyklus = PromotionCycle(
            lambda c: {"presnost": measure("(měření promoce)", 1).presnost},
            lambda c: None, limit=328)
        return cyklus.run(corpus, graf)

    def calibrate(label):
        print("  kalibruji θ nad SUPERVIZÍ…", file=sys.stderr, flush=True)
        nalez = ThresholdCalibrator().calibrate(
            trenink, vysledky(trenink, 2))
        m = Matcher(corpus, spread_depth=2, theta=nalez["theta"],
                    graph_recall=recall)
        presne = veta = mlcelo = nezodp = 0
        for radek in etalon:
            vysledek = m.match(pole(radek["otazka"]))
            if radek["zodpoveditelna"]:
                presne += bool(vysledek.outcome != "silent" and vysledek.best
                               and vysledek.best.lemma
                               == radek["odpoved_lemma"])
                veta += sentence_hit(vysledek, radek["odpoved_lemma"],
                                     corpus, top=3)
            else:
                nezodp += 1
                mlcelo += vysledek.outcome == "silent"
        return ArmResult(label, round(presne / len(zodpoveditelne), 4),
                         round(mlcelo / nezodp, 2) if nezodp else 0.0,
                         veta, len(zodpoveditelne),
                         f"θ={nalez['theta']:.3f} (na tréninku "
                         f"{nalez['presnost']}/{nalez['mlceni']})")

    report = BenchmarkProtocol(measure, train, promote, calibrate).run()

    print("\n" + "=" * 72)
    print(f"{'rameno':4} {'co měří':46} {'přesnost':>9} {'mlčení':>7} "
          f"{'věta':>6}")
    print("=" * 72)
    popisy = dict(BenchmarkProtocol.ARMS)
    for rameno in report.arms:
        print(f"{rameno.label:4} {popisy.get(rameno.label, '')[:46]:46} "
              f"{rameno.presnost:>9.4f} {rameno.mlceni:>7.2f} "
              f"{rameno.veta:>3}/{rameno.zodpoveditelnych}")
        if rameno.pozn:
            print(f"     {rameno.pozn}")

    print("\nvylosované příklady (semínko 328):")
    import random
    los = random.Random(328)
    m = matcher(2)
    for radek in los.sample(etalon, min(4, len(etalon))):
        vysledek = m.match(pole(radek["otazka"]))
        znak = "OK" if (radek["zodpoveditelna"] and vysledek.best
                        and vysledek.best.lemma
                        == radek["odpoved_lemma"]) else "--"
        print(f"  {znak} {radek['otazka']}")
        print(f"       čeká {radek['odpoved_lemma']} → "
              f"{vysledek.best.lemma!r} [{vysledek.outcome}]")
        print(f"       věta: {corpus[vysledek.best.sentence].source[:62]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
