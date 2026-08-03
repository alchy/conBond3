"""Učení vah propojení — fáze 4b (Hebb) a 4c (kontrastivně na etalonu).

Spuštění celého protokolu s měřením před/po každou fází:

    ./run-python -m cb_field.learning

Koeficient propojení je učitelný parametr součinu (P-B spec): čím
silnější propojení, tím větší parametr. Učí se výhradně hrany se
zdrojem hebb/etalon — axiomy jsou definice jazyka a registr je chrání.
Protiváha (§ 6 spec): učení, které zvedne přesnost a shodí
NEVÍM-správnost, se nepřijímá — výsledek se hlásí, ne zamlčí.

Pozn. k poctivosti: 4c se v této fázi ladí a měří na TÉMŽE etalonu
(jiný zatím není) — číslo po 4c je tedy horní odhad, ne generalizace.
Zapsáno i v reportu; rozdělení etalonu přijde s jeho růstem.
"""

import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from cb_field.matching import MATCH_PREFIXES, candidate_centers, match

MODULE_DIR = Path(__file__).resolve().parent
REPORT = MODULE_DIR / "docs" / "mereni-uceni.md"
REPORT_KORPUSY = MODULE_DIR / "docs" / "mereni-uceni-korpusy.md"
LEARNED = MODULE_DIR / "data-persistent" / "verticals-learned.json"
LEARNED_KORPUSY = (MODULE_DIR / "data-persistent"
                   / "verticals-learned-korpusy.json")

#: Rychlost učení a spodní práh souvýskytů pro Hebba. Startovní hodnoty
#: (registr prahů modulu); kalibruje protokol níže.
ETA_HEBB = 0.5
ETA_CONTRAST = 0.15
MIN_COOCCURRENCE = 2
MAX_EPOCHS = 3


def _semantic_bag(sentence, rows) -> dict:
    """{vertikála: váha} přes dané řádky, jen párovací vertikály."""
    bag = {}
    for i in rows:
        for key, weight in sentence.complete[i].items():
            if key.startswith(MATCH_PREFIXES) \
                    and not key.startswith("WORD=PUNCT"):
                bag[key] = bag.get(key, 0.0) + weight
    return bag


def hebb(corpus, eta: float = ETA_HEBB,
         min_count: int = MIN_COOCCURRENCE) -> dict:
    """4b: Hebbovské koeficienty ze souaktivací — „co se aktivuje spolu,
    to se propojí".

    Jednotka souaktivace je koš věty (celá věta jako pytel). Síla hrany
    je normalizovaný souvýskyt nad náhodu (NPMI ∈ −1…1) × eta — prosté
    počty by posilovaly frekvenci, ne vztah (protiváha měřítka). Hrany
    se zapisují oběma směry se zdrojem hebb; axiomy registr ochrání.
    """
    registry = corpus.registry
    bags = []
    for sentence in corpus:
        bags.append(frozenset(
            _semantic_bag(sentence, range(len(sentence.tokens)))))
    total = len(bags)
    count = Counter()
    pair_count = Counter()
    for bag in bags:
        for key in bag:
            count[key] += 1
        ordered = sorted(bag)
        for a_i, a in enumerate(ordered):
            for b in ordered[a_i + 1:]:
                pair_count[(a, b)] += 1

    added = 0
    for (a, b), n_ab in pair_count.items():
        if n_ab < min_count:
            continue
        pmi = math.log(total * n_ab / (count[a] * count[b]))
        denominator = -math.log(n_ab / total)
        npmi = pmi / denominator if denominator > 0 else 0.0
        if npmi <= 0:
            continue
        weight = max(-1.0, min(1.0, eta * npmi))
        for src, dst in ((a, b), (b, a)):
            if registry.get_link(src, dst) is None:
                added += 1
            registry.link(src, dst, weight, source="hebb")
    return {"vet": total, "paru": len(pair_count), "hran": added}


def _window_rows(sentence, center, r):
    return range(max(0, center - r), min(len(sentence.tokens),
                                         center + r + 1))


def contrastive_step(registry, question_bag: dict, correct_bag: dict,
                     wrong_bag: dict, eta: float = ETA_CONTRAST) -> int:
    """Jeden kontrastivní krok: posílit hrany otázka→správná, oslabit
    otázka→vítěz. Jen na souaktivovaných dvojicích (qᵢ·aⱼ ≠ 0); meze ±1;
    axiomy chrání registr. Vrací počet upravených hran."""
    changed = 0
    for sign, bag in ((+1.0, correct_bag), (-1.0, wrong_bag)):
        for q_key, q_weight in question_bag.items():
            for a_key, a_weight in bag.items():
                if q_key == a_key:
                    continue
                existing = registry.get_link(q_key, a_key)
                if existing and existing[1] == "axiom":
                    continue
                old = existing[0] if existing else 0.0
                new = max(-1.0, min(1.0,
                                    old + sign * eta * q_weight * a_weight))
                if new != old:
                    registry.link(q_key, a_key, new, source="etalon")
                    changed += 1
    return changed


