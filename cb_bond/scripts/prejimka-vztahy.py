#!/usr/bin/env python3
"""Přejímka kroku 7 — definiční a derivační vazby.

    ./run-python cb_bond/scripts/prejimka-vztahy.py

Definice se měří na celém korpusu (12 258 vět), protože právě tam je
zmražená hodnota 94 naměřená. Derivace se NEMĚŘÍ plošně: plošné
nasazení dalo 11 268 vazeb a stálo baseline 3,3 bodu — skript proto
ukazuje cílenou těžbu kolem slov jedné otázky, což je provozní režim.
"""

import sys
from pathlib import Path

from cb_bond import KnowledgeGraph, RelationMiner
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

#: Zmražené hodnoty ze zadání § 6 a § krok 7.
OCEKAVANO = {"definic": 94}

#: Vzorky, které zadání jmenuje — počet sám o sobě nestačí.
VZORKY = [("gravitace", "síla"), ("foton", "částice"),
          ("elektromotor", "stroj"), ("Isaac", "fyzik")]


def main() -> int:
    korpus = Path("cb_field/data-persistent/korpus")
    paths = sorted(korpus.glob("korpus-*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    corpus = build_corpus(paths, UdpipeClient(), r=1)
    graf = KnowledgeGraph()
    for pole in corpus:
        graf.add_sentence(pole)

    miner = RelationMiner()
    definic = miner.mine_definitions(corpus, corpus.registry)

    chyb = 0
    print(f"{'co':22} {'naměřeno':>10} {'zadání':>10}")
    for klic, ceka in OCEKAVANO.items():
        je = {"definic": definic}[klic]
        sedi = je == ceka
        chyb += not sedi
        print(f"{klic:22} {je:>10} {ceka:>10}   {'' if sedi else '← ROZDÍL'}")

    nalezene = {(src.split(":", 1)[1], dst.split(":", 1)[1])
                for src, dst, *_ in miner.definitions}
    print("\njmenované vzorky:")
    for dvojice in VZORKY:
        je = dvojice in nalezene
        chyb += not je
        print(f"  {dvojice[0]} → {dvojice[1]:12} {'ANO' if je else '← CHYBÍ'}")

    # Derivace cíleně: kolem slov otázky o dálnici (provozní režim).
    okoli = {"rychlost", "dálnice", "kámen"}
    derivaci = miner.mine_derivations(graf, corpus.registry, around=okoli)
    print(f"\nderivace kolem {sorted(okoli)}: {derivaci} vazeb")
    for src, dst, vaha, _ in miner.derivations[:8]:
        print(f"  {src.split('=', 1)[1]:22} → {dst.split('=', 1)[1]:22} "
              f"{vaha:.2f}")
    print("(plošná těžba se NEMĚŘÍ: 11 268 vazeb stálo baseline 3,3 bodu)")

    return 1 if chyb else 0


if __name__ == "__main__":
    sys.exit(main())
