#!/usr/bin/env python3
"""Přejímka kroku 2 — graf faktů proti zmraženým hodnotám § 6 zadání.

Měří na 2 912 větách (korpusy 101–107), protože právě na nich jsou
zmražené hodnoty naměřené. Skript nic nemění; vypíše naměřené vedle
očekávaného a skončí nenulově, když se něco rozejde.

    ./run-python cb_bond/scripts/prejimka-graf.py

Potřebuje běžící cb-udpipe (rozbory jdou z trvalé cache) a korpusy
v cb_field/data-persistent/korpus (mimo git — viz ZDROJ.md).
"""

import sys
from pathlib import Path

from cb_bond import KnowledgeGraph
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

#: Zmražené hodnoty ze zadání § 6. Kdo je mění, mění definici hotového.
OCEKAVANO = {
    "vět": 2912,
    "hran": 16074,
    "lemmat s hranou": 5695,
    "stupeň": 5.6,
    "rok: různých/hran": "162/191",
    "rok: skóre": 137.4,
    "rok: ratio": 0.85,
    "Ježíš: ratio": 0.54,
    "jmen v limitu 328": 11,
}


def main() -> int:
    korpus = Path("cb_field/data-persistent/korpus")
    paths = sorted(korpus.glob("korpus-1*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    corpus = build_corpus(paths, UdpipeClient(), r=1)
    graf = KnowledgeGraph()
    for pole in corpus:
        graf.add_sentence(pole)

    stat = graf.statistics()
    lemmata = {klic.split(":", 1)[1] for klic in stat}
    rok = graf.node_stat("NOUN:rok")
    jezis = graf.node_stat("PROPN:Ježíš")
    vybrane = graf.select_verticals(limit=328, with_scores=True)
    jmen = sum(1 for klic, _ in vybrane if klic.startswith("PROPN:"))

    namereno = {
        "vět": len(corpus),
        "hran": len(graf.edges()),
        "lemmat s hranou": len(lemmata),
        "stupeň": round(2 * len(graf.edges()) / len(lemmata), 1),
        "rok: různých/hran": f"{rok.distinct}/{rok.edges}",
        "rok: skóre": round(rok.distinct ** 2 / rok.edges, 1),
        "rok: ratio": round(rok.ratio, 2),
        "Ježíš: ratio": round(jezis.ratio, 2),
        "jmen v limitu 328": jmen,
    }

    chyb = 0
    print(f"{'co':22} {'naměřeno':>10} {'zadání':>10}")
    for klic, ceka in OCEKAVANO.items():
        je = namereno[klic]
        sedi = je == ceka
        chyb += not sedi
        print(f"{klic:22} {je!s:>10} {ceka!s:>10}   {'' if sedi else '← ROZDÍL'}")

    print(f"\nhranice limitu (328. místo): {vybrane[-1][1]:.1f} "
          f"{vybrane[-1][0]}   (zadání 12,1)")
    poradi = {klic: i for i, (klic, _) in enumerate(vybrane, 1)}
    for kdo in ("PROPN:Praha", "PROPN:Karel", "PROPN:Ježíš", "PROPN:Hrabal"):
        print(f"  {kdo:16} {poradi.get(kdo, 'mimo limit')}")
    print("první tři:", [(k, round(v, 1)) for k, v in vybrane[:3]])

    return 1 if chyb else 0


if __name__ == "__main__":
    sys.exit(main())
