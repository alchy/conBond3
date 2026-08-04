"""Měření grafu faktů na korpusu — přejímka kroku 1 handoveru.

Spuštění:  ./run-python -m cb_field.measure_graph

Přeběhne korpus komplexních textů (2 912 vět), postaví FactGraph
a porovná čísla s referenčním měřením ze 4. 8. 2026. Referenční
statistika klíčovala uzly jen lemmatem; graf podle handoveru klíčuje
UPOS:lemma („stát" stát-NOUN od stát-VERB odlišuje). Report proto
uvádí obě čtení vedle sebe (workflow § B5: číslo bez protiváhy se
neuvádí) — hranové instance jsou na klíči nezávislé a musejí sedět
přesně.
"""

import sys
from datetime import date
from pathlib import Path

from cb_field import __version__
from cb_field.graph import FactGraph

MODULE_DIR = Path(__file__).resolve().parent
REPORT = MODULE_DIR / "docs" / "mereni-graf.md"

#: Referenční čísla ze 4. 8. 2026 (docs/handover-implementace.md,
#: krok 1) — měřeno nad uzly klíčovanými lemmatem bez UPOS.
REFERENCE = {
    "vet": 2912, "lemmat": 5695, "hran": 16074,
    "prumerny_stupen": 5.6, "prumer_ruznych": 4.6,
}
REFERENCE_NODES = {
    "mít": (185, 260, 118), "říci": (177, 308, 160),
    "rok": (162, 191, 93), "jít": (129, 174, 78),
    "přijít": (124, 168, 71), "moci": (119, 147, 60),
    "stát": (85, 93, 42), "stroj": (79, 144, 81),
    "Karel": (75, 152, 70), "začít": (62, 67, 30),
    "Ježíš": (60, 111, 106), "Bohumil": (60, 120, 55),
}


def lemma_stats(graph: FactGraph) -> dict:
    """Statistika sloučená na lemma (bez UPOS) — čtení referenčního
    měření. Sousedé se slévají také, takže „různých" je počet různých
    lemmat, ne klíčů."""
    merged: dict = {}
    for key, stat in graph.node_stats().items():
        lemma = key.split(":", 1)[1]
        entry = merged.setdefault(lemma, [0, 0, set()])
        entry[0] += stat.occurrences
        entry[1] += stat.edges
        entry[2].update(n.split(":", 1)[1] for n in stat.neighbours)
    return merged


def main() -> None:
    from cb_udpipe import UdpipeClient
    from cb_field.evaluate import build_complex_corpus

    parser = UdpipeClient()
    corpus = build_complex_corpus(parser)
    graph = FactGraph()
    for field in corpus:
        graph.add_sentence(field)

    s = graph.stats()
    merged = lemma_stats(graph)
    connected = {lemma: (occ, edges, sorted(nb))
                 for lemma, (occ, edges, nb) in merged.items() if edges}
    lemma_view = {
        "vet": len(corpus), "lemmat": len(connected), "hran": s["hran"],
        "prumerny_stupen": round(2 * s["hran"] / len(connected), 1),
        "prumer_ruznych": round(
            sum(len(nb) for _o, _e, nb in connected.values())
            / len(connected), 1),
    }

    checks = []
    for key, expected in REFERENCE.items():
        checks.append((f"{key} = {expected}", lemma_view[key] == expected,
                       lemma_view[key]))
    for lemma, (distinct, edges, occ) in REFERENCE_NODES.items():
        got = connected.get(lemma)
        actual = (len(got[2]), got[1], got[0]) if got else None
        checks.append((f"{lemma} {distinct}/{edges}/{occ}",
                       actual == (distinct, edges, occ), actual))

    print(f"korpus {len(corpus)} vět · graf {s['uzlu']} uzlů "
          f"(UPOS:lemma) · {s['hran']} hran")
    failed = 0
    for label, ok, actual in checks:
        mark = "OK" if ok else "!!"
        failed += 0 if ok else 1
        print(f"  {mark} {label}" + ("" if ok else f" — naměřeno {actual}"))

    report = ["# Měření grafu faktů (krok 1 handoveru)", ""]
    report.append(f"- datum: {date.today().isoformat()} · verze modulu "
                  f"{__version__} · korpus {len(corpus)} vět")
    report.append("")
    report.append("## Graf podle handoveru (uzel = UPOS:lemma)")
    report.append("")
    report.append(f"- uzlů s hranou **{s['uzlu']}** · hranových instancí "
                  f"**{s['hran']}** · průměrný stupeň "
                  f"**{s['prumerny_stupen']:.2f}** · průměr různých "
                  f"sousedů **{s['prumer_ruznych']:.2f}**")
    report.append("")
    report.append("## Čtení referenčního měření (uzel = lemma)")
    report.append("")
    report.append("Referenční čísla ze 4. 8. 2026 klíčovala uzly jen "
                  "lemmatem; sloučení UPOS mění jen uzly, které jsou "
                  "víc slovními druhy najednou (stát). Hranové "
                  "instance na klíči nezávisejí a sedí přesně.")
    report.append("")
    report.append("| kontrola | stav |")
    report.append("|---|---|")
    for label, ok, actual in checks:
        report.append(f"| {label} | "
                      + ("OK" if ok else f"**{actual}**") + " |")
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
