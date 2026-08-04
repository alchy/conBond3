"""Sítko na kandidátní trénovací otázky (vstup: JSONL od anotátorů).

    ./run-python cb_field/scripts/validuj-trenink.py kandidati.jsonl > cista.jsonl

Anotátor (i člověk) vyrábí otázky, které se učit nedají: odpověď uniklá
do otázky, lemma, které v korpusu není, nebo otázka opisující větu.
Sítko je čistě mechanické a každý zahozený řádek vypíše na stderr
s důvodem — rozhodnutí, co s hraničními, zůstává na člověku.

Kritéria (zodpověditelné):
  1. lemma odpovědi je v korpusu (jinak se nemá co učit),
  2. lemma odpovědi NENÍ mezi lemmaty otázky (únik — grep by vyhrál),
  3. otázka nesdílí s žádnou větou korpusu víc než polovinu svých
     obsahových lemmat (opisování věty = učí grep, spec § 6),
  4. otázka je tázací (parser pozná otazník a tázací slovo).
Nezodpověditelné: odpoved_lemma musí být null a žádná věta nesmí nést
všechna obsahová lemmata otázky (to by ji dělalo zodpověditelnou).

Přepínač --mezivetne přidá pátou podmínku (pravidlo J. 2026-08-04:
*„fakta nejsou jednovětá s utrženým tématem"*): podnět a odpověď nesmí
stát v TÉŽE větě. Otázka, kterou lze zodpovědět z jedné věty, učí
systém tvar, jaký v souvislém textu není — navazovat přes hranici věty
se na ní nenaučí.
"""

import json
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent
CONTENT_UPOS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV", "NUM"}
#: Překryv se měří bez vlastních jmen: entita je ADRESA otázky (musí
#: se shodovat, jinak se otázka ptá na něco jiného), grep-test je
#: o slovese a vztahu. „Kde přišel na svět Bohumil Hrabal?" sdílí
#: s větou jen jméno — a to je dobrá parafráze, ne opis.
OVERLAP_UPOS = CONTENT_UPOS - {"PROPN"}
#: Tázací slova do překryvu nepatří: „kde" v otázce a vztažné „kde"
#: ve větě jsou různá slova (celý mechanismus QLEM stojí na tom).
INTERROGATIVES = frozenset({
    "kdo", "co", "kde", "kam", "kdy", "odkud", "kudy", "jak", "proč",
    "který", "jaký", "kolik", "čí", "dokdy", "odkdy"})


def content_lemmas(sentence, upos=CONTENT_UPOS) -> set:
    return {t.lemma.lower() for t in sentence.tokens
            if t.upos in upos and t.lemma
            and t.lemma.lower() not in INTERROGATIVES}


def main() -> None:
    sys.path.insert(0, str(MODULE_DIR.parent))
    from cb_udpipe import UdpipeClient
    from cb_field.measure_corpora import DOMAINS, ingest

    across_sentences = "--mezivetne" in sys.argv[1:]
    candidates = [json.loads(line) for line
                  in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
                  if line.strip()]
    parser = UdpipeClient()

    corpus_lemmas = set()
    sentence_lemmas = []       # (obsahová, obsahová bez vlastních jmen)
    for names in DOMAINS.values():
        parsed, _errors, _digests = ingest(parser, names)
        for sentence in parsed:
            sentence_lemmas.append((content_lemmas(sentence),
                                    content_lemmas(sentence, OVERLAP_UPOS)))
            corpus_lemmas |= {t.lemma.lower() for t in sentence.tokens
                              if t.lemma}
    print(f"korpus: {len(sentence_lemmas)} vět · {len(corpus_lemmas)} lemmat",
          file=sys.stderr)

    kept = 0
    for entry in candidates:
        question = parser.parse(text=entry["otazka"]).sentences[0]
        q_lemmas = content_lemmas(question)
        q_overlap = content_lemmas(question, OVERLAP_UPOS)
        answer = (entry.get("odpoved_lemma") or "").lower()

        def drop(reason):
            print(f"ZAHOZENO [{reason}] {entry['otazka']}"
                  f" → {entry.get('odpoved_lemma')}", file=sys.stderr)

        if entry["zodpoveditelna"]:
            if not answer:
                drop("chybí odpověď")
                continue
            if answer not in corpus_lemmas:
                drop("lemma odpovědi není v korpusu")
                continue
            if answer in q_lemmas:
                drop("únik: odpověď je v otázce")
                continue
            # Grep-test se dělá proti CÍLOVÝM větám (těm, kde odpověď
            # je) — shoda slov s nesouvisející větou z 2 912 o otázce
            # nic neříká a zahazovala by dobré parafráze.
            targets = [o for s, o in sentence_lemmas if answer in s]
            if across_sentences:
                # věta, která nese odpověď I podnět, dělá otázku
                # jednovětou — přesně to, co se nemá učit
                jednoveta = [o for s, o in sentence_lemmas
                             if answer in s and (q_overlap & o)]
                if jednoveta:
                    drop("jednovětá: podnět i odpověď v téže větě")
                    continue
            overlap = max((len(q_overlap & o) for o in targets), default=0)
            if q_overlap and overlap / len(q_overlap) > 0.5:
                drop(f"opisuje cílovou větu "
                     f"(překryv {overlap}/{len(q_overlap)})")
                continue
        else:
            if entry.get("odpoved_lemma") is not None:
                drop("nezodpověditelná s odpovědí")
                continue
            if any(q_lemmas and q_lemmas <= s for s, _o in sentence_lemmas):
                drop("věta nese všechna lemmata otázky — je zodpověditelná")
                continue
        if "?" not in entry["otazka"]:
            drop("není otázka")
            continue
        print(json.dumps(entry, ensure_ascii=False))
        kept += 1

    print(f"prošlo {kept}/{len(candidates)}", file=sys.stderr)


if __name__ == "__main__":
    main()
