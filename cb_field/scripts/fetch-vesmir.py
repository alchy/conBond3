"""Pořizovací skript: doména VESMÍR z české Wikipedie.

Spuštění:  ./run-python cb_field/scripts/fetch-vesmir.py

Pořizovací skript (§ 19 politiky): stahuje plaintext extrakty vybraných
článků přes API cs.wikipedia.org (action=query&prop=extracts) a zapisuje
fixovaný korpus data-persistent/korpus/korpus-201.json. Text je licencovaný
(CC BY-SA 4.0, ZDROJ.md) — do gitu nepatří, jen do gitignorované
data-persistent/. Skript používá jen standardní knihovnu (urllib), aby se
neměnilo requirements.txt.

Výchozí bod je článek „Vesmír“, ARTICLES pak vyjmenovává jeho klíčová
navazující témata — seznam je konstanta, aby byl běh opakovatelný a dal
pokaždé stejná data (dokud se nezmění samotné články na Wikipedii).

Blok = odstavec extraktu (mezi dvěma prázdnými řádky). Nadpisy („== Nadpis
==“) se do bloků nezapisují, jen mění nadpis pro `topic`; sekce Reference,
Externí odkazy, Literatura, Poznámky, Související články a podobný aparát
článku (SKIP_SECTIONS) se přeskakují celé. Krátké řádky (méně než ~4 slova
— zbytky seznamů, popisky, zkratky nadpisů) se zahazují.

Věty vznikají rozparsováním CELÉHO odstavce projektovým parserem (ne
spojením předem vytržených vět) — stejné pravidlo jako v
`corpusfile.add_to_corpus` a `preved-korpusy-json.py`: věta vytržená
z kontextu se může parserem rozdělit jinak, a fixace by se rozjela.

Rozpočet vět je 600–900 (zadání J.). Odstavce jednotlivých článků se berou
od začátku (úvod, pak hlavní sekce), ne náhodně, a prokládají se mezi
tématy po kolech — kdyby se braly čistě popořadě podle ARTICLES, spotřeboval
by první velký článek (Vesmír, Hvězda…) celý rozpočet a zbytek by nedostal
žádný prostor.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cb_field.corpus import Corpus                    # noqa: E402
from cb_field.corpusfile import add_to_corpus, load_corpus_file  # noqa: E402

API = "https://cs.wikipedia.org/w/api.php"

# Slušné představení skriptu — Wikimedia API rate-limituje anonymní klienty
# bez User-Agentu tvrději a bez kontaktu neví, koho případně upozornit.
# Hlavičky HTTP musí být ASCII (latin-1); český popisek by je rozbil.
USER_AGENT = ("conBond3-cb_field/1.0 (fetch-vesmir.py; one-off download "
              "of a measurement corpus; contact: see ZDROJ.md in repo)")

TARGET = (Path(__file__).resolve().parents[1]
          / "data-persistent" / "korpus" / "korpus-201.json")

# Vesmír a jeho klíčová navazující témata (zadání J. 2026-08-04). Pořadí je
# záměrné — určuje pořadí kol prokládání, ne jen pořadí stahování.
ARTICLES = (
    "Vesmír",
    "Velký třesk",
    "Kosmologie",
    "Galaxie",
    "Mléčná dráha",
    "Hvězda",
    "Černá díra",
    "Sluneční soustava",
    "Slunce",
    "Planeta",
    "Země",
)

# Sekce, které nesou jen aparát článku (odkazy, citace), ne věcný text.
SKIP_SECTIONS = {
    "reference", "poznámky", "poznámky a reference", "literatura",
    "externí odkazy", "související články", "odkazy", "galerie",
}

HEADING_RE = re.compile(r"^=+\s*(.+?)\s*=+$")

MIN_WORDS = 4           # kratší řádek je titulek, popisek, ne souvislý text
TARGET_MIN = 600
TARGET_MAX = 900

# Kolik pokusů o dotaz, než se to vzdá, a jak dlouho čekat, když API
# neřekne samo (hlavičkou `Retry-After`), za jak dlouho to zkusit znovu.
MAX_POKUSU = 5
VYCHOZI_CEKANI_S = 5.0


def fetch_extract(title: str) -> str:
    """Stáhne plaintext extrakt článku z API české Wikipedie.

    `explaintext=1` vrací čistý text bez wiki značkování (nadpisy zůstávají
    jako „== Nadpis ==“), `redirects=1` následuje přesměrování (např. běžné
    tvary názvů). Při HTTP 429 (Wikimedia rate-limit) čeká podle hlavičky
    `Retry-After` a zkouší to znovu — mlčky to nevzdává ani neruší celý běh.
    """
    params = {"action": "query", "prop": "extracts", "explaintext": 1,
              "format": "json", "redirects": 1, "titles": title}
    url = API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for pokus in range(1, MAX_POKUSU + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            if error.code == 429 and pokus < MAX_POKUSU:
                cekani = float(error.headers.get("Retry-After",
                                                  VYCHOZI_CEKANI_S))
                print(f"  … {title}: 429 (rate limit), čekám {cekani:.0f}s "
                      f"(pokus {pokus}/{MAX_POKUSU})")
                time.sleep(cekani)
                continue
            raise
    else:
        raise RuntimeError(f"článek {title!r}: opakovaně 429, vzdávám se")

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        if "missing" in page:
            raise ValueError(
                f"článek {title!r} na cs.wikipedia.org neexistuje "
                f"(zkontroluj ARTICLES)")
        return page.get("extract", "")
    raise ValueError(f"článek {title!r}: prázdná odpověď API")


def clean_paragraphs(extract: str) -> list:
    """Rozseká extrakt na odstavce; vynechá nadpisy, vyřazené sekce a krátké řádky.

    Vrací dvojice (sekce, text odstavce) v pořadí výskytu v článku. Blok je
    text mezi dvěma prázdnými řádky; nadpis sám se do textu nezapisuje, jen
    přepne `section` (a případně zapne přeskakování, je-li v SKIP_SECTIONS).
    """
    paragraphs = []
    section = "Úvod"
    skipping = False
    buffer: list = []

    def flush() -> None:
        if not buffer:
            return
        text = " ".join(" ".join(buffer).split())
        if len(text.split()) >= MIN_WORDS:
            paragraphs.append((section, text))
        buffer.clear()

    for raw_line in extract.splitlines():
        line = raw_line.strip()
        heading = HEADING_RE.match(line)
        if heading:
            flush()
            name = heading.group(1).strip()
            skipping = name.casefold() in SKIP_SECTIONS
            if not skipping:
                section = name
            continue
        if not line:
            flush()
            continue
        if skipping:
            continue
        if len(line.split()) < MIN_WORDS:
            continue
        buffer.append(line)
    flush()
    return paragraphs


def interleave(per_article: dict):
    """Prokládá odstavce článků po kolech (kolo = jeden odstavec z každého).

    Kolo místo prostého zřetězení podle ARTICLES, aby velký článek na
    začátku seznamu nespotřeboval celý rozpočet vět dřív, než dojde řada na
    další témata — pořadí uvnitř článku (od začátku) přitom zůstává.
    """
    iterators = {title: iter(paragraphs)
                 for title, paragraphs in per_article.items()}
    active = list(iterators)
    while active:
        for title in list(active):
            try:
                section, text = next(iterators[title])
            except StopIteration:
                active.remove(title)
                continue
            yield title, section, text


def main() -> None:
    from cb_udpipe import UdpipeClient
    parser = UdpipeClient()

    print("stahuji z cs.wikipedia.org:")
    per_article = {}
    for title in ARTICLES:
        extract = fetch_extract(title)
        paragraphs = clean_paragraphs(extract)
        per_article[title] = paragraphs
        words = sum(len(text.split()) for _, text in paragraphs)
        print(f"  {title}: {len(paragraphs)} odstavců, {words} slov "
              f"po očištění")
        time.sleep(1.0)   # slušné rozestupy mezi dotazy na cizí server

    blocks = []
    total_sentences = 0
    for title, section, text in interleave(per_article):
        if total_sentences >= TARGET_MIN:
            break
        sentences = [s.source or " ".join(t.form for t in s.tokens)
                     for s in parser.parse(text=text).sentences]
        if not sentences:
            continue
        blocks.append({"topic": f"{title} · {section}",
                       "text": text, "sentences": sentences})
        total_sentences += len(sentences)

    if total_sentences < TARGET_MIN:
        sys.exit(f"nedostatek vět po vyčištění: {total_sentences} "
                 f"< {TARGET_MIN} — rozšiř ARTICLES nebo sniž MIN_WORDS")
    if total_sentences > TARGET_MAX:
        print(f"pozor: {total_sentences} vět přesahuje horní mez "
              f"{TARGET_MAX} (poslední blok ji překročil vcelku)")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(
        {"format_version": 1, "language": "cs",
         "blocks": blocks, "questions": []},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # zpětná kontrola (stejná jako u ostatních pořizovacích skriptů): soubor
    # se znovu načte a rozpad musí sedět položkám počtem i zněním, jinak by
    # číslování vět, na které jednou budou mířit otázky, bylo nespolehlivé
    corpus_file = load_corpus_file(TARGET)
    corpus = Corpus(r=1)
    add_to_corpus(corpus, corpus_file, parser)
    print(f"\n{TARGET.name}: {len(corpus_file.blocks)} bloků · "
          f"{len(corpus)} vět (zpětná kontrola proti parseru OK)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
