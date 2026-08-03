# Měření učení vah (4b Hebb + 4c kontrastivně) — komplexní korpusy

- datum: 2026-08-03 · η_hebb=0.5 · η_kontrast=0.15 · epochy≤3
- Hebb: {'vet': 2912, 'paru': 232798, 'hran': 103365}
- kontrastivně: epoch=3 kroků=96 hran=11603

| epocha | loss (hinge marže) | trefy na tréninku | korekcí | nových/změněných hran |
|---|---|---|---|---|
| 1 | 867.405 | 0/32 (0.0) | 32 | 3917 |
| 2 | 810.172 | 0/32 (0.0) | 32 | 3843 |
| 3 | 763.848 | 0/32 (0.0) | 32 | 3843 |
- trénink: 35 otázek · měření: 25 otázek (oddělené sady — parafráze vs. etalon)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.21 | 0.00 |
| po 4b (Hebb) | 0.00 | 0.00 |
| po 4c (etalon) | 0.00 | 0.00 |

Výrok protokolu: **NEPŘIJATO — přesnost klesla** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
