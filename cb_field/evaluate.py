"""Vyhodnocení propojení na etalonu otázek — baseline 4a s diagnózou.

Spuštění:  ./run-python -m cb_field.evaluate

Čte zmražený testbed a etalon otázek, pustí match() s ručním W (axiomy)
a každý výsledek oznámkuje. Chyby klasifikuje podle růstového zákona
(README-PROPOJENI § 5): SLABÁ (d > 0 → do učení) vs. NEPŘESNÁ (d == 0 →
do růstu os) vs. NEPOKRYTÁ (kandidát vůbec neprošel branou). Píše
docs/mereni-propojeni.md; čísla nesou otisky dat.

Potřebuje běžící službu cb-udpipe (měření, ne test).
"""

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

from cb_field import __version__
from cb_field.corpus import Corpus
from cb_field.matching import EPSILON, THETA, candidate_centers, match
from cb_field.service import Representation

MODULE_DIR = Path(__file__).resolve().parent
TESTBED = MODULE_DIR / "tests" / "data" / "testbed-kdo-kde-kdy.txt"
ETALON = MODULE_DIR / "tests" / "data" / "etalon-otazky.jsonl"
REPORT = MODULE_DIR / "docs" / "mereni-propojeni.md"


def _bag(sentence, corpus, center):
    matrix = sentence.matrix(Representation.COMPLETE)
    left = max(0, center - corpus.r)
    n = len(corpus.registry)
    padded = np.zeros(n, dtype=np.float32)
    row = matrix[left:center + corpus.r + 1].sum(axis=0)
    padded[:len(row)] = row
    return padded


def diagnose(result, expected_lemma, corpus):
    """Klasifikace chyby podle P-E: SLABÁ (d>0) / NEPŘESNÁ (d==0) /
    NEPOKRYTÁ (správná odpověď mezi kandidáty vůbec není)."""
    winner = result.best
    correct = [c for c in result.candidates
               if c.token.lemma == expected_lemma]
    if not correct:
        return "NEPOKRYTÁ", None
    best_correct = correct[0]
    d = float(np.linalg.norm(
        _bag(winner.sentence, corpus, winner.center)
        - _bag(best_correct.sentence, corpus, best_correct.center)))
    return ("SLABÁ" if d > 1e-6 else "NEPŘESNÁ"), round(d, 3)


