"""Pole jedné věty — pracovní úroveň knihovny cb_field.

Field zapouzdřuje choreografii vrstev, kterou by si jinak každý vývojář
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
    Activations,
    Representation,
    build_baskets,
    expand_token,
    is_question,
)


class Field:
    """Pole (field) věty: koše, aktivace, matice a obrázek z jednoho místa.

    Vzniká z rozparsované věty (from_sentence) nebo přímo z tokenů.
    Registr jde sdílet přes věty: Field.from_sentence(s, registry=reg) —
    závislost se předává parametrem (§ 3), žádný globální stav.

    Obsah po konstrukci:
        tokens      tokeny věty, jak přišly z parse
        source      původní text věty (provenience; None u holých tokenů)
        r           poloměr okna košů
        question    zda je věta tázací — spočteno jednou, používáno všude
        registry    registr vertikál (vlastní, nebo předaný sdílený)
        baskets     koše posuvného okna (jeden na token)
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
        self.baskets = build_baskets(self.tokens, r=r)
        self.rows = tuple(expand_token(t) for t in self.tokens)
        self.activations = tuple(
            Activations.from_row(row, question=self.question)
            for row in self.rows)

    @classmethod
    def from_sentence(cls, sentence, r: int = 2,
                      registry: VerticalRegistry | None = None) -> "Field":
        """Z věty z cb_udpipe (ParsedSentence: má .tokens a .source)."""
        return cls(sentence.tokens, r=r, registry=registry,
                   source=getattr(sentence, "source", None))

    # --- matice ---------------------------------------------------------

    def matrix(self,
               representation: Representation = Representation.METADATA
               ) -> np.ndarray:
        """Matice věty: řádek na slovo, sloupec na vertikálu registru.

        Dvoufázově schválně: nejdřív registr vyroste přes všechny řádky,
        teprve pak se vektorizuje — všechny řádky mají touž šířku
        a jednou přidělené sloupce se nikdy nepřečíslují.
        """
        for act in self.activations:
            for key in act.weights(representation):
                self.registry.add(key)
        return np.stack([
            act.as_array(self.registry, representation, grow=False)
            for act in self.activations])

    def basket_matrix(self, center: int,
                      representation: Representation = Representation.METADATA
                      ) -> np.ndarray:
        """Matice koše: výřez matice věty s pevným tvarem 2r+1 řádků.

        Za hranicí věty jsou nulové řádky — nula je „žádná aktivace",
        takže doplnění nic netvrdí. Střed tak leží vždy na řádku r
        a koše jsou tvarově porovnatelné (fixní x i y).
        """
        if not 0 <= center < len(self.tokens):
            raise IndexError(
                f"koš {center} není; věta má {len(self.tokens)} tokenů")
        m = self.matrix(representation)
        out = np.zeros((2 * self.r + 1, m.shape[1]), dtype=m.dtype)
        for offset in range(-self.r, self.r + 1):
            j = center + offset
            if 0 <= j < len(self.tokens):
                out[offset + self.r] = m[j]
        return out

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
        return (f"Field({len(self.tokens)} tokenů, r={self.r}, "
                f"question={self.question}, "
                f"registr {len(self.registry)} vertikál)")
