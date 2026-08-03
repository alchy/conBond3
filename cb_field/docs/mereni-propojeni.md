# Měření propojení (4a, ruční W) — etalon otázek

- datum: 2026-08-03 · verze modulu 0.7.0 · θ=0.0 · ε=0.25 · r=1
- data: testbed sha256:468e643aba15 · etalon sha256:e9c1bda9ab9f (40 otázek)

| metrika | hodnota |
|---|---|
| přesnost@1 (zodpověditelné) | 26/33 = 0.79 |
| NEVÍM-správnost (nezodpověditelné) | 5/7 = 0.71 |
| SLABÁ | 2 |
| NEPŘESNÁ | 0 |
| NEPOKRYTÁ | 1 |
| DOTAZ | 4 |
| NEVÍM-chybné | 0 |
| FALEŠNÁ | 1 |
| DOTAZ-nezodp. | 1 |

| otázka | výsledek | odpověď | očekáváno | skóre |
|---|---|---|---|---|
| Kde bydlí Jana? | SPRÁVNĚ | Brně | Brno | 4.41 |
| Kde bydlí Petr? | SPRÁVNĚ | Liberci | Liberec | 4.41 |
| Kde pracuje Marie? | SPRÁVNĚ | kanceláři | kancelář | 3.92 |
| Kde pracuje Eva? | SPRÁVNĚ | poště | pošta | 3.92 |
| Kde spí kočka? | SPRÁVNĚ | kuchyni | kuchyň | 3.92 |
| Kde je Petr? | SPRÁVNĚ | Praze | Praha | 8.33 |
| Kde čeká řidič? | SPRÁVNĚ | nádražím | nádraží | 3.92 |
| Kde sedí děda? | DOTAZ | lavičce | lavička | 3.92 |
| Kde se pase kůň? | SPRÁVNĚ | louce | louka | 4.41 |
| Kde spí pes? | SPRÁVNĚ | boudě | bouda | 3.92 |
| Kam šel Karel? | SPRÁVNĚ | lesa | les | 3.92 |
| Kam běžel pes? | SPRÁVNĚ | zahrady | zahrada | 3.92 |
| Kam letěla Soňa? | SPRÁVNĚ | Paříže | Paříž | 4.90 |
| Kam jela Marie? | SPRÁVNĚ | Ostravy | Ostrava | 7.35 |
| Kam jeli turisté? | SPRÁVNĚ | hory | hora | 4.90 |
| Odkud přijela teta? | SPRÁVNĚ | Ameriky | Amerika | 4.90 |
| Odkud odjela Soňa? | SPRÁVNĚ | Prahy | Praha | 4.90 |
| Odkud přijel Pavel? | SPRÁVNĚ | Liberce | Liberec | 4.41 |
| Odkud se vrátili sousedé? | SPRÁVNĚ | hor | hora | 4.41 |
| Odkud se vrátil Karel? | SPRÁVNĚ | práce | práce | 4.41 |
| Kdy přijel Petr do Brna? | SLABÁ | školy | leden | 10.78 |
| Kdy odjel Petr do Vídně? | SLABÁ | Plzně | pondělí | 11.76 |
| Kdy začíná schůze? | SPRÁVNĚ | devět | devět | 2.45 |
| Kdy odjíždí autobus z nádraží? | SPRÁVNĚ | poledne | poledne | 5.88 |
| Kdy se přestěhoval Karel do Plzně? | SPRÁVNĚ | březnu | březen | 6.86 |
| Kdy odletěli ptáci na jih? | SPRÁVNĚ | říjnu | říjen | 5.39 |
| Kdy odjela Jana do Vídně? | NEPOKRYTÁ | Plzně | včera | 12.74 |
| Kolik dětí čekalo před školou? | DOTAZ | Řidič | pět | 7.84 |
| Kdo bydlí v Liberci? | SPRÁVNĚ | Petr | Petr | 7.35 |
| Kdo pracuje v nemocnici? | DOTAZ | Marie | lékař | 6.86 |
| Kdo se vrátil z hor? | DOTAZ | Karel | soused | 4.41 |
| Kdo spí v boudě? | SPRÁVNĚ | Pes | pes | 6.86 |
| Kdo studuje v Olomouci? | SPRÁVNĚ | Soňa | Soňa | 7.35 |
| Kde bydlí Alois? | MLČENÍ-správné | — | None | — |
| Kdo bydlí v Ostravě? | DOTAZ-nezodp. | Jana | None | 6.86 |
| Kam letěl Karel? | MLČENÍ-správné | — | None | — |
| Kdy odjel Honza? | MLČENÍ-správné | — | None | — |
| Kde parkuje Petr? | MLČENÍ-správné | — | None | — |
| Kolik koček čekalo před školou? | FALEŠNÁ | dětí | None | 10.29 |
| Odkud přijela Marie? | MLČENÍ-správné | — | None | — |

Diagnóza řídí další krok (README-PROPOJENI § 5): SLABÁ → učení vah (4b/4c); NEPŘESNÁ → fronta růstu os; NEPOKRYTÁ → známé díry reprezentace (typ — krok 5, slot kdy — krok 3).
