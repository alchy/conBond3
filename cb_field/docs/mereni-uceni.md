# Měření učení vah (4b Hebb + 4c kontrastivně)

- datum: 2026-08-03 · η_hebb=0.5 · η_kontrast=0.15 · epochy≤3
- Hebb: {'vet': 179, 'paru': 3817, 'hran': 1626} · kontrastivně: {'epoch': 3, 'kroku': 19, 'hran': 2360}
- POZOR: 4c laděno i měřeno na témže etalonu — číslo je horní odhad, ne generalizace (zapsaná mez).

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.79 | 0.71 |
| po 4b (Hebb) | 0.79 | 0.71 |
| po 4c (etalon) | 0.82 | 0.71 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
