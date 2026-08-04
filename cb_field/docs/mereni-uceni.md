# Měření učení vah (4b Hebb + 4c kontrastivně)

- datum: 2026-08-04 · η_hebb=0.5 · η_kontrast=0.01 · epochy≤10
- Hebb: {'vet': 179, 'paru': 3817, 'hran': 1626}
- kontrastivně: epoch=10 kroků=215 hran=16224
- kalibrace θ na trénovací sadě (D2): θ=2.029 · trénink přesnost 0.91 · mlčení 0.86

| epocha | loss (hinge marže) | trefy na tréninku | ticho (nezodp.) | korekcí | nových/změněných hran |
|---|---|---|---|---|---|
| 1 | 0.214 | 25/33 (0.76) | 5/7 | 31 | 2114 |
| 2 | 0.153 | 29/33 (0.88) | 6/7 | 25 | 1829 |
| 3 | 0.129 | 32/33 (0.97) | 5/7 | 24 | 1753 |
| 4 | 0.108 | 32/33 (0.97) | 5/7 | 24 | 1845 |
| 5 | 0.095 | 32/33 (0.97) | 4/7 | 21 | 1580 |
| 6 | 0.085 | 32/33 (0.97) | 4/7 | 21 | 1698 |
| 7 | 0.076 | 32/33 (0.97) | 4/7 | 19 | 1532 |
| 8 | 0.068 | 32/33 (0.97) | 4/7 | 18 | 1432 |
| 9 | 0.062 | 32/33 (0.97) | 5/7 | 16 | 1241 |
| 10 | 0.062 | 31/33 (0.94) | 4/7 | 16 | 1200 |
- trénink: 40 otázek · měření: 40 otázek (TÁŽ sada — horní odhad, ne generalizace)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.85 | 0.00 |
| po 4b (Hebb) | 0.79 | 0.00 |
| po 4c (etalon) | 0.94 | 0.00 |
| po 4c, θ=2.029 | 0.88 | 0.86 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
