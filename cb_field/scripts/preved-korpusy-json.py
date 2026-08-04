"""Převod licencovaných korpusů (txt) do fixovaného JSON formátu.

Spuštění:  ./run-python cb_field/scripts/preved-korpusy-json.py

Pořizovací skript (§ 19 politiky): čte data-persistent/corpora/*.txt
(mimo git, licence — ZDROJ.md) a zapisuje data-persistent/korpus/
korpus-1NN.json v pořadí dnešního ingestu (measure_corpora.DOMAINS),
aby se pořadí vět v korpusu nezměnilo. Jména souborů jsou pořadová
a významově prázdná; jméno zdroje nese jen lidský popisek bloku.

Blok = odstavec zdroje (řádek), věty = rozpad odstavce parserem.
Otázky se nepřevádějí — existující etalony JSONL stojí vedle.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cb_field.corpus import Corpus                    # noqa: E402
from cb_field.corpusfile import add_to_corpus, load_corpus_file  # noqa: E402
from cb_field.measure_corpora import CORPORA, DOMAINS  # noqa: E402

TARGET = CORPORA.parent / "korpus"


def convert(parser, name: str, number: int) -> Path:
    source = CORPORA / name
    blocks = []
    for line_number, paragraph in enumerate(
            source.read_text(encoding="utf-8").splitlines(), start=1):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        sentences = [s.source or " ".join(t.form for t in s.tokens)
                     for s in parser.parse(text=paragraph).sentences]
        if not sentences:
            continue
        blocks.append({"topic": f"{name} odstavec {line_number}",
                       "text": paragraph,
                       "sentences": sentences})
    path = TARGET / f"korpus-{number}.json"
    path.write_text(json.dumps(
        {"format_version": 1, "language": "cs",
         "blocks": blocks, "questions": []},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    from cb_udpipe import UdpipeClient
    parser = UdpipeClient()
    TARGET.mkdir(parents=True, exist_ok=True)
    total = 0
    number = 101
    for names in DOMAINS.values():
        for name in names:
            path = convert(parser, name, number)
            # zpětná kontrola: soubor se načte a každá položka je
            # při samostatném rozparsování zase přesně jedna věta
            corpus_file = load_corpus_file(path)
            corpus = Corpus(r=1)
            add_to_corpus(corpus, corpus_file, parser)
            total += len(corpus)
            print(f"{path.name}: {len(corpus_file.blocks)} bloků · "
                  f"{len(corpus)} vět · zdroj {name}")
            number += 1
    print(f"celkem vět: {total}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
