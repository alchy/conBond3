"""Korpus polí — víc vět nad jedním registrem.

Corpus drží pole vět se **sdílenou osou sloupců**: všechna pole vznikají
nad týmž registrem (závislost parametrem, § 3), takže jejich matice jsou
porovnatelné a šablony se počítají přes celý korpus, ne po větě.
"""

from cb_field.field import SentenceField
from cb_field.registry import VerticalRegistry


class Corpus:
    """Posloupnost polí (vět) nad sdíleným registrem vertikál.

    Obsah:
        registry  sdílený registr — osa sloupců všech polí
        fields    pole vět v pořadí přidání
        r         poloměr okna košů (týž pro celý korpus)
    """

    def __init__(self, registry: VerticalRegistry | None = None,
                 r: int = 2, r_sentences: int = 0) -> None:
        self.registry = registry if registry is not None else VerticalRegistry()
        self.r = r
        #: Druhý poloměr: kolik sousedních VĚT přitéká do koše (r pro
        #: slovo × r pro větu, zadání J.). 0 = koš končí větou. Kontext
        #: teče jen uvnitř dokumentu — sousedství přes hranici textu
        #: není souvislost, jen pořadí v souboru.
        self.r_sentences = r_sentences
        self.fields: list = []
        self.documents: list = []      # index dokumentu na větu

    def add_text(self, text: str, parser, document=None) -> SentenceField:
        """Rozparsuje jednu větu a přidá ji do korpusu.

        Platí totéž co u SentenceField.from_text: jedna věta na volání;
        víc vět je hlasitá chyba — korpus se plní po větách vědomě.
        """
        field = SentenceField.from_text(text, parser, r=self.r,
                                        registry=self.registry)
        self.fields.append(field)
        self.documents.append(document)
        return field

    def add_sentence(self, sentence, document=None) -> SentenceField:
        """Přidá už rozebranou větu (ParsedSentence).

        document: značka textu, ze kterého věta je (název souboru,
        kapitola). Věty s touž značkou jsou si sousedy pro r_sentences;
        None = věta stojí sama (nezávislá věta testbedu).
        """
        field = SentenceField.from_sentence(sentence, r=self.r,
                                            registry=self.registry)
        self.fields.append(field)
        self.documents.append(document if document is not None
                              else object())   # samostatný dokument
        return field

    def add_document(self, text: str, parser, document=None) -> list:
        """Rozparsuje souvislý text (odstavec, kapitolu) a přidá všechny
        jeho věty. Na rozdíl od add_text tu víc vět není chyba — dokument
        se po větách rozpadá vědomě tady, ne tichým vzetím první.

        Věty jednoho volání jsou si navzájem sousedy pro r_sentences.
        """
        marker = document if document is not None else object()
        return [self.add_sentence(s, document=marker)
                for s in parser.parse(text=text).sentences]

    def __len__(self) -> int:
        return len(self.fields)

    def __iter__(self):
        return iter(self.fields)

    def __getitem__(self, i: int) -> SentenceField:
        return self.fields[i]

    def __repr__(self) -> str:
        return (f"Corpus({len(self.fields)} vět, r={self.r}, "
                f"registr {len(self.registry)} vertikál)")
