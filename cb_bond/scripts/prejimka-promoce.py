#!/usr/bin/env python3
"""Přejímka kroku 6 — promoční cyklus na skutečném korpusu.

Ověřuje čtyři věci, které zadání žádá:

  1. selekt obsadí limit slotů a osa dostane novou verzi,
  2. přegenerovaný korpus nese CUSTOM= aktivace SÁM (transparentnost),
  3. při zhoršení se stav vrátí BIT PO BITU (vazby, obsazení i verze),
  4. beze změny osy se nepřeučuje ani neměří podruhé.

    ./run-python cb_bond/scripts/prejimka-promoce.py

Měří se přesností na etalonu bez učení (retrain je prázdný), takže
výsledek říká, co promoce sama o sobě udělá — v referenci je to
C−B = 0, tedy sloty si na přesnost teprve mají vydělat.
"""

import json
import sys
from pathlib import Path

from cb_bond import KnowledgeGraph, Matcher, PromotionCycle
from cb_bond.config import corpus_dir
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

ETALON = Path("cb_field/tests/data/etalon-otazky-korpusy.jsonl")
LIMIT = 328


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

    rows = [json.loads(r) for r in ETALON.read_text(encoding="utf-8").
            splitlines() if r.strip()]
    zodpoveditelne = [r for r in rows if r["zodpoveditelna"]]

    def measure(c):
        matcher = Matcher(c, spread_depth=1, theta=0.0)
        dobre = sum(
            1 for radek in zodpoveditelne
            if (nej := matcher.match(SentenceField.from_text(
                radek["otazka"], parser, r=1, registry=c.registry)).best)
            and nej.lemma == radek["odpoved_lemma"])
        return {"presnost": round(dobre / len(zodpoveditelne), 4)}

    registry = corpus.registry
    otisk_pred = _otisk(registry)
    chyb = 0

    vysledek = PromotionCycle(measure, lambda c: None, limit=LIMIT).run(
        corpus, graf)
    print(f"1) selekt: {vysledek.axis_changes}")
    sedi = vysledek.axis_changes["pridano"] == LIMIT
    chyb += not sedi
    print(f"   obsazeno {vysledek.axis_changes['pridano']} slotů, "
          f"zadání {LIMIT}{'' if sedi else '   ← ROZDÍL'}")

    print(f"\n2) měření: {vysledek.before} → {vysledek.after}")
    print(f"   {'PŘIJATO' if vysledek.accepted else 'VRÁCENO'} "
          f"· přeučeno={vysledek.retrained}")

    if not vysledek.accepted:
        otisk_po = _otisk(registry)
        sedi = otisk_pred == otisk_po
        chyb += not sedi
        print(f"\n3) návrat bit po bitu: "
              f"{'SEDÍ' if sedi else 'ROZDÍL'}")
        print(f"   vazeb {otisk_pred[0]} → {otisk_po[0]} · "
              f"obsazení {otisk_pred[1]} → {otisk_po[1]} · "
              f"verze {otisk_pred[2]} → {otisk_po[2]}")
        zbyle = {klic for pole in corpus for radek in pole.complete
                 for klic in radek if klic.startswith("CUSTOM=")}
        chyb += bool(zbyle)
        print(f"   zbylých CUSTOM= aktivací v koších: {len(zbyle)} "
              f"(zadání 0)")
    else:
        osy = {klic for pole in corpus for radek in pole.complete
               for klic in radek if klic.startswith("CUSTOM=")}
        chyb += not osy
        print(f"\n3) transparentnost: koše nesou {len(osy)} různých "
              f"CUSTOM= os samy")

    # 4) beze změny osy se nepřeučuje. Po návratu je obsazení prázdné,
    #    takže se nejdřív musí přijmout — proto měřič, který nezhorší.
    stabilni = PromotionCycle(lambda c: {"p": 0.0}, lambda c: None,
                              limit=LIMIT)
    stabilni.run(corpus, graf)
    druhy = stabilni.run(corpus, graf)
    sedi = druhy.accepted and not druhy.retrained
    chyb += not sedi
    print(f"\n4) druhý průchod beze změny osy: přijato={druhy.accepted} "
          f"· přeučeno={druhy.retrained} · {druhy.axis_changes}")
    print(f"   zadání: přijato, NEPŘEUČUJE"
          f"{'' if sedi else '   ← ROZDÍL'}")

    return 1 if chyb else 0


def _otisk(registry) -> tuple:
    """Otisk stavu registru, na kterém se pozná návrat bit po bitu."""
    return (len(registry.links()), registry.custom_axes,
            registry.axis_version)


if __name__ == "__main__":
    sys.exit(main())
