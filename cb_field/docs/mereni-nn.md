# Experimenty zapojení NN (mosty promoce, hloubka šíření)

- datum: 2026-08-04 · verze modulu 0.10.0 · korpus 12258 vět · etalon 40 otázek · trénink 120 otázek (oddělené sady)

| rameno | přesnost@1 | NEVÍM | dosah OK | vad | pozn. |
|---|---|---|---|---|---|
| A baseline | 0.27 | 0.00 | 10 | 1 |  |
| B učení 4c | 0.33 | 0.00 | 10 | 1 | epoch 2 · hran 15447 |
| D hloubka k=2 (baseline) | 0.30 | 0.00 | 9 | 2 |  |
| D hloubka k=3 (baseline) | 0.33 | 0.00 | 9 | 2 |  |
| C promoce+mosty+učení | 0.33 | 0.00 | 10 | 1 | PŘIJATO · osy {'pridano': 328, 'odebrano': 0, 'hran_odebrano': 0} |
| E hloubka k=2 nad C | 0.40 | 0.00 | 10 | 0 |  |

Čtení: B je kontrola k C — rozdíl C−B je čistý příspěvek promovaných os (učení mají obě ramena stejné). D měří hloubku šíření samotnou na čistém baselinu, E její složení se stavem po C; sloupec vad = odpověď v dosahu, a přesto propadla (reach_report).

## Vylosované příklady (semínko 328, stav po posledním rameni)

| otázka | očekáváno | východisko | token | věta v kandidátech | vítězná věta |
|---|---|---|---|---|---|
| Kdy se narodil Ježíš? | (bez odpovědi) | dotaz | Abraham | — | Achim měl syna Eliuda, Eliud Eleazara, Eleazar Mattana, Mattan Jákoba, Jákob pak |
| K čemu slouží elektromotor? | přeměna | dotaz | přeměně | ano | Elektromotor je v elektrotechnice elektrický stroj, který slouží k přeměně elekt |
| Co popisuje zákon všeobecné gravitace? | přitahování | odpoved | přitahování | ano | Zákon všeobecné gravitace popisuje vzájemné přitahování hmotných těles. |
| Kdo zformuloval zákony termodynamiky? | (bez odpovědi) | odpoved | Newton | — | Paul Verlaine |
| Kolem čeho obíhá Měsíc? | země | odpoved | Země | ano | Měsíc obíhá kolem Země. |
| Co napsal Einstein? | (bez odpovědi) | odpoved | Pilát | — | Paul Verlaine |
