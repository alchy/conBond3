# Měření učení vah (4c kontrastivně + mlčení; 4b vyřazen) — komplexní korpusy

- datum: 2026-08-04 · η_kontrast=0.01 · epochy≤10
- 4b (Hebb) vyřazen z přejímací cesty (J. 2026-08-04; D4 — vrátí se až nad strukturou)
- kontrastivně: epoch=6 kroků=192 hran=13859
- kalibrace θ na trénovací sadě (D2): θ=2.125 · trénink přesnost 0.09 · mlčení 1.0

| epocha | loss (hinge marže) | trefy na tréninku | ticho (nezodp.) | korekcí | nových/změněných hran |
|---|---|---|---|---|---|
| 1 | 0.636 | 1/23 (0.04) | 0/10 | 32 | 2578 |
| 2 | 0.559 | 1/23 (0.04) | 0/10 | 32 | 2414 |
| 3 | 0.512 | 5/23 (0.22) | 0/10 | 32 | 1995 |
| 4 | 0.465 | 6/23 (0.26) | 0/10 | 32 | 2219 |
| 5 | 0.447 | 6/23 (0.26) | 0/10 | 32 | 2247 |
| 6 | 0.449 | 5/23 (0.22) | 0/10 | 32 | 2406 |
- trénink: 33 otázek · měření: 40 otázek (oddělené sady — parafráze vs. etalon)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.43 | 0.00 |
| po 4c (etalon) | 0.43 | 0.00 |
| po 4c, θ=2.125 | 0.33 | 1.00 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
