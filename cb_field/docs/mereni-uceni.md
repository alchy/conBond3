# Měření učení vah (4c kontrastivně + mlčení; 4b vyřazen)

- datum: 2026-08-04 · η_kontrast=0.01 · epochy≤10
- 4b (Hebb) vyřazen z přejímací cesty (J. 2026-08-04; D4 — vrátí se až nad strukturou)
- kontrastivně: epoch=7 kroků=60 hran=4813
- kalibrace θ na trénovací sadě (D2): θ=1.989 · trénink přesnost 0.94 · mlčení 1.0

| epocha | loss (hinge marže) | trefy na tréninku | ticho (nezodp.) | korekcí | nových/změněných hran |
|---|---|---|---|---|---|
| 1 | 0.071 | 28/33 (0.85) | 7/7 | 10 | 848 |
| 2 | 0.054 | 30/33 (0.91) | 7/7 | 9 | 756 |
| 3 | 0.04 | 32/33 (0.97) | 7/7 | 9 | 749 |
| 4 | 0.032 | 33/33 (1.0) | 6/7 | 9 | 675 |
| 5 | 0.028 | 33/33 (1.0) | 6/7 | 6 | 418 |
| 6 | 0.025 | 33/33 (1.0) | 6/7 | 7 | 586 |
| 7 | 0.028 | 33/33 (1.0) | 6/7 | 10 | 781 |
- trénink: 40 otázek · měření: 40 otázek (TÁŽ sada — horní odhad, ne generalizace)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.85 | 0.00 |
| po 4c (etalon) | 1.00 | 0.00 |
| po 4c, θ=1.989 | 0.94 | 1.00 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
