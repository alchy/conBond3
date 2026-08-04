"""Matcher — párování otázky s korpusem.

Otázka je pole (koš os), věty korpusu jsou pole. Párování je **měření
setkání** obou košů, ne hledání shody: žádné filtry, jen uzly, vážené
hrany a vážené členy skóre (princip 2). Jediné řezy jsou θ (mlčení)
a ε (dotaz) — a stojí až na konci, nad hotovým pořadím.

## Dvoustupňové čtení (§ 5/S1 zadání)

Cíl je vybrat kandidátní VĚTY, ale jemné skóre se počítá po tokenech.
Skórovat všech 58 000 tokenů korpusu pythonní smyčkou je zbytečné:
recall po větách je JEDEN maticový součin, jemné čtení se pak platí
jen za top-K vět. Věta „Mojžíš vyvedl lid z Egypta." se u otázky
o dálnici nemá proč číst po tokenech.

## Členy skóre

    cos(q̃, okno)               setkání v uzlech (šířené aktivace)
  + (center−1)·cos(q̃, střed)   zdůraznění středu koše
  + cover·min(pokrytí daných)  nejslabší DANÁ osa — kde je propast,
                               je propast i ve skóre
  + topic·cos(slova q, věta)   téma
  + given·cos(slova q, střed)  postih: kandidát, který v otázce STOJÍ,
                               není odpověď („Kdo pokřtil Ježíše?"
                               nemá odpovědět „Ježíš")

Slova otázky pro oba poslední členy jsou to, co otázka TVRDÍ — bez
tázacího slova a bez interpunkce (`question_words`, táž množina jako
`given_axes`). Kdyby v nich „kdo" zůstalo, téma by odměňovalo věty,
které samy obsahují „kdo": v Markově evangeliu tedy OTÁZKY, ne
odpovědi.

Váhy jsou **páky, ne pravidla** (ScoreWeights) — vypnout člen znamená
dát mu nulu, ne odstranit větev v kódu.

## Proč se rozklad počítá líně

Rozklad skóre po členech je to, čím systém vysvětluje své rozhodnutí.
Počítat ho pro každého kandidáta stálo v referenci 60 % času `match`,
a četl ho jen vítěz. `ScoreCandidate.decomposition()` ho proto počítá
až na vyžádání ze zapamatovaných členů.
"""

from dataclasses import dataclass

import numpy as np

from cb_field.service import Representation

DTYPE = np.float32

#: Slovní druhy, které kandidátem být nemohou. Není to filtr v datové
#: cestě (princip 2): interpunkce není token, který by mohl BÝT odpovědí —
#: měřit u ní skóre je jako měřit teplotu mezery mezi slovy. Skórování
#: všech ostatních zůstává bez výjimky.
NEKANDIDATI = frozenset({"PUNCT", "SYM", "X"})

#: Významové osy — co projde SEMANTICKOU MASKOU do pytle.
#:
#: Strukturní osy (UPOS=, DEPREL=, Case=, SUBPOS= a morfologické rysy)
#: vypadnou úplně. Nesou tvar, ne význam: sdílí je skoro každá věta,
#: takže by kosinus měřil podobnost gramatiky. Zbývá to, co roste
#: s významem — slovo, lemma zavřených tříd, kotvy, polarita a custom
#: sloty. Je to táž množina, nad kterou se smí učit (invariant 1),
#: rozšířená o WORD=; párování slovo vidět smí, učení ne.
SEMANTIC_PREFIXES = ("WORD=", "LEM=", "QLEM=", "ANCHOR=", "QANCHOR=",
                     "Polarity=", "CUSTOM=")


def semantic_bag(rows) -> dict:
    """Součet řádků přes SEMANTICKOU MASKU — jeden pytel na celek.

    Maskuje se PŘED sečtením: strukturní osy do pytle vůbec nevstoupí,
    takže nemohou nafouknout normu a utopit v ní významové osy.
    """
    pytel: dict[str, float] = {}
    for radek in rows:
        for klic, vaha in radek.items():
            if klic.startswith(SEMANTIC_PREFIXES):
                pytel[klic] = pytel.get(klic, 0.0) + vaha
    return pytel


