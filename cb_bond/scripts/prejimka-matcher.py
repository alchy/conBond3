#!/usr/bin/env python3
"""Přejímka kroku 3 — párování proti zmraženým hodnotám § 6 zadání.

Měří na 2 912 větách (korpusy 101–107) s hloubkou k=1 a bez učení,
tedy přesně v podmínkách, ve kterých je baseline zmrazený.

    ./run-python cb_bond/scripts/prejimka-matcher.py

Vypisuje naměřené vedle očekávaného; nenulový návrat znamená rozdíl.
POZOR: přesnost se dnes NEREPRODUKUJE (viz docs/prirucka.md) — skript
to hlásí jako rozdíl, ne jako úspěch.
"""

import json
import sys
from pathlib import Path

from cb_bond import Matcher, ScoreWeights
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

ETALON = Path("cb_field/tests/data/etalon-otazky-korpusy.jsonl")

#: Zmražené hodnoty ze zadání § 6 a kroku 3b (Matcher baseline k=1).
#:
#: POZOR na dvě čísla, ne jedno: 0,3667 je SPRÁVNĚ **s řezem** (top-1
#: lemma a zároveň outcome „odpoved"), totéž bez řezu je 0,4667 (14/30);
#: rozdíl jsou tři otázky spadlé do DOTAZ/NEVÍM. Tenhle skript měří
#: bez řezu (theta=0), takže se poměřuje se 14/30.
OCEKAVANO = {
    "pokrytí být": 1.000,
    "pokrytí pokřtěný": 0.604,
    "pokrytí Ježíš": 0.885,
    "mrtvá osa dálnice": 0.0,
    "přesnost bez řezu": 0.4667,
    "mlčení": 0,
}

#: Ablace ze kroku 3b: který člen skóre je nosný. Nulové hodnoty jsou
#: tvrdá zemní pravda — bez postihu daného vyhrává vždycky ozvěna
#: otázky, takže samotné setkání netrefí ani jednu otázku.
ABLACE = {
    "plné skóre": ("14/30", {}),
    "bez tématu": ("12/30", {"topic": 0.0}),
    "bez zdůraznění středu": ("9/30", {"center": 1.0}),
    "bez pokrytí": ("7/30", {"cover": 0.0}),
    "bez postihu daného": ("0/30", {"given": 0.0}),
    "jen setkání": ("0/30", {"cover": 0.0, "topic": 0.0, "given": 0.0}),
}


def main() -> int:
    korpus = Path("cb_field/data-persistent/korpus")
    paths = sorted(korpus.glob("korpus-1*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    parser = UdpipeClient()
    corpus = build_corpus(paths, parser, r=1)
    matcher = Matcher(corpus, spread_depth=1, theta=0.0)

    def pole(text):
        return SentenceField.from_text(text, parser, r=1,
                                       registry=corpus.registry)

    krest = matcher.coverage(pole("Kde byl pokřtěn Ježíš?"))
    dalnice = matcher.coverage(pole("Jak je omezena rychlost na dálnici?"))

    rows = [json.loads(r) for r in ETALON.read_text(encoding="utf-8").
            splitlines() if r.strip()]
    zodpoveditelne = [r for r in rows if r["zodpoveditelna"]]
    spravne = mlceni = 0
    for radek in rows:
        vysledek = matcher.match(pole(radek["otazka"]))
        if vysledek.outcome == "silent":
            mlceni += 1
        elif radek["zodpoveditelna"] and vysledek.best and \
                vysledek.best.lemma == radek["odpoved_lemma"]:
            spravne += 1

    namereno = {
        "pokrytí být": round(krest["WORD=AUX:být"], 3),
        "pokrytí pokřtěný": round(krest["WORD=ADJ:pokřtěný"], 3),
        "pokrytí Ježíš": round(krest["WORD=PROPN:Ježíš"], 3),
        "mrtvá osa dálnice": dalnice["WORD=NOUN:dálnice"],
        "přesnost bez řezu": round(spravne / len(zodpoveditelne), 4),
        "mlčení": mlceni,
    }

    chyb = 0
    print(f"{'co':22} {'naměřeno':>10} {'zadání':>10}")
    for klic, ceka in OCEKAVANO.items():
        je = namereno[klic]
        sedi = je == ceka
        chyb += not sedi
        print(f"{klic:22} {je!s:>10} {ceka!s:>10}   "
              f"{'' if sedi else '← ROZDÍL'}")

    print(f"\nsprávně {spravne} z {len(zodpoveditelne)} zodpověditelných "
          f"({len(rows)} otázek celkem)\n")

    print(f"{'ablace členů skóre':26} {'naměřeno':>10}   reference")
    for jmeno, (referencni, uprava) in ABLACE.items():
        vahy = ScoreWeights(**uprava)
        ablacni = Matcher(corpus, spread_depth=1, theta=0.0, weights=vahy)
        trefy = sum(
            1 for radek in rows
            if radek["zodpoveditelna"]
            and (nej := ablacni.match(pole(radek["otazka"])).best)
            and nej.lemma == radek["odpoved_lemma"])
        print(f"{jmeno:26} {trefy:>7}/30   {referencni:>9}")

    return 1 if chyb else 0


if __name__ == "__main__":
    sys.exit(main())
