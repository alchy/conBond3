"""PromotionCycle — výměna vstupní vrstvy NN, atomicky a vratně.

Custom slot je **pojmenovaný neuron vstupní vrstvy**, ne cache častých
slov. Tři vlastnosti a u každé důvod:

1. **Omezená kapacita** (limit ≤328) vynucuje zobecnění: co se do slotů
   nevejde, musí do učení projít metadaty a vztahy, ne jménem.
   Kapacita je tlak, ne úspora.
2. **Soutěž** obsazuje kapacitu nejnosnějšími — skóre `různých²/hran`
   žádá mnoho sousedů a zároveň neopakovat se do týchž míst.
3. **Vratnost** je plasticita: kdo z limitu vypadne, uvolní slot i
   s hranami; naměřená stabilizace výměn je 38 % → 16 % na přírůstek.

## Pořadí kroků je závazné

    1. before = measure(corpus)
    2. snap   = registry.snapshot()
    3. target = graph.select_verticals(limit) → set_custom_axes
    4. corpus.regenerate()          ← TEPRVE TEĎ nesou koše CUSTOM=
    5. retrain(corpus)
    6. after  = measure(corpus)
    7. horší? → restore(snap) + regenerate()

Krok 4 před 5 je podstata **transparentní promoce**: koše si aktivaci
`CUSTOM=` přidají samy nahlédnutím do osy, takže učení už vidí hotový
stav. Kdyby se trénovalo dřív, učilo by se nad osou, která ještě
neexistuje.

## Beze změny osy se nepřeučuje

Když `set_custom_axes` nic nezmění, cyklus končí přijetím
a `retrained=False` — trénink je drahý a neměl by co nového vidět.
Odtud plyne, že s růstem korpusu cyklus řídne sám od sebe.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CycleOutcome:
    """Výsledek jednoho průchodu cyklem."""

    accepted: bool
    before: dict
    after: dict | None
    axis_changes: dict
    retrained: bool

    def __repr__(self) -> str:
        stav = "přijato" if self.accepted else "vráceno"
        return (f"CycleOutcome({stav}, osa {self.axis_changes}, "
                f"přeučeno={self.retrained})")


class PromotionCycle:
    """Jeden průchod promocí: selekt → přegenerování → učení → měření.

    `measure` i `retrain` se předávají parametrem (§ 3): cyklus neví,
    čím se měří ani jak se učí, a jde ho tak otestovat bez obojího.
    """

    def __init__(self, measure, retrain, limit: int = 328) -> None:
        self.measure = measure
        self.retrain = retrain
        self.limit = limit

    def run(self, corpus, graph) -> CycleOutcome:
        registry = corpus.registry
        before = self.measure(corpus)
        snap = registry.snapshot()

        target = graph.select_verticals(limit=self.limit)
        zmeny = registry.set_custom_axes(target)
        if not zmeny["pridano"] and not zmeny["odebrano"]:
            # Osa se nehnula: není co přegenerovat, co přeučit ani co
            # měřit podruhé. Stav zůstává, jaký byl.
            return CycleOutcome(True, before, None, zmeny, False)

        corpus.regenerate()
        self.retrain(corpus)
        after = self.measure(corpus)

        if _zhorsilo_se(before, after):
            registry.restore(snap)
            corpus.regenerate()
            return CycleOutcome(False, before, after, zmeny, True)
        return CycleOutcome(True, before, after, zmeny, True)


def _zhorsilo_se(before: dict, after: dict) -> bool:
    """Klesla KTERÁKOLI metrika?

    Stačí jedna: promoce, která zvedne přesnost a srazí dosah, není
    zlepšení — je to výměna, o které nikdo nerozhodl. Shoda projde,
    protože vratná je promoce pořád.
    """
    return any(after[klic] < hodnota for klic, hodnota in before.items()
               if klic in after)
