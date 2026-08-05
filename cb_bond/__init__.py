"""cb_bond — jádro vazeb nad polem: graf faktů, párování, odpověď.

Modul staví nad cb_field (pole věty) tázací systém: z otázky v české
větě vybere kandidátní VĚTY, které nesou odpověď, a umí říct proč —
rozkladem skóre po pojmenovaných členech a vysvícením v grafu.

Běžná cesta vede přes službu — systém je postavený v ní:

```python
from cb_bond import BondClient

odpoved = BondClient().ask("Kde byl pokřtěn Ježíš?")
odpoved["answer"]           # 'říci'
odpoved["decomposition"]    # {'meet': 1.23, 'cover': 0.60, …}
```

V procesu (skripty přejímek, měření) se sáhne po fasádě:

```python
from cb_bond import BondService

sluzba = BondService(config, parser)
sluzba.build()                        # 2 912 vět · 16 074 hran
sluzba.ask("Kde byl pokřtěn Ježíš?")
```

Co je tady, je veřejné API. Co tady není, je vnitřek a smí se kdykoli
změnit (§ 3 politiky) — sáhne se na to importem z podmodulu
(`from cb_bond.matcher import ScoreCandidate`) a kdo to udělá, ví, že
sahá pod kapotu.

Seznam je **zúžený schválně**: dřív tu stálo 41 jmen, tedy skoro celý
vnitřek. Takový seznam přestane být švem — nejde za ním vyměnit
implementace, protože někdo spoléhá na to, co je uvnitř.
"""

#: Verze modulu; roste s každou změnou chování. 0.1.0 = kroky 1–10 zadání
#: jako knihovna, 0.2.0 = totéž jako služba (fasáda, REST, ovládání).
__version__ = "0.2.0"

#: Verze REST rozhraní. Cesty pod `/v1/` se nemění; co se změnit musí,
#: dostane `/v2/` (§ 14).
__api__ = ["v1"]

from cb_bond.answer import AnswerField  # noqa: E402
from cb_bond.benchmark import BenchmarkProtocol  # noqa: E402
from cb_bond.client import (  # noqa: E402
    BondClient,
    IncompatibleApi,
    ServiceUnavailable,
)
from cb_bond.dialog import Reply, Responder  # noqa: E402
from cb_bond.graph import KnowledgeGraph  # noqa: E402
from cb_bond.matcher import (  # noqa: E402
    Matcher,
    MatchResult,
    ScoreWeights,
)
from cb_bond.promotion import PromotionCycle  # noqa: E402
from cb_bond.recall import GraphRecall  # noqa: E402
from cb_bond.service import BondService  # noqa: E402
from cb_bond.training import ContrastiveTrainer  # noqa: E402

__all__ = [
    "BondService",                                    # pracovní úroveň
    "BondClient", "ServiceUnavailable", "IncompatibleApi",   # přes síť
    "KnowledgeGraph", "GraphRecall",                  # graf
    "Matcher", "MatchResult", "ScoreWeights",         # párování
    "AnswerField",                                    # čtení
    "Responder", "Reply",                             # dialog
    "ContrastiveTrainer", "PromotionCycle",           # smyčky
    "BenchmarkProtocol",                              # měření
    "__version__",
    "__api__",
]
