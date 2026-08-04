# Fixovaný korpus v JSON — číslované věty a otázky na indexy

Zadání J. (2026-08-04): korpus fixovat v JSONu — věty číslované, korpus
rozsekán po blocích, otázky míří na **index věty** z daného souboru.
**Pojmenování souboru nemá co dělat s obsahem a nesmí v programu nést
významovou váhu** — program bere jméno jako neprůhledný identifikátor
(žádné mapy klíčované doménou, jako měl `measure_corpora.DOMAINS`).

Soubory žijí zmražené v gitu v `tests/data/korpus/` (§ 13 politiky:
původní text psaný pro projekt, žádná licence třetí strany; licencované
korpusy zůstávají mimo git v `data-persistent/corpora/`). Jména souborů
jsou neutrální pořadová: `korpus-001.json`, `korpus-002.json`, …

## Formát (format_version 1)

```json
{
  "format_version": 1,
  "language": "cs",
  "blocks": [
    {
      "topic": "volný popisek pro člověka — program ho nečte",
      "sentences": [
        "První věta bloku.",
        "Druhá věta bloku."
      ]
    }
  ],
  "questions": [
    {
      "text": "Na co se ptám?",
      "sentence": 12,
      "answer_lemma": "odpověď",
      "answerable": true
    },
    {
      "text": "Otázka, na kterou text neodpovídá?",
      "sentence": null,
      "answer_lemma": null,
      "answerable": false
    }
  ]
}
```

Pravidla:

- **Index věty je globální v rámci souboru**, 0 od začátku, počítá se
  přes bloky v pořadí zápisu. Otázka míří na index věty, ve které leží
  odpověď; nezodpověditelná otázka má `sentence: null`.
- **Jedna položka pole = přesně jedna věta.** Rozpadne-li se položka
  parserem na víc vět, je to hlasitá chyba zápisu dat, ne tiché vzetí
  první — číslování by se rozjelo.
- **Blok = souvislý text** (hranice dokumentu pro `r_sentences`):
  kontext teče jen uvnitř bloku. `topic` je popisek pro člověka,
  program na něm nesmí nic stavět.
- `answer_lemma` je základní tvar slova, které ve větě s odpovědí
  opravdu je (kontroluje validace parserem).

## Nástroje

- Čtení a stavba korpusu: `cb_field/corpusfile.py` (závislosti
  parametrem — parser se předává, § 3).
- Validace souboru: `./run-python -m cb_field.corpusfile <cesta>…` —
  zkontroluje formát, 1 položka = 1 věta, rozsahy indexů
  a `answer_lemma` proti lemmatům cílové věty.
