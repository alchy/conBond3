# Měření učení vah (4b Hebb + 4c kontrastivně) — komplexní korpusy

- datum: 2026-08-03 · η_hebb=0.5 · η_kontrast=0.15 · epochy≤3
- Hebb: {'vet': 2912, 'paru': 232798, 'hran': 103365} · kontrastivně: {'epoch': 3, 'kroku': 25, 'hran': 3414}
- POZOR: 4c laděno i měřeno na témže etalonu — číslo je horní odhad, ne generalizace (zapsaná mez).

| fáze | přesnost@1 | NEVÍM-správnost |
|---|---|---|
| baseline (axiomy) | 0.37 | 0.33 |
| po 4b (Hebb) | 0.32 | 0.33 |
| po 4c (etalon) | 0.42 | 0.33 |

Výrok protokolu: **PŘIJATO** (učení, které shodí NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený registr: `data-persistent/verticals-learned.json`.
