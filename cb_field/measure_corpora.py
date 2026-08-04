"""Měření na komplexních textech — Nový zákon, fyzika, spisovatelé.

Spuštění:  ./run-python -m cb_field.measure_corpora

Korpusy jsou licencované a žijí mimo git (data-persistent/corpora/);
pořizuje je ./cb_field/scripts/fetch-korpusy.sh. Měří se: robustnost
průchodu (přeskočené věty s důvodem — žádná tichá díra), tvar dat
(délky vět, sloty), T2 šablon per doména, pokrytí kotvami a růst
registru. Čísla nesou otisky souborů.
"""

import hashlib
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from cb_field import __version__
from cb_field.corpus import Corpus
from cb_field.templates import R2_PREFIXES, TemplateBank, default_centers

MODULE_DIR = Path(__file__).resolve().parent
CORPORA = MODULE_DIR / "data-persistent" / "corpora"
REPORT = MODULE_DIR / "docs" / "mereni-korpusy.md"

DOMAINS = {
    "zákon": ("bible_markus.txt",),
    "fyzika": ("fyzika_gravitace.txt", "elektromotor.txt",
               "fotosyntéza.txt"),
    "spisovatelé": ("karel_čapek.txt", "jan_neruda.txt",
                    "bohumil_hrabal.txt"),
}


def ingest(parser, names):
    """Naparsuje soubory domény; vrací (věty, chyby, otisky)."""
    sentences, errors, digests = [], Counter(), []
    for name in names:
        path = CORPORA / name
        if not path.is_file():
            sys.exit(f"chybí korpus {path}\n"
                     f"pořídíš: ./cb_field/scripts/fetch-korpusy.sh")
        digests.append((name,
                        hashlib.sha256(path.read_bytes()).hexdigest()[:10]))
        for paragraph in path.read_text(encoding="utf-8").splitlines():
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            try:
                parsed = parser.parse(text=paragraph).sentences
            except Exception as error:                     # noqa: BLE001
                errors[f"parse: {type(error).__name__}"] += 1
                continue
            sentences.extend(parsed)
    return sentences, errors, digests


def build(sentences, r=1, r_sentences=0):
    """Postaví korpus; přeskočené věty počítá s důvodem (žádná tichá díra).

    sentences: věty, nebo dvojice (dokument, věta) — druhý tvar drží
    hranice textů pro r_sentences (kontext nepřetéká mezi soubory).
    """
    corpus = Corpus(r=r, r_sentences=r_sentences)
    skipped = Counter()
    for item in sentences:
        document, sentence = item if isinstance(item, tuple) \
            else (None, item)
        try:
            corpus.add_sentence(sentence, document=document)
        except ValueError as error:
            reason = "sloty feats" if "slotů" in str(error) else "ValueError"
            skipped[reason] += 1
        except Exception as error:                          # noqa: BLE001
            skipped[type(error).__name__] += 1
    return corpus, skipped


def stats(corpus):
    tokens = sum(len(f.tokens) for f in corpus)
    centers = sum(len(default_centers(f)) for f in corpus)
    anchored = sum(
        1 for f in corpus for m in f.metadata
        if any(k.startswith("ANCHOR=") for k in m))
    rows = sum(len(f.tokens) for f in corpus)
    bank = TemplateBank(verticals=R2_PREFIXES, center="out")
    bank.add_corpus(corpus)
    # vertikály přímo z dat (registr tu neroste — signatury ho nepotřebují)
    meta_keys = {k for f in corpus for m in f.metadata for k in m}
    word_keys = {k for f in corpus for c in f.complete for k in c
                 if k.startswith("WORD=") and not k.startswith("WORD=PUNCT")}
    return {
        "vet": len(corpus), "tokenu": tokens,
        "prum_delka": round(tokens / len(corpus), 1) if len(corpus) else 0,
        "stredu": centers, "sablon": bank.templates,
        "t2": round(bank.ratio(), 2),
        "kotveno": round(anchored / rows, 2) if rows else 0,
        "vertikal": len(meta_keys), "slovnik": len(word_keys),
    }


def main() -> None:
    from cb_udpipe import UdpipeClient
    parser = UdpipeClient()

    rows_out, all_digests = [], []
    combined_sentences = []
    for domain, names in DOMAINS.items():
        sentences, parse_errors, digests = ingest(parser, names)
        all_digests.extend(digests)
        corpus, skipped = build(sentences)
        combined_sentences.extend(sentences)
        s = stats(corpus)
        s["preskoceno"] = dict(skipped) or "—"
        s["chyby_parse"] = dict(parse_errors) or "—"
        rows_out.append((domain, s))
        print(f"{domain:<12} vět {s['vet']:>4} · tokenů {s['tokenu']:>6} · "
              f"prům. {s['prum_delka']:>5} tok/větu · T2 {s['t2']:.2f} · "
              f"kotveno {s['kotveno']:.2f} · přeskočeno {s['preskoceno']}")

    combined, skipped = build(combined_sentences)
    s = stats(combined)
    rows_out.append(("CELKEM", s))
    print(f"{'CELKEM':<12} vět {s['vet']:>4} · tokenů {s['tokenu']:>6} · "
          f"prům. {s['prum_delka']:>5} tok/větu · T2 {s['t2']:.2f} · "
          f"kotveno {s['kotveno']:.2f} · vertikál {s['vertikal']} · "
          f"slovník {s['slovnik']}")

    report = ["# Měření na komplexních textech (zákon · fyzika · "
              "spisovatelé)", ""]
    report.append(f"- datum: {date.today().isoformat()} · verze modulu "
                  f"{__version__} · r=1 · šablony R2/střed mimo")
    report.append("- korpusy mimo git (licence, ZDROJ.md); otisky: "
                  + " · ".join(f"{n} sha256:{d}" for n, d in all_digests))
    report.append("")
    report.append("| doména | vět | tokenů | prům. délka | středů | šablon "
                  "| T2 | kotveno | vertikál | slovník | přeskočeno |")
    report.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for domain, s in rows_out:
        report.append(
            f"| {domain} | {s['vet']} | {s['tokenu']} | {s['prum_delka']} "
            f"| {s['stredu']} | {s['sablon']} | {s['t2']:.2f} "
            f"| {s['kotveno']:.2f} | {s['vertikal']} | {s['slovnik']} "
            f"| {s.get('preskoceno', '—')} |")
    report.append("")
    report.append("T2 prahy (README-EXTRAKCNI_VRSTVA § 5): ≤0,2 zdravé · "
                  "≤0,5 přijatelné · >0,7 okno nezobecňuje. „Kotveno“ = "
                  "podíl řádků s aspoň jednou kotvou ANCHOR.")
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nzapsáno: {REPORT.relative_to(MODULE_DIR.parent)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
