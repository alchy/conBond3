"""GraphMirror — graf a jeho obrázek jsou totéž (princip 6).

Zrcadlo přeloží delty grafu na volání okna viewBase2. Okno se předává
parametrem, takže jádro na kreslítku nezávisí a testy si vystačí
s atrapou; `KnowledgeGraph(emit=GraphMirror(okno).emit)` je celé
zapojení.

## Proč delty, a ne překreslení

Graf roste za běhu — ingestem korpusu, definicí ze slovníku, větou
z dialogu. Kdyby se obrázek stavěl znovu po každé změně, byl by buď
pomalý, nebo zastaralý; delta je jediná změna a přijde v okamžiku, kdy
nastane. `mirror()` je jen doháněcí cesta pro graf, který vznikl dřív,
než se okno otevřelo.

## Typy uzlů se musejí zavést napřed

viewBase odmítne uzel s nedefinovaným typem. Zrcadlo si typ zavede samo
při prvním setkání — jinak by ingest spadl uprostřed, jakmile se
v korpusu objeví nový slovní druh.

## Co se nekreslí

**Smyčky.** Uzel na sebe sama viewBase odmítá; graf je proto ani
neemituje (počítá je do součtu hran, ale delta z nich nevzniká).

**Druhý výskyt téže hrany — v obou směrech.** viewBase drží hrany
NEORIENTOVANĚ (A→B a B→A je jedna hrana), graf orientaci nese
v deprelu. Graf navíc počítá hranové instance
S OPAKOVÁNÍM — je to informace (uzel, který se do téhož místa vrací,
je jinačí než uzel s mnoha různými sousedy) a stojí na ní skóre
promoce. Obrázek má ale každou dvojici jednou; viewBase duplicitu
odmítá výjimkou. Dedup proto patří do kresby, ne do dat.

**Pozor na jméno `source`.** V deltě grafu znamená provenienci
(text × dictionary × dialog), ve viewBase ZDROJOVÝ UZEL hrany. Do okna
proto chodí jako `origin` — jinak je z toho TypeError při každém
kreslení hrany.

**Neznámé operace** jsou hlasitá chyba. Tiché přeskočení by znamenalo,
že se něco nekreslí a nikdo neví proč — a u vizualizace je „nevidím to"
právě ten příznak, kterému se nesmí věřit.
"""


#: Barva podle slovního druhu. Není to dekorace: na obrázku je pak
#: hned vidět, jestli uzel nese věc (NOUN), jméno (PROPN), děj (VERB)
#: nebo vlastnost (ADJ) — a odpovědi bývají v jistých typech.
TYPE_STYLES = {
    "NOUN": {"color": "#4c8dff"},
    "PROPN": {"color": "#ffb347"},
    "VERB": {"color": "#5fd08a"},
    "ADJ": {"color": "#c78bff"},
    "ADV": {"color": "#8ad4d6"},
    "NUM": {"color": "#ff8f8f"},
}


class GraphMirror:
    """Překládá delty grafu na okno viewBase2 (GraphWindow)."""

    def __init__(self, window) -> None:
        self.window = window
        self._typy: set = set()
        self._hrany: set = set()

    def emit(self, delta: dict) -> None:
        """Jedna delta grafu → jedno volání okna."""
        op = delta.get("op")
        if op == "node":
            klic = delta["id"]
            upos, lemma = _rozloz(klic)
            self._zaved_typ(upos)
            self.window.add_node(klic, type=upos, label=lemma)
        elif op == "edge":
            # Provenience jde do okna jako `origin`, ne `source`:
            # GraphWindow.add_edge(source, target, **meta) používá
            # `source` pro ZDROJOVÝ UZEL hrany. Kolize jmen je reálná
            # a byla by z ní TypeError při každém kreslení.
            # Klíč je NESETŘÍDĚNÁ dvojice: viewBase drží hrany
            # neorientovaně, takže A→B a B→A je pro obrázek jedna hrana.
            # V grafu orientace zůstává — nese ji deprel.
            dvojice = frozenset((delta["src"], delta["dst"]))
            if dvojice in self._hrany:
                return               # obrázek má každou dvojici jednou
            self._hrany.add(dvojice)
            self.window.add_edge(delta["src"], delta["dst"],
                                 deprel=delta["deprel"],
                                 origin=delta["source"])
        elif op == "style":
            self.window.update_node(delta["id"], glow=delta["glow"])
        else:
            raise ValueError(f"neznámá operace delty: {delta!r}")

    def _zaved_typ(self, upos: str) -> None:
        """Zavede typ uzlu při prvním setkání.

        viewBase odmítne uzel s nedefinovaným typem (`define_type`
        napřed). Zrcadlo si to hlídá samo, aby na to volající nemusel
        myslet a aby graf, který roste za běhu o nový slovní druh,
        nespadl uprostřed ingestu.
        """
        if upos in self._typy:
            return
        self.window.define_type(upos, **TYPE_STYLES.get(upos, {}))
        self._typy.add(upos)

    def mirror(self, graph) -> None:
        """Dožene do okna graf, který vznikl bez zrcadla."""
        for klic in graph.nodes():
            self.emit({"op": "node", "id": klic})
        for src, dst, deprel, _, zdroj in graph.edges():
            if src == dst:
                continue                 # smyčky viewBase odmítá
            self.emit({"op": "edge", "src": src, "dst": dst,
                       "deprel": deprel, "source": zdroj})

    def refresh(self, graph) -> None:
        """Doplní uzlům metadata pro čtení: sousedy a stupeň.

        Co je na obrázku vidět, má jít i přečíst — kliknutím na uzel se
        člověk dozví, s kým sousedí a jakým vztahem, aniž by musel do
        dat. Dělá se to hromadně po ingestu, ne při každé hraně: 16 000
        hran by znamenalo 32 000 zbytečných volání okna.
        """
        deprely = {}
        for src, dst, deprel, _, _ in graph.edges():
            if src == dst:
                continue
            deprely.setdefault(src, {}).setdefault(dst, deprel)
            deprely.setdefault(dst, {}).setdefault(src, deprel)
        for klic, stat in graph.statistics().items():
            sousede = ", ".join(
                f"{soused} ({deprely.get(klic, {}).get(soused, '?')})"
                for soused in sorted(stat.neighbours))
            self.window.update_node(klic, sousede=sousede,
                                    stupen=stat.distinct)

    def illuminate(self, graph, ranked_sentences, question_lemmas,
                   boost: float = 2.0) -> dict:
        """Rozsvítí kandidátní věty v grafu a promítne jas do okna.

        Tohle je ta část, kvůli které princip 6 stojí za tu kázeň:
        člověk VIDÍ, proč systém odpověděl — Jordán zjasní nad Galilejí
        a nikdo kvůli tomu nemusí číst kód.
        """
        jas = graph.illuminate(ranked_sentences, question_lemmas, boost)
        for klic, hodnota in jas.items():
            self.emit({"op": "style", "id": klic, "glow": float(hodnota)})
        return jas


def _rozloz(klic: str) -> tuple:
    """„PROPN:Jordán" → („PROPN", „Jordán"); popisek je pro člověka."""
    upos, _, lemma = klic.partition(":")
    return upos, (lemma or klic)
