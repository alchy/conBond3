"""Vyhodnocení propojení na etalonu otázek — s diagnózou růstového zákona.

Spuštění:  ./run-python -m cb_field.evaluate

Čte zmražený testbed a etalon, pustí match() a každý výsledek oznámkuje.
Chyby klasifikuje podle README-PROPOJENI § 5: SLABÁ (d > 0 → učení) /
NEPŘESNÁ (d == 0 → růst os) / NEPOKRYTÁ (správná odpověď nekandiduje).
Funkce build_corpus/load_etalon/evaluate_corpus používá i učicí protokol
(cb_field.learning). Potřebuje běžící službu cb-udpipe.
"""

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

from cb_field import __version__
from cb_field.corpus import Corpus
from cb_field.field import SentenceField
from cb_field.matching import EPSILON, THETA, match
from cb_field.service import Representation

MODULE_DIR = Path(__file__).resolve().parent
TESTBED = MODULE_DIR / "tests" / "data" / "testbed-kdo-kde-kdy.txt"
ETALON = MODULE_DIR / "tests" / "data" / "etalon-otazky.jsonl"
ETALON_KORPUSY = (MODULE_DIR / "tests" / "data"
                  / "etalon-otazky-korpusy.jsonl")
REPORT = MODULE_DIR / "docs" / "mereni-propojeni.md"
REPORT_KORPUSY = MODULE_DIR / "docs" / "mereni-propojeni-korpusy.md"


def build_complex_corpus(parser, r: int = 1, r_sentences: int = 0):
    """Korpus komplexních textů (zákon/fyzika/spisovatelé) — viz
    measure_corpora; potřebuje pořízené soubory (fetch-korpusy.sh).

    Souvislý text: věty jednoho souboru jsou si sousedy, takže do koše
    smí přitéct kontext (r_sentences).
    """
    from cb_field.measure_corpora import DOMAINS, build, ingest
    sentences = []
    for names in DOMAINS.values():
        for name in names:
            parsed, _errors, _digests = ingest(parser, (name,))
            sentences.extend((name, s) for s in parsed)
    corpus, _skipped = build(sentences, r=r, r_sentences=r_sentences)
    return corpus


