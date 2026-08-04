"""Projekce znalostního grafu do viewBase2 — krok I návrhu.

Pravidlo J. (2026-08-04): cokoli se děje v rámci grafu, se VŽDY
projeví v jeho vizualizaci. FactGraph proto každou mutaci a každé
vysvícení emituje jako deltu; tady se delty překládají na objektové
API viewBase2 (ensure_node / ensure_edge / update_node — WebSocket
delty za běhu, živá stylizace beze ztráty pozice). Bez běžící
vizualizace systém nestojí: graf s emit=None delty zahazuje.

Pořízení závislosti (mimo requirements.txt — viz komentář tam):
    .venv/bin/pip install \
        "viewbase @ git+https://github.com/alchy/viewBase2#subdirectory=python"

Spuštění nad celým korpusem:
    ./run-python -m cb_field.graphview
"""

import sys


def viewbase_emitter(graph_window):
    """Emitor delt FactGraph → okno viewBase2 (závislost parametrem).

    Každý uzel nese v metadatech seznam SOUSEDŮ s deprel („ADJ:pokřtěný
    (obl)") — viewBase2 metadata ukazuje v detailu uzlu, takže důvod
    hrany je vidět bez čtení kódu. Seznam se doplňuje průběžně s každou
    hranou (živé zrcadlo), stav drží adaptér, ne graf.
    """
    neighbours: dict = {}

    def _note(node, other, deprel):
        near = neighbours.setdefault(node, [])
        entry = f"{other} ({deprel})"
        if entry not in near:
            near.append(entry)
            graph_window.update_node(node, sousede=", ".join(near),
                                     stupen=len(near))

    def emit(delta):
        op = delta["op"]
        if op == "node":
            graph_window.ensure_node(delta["id"], label=delta["id"])
        elif op == "edge":
            # smyčku (rok a rok, conj) viewBase2 nenakreslí — graf ji
            # drží dál, jen se do vizualizace nepřekládá
            if delta["src"] != delta["dst"]:
                graph_window.ensure_edge(delta["src"], delta["dst"])
                _note(delta["src"], delta["dst"], delta["deprel"])
                _note(delta["dst"], delta["src"], delta["deprel"])
        elif op == "style":
            graph_window.update_node(delta["id"], glow=delta["glow"])

    return emit


def main() -> None:
    try:
        import viewbase as vb
    except ImportError:
        sys.exit(
            "viewBase2 není nainstalovaný; pořídíš:\n"
            "  .venv/bin/pip install 'viewbase @ "
            "git+https://github.com/alchy/viewBase2#subdirectory=python'")
    from cb_udpipe import UdpipeClient
    from cb_field.evaluate import build_complex_corpus
    from cb_field.graph import FactGraph

    parser = UdpipeClient()
    corpus = build_complex_corpus(parser)
    screen = vb.Screen(title="conBond3 — znalostní graf")
    window = vb.GraphWindow(screen=screen, dimensions=3)
    graph = FactGraph(emit=viewbase_emitter(window))
    for field in corpus:
        graph.add_sentence(field)
    stats = graph.stats()
    print(f"graf: {stats['uzlu']} uzlů · {stats['hran']} hran — "
          f"servíruji viewBase2")
    project = vb.Project(port=8080)
    project.serve(screen, open_browser=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
