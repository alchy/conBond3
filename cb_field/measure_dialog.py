"""Měření detekce mezery a dialogu — přejímka kroku 4 handoveru.

Spuštění:  ./run-python -m cb_field.measure_dialog

Přehraje průběh dialogu z handoveru na korpusu 2 912 vět: otázka
o dálnici má právě jednu mezeru (rychlost korpus ZNÁ z fyziky),
otázka o křtu žádnou; po doplnění kontextu mezera zmizí a v grafu
přibudou uzly i hrany se zdrojem dialog.
"""

import sys
from datetime import date
from pathlib import Path

from cb_field import __version__
from cb_field.dialog import append_context, axis_coverage, fact_gaps, reply
from cb_field.field import SentenceField
from cb_field.graph import FactGraph

MODULE_DIR = Path(__file__).resolve().parent
REPORT = MODULE_DIR / "docs" / "mereni-dialog.md"

OTAZKA_DALNICE = "Jak je omezena rychlost na dálnici?"
OTAZKA_KREST = "Kde byl pokřtěn Ježíš?"
KONTEXT = ("Dálnice je silnice pro motorová vozidla, kde je stanovena "
           "rychlost na 130 km/h.")


def main() -> None:
    from cb_udpipe import UdpipeClient
    from cb_field.corpusfile import build_corpus
    from cb_field.measure_graph import REFERENCE_FILES

    parser = UdpipeClient()
    # zmražená reference (viz measure_graph): příklad z handoveru je
    # měřený na korpusu ze 4. 8. 2026, rostoucí baseline sem nepatří
    corpus = build_corpus(REFERENCE_FILES, parser, r=1)
    graph = FactGraph()
    for field in corpus:
        graph.add_sentence(field)

    def question(text):
        return SentenceField.from_text(text, parser, r=corpus.r,
                                       registry=corpus.registry)

    q_dalnice = question(OTAZKA_DALNICE)
    q_krest = question(OTAZKA_KREST)

    coverage_before = axis_coverage(q_dalnice, corpus)
    krest_coverage = axis_coverage(q_krest, corpus)
    answer_before = reply(q_dalnice, corpus, graph)

    edges_before = len(graph.edges())
    nodes_before = set(graph.nodes())
    append_context(KONTEXT, corpus, graph, parser)
    coverage_after = axis_coverage(q_dalnice, corpus)
    answer_after = reply(q_dalnice, corpus, graph)
    krest_answer = reply(q_krest, corpus, graph)
    dialog_edges = [e for e in graph.edges() if e[4] == "dialog"]
    new_nodes = [n for n in graph.nodes() if n not in nodes_before]

    checks = [
        ("mezera otázky o dálnici je právě WORD=NOUN:dálnice",
         fact_gaps(q_dalnice, corpus) == [] and
         answer_before.missing == ["WORD=NOUN:dálnice"],
         answer_before.missing),
        ("rychlost korpus zná (fyzika) — neoznačí se",
         coverage_before.get("WORD=NOUN:rychlost", 0.0) > 0.0,
         coverage_before.get("WORD=NOUN:rychlost")),
        ("otázka o křtu je pokrytá — missing prázdné",
         krest_answer.missing == [], krest_answer.missing),
        ("reply vrací kandidáta i při mezeře (nemlčí)",
         answer_before.best is not None
         and answer_before.outcome == "needs_context",
         answer_before.outcome),
        ("po append_context má dálnice nenulové pokrytí",
         coverage_after.get("WORD=NOUN:dálnice", 0.0) > 0.0,
         coverage_after.get("WORD=NOUN:dálnice")),
        ("po doplnění už otázka mezeru nehlásí",
         answer_after.missing == [], answer_after.missing),
        ("v grafu přibyly hrany se zdrojem dialog",
         len(dialog_edges) > 0, len(dialog_edges)),
        ("v grafu přibyly uzly (dálnice…)",
         "NOUN:dálnice" in new_nodes, new_nodes),
    ]

    print(f"korpus {len(corpus)} vět (po dialogu) · graf +{new_nodes} "
          f"· dialogových hran {len(dialog_edges)}")
    failed = 0
    for label, ok, actual in checks:
        mark = "OK" if ok else "!!"
        failed += 0 if ok else 1
        print(f"  {mark} {label}" + ("" if ok else f" — {actual!r}"))

    report = ["# Měření detekce mezery a dialogu (krok 4 handoveru)", ""]
    report.append(f"- datum: {date.today().isoformat()} · verze modulu "
                  f"{__version__} · korpus {len(corpus) - 1} vět "
                  f"+ 1 dialogová")
    report.append("")
    report.append(f"## {OTAZKA_DALNICE}")
    report.append("")
    report.append("| osa | pokrytí před | po doplnění |")
    report.append("|---|---|---|")
    for key, value in coverage_before.items():
        report.append(f"| {key} | {value:.3f} | "
                      f"{coverage_after.get(key, 0.0):.3f} |")
    report.append("")
    report.append(f"Východisko před: **{answer_before.outcome}** "
                  f"(missing {answer_before.missing}), po: "
                  f"**{answer_after.outcome}**.")
    report.append("")
    report.append(f"## {OTAZKA_KREST}")
    report.append("")
    report.append("| osa | pokrytí |")
    report.append("|---|---|")
    for key, value in krest_coverage.items():
        report.append(f"| {key} | {value:.3f} |")
    report.append("")
    report.append("## Co dialog přidal do grafu")
    report.append("")
    report.append(f"Uzly: {', '.join(new_nodes) or '—'}.")
    report.append("")
    report.append("| od | do | deprel |")
    report.append("|---|---|---|")
    for src, dst, rel, _w, _source in dialog_edges:
        report.append(f"| {src} | {dst} | {rel} |")
    report.append("")
    report.append("## Kontroly")
    report.append("")
    report.append("| kontrola | stav |")
    report.append("|---|---|")
    for label, ok, actual in checks:
        report.append(f"| {label} | "
                      + ("OK" if ok else f"**{actual!r}**") + " |")
    report.append("")
    report.append(f"Prošlo {len(checks) - failed}/{len(checks)} kontrol.")
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nzapsáno: {REPORT.relative_to(MODULE_DIR.parent)}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
