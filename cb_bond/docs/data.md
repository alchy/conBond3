# Data pro cb_bond — soupis a ověřené počty

Zadání (`zadani.md`, § 0b a § 7) jmenuje data, od kterých se stavba odráží.
Tenhle soubor říká, kde ta data po přenosu leží a **jaké počty z nich reálně
vycházejí** — spočítané, ne opsané. Kdo staví krok 1, má tady zemní pravdu
pro přejímky; kdo najde rozdíl, ví, že se něco pokazilo v datech, ne v kódu.

Licenční dělení (co smí do gitu a co ne) je v kořenovém `ZDROJ.md`.

## Kde co leží

```
<data_root>/corpus/                  35 souborů, 2,6 MB — MIMO repozitář
    korpus-101…107.json    2 912 vět    Marek, fyzika, spisovatelé
    korpus-201.json          605 vět    vesmír (Wikipedie)
    korpus-202.json          600 vět    hudba (Wikipedie)
    korpus-301…326.json    8 141 vět    Nový zákon po knihách
                          ─────────
                          12 258 vět    ← součet pro build_corpus()

cb_field/tests/data/                 V gitu (vlastní texty a otázky)
    korpus/korpus-001.json    96 vět · 18 otázek    doprava
    korpus/korpus-002.json   103 vět · 18 otázek    příroda
    korpus/korpus-003.json    96 vět · 18 otázek    dějiny
    korpus/otazky-201.json     0 vět · 60 otázek    "corpus": korpus-201.json
    korpus/otazky-202.json     0 vět · 60 otázek    "corpus": korpus-202.json
    trenink-otazky-korpusy.jsonl   120 položek (75 zodpověditelných)
    etalon-otazky-korpusy.jsonl     40 položek (30 zodpověditelných)
    etalon-otazky.jsonl             40 položek  starší etalon (bez pole typ)
    testbed-kdo-kde-kdy.txt         ruční testbed
```

Supervize podle § 10 = 120 (trénink JSONL) + 2×60 (otázky-201/202) = **240**.
Etalon 40 do tréninku **nikdy**.

## Tvar souborů — co je ověřené

Všech 1 532 bloků v `<data_root>/corpus/` **má pole `text`** (původní
odstavec). Krok 1 se tedy o přednost `text` před `sentences` opře vždycky;
větev „blok bez textu" nastane jen u vlastních korpusů 001–003, kde pole
`text` nemá ani jeden blok.

Klíče: soubor `{format_version, language, blocks, questions}`, blok
`{topic, text, sentences}`, otázka `{text, sentence, answer_lemma,
answerable}`. Otázkový soubor navíc `corpus` a prázdné `blocks`.

Řádek trénink JSONL: `{otazka, odpoved_lemma, zodpoveditelna, most}` — pole
`most` je slovní popis jazykového mostu (např. „pasivum: byl od Jana pokřtěn
(VERB×ADJ)"), tedy poznámka pro člověka, ne vstup do učení. Řádek etalonu má
místo `most` pole `typ` (22 hodnot: `přímá`, `kopula`, `most: …`, `svod: …`).
Ani jeden z JSONL nenese index věty — větnou zemní pravdu (`answer_position`)
dávají jen otázkové soubory u korpusů.

## Jedna odchylka proti zadání

Zadání ukazuje větu o dálnici jako „globální index 12" v `korpus-001.json`.
Ve skutečnosti je na **indexu 4** a otázka na ni míří správně (`"sentence": 4`,
`answer_lemma: "třicet"`). Číslo 12 v zadání je schematické (vzorek je značen
„zkráceno") — **test se na 12 vázat nesmí**, referenční hodnota je 4.

Ověření: `korpus-001.json` blok „Dálnice a silniční síť" má 17 vět a věta
„Nejvyšší povolená rychlost na dálnici v Česku je sto třicet kilometrů za
hodinu." je pátá v pořadí.

## Jak počty přepočítat

```
./run-python -m cb_field.corpusfile <soubor>     # až bude krok 1 hotový
```

Do té doby platí, že počty výše vznikly součtem `len(block["sentences"])`
přes bloky a odpovídají § 0b zadání do kusu (2 912 · 605 · 600 · 8 141).
