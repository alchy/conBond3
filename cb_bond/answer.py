"""AnswerField — čtení aktivačního pole odpovědi.

**Odpověď JE pole.** Token, okno, věta a gaussovský vrchol nejsou čtyři
algoritmy, ale čtyři ČTENÍ téhož pole skóre. Který z nich je ten
správný, závisí na otázce, ne na kódu.

## Proč se čte gaussovsky

Odpověď není jeden token — je to místo, kde se souhlasné aktivace
**shlukují**. Kdo čte argmax po tokenech, vybere osamělou špičku;
kdo dělí délkou věty, vyrobí degenerát z krátkých vět (naměřeno na
12 258 větách: vyhrávala „Máš ženu?").

Gauss to řeší bez normalizace a bez prahu — na každém kandidátovi
sedí zvon a zvony se sčítají:

    jádro σ=1,5:   k0 = 0,267 · k1 = 0,213 · k2 = 0,110

    shluk 1,0+1,0+1,0 na pozicích 11–13:
        vrchol = 1·k1 + 1·k0 + 1·k1 = 0,69
    osamělá špička 1,5:
        vrchol = 1,5·k0 = 0,40

Shluk tedy poráží o polovinu silnější špičku — a je to vlastnost
tvaru, ne pravidlo, které by někdo dopisoval.

## Past konvoluce

`np.convolve(..., mode="same")` vrací pole o délce DELŠÍHO vstupu.
U věty kratší než jádro (9 vzorků při σ=1,5) by výsledek byl delší
než věta a index vrcholu by ukázal mimo ni. Proto se počítá `full`
a řeže se přesně na délku věty.
"""

import numpy as np

DTYPE = np.float32


def gaussian_kernel(sigma: float = 1.5) -> np.ndarray:
    """Normované gaussovské jádro o poloměru int(3σ).

    Poloměr 3σ je obvyklá mez: dál už zvon nese pod 1,2 % hmoty a jen
    by prodlužoval konvoluci. Normuje se na součet 1, aby vrchol zůstal
    ve stejném měřítku jako aktivace, které vyhlazuje.
    """
    if sigma <= 0:
        raise ValueError(f"σ musí být kladné, dostal jsem {sigma}")
    polomer = int(3 * sigma)
    x = np.arange(-polomer, polomer + 1, dtype=DTYPE)
    jadro = np.exp(-(x ** 2) / (2 * sigma ** 2))
    return (jadro / jadro.sum()).astype(DTYPE)


class AnswerField:
    """Pole skóre nad kandidáty jednoho dotazu, čitelné čtyřmi způsoby.

    Vzniká z `MatchResult`; kandidáti se rozloží po větách na pozice
    svých tokenů, mezery (tokeny, které kandidáty nebyly) drží nulu —
    nula je „žádná aktivace", takže nic netvrdí.
    """

    def __init__(self, result) -> None:
        self.result = result
        self._pole: dict[int, np.ndarray] = {}
        for kandidat in result.candidates:
            delka = self._pole.get(kandidat.sentence)
            potreba = kandidat.token + 1
            if delka is None:
                self._pole[kandidat.sentence] = np.zeros(potreba, dtype=DTYPE)
            elif len(delka) < potreba:
                self._pole[kandidat.sentence] = np.pad(
                    delka, (0, potreba - len(delka)))
            self._pole[kandidat.sentence][kandidat.token] = kandidat.score

    # --- čtyři čtení ----------------------------------------------------

    def tokens(self) -> tuple:
        """Nejjemnější čtení: kandidáti tak, jak přišli ze skórování."""
        return self.result.candidates

    def spans(self, width: int = 2) -> tuple:
        """Okna šířky `width`: (věta, počáteční pozice, součet)."""
        okna = []
        for veta, pole in self._pole.items():
            for start in range(max(1, len(pole) - width + 1)):
                okna.append((veta, start,
                             float(pole[start:start + width].sum())))
        okna.sort(key=lambda o: -o[2])
        return tuple(okna)

    def sentences(self) -> tuple:
        """Nejhrubší čtení: (věta, součet celého pole věty).

        Bez dělení délkou — normalizace průměrem je právě ten degenerát,
        kvůli kterému vyhrávaly krátké věty.
        """
        vety = [(veta, float(pole.sum())) for veta, pole in self._pole.items()]
        vety.sort(key=lambda v: -v[1])
        return tuple(vety)

    def gaussian_peaks(self, sigma: float = 1.5) -> tuple:
        """(věta, vrchol, index) seřazené sestupně podle vrcholu.

        Vrchol je maximum pole vyhlazeného gaussovským jádrem; index
        ukazuje, KDE ve větě shluk vrcholí — vždy uvnitř věty, i když
        je věta kratší než jádro.
        """
        jadro = gaussian_kernel(sigma)
        vrcholy = []
        for veta, pole in self._pole.items():
            vyhlazene = _vyhlad(pole, jadro)
            index = int(np.argmax(vyhlazene))
            vrcholy.append((veta, float(vyhlazene[index]), index))
        vrcholy.sort(key=lambda v: -v[1])
        return tuple(vrcholy)

    def __repr__(self) -> str:
        return (f"AnswerField({len(self._pole)} vět, "
                f"{len(self.result.candidates)} kandidátů)")


def _vyhlad(pole: np.ndarray, jadro: np.ndarray) -> np.ndarray:
    """Konvoluce s řezem přesně na délku věty (past mode='same')."""
    plne = np.convolve(pole, jadro, mode="full")
    zacatek = len(jadro) // 2
    return plne[zacatek:zacatek + len(pole)]
