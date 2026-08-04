"""Vztahové vazby — definice a derivace (kroky A a E návrhu
docs/rozsireni-otazky.md, odsouhlaseno J. 2026-08-04).

Definiční hrana povyšuje kopulární vzor („Dálnice je silnice…") na
váženou vazbu v registru: subjekt → predikátové jméno, zdroj
`definice`. Expanze koše otázky pak jde JEN MATICÍ: otázka nesoucí
dálnici po jednom kroku šíření svítí i na silnici — žádná zvláštní
větev, složení do koše dělá spread. Váhu vazby smí doladit učení
(zdroj definice není axiom).
"""

from cb_field.corpus import Corpus
from cb_field.registry import VerticalRegistry

#: Váha definiční vazby — startovní hodnota v rozsahu vah aktivací
#: (výchozí váha řádku); je to páka, ne pravidlo — kalibruje měření
#: a smí ji doladit učení.
DEFINITION_WEIGHT = 0.7

#: Slovní druhy, mezi nimiž se definice čte (subjekt i predikátové
#: jméno) — kopulární vzor s jiným druhem („Být tady je nutné") není
#: definice pojmu.
_NOMINAL = ("NOUN", "PROPN")


def definition_links(corpus: Corpus,
                     registry: VerticalRegistry) -> int:
    """Připíše definiční vazby z kopulárních vět korpusu.

    Vzor: root NOUN/PROPN + jeho nsubj NOUN/PROPN + cop. Vazba vede
    WORD=subjekt → WORD=predikátové jméno. Idempotentní (existující
    vazba se nepřepisuje ani nepočítá); vrací počet nových vazeb.
    """
    added = 0
    for field in corpus:
        root = next((t for t in field.tokens
                     if t.deprel == "root" and t.upos in _NOMINAL), None)
        if root is None:
            continue
        # Definice žádá predikátové jméno v NOMINATIVU („je silnice").
        # Kopula s pádem místa/způsobu („byl ve vězení", lokál) pojem
        # nedefinuje — je to zpřesnění vzoru extrakce, ne filtr dat.
        if "Nom" not in ((root.feats or {}).get("Case") or ""):
            continue
        if not any(t.head == root.id and t.deprel == "cop"
                   for t in field.tokens):
            continue
        subject = next((t for t in field.tokens
                        if t.head == root.id
                        and t.deprel.startswith("nsubj")
                        and t.upos in _NOMINAL), None)
        if subject is None:
            continue
        src = f"WORD={subject.upos}:{subject.lemma}"
        dst = f"WORD={root.upos}:{root.lemma}"
        if src == dst or registry.get_link(src, dst) is not None:
            continue
        registry.link(src, dst, DEFINITION_WEIGHT, source="definice")
        added += 1
    return added
