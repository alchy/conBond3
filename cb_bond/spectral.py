"""SpectralMember — spojité zobecnění vedle pojmenované osy (§ 5/S2).

## Co zaceluje

Nejtvrdší mezera systému je třída *smět ↔ povolený*: jiná slova, žádný
společný kmen, žádná definice. Pytel je nespojí nikdy, protože spolu
nestojí ve větě. Spektrum je spojí přes **sdílený kontext** — obojí se
drží *rychlosti*, *dálnice* a *jezdit*.

Naměřeno na vzorku ze zadání (4 věty × 5 os):

    surový cos(smět, povolený)          0,00   nikdy spolu nestojí
    singulární hodnoty      2,885 · 1,681 · 0,922 · 0
    k=1  cos(smět, povolený)            1,00   slito přes kontext
    k=2  cos(smět, povolený)            0,00   kontrast se vrátil

A na korpusu 2 912 vět (k=200): *Newton × Einstein* surově 0,00 →
spektrálně 0,51, ačkoli spolu nikdy nestojí ve větě.

## Proč JEN vážený člen, a ne náhrada osy

Latentní osy nemají jména. Kdyby nahradily registr, padlo by trojí:
rozklad skóre po pojmenovaných členech, vysvícení grafu (uzel „latentní
dimenze 37" se nakreslit nedá) a invariant „slovo do učení jen promocí"
(každá latentní dimenze je směs slov).

A hlavně: **v latentním prostoru není nic přesně nula.** Naměřeno —
otázka o dálnici má surově přesnou nulu u 1 971 z 2 912 vět, latentně
u nuly z nich. Na té přesné nule přitom stojí detekce mezery (krok 8):
propast, ne škála. Spektrum ji proto doplňuje jedním přiznaným číslem
ve skóre, ne že by osu nahradilo.

## k je páka, ne konstanta

Malé k slévá, velké drží kontrasty — a okno se liší podle toho, co má
zobecnit. Naměřeno na 2 912 větách:

    dvojice                    k=5    k=20    k=50   k=200
    Newton × Einstein        +0,98   +0,86   +0,92   +0,51
    z × od (obě „from")      +0,72   +0,77   −0,27   −0,32
    od × do (OPAČNÉ)         +0,61   −0,07   −0,02   −0,00

Obsahová slova snesou i velké k; gramatické rozdíly žijí kolem k=20,
a při k=5 se slijí i protiklady. Kalibruje se měřením (K7), ne dojmem.

## Kdy se přepočítává

V promočním cyklu — tam, kde se stejně mění osa. Kdyby se počítal
průběžně, `V_k` by se rozešlo s tím, nad čím se učilo, a cache by
měřila jinou reprezentací, než jakou vyrobila.
"""

import numpy as np

DTYPE = np.float32

#: Kolik dimenzí navíc si randomizovaná projekce bere, než kolik jich
#: vrátí. Přebytek zpřesňuje odhad podprostoru a stojí skoro nic.
OVERSAMPLING = 8


def truncated_svd(matrix, k: int, seed: int = 328, iters: int = 4):
    """Randomizované truncated SVD — čisté numpy, deterministické.

    Vrací `(U_k, Σ_k, V_k)`. Náhoda je jen ve startovní projekci
    a semínko ji fixuje (princip 8); podprostor, který vyjde, je
    vlastnost matice — jiné semínko dá touž rovinu, jen v jiné bázi.

    Power iterace (`iters`) přitlačí projekci k silným směrům; čtyři
    stačí, protože singulární hodnoty klesají rychle.
    """
    M = np.asarray(matrix, dtype=DTYPE)
    k = max(1, min(k, min(M.shape)))
    rng = np.random.default_rng(seed)
    sirka = min(M.shape[1], k + OVERSAMPLING)
    Q = M @ rng.standard_normal((M.shape[1], sirka)).astype(DTYPE)
    for _ in range(iters):
        Q, _ = np.linalg.qr(M @ (M.T @ Q))
    B = Q.T @ M
    Ub, s, Vt = np.linalg.svd(B, full_matrices=False)
    return (Q @ Ub)[:, :k], s[:k], Vt[:k]


class SpectralMember:
    """Latentní podobnost otázky a věty — jeden vážený člen skóre.

    Bez `fit` mlčí (vrací 0,0), takže nenaučený člen nemůže mlčky
    ovlivnit baseline — táž kázeň jako u váhy `fit` v ScoreWeights.
    """

    def __init__(self) -> None:
        self.k = 0
        self.axes = 0
        self._Vt = None          # (k × osy)
        self._vety = None        # (věty × k), normované
        self._normy = None

    def fit(self, sentence_matrix, k: int = 250) -> "SpectralMember":
        """Spočítá latentní prostor z matice věty × osy."""
        M = np.asarray(sentence_matrix, dtype=DTYPE)
        _, _, Vt = truncated_svd(M, k)
        self._Vt = Vt
        self.k = Vt.shape[0]
        self.axes = M.shape[1]
        self._vety = M @ Vt.T
        self._normy = np.linalg.norm(self._vety, axis=1)
        return self

    def score(self, question_bag, sentence_id: int) -> float:
        """cos(q·V_kᵀ, věta·V_kᵀ) — bez fitu 0,0."""
        if self._Vt is None or not 0 <= sentence_id < len(self._vety):
            return 0.0
        q = self._zarovnej(np.asarray(question_bag, dtype=DTYPE))
        ql = q @ self._Vt.T
        norma = float(np.linalg.norm(ql)) * float(self._normy[sentence_id])
        if norma == 0.0:
            return 0.0
        return float(ql @ self._vety[sentence_id] / norma)

    def scores(self, question_bag) -> np.ndarray:
        """Skóre proti VŠEM větám najednou — jeden součin (pro recall)."""
        if self._Vt is None:
            return np.zeros(0, dtype=DTYPE)
        q = self._zarovnej(np.asarray(question_bag, dtype=DTYPE))
        ql = q @ self._Vt.T
        delitel = self._normy * float(np.linalg.norm(ql))
        return np.divide(self._vety @ ql, delitel,
                         out=np.zeros(len(self._vety), dtype=DTYPE),
                         where=delitel > 0)

    def _zarovnej(self, q: np.ndarray) -> np.ndarray:
        """Osa roste; kratší pytel se doplní nulami, delší je chyba.

        Nula je „žádná aktivace", takže doplnění nic netvrdí. Delší
        vektor ale vznikl nad novější osou a jeho sloupce navíc by se
        tiše zahodily — to je hlasitá chyba, ne zaokrouhlení.
        """
        if len(q) > self.axes:
            raise ValueError(
                f"pytel má {len(q)} os, spektrum bylo fitováno na "
                f"{self.axes} — vznikl nad novější osou?")
        if len(q) == self.axes:
            return q
        doplneny = np.zeros(self.axes, dtype=DTYPE)
        doplneny[:len(q)] = q
        return doplneny

    def __repr__(self) -> str:
        stav = f"k={self.k}, {self.axes} os" if self._Vt is not None \
            else "bez fitu"
        return f"SpectralMember({stav})"
