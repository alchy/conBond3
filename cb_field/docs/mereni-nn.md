# Experimenty zapojení NN (mosty promoce, hloubka šíření)

- datum: 2026-08-04 · verze modulu 0.10.0 · korpus 2912 vět · etalon 40 otázek · trénink 120 otázek (oddělené sady)

| rameno | přesnost@1 | NEVÍM | dosah OK | vad | pozn. |
|---|---|---|---|---|---|
| A baseline | 0.37 | 0.00 | 10 | 1 |  |
| B učení 4c | 0.43 | 0.00 | 10 | 0 | epoch 2 · hran 23699 |
| D hloubka k=2 (baseline) | 0.40 | 0.00 | 10 | 1 |  |
| D hloubka k=3 (baseline) | 0.40 | 0.00 | 10 | 1 |  |
| C promoce+mosty+učení | 0.43 | 0.00 | 10 | 0 | PŘIJATO · osy {'pridano': 328, 'odebrano': 0, 'hran_odebrano': 0} |
| E hloubka k=2 nad C | 0.50 | 0.00 | 10 | 0 |  |

Čtení: B je kontrola k C — rozdíl C−B je čistý příspěvek promovaných os s mosty (učení mají obě ramena stejné). D měří hloubku šíření samotnou na čistém baselinu, E její složení se stavem po C; sloupec vad = odpověď v dosahu, a přesto propadla (reach_report).