def main() -> None:
    from cb_udpipe import UdpipeClient

    parser = UdpipeClient()
    corpus = Corpus(r=1)
    lines = [ln.strip() for ln in TESTBED.read_text(encoding="utf-8")
             .splitlines() if ln.strip()]
    for line in lines:
        corpus.add_text(line, parser)
    etalon = [json.loads(ln) for ln in ETALON.read_text(encoding="utf-8")
              .splitlines() if ln.strip()]

    counts = {"SPRÁVNĚ": 0, "SLABÁ": 0, "NEPŘESNÁ": 0, "NEPOKRYTÁ": 0,
              "DOTAZ": 0, "NEVÍM-chybné": 0,
              "MLČENÍ-správné": 0, "FALEŠNÁ": 0, "DOTAZ-nezodp.": 0}
    detaily = []

    for entry in etalon:
        from cb_field.field import SentenceField
        question = SentenceField.from_text(entry["otazka"], parser,
                                           r=corpus.r,
                                           registry=corpus.registry)
        result = match(question, corpus)
        expected = entry["odpoved_lemma"]

        if entry["zodpoveditelna"]:
            if result.outcome == "odpoved":
                if result.best.token.lemma == expected:
                    grade = "SPRÁVNĚ"
                else:
                    grade, d = diagnose(result, expected, corpus)
                    grade_note = f"d={d}"
            elif result.outcome == "dotaz":
                grade = "DOTAZ"
            else:
                grade = "NEVÍM-chybné"
        else:
            if result.outcome == "nevim":
                grade = "MLČENÍ-správné"
            elif result.outcome == "dotaz":
                grade = "DOTAZ-nezodp."
            else:
                grade = "FALEŠNÁ"
        counts[grade] += 1
        best = result.best
        detaily.append((entry["otazka"], expected, grade,
                        best.token.form if best else "—",
                        f"{best.score:.2f}" if best else "—",
                        best.sentence.source if best else "—",
                        best.top_nodes if best else ()))

    zodp = [d for d, e in zip(detaily, etalon) if e["zodpoveditelna"]]
    nezodp_n = sum(1 for e in etalon if not e["zodpoveditelna"])
    presnost = counts["SPRÁVNĚ"] / len(zodp) if zodp else 0
    mlceni = counts["MLČENÍ-správné"] / nezodp_n if nezodp_n else 0

    digest_t = hashlib.sha256(TESTBED.read_bytes()).hexdigest()[:12]
    digest_e = hashlib.sha256(ETALON.read_bytes()).hexdigest()[:12]

    print(f"etalon: {len(etalon)} otázek ({len(zodp)} zodpověditelných) · "
          f"korpus {len(corpus)} vět · θ={THETA} ε={EPSILON}")
    print(f"přesnost@1: {counts['SPRÁVNĚ']}/{len(zodp)} = {presnost:.2f}")
    print(f"NEVÍM-správnost: {counts['MLČENÍ-správné']}/{nezodp_n} "
          f"= {mlceni:.2f}")
    print(f"rozklad: {counts}\n")
    for otazka, expected, grade, answer, score, source, nodes in detaily:
        mark = "✓" if grade in ("SPRÁVNĚ", "MLČENÍ-správné") else "✗" \
            if grade in ("FALEŠNÁ", "NEPŘESNÁ", "NEPOKRYTÁ",
                         "NEVÍM-chybné", "SLABÁ") else "?"
        print(f"  {mark} [{grade:<15}] {otazka:<38} → {answer:<10} "
              f"(oček. {expected})  {score}")

    report = ["# Měření propojení (4a, ruční W) — etalon otázek", ""]
    report.append(f"- datum: {date.today().isoformat()} · verze modulu "
                  f"{__version__} · θ={THETA} · ε={EPSILON} · r={corpus.r}")
    report.append(f"- data: testbed sha256:{digest_t} ({len(lines)} vět) · "
                  f"etalon sha256:{digest_e} ({len(etalon)} otázek)")
    report.append("")
    report.append(f"| metrika | hodnota |")
    report.append(f"|---|---|")
    report.append(f"| přesnost@1 (zodpověditelné) | "
                  f"{counts['SPRÁVNĚ']}/{len(zodp)} = {presnost:.2f} |")
    report.append(f"| NEVÍM-správnost (nezodpověditelné) | "
                  f"{counts['MLČENÍ-správné']}/{nezodp_n} = {mlceni:.2f} |")
    for key in ("SLABÁ", "NEPŘESNÁ", "NEPOKRYTÁ", "DOTAZ", "NEVÍM-chybné",
                "FALEŠNÁ", "DOTAZ-nezodp."):
        report.append(f"| {key} | {counts[key]} |")
    report.append("")
    report.append("| otázka | výsledek | odpověď | očekáváno | skóre |")
    report.append("|---|---|---|---|---|")
    for otazka, expected, grade, answer, score, source, nodes in detaily:
        report.append(f"| {otazka} | {grade} | {answer} | {expected} "
                      f"| {score} |")
    report.append("")
    report.append("Diagnóza řídí další krok (README-PROPOJENI § 5): "
                  "SLABÁ → učení vah (4b/4c); NEPŘESNÁ → fronta růstu os; "
                  "NEPOKRYTÁ → známé díry reprezentace (kandidátní středy, "
                  "typ — krok 5, slot kdy — krok 3).")
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nzapsáno: {REPORT.relative_to(MODULE_DIR.parent)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