@dataclass(frozen=True)
class ScoreWeights:
    """Váhy členů skóre — páky ke kalibraci, ne pravidla.

    `fit` je připraven pro krok 5 (naučený člen) a `spectral` nese
    latentní podobnost (§ 5/S2). Oba jsou vypnuté nulou, což je jejich
    jediný správný výchozí stav: nespočítaný ani nenaučený člen nesmí
    mlčky ovlivňovat baseline.
    """

    center: float = 2.0
    cover: float = 1.0
    topic: float = 1.0
    given: float = -3.0
    fit: float = 0.0
    spectral: float = 0.0


class LinkOperator:
    """Vazby registru jako řídký operátor — v·L bez husté matice.

    Hustá matice L je při n = 14 748 vertikálách 870 MB a roste
    kvadraticky s korpusem, přitom nese jen desítky tisíc nenul
    (§ 5/S3 zadání). Držíme proto tři pole (řádky, sloupce, váhy)
    a součin počítáme přes `bincount` — čistě numpy, bez scipy.
    """

    def __init__(self, registry) -> None:
        self.size = len(registry)
        vazby = registry.links()
        index = {klic: i for i, klic in enumerate(registry.keys())}
        self._rows = np.array([index[s] for s, _, _ in vazby], dtype=np.int64)
        self._cols = np.array([index[d] for _, d, _ in vazby], dtype=np.int64)
        self._weights = np.array([w for *_, w in vazby], dtype=DTYPE)

    def apply(self, vector) -> np.ndarray:
        """v·L — příspěvek, který do vertikál přiteče po vazbách."""
        out = np.zeros(self.size, dtype=DTYPE)
        if not len(self._rows):
            return out
        prispevky = vector[self._rows] * self._weights
        np.add.at(out, self._cols, prispevky)
        return out


def saturate(vector, links, steps: int) -> np.ndarray:
    """Šíření po vazbách s tanh PO KAŽDÉM kroku.

    tanh až na konci by nebyl týž výpočet: mezikrok bez saturace nechá
    silnou aktivaci narůst a druhý skok ji rozšíří dál, než kam patří.
    Saturace po každém kroku je to, co drží k (hloubku) jako páku
    a ne jako zesilovač.
    """
    vec = np.asarray(vector, dtype=DTYPE)
    for _ in range(steps):
        vec = np.tanh(vec + (links.apply(vec) if links is not None
                             else 0.0)).astype(DTYPE)
    return vec


class ScoreCandidate:
    """Jeden kandidát: token ve větě, jeho skóre a (líný) rozklad."""

    __slots__ = ("sentence", "token", "lemma", "score", "_members")

    def __init__(self, sentence: int, token: int, lemma: str, score: float,
                 members) -> None:
        self.sentence = sentence
        self.token = token
        self.lemma = lemma
        self.score = score
        self._members = members

    @property
    def key(self) -> tuple:
        """Adresa kandidáta v korpusu — (věta, token)."""
        return self.sentence, self.token

    def decomposition(self) -> dict:
        """Skóre po pojmenovaných členech; součet dá `score`."""
        return dict(self._members)

    def __repr__(self) -> str:
        return (f"ScoreCandidate(věta {self.sentence}, token {self.token}, "
                f"{self.lemma!r}, skóre {self.score:.3f})")


class MatchResult:
    """Výsledek párování: seřazení kandidáti a východisko.

    Koše jdou skládat logikou vah (princip 2 — vahami, ne filtry):
    `a & b` je součin kladných (dvě záporná nesmí dát kladné, proto
    minimum), `a | b` součet, `~a` obrácené znaménko. Tím se ptá
    „kdo, ale ne kdy": `kdo & ~kdy`.
    """

    def __init__(self, candidates, outcome: str, question=None) -> None:
        self.candidates = tuple(candidates)
        self.outcome = outcome
        self.question = question

    @property
    def best(self):
        return self.candidates[0] if self.candidates else None

    def sentences(self) -> tuple:
        """Pozice vět kandidátů v pořadí prvního výskytu."""
        videne, poradi = set(), []
        for kandidat in self.candidates:
            if kandidat.sentence not in videne:
                videne.add(kandidat.sentence)
                poradi.append(kandidat.sentence)
        return tuple(poradi)

    def __and__(self, other: "MatchResult") -> "MatchResult":
        return self._spoj(other, _and)

    def __or__(self, other: "MatchResult") -> "MatchResult":
        return self._spoj(other, lambda a, b: a + b)

    def __invert__(self) -> "MatchResult":
        return MatchResult(
            [ScoreCandidate(k.sentence, k.token, k.lemma, -k.score,
                            {jmeno: -hodnota
                             for jmeno, hodnota in k._members.items()})
             for k in self.candidates],
            self.outcome, self.question)

    def __len__(self) -> int:
        return len(self.candidates)

    def __repr__(self) -> str:
        return (f"MatchResult({self.outcome}, {len(self.candidates)} "
                f"kandidátů, nejlepší {self.best.lemma if self.best else '—'})")

    def _spoj(self, other: "MatchResult", operace) -> "MatchResult":
        druhy = {k.key: k for k in other.candidates}
        spojene = []
        for kandidat in self.candidates:
            protejsek = druhy.get(kandidat.key)
            if protejsek is None:
                continue
            spojene.append(ScoreCandidate(
                kandidat.sentence, kandidat.token, kandidat.lemma,
                operace(kandidat.score, protejsek.score), {}))
        spojene.sort(key=lambda k: -k.score)
        return MatchResult(spojene, self.outcome, self.question)


