"""Živý graf faktů ve viewBase2 — `./run-python -m cb_bond.graphview`.

Postaví graf z korpusu, zrcadlí ho do okna a nechá server běžet na
:8080. Odpověď na otázku se pak v grafu **rozsvítí**: uzly kandidátních
vět se zjasní, lemata otázky je zesílí, a člověk vidí, proč systém
odpověděl, bez čtení kódu (princip 6).

    ./run-python -m cb_bond.graphview                       # celý korpus
    ./run-python -m cb_bond.graphview "Kde byl pokřtěn Ježíš?"

## Otisk frontendu se ověřuje

Starý projekt viewBase je k ledu — má jiné API a jednou už podvrhl
starou generaci frontendu. Modul proto při startu vypíše otisk bundlu
z `index.html`; kdo vidí jiný než očekávaný, ví hned, že mu běží něco
jiného, než si myslí.

Instalace VÝHRADNĚ:

    pip install 'viewbase @ git+https://github.com/alchy/viewBase2#subdirectory=python'
"""

import hashlib
import re
import sys
from pathlib import Path

from cb_bond import GraphMirror, KnowledgeGraph, Matcher
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

#: Otisk frontendu, proti kterému se tohle psalo (2026-08-04).
#: Neshoda není chyba — je to upozornění, že běží jiná generace.
OCEKAVANY_BUNDLE = "39a833cc57f74bb4"

HOST, PORT = "127.0.0.1", 8080


def bundle_fingerprint() -> tuple:
    """(jméno bundlu, prvních 16 znaků sha256) z instalovaného viewbase."""
    import viewbase

    static = Path(viewbase.__file__).parent / "static"
    index = (static / "index.html").read_text(encoding="utf-8")
    shoda = re.search(r'src="(/assets/[^"]+\.js)"', index)
    if not shoda:
        return ("?", "?")
    soubor = static / shoda.group(1).lstrip("/")
    otisk = hashlib.sha256(soubor.read_bytes()).hexdigest()[:16]
    return (soubor.name, otisk)


def main(argv=None) -> int:
    from viewbase import GraphWindow, serve

    argv = list(sys.argv[1:] if argv is None else argv)
    otazka = argv[0] if argv else None

    jmeno, otisk = bundle_fingerprint()
    stav = "OK" if otisk == OCEKAVANY_BUNDLE else \
        f"JINÁ GENERACE (čekáno {OCEKAVANY_BUNDLE})"
    print(f"frontend: {jmeno} · otisk {otisk} — {stav}", file=sys.stderr)

    korpus = Path("cb_field/data-persistent/korpus")
    paths = sorted(korpus.glob("korpus-1*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    parser = UdpipeClient()
    corpus = build_corpus(paths, parser, r=1)
    okno = GraphWindow(title="cb_bond — graf faktů")
    zrcadlo = GraphMirror(okno)
    graf = KnowledgeGraph(emit=zrcadlo.emit)
    for pole in corpus:
        graf.add_sentence(pole)
    zrcadlo.refresh(graf)
    print(f"graf: {len(graf.nodes())} uzlů · {len(graf.edges())} hran "
          f"z {len(corpus)} vět", file=sys.stderr)

    if otazka:
        matcher = Matcher(corpus, spread_depth=1, theta=0.0)
        pole_otazky = SentenceField.from_text(otazka, parser, r=1,
                                              registry=corpus.registry)
        vysledek = matcher.match(pole_otazky)
        vahy = _vahy_vet(vysledek)
        lemata = {t.lemma for t in pole_otazky.tokens}
        jas = zrcadlo.illuminate(graf, vahy, lemata)
        nejjasnejsi = sorted(jas.items(), key=lambda d: -d[1])[:5]
        print(f"otázka: {otazka}", file=sys.stderr)
        print(f"  nejlepší kandidát: {vysledek.best.lemma!r} "
              f"({vysledek.outcome})", file=sys.stderr)
        print(f"  nejjasnější uzly: "
              f"{[(k, round(v, 2)) for k, v in nejjasnejsi]}", file=sys.stderr)

    print(f"běží na http://{HOST}:{PORT}/ — Ctrl+C ukončí", file=sys.stderr)
    serve(okno, host=HOST, port=PORT)
    return 0


def _vahy_vet(result, top: int = 5) -> dict:
    """{pozice věty: váha} z nejlepších kandidátů — vstup pro illuminate."""
    vahy = {}
    for kandidat in result.candidates:
        if kandidat.sentence not in vahy:
            vahy[kandidat.sentence] = max(0.0, kandidat.score)
        if len(vahy) >= top:
            break
    nejvyssi = max(vahy.values(), default=0.0)
    if nejvyssi > 0:
        vahy = {veta: vaha / nejvyssi for veta, vaha in vahy.items()}
    return vahy


if __name__ == "__main__":
    sys.exit(main())
