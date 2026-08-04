"""Vztahové vazby — definice a derivace (kroky A a E návrhu
docs/rozsireni-otazky.md, odsouhlaseno J. 2026-08-04).

Definiční hrana povyšuje kopulární vzor („Dálnice je silnice…") na
váženou vazbu v registru: subjekt → predikátové jméno, zdroj
`definice`. Expanze koše otázky pak jde JEN MATICÍ: otázka nesoucí
dálnici po jednom kroku šíření svítí i na silnici — žádná zvláštní
větev, složení do koše dělá spread. Váhu vazby smí doladit učení
(zdroj definice není axiom).
"""

import json
import urllib.parse
import urllib.request

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
    return sum(_field_definition_link(field, registry)
               for field in corpus)


def _field_definition_link(field, registry: VerticalRegistry) -> int:
    root = next((t for t in field.tokens
                 if t.deprel == "root" and t.upos in _NOMINAL), None)
    if root is None:
        return 0
    # Definice žádá predikátové jméno v NOMINATIVU („je silnice").
    # Kopula s pádem místa/způsobu („byl ve vězení", lokál) pojem
    # nedefinuje — je to zpřesnění vzoru extrakce, ne filtr dat.
    if "Nom" not in ((root.feats or {}).get("Case") or ""):
        return 0
    if not any(t.head == root.id and t.deprel == "cop"
               for t in field.tokens):
        return 0
    subject = next((t for t in field.tokens
                    if t.head == root.id
                    and t.deprel.startswith("nsubj")
                    and t.upos in _NOMINAL), None)
    if subject is None:
        return 0
    src = f"WORD={subject.upos}:{subject.lemma}"
    dst = f"WORD={root.upos}:{root.lemma}"
    if src == dst or registry.get_link(src, dst) is not None:
        return 0
    registry.link(src, dst, DEFINITION_WEIGHT, source="definice")
    return 1


def wikipedia_definition(term: str) -> str | None:
    """První odstavec úvodu hesla české Wikipedie, nebo None.

    Táž cesta jako pořizovací skripty (jen urllib, slušný ASCII
    User-Agent). Volá se JEDNOU při prvním setkání se slovem —
    výsledek se fixuje v korpusu (zdroj slovnik), takže offline-first
    platí dál.
    """
    params = urllib.parse.urlencode({
        "action": "query", "prop": "extracts", "explaintext": 1,
        "exintro": 1, "format": "json", "redirects": 1, "titles": term})
    request = urllib.request.Request(
        "https://cs.wikipedia.org/w/api.php?" + params,
        headers={"User-Agent": "conBond3 (jindrich.nemec@yahoo.com)"})
    try:
        data = json.loads(urllib.request.urlopen(request,
                                                 timeout=30).read())
        page = next(iter(data["query"]["pages"].values()))
        paragraph = (page.get("extract") or "").split("\n")[0].strip()
        return paragraph or None
    except Exception:                                   # noqa: BLE001
        return None                    # síť/heslo chybí → cesta dialogu


def has_definition(word_key: str, registry: VerticalRegistry) -> bool:
    """Má slovo už definiční vazbu ven?"""
    return any(src == word_key and origin == "definice"
               for src, _dst, _w, origin in registry.links())


def ensure_definition(word_key: str, corpus: Corpus, graph, parser,
                      lookup=wikipedia_definition) -> str:
    """Zajistí definici slova třístupňově; vrací zdroj, který zabral.

    1. „korpus"  — definiční vazba už v registru je (nic se nedělá);
    2. „slovnik" — lookup přinese definici; ta jde STANDARDNÍ cestou
       (parse → korpus se značkou slovnik → graf se zdrojem slovnik
       → definiční vazba), takže se fixuje a příště platí bod 1;
    3. „dialog"  — nezná ani slovník; volající se ptá uživatele
       (mechanika kroku 4, needs_context).

    Expanzi samotnou pak dělá šíření po vazbě (jen matice) — tady se
    definice jen OPATŘUJE.
    """
    registry = corpus.registry
    if has_definition(word_key, registry):
        return "korpus"
    term = word_key.split(":", 1)[1]
    text = lookup(term)
    if not text:
        return "dialog"
    marker = object()                  # blok definice = vlastní dokument
    for sentence in parser.parse(text=text).sentences:
        field = corpus.add_sentence(sentence, document=marker)
        graph.add_sentence(field, source="slovnik")
        _field_definition_link(field, registry)
    return "slovnik"
