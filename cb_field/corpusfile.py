"""Fixovaný korpus v JSON — číslované věty, bloky, otázky na indexy.

Formát a pravidla: docs/korpus-json.md (zadání J. 2026-08-04). Jméno
souboru je neprůhledný identifikátor — loader z něj nic nevyvozuje
a nikam ho nepropaguje (hranice bloků nesou anonymní markery, ne
jména). Soubor nese format_version (§ 14 politiky): cizí verze se
odmítne hlasitě, ne hádáním.

Validace datového souboru proti parseru (1 položka = 1 věta,
answer_lemma leží v cílové větě):

    ./run-python -m cb_field.corpusfile tests/data/korpus/*.json
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from cb_field.corpus import Corpus

FORMAT_VERSION = 1


@dataclass(frozen=True)
class CorpusQuestion:
    """Otázka mířící na globální index věty souboru (None = bez odpovědi)."""

    text: str
    sentence: int | None
    answer_lemma: str | None
    answerable: bool


@dataclass(frozen=True)
class CorpusBlock:
    """Blok = souvislý text; položky jsou jeho očíslovaný rozpad.

    text: původní odstavec (převod z txt). Parsuje se ON, ne spojení
    položek — věty vytržené z kontextu se mohou rozdělit jinak.
    """

    sentences: tuple
    text: str | None = None


@dataclass(frozen=True)
class CorpusFile:
    """Načtený fixovaný korpus: bloky vět a otázky na jejich indexy.

    corpus: jméno souboru s větami, na jehož indexy míří otázky
    (krok F návrhu — otázky k UŽ fixovanému korpusu). Soubor s
    odkazem bloky mít nemusí; rozsah indexů se validuje až proti
    odkazovanému souboru (_validate ho vyhledá vedle sebe a v
    obvyklých úložištích korpusů).
    """

    path: Path
    blocks: tuple                      # n-tice CorpusBlock
    questions: tuple
    corpus: str | None = None

    @property
    def sentences(self) -> tuple:
        """Věty v globálním číslování souboru (0 od začátku, přes bloky)."""
        return tuple(text for block in self.blocks
                     for text in block.sentences)


def load_corpus_file(path: Path) -> CorpusFile:
    """Načte a zkontroluje soubor fixovaného korpusu.

    Kontroluje formát, verzi a odkazy otázek: index v rozsahu,
    zodpověditelná otázka má answer_lemma, nezodpověditelná nemá
    index. Chyba dat je ValueError se jménem souboru — data se
    opravují u zdroje, ne obcházejí při čtení.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    version = data.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(
            f"{path}: neznámá verze formátu korpusu {version!r}; "
            f"tahle čtečka umí {FORMAT_VERSION}")
    blocks = []
    for b, block in enumerate(data.get("blocks", [])):
        sentences = block.get("sentences", [])
        if not sentences or not all(
                isinstance(s, str) and s.strip() for s in sentences):
            raise ValueError(f"{path}: blok {b} nemá neprázdné věty")
        blocks.append(CorpusBlock(sentences=tuple(sentences),
                                  text=block.get("text")))
    reference = data.get("corpus")
    total = sum(len(block.sentences) for block in blocks)
    questions = []
    for q, entry in enumerate(data.get("questions", [])):
        question = CorpusQuestion(
            text=entry["text"], sentence=entry.get("sentence"),
            answer_lemma=entry.get("answer_lemma"),
            answerable=bool(entry.get("answerable")))
        if question.answerable:
            if not isinstance(question.sentence, int) \
                    or (reference is None
                        and not 0 <= question.sentence < total):
                raise ValueError(
                    f"{path}: otázka {q} míří na větu "
                    f"{question.sentence!r}, soubor má {total} vět")
            if not question.answer_lemma:
                raise ValueError(
                    f"{path}: zodpověditelná otázka {q} nemá answer_lemma")
        elif question.sentence is not None:
            raise ValueError(
                f"{path}: nezodpověditelná otázka {q} má index věty — "
                f"buď je zodpověditelná, nebo index nemá co znamenat")
        questions.append(question)
    return CorpusFile(path=path, blocks=tuple(blocks),
                      questions=tuple(questions), corpus=reference)


