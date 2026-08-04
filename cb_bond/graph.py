"""KnowledgeGraph — paměť faktů: kdo s kým a jakým vztahem.

Proč graf, když pole umí větu rozložit na vážené aktivace: **pytel
ztrácí strukturu**. Na otázku „Kde byl pokřtěn Ježíš?" jsou v pytli
Jordán (2,088) a Galilej (2,068) k nerozeznání, ačkoli strukturně je
rozdíl triviální — Jordán visí na *pokřtěný*, Galilej na *přijít*.
Graf ten rozdíl drží a `illuminate` z něj dělá číslo.

**Co je uzel.** Obsahové slovo: NOUN, PROPN, VERB, ADJ, ADV, NUM.
Předložky, spojky, členy, pomocná slovesa a zájmena uzly nejsou —
jejich příspěvek nese gramatika (vertikály pole), ne fakt. Uzel se
klíčuje `UPOS:lemma`, protože spojkové „jak" je jiné slovo než
příslovečné (táž kolize, kterou řeší LEM= v cb_field).

**Co je hrana.** Závislost mezi dvěma PŘÍMO sousedícími uzly, od
závislého k řídícímu. Visí-li uzel na gramatickém slově, hrana
NEVZNIKÁ a nedovozuje se přes ně dál: „nového" v *Viděl něco nového*
visí na zájmenu a s *vidět* se nespojí. Odvozování přes gramatiku bylo
zkoušeno a graf se s ním rozešel se zmraženou přejímkou (15 975 hran
místo 16 074 a *rok* 163/192 místo 162/191).

Kopulu to nebolí: v „Gravitace **je** síla" visí kopula na *síle*,
mezi uzly nestojí — definiční vazba proto vzniká přímo.

**Smyčka** (táž vertikála dvakrát ve větě, „pes → psa") se do součtu
hran počítá, ale sousedství nemění a nekreslí se — viewBase smyčky
odmítá.

**Proč se počítá `distinct²/edges`.** Skóre pro promoci: mnoho různých
sousedů (uzel je rozcestí, ne slepá ulice) A ZÁROVEŇ neopakovat se do
týchž míst. Je to statistické zdůvodnění, proč si slovo zaslouží
pojmenovaný neuron ve vstupní vrstvě.
"""

from collections import Counter

#: Obsahové slovní druhy — kandidáti na uzel. Zbytek (ADP, AUX, CCONJ,
#: DET, PART, PRON, SCONJ, PUNCT, X, SYM, INTJ) nese gramatika.
NODE_UPOS = frozenset({"NOUN", "PROPN", "VERB", "ADJ", "ADV", "NUM"})

#: Váha hrany z běžného textu. Vazby z definic mají svou (krok 7).
TEXT_WEIGHT = 1.0


class NodeStat:
    """Statistika jednoho uzlu — kolikrát byl a s kým sousedil.

    `edges` jsou hranové instance S OPAKOVÁNÍM (tentýž soused podruhé
    se počítá znovu), `distinct` je počet různých sousedů. Poměr obojího
    je míra, jestli je uzel rozcestí, nebo se pořád opakuje do týchž
    míst — a přesně to potřebuje promoce.
    """

    __slots__ = ("occurrences", "neighbours")

    def __init__(self) -> None:
        self.occurrences = 0
        self.neighbours: Counter = Counter()

    @property
    def edges(self) -> int:
        """Hranové instance uzlu (s opakováním)."""
        return sum(self.neighbours.values())

    @property
    def distinct(self) -> int:
        """Kolik různých sousedů uzel má."""
        return len(self.neighbours)

    @property
    def ratio(self) -> float:
        """distinct/edges — 1,0 znamená „ani jednou se neopakoval"."""
        pocet = self.edges
        return self.distinct / pocet if pocet else 0.0

    def __repr__(self) -> str:
        return (f"NodeStat(occurrences={self.occurrences}, "
                f"edges={self.edges}, distinct={self.distinct}, "
                f"ratio={self.ratio:.2f})")


