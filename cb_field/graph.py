"""Graf faktů — paměť konkrétního světa, samostatná vrstva vedle registru.

Krok 1 handoveru (docs/handover-implementace.md): registr zůstává osou
systému, graf drží fakta. Míchat je dohromady by znamenalo, že se
konkrétní svět dostane do os dřív, než o tom rozhodne promoce (krok 2).

Uzel = lemma se slovním druhem („NOUN:rok"). Hrana = závislost mezi
dvěma obsahovými uzly, vede od závislého k hlavě a nese deprel, váhu
a zdroj (text | dialog) — táž trojice jako u vazeb v registru, aby se
s tím dalo zacházet jednotně a šlo dialogové hrany kdykoli odlišit od
korpusových.

Co graf záměrně nedělá: neřeší koreference, neslučuje synonyma, nesahá
na skóre párování. To je práce pozdějších kroků; smíchat to sem by
znemožnilo měřit, co za co může.
"""

from dataclasses import dataclass, field as dataclass_field

#: Slovní druhy, jejichž tokeny se stávají uzly. Funkční slova
#: (předložky, spojky, determinátory, pomocná slovesa, interpunkce)
#: nese gramatika — osy UDPipe — a graf by je držel podruhé. Zájmena
#: stojí vedle nich: bez koreference je „on" jen odkaz bez obsahu
#: a v referenčním měření (4. 8. 2026) uzlem nebylo — s PRON čísla
#: korpusu nesedí (17 953 hran místo 16 074).
CONTENT_UPOS = frozenset({"NOUN", "PROPN", "VERB", "ADJ", "ADV", "NUM"})


@dataclass
class NodeStat:
    """Statistika jednoho uzlu — diskriminátor obecnosti (krok 1).

    Poměr různých sousedů k počtu hran odděluje obecné od konkrétního:
    vysoký znamená, že skoro každá hrana jde jinam (uzel nese TVAR),
    nízký znamená opakované hrany do týchž míst (konkrétní svět).
    """

    occurrences: int = 0               # kolikrát byl uzel tokenem věty
    edges: int = 0                     # hranové instance (s opakováním)
    neighbours: dict = dataclass_field(default_factory=dict)

    @property
    def distinct(self) -> int:
        """Počet různých sousedů (bez ohledu na směr, deprel i zdroj)."""
        return len(self.neighbours)

    @property
    def ratio(self) -> float:
        """různých / hran — 0.0 pro uzel zatím bez hran."""
        return self.distinct / self.edges if self.edges else 0.0


