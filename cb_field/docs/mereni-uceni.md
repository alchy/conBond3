# Měření učení vah (4b Hebb + 4c kontrastivně)

- datum: 2026-08-03 · η_hebb=0.5 · η_kontrast=0.01 · epochy≤10
- Hebb: {'vet': 179, 'paru': 3817, 'hran': 1626}
- kontrastivně: epoch=6 kroků=192 hran=16346

| epocha | loss (hinge marže) | trefy na tréninku | korekcí | nových/změněných hran |
|---|---|---|---|---|
| 1 | 0.324 | 16/33 (0.48) | 33 | 2872 |
| 2 | 0.267 | 20/33 (0.61) | 33 | 2633 |
| 3 | 0.235 | 23/33 (0.7) | 32 | 2588 |
| 4 | 0.21 | 24/33 (0.73) | 31 | 2565 |
| 5 | 0.203 | 24/33 (0.73) | 31 | 2724 |
| 6 | 0.222 | 24/33 (0.73) | 32 | 2964 |
- trénink: 40 otázek · měření: 40 otázek (TÁŽ sada — horní odhad, ne generalizace)

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.67 | 0.00 |
| po 4b (Hebb) | 0.45 | 0.00 |
| po 4c (etalon) | 0.79 | 0.00 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
