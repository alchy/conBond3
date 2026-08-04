"""Pořizovací skript: doména Nový zákon (bez Marka) do korpusu cb_field.

Spuštění (opakovaně, dokud nejsou hotové všechny knihy — viz IDEMPOTENCE):

    ./run-python cb_field/scripts/fetch-novy-zakon.py

Pořizovací skript (§ 19 politiky): čte ~/Projects/conBond2/data/raw/
bible_*.txt (moderní český překlad, licencovaný text — do gitu nesmí,
ZDROJ.md) a zapisuje po jedné knize data-persistent/korpus/korpus-3NN.json
v kanonickém pořadí Nového zákona (NT_BOOKS). Markovo evangelium se
nepoužívá — je v korpusu už jako korpus-101.json (fetch-korpusy.sh) a
duplikovalo by se. Exodus a Žalmy se nepoužívají vůbec, patří do Starého
zákona.

Blok = odstavec zdroje (jeden neprázdný řádek txt — v těchto souborech
vychází řádek na kapitolu), věty vznikají rozparsováním CELÉHO odstavce
parserem cb-udpipe (stejné pravidlo jako corpusfile.add_to_corpus a
preved-korpusy-json.py: věta vytržená z kontextu se může rozdělit jinak,
a fixace by se rozjela).

IDEMPOTENCE: parsování ~10 000 nových vět trvá dlouho, proto skript
zpracovává knihy jednu po druhé a hlídá si čas (BUDGET_S) — po jeho
vyčerpání běh sám skončí, i když nejsou hotové všechny knihy. Kniha,
jejíž cílový soubor už existuje a je validní JSON, se přeskočí beze čtení
zdroje. Zápis je atomický (.tmp + os.replace), takže přerušený běh nikdy
nenechá za sebou napůl zapsaný soubor, který by vypadal jako hotový.
Opakované spuštění tedy pokračuje tam, kde minulé skončilo.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cb_field.corpus import Corpus                    # noqa: E402
from cb_field.corpusfile import add_to_corpus, load_corpus_file  # noqa: E402

SOURCE = Path.home() / "Projects" / "conBond2" / "data" / "raw"
TARGET = Path(__file__).resolve().parents[1] / "data-persistent" / "korpus"

# Kolik vteřin smí jeden běh nanejvýš zpracovávat knihy, než sám skončí
# (zadání J.: běhy pod ~8 minut). Kontroluje se PŘED každou knihou, ne
# uprostřed jejího zpracování — kniha se zapisuje vždy celá, nebo vůbec.
BUDGET_S = 360

# Kanonické pořadí Nového zákona bez Marka (zadání J. 2026-08-04). Marek
# je už v korpusu jako korpus-101.json (fetch-korpusy.sh), Exodus a Žalmy
# patří do Starého zákona a do domény "zákon" (Nový zákon) nepatří vůbec.
# Číslo dává jméno výstupnímu souboru, jméno souboru zdroje se čte
# z conBond2, popisek je jen pro člověka v logu.
NT_BOOKS = (
    (301, "bible_matous.txt", "Matouš"),
    (302, "bible_lukas.txt", "Lukáš"),
    (303, "bible_jan.txt", "Jan"),
    (304, "bible_skutky_apoštolské.txt", "Skutky apoštolské"),
    (305, "bible_římanům.txt", "Římanům"),
    (306, "bible_1_korintským.txt", "1. Korintským"),
    (307, "bible_2_korintským.txt", "2. Korintským"),
    (308, "bible_galaťanům.txt", "Galaťanům"),
    (309, "bible_efezským.txt", "Efezským"),
    (310, "bible_filipským.txt", "Filipským"),
    (311, "bible_koloským.txt", "Koloským"),
    (312, "bible_1_tesalonickým.txt", "1. Tesalonickým"),
    (313, "bible_2_tesalonickým.txt", "2. Tesalonickým"),
    (314, "bible_1_timoteovi.txt", "1. Timoteovi"),
    (315, "bible_2_timoteovi.txt", "2. Timoteovi"),
    (316, "bible_titovi.txt", "Titovi"),
    (317, "bible_filemonovi.txt", "Filemonovi"),
    (318, "bible_židům.txt", "Židům"),
    (319, "bible_jakub.txt", "Jakub"),
    (320, "bible_1_petr.txt", "1. Petr"),
    (321, "bible_2_petr.txt", "2. Petr"),
    (322, "bible_1_jan.txt", "1. Jan"),
    (323, "bible_2_jan.txt", "2. Jan"),
    (324, "bible_3_jan.txt", "3. Jan"),
    (325, "bible_juda.txt", "Juda"),
    (326, "bible_zjevení.txt", "Zjevení"),
)


def already_done(path: Path) -> bool:
    """Cílový soubor existuje a je to validní JSON => kniha je hotová.

    Nekontroluje se proti parseru (to dělá až závěrečná validace přes
    cb_field.corpusfile) — jen aby přerušený/poškozený zápis z minulého
    běhu nevypadal jako hotová kniha.
    """
    if not path.is_file():
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return True


def convert(parser, source_name: str, number: int) -> Path:
    """Naparsuje jednu knihu a atomicky ji zapíše do korpus-<number>.json."""
    source = SOURCE / source_name
    if not source.is_file():
        sys.exit(f"chybí zdroj: {source}\n"
                 f"(licencovaný text mimo git, viz ZDROJ.md — "
                 f"pořizuje se z conBond2)")
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
        blocks.append({"topic": f"{source_name} odstavec {line_number}",
                       "text": paragraph,
                       "sentences": sentences})
    path = TARGET / f"korpus-{number}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(
        {"format_version": 1, "language": "cs",
         "blocks": blocks, "questions": []},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def main() -> None:
    from cb_udpipe import UdpipeClient
    parser = UdpipeClient()
    TARGET.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    done = skipped = 0
    total_blocks = total_sentences = 0
    for number, source_name, title in NT_BOOKS:
        path = TARGET / f"korpus-{number}.json"
        if already_done(path):
            skipped += 1
            continue
        if time.monotonic() - start > BUDGET_S:
            print(f"čas běhu vyčerpán ({BUDGET_S}s) — zbytek knih "
                 f"doděláme v dalším spuštění")
            break

        path = convert(parser, source_name, number)

        # zpětná kontrola hned po zápisu (stejně jako ostatní pořizovací
        # skripty): soubor se znovu načte a rozpad musí sedět počtem
        # i zněním vět, jinak by číslování, na které jednou budou mířit
        # otázky, bylo nespolehlivé
        corpus_file = load_corpus_file(path)
        corpus = Corpus(r=1)
        add_to_corpus(corpus, corpus_file, parser)
        total_blocks += len(corpus_file.blocks)
        total_sentences += len(corpus)
        done += 1
        print(f"{path.name}: {len(corpus_file.blocks)} bloků · "
             f"{len(corpus)} vět · {title} ({source_name})")

    print(f"\ntenhle běh: {done} knih zpracováno, {skipped} přeskočeno "
         f"(už hotové), {total_blocks} bloků, {total_sentences} vět")
    remaining = len(NT_BOOKS) - done - skipped
    if remaining:
        print(f"zbývá {remaining} knih — spusť skript znovu")
    else:
        print("hotovo — všechny knihy Nového zákona (bez Marka) "
             "zpracovány")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
