# Měření učení vah (4b Hebb + 4c kontrastivně)

- datum: 2026-08-04 · η_hebb=0.5 · η_kontrast=0.01 · epochy≤10
- Hebb: {'vet': 179, 'paru': 3817, 'hran': 1626}
- kontrastivně: epoch=10 kroků=215 hran=16889

| epocha | loss (hinge marže) | trefy na tréninku | korekcí | nových/změněných hran |
|---|---|---|---|---|
| 1 | 0.247 | 25/33 (0.76) | 29 | 1978 |
| 2 | 0.18 | 29/33 (0.88) | 28 | 1968 |
| 3 | 0.15 | 32/33 (0.97) | 23 | 1744 |
| 4 | 0.126 | 32/33 (0.97) | 22 | 1730 |
| 5 | 0.113 | 32/33 (0.97) | 21 | 1713 |
| 6 | 0.105 | 32/33 (0.97) | 19 | 1566 |
| 7 | 0.097 | 32/33 (0.97) | 20 | 1733 |
| 8 | 0.088 | 32/33 (0.97) | 17 | 1477 |
| 9 | 0.082 | 32/33 (0.97) | 18 | 1490 |
| 10 | 0.081 | 32/33 (0.97) | 18 | 1490 |
- trénink: 40 otázek · měření: 40 otázek (TÁŽ sada — horní odhad, ne generalizace)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.85 | 0.00 |
| po 4b (Hebb) | 0.79 | 0.00 |
| po 4c (etalon) | 0.97 | 0.00 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