def load_etalon_korpusy() -> list:
    return [json.loads(line) for line
            in ETALON_KORPUSY.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def build_corpus(parser, r: int = 1, r_sentences: int = 0) -> Corpus:
    """Korpus ze zmraženého testbedu (jedna věta na řádek).

    Věty testbedu jsou navzájem nezávislé, takže každá je vlastní
    dokument — sousedství na řádcích není souvislost a r_sentences tu
    nemá co přitéct (na rozdíl od korpusů souvislého textu).
    """
    corpus = Corpus(r=r, r_sentences=r_sentences)
    for line in TESTBED.read_text(encoding="utf-8").splitlines():
        if line.strip():
            corpus.add_text(line.strip(), parser)
    return corpus


def load_etalon() -> list:
    return [json.loads(line) for line
            in ETALON.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _bag(sentence, corpus, center):
    matrix = sentence.matrix(Representation.COMPLETE)
    left = max(0, center - corpus.r)
    padded = np.zeros(len(corpus.registry), dtype=np.float32)
    row = matrix[left:center + corpus.r + 1].sum(axis=0)
    padded[:len(row)] = row
    return padded


def diagnose(result, expected_lemma, corpus):
    """SLABÁ (d>0) / NEPŘESNÁ (d==0) / NEPOKRYTÁ — viz spec § 5."""
    winner = result.best
    correct = [c for c in result.candidates
               if c.token.lemma == expected_lemma]
    if not correct:
        return "NEPOKRYTÁ", None
    d = float(np.linalg.norm(
        _bag(winner.sentence, corpus, winner.center)
        - _bag(correct[0].sentence, corpus, correct[0].center)))
    return ("SLABÁ" if d > 1e-6 else "NEPŘESNÁ"), round(d, 3)


def evaluate_corpus(corpus, etalon, parser, theta=None):
    """Oznámkuje celý etalon; vrací (counts, přesnost, mlčení, detaily).

    theta: řez pro NEVÍM; None = výchozí THETA z matching (kalibrovaný
    řez předává učicí protokol po kalibraci na trénovací sadě).
    """
    counts = {"SPRÁVNĚ": 0, "SLABÁ": 0, "NEPŘESNÁ": 0, "NEPOKRYTÁ": 0,
              "DOTAZ": 0, "NEVÍM-chybné": 0,
              "MLČENÍ-správné": 0, "FALEŠNÁ": 0, "DOTAZ-nezodp.": 0}
    details = []
    for entry in etalon:
        question = SentenceField.from_text(entry["otazka"], parser,
                                           r=corpus.r,
                                           registry=corpus.registry)
        result = match(question, corpus,
                       theta=THETA if theta is None else theta)
        expected = entry["odpoved_lemma"]
        if entry["zodpoveditelna"]:
            if result.outcome == "odpoved":
                if result.best.token.lemma == expected:
                    grade = "SPRÁVNĚ"
                else:
                    grade, _d = diagnose(result, expected, corpus)
            elif result.outcome == "dotaz":
                grade = "DOTAZ"
            else:
                grade = "NEVÍM-chybné"
        else:
            grade = {"nevim": "MLČENÍ-správné",
                     "dotaz": "DOTAZ-nezodp."}.get(result.outcome, "FALEŠNÁ")
        counts[grade] += 1
        best = result.best
        details.append((entry["otazka"], expected, grade,
                        best.token.form if best else "—",
                        f"{best.score:.2f}" if best else "—",
                        best.sentence.source if best else "—",
                        best.top_nodes if best else ()))
    answerable = sum(1 for e in etalon if e["zodpoveditelna"])
    unanswerable = len(etalon) - answerable
    presnost = counts["SPRÁVNĚ"] / answerable if answerable else 0.0
    mlceni = (counts["MLČENÍ-správné"] / unanswerable
              if unanswerable else 0.0)
    return counts, presnost, mlceni, details


def main() -> None:
    from cb_udpipe import UdpipeClient

    korpusy = "korpusy" in sys.argv[1:]
    parser = UdpipeClient()
    if korpusy:
        corpus = build_complex_corpus(parser)
        etalon = load_etalon_korpusy()
        etalon_path, report_path = ETALON_KORPUSY, REPORT_KORPUSY
    else:
        corpus = build_corpus(parser)
        etalon = load_etalon()
        etalon_path, report_path = ETALON, REPORT
    counts, presnost, mlceni, details = evaluate_corpus(
        corpus, etalon, parser)

    answerable = sum(1 for e in etalon if e["zodpoveditelna"])
    unanswerable = len(etalon) - answerable
    digest_t = hashlib.sha256(TESTBED.read_bytes()).hexdigest()[:12]
    digest_e = hashlib.sha256(etalon_path.read_bytes()).hexdigest()[:12]

    print(f"etalon: {len(etalon)} otázek ({answerable} zodpověditelných) · "
          f"korpus {len(corpus)} vět · θ={THETA} ε={EPSILON}")
    print(f"přesnost@1: {counts['SPRÁVNĚ']}/{answerable} = {presnost:.2f}")
    print(f"NEVÍM-správnost: {counts['MLČENÍ-správné']}/{unanswerable} "
          f"= {mlceni:.2f}")
    print(f"rozklad: {counts}\n")
    for otazka, expected, grade, answer, score, _source, _nodes in details:
        mark = "✓" if grade in ("SPRÁVNĚ", "MLČENÍ-správné") else "✗" \
            if grade in ("FALEŠNÁ", "NEPŘESNÁ", "NEPOKRYTÁ",
                         "NEVÍM-chybné", "SLABÁ") else "?"
        print(f"  {mark} [{grade:<15}] {otazka:<38} → {answer:<10} "
              f"(oček. {expected})  {score}")

    title = ("# Měření propojení — etalon nad komplexními korpusy"
             if korpusy else
             "# Měření propojení (4a, ruční W) — etalon otázek")
    report = [title, ""]
    report.append(f"- datum: {date.today().isoformat()} · verze modulu "
                  f"{__version__} · θ={THETA} · ε={EPSILON} · r={corpus.r}")
    report.append(f"- data: testbed sha256:{digest_t} · "
                  f"etalon sha256:{digest_e} ({len(etalon)} otázek)")
    report.append("")
    report.append("| metrika | hodnota |")
    report.append("|---|---|")
    report.append(f"| přesnost@1 (zodpověditelné) | "
                  f"{counts['SPRÁVNĚ']}/{answerable} = {presnost:.2f} |")
    report.append(f"| NEVÍM-správnost (nezodpověditelné) | "
                  f"{counts['MLČENÍ-správné']}/{unanswerable} "
                  f"= {mlceni:.2f} |")
    for key in ("SLABÁ", "NEPŘESNÁ", "NEPOKRYTÁ", "DOTAZ", "NEVÍM-chybné",
                "FALEŠNÁ", "DOTAZ-nezodp."):
        report.append(f"| {key} | {counts[key]} |")
    report.append("")
    report.append("| otázka | výsledek | odpověď | očekáváno | skóre |")
    report.append("|---|---|---|---|---|")
    for otazka, expected, grade, answer, score, _source, _nodes in details:
        report.append(f"| {otazka} | {grade} | {answer} | {expected} "
                      f"| {score} |")
    report.append("")
    report.append("Diagnóza řídí další krok (README-PROPOJENI § 5): "
                  "SLABÁ → učení vah (4b/4c); NEPŘESNÁ → fronta růstu os; "
                  "NEPOKRYTÁ → známé díry reprezentace (typ — krok 5, "
                  "slot kdy — krok 3).")
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nzapsáno: {report_path.relative_to(MODULE_DIR.parent)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
