# Měření učení vah (4b Hebb + 4c kontrastivně)

- datum: 2026-08-04 · η_hebb=0.5 · η_kontrast=0.01 · epochy≤10
- Hebb: {'vet': 179, 'paru': 3817, 'hran': 1626}
- kontrastivně: epoch=10 kroků=227 hran=17203
- kalibrace θ na trénovací sadě (D2): θ=2.05 · trénink přesnost 0.88 · mlčení 0.86

| epocha | loss (hinge marže) | trefy na tréninku | ticho (nezodp.) | korekcí | nových/změněných hran |
|---|---|---|---|---|---|
| 1 | 0.216 | 25/33 (0.76) | 4/7 | 32 | 2164 |
| 2 | 0.157 | 29/33 (0.88) | 5/7 | 28 | 1989 |
| 3 | 0.13 | 32/33 (0.97) | 5/7 | 25 | 1855 |
| 4 | 0.108 | 32/33 (0.97) | 5/7 | 24 | 1908 |
| 5 | 0.096 | 32/33 (0.97) | 5/7 | 22 | 1701 |
| 6 | 0.088 | 32/33 (0.97) | 6/7 | 20 | 1626 |
| 7 | 0.083 | 32/33 (0.97) | 5/7 | 19 | 1534 |
| 8 | 0.077 | 32/33 (0.97) | 4/7 | 19 | 1399 |
| 9 | 0.073 | 32/33 (0.97) | 5/7 | 19 | 1528 |
| 10 | 0.07 | 32/33 (0.97) | 3/7 | 19 | 1499 |
- trénink: 40 otázek · měření: 40 otázek (TÁŽ sada — horní odhad, ne generalizace)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.85 | 0.00 |
| po 4b (Hebb) | 0.79 | 0.00 |
| po 4c (etalon) | 0.97 | 0.00 |
| po 4c, θ=2.05 | 0.85 | 0.86 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