def add_to_corpus(corpus: Corpus, corpus_file: CorpusFile,
                  parser) -> tuple:
    """Přidá věty souboru do korpusu; vrací pozice po globálních indexech.

    Blok se parsuje VCELKU — věta vytržená z odstavce se může sama
    o sobě rozdělit jinak (dvojtečka s uvozovkou), zatímco v kontextu
    bloku parser dělí stejně jako původní ingest po odstavcích. Rozpad
    se pak rovná položkám: jiný POČET vět i jiné ZNĚNÍ věty je hlasitá
    chyba s adresou — číslování, na které míří otázky, se nesmí tiše
    rozjet.

    Blok = dokument (kontext r_sentences nepřetéká hranici bloku);
    marker hranice je anonymní objekt — jméno souboru významovou váhu
    nést nesmí.
    """
    positions = []
    index = 0
    for b, block in enumerate(corpus_file.blocks):
        marker = object()
        items = block.sentences
        parsed = parser.parse(
            text=block.text or " ".join(items)).sentences
        if len(parsed) != len(items):
            raise ValueError(
                f"{corpus_file.path}: blok {b} má {len(items)} položek, "
                f"parser z něj udělal {len(parsed)} vět (věty "
                f"{index}–{index + len(items) - 1})")
        for text, sentence in zip(items, parsed):
            source = getattr(sentence, "source", None)
            if source and " ".join(source.split()) \
                    != " ".join(text.split()):
                raise ValueError(
                    f"{corpus_file.path}: věta {index} zní {text!r}, "
                    f"parser vrátil {source!r} — fixace se rozjela")
            corpus.add_sentence(sentence, document=marker)
            positions.append(len(corpus) - 1)
            index += 1
    return tuple(positions)


def build_corpus(paths, parser, r: int = 1,
                 r_sentences: int = 0) -> Corpus:
    """Korpus z fixovaných souborů v daném pořadí (závislosti
    parametrem, § 3). Pořadí určuje volající — glob pro rostoucí
    baseline, výslovný seznam pro zmraženou referenci."""
    corpus = Corpus(r=r, r_sentences=r_sentences)
    for path in paths:
        add_to_corpus(corpus, load_corpus_file(path), parser)
    return corpus


def etalon_entries(corpus_file: CorpusFile,
                   positions: tuple | None = None) -> list:
    """Otázky souboru ve tvaru etalonu (evaluate/learning).

    positions: pozice vět v korpusu (výstup add_to_corpus) — s nimi
    zodpověditelná otázka nese i answer_position, tedy zemní pravdu
    na úrovni VĚTY. Token ji má v odpoved_lemma; obě metriky se pak
    dají počítat vedle sebe.
    """
    entries = []
    for question in corpus_file.questions:
        entry = {"otazka": question.text,
                 "odpoved_lemma": question.answer_lemma,
                 "zodpoveditelna": question.answerable}
        if question.answerable and positions is not None:
            entry["answer_position"] = positions[question.sentence]
        entries.append(entry)
    return entries


def _resolve_reference(path: Path, name: str) -> Path:
    """Najde odkazovaný soubor s větami: vedle souboru a v obvyklých
    úložištích korpusů (data-persistent, zmražená testovací data)."""
    module = Path(__file__).resolve().parent
    for candidate in (path.parent / name,
                      module / "data-persistent" / "korpus" / name,
                      module / "tests" / "data" / "korpus" / name):
        if candidate.is_file():
            return candidate
    raise ValueError(f"{path}: odkazovaný korpus {name!r} nenalezen")


def _validate(paths) -> int:
    """Validace datových souborů proti parseru; vrací počet chyb."""
    from cb_udpipe import UdpipeClient
    parser = UdpipeClient()
    failures = 0
    for path in paths:
        corpus_file = load_corpus_file(path)
        target = corpus_file
        if corpus_file.corpus:
            target = load_corpus_file(
                _resolve_reference(Path(path), corpus_file.corpus))
        corpus = Corpus(r=1)
        try:
            positions = add_to_corpus(corpus, target, parser)
        except ValueError as error:
            print(f"!! {error}")
            failures += 1
            continue
        for q, question in enumerate(corpus_file.questions):
            if not question.answerable:
                continue
            if not 0 <= question.sentence < len(positions):
                print(f"!! {path}: otázka {q} míří na větu "
                      f"{question.sentence}, korpus má "
                      f"{len(positions)} vět")
                failures += 1
                continue
            field = corpus[positions[question.sentence]]
            lemmas = {t.lemma for t in field.tokens}
            if question.answer_lemma not in lemmas:
                print(f"!! {path}: otázka {q} ({question.text}) — "
                      f"answer_lemma {question.answer_lemma!r} není "
                      f"mezi lemmaty věty {question.sentence}: "
                      f"{sorted(lemmas)}")
                failures += 1
        answerable = sum(1 for q in corpus_file.questions if q.answerable)
        print(f"{path.name}: {len(corpus_file.blocks)} bloků · "
              f"{len(corpus_file.sentences)} vět · "
              f"{len(corpus_file.questions)} otázek "
              f"({answerable} zodpověditelných)")
    return failures


if __name__ == "__main__":
    files = [Path(p) for p in sys.argv[1:]]
    if not files:
        sys.exit("použití: ./run-python -m cb_field.corpusfile "
                 "<soubor.json>…")
    sys.exit(1 if _validate(files) else 0)
