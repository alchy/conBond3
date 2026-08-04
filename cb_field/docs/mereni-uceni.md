# Měření učení vah (4c kontrastivně + mlčení; 4b vyřazen)

- datum: 2026-08-04 · η_kontrast=0.01 · epochy≤10
- 4b (Hebb) vyřazen z přejímací cesty (J. 2026-08-04; D4 — vrátí se až nad strukturou)
- kontrastivně: epoch=9 kroků=88 hran=5846
- kalibrace θ na trénovací sadě (D2): θ=1.889 · trénink přesnost 0.97 · mlčení 1.0

| epocha | loss (hinge marže) | trefy na tréninku | ticho (nezodp.) | korekcí | nových/změněných hran |
|---|---|---|---|---|---|
| 1 | 0.078 | 28/33 (0.85) | 7/7 | 22 | 1415 |
| 2 | 0.055 | 31/33 (0.94) | 5/7 | 12 | 866 |
| 3 | 0.041 | 32/33 (0.97) | 5/7 | 11 | 774 |
| 4 | 0.03 | 33/33 (1.0) | 6/7 | 7 | 391 |
| 5 | 0.025 | 33/33 (1.0) | 6/7 | 8 | 541 |
| 6 | 0.021 | 33/33 (1.0) | 6/7 | 7 | 486 |
| 7 | 0.02 | 33/33 (1.0) | 6/7 | 7 | 457 |
| 8 | 0.019 | 33/33 (1.0) | 6/7 | 7 | 467 |
| 9 | 0.021 | 33/33 (1.0) | 6/7 | 7 | 449 |
- trénink: 40 otázek · měření: 40 otázek (TÁŽ sada — horní odhad, ne generalizace)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.85 | 0.00 |
| po 4c (etalon) | 1.00 | 0.00 |
| po 4c, θ=1.889 | 0.97 | 1.00 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
