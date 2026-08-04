"""Pole jedné věty — pracovní úroveň knihovny cb_field.

SentenceField zapouzdřuje choreografii vrstev, kterou by si jinak každý vývojář
drátoval sám (a pokaždé trochu jinak): otázkovost věty se spočítá jednou
v konstruktoru, registr se rodí s kotevními vazbami, matice se staví
dvoufázově, takže nevzniká past různě širokých vektorů. Nižší vrstvy
(build_baskets, expand_token, activations) zůstávají veřejné — jsou to
ladicí pohledy pod kapotu, ne pracovní úroveň.
"""

import sys

import numpy as np

from cb_field.registry import VerticalRegistry
from cb_field.service import (
    DEFAULT_WEIGHT,
    PREPOSITION_DIRECTIONS,
    Activations,
    Representation,
    expand_token,
    is_question,
)


class FieldBasket:
    """Koš uvnitř pole — se stejnou trojicí pohledů jako celá věta.

    metadata / complete jsou vážené aktivace řádků okna (slovníky,
    čitelné okem); array je matice vah koše s pevným tvarem 2r+1 řádků —
    za hranicí věty nuly (0.0 = žádná aktivace), střed vždy na y=r.
    Slovníky ukazují jen skutečné řádky věty, matice drží pevnou
    geometrii: čitelnost vs. porovnatelnost, každá má svůj pohled.
    """

    def __init__(self, field: "SentenceField", center: int) -> None:
        self._field = field
        self.center = center

    @property
    def r(self) -> int:
        return self._field.r

    @property
    def rows(self) -> tuple:
        """Tokeny okna; na krajích věty jich je méně."""
        left = max(0, self.center - self.r)
        return self._field.tokens[left:self.center + self.r + 1]

    @property
    def center_token(self):
        """Token, kolem kterého je koš postavený."""
        left = max(0, self.center - self.r)
        return self.rows[self.center - left]

    def _acts(self) -> tuple:
        left = max(0, self.center - self.r)
        return self._field.activations[left:self.center + self.r + 1]

    @property
    def metadata(self) -> tuple:
        """Aktivace řádků okna bez slov — {vertikála: váha} na řádek."""
        return tuple(a.weights() for a in self._acts())

    @property
    def complete(self) -> tuple:
        """Aktivace řádků okna včetně slov (WORD=…)."""
        return tuple(a.weights(Representation.COMPLETE) for a in self._acts())

    def matrix(self,
               representation: Representation = Representation.METADATA
               ) -> np.ndarray:
        """Matice koše: výřez matice věty s pevným tvarem 2r+1 řádků."""
        m = self._field.matrix(representation)
        out = np.zeros((2 * self.r + 1, m.shape[1]), dtype=m.dtype)
        for offset in range(-self.r, self.r + 1):
            j = self.center + offset
            if 0 <= j < len(self._field.tokens):
                out[offset + self.r] = m[j]
        return out

    @property
    def array(self) -> np.ndarray:
        """Matice vah koše (primární, bezeslovná reprezentace)."""
        return self.matrix()

    def __repr__(self) -> str:
        return (f"FieldBasket(center={self.center} "
                f"{self.center_token.form!r}, r={self.r}, "
                f"{len(self.rows)} řádků)")


