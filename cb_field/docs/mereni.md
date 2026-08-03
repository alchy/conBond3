# Měření cb_field — testbed kdo-kde-kdy

- datum: 2026-08-03
- verze modulu: 0.6.0
- data: testbed-kdo-kde-kdy.txt · 179 vět · 1006 tokenů · otisk sha256:468e643aba15
- středy podle R1 (výchozí varianta): 343
- registr po korpusu: 175 vertikál

## T2 — poměr šablon k středům (jediný test schopný koncept vyvrátit)

| konfigurace | šablon | středů | T2 | hodnocení | sdílených šablon |
|---|---|---|---|---|---|
| plné vertikály · střed uvnitř | 303 | 343 | 0.88 | okno nezobecňuje | 24 |
| plné vertikály · střed mimo | 267 | 343 | 0.78 | okno nezobecňuje | 39 |
| R2 vertikály · střed uvnitř | 245 | 343 | 0.71 | okno nezobecňuje | 52 |
| R2 vertikály · střed mimo | 203 | 343 | 0.59 | hraniční | 63 |

## Páky r (R4) a kanonizace pořadí (mitigace S1) — R2 vertikály, střed mimo

| konfigurace | šablon | středů | T2 | hodnocení | sdílených šablon |
|---|---|---|---|---|---|
| r=1 · linear | 119 | 343 | 0.35 | přijatelné | 53 |
| r=1 · canon | 115 | 343 | 0.34 | přijatelné | 54 |
| r=2 · linear | 203 | 343 | 0.59 | hraniční | 63 |
| r=2 · canon | 203 | 343 | 0.59 | hraniční | 63 |
| r=3 · linear | 259 | 343 | 0.76 | okno nezobecňuje | 49 |
| r=3 · canon | 255 | 343 | 0.74 | okno nezobecňuje | 50 |

Prahy dle README-EXTRAKCNI_VRSTVA § 5: ≤0,2 zdravé · ≤0,5 přijatelné · >0,7 okno nezobecňuje. Čísla se nesmí ohýbat po měření — když nevyhoví, mění se páky (R2, r, profil středu), ne prahy.
