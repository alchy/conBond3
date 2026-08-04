# Měření grafu faktů (krok 1 handoveru)

- datum: 2026-08-04 · verze modulu 0.9.0 · korpus 2912 vět

## Graf podle handoveru (uzel = UPOS:lemma)

- uzlů s hranou **5727** · hranových instancí **16074** · průměrný stupeň **5.61** · průměr různých sousedů **4.54**

## Čtení referenčního měření (uzel = lemma)

Referenční čísla ze 4. 8. 2026 klíčovala uzly jen lemmatem; sloučení UPOS mění jen uzly, které jsou víc slovními druhy najednou (stát). Hranové instance na klíči nezávisejí a sedí přesně.

## Promoce do custom vertikál (krok 2)

Skóre = různých²/hran, limit 328 custom vertikál; vlastních jmen v limitu 11 (3%). Hranice posledního místa: `VERB:představovat` se skóre 12.1.

| # | uzel | různých | hran | skóre |
|---|---|---|---|---|
| 1 | NOUN:rok | 162 | 191 | 137.4 |
| 2 | VERB:mít | 185 | 260 | 131.6 |
| 3 | VERB:říci | 178 | 308 | 102.9 |
| 4 | VERB:moci | 119 | 147 | 96.3 |
| 5 | VERB:jít | 129 | 174 | 95.6 |
| 6 | VERB:přijít | 124 | 168 | 91.5 |
| 7 | NOUN:část | 88 | 100 | 77.4 |
| 8 | VERB:stát | 81 | 89 | 73.7 |
| 9 | NOUN:život | 90 | 110 | 73.6 |
| 10 | VERB:vyjít | 82 | 97 | 69.3 |
| 11 | NOUN:povídka | 87 | 115 | 65.8 |
| 12 | NOUN:léta | 79 | 97 | 64.3 |

Kam padla vlastní jména: Praha 19. · Karel 35. · Ježíš 45. · Bohumil 52. — Hrabal mimo limit.

Otevřené k rozhodnutí (J.): dělení rozpočtu 328 mezi slova a typy vztahů — typy zatím v grafu nejsou, soutěží jen slova.

## Kontroly

| kontrola | stav |
|---|---|
| vet = 2912 | OK |
| lemmat = 5695 | OK |
| hran = 16074 | OK |
| prumerny_stupen = 5.6 | OK |
| prumer_ruznych = 4.6 | OK |
| mít 185/260/118 | OK |
| říci 177/308/160 | OK |
| rok 162/191/93 | OK |
| jít 129/174/78 | OK |
| přijít 124/168/71 | OK |
| moci 119/147/60 | OK |
| stát 85/93/42 | OK |
| stroj 79/144/81 | OK |
| Karel 75/152/70 | OK |
| začít 62/67/30 | OK |
| Ježíš 60/111/106 | OK |
| Bohumil 60/120/55 | OK |
| promoce obsahuje NOUN:rok | OK |
| promoce obsahuje VERB:mít | OK |
| promoce obsahuje VERB:moci | OK |
| promoce obsahuje VERB:stát | OK |
| promoce obsahuje VERB:začít | OK |
| promoce obsahuje NOUN:dílo | OK |
| PROPN:Hrabal mimo limit | OK |
| podíl vlastních jmen <= 10 % | OK |
| dvojí zavolání = identický seznam | OK |

Prošlo 26/26 kontrol.
