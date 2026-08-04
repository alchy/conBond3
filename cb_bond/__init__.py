"""cb_bond — jádro vazeb nad polem: graf faktů, párování, odpověď.

Modul staví nad cb_field (pole věty) tázací systém: z otázky v české
větě vybere kandidátní VĚTY, které nesou odpověď, a umí říct proč —
rozkladem skóre po pojmenovaných členech a vysvícením v grafu.

Staví se po krocích (`docs/zadani.md`); dnes je hotový krok 2, graf
faktů:

```python
from cb_bond import KnowledgeGraph

graf = KnowledgeGraph()
graf.add_sentence(veta)              # rozparsovaná věta z cb_udpipe
graf.node_stat("VERB:přijít").ratio  # různých sousedů / hran
graf.select_verticals(limit=328)     # kandidáti na custom sloty
graf.illuminate({0: 1.0}, {"pokřtěný", "Ježíš"})
```

Co je tady, je veřejné API. Co tady není, je vnitřek a smí se kdykoli
změnit (README-MODULES.md § 3).
"""

#: Verze modulu; roste s každou změnou chování. 0.1.0 = krok 2 zadání
#: (KnowledgeGraph); kroky 1 a 3–10 jsou popsané v docs/zadani.md.
__version__ = "0.1.0"

from cb_bond.answer import AnswerField, gaussian_kernel  # noqa: E402
from cb_bond.graph import (  # noqa: E402
    NODE_UPOS,
    KnowledgeGraph,
    NodeStat,
)
from cb_bond.relations import RelationMiner, kmen  # noqa: E402
from cb_bond.matcher import (  # noqa: E402
    LinkOperator,
    MatchResult,
    Matcher,
    ScoreCandidate,
    ScoreWeights,
    saturate,
    semantic_bag,
)

__all__ = [
    "AnswerField",
    "gaussian_kernel",
    "KnowledgeGraph",
    "NodeStat",
    "NODE_UPOS",
    "Matcher",
    "MatchResult",
    "ScoreCandidate",
    "ScoreWeights",
    "LinkOperator",
    "saturate",
    "semantic_bag",
    "RelationMiner",
    "kmen",
    "__version__",
]
