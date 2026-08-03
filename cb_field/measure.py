"""Měření extrakční vrstvy na zmraženém testbedu.

Spuštění:  ./run-python -m cb_field.measure

Čte tests/data/testbed-kdo-kde-kdy.txt (zmražený v gitu), postaví korpus
nad sdíleným registrem a změří T2 (šablony/středy) pro mřížku konfigurací
pák: vertikály (plné × R2) a maskování středu (uvnitř × mimo). Výsledek
vypíše a zapíše do docs/mereni.md — číslo bez zapsané verze dat je
nesrovnatelné, proto se ukládá i otisk testbedu.

Potřebuje běžící službu cb-udpipe (měření, ne test — testy služby
nepotřebují).
"""

import hashlib
import sys
from datetime import date
from pathlib import Path

from cb_field import __version__
from cb_field.corpus import Corpus
from cb_field.templates import R2_PREFIXES, TemplateBank, default_centers

MODULE_DIR = Path(__file__).resolve().parent
TESTBED = MODULE_DIR / "tests" / "data" / "testbed-kdo-kde-kdy.txt"
REPORT = MODULE_DIR / "docs" / "mereni.md"

#: Mřížka konfigurací: (název, vertikály, střed). Prahy hodnocení T2
#: podle README-EXTRAKCNI_VRSTVA § 5: ≤0,2 zdravé · ≤0,5 přijatelné ·
#: >0,7 okno nezobecňuje.
CONFIGS = (
    ("plné vertikály · střed uvnitř", None, "in"),
    ("plné vertikály · střed mimo", None, "out"),
    ("R2 vertikály · střed uvnitř", R2_PREFIXES, "in"),
    ("R2 vertikály · střed mimo", R2_PREFIXES, "out"),
)


def verdict(ratio: float) -> str:
    if ratio <= 0.2:
        return "zdravé zobecnění"
    if ratio <= 0.5:
        return "přijatelné"
    if ratio <= 0.7:
        return "hraniční"
    return "okno nezobecňuje"


def main() -> None:
    from cb_udpipe import UdpipeClient

    lines = [ln.strip() for ln in TESTBED.read_text(encoding="utf-8")
             .splitlines() if ln.strip()]
    digest = hashlib.sha256(TESTBED.read_bytes()).hexdigest()[:12]

    parser = UdpipeClient()
    corpus = Corpus()
    for line in lines:
        corpus.add_text(line, parser)
    for field in corpus:
        field.matrix()          # nechá registr dorůst — kvůli hlášené šířce os

    tokens_total = sum(len(f.tokens) for f in corpus)
    centers_total = sum(len(default_centers(f)) for f in corpus)

    rows = []
    banks = {}
    for name, verticals, center in CONFIGS:
        bank = TemplateBank(verticals=verticals, center=center)
        bank.add_corpus(corpus)
        banks[name] = bank
        rows.append((name, bank.templates, bank.centers,
                     bank.ratio(), bank.shared()))

    print(f"testbed: {len(lines)} vět · {tokens_total} tokenů · "
          f"{centers_total} středů (R1) · otisk {digest}")
    print(f"registr po korpusu: {len(corpus.registry)} vertikál\n")
    for name, templates, centers, ratio, shared in rows:
        print(f"  {name:<34} šablon {templates:>3} / středů {centers} · "
              f"T2 = {ratio:.2f} ({verdict(ratio)}) · sdílených {shared}")

    # druhá mřížka: páky r (R4) a kanonizace pořadí (mitigace S1),
    # na konfiguraci R2 vertikály · střed mimo
    corpora = {2: corpus}
    for radius in (1, 3):
        c = Corpus(r=radius)
        for line in lines:
            c.add_text(line, parser)
        corpora[radius] = c
    rows2 = []
    for radius in (1, 2, 3):
        for order in ("linear", "canon"):
            bank = TemplateBank(verticals=R2_PREFIXES, center="out",
                                order=order)
            bank.add_corpus(corpora[radius])
            rows2.append((f"r={radius} · {order}", bank.templates,
                          bank.centers, bank.ratio(), bank.shared()))
    print()
    for name, templates, centers, ratio, shared in rows2:
        print(f"  {name:<34} šablon {templates:>3} / středů {centers} · "
              f"T2 = {ratio:.2f} ({verdict(ratio)}) · sdílených {shared}")

    best = min(rows + rows2, key=lambda r: r[3])
    print(f"\nnejlepší T2: {best[0]} — {best[3]:.2f}")
    best_conf = min(rows, key=lambda r: r[3])
    print("\nnejčastější šablony (R2 · střed mimo · r=2):")
    for tid, count, examples in banks[best_conf[0]].top(5):
        forms = ", ".join(f"{form} ({source})" for source, form in
                          [(s, f) for s, f in examples])
        print(f"  šablona {tid}: {count}× — např. {forms}")

    report = ["# Měření cb_field — testbed kdo-kde-kdy", ""]
    report.append(f"- datum: {date.today().isoformat()}")
    report.append(f"- verze modulu: {__version__}")
    report.append(f"- data: {TESTBED.name} · {len(lines)} vět · "
                  f"{tokens_total} tokenů · otisk sha256:{digest}")
    report.append(f"- středy podle R1 (výchozí varianta): {centers_total}")
    report.append(f"- registr po korpusu: {len(corpus.registry)} vertikál")
    report.append("")
    report.append("## T2 — poměr šablon k středům (jediný test schopný "
                  "koncept vyvrátit)")
    report.append("")
    report.append("| konfigurace | šablon | středů | T2 | hodnocení | "
                  "sdílených šablon |")
    report.append("|---|---|---|---|---|---|")
    for name, templates, centers, ratio, shared in rows:
        report.append(f"| {name} | {templates} | {centers} | {ratio:.2f} "
                      f"| {verdict(ratio)} | {shared} |")
    report.append("")
    report.append("## Páky r (R4) a kanonizace pořadí (mitigace S1) — "
                  "R2 vertikály, střed mimo")
    report.append("")
    report.append("| konfigurace | šablon | středů | T2 | hodnocení | "
                  "sdílených šablon |")
    report.append("|---|---|---|---|---|---|")
    for name, templates, centers, ratio, shared in rows2:
        report.append(f"| {name} | {templates} | {centers} | {ratio:.2f} "
                      f"| {verdict(ratio)} | {shared} |")
    report.append("")
    report.append("Prahy dle README-EXTRAKCNI_VRSTVA § 5: ≤0,2 zdravé · "
                  "≤0,5 přijatelné · >0,7 okno nezobecňuje. Čísla se "
                  "nesmí ohýbat po měření — když nevyhoví, mění se páky "
                  "(R2, r, profil středu), ne prahy.")
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nzapsáno: {REPORT.relative_to(MODULE_DIR.parent)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
