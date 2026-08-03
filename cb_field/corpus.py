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
                 r: int = 2) -> None:
        self.registry = registry if registry is not None else VerticalRegistry()
        self.r = r
        self.fields: list = []

    def add_text(self, text: str, parser) -> SentenceField:
        """Rozparsuje jednu větu a přidá ji do korpusu.

        Platí totéž co u SentenceField.from_text: jedna věta na volání;
        víc vět je hlasitá chyba — korpus se plní po větách vědomě.
        """
        field = SentenceField.from_text(text, parser, r=self.r,
                                        registry=self.registry)
        self.fields.append(field)
        return field

    def add_sentence(self, sentence) -> SentenceField:
        """Přidá už rozebranou větu (ParsedSentence)."""
        field = SentenceField.from_sentence(sentence, r=self.r,
                                            registry=self.registry)
        self.fields.append(field)
        return field

    def __len__(self) -> int:
        return len(self.fields)

    def __iter__(self):
        return iter(self.fields)

    def __getitem__(self, i: int) -> SentenceField:
        return self.fields[i]

    def __repr__(self) -> str:
        return (f"Corpus({len(self.fields)} vět, r={self.r}, "
                f"registr {len(self.registry)} vertikál)")
