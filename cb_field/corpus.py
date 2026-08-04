"""Korpus — posloupnost polí nad JEDNÍM registrem.

Proč vlastní třída, když je korpus „jen seznam vět": tři věci, které se
jinak drátují ručně a pokaždé trochu jinak.

**Jedna osa.** Registr se sdílí přes všechna pole. Bez toho by každá věta
měla vlastní číslování sloupců a matice dvou vět by se nedaly porovnat —
což je přesně to, co má korpus umožnit.

**Hranice odstavců.** Kontext přes sousední věty (r_sentences) nesmí
přetéct z jednoho odstavce do druhého: souvětí o dálnici a souvětí
o gravitaci spolu nesousedí významem, jen shodou zápisu. Korpus proto
u každé věty drží marker dokumentu a `document_span` z něj dělá meze.

**Přestavba bez parseru.** Promoce mění osu (přibudou custom vertikály)
a všechna pole se musí postavit znovu — ale z týchž tokenů. `regenerate()`
proto nikdy neparsuje: parsování je drahé a hlavně by mohlo vrátit jiný
rozbor, takže by se změřila změna, která nevznikla promocí.
"""

from cb_field.field import SentenceField
from cb_field.registry import VerticalRegistry
from cb_field.service import Representation


class Corpus:
    """Posloupnost SentenceField nad sdíleným registrem.

    Chová se jako sekvence: `len(corpus)`, `corpus[12]`, `for pole in
    corpus`. Závislosti se předávají parametrem (§ 3) — parser se nikdy
    nevytváří uvnitř, chodí do metod, které ho opravdu potřebují.

    Obsah po konstrukci:
        registry     sdílená osa všech vět (append-only)
        r            poloměr okna košů, předává se polím
        r_sentences  poloměr větného kontextu (drží se pro čtenáře pole;
                     hranice dokumentu ho zastaví — viz document_span)
        documents    marker dokumentu pro každou větu, ve stejném pořadí
    """

    def __init__(self, r: int = 2, r_sentences: int = 0,
                 registry: VerticalRegistry | None = None) -> None:
        self.r = r
        self.r_sentences = r_sentences
        self.registry = registry if registry is not None else VerticalRegistry()
        #: Provenience: jméno fixace → pozice jejích vět v korpusu.
        #: Jméno je neprůhledný identifikátor (princip 7) — slouží jen
        #: k převodu indexů otázek na pozice ve složeném korpusu.
        self.positions: dict[str, tuple] = {}
        self._fields: list[SentenceField] = []
        self._documents: list[int] = []
        self._named: dict[str, int] = {}
        self._next_document = 0

    # --- přidávání ------------------------------------------------------

    def add_sentence(self, sentence, document=None) -> SentenceField:
        """Přidá rozparsovanou větu (má .tokens, volitelně .source)."""
        field = SentenceField.from_sentence(sentence, r=self.r,
                                            registry=self.registry)
        self._pripoj(field, document)
        return field

    def add_text(self, text: str, parser, document=None) -> SentenceField:
        """Rozparsuje text a přidá ho jako JEDNU větu.

        Text s víc větami je hlasitá chyba, ne tiché vzetí první — kdo má
        odstavec, volá `add_document`.
        """
        field = SentenceField.from_text(text, parser, r=self.r,
                                        registry=self.registry)
        self._pripoj(field, document)
        return field

    def add_document(self, text: str, parser, document=None) -> list:
        """Rozparsuje souvislý text a přidá VŠECHNY jeho věty jako blok.

        Věty dostanou společný marker — jsou to sousedé, mezi kterými smí
        téct kontext. Parsuje se text vcelku: věta vytržená z odstavce se
        může sama rozdělit jinak.
        """
        marker = self._marker(document) if document is not None \
            else self._nove_id()
        fields = []
        for sentence in parser.parse(text=text).sentences:
            field = SentenceField.from_sentence(sentence, r=self.r,
                                                registry=self.registry)
            self._fields.append(field)
            self._documents.append(marker)
            self._osa(field)
            fields.append(field)
        return fields

    # --- dokumenty ------------------------------------------------------

    @property
    def documents(self) -> tuple:
        """Marker dokumentu pro každou větu (v pořadí korpusu)."""
        return tuple(self._documents)

    def document_span(self, position: int) -> tuple:
        """Meze souvislého bloku, ve kterém věta leží — [start, stop).

        Slouží čtení kontextu: `r_sentences` se ořeže o tyhle meze, takže
        okno nikdy nepřeteče do cizího odstavce.
        """
        if not 0 <= position < len(self._fields):
            raise IndexError(f"věta {position} v korpusu není "
                             f"({len(self._fields)} vět)")
        marker = self._documents[position]
        start = position
        while start > 0 and self._documents[start - 1] == marker:
            start -= 1
        stop = position + 1
        while stop < len(self._documents) and self._documents[stop] == marker:
            stop += 1
        return start, stop

    # --- přestavba ------------------------------------------------------

    def regenerate(self) -> None:
        """Přestaví všechna pole z tokenů proti AKTUÁLNÍ ose.

        Bez parsování a bez dotyku markerů: mění se jen to, co registr
        mezitím začal aktivovat (typicky custom vertikály po promoci).
        """
        self._fields = [
            SentenceField(field.tokens, r=self.r, registry=self.registry,
                          source=field.source)
            for field in self._fields]
        for field in self._fields:
            self._osa(field)

    # --- sekvence -------------------------------------------------------

    def __len__(self) -> int:
        return len(self._fields)

    def __getitem__(self, position):
        return self._fields[position]

    def __iter__(self):
        return iter(self._fields)

    def __repr__(self) -> str:
        return (f"Corpus({len(self._fields)} vět, "
                f"{len(set(self._documents))} dokumentů, r={self.r}, "
                f"registr {len(self.registry)} vertikál)")

    # --- vnitřek --------------------------------------------------------

    def _pripoj(self, field: SentenceField, document) -> None:
        self._fields.append(field)
        self._documents.append(self._marker(document))
        self._osa(field)

    def _osa(self, field: SentenceField) -> None:
        """Doplní osu o vertikály věty hned při přidání.

        Bez toho by registr rostl až při prvním `matrix()` a matice vět
        by měly různou šířku podle toho, v jakém pořadí si je kdo
        vyžádal — přesně ta past, kvůli které korpus existuje. Registruje
        se COMPLETE (tedy i WORD=), protože slovní vrstvu potřebuje
        promoce: custom slot vzniká z osy, ne mimo ni.
        """
        for act in field.activations:
            for key in act.weights(Representation.COMPLETE):
                self.registry.add(key)

    def _marker(self, document) -> int:
        """Marker pro pojmenovaný dokument; bez jména dostane věta svůj."""
        if document is None:
            return self._nove_id()
        if document not in self._named:
            self._named[document] = self._nove_id()
        return self._named[document]

    def _nove_id(self) -> int:
        cislo = self._next_document
        self._next_document += 1
        return cislo
