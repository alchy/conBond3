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
class CorpusFile:
    """Načtený fixovaný korpus: bloky vět a otázky na jejich indexy."""

    path: Path
    blocks: tuple                      # blok = n-tice textů vět
    questions: tuple

    @property
    def sentences(self) -> tuple:
        """Věty v globálním číslování souboru (0 od začátku, přes bloky)."""
        return tuple(text for block in self.blocks for text in block)


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
        blocks.append(tuple(sentences))
    total = sum(len(block) for block in blocks)
    questions = []
    for q, entry in enumerate(data.get("questions", [])):
        question = CorpusQuestion(
            text=entry["text"], sentence=entry.get("sentence"),
            answer_lemma=entry.get("answer_lemma"),
            answerable=bool(entry.get("answerable")))
        if question.answerable:
            if not isinstance(question.sentence, int) \
                    or not 0 <= question.sentence < total:
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
                      questions=tuple(questions))


def add_to_corpus(corpus: Corpus, corpus_file: CorpusFile,
                  parser) -> tuple:
    """Přidá věty souboru do korpusu; vrací pozice po globálních indexech.

    Blok = dokument (kontext r_sentences nepřetéká hranici bloku);
    marker hranice je anonymní objekt — jméno souboru významovou váhu
    nést nesmí. Rozpad položky na víc vět parserem je hlasitá chyba
    se jménem souboru a globálním indexem věty: číslování, na které
    míří otázky, by se tiše rozjelo.
    """
    positions = []
    index = 0
    for block in corpus_file.blocks:
        marker = object()
        for text in block:
            try:
                corpus.add_text(text, parser, document=marker)
            except ValueError as error:
                raise ValueError(
                    f"{corpus_file.path}: věta {index} ({text!r}) — "
                    f"{error}") from None
            positions.append(len(corpus) - 1)
            index += 1
    return tuple(positions)


def _validate(paths) -> int:
    """Validace datových souborů proti parseru; vrací počet chyb."""
    from cb_udpipe import UdpipeClient
    parser = UdpipeClient()
    failures = 0
    for path in paths:
        corpus_file = load_corpus_file(path)
        corpus = Corpus(r=1)
        try:
            positions = add_to_corpus(corpus, corpus_file, parser)
        except ValueError as error:
            print(f"!! {error}")
            failures += 1
            continue
        for q, question in enumerate(corpus_file.questions):
            if not question.answerable:
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
