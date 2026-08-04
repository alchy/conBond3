# cb_field — extrakční vrstva: pole, koše, vážené aktivace

Modul dělá z rozebrané české věty **pole**: řádek na slovo, vertikála na
dvojici atribut=hodnota, buňka = váha. Nad polem staví koše posuvného
okna a matice pro počítání; k tomu drží append-only registr vertikál
s váženými vazbami a kukátko (viewer) na prohlížení.

Vývojářský průvodce s ukázkami je v kořeni: `README-FIELD.md`.
Návrhová rozhodnutí a pasti: `docs/`.

## Stav: mockup (verze 0.7.0)

Vědomě zatím **není** plný modul podle README-MODULES § 2: chybí
konfigurace se schématem, logování přes cb-logger, REST API (`api.py`),
`control.py` + `cb-field.py` a klient. Doplní se podle § 16, až se tvar
usadí. Co už platí: čistá doménová logika bez cest a HTTP (`service.py`,
`field.py`), verzované formáty souborů, testy na zmražených datech.

## Rozhraní (veřejné API)

| jméno | co to je |
|---|---|
| `Corpus` | posloupnost polí nad JEDNÍM registrem: `add_sentence`/`add_text`/`add_document`, `documents`, `document_span`, `regenerate()`, `positions` |
| `load_corpus_file`, `add_to_corpus`, `build_corpus`, `etalon_entries` | fixovaný korpus v JSON (`corpusfile.py`) — čtení, validace, stavba, otázky ve tvaru etalonu |
| `CorpusFile`, `CorpusBlock`, `CorpusQuestion` | přečtená fixace: bloky (odstavce) a otázky mířící na index věty |
| `SentenceField` | pracovní úroveň: `from_text` / `from_sentence`, pohledy `metadata`/`complete`/`array`, `baskets`, `matrix()`, `show()` |
| `FieldBasket` | koš pole s touž trojicí pohledů; `array` má pevný tvar 2r+1 řádků |
| `VerticalRegistry` | append-only osa sloupců: `add`, `key(i)`, `vectorize`/`unvectorize`, `link`/`get_link`/`unlink`/`links`/`spread`, custom sloty (`set_custom_axes`, `axis_version`, `custom_axes`, `is_custom`), vratnost (`snapshot`/`restore`), `save`/`load` |
| `Activations` | vážené aktivace slova: `get`/`set`, `weights(representation)`, `as_array` |
| `Representation` | `METADATA` (bezeslovná, primární) / `COMPLETE` (+`WORD=`) |
| `MetaValue`, `Basket`, `build_baskets`, `expand_token`, `expand_basket`, `activations`, `is_question`, `seed_anchor_links` | nižší (ladicí) vrstvy |
| `Visualizer` / `visualize` | publikace do kukátka mimo SentenceField (starší cesta; `sentence.show()` je pracovní) |

## Porty

| port | co |
|---|---|
| 42300 | rezervováno pro budoucí REST API modulu |
| 42301 | kukátko na pole (viewer) — `./run-python -m cb_field.viewer` |

Tabulka rozsahů je v README-MODULES § 5 (cb-field má 42300–42399).

## Registr prahů

| id | hodnota | co ovlivňuje | zdůvodnění |
|---|---|---|---|
| `FEAT_SLOTS` | 4 | šířka slotů na klíč feats | naměřené maximum jsou 2 hodnoty (`Fem,Neut`); dvojnásobná rezerva (2026-08-03) |
| `DEFAULT_WEIGHT` | 0.7 | váha, se kterou se aktivace rodí | stanovená startovní hodnota (zadání J., 2026-08-03); ladit ji bude pozdější vrstva |
| `WEIGHT_MIN/MAX` | −1.0 / +1.0 | meze vah; znaménko = druh vazby | zadání J.; hlídá se při zápisu, ne až v počítání |
| viewer poll | 1000 ms | obnova stránky kukátka | dost rychlé na práci, dost líné na klid |

Až vznikne konfigurace modulu, prahy se přestěhují do ní.

## Závislosti

| závislost | druh | pozn. |
|---|---|---|
| `cb_udpipe` (import) | povinná | typ `Token`; `from_text` navíc potřebuje předaný parser (běžící službu) |
| `numpy` | povinná | **schválená výjimka** z pravidla „moduly bez závislostí" (§ 19) — koše jsou matice vah; zapsáno v requirements.txt |
| kukátko (viewer) | nepovinná | `show()` bez běžící služby jen vypíše, čím ji spustit |
| `cb_logger` | zatím žádná | napojí se při stavbě plného modulu |

## Formáty souborů

| soubor | formát | verze |
|---|---|---|
| registr vertikál (`save`/`load`) | JSON: `format_version`, `keys[]`, `links[[od,do,váha]]`, `custom_axes[]`, `axis_version` | 2 — cizí verze se odmítá |
| fixovaný korpus (`corpusfile`) | JSON: `format_version`, `language`, `blocks[{topic,text,sentences}]`, `questions[{text,sentence,answer_lemma,answerable}]`; otázkový soubor navíc `corpus` | 1 — cizí verze se odmítá |
| `run/current.json` | soukromá přepravka viewer↔stránka; žije a umírá s kukátkem | neverzuje se |

## Co modul vědomě neřeší

- **Šablony, sloty, atomy** — identita šablon a plnění rolí po hranách
  (P2) přijdou jako další vrstva nad maticemi.
- **Složené časy po hranách** — „zpíval jsem" dnes kotví po řádcích
  (Part=past i AUX=pres); správný čas klauze vyžaduje slovesnou skupinu.
- **Nepřímé otázky** — `is_question` vidí jen otazník; „Nevím, kde je."
  zůstává na straně odpovědi.
- **Typ z gazetteeru/clusterů** (P4) — dnes jen NameType z rozboru;
  „v lednu" ještě nekotví čas.
- **Víc vět, odkazy, koreference** — pole je jedna věta; mosty mezi
  větami budou vrstva nad tím.

## Testy

```
./run-python -m unittest discover -s cb_field -t .    # 70 testů
```

Zmražená data přímo v testech (skutečné výstupy UDPipe z 2026-08-03);
žádný test nepotřebuje běžící službu. Testy korpusu si parser atrapují,
data korpusu čtou ze zmražených souborů v `tests/data/korpus/`.

Validace datového souboru (tahle potřebuje běžící UDPipe, protože
kontroluje rozpad vět a `answer_lemma` proti lemmatům):

```
./run-python -m cb_field.corpusfile cb_field/tests/data/korpus/korpus-001.json
```
