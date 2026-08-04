# Měření detekce mezery a dialogu (krok 4 handoveru)

- datum: 2026-08-04 · verze modulu 0.10.0 · korpus 2912 vět + 1 dialogová

## Jak je omezena rychlost na dálnici?

| osa | pokrytí před | po doplnění |
|---|---|---|
| WORD=AUX:být | 0.761 | 0.761 |
| WORD=ADJ:omezený | 0.540 | 0.540 |
| WORD=NOUN:rychlost | 0.540 | 0.540 |
| WORD=ADP:na | 0.761 | 0.761 |
| WORD=NOUN:dálnice | 0.000 | 0.540 |

Východisko před: **needs_context** (missing ['WORD=NOUN:dálnice']), po: **dotaz**.

## Kde byl pokřtěn Ježíš?

| osa | pokrytí |
|---|---|
| WORD=AUX:být | 0.761 |
| WORD=ADJ:pokřtěný | 0.540 |
| WORD=PROPN:Ježíš | 0.709 |

## Co dialog přidal do grafu

Uzly: NOUN:dálnice.

| od | do | deprel |
|---|---|---|
| NOUN:dálnice | NOUN:silnice | nsubj |
| ADJ:motorový | NOUN:vozidlo | amod |
| NOUN:vozidlo | NOUN:silnice | nmod |
| ADV:kde | ADJ:stanovený | advmod |
| ADJ:stanovený | NOUN:silnice | acl:relcl |
| NOUN:rychlost | ADJ:stanovený | nsubj:pass |
| NUM:130 | ADJ:stanovený | obl:arg |
| NOUN:kilometr | NUM:130 | nmod |
| NOUN:hodina | NOUN:kilometr | nmod |

## Kontroly

| kontrola | stav |
|---|---|
| mezera otázky o dálnici je právě WORD=NOUN:dálnice | OK |
| rychlost korpus zná (fyzika) — neoznačí se | OK |
| otázka o křtu je pokrytá — missing prázdné | OK |
| reply vrací kandidáta i při mezeře (nemlčí) | OK |
| po append_context má dálnice nenulové pokrytí | OK |
| po doplnění už otázka mezeru nehlásí | OK |
| v grafu přibyly hrany se zdrojem dialog | OK |
| v grafu přibyly uzly (dálnice…) | OK |

Prošlo 8/8 kontrol.
