# Měření učení vah (4c kontrastivně + mlčení; 4b vyřazen) — komplexní korpusy

- datum: 2026-08-04 · η_kontrast=0.01 · epochy≤10
- 4b (Hebb) vyřazen z přejímací cesty (J. 2026-08-04; D4 — vrátí se až nad strukturou)
- kontrastivně: epoch=3 kroků=300 hran=8072
- kalibrace θ na trénovací sadě (D2): θ=2.396 · trénink přesnost 0.01 · mlčení 1.0

| epocha | loss (hinge marže) | trefy na tréninku | ticho (nezodp.) | korekcí | nových/změněných hran |
|---|---|---|---|---|---|
| 1 | 0.619 | 1/71 (0.01) | 0/33 | 100 | 2760 |
| 2 | 0.603 | 2/71 (0.03) | 0/33 | 100 | 2624 |
| 3 | 0.673 | 2/71 (0.03) | 0/33 | 100 | 2688 |
- trénink: 104 otázek · měření: 40 otázek (oddělené sady — parafráze vs. etalon)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.37 | 0.00 |
| po 4c (etalon) | 0.47 | 0.00 |
| po 4c, θ=2.396 | 0.13 | 1.00 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
