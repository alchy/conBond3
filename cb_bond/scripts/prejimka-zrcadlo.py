#!/usr/bin/env python3
"""Přejímka kroku 9 — zrcadlo grafu proti SKUTEČNÉMU GraphWindow.

Nekontroluje se atrapa, ale okno viewBase2: kdyby se změnilo jeho API
(a jednou už se změnilo — starý projekt viewBase je proto k ledu),
tohle spadne, místo aby testy dál svítily zeleně nad atrapou.

    ./run-python cb_bond/scripts/prejimka-zrcadlo.py

Nenulový návrat znamená rozdíl proti zadání § krok 9.
"""

import sys

from viewbase import GraphWindow
from cb_bond import KnowledgeGraph
from cb_bond.mirror import GraphMirror
from cb_bond.tests.vzorky import KRESTA

okno = GraphWindow(title="přejímka")
zrcadlo = GraphMirror(okno)
graf = KnowledgeGraph(emit=zrcadlo.emit)
graf.add_sentence(KRESTA)
zrcadlo.refresh(graf)
jas = zrcadlo.illuminate(graf, {0: 1.0}, {"pokřtěný", "Ježíš"})

u = okno.node("PROPN:Jordán"); m = u.get("meta", {})
h = okno.edge("PROPN:Jordán", "ADJ:pokřtěný")
print(f"{'co':34} {'naměřeno':>26} {'zadání':>26}")
print(f"{'uzel id':34} {u['id']:>26} {'PROPN:Jordán':>26}")
print(f"{'hrana deprel':34} {h['meta']['deprel']:>26} {'obl':>26}")
print(f"{'jas Jordánu (style/glow)':34} {round(m['glow'],2):>26} {1.67:>26}")
print(f"{'metadata: sousede':34} {m['sousede']:>26} {'ADJ:pokřtěný (obl)':>26}")
print(f"{'metadata: stupen':34} {m['stupen']:>26} {1:>26}")
smycek = sum(1 for e in okno.edges if e["source"] == e["target"])
print(f"{'smyček nakresleno':34} {smycek:>26} {0:>26}")

chyb = sum([
    u["id"] != "PROPN:Jordán",
    h["meta"]["deprel"] != "obl",
    round(m["glow"], 2) != 1.67,
    m["sousede"] != "ADJ:pokřtěný (obl)",
    m["stupen"] != 1,
    smycek != 0,
])
if chyb:
    print(f"\n← ROZDÍL v {chyb} hodnotách")
sys.exit(1 if chyb else 0)