class FactGraph:
    """Graf faktů nad větami: uzly a hrany ze závislostí, statistika.

    Nic víc: žádná promoce, žádný zásah do párování. Vrstva jde vypnout
    tím, že se nezavolá.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, NodeStat] = {}
        #: (od, do, deprel, zdroj) → váha; instance téže hrany se
        #: sčítají (1,0 na doklad), takže váha je zároveň počet dokladů.
        self._edges: dict[tuple, float] = {}

    @staticmethod
    def node_key(token) -> str | None:
        """„UPOS:lemma" pro obsahové slovo, None pro funkční."""
        if token.upos in CONTENT_UPOS:
            return f"{token.upos}:{token.lemma}"
        return None

    def add_sentence(self, sentence, source: str = "text") -> int:
        """Přijme větu (cokoli s .tokens) a připíše uzly a hrany.

        Hrana vede od závislého k hlavě jen tehdy, když jsou OBA konce
        obsahové; závislost přes funkční slovo nevzniká (tu nese
        gramatika). Vrací počet připsaných hranových instancí.
        """
        tokens = sentence.tokens
        by_id = {t.id: t for t in tokens}
        added = 0
        for token in tokens:
            key = self.node_key(token)
            if key is None:
                continue
            self._nodes.setdefault(key, NodeStat()).occurrences += 1
        for token in tokens:
            src = self.node_key(token)
            head = by_id.get(token.head)
            dst = self.node_key(head) if head is not None else None
            if src is None or dst is None:
                continue
            self._edges[(src, dst, token.deprel, source)] = \
                self._edges.get((src, dst, token.deprel, source), 0.0) + 1.0
            for node, neighbour in ((src, dst), (dst, src)):
                stat = self._nodes[node]
                stat.edges += 1
                stat.neighbours[neighbour] = \
                    stat.neighbours.get(neighbour, 0) + 1
            added += 1
        return added

    # --- čtení ----------------------------------------------------------

    def nodes(self) -> tuple:
        """Klíče uzlů v pořadí prvního výskytu."""
        return tuple(self._nodes)

    def edges(self) -> tuple:
        """Hrany jako pětice (od, do, deprel, váha, zdroj)."""
        return tuple((s, d, rel, w, src) for (s, d, rel, src), w
                     in self._edges.items())

    def node_stat(self, key: str) -> NodeStat:
        """Statistika uzlu; neznámý uzel je KeyError, ne tiché nic."""
        try:
            return self._nodes[key]
        except KeyError:
            raise KeyError(f"uzel {key!r} v grafu není") from None

    def node_stats(self) -> dict:
        """{uzel: NodeStat} v pořadí prvního výskytu — vstup promoce."""
        return dict(self._nodes)

    def stats(self) -> dict:
        """Souhrn pro měření: uzly, hranové instance, průměrné stupně.

        Fakt je vztah — do grafu faktů se počítají jen uzly s aspoň
        jednou hranou. Izolované obsahové slovo zůstává evidované
        (node_stat, výskyty), ale bez hrany žádný fakt nenese.
        """
        connected = [s for s in self._nodes.values() if s.edges]
        nodes = len(connected)
        instances = int(sum(self._edges.values()))
        return {
            "uzlu": nodes,
            "hran": instances,
            "prumerny_stupen": 2 * instances / nodes if nodes else 0.0,
            "prumer_ruznych":
                sum(s.distinct for s in connected) / nodes if nodes
                else 0.0,
        }

    def __repr__(self) -> str:
        s = self.stats()
        return f"FactGraph({s['uzlu']} uzlů, {s['hran']} hran)"


#: Strop custom vertikál (krok 2 handoveru). Platí na promované osy;
#: osy z UDPipe stojí vedle a nesoutěží. Pevná velikost je to, co dělá
#: z registru vstupní vrstvu sítě s pevnou dimenzí — a tlak k obecnosti:
#: co se nevejde, nebylo dost nosné.
PROMOTION_LIMIT = 328


def promote_verticals(graph: FactGraph,
                      limit: int = PROMOTION_LIMIT) -> tuple:
    """Cílový stav osy custom vertikál — kdo si zaslouží sloupec.

    Kritérium: skóre = různých²/hran (efektivní počet různých sousedů).
    Odměňuje rozmanitost i obecnost zároveň — uzel musí mít mnoho
    sousedů A ZÁROVEŇ se neopakovat do týchž míst. Tlumená varianta
    poměr × n/(n+1) je zavržená měřením (saturuje při dvaceti hranách,
    handover krok 2), duplicitu s osami UDPipe hlídá už krok 1:
    funkční slova, která by gramatiku držela podruhé, uzlem nejsou.

    Vratnost: vrací se CELÝ cílový stav, ne přírůstek — porovnává se
    stav proti stavu, takže uzel, který z grafu zmizí, po přepočtu
    z osy vypadne. Deterministické: shodné skóre řadí klíč uzlu,
    ne pořadí vět.

    Nesahá na registr, cache ani indexy — zápis osy je práce
    promočního cyklu (krok 3).
    """
    scored = sorted(
        (-stat.distinct ** 2 / stat.edges, key)
        for key, stat in graph.node_stats().items() if stat.edges)
    return tuple(key for _score, key in scored[:limit])
