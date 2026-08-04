"""Fixovaný korpus v JSON — čtení, validace, stavba pole z něj.

Korpus se fixuje v souboru proto, aby měření dvou běhů srovnávalo tatáž
data: text v souboru je zmražený, číslovaný a otázky míří na **index
věty**. Kdo změní data, změní čísla — a je to vidět v diffu, ne až
v grafu.

**Jméno souboru nenese významovou váhu** (princip 7). Program ho bere
jako neprůhledný identifikátor: žádné mapy klíčované doménou, žádné
„soubor 3xx je bible". Co má program vědět o obsahu, stojí uvnitř
souboru.

Formát je popsaný v `docs/korpus-json.md`; tady jsou pravidla, která se
z něj vynucují:

- **index věty je globální v rámci souboru**, počítá se přes bloky
  v pořadí zápisu; nezodpověditelná otázka má `sentence: null`,
- **jedna položka `sentences` = přesně jedna věta**; rozpadne-li se
  parserem na víc, je to hlasitá chyba zápisu dat — číslování by se
  rozjelo a všechna měření by tiše ukazovala jinam,
- **blok se parsuje vcelku**, když nese `text` (původní odstavec): věta
  vytržená z kontextu se dělí jinak, takže by fixace neodpovídala tomu,
  co uvidí parser za provozu,
- **blok je hranicí dokumentu** — kontext přes věty nepřeteče odstavec.

Validace souboru z příkazové řádky:

    ./run-python -m cb_field.corpusfile cb_field/tests/data/korpus/*.json
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from cb_field.corpus import Corpus

#: Verze formátu, které tenhle kód rozumí. Cizí verze je hlasitá chyba:
#: tiché přečtení by znamenalo měřit něco jiného, než si člověk myslí.
FORMAT_VERSION = 1


@dataclass(frozen=True)
class CorpusBlock:
    """Souvislý odstavec: jeho věty a (volitelně) původní znění.

    `topic` je popisek pro člověka — program na něm nesmí nic stavět.
    """

    sentences: tuple
    text: str | None = None
    topic: str | None = None


@dataclass(frozen=True)
class CorpusQuestion:
    """Otázka mířící na index věty v témž souboru (nebo v odkazovaném)."""

    text: str
    sentence: int | None
    answer_lemma: str | None
    answerable: bool


@dataclass(frozen=True)
class CorpusFile:
    """Přečtená fixace. `corpus` je jméno cizího souboru u otázkových."""

    path: Path
    blocks: tuple
    questions: tuple
    corpus: str | None = None

    @property
    def name(self) -> str:
        """Neprůhledný identifikátor fixace — jméno souboru."""
        return self.path.name

    @property
    def sentences(self) -> tuple:
        """Věty všech bloků za sebou; pořadí = globální indexy."""
        return tuple(s for block in self.blocks for s in block.sentences)


def load_corpus_file(path) -> CorpusFile:
    """Přečte a zvaliduje fixaci. Každá vada je ValueError s adresou.

    Kontroluje se tvar (klíče, typy), verze formátu a rozsahy indexů;
    `answer_lemma` proti lemmatům věty se kontrolovat nedá bez parseru —
    to dělá `main()` na příkazové řádce, kam parser patří.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    kde = path.name

    verze = data.get("format_version")
    if verze != FORMAT_VERSION:
        raise ValueError(
            f"{kde}: format_version {verze!r}, umím {FORMAT_VERSION}")

    blocks = []
    for i, syrovy in enumerate(data.get("blocks", [])):
        sentences = syrovy.get("sentences")
        if not isinstance(sentences, list) or not sentences:
            raise ValueError(f"{kde}: blok {i} nemá neprázdné 'sentences'")
        blocks.append(CorpusBlock(sentences=tuple(sentences),
                                  text=syrovy.get("text"),
                                  topic=syrovy.get("topic")))

    pocet = sum(len(b.sentences) for b in blocks)
    odkaz = data.get("corpus")
    questions = []
    for i, syrova in enumerate(data.get("questions", [])):
        otazka = CorpusQuestion(
            text=syrova["text"],
            sentence=syrova.get("sentence"),
            answer_lemma=syrova.get("answer_lemma"),
            answerable=bool(syrova.get("answerable", False)))
        if otazka.answerable and otazka.sentence is None:
            raise ValueError(
                f"{kde}: otázka {i} je zodpověditelná, ale nemá index věty")
        # Index cizího souboru se tady zvalidovat nedá — proti čemu by se
        # měřil? Zkontroluje ho add_to_corpus, až bude odkazovaný korpus
        # po ruce.
        if otazka.sentence is not None and odkaz is None:
            if not 0 <= otazka.sentence < pocet:
                raise ValueError(
                    f"{kde}: otázka {i} míří na větu {otazka.sentence}, "
                    f"soubor jich má {pocet}")
        questions.append(otazka)

    return CorpusFile(path=path, blocks=tuple(blocks),
                      questions=tuple(questions), corpus=odkaz)


