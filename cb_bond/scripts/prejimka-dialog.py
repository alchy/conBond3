#!/usr/bin/env python3
"""Přejímka kroku 8 — celý dialogový průběh o dálnici.

Zadání ho popisuje do puntíku a tenhle skript ho přehraje:

    q: Jak je omezena rychlost na dálnici?
       být 1,000 · omezený 0,604 · rychlost 0,604 · na 1,000 · dálnice 0,000
    a: needs_context, missing = [WORD=NOUN:dálnice]
    u: Dálnice je silnice pro motorová vozidla, kde je stanovena
       rychlost na 130 km/h.
    q znovu: dálnice 0,604 → answer

    ./run-python cb_bond/scripts/prejimka-dialog.py

Běží na 2 912 větách (korpusy 101–107), kde dálnice opravdu chybí —
je to biblicko-fyzikální korpus. Nenulový návrat znamená rozdíl.
"""

import sys
from pathlib import Path

from cb_bond import KnowledgeGraph, Matcher, Responder
from cb_bond.config import corpus_dir
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

OTAZKA = "Jak je omezena rychlost na dálnici?"
KONTEXT = ("Dálnice je silnice pro motorová vozidla, kde je stanovena "
           "rychlost na 130 km/h.")

#: Zmražené pokrytí otázky PŘED doplněním kontextu.
PRED = {
    "WORD=AUX:být": 1.000,
    "WORD=ADJ:omezený": 0.604,
    "WORD=NOUN:rychlost": 0.604,
    "WORD=ADP:na": 1.000,
    "WORD=NOUN:dálnice": 0.000,
}

#: A po něm: jediná mezera se zavře na jeden výskyt slovní osy.
PO = {"WORD=NOUN:dálnice": 0.604}


def main() -> int:
    korpus = corpus_dir()
    paths = sorted(korpus.glob("korpus-1*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    parser = UdpipeClient()
    corpus = build_corpus(paths, parser, r=1)
    graf = KnowledgeGraph()
    for pole in corpus:
        graf.add_sentence(pole)
    hran_pred = len(graf.edges())

    responder = Responder(Matcher(corpus, spread_depth=1, theta=0.0), graf)

    def otazka():
        return SentenceField.from_text(OTAZKA, parser, r=1,
                                       registry=corpus.registry)

    chyb = 0
    pokryti = responder.matcher.coverage(otazka())
    print(f"q: {OTAZKA}")
    for osa, ceka in PRED.items():
        je = round(pokryti.get(osa, 0.0), 3)
        sedi = je == ceka
        chyb += not sedi
        print(f"   {osa:22} {je:>6.3f}   zadání {ceka:.3f}"
              f"{'' if sedi else '   ← ROZDÍL'}")

    reply = responder.reply(otazka())
    ceka_missing = ["WORD=NOUN:dálnice"]
    sedi = reply.outcome == "needs_context" and reply.missing == ceka_missing
    chyb += not sedi
    print(f"\na: {reply.outcome}, missing={reply.missing}")
    print(f"   zadání: needs_context, missing={ceka_missing}"
          f"{'' if sedi else '   ← ROZDÍL'}")
    print(f"   (odpovídá i tak — nejlepší kandidát {reply.lemma!r})")

    print(f"\nu: {KONTEXT}")
    vet_pred = len(corpus)
    responder.append_context(KONTEXT, parser)
    pribylo = len(graf.edges()) - hran_pred
    print(f"   korpus +{len(corpus) - vet_pred} věta ({len(corpus)} celkem) "
          f"· graf +{pribylo} hran   zadání +1 věta · +9 hran")
    for src, dst, deprel, _, zdroj in graf.edges()[hran_pred:]:
        print(f"     {src:22} --{deprel}--> {dst}  [{zdroj}]")

    pokryti = responder.matcher.coverage(otazka())
    reply = responder.reply(otazka())
    print("\nq znovu:")
    for osa, ceka in PO.items():
        je = round(pokryti.get(osa, 0.0), 3)
        sedi = je == ceka
        chyb += not sedi
        print(f"   {osa:22} {je:>6.3f}   zadání {ceka:.3f}"
              f"{'' if sedi else '   ← ROZDÍL'}")
    sedi = reply.outcome == "answer"
    chyb += not sedi
    print(f"   outcome {reply.outcome}   zadání answer"
          f"{'' if sedi else '   ← ROZDÍL'}")

    return 1 if chyb else 0


if __name__ == "__main__":
    sys.exit(main())
