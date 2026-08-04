"""GraphRecall — předvýběr vět grafem faktů.

## Proč grafem

Graf nese **strukturu**, pytel jen množinu. Když se rozsvítí *Ježíš*
a *pokřtěný*, záře po hranách dojde k *Jordánu*, protože na *pokřtěném*
opravdu visí — kdežto pytel vidí „tahle věta obsahuje tato slova"
a Jordán s Galilejí jsou v něm k nerozeznání. Je to přesně ten rozdíl,
kvůli kterému graf v § 1 zadání vznikl.

Naměřeno na 117 tréninkových otázkách, jejichž odpověď v korpusu je
(věta s ní v předvýběru):

    kosinus slov otázky   37/117 (top-50)   58/117 (top-200)
    GRAFEM                54/117            68/117

A na etalonu: věta s odpovědí v top-3 stoupla z 22/30 na 25/30.

## Napojení uzlu na větu je zadarmo

Graf si u každé věty pamatuje její uzly (`sentence_nodes`). Obrácený
rejstřík uzel → věty je proto jen přeskládání toho, co už v datech je;
nic se nedopočítává.

## Co se počítá

    1. lemata otázky, která graf ZNÁ, se rozsvítí na 1,0
    2. `depth` skoků po hranách; soused dostane
       záři × (počet hran k němu / všechny hrany uzlu)
    3. záře se SČÍTÁ — uzel, ke kterému vede cesta od víc lemat
       otázky, je nosnější
    4. skóre věty = MAXIMUM ze záře jejích uzlů

Bod 4 je podstatný: součet by zvýhodnil dlouhé věty — týž degenerát,
kvůli kterému je čtení gaussovské (naměřeno: max 25/30, součet 23/30).

## Stop slova do grafu nepatří

Naměřeno na 117 otázkách — s každou přidanou zavřenou třídou to klesá:

    obsahová slova (dnešek)          54/117
    + předložky                      48/117
    + předložky a spojky             47/117
    + zájmena a pomocná slovesa      27/117   (na etalonu 0/30)

Důvod je v mechanismu: zavřená slova jsou rozcestí, která leží na každé
cestě. Podíl `1/hran` sice omezí, kolik každá jednotlivá hrana předá,
ale při dvou skocích přes ně dojde záře odevšad všude — a rozdíl mezi
větami zmizí.
"""

from collections import defaultdict


class GraphRecall:
    """Vybírá věty, které stojí za jemné čtení — pomocí grafu faktů.

    Graf i korpus se předávají parametrem (§ 3); rejstřík se staví při
    prvním dotazu a přepočítá se, když korpus vyroste.
    """

    def __init__(self, graph, corpus, *, depth: int = 2) -> None:
        self.graph = graph
        self.corpus = corpus
        self.depth = depth
        self._rejstrik: dict = {}
        self._vet = -1

    # --- čtení ----------------------------------------------------------

    def sentences(self, question, top_k: int = 50) -> tuple:
        """Pozice vět seřazené sestupně podle záře, nejvýš `top_k`."""
        skore = self.sentence_scores(question)
        poradi = sorted(skore.items(), key=lambda dvojice: (-dvojice[1],
                                                            dvojice[0]))
        return tuple(veta for veta, _ in poradi[:top_k])

    def sentence_scores(self, question) -> dict:
        """{pozice věty: záře} — maximum přes uzly věty."""
        jas = self.glow(question)
        skore: dict = {}
        for klic, hodnota in jas.items():
            for veta in self._vety_uzlu(klic):
                if hodnota > skore.get(veta, 0.0):
                    skore[veta] = hodnota
        return skore

    def glow(self, question) -> dict:
        """{uzel: jas} — lemata otázky rozsvícená a rozzářená po hranách."""
        return self._zar(self._start(question))

    # --- vnitřek --------------------------------------------------------

    def _start(self, question) -> dict:
        """Uzly, které otázka rozsvěcí: její lemata, která graf zná."""
        start = {}
        for token in question.tokens:
            klic = f"{token.upos}:{token.lemma}"
            if self._vety_uzlu(klic):
                start[klic] = 1.0
        return start

    def _zar(self, start: dict) -> dict:
        """Záře po hranách do hloubky `depth`; příspěvky se sčítají."""
        jas = dict(start)
        hranice = dict(start)
        for _ in range(self.depth):
            nova: dict = {}
            for klic, hodnota in hranice.items():
                stat = self.graph.node_stat(klic)
                celkem = stat.edges
                if not celkem:
                    continue
                for soused, pocet in stat.neighbours.items():
                    nova[soused] = nova.get(soused, 0.0) + \
                        hodnota * (pocet / celkem)
            if not nova:
                break
            for klic, hodnota in nova.items():
                jas[klic] = jas.get(klic, 0.0) + hodnota
            hranice = nova
        return jas

    def _vety_uzlu(self, klic: str) -> list:
        self._priprav()
        return self._rejstrik.get(klic, ())

    def _priprav(self) -> None:
        """Obrácený rejstřík uzel → věty; přestaví se s růstem korpusu."""
        if self._vet == len(self.corpus):
            return
        rejstrik = defaultdict(list)
        for pozice in range(len(self.corpus)):
            for klic in self.graph.sentence_nodes(pozice):
                rejstrik[klic].append(pozice)
        self._rejstrik = dict(rejstrik)
        self._vet = len(self.corpus)

    def __repr__(self) -> str:
        return (f"GraphRecall(depth={self.depth}, "
                f"{len(self.corpus)} vět, {len(self.graph.nodes())} uzlů)")