def _and(a: float, b: float) -> float:
    """Součin kladných; kde je záporné, rozhoduje minimum.

    Dvě záporná čísla by součinem dala kladné — tvrzení „ani jedno"
    by se zrodilo jako „obojí". Minimum ten degenerát nemá.
    """
    if a < 0 or b < 0:
        return min(a, b)
    return a * b


class Matcher:
    """Páruje otázku s korpusem; závislosti parametrem (§ 3).

    Korpus je posloupnost polí nad jedním registrem; otázka musí být
    pole nad TÝMŽ registrem, jinak by se porovnávaly různé osy.
    """

    def __init__(self, corpus, *, spread_depth: int = 2,
                 weights: ScoreWeights = ScoreWeights(),
                 theta: float = 0.0, epsilon: float = 0.0,
                 top_k: int = 50, spectral_k: int = 0,
                 graph_recall=None) -> None:
        self.corpus = corpus
        self.spread_depth = spread_depth
        self.weights = weights
        self.theta = theta
        self.epsilon = epsilon
        self.top_k = top_k
        #: Kolik latentních os má spektrální člen. Nula = nepočítá se
        #: vůbec; SVD nad 12 tisíci větami není zadarmo a nikdo za něj
        #: nemá platit, dokud si o něj neřekne váhou.
        self.spectral_k = spectral_k
        #: Předvýběr grafem (GraphRecall), nebo None pro kosinus slov.
        #: Graf nese strukturu, pytel jen množinu — naměřeno 53/117
        #: proti 37/117 (věta s odpovědí v top-50). Předává se
        #: parametrem (§ 3): Matcher si graf nestaví sám.
        self.graph_recall = graph_recall
        self.spectral = None
        self._cache_klic = None
        self._links = None
        self._bags = None          # saturované pytle vět (řídce)
        self._word_bags = None     # jen slovní osy, pro téma
        self._norms = None
        self._word_norms = None
        #: Pytle řádků po větách. Okno se staví přes CELOU větu, takže
        #: bez zapamatování by se týž řádek maskoval znovu pro každého
        #: kandidáta — kvadraticky v délce věty (naměřeno: 68 % času
        #: match). Maže se s cache.
        self._radky: dict = {}

    @property
    def links(self):
        """Řídký operátor vazeb registru (postaví se při první potřebě)."""
        self._priprav()
        return self._links

    # --- osy otázky -----------------------------------------------------

    def given_axes(self, question) -> list:
        """Slovní osy, které otázka DÁVÁ — bez tázacích slov.

        Řádek s QLEM= se ptá, netvrdí: „kde" v „Kde byl pokřtěn Ježíš?"
        mezi dané osy nepatří, kdežto být, pokřtěný a Ježíš ano. Právě
        na nich se měří pokrytí — a mezera v nich je mezera ve znalosti.

        Interpunkce se vynechává: otazník je v otázce vždycky a v oznamovací
        větě nikdy, takže by pokrytí nejslabší dané osy bylo trvale nula
        a člen `cover` by tiše zmizel ze skóre.
        """
        osy = []
        for radek in question.complete:
            if any(klic.startswith("QLEM=") for klic in radek):
                continue
            osy.extend(klic for klic in radek
                       if klic.startswith("WORD=")
                       and not klic.startswith("WORD=PUNCT:"))
        return list(dict.fromkeys(osy))

    def question_words(self, question) -> dict:
        """{slovní osa: váha} toho, co otázka TVRDÍ.

        Táž množina os jako `given_axes`, jen s vahami — jedno pravidlo,
        ne dvě. Stojí na ní členy `topic` a `given`.

        Proč se tázací slovo vynechává: kdyby v pytli zůstalo, člen
        `topic` by odměňoval věty, které samy obsahují „kdo" nebo
        „kde" — tedy OTÁZKY v korpusu, ne odpovědi. Naměřeno na
        Markově evangeliu: „Kdo pokřtil Ježíše?" vyhrávalo „A kdo ti
        dal moc, abys to činil?".
        """
        slova: dict[str, float] = {}
        for radek in question.complete:
            if any(klic.startswith("QLEM=") for klic in radek):
                continue
            for klic, vaha in radek.items():
                if klic.startswith("WORD=") and \
                        not klic.startswith("WORD=PUNCT:"):
                    slova[klic] = slova.get(klic, 0.0) + vaha
        return slova

    def coverage(self, question) -> dict:
        """{daná osa: nejlepší pokrytí přes věty korpusu}.

        Pro každou větu se sečtou aktivace jejích řádků (dva výskyty
        téhož slova se sčítají — proto tanh(1,4) = 0,885 proti
        tanh(0,7) = 0,604 u jednoho), pole se nechá šířit po vazbách
        a saturovat; vrací se maximum přes věty.

        Osa, kterou korpus nezná, dá **přesnou nulu** — propast, ne
        škála. Na tom stojí detekce mezery v kroku 8: „nevím" se pozná
        podle nuly, ne podle prahu na malém čísle.
        """
        self._priprav()
        registry = self.corpus.registry
        pokryti = {}
        for osa in self.given_axes(question):
            index = registry.index(osa) if osa in registry else None
            if index is None or index >= self._bags.shape[1]:
                pokryti[osa] = 0.0
                continue
            sloupec = self._bags[:, index]
            pokryti[osa] = float(sloupec.max()) if len(sloupec) else 0.0
        return pokryti

    # --- dvoustupňové čtení ---------------------------------------------

    def recall_scores(self, question) -> np.ndarray:
        """Skóre předvýběru pro každou větu — jeden maticový součin.

        Řadí se podle toho, co otázka TVRDÍ (`question_words`), ne podle
        celého saturovaného pytle. Týž princip jako u členů `topic`
        a `given`: tázací slovo netvrdí nic, a gramatické osy sdílí
        skoro každá věta, takže by kosinus měřil podobnost tvaru.

        Naměřeno na 117 tréninkových otázkách (věta s odpovědí v top-50):
        podle tvrzení 37×, podle celého saturovaného pytle 31×.
        """
        self._priprav()
        q = self._vektor(self.question_words(question), jen_slova=True)
        if not q.any() or not len(self._word_bags):
            return np.zeros(len(self.corpus), dtype=DTYPE)
        delitel = self._word_norms * float(np.linalg.norm(q))
        return np.divide(self._word_bags @ q,
                         delitel, out=np.zeros(len(self.corpus), dtype=DTYPE),
                         where=delitel > 0)

    def recall(self, question, top_k: int | None = None) -> tuple:
        """Pozice vět, které stojí za jemné čtení.

        Tohle je celý recall: co se sem nedostane, se po tokenech
        nečte — a je to nejužší místo systému. S `graph_recall` se
        vybírá GRAFEM (naměřeno 53/117 proti 37/117 kosinem), jinak
        kosinem slov, která otázka tvrdí.
        """
        k = top_k or self.top_k
        if self.graph_recall is not None:
            vybrane = self.graph_recall.sentences(question, top_k=k)
            # Graf, který nezná ani jedno lemma otázky, nesmí shodit
            # čtení — pak rozhoduje kosinus jako dřív.
            if vybrane:
                return vybrane
        skore = self.recall_scores(question)
        if not skore.any():
            return tuple(range(min(k, len(self.corpus))))
        k = min(k, len(skore))
        nejlepsi = np.argpartition(-skore, k - 1)[:k]
        return tuple(int(i) for i in nejlepsi[np.argsort(-skore[nejlepsi])])

    # --- vektory (krok 3b) ----------------------------------------------

    def question_vector(self, question) -> np.ndarray:
        """Pytel CELÉ otázky: součet řádků → maska → saturace.

        Jeden pytel na celou otázku, ne po řádcích: otázka nemá střed,
        na kterém by záleželo — roli nese pád, ne pozice (princip 5).
        """
        self._priprav()
        return saturate(self._vektor(semantic_bag(question.complete)),
                        self._links, self.spread_depth)

    def candidate_vectors(self, sentence: int, token: int) -> tuple:
        """(okno, střed) kandidáta — obojí saturované a JEDNOTKOVÉ.

        Okno je harmonicky vážené přes CELOU větu: řádek ve vzdálenosti
        `o` od středu přispívá vahou 1/(1+|o|). Váha doznívá, takže okno
        nemá hranu — ořezat ho na ±r by tu hranu vrátilo a smysl
        harmonického vážení zmizel (naměřeno: ořez na ±1 stojí bod
        na etalonu, 10/30 proti 11/30).

        Střed se saturuje a normuje ZVLÁŠŤ, protože zdůraznění středu je
        vlastní člen skóre, ne násobek uvnitř okna — jinak by se trestaly
        středy s bohatou morfologií.
        """
        self._priprav()
        radky = self._radky_vety(sentence)
        okno: dict[str, float] = {}
        for j in range(len(radky)):
            vaha = 1.0 / (1.0 + abs(j - token))
            for klic, hodnota in radky[j].items():
                okno[klic] = okno.get(klic, 0.0) + vaha * hodnota
        okno_v = _jednotkovy(saturate(self._vektor(okno), self._links,
                                      self.spread_depth))
        stred_v = _jednotkovy(saturate(
            self._vektor(radky[token]), self._links, self.spread_depth))
        return okno_v, stred_v

    def _radky_vety(self, sentence: int) -> tuple:
        """Maskované pytle řádků věty — spočítají se jednou za cache."""
        hotove = self._radky.get(sentence)
        if hotove is None:
            hotove = tuple(semantic_bag((radek,))
                           for radek in self.corpus[sentence].complete)
            self._radky[sentence] = hotove
        return hotove

    def sentence_coverage(self, question) -> dict:
        """{pozice věty: pokrytí daných os TOU větou}.

        Pokrytí NENÍ kosinus — je to **mohutnost**: nejslabší daná osa
        v poli věty. Proto je to člen VĚTNÝ (pro všechny kandidáty věty
        stejný, řadí věty), kdežto meet a given řadí tokeny uvnitř věty.
        """
        self._priprav()
        registry = self.corpus.registry
        indexy = [registry.index(osa) for osa in self.given_axes(question)
                  if osa in registry]
        if not indexy:
            return {i: 0.0 for i in range(len(self.corpus))}
        sloupce = self._bags[:, indexy]
        return {i: float(sloupce[i].min()) for i in range(len(self.corpus))}

    # --- párování -------------------------------------------------------

    def match(self, question) -> MatchResult:
        """Spáruje otázku s korpusem a vrátí seřazené kandidáty."""
        self._priprav()
        q = self.question_vector(question)
        q_norma = float(np.linalg.norm(q))
        q_slova = self._vektor(self.question_words(question), jen_slova=True)
        pokryti_vet = self.sentence_coverage(question)
        spektralni = (self.spectral.scores(
            saturate(self._vektor(semantic_bag(question.complete)),
                     self._links, self.spread_depth))
            if self.spectral is not None else None)

        kandidati = []
        for pozice in self.recall(question):
            pole = self.corpus[pozice]
            tema = _cos(q_slova, self._word_bags[pozice])
            cover = pokryti_vet.get(pozice, 0.0)
            spektrum = float(spektralni[pozice]) \
                if spektralni is not None else 0.0
            for i in range(len(pole.tokens)):
                if pole.tokens[i].upos in NEKANDIDATI:
                    continue
                kandidati.append(self._kandidat(
                    q, q_norma, q_slova, pozice, i, pole, cover, tema,
                    spektrum))

        kandidati.sort(key=lambda k: -k.score)
        return MatchResult(kandidati, self._vychodisko(kandidati), question)

    # --- vnitřek --------------------------------------------------------

    def _kandidat(self, q, q_norma, q_slova, pozice, i, pole, cover,
                  tema, spektrum=0.0) -> ScoreCandidate:
        # Obě strany se šíří stejně: otázka nese QANCHOR=, věta ANCHOR=,
        # a společnou souřadnici mají až o krok dál (ANCHOR=space). Šířit
        # jen otázku by znamenalo měřit setkání v místě, kam druhá strana
        # nedošla — členy by pak měřily podobnost gramatiky, ne významu.
        okno, stred = self.candidate_vectors(pozice, i)
        # Okno i střed jsou jednotkové, takže součin s q/‖q‖ JE kosinus
        # a platí identita meet = cos(q̃,okno) + (W_CENTER−1)·cos(q̃,střed).
        combined = okno + (self.weights.center - 1.0) * stred
        stred_slova = self._vektor(
            {klic: vaha
             for klic, vaha in self._radky_vety(pozice)[i].items()
             if not klic.startswith("WORD=PUNCT:")}, jen_slova=True)

        cleny = {
            "meet": float(np.dot(q, combined) / q_norma) if q_norma else 0.0,
            "cover": self.weights.cover * cover,
            "topic": self.weights.topic * tema,
            "given": self.weights.given * _cos(q_slova, stred_slova),
            "fit": self.weights.fit * 0.0,
            # Latentní podobnost je VĚTNÁ jako pokrytí — patří větě, ne
            # tokenu, takže řadí věty. A je to jedno přiznané číslo,
            # ne rozprostřený šum: to je celý důvod, proč smí být
            # v systému, který stojí na pojmenovaných osách.
            "spectral": self.weights.spectral * spektrum,
        }
        return ScoreCandidate(pozice, i, pole.tokens[i].lemma,
                              float(sum(cleny.values())), cleny)

    def _vychodisko(self, kandidati) -> str:
        """θ dělí mlčení od odpovědi, ε odpověď od dotazu.

        Jediné dva řezy v celé cestě, a stojí až tady — nad hotovým
        pořadím, ne uvnitř skórování.
        """
        if not kandidati or kandidati[0].score < self.theta:
            return "silent"
        if len(kandidati) > 1 and \
                kandidati[0].score - kandidati[1].score < self.epsilon:
            return "ask"
        return "answer"

    def _priprav(self) -> None:
        """Postaví pytle vět; přestaví je, když se korpus nebo osa hnuly."""
        # Klíč nese link_version, ne počet vazeb: učení mění VÁHY
        # existujících hran, takže počet zůstane a pytle by zastaraly.
        klic = (len(self.corpus), len(self.corpus.registry),
                self.corpus.registry.link_version,
                self.corpus.registry.axis_version, self.spread_depth)
        if klic == self._cache_klic:
            return
        self._links = LinkOperator(self.corpus.registry)
        sirka = len(self.corpus.registry)
        bags = np.zeros((len(self.corpus), sirka), dtype=DTYPE)
        slova = np.zeros((len(self.corpus), sirka), dtype=DTYPE)
        for i, pole in enumerate(self.corpus):
            pytel = semantic_bag(pole.complete)
            bags[i] = saturate(self._vektor(pytel), self._links,
                               self.spread_depth)
            # Interpunkce ven i na větné straně: tečka je v každé větě
            # a v žádné otázce, takže by jen nafukovala normu tématu.
            slova[i] = self._vektor(
                {klic: vaha for klic, vaha in pytel.items()
                 if not klic.startswith("WORD=PUNCT:")}, jen_slova=True)
        self._bags = bags
        self._word_bags = slova
        if self.spectral_k:
            from cb_bond.spectral import SpectralMember
            self.spectral = SpectralMember().fit(bags, k=self.spectral_k)
        self._radky = {}
        self._norms = np.linalg.norm(bags, axis=1)
        self._word_norms = np.linalg.norm(slova, axis=1)
        self._cache_klic = klic

    def _vektor(self, pytel, jen_slova: bool = False) -> np.ndarray:
        """Pytel {osa: váha} jako vektor nad osou korpusu — BEZ šíření.

        Šíří se výslovně u volajícího. Kdyby vektor saturoval sám,
        snadno by se šířilo dvakrát (naměřeno: otázka pak běžela
        v hloubce 2, když měla v 1) a hloubka by přestala být pákou.
        """
        registry = self.corpus.registry
        vec = np.zeros(len(registry), dtype=DTYPE)
        for klic, vaha in pytel.items():
            if jen_slova and not klic.startswith("WORD="):
                continue
            if klic in registry:
                vec[registry.index(klic)] += vaha
        return vec


def _jednotkovy(vector) -> np.ndarray:
    """Vektor o jednotkové normě; nulový zůstane nulový."""
    norma = float(np.linalg.norm(vector))
    return vector if norma == 0.0 else (vector / norma).astype(DTYPE)


def _cos(a, b) -> float:
    """Kosinus dvou vektorů; nulový vektor dá 0,0, ne dělení nulou."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
