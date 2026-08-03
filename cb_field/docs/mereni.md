# Měření cb_field — testbed kdo-kde-kdy

- datum: 2026-08-03
- verze modulu: 0.6.0
- data: testbed-kdo-kde-kdy.txt · 72 vět · 413 tokenů · otisk sha256:fe1981f179c4
- středy podle R1 (výchozí varianta): 141
- registr po korpusu: 154 vertikál

## T2 — poměr šablon k středům (jediný test schopný koncept vyvrátit)

| konfigurace | šablon | středů | T2 | hodnocení | sdílených šablon |
|---|---|---|---|---|---|
| plné vertikály · střed uvnitř | 134 | 141 | 0.95 | okno nezobecňuje | 5 |
| plné vertikály · střed mimo | 127 | 141 | 0.90 | okno nezobecňuje | 9 |
| R2 vertikály · střed uvnitř | 120 | 141 | 0.85 | okno nezobecňuje | 16 |
| R2 vertikály · střed mimo | 112 | 141 | 0.79 | okno nezobecňuje | 21 |

## Páky r (R4) a kanonizace pořadí (mitigace S1) — R2 vertikály, střed mimo

| konfigurace | šablon | středů | T2 | hodnocení | sdílených šablon |
|---|---|---|---|---|---|
| r=1 · linear | 81 | 141 | 0.57 | hraniční | 22 |
| r=1 · canon | 80 | 141 | 0.57 | hraniční | 22 |
| r=2 · linear | 112 | 141 | 0.79 | okno nezobecňuje | 21 |
| r=2 · canon | 112 | 141 | 0.79 | okno nezobecňuje | 21 |
| r=3 · linear | 124 | 141 | 0.88 | okno nezobecňuje | 13 |
| r=3 · canon | 121 | 141 | 0.86 | okno nezobecňuje | 13 |

Prahy dle README-EXTRAKCNI_VRSTVA § 5: ≤0,2 zdravé · ≤0,5 přijatelné · >0,7 okno nezobecňuje. Čísla se nesmí ohýbat po měření — když nevyhoví, mění se páky (R2, r, profil středu), ne prahy.
