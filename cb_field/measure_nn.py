"""Experimenty zapojení NN — mosty promoce a hloubka šíření.

Spuštění:  ./run-python -m cb_field.measure_nn

Zadání J. (2026-08-04): jak zapojit NN do učení, jak škálovat, jak
řešit aktivace a výstup — předmět výzkumu, návrhy vítány. Měří se
čtyři ramena nad týmž korpusem (2 912 vět) a etalonem (40 otázek),
trénink na oddělené sadě 104 otázek (§ B6 trénink ≠ měření):

    A  baseline: axiomy, bez učení (reference)
    B  učení samotné (4c kontrastivně) — kontrolní rameno
    D  hloubka šíření k=2 a k=3 na ČISTÉM baselinu (bez učení) —
       druhá vrstva nad L, izolovaný příspěvek hloubky
    C  promoční cyklus: osy CUSTOM + mosty WORD→CUSTOM + přeučení;
       cyklus sám rozhodne přijmout/vrátit proti A
    E  hloubka k=2 NAD stavem po C — složení hloubky s promocí a učením

Každé rameno se měří trojicí přesnost × NEVÍM-správnost × dosah
(workflow § B5: číslo bez protiváhy se neuvádí).
"""

import sys
from datetime import date
from functools import partial
from pathlib import Path

from cb_field import __version__
from cb_field.graph import FactGraph
from cb_field.matching import match
from cb_field.promotion import promotion_cycle

MODULE_DIR = Path(__file__).resolve().parent
REPORT = MODULE_DIR / "docs" / "mereni-nn.md"
TRAINING = MODULE_DIR / "tests" / "data" / "trenink-otazky-korpusy.jsonl"


def _measure(corpus, etalon, parser, spread_steps=1):
    """Trojice metrik; hloubka šíření se předává match() explicitně."""
    import cb_field.evaluate as evaluate
    original = evaluate.match
    evaluate.match = partial(match, spread_steps=spread_steps)
    try:
        counts, presnost, mlceni, _details = evaluate.evaluate_corpus(
            corpus, etalon, parser)
        reach = evaluate.reach_report(corpus, etalon, parser)
    finally:
        evaluate.match = original
    return {"presnost": round(presnost, 4), "mlceni": round(mlceni, 4),
            "dosah_ok": reach["v_dosahu_ok"], "vada": -reach["vada"],
            "_counts": counts, "_mimo": reach["mimo_dosah"]}


def _public(metrics):
    return {k: v for k, v in metrics.items() if not k.startswith("_")}


def main() -> None:
    import json

    from cb_udpipe import UdpipeClient
    from cb_field.evaluate import build_complex_corpus, load_etalon_korpusy
    from cb_field.learning import train_on_etalon

    parser = UdpipeClient()
    corpus = build_complex_corpus(parser)
    etalon = load_etalon_korpusy()
    training = [json.loads(line) for line
                in TRAINING.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    registry = corpus.registry
    rows = []

    def report_arm(label, metrics, note=""):
        rows.append((label, metrics, note))
        public = _public(metrics)
        print(f"{label:<28} {public}" + (f" · {note}" if note else ""))

    # A · baseline
    baseline = _measure(corpus, etalon, parser)
    report_arm("A baseline", baseline)

    # B · učení samotné (kontrolní rameno pro C)
    baseline_state = registry.snapshot()
    stats_b = train_on_etalon(corpus, training, parser)
    metrics_b = _measure(corpus, etalon, parser)
    report_arm("B učení 4c", metrics_b,
               f"epoch {stats_b['epoch']} · hran {stats_b['hran']}")
    registry.restore(baseline_state)

    # D · hloubka šíření na čistém baselinu (bez učení)
    for steps in (2, 3):
        metrics_d = _measure(corpus, etalon, parser, spread_steps=steps)
        report_arm(f"D hloubka k={steps} (baseline)", metrics_d)

    # C · promoční cyklus (osy + mosty + přeučení), rozhodne sám
    graph = FactGraph()
    for field in corpus:
        graph.add_sentence(field)
    outcome = promotion_cycle(
        corpus, graph,
        measure=lambda c: _public(_measure(c, etalon, parser)),
        retrain=lambda c: train_on_etalon(c, training, parser))
    report_arm("C promoce+mosty+učení", outcome["po"],
               ("PŘIJATO" if outcome["prijato"] else "ODVOLÁNO")
               + f" · osy {outcome['osy']}")

    # E · složení: hloubka k=2 nad stavem po C (jen když cyklus prošel)
    if outcome["prijato"]:
        metrics_e = _measure(corpus, etalon, parser, spread_steps=2)
        report_arm("E hloubka k=2 nad C", metrics_e)

    report = ["# Experimenty zapojení NN (mosty promoce, hloubka šíření)",
              ""]
    report.append(f"- datum: {date.today().isoformat()} · verze modulu "
                  f"{__version__} · korpus {len(corpus)} vět · etalon "
                  f"{len(etalon)} otázek · trénink {len(training)} otázek "
                  f"(oddělené sady)")
    report.append("")
    report.append("| rameno | přesnost@1 | NEVÍM | dosah OK | vad | pozn. |")
    report.append("|---|---|---|---|---|---|")
    for label, metrics, note in rows:
        report.append(
            f"| {label} | {metrics['presnost']:.2f} "
            f"| {metrics['mlceni']:.2f} | {metrics['dosah_ok']} "
            f"| {-metrics['vada']} | {note} |")
    report.append("")
    report.append("Čtení: B je kontrola k C — rozdíl C−B je čistý příspěvek "
                  "promovaných os s mosty (učení mají obě ramena stejné). "
                  "D měří hloubku šíření samotnou na čistém baselinu, "
                  "E její složení se stavem po C; sloupec vad = odpověď "
                  "v dosahu, a přesto propadla (reach_report).")
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nzapsáno: {REPORT.relative_to(MODULE_DIR.parent)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