def add_to_corpus(corpus: Corpus, corpus_file: CorpusFile, parser) -> tuple:
    """Přidá věty fixace do korpusu; vrátí jejich pozice v korpusu.

    Pozice != index v souboru: korpus bývá složený z víc fixací za sebou.
    Návratová n-tice je právě ten převod (index v souboru → pozice).

    Blok s polem `text` se parsuje vcelku a rozpad se musí rovnat
    položkám počtem i zněním; blok bez něj se parsuje po větách.
    """
    pozice = []
    for i, block in enumerate(corpus_file.blocks):
        kde = f"{corpus_file.name}: blok {i}"
        if block.text:
            fields = corpus.add_document(block.text, parser)
            _over_rozpad(fields, block, kde)
        else:
            marker = f"{corpus_file.name}#{i}"
            fields = [corpus.add_text(veta, parser, document=marker)
                      for veta in block.sentences]
        pozice.extend(range(len(corpus) - len(fields), len(corpus)))
    return tuple(pozice)


def build_corpus(paths, parser, r: int = 2, r_sentences: int = 0) -> Corpus:
    """Složí korpus z několika fixací nad JEDNÍM registrem.

    Otázkové soubory (`corpus: "…"`) nenesou věty — do korpusu se
    nepřidávají, jejich otázky se mapují přes pozice odkazovaného
    souboru (`corpus.positions`).
    """
    corpus = Corpus(r=r, r_sentences=r_sentences)
    for path in paths:
        corpus_file = load_corpus_file(path)
        if corpus_file.corpus is not None:
            continue
        corpus.positions[corpus_file.name] = add_to_corpus(
            corpus, corpus_file, parser)
    return corpus


def etalon_entries(corpus_file: CorpusFile, positions) -> list:
    """Otázky ve tvaru etalonu, s pozicí věty s odpovědí v korpusu.

    `answer_position` je zemní pravda na úrovni VĚTY — proti ní se měří
    recall („byla věta s odpovědí mezi kandidáty?"), tedy metrika, která
    nezávisí na tom, který token systém nakonec vybral.
    """
    polozky = []
    for otazka in corpus_file.questions:
        if otazka.sentence is None:
            pozice = None
        elif not 0 <= otazka.sentence < len(positions):
            raise ValueError(
                f"{corpus_file.name}: otázka míří na větu {otazka.sentence}, "
                f"odkazovaný korpus jich má {len(positions)}")
        else:
            pozice = positions[otazka.sentence]
        polozky.append({
            "otazka": otazka.text,
            "odpoved_lemma": otazka.answer_lemma,
            "zodpoveditelna": otazka.answerable,
            "answer_position": pozice})
    return polozky


def _over_rozpad(fields, block: CorpusBlock, kde: str) -> None:
    """Rozpad odstavce se musí rovnat položkám počtem i zněním."""
    rozpad = tuple(f.source for f in fields)
    if len(rozpad) != len(block.sentences):
        raise ValueError(
            f"{kde}: text se rozpadl na {len(rozpad)} vět, "
            f"položek je {len(block.sentences)} — číslování by se rozjelo")
    for j, (mel, je) in enumerate(zip(block.sentences, rozpad)):
        if mel.strip() != (je or "").strip():
            raise ValueError(
                f"{kde}, věta {j}: fixováno {mel!r}, parser dal {je!r}")


def main(argv=None) -> int:
    """Validace souborů z příkazové řádky.

    Kontroluje navíc to, co bez parseru nejde: že se položky opravdu
    nerozpadají a že `answer_lemma` je mezi lemmaty cílové věty.
    """
    from cb_udpipe import UdpipeClient

    cesty = [Path(a) for a in (argv if argv is not None else sys.argv[1:])]
    if not cesty:
        print("použití: ./run-python -m cb_field.corpusfile <soubor>…",
              file=sys.stderr)
        return 2

    parser = UdpipeClient()
    chyb = 0
    for path in cesty:
        try:
            corpus_file = load_corpus_file(path)
            corpus = Corpus()
            pozice = add_to_corpus(corpus, corpus_file, parser) \
                if corpus_file.blocks else ()
            chybna = _over_lemmata(corpus, corpus_file, pozice)
            stav = "OK" if not chybna else f"{len(chybna)} vadných lemmat"
            print(f"{path.name}: {len(corpus_file.sentences)} vět, "
                  f"{len(corpus_file.questions)} otázek — {stav}")
            for zprava in chybna:
                print(f"    {zprava}")
            chyb += len(chybna)
        except (ValueError, KeyError, OSError) as e:
            print(f"{path.name}: CHYBA — {e}", file=sys.stderr)
            chyb += 1
    return 1 if chyb else 0


def _over_lemmata(corpus: Corpus, corpus_file: CorpusFile,
                  positions) -> list:
    """Je `answer_lemma` mezi lemmaty věty, na kterou otázka míří?"""
    if not positions:
        return []
    chybna = []
    for i, otazka in enumerate(corpus_file.questions):
        if otazka.sentence is None or otazka.answer_lemma is None:
            continue
        pozice = positions[otazka.sentence]
        lemmata = {t.lemma for t in corpus[pozice].tokens}
        if otazka.answer_lemma not in lemmata:
            chybna.append(
                f"otázka {i}: lemma {otazka.answer_lemma!r} není ve větě "
                f"{otazka.sentence} ({corpus[pozice].source!r})")
    return chybna


if __name__ == "__main__":
    sys.exit(main())
