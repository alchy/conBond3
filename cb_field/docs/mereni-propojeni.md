# Měření propojení (4a, ruční W) — etalon otázek

- datum: 2026-08-03 · verze modulu 0.9.0 · θ=0.45 · ε=0.057 · r=1
- data: testbed sha256:468e643aba15 · etalon sha256:e9c1bda9ab9f (40 otázek)

| metrika | hodnota |
|---|---|
| přesnost@1 (zodpověditelné) | 22/33 = 0.67 |
| NEVÍM-správnost (nezodpověditelné) | 0/7 = 0.00 |
| SLABÁ | 0 |
| NEPŘESNÁ | 0 |
| NEPOKRYTÁ | 0 |
| DOTAZ | 11 |
| NEVÍM-chybné | 0 |
| FALEŠNÁ | 3 |
| DOTAZ-nezodp. | 4 |

| otázka | výsledek | odpověď | očekáváno | skóre |
|---|---|---|---|---|
| Kde bydlí Jana? | SPRÁVNĚ | Brně | Brno | 1.63 |
| Kde bydlí Petr? | DOTAZ | Liberci | Liberec | 1.63 |
| Kde pracuje Marie? | SPRÁVNĚ | kanceláři | kancelář | 1.53 |
| Kde pracuje Eva? | SPRÁVNĚ | poště | pošta | 1.53 |
| Kde spí kočka? | SPRÁVNĚ | kuchyni | kuchyň | 1.56 |
| Kde je Petr? | SPRÁVNĚ | Praze | Praha | 1.84 |
| Kde čeká řidič? | SPRÁVNĚ | nádražím | nádraží | 1.56 |
| Kde sedí děda? | DOTAZ | parku | lavička | 1.45 |
| Kde se pase kůň? | SPRÁVNĚ | louce | louka | 1.59 |
| Kde spí pes? | SPRÁVNĚ | boudě | bouda | 1.56 |
| Kam šel Karel? | DOTAZ | lesa | les | 1.53 |
| Kam běžel pes? | SPRÁVNĚ | zahrady | zahrada | 1.56 |
| Kam letěla Soňa? | DOTAZ | odjela | Paříž | 1.51 |
| Kam jela Marie? | DOTAZ | Prahy | Ostrava | 1.62 |
| Kam jeli turisté? | SPRÁVNĚ | hory | hora | 1.50 |
| Odkud přijela teta? | SPRÁVNĚ | Ameriky | Amerika | 1.65 |
| Odkud odjela Soňa? | SPRÁVNĚ | Prahy | Praha | 1.62 |
| Odkud přijel Pavel? | SPRÁVNĚ | Liberce | Liberec | 1.57 |
| Odkud se vrátili sousedé? | SPRÁVNĚ | hor | hora | 1.59 |
| Odkud se vrátil Karel? | DOTAZ | Eva | práce | 1.50 |
| Kdy přijel Petr do Brna? | SPRÁVNĚ | lednu | leden | 1.65 |
| Kdy odjel Petr do Vídně? | DOTAZ | Plzně | pondělí | 1.67 |
| Kdy začíná schůze? | DOTAZ | Dovolená | devět | 1.37 |
| Kdy odjíždí autobus z nádraží? | SPRÁVNĚ | poledne | poledne | 1.52 |
| Kdy se přestěhoval Karel do Plzně? | SPRÁVNĚ | březnu | březen | 1.66 |
| Kdy odletěli ptáci na jih? | SPRÁVNĚ | říjnu | říjen | 1.58 |
| Kdy odjela Jana do Vídně? | DOTAZ | šla | včera | 1.69 |
| Kolik dětí čekalo před školou? | DOTAZ | zastavil | pět | 1.62 |
| Kdo bydlí v Liberci? | SPRÁVNĚ | Petr | Petr | 1.85 |
| Kdo pracuje v nemocnici? | SPRÁVNĚ | Lékař | lékař | 1.77 |
| Kdo se vrátil z hor? | DOTAZ | Sousedé | soused | 1.58 |
| Kdo spí v boudě? | SPRÁVNĚ | Pes | pes | 1.77 |
| Kdo studuje v Olomouci? | SPRÁVNĚ | Soňa | Soňa | 1.85 |
| Kde bydlí Alois? | FALEŠNÁ | Petr | None | 1.53 |
| Kdo bydlí v Ostravě? | DOTAZ-nezodp. | Brně | None | 1.68 |
| Kam letěl Karel? | FALEŠNÁ | zůstal | None | 1.49 |
| Kdy odjel Honza? | DOTAZ-nezodp. | dorazil | None | 1.46 |
| Kde parkuje Petr? | FALEŠNÁ | bydlí | None | 1.75 |
| Kolik koček čekalo před školou? | DOTAZ-nezodp. | zastavil | None | 1.62 |
| Odkud přijela Marie? | DOTAZ-nezodp. | nejela | None | 1.51 |

Diagnóza řídí další krok (README-PROPOJENI § 5): SLABÁ → učení vah (4b/4c); NEPŘESNÁ → fronta růstu os; NEPOKRYTÁ → známé díry reprezentace (typ — krok 5, slot kdy — krok 3).