class KnowledgeGraph:
    """Graf faktů: uzly obsahových slov, hrany závislostí mezi nimi.

    Emitor delt se předává parametrem (princip 6: graf a jeho
    vizualizace jsou totéž) — každá mutace ho zavolá, takže obrázek
    nikdy nezaostává za daty a nikdo ho nemusí ručně obnovovat.
    """

    def __init__(self, emit=None) -> None:
        self._emit = emit
        self._stats: dict[str, NodeStat] = {}
        self._edges: list[tuple] = []
        self._sentences: list[tuple] = []

    # --- stavba ---------------------------------------------------------

    def add_sentence(self, sentence, source: str = "text") -> int:
        """Přidá větu; vrátí počet hran, které z ní vznikly.

        `sentence` je rozparsovaná věta (má .tokens). Pořadí přidání je
        pořadí, na které se pak odkazuje `illuminate`.
        """
        tokens = tuple(sentence.tokens)
        podle_id = {t.id: t for t in tokens}
        uzly = {t.id: _key(t) for t in tokens if _je_uzel(t)}

        for token_id in sorted(uzly):
            self._uzel(uzly[token_id])

        pocet = 0
        for token_id in sorted(uzly):
            token = podle_id[token_id]
            cil = uzly.get(token.head)
            if cil is None:
                continue                     # kořen, nebo řídící není uzel
            self._hrana(uzly[token_id], cil, token.deprel, TEXT_WEIGHT,
                        source)
            pocet += 1

        self._sentences.append(tuple(sorted(set(uzly.values()))))
        return pocet

    # --- čtení ----------------------------------------------------------

    def nodes(self) -> tuple:
        """Klíče všech uzlů, i těch bez hrany."""
        return tuple(self._stats)

    def node_stat(self, key: str) -> NodeStat:
        """Statistika uzlu; neznámý uzel dá prázdnou, ne výjimku."""
        return self._stats.get(key, NodeStat())

    def edges(self) -> tuple:
        """Hrany jako (src, dst, deprel, váha, zdroj) — s opakováním."""
        return tuple(self._edges)

    def sentence_nodes(self, position: int) -> tuple:
        """Uzly věty na dané pozici (v pořadí přidávání)."""
        return self._sentences[position]

    def statistics(self) -> dict:
        """Statistiky uzlů, které mají aspoň jednu hranu.

        Izolovaný uzel se nepočítá: nese nulovou informaci o vztazích
        a v průměrném stupni by dělal tichý posun dolů.
        """
        return {key: stat for key, stat in self._stats.items()
                if stat.edges}

    # --- promoce --------------------------------------------------------

    def select_verticals(self, limit: int = 328, *, usage=None,
                         w_usage: float = 0.0, with_scores: bool = False):
        """Uzly, které si zaslouží pojmenovaný neuron vstupní vrstvy.

        Skóre je `distinct²/edges` — mnoho různých sousedů a málo
        opakování. Volitelný `usage` (doklady uzlu v otázkách a
        odpovědích supervize) je VÁŽENÝ ČLEN, ne filtr:

            skóre = distinct²/edges × (1 + w_usage · doklady)

        Čistě korpusová statistika totiž plave se žánrem: po záplavě
        Nového zákona vystoupala hranice z 12,1 na 41,9 a slova, která
        otázky opravdu potřebují (rychlost 33,8, smět 41,7), vypadla
        těsně pod ni. Slot si má vydělávat službou otázkám.

        Vrací se CELÝ cílový stav (ne přírůstek) — promoce je vratná
        a registr se jím přepisuje.
        """
        usage = usage or {}
        skore = []
        for key, stat in self.statistics().items():
            zaklad = stat.distinct ** 2 / stat.edges
            skore.append((key, zaklad * (1 + w_usage * usage.get(key, 0))))
        skore.sort(key=lambda dvojice: (-dvojice[1], dvojice[0]))
        vybrane = skore[:limit]
        return tuple(vybrane) if with_scores else tuple(k for k, _ in vybrane)

    # --- vysvícení ------------------------------------------------------

    def illuminate(self, ranked_sentences, question_lemmas,
                   boost: float = 2.0) -> dict:
        """Rozsvítí uzly kandidátních vět a nechá je zazářit po hranách.

        `ranked_sentences` je {pozice věty: váha}, `question_lemmas`
        lemmata otázky. Uzel kandidáta dostane váhu věty, uzel s lemmatem
        otázky se násobí `boost`, a pak každý uzel přibere podíl záře
        svých sousedů — úměrně tomu, jakou část sousedových hran k němu
        vede.

        Tím vznikne rozdíl, který pytel nevidí: Jordán (soused
        *pokřtěný*, 3 hrany) zjasní 1,0 + 2,0·(1/3) = 1,67, kdežto
        Galilej (soused *přijít*, 5 hran) jen 1,0 + 1,0·(1/5) = 1,20.
        """
        zaklad: dict[str, float] = {}
        for position, weight in ranked_sentences.items():
            for key in self._sentences[position]:
                zaklad[key] = max(zaklad.get(key, 0.0), float(weight))

        for key in list(zaklad):
            if _lemma(key) in question_lemmas:
                zaklad[key] *= boost

        jas = dict(zaklad)
        for key, hodnota in zaklad.items():
            stat = self._stats.get(key)
            if stat is None or not stat.edges:
                continue
            for soused, pocet in stat.neighbours.items():
                jas[soused] = jas.get(soused, 0.0) + \
                    hodnota * (pocet / stat.edges)
        return jas

    def __repr__(self) -> str:
        return (f"KnowledgeGraph({len(self._stats)} uzlů, "
                f"{len(self._edges)} hran, {len(self._sentences)} vět)")

    # --- vnitřek --------------------------------------------------------

    def _uzel(self, key: str) -> NodeStat:
        stat = self._stats.get(key)
        if stat is None:
            stat = self._stats[key] = NodeStat()
            self._delta({"op": "node", "id": key})
        stat.occurrences += 1
        return stat

    def _hrana(self, src: str, dst: str, deprel: str, weight: float,
               source: str) -> None:
        self._edges.append((src, dst, deprel, weight, source))
        if src == dst:
            # Smyčka: táž vertikála dvakrát v jedné větě („pes → psa").
            # Do součtu hran patří (je to doložená závislost), ale
            # sousedství nemění — soused sám sobě není — a nekreslí se,
            # viewBase smyčky odmítá.
            return
        self._stats[src].neighbours[dst] += 1
        self._stats[dst].neighbours[src] += 1
        self._delta({"op": "edge", "src": src, "dst": dst,
                     "deprel": deprel, "source": source})

    def _delta(self, delta: dict) -> None:
        if self._emit is not None:
            self._emit(delta)


def _je_uzel(token) -> bool:
    """Obsahové slovo?

    Zájmenná příslovce (*tam*, *tehdy*) uzly JSOU, přestože v cb_field
    patří k zavřeným třídám: tam nesou gramatický rys, tady nesou fakt
    („bydlí **tam**"). Naměřeno na 2 912 větách — bez nich má graf
    15 953 hran místo zmražených 16 074.
    """
    return token.upos in NODE_UPOS


def _key(token) -> str:
    return f"{token.upos}:{token.lemma}"


def _lemma(key: str) -> str:
    """Lemma z klíče uzlu — lemma samo, bez slovního druhu."""
    return key.split(":", 1)[1]