def train_on_etalon(corpus, etalon_entries, parser,
                    eta: float = ETA_CONTRAST,
                    max_epochs: int = MAX_EPOCHS) -> dict:
    """4c: kontrastivní doladění na chybách typu SLABÁ/DOTAZ.

    Učí se jen tam, kde správná odpověď kandiduje a prohrává — přesně
    kategorie „signál existuje, jen má malý koeficient" z růstového
    zákona. NEPOKRYTÉ chyby se neučí (patří růstu os / dalším krokům).
    """
    from cb_field.field import SentenceField
    stats = {"epoch": 0, "kroku": 0, "hran": 0}
    for epoch in range(max_epochs):
        corrections = 0
        for entry in etalon_entries:
            if not entry["zodpoveditelna"]:
                continue
            question = SentenceField.from_text(
                entry["otazka"], parser, r=corpus.r,
                registry=corpus.registry)
            result = match(question, corpus)
            if not result.candidates:
                continue
            winner = result.best
            expected = entry["odpoved_lemma"]
            if winner.token.lemma == expected \
                    and result.outcome == "odpoved":
                continue
            correct = next((c for c in result.candidates
                            if c.token.lemma == expected), None)
            if correct is None:
                continue                     # NEPOKRYTÁ — učení nepatří
            q_bag = _semantic_bag(question, range(len(question.tokens)))
            correct_bag = _semantic_bag(
                correct.sentence,
                _window_rows(correct.sentence, correct.center, corpus.r))
            wrong_bag = _semantic_bag(
                winner.sentence,
                _window_rows(winner.sentence, winner.center, corpus.r))
            stats["hran"] += contrastive_step(
                corpus.registry, q_bag, correct_bag, wrong_bag, eta)
            corrections += 1
        stats["epoch"] = epoch + 1
        stats["kroku"] += corrections
        if corrections == 0:
            break
    return stats


def main() -> None:
    from cb_udpipe import UdpipeClient
    from cb_field.evaluate import (build_complex_corpus, build_corpus,
                                   evaluate_corpus, load_etalon,
                                   load_etalon_korpusy)

    korpusy = "korpusy" in sys.argv[1:]
    parser = UdpipeClient()
    if korpusy:
        corpus = build_complex_corpus(parser)
        etalon = load_etalon_korpusy()
    else:
        corpus = build_corpus(parser)
        etalon = load_etalon()

    phases = []

    def measure(label):
        counts, presnost, mlceni, _details = evaluate_corpus(
            corpus, etalon, parser)
        phases.append((label, presnost, mlceni, dict(counts)))
        print(f"{label:<28} přesnost@1 {presnost:.2f} · "
              f"NEVÍM-správnost {mlceni:.2f} · {counts}")

    measure("baseline (axiomy)")
    hebb_stats = hebb(corpus)
    print(f"4b Hebb: {hebb_stats}")
    measure("po 4b (Hebb)")
    train_stats = train_on_etalon(corpus, etalon, parser)
    print(f"4c kontrastivně: {train_stats}")
    measure("po 4c (etalon)")

    corpus.registry.save(LEARNED_KORPUSY if korpusy else LEARNED)

    baseline, final = phases[0], phases[-1]
    protivaha_ok = final[2] >= baseline[2]
    verdict = ("PŘIJATO" if protivaha_ok and final[1] >= baseline[1]
               else "NEPŘIJATO — protiváha" if not protivaha_ok
               else "NEPŘIJATO — přesnost klesla")
    print(f"\nprotiváha (NEVÍM-správnost neklesla): "
          f"{'ano' if protivaha_ok else 'NE'} → {verdict}")

    lines = ["# Měření učení vah (4b Hebb + 4c kontrastivně)"
             + (" — komplexní korpusy" if korpusy else ""), ""]
    lines.append(f"- datum: {date.today().isoformat()} · η_hebb={ETA_HEBB} "
                 f"· η_kontrast={ETA_CONTRAST} · epochy≤{MAX_EPOCHS}")
    lines.append(f"- Hebb: {hebb_stats} · kontrastivně: {train_stats}")
    lines.append(f"- POZOR: 4c laděno i měřeno na témže etalonu — číslo "
                 f"je horní odhad, ne generalizace (zapsaná mez).")
    lines.append("")
    lines.append("| fáze | přesnost@1 | NEVÍM-správnost |")
    lines.append("|---|---|---|")
    for label, presnost, mlceni, _counts in phases:
        lines.append(f"| {label} | {presnost:.2f} | {mlceni:.2f} |")
    lines.append("")
    lines.append(f"Výrok protokolu: **{verdict}** (učení, které shodí "
                 f"NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený "
                 f"registr: `data-persistent/verticals-learned.json`.")
    report_path = REPORT_KORPUSY if korpusy else REPORT
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"zapsáno: {report_path.relative_to(MODULE_DIR.parent)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
