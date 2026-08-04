# Měření učení vah (4b Hebb + 4c kontrastivně) — komplexní korpusy

- datum: 2026-08-04 · η_hebb=0.5 · η_kontrast=0.01 · epochy≤10
- Hebb: {'vet': 2912, 'paru': 232845, 'hran': 103371}
- kontrastivně: epoch=5 kroků=160 hran=13368
- kalibrace θ na trénovací sadě (D2): θ=2.919 · trénink přesnost 0.0 · mlčení 1.0

| epocha | loss (hinge marže) | trefy na tréninku | ticho (nezodp.) | korekcí | nových/změněných hran |
|---|---|---|---|---|---|
| 1 | 0.869 | 1/23 (0.04) | 0/10 | 32 | 2712 |
| 2 | 0.859 | 1/23 (0.04) | 0/10 | 32 | 2717 |
| 3 | 0.848 | 1/23 (0.04) | 0/10 | 32 | 2629 |
| 4 | 0.834 | 1/23 (0.04) | 0/10 | 32 | 2623 |
| 5 | 0.834 | 1/23 (0.04) | 0/10 | 32 | 2687 |
- trénink: 33 otázek · měření: 40 otázek (oddělené sady — parafráze vs. etalon)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.43 | 0.00 |
| po 4b (Hebb) | 0.17 | 0.00 |
| po 4c (etalon) | 0.20 | 0.00 |
| po 4c, θ=2.919 | 0.07 | 0.90 |

Výrok protokolu: **NEPŘIJATO — přesnost klesla** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
