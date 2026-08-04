# Měření učení vah (4c kontrastivně + mlčení; 4b vyřazen)

- datum: 2026-08-04 · η_kontrast=0.01 · epochy≤10
- 4b (Hebb) vyřazen z přejímací cesty (J. 2026-08-04; D4 — vrátí se až nad strukturou)
- kontrastivně: epoch=10 kroků=90 hran=2654
- kalibrace θ na trénovací sadě (D2): θ=1.875 · trénink přesnost 0.94 · mlčení 1.0

| epocha | loss (hinge marže) | trefy na tréninku | ticho (nezodp.) | korekcí | nových/změněných hran |
|---|---|---|---|---|---|
| 1 | 0.07 | 28/33 (0.85) | 7/7 | 10 | 304 |
| 2 | 0.065 | 29/33 (0.88) | 7/7 | 9 | 281 |
| 3 | 0.062 | 30/33 (0.91) | 7/7 | 9 | 281 |
| 4 | 0.059 | 30/33 (0.91) | 7/7 | 10 | 286 |
| 5 | 0.057 | 30/33 (0.91) | 7/7 | 9 | 261 |
| 6 | 0.055 | 30/33 (0.91) | 7/7 | 9 | 261 |
| 7 | 0.053 | 30/33 (0.91) | 7/7 | 9 | 259 |
| 8 | 0.052 | 30/33 (0.91) | 7/7 | 8 | 237 |
| 9 | 0.052 | 30/33 (0.91) | 7/7 | 9 | 259 |
| 10 | 0.051 | 30/33 (0.91) | 7/7 | 8 | 225 |
- trénink: 40 otázek · měření: 40 otázek (TÁŽ sada — horní odhad, ne generalizace)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.85 | 0.00 |
| po 4c (etalon) | 0.88 | 0.00 |
| po 4c, θ=1.875 | 0.88 | 1.00 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
