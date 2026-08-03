# Měření propojení (4a, ruční W) — etalon otázek

- datum: 2026-08-04 · verze modulu 0.9.0 · θ=0.45 · ε=0.057 · r=1
- data: testbed sha256:468e643aba15 · etalon sha256:e9c1bda9ab9f (40 otázek)

| metrika | hodnota |
|---|---|
| přesnost@1 (zodpověditelné) | 28/33 = 0.85 |
| NEVÍM-správnost (nezodpověditelné) | 0/7 = 0.00 |
| SLABÁ | 1 |
| NEPŘESNÁ | 0 |
| NEPOKRYTÁ | 0 |
| DOTAZ | 4 |
| NEVÍM-chybné | 0 |
| FALEŠNÁ | 3 |
| DOTAZ-nezodp. | 4 |

| otázka | výsledek | odpověď | očekáváno | skóre |
|---|---|---|---|---|
| Kde bydlí Jana? | SPRÁVNĚ | Brně | Brno | 2.24 |
| Kde bydlí Petr? | DOTAZ | Liberci | Liberec | 2.24 |
| Kde pracuje Marie? | SPRÁVNĚ | kanceláři | kancelář | 2.13 |
| Kde pracuje Eva? | SPRÁVNĚ | poště | pošta | 2.13 |
| Kde spí kočka? | SPRÁVNĚ | kuchyni | kuchyň | 2.16 |
| Kde je Petr? | SPRÁVNĚ | Praze | Praha | 2.45 |
| Kde čeká řidič? | SPRÁVNĚ | nádražím | nádraží | 2.16 |
| Kde sedí děda? | DOTAZ | parku | lavička | 2.05 |
| Kde se pase kůň? | SPRÁVNĚ | louce | louka | 2.20 |
| Kde spí pes? | SPRÁVNĚ | boudě | bouda | 2.16 |
| Kam šel Karel? | SPRÁVNĚ | lesa | les | 2.13 |
| Kam běžel pes? | SPRÁVNĚ | zahrady | zahrada | 2.16 |
| Kam letěla Soňa? | SPRÁVNĚ | Paříže | Paříž | 2.09 |
| Kam jela Marie? | DOTAZ | Prahy | Ostrava | 2.22 |
| Kam jeli turisté? | SPRÁVNĚ | hory | hora | 2.10 |
| Odkud přijela teta? | SPRÁVNĚ | Ameriky | Amerika | 2.25 |
| Odkud odjela Soňa? | SPRÁVNĚ | Prahy | Praha | 2.22 |
| Odkud přijel Pavel? | SPRÁVNĚ | Liberce | Liberec | 2.18 |
| Odkud se vrátili sousedé? | SPRÁVNĚ | hor | hora | 2.20 |
| Odkud se vrátil Karel? | SPRÁVNĚ | práce | práce | 2.05 |
| Kdy přijel Petr do Brna? | SPRÁVNĚ | lednu | leden | 2.25 |
| Kdy odjel Petr do Vídně? | SPRÁVNĚ | pondělí | pondělí | 2.25 |
| Kdy začíná schůze? | SLABÁ | v | devět | 1.73 |
| Kdy odjíždí autobus z nádraží? | SPRÁVNĚ | poledne | poledne | 2.13 |
| Kdy se přestěhoval Karel do Plzně? | SPRÁVNĚ | březnu | březen | 2.26 |
| Kdy odletěli ptáci na jih? | SPRÁVNĚ | říjnu | říjen | 2.18 |
| Kdy odjela Jana do Vídně? | SPRÁVNĚ | včera | včera | 1.94 |
| Kolik dětí čekalo před školou? | DOTAZ | . | pět | 1.98 |
| Kdo bydlí v Liberci? | SPRÁVNĚ | Petr | Petr | 2.45 |
| Kdo pracuje v nemocnici? | SPRÁVNĚ | Lékař | lékař | 2.37 |
| Kdo se vrátil z hor? | SPRÁVNĚ | Sousedé | soused | 2.19 |
| Kdo spí v boudě? | SPRÁVNĚ | Pes | pes | 2.37 |
| Kdo studuje v Olomouci? | SPRÁVNĚ | Soňa | Soňa | 2.45 |
| Kde bydlí Alois? | FALEŠNÁ | Petr | None | 1.53 |
| Kdo bydlí v Ostravě? | DOTAZ-nezodp. | Brně | None | 1.68 |
| Kam letěl Karel? | FALEŠNÁ | zůstal | None | 1.49 |
| Kdy odjel Honza? | DOTAZ-nezodp. | dorazil | None | 1.46 |
| Kde parkuje Petr? | FALEŠNÁ | bydlí | None | 1.75 |
| Kolik koček čekalo před školou? | DOTAZ-nezodp. | zastavil | None | 1.59 |
| Odkud přijela Marie? | DOTAZ-nezodp. | nejela | None | 1.51 |

Diagnóza řídí další krok (README-PROPOJENI § 5): SLABÁ → učení vah (4b/4c); NEPŘESNÁ → fronta růstu os; NEPOKRYTÁ → známé díry reprezentace (typ — krok 5, slot kdy — krok 3).
