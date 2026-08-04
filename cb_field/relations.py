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


#: Váha derivační vazby v plné síle; skutečná váha ji škáluje složením
#: kmene a překryvu sousedství.
DERIVATION_WEIGHT = 0.7

#: Párovací podmínka kmene: sdílený začátek lemmat (bez diakritiky)
#: aspoň 5 znaků A ZÁROVEŇ aspoň 75 % kratšího lemmatu. Zavrženo
#: měřením: v1 (3 znaky) — 19 644 vazeb, předpona pro- párovala
#: pronásledovaný↔procitnout; v2 (4 znaky, 60 %) — 32 812 vazeb,
#: naléhavý↔náledí. Přísný kmen nechá krátkokmenné páry
#: (stavba–stavět, hudba–hudební) i střídání samohlásek
#: (křtít–pokřtěný) na slovotvorný zdroj (DeriNet) nebo typy vztahů
#: — vážená hrana za tu cenu nesmí zaplavit L šumem.
_STEM_MIN = 5
_STEM_SHARE = 0.75


def _fold(text: str) -> str:
    """Malá písmena bez diakritiky (vzkaz–vzkázat sdílí kmen až po
    složení á→a)."""
    import unicodedata
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed
                   if not unicodedata.combining(c))


def derivation_links(graph, registry: VerticalRegistry,
                     around=None) -> int:
    """Krok E: derivační vazby SLOŽENÍM kmene a překryvu sousedství.

    Dvojice se sdíleným kmenem (viz _STEM_MIN/_STEM_SHARE) dostane
    obousměrnou vazbu s vahou DERIVATION_WEIGHT × (kmen/2 + překryv/2)
    — kmen sám dá slabou vazbu, překryv ji zesílí
    (rychlost–rychlostní). Sonda: překryv sám je na úrovni náhody,
    kmen sám páruje předpony — signál nese složení.

    around: lemmata, na jejichž okolí se párování omezí (kmeny slov
    otázky a její expanze). PLOŠNÉ nasazení do L je zavržené měřením
    (11 268 vazeb stálo baseline 3,3 bodu přesnosti) — derivace se
    pouští CÍLENĚ při expanzi otázky; None = plošně (měřicí režim).
    """
    wanted = ({_fold(lemma)[:_STEM_MIN] for lemma in around}
              if around is not None else None)
    nodes = []
    for key, stat in graph.node_stats().items():
        if stat.edges:
            lemma = _fold(key.split(":", 1)[1])
            if len(lemma) >= _STEM_MIN:
                nodes.append((key, lemma, set(stat.neighbours)))
    groups: dict = {}
    for entry in nodes:
        stem = entry[1][:_STEM_MIN]
        if wanted is None or stem in wanted:
            groups.setdefault(stem, []).append(entry)
    added = 0
    for group in groups.values():
        for i, (key_a, lemma_a, near_a) in enumerate(group):
            for key_b, lemma_b, near_b in group[i + 1:]:
                stem = 0
                for x, y in zip(lemma_a, lemma_b):
                    if x != y:
                        break
                    stem += 1
                shorter = min(len(lemma_a), len(lemma_b))
                if stem < _STEM_MIN or stem < _STEM_SHARE * shorter:
                    continue
                overlap = (len(near_a & near_b)
                           / min(len(near_a), len(near_b))
                           if near_a and near_b else 0.0)
                strength = stem / max(len(lemma_a), len(lemma_b))
                weight = min(1.0, DERIVATION_WEIGHT
                             * (0.5 * strength + 0.5 * overlap))
                for src, dst in ((f"WORD={key_a}", f"WORD={key_b}"),
                                 (f"WORD={key_b}", f"WORD={key_a}")):
                    if registry.get_link(src, dst) is None:
                        registry.link(src, dst, weight,
                                      source="derivace")
                        added += 1
    return added


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


def _store_definition(store, term: str, text: str, sentences) -> None:
    """Fixace slovníkové definice na disk (offline-first): blok se
    PŘIPÍŠE do rostoucího fixovaného korpusu (formát docs/korpus-json),
    takže lookup přežije restart a glob baselinu ho příště přibere."""
    import os
    from pathlib import Path
    store = Path(store)
    if store.is_file():
        data = json.loads(store.read_text(encoding="utf-8"))
    else:
        data = {"format_version": 1, "language": "cs",
                "blocks": [], "questions": []}
    data["blocks"].append({
        "topic": f"slovnik {term}", "text": text,
        "sentences": [getattr(s, "source", None)
                      or " ".join(t.form for t in s.tokens)
                      for s in sentences]})
    tmp = store.with_suffix(store.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2)
                   + "\n", encoding="utf-8")
    os.replace(tmp, store)


def ensure_definition(word_key: str, corpus: Corpus, graph, parser,
                      lookup=wikipedia_definition,
                      store=None) -> str:
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
    sentences = parser.parse(text=text).sentences
    for sentence in sentences:
        field = corpus.add_sentence(sentence, document=marker)
        graph.add_sentence(field, source="slovnik")
        _field_definition_link(field, registry)
    if store is not None:
        _store_definition(store, term, text, sentences)
    return "slovnik"