class SentenceField:
    """Rozebraná věta jako pole: koše, aktivace, matice, obrázek.

    Vzniká z rozparsované věty (from_sentence) nebo přímo z tokenů.
    Registr jde sdílet přes věty: SentenceField.from_text(text, parser,
    registry=reg) —
    závislost se předává parametrem (§ 3), žádný globální stav.

    Obsah po konstrukci:
        tokens      tokeny věty, jak přišly z parse
        source      původní text věty (provenience; None u holých tokenů)
        r           poloměr okna košů
        question    zda je věta tázací — spočteno jednou, používáno všude
        registry    registr vertikál (vlastní, nebo předaný sdílený)
        baskets     koše (FieldBasket) — každý s pohledy metadata/complete/array
        rows        vážené řádky věty (expand_token, jeden na token)
        activations Activations řádků — už se správnou stranou Q/A
    """

    def __init__(self, tokens, r: int = 2,
                 registry: VerticalRegistry | None = None,
                 source: str | None = None) -> None:
        self.tokens = tuple(tokens)
        self.r = r
        self.source = source
        self.question = is_question(self.tokens)
        self.registry = registry if registry is not None else VerticalRegistry()
        self.rows = tuple(expand_token(t) for t in self.tokens)
        self.activations = tuple(
            Activations.from_row(row, question=self.question)
            for row in self.rows)
        self._transfer_preposition_directions()
        self.baskets = tuple(
            FieldBasket(self, center) for center in range(len(self.tokens)))
        self._matrix_cache: dict = {}

    def _transfer_preposition_directions(self) -> None:
        """Předložka daruje směr svému jádru (hrana case → hlava).

        Přenos, ne kopie: activations() směr na ADP řádku neemituje,
        takže po přenosu ho nese jen jádro. V zatřeseném koši (P-A spec
        kroku 4) tak směr patří jménu — „do Brna" kotví Brno jako cíl,
        i když předložka v pytli sousedí s čímkoli.
        """
        id_to_index = {t.id: i for i, t in enumerate(self.tokens)}
        for token in self.tokens:
            if token.upos != "ADP" or token.deprel != "case":
                continue
            for case in ((token.feats or {}).get("Case") or "").split(","):
                direction = PREPOSITION_DIRECTIONS.get((token.lemma, case))
                if direction and token.head in id_to_index:
                    head = id_to_index[token.head]
                    # Předložka u tázacího slova kvalifikuje neznámou:
                    # „kolem čeho" se ptá i na směr — kotva jde na
                    # stranu otázky (QANCHOR), ne odpovědi.
                    side = "QANCHOR" if any(
                        k.startswith("QANCHOR=")
                        for k in self.activations[head].weights())                         else "ANCHOR"
                    self.activations[head].graft(
                        f"{side}={direction}", DEFAULT_WEIGHT)
                    break

    @classmethod
    def from_sentence(cls, sentence, r: int = 2,
                      registry: VerticalRegistry | None = None) -> "SentenceField":
        """Z věty z cb_udpipe (ParsedSentence: má .tokens a .source)."""
        return cls(sentence.tokens, r=r, registry=registry,
                   source=getattr(sentence, "source", None))

    @classmethod
    def from_text(cls, text: str, parser, r: int = 2,
                  registry: VerticalRegistry | None = None) -> "SentenceField":
        """Rozparsuje text a postaví z něj pole — hlavní vstup pro vývoj.

        Pole je jedna věta. Text s více větami je hlasitá chyba, ne tiché
        vzetí první — volající má věty rozdělit a stavět pole po větách.
        Parser se předává parametrem (§ 3): žádné skryté vytváření
        klienta uvnitř.
        """
        sentences = parser.parse(text=text).sentences
        if len(sentences) != 1:
            raise ValueError(
                f"text má {len(sentences)} vět; pole je jedna věta — "
                f"rozděl text a stav pole na každou zvlášť")
        return cls.from_sentence(sentences[0], r=r, registry=registry)

    # --- matice ---------------------------------------------------------

    def matrix(self,
               representation: Representation = Representation.METADATA
               ) -> np.ndarray:
        """Matice věty: řádek na slovo, sloupec na vertikálu registru.

        Dvoufázově schválně: nejdřív registr vyroste přes všechny řádky,
        teprve pak se vektorizuje — všechny řádky mají touž šířku
        a jednou přidělené sloupce se nikdy nepřečíslují.

        Cache: obsah věty se po konstrukci nemění a RŮST registru
        sloupce nepřečíslovává, takže postavená matice smí být jen UŽŠÍ
        než aktuální registr (konzument doplňuje šířku nulami — nula =
        žádná aktivace, § registr spread). Bez cache stála přestavba
        matic celé měření: každá otázka ji stavěla znovu pro všechny
        věty korpusu.

        ZMĚNA OBSAZENÍ osy (promoce, krok 3) ale sloupcům mění význam —
        matice proto nese verzi osy a tohle je ta jediná funkce, která
        ji při čtení porovná: cache z cizí verze se odmítne použít
        a matice se přestaví z aktivací (ty jsou klíčované jmény,
        přeobsazení je nerozbije).
        """
        cached = self._matrix_cache.get(representation)
        if cached is not None and cached[0] == self.registry.axis_version:
            return cached[1]
        for act in self.activations:
            for key in act.weights(representation):
                self.registry.add(key)
        built = np.stack([
            act.as_array(self.registry, representation, grow=False)
            for act in self.activations])
        built.setflags(write=False)      # sdílená cache se nemutuje
        self._matrix_cache[representation] = (self.registry.axis_version,
                                             built)
        return built

    @property
    def metadata(self) -> tuple:
        """Aktivace všech řádků bez slov — {vertikála: váha} na řádek."""
        return tuple(a.weights() for a in self.activations)

    @property
    def complete(self) -> tuple:
        """Aktivace všech řádků včetně slov (WORD=…)."""
        return tuple(a.weights(Representation.COMPLETE)
                     for a in self.activations)

    @property
    def array(self) -> np.ndarray:
        """Matice vah věty (primární, bezeslovná reprezentace).

        Táž trojice pohledů jako u koše: metadata / complete / array —
        struktura se opakuje na obou úrovních.
        """
        return self.matrix()

    # --- obrázek --------------------------------------------------------

    def show(self):
        """Publikuje pole do kukátka (viewer na 127.0.0.1:42301).

        Zápis proběhne i bez běžící služby kukátka — jen se vypíše,
        čím ji spustit. Vrací cestu publikovaného souboru.
        """
        from cb_field.viewer import (CURRENT_PATH, HOST, PORT,
                                     _viewer_alive, _write_current)
        path = _write_current(self.baskets, CURRENT_PATH,
                              source=self.source, question=self.question)
        if not _viewer_alive():
            print(f"pozn.: kukátko na http://{HOST}:{PORT}/ neodpovídá — "
                  f"spusť ho: ./run-python -m cb_field.viewer",
                  file=sys.stderr)
        return path

    def __repr__(self) -> str:
        return (f"SentenceField({len(self.tokens)} tokenů, r={self.r}, "
                f"question={self.question}, "
                f"registr {len(self.registry)} vertikál)")
