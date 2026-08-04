"""Dialogová vrstva — systém odpovídá vždycky a při mezeře se ZEPTÁ.

Tři objekty, tři různé práce:

- `Responder` je hlas systému: řekne, co našel, a přizná, co neví.
- `DefinitionResolver` OPATŘUJE definici chybějícímu slovu — nejdřív
  z korpusu, pak ze slovníku (a fixuje ho na disk), a teprve když ani
  to ne, požádá člověka.
- `QuestionExpander` rozšiřuje otázku o oblast kolem jejích slov.

## Mezera je přesná nula, ne malé číslo

`gaps()` hlásí osy, jejichž pokrytí je **přesně 0,0**. Není to práh:
osa, kterou korpus zná jen slabě, má tanh(0,7) = 0,604, kdežto osa,
kterou nezná vůbec, má nulu. Mezi tím je propast, ne škála — proto se
mezera pozná bez kalibrace a nedá se „skoro" splnit.

Naměřený průběh (otázka „Jak je omezena rychlost na dálnici?" nad
biblicko-fyzikálním korpusem):

    být 1,000 · omezený 0,604 · rychlost 0,604 · na 1,000 · dálnice 0,000

Jediná mezera je *dálnice* — a systém se zeptá právě na ni, ne na celou
otázku. *Rychlost* zná (z fyziky), takže se na ni ptát nebude.

## Odpovídá se VŽDY

`reply()` vrací nejlepšího kandidáta i tehdy, když hlásí
`needs_context`. Mlčet naslepo je horší než odpovědět a přiznat, oč
se systém opírá; člověk pak vidí, kde se rozhodnutí láme.

## Offline-first

Fixované heslo se zapíše do JSON úložiště a příště platí z disku.
Síť se volá jen při PRVNÍM setkání se slovem (princip 7).
"""

import json
from dataclasses import dataclass, field as _field
from pathlib import Path

from cb_bond.relations import DEFINITION_WEIGHT

#: Verze formátu slovníkového úložiště.
FORMAT_VERSION = 1


@dataclass(frozen=True)
class Reply:
    """Odpověď systému: co našel, s jakým východiskem a co mu chybí."""

    best: object
    outcome: str
    missing: list = _field(default_factory=list)

    @property
    def lemma(self):
        return self.best.lemma if self.best is not None else None


@dataclass(frozen=True)
class Expansion:
    """Co expanze otázce opatřila: definice po osách a počet derivací."""

    definitions: dict = _field(default_factory=dict)
    derivations: int = 0


class Responder:
    """Dialogová vrstva nad párováním a grafem."""

    def __init__(self, matcher, graph, expander=None) -> None:
        self.matcher = matcher
        self.graph = graph
        self.expander = expander

    def gaps(self, question) -> list:
        """Osy otázky, které korpus nezná — pokrytí přesně 0,0."""
        return [osa for osa, hodnota
                in self.matcher.coverage(question).items()
                if hodnota == 0.0]

    def reply(self, question, *, expand: bool = False) -> Reply:
        """Odpoví — a při mezeře řekne, co mu k odpovědi chybí.

        `expand=True` nechá expander mezeru zacelit (definicí z korpusu,
        slovníku nebo dialogu), teprve pak se páruje.
        """
        if expand and self.expander is not None:
            self.expander.expand(question)
        mezery = self.gaps(question)
        vysledek = self.matcher.match(question)
        if vysledek.outcome == "silent":
            return Reply(vysledek.best, "silent", mezery)
        if mezery:
            return Reply(vysledek.best, "needs_context", mezery)
        return Reply(vysledek.best, vysledek.outcome, [])

    def append_context(self, text: str, parser, source: str = "dialog"):
        """Přidá větu od uživatele standardní cestou — korpus i graf.

        Žádná zvláštní cesta pro dialogová data: táž stavba pole, týž
        registr, týž graf. Liší se jen zdroj hrany, aby šlo poznat,
        odkud fakt přišel.
        """
        pole = self.matcher.corpus.add_text(text, parser, document=source)
        self.graph.add_sentence(pole, source=source)
        return pole


class DefinitionResolver:
    """Opatří definici slovu, které otázka zná a korpus ne.

    Pořadí je dané principem 7 (offline-first): korpus → úložiště →
    slovník ze sítě (a fixace na disk) → dialog s člověkem. Vyhledávač
    i úložiště se předávají parametrem — jádro nesmí samo sahat na síť.
    """

    def __init__(self, corpus, graph, parser, *, lookup, store) -> None:
        self.corpus = corpus
        self.graph = graph
        self.parser = parser
        self.lookup = lookup
        self.store = Path(store)

    def resolve(self, word_key: str) -> str:
        """Vrátí, odkud definice přišla: corpus | dictionary | dialogue."""
        if self._v_korpusu(word_key):
            return "corpus"
        slovo = word_key.split(":", 1)[1]
        heslo = self._z_uloziste(slovo)
        if heslo is None:
            heslo = self.lookup(slovo)
            if heslo:
                self._uloz(slovo, heslo)
        if not heslo:
            return "dialogue"
        self._ingest(heslo)
        return "dictionary"

    def _v_korpusu(self, word_key: str) -> bool:
        """Vede z osy definiční vazba? Pak je slovo v korpusu vyložené."""
        return any(src == word_key and vaha == DEFINITION_WEIGHT
                   for src, _, vaha in self.corpus.registry.links())

    def _z_uloziste(self, slovo: str):
        if not self.store.exists():
            return None
        data = json.loads(self.store.read_text(encoding="utf-8"))
        return data.get("hesla", {}).get(slovo)

    def _uloz(self, slovo: str, heslo: str) -> None:
        """Fixace hesla — příště se na síť nechodí (princip 7)."""
        data = {"format_version": FORMAT_VERSION, "hesla": {}}
        if self.store.exists():
            data = json.loads(self.store.read_text(encoding="utf-8"))
        data.setdefault("hesla", {})[slovo] = heslo
        self.store.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store.with_suffix(self.store.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(self.store)

    def _ingest(self, heslo: str) -> None:
        """Heslo projde standardní cestou: korpus (zdroj dictionary) + graf."""
        for pole in self.corpus.add_document(heslo, self.parser,
                                             document="dictionary"):
            self.graph.add_sentence(pole, source="dictionary")


class QuestionExpander:
    """Rozšíří otázku o oblast kolem jejích slov.

    Nejdřív se chybějícím osám opatří definice (resolver), pak se kolem
    slov otázky cíleně vytěží derivace (miner). Plošná těžba by stála
    3,3 bodu baseline — proto `around` právě z otázky.
    """

    def __init__(self, resolver, miner) -> None:
        self.resolver = resolver
        self.miner = miner

    def expand(self, question) -> Expansion:
        corpus = self.resolver.corpus
        matcher_osy = [klic for radek in question.complete for klic in radek
                       if klic.startswith("WORD=")
                       and not klic.startswith("WORD=PUNCT:")]
        definice = {}
        for osa in dict.fromkeys(matcher_osy):
            definice[osa] = self.resolver.resolve(osa)
        okoli = {osa.split(":", 1)[1] for osa in definice}
        derivaci = self.miner.mine_derivations(
            self.resolver.graph, corpus.registry, around=okoli)
        return Expansion(definitions=definice, derivations=derivaci)
