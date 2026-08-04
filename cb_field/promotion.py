"""Promoční cyklus — invalidace, přeučení a odvolání jako JEDNA operace.

Krok 3 handoveru. Původně navržené jako dva kroky (technická invalidace
zvlášť, přeučení zvlášť); J. to sloučil, a má pravdu: promoce bez
přeučení nechá systém v horším stavu, než v jakém byl — dostane nové
osy, na kterých nemá naučeno nic, zatímco stará váha platila pro jinou
reprezentaci. A odvolání promoce potřebuje měření, které dává smysl
teprve PO přeučení; jinak by se odvolávalo podle čísla z mezistavu.

Cyklus je proto atomický: buď projde celý, nebo se nestalo nic.

    0. měření před cyklem (reference pro odvolání)
    1. snapshot osy i vazeb
    2. promote_verticals() → cílový stav osy
    3. zápis os · axis_version++ · invalidace všeho, co drží sloupce
    4. přeučení nad novými osami
    5. měření (přesnost × NEVÍM-správnost × recall v dosahu)
    6. horší než před cyklem → návrat na snapshot, jinak přijmout

Přeučení a měření se předávají parametrem (§ 3, závislost parametrem):
cyklus je mechanika, ne politika — CO se učí a ČÍM se měří, rozhoduje
volající (učicí protokol nad etalonem). Protiváha platí workflow § B5:
zhoršení KTERÉKOLI metriky cyklus odvolává — přesnost koupená za
mlčení se nepřijímá.
"""

from typing import Callable

from cb_field.corpus import Corpus
from cb_field.graph import PROMOTION_LIMIT, FactGraph, promote_verticals
from cb_field.registry import CUSTOM_PREFIX


def promotion_cycle(corpus: Corpus, graph: FactGraph,
                    measure: Callable[[Corpus], dict],
                    retrain: Callable[[Corpus], object],
                    limit: int = PROMOTION_LIMIT) -> dict:
    """Provede jeden promoční cyklus nad korpusem a grafem.

    measure: korpus → {metrika: číslo}; volá se před cyklem a po
        přeučení, porovnává se po složkách.
    retrain: korpus → cokoli; učicí protokol nad novými osami.

    Vrací {"prijato", "pred", "po", "osy"} — výsledek se hlásí,
    ne zamlčí, i když se cyklus odvolal.
    """
    registry = corpus.registry
    before = measure(corpus)
    snapshot = registry.snapshot()
    target = tuple(CUSTOM_PREFIX + node
                   for node in promote_verticals(graph, limit))
    changes = registry.set_custom_axes(target)
    retrain(corpus)
    after = measure(corpus)
    worse = any(after[key] < before[key]
                for key in before if key in after)
    if worse:
        registry.restore(snapshot)
    return {"prijato": not worse, "pred": before, "po": after,
            "osy": changes}
