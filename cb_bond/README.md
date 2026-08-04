# cb_bond — jádro vazeb nad polem: graf faktů, párování, odpověď

Modul staví nad cb_field (pole věty) **tázací systém**: z otázky
v české větě vybere kandidátní VĚTY, které nesou odpověď, a umí říct
proč — rozkladem skóre po pojmenovaných členech a vysvícením v grafu.

Zadání celé stavby (deset kroků, zmražené přejímky, páky systému):
`docs/zadani.md`. Návrhová rozhodnutí a pasti: `docs/`.

## Stav: krok 2 z deseti (verze 0.1.0)

| krok | co | stav |
|---|---|---|
| 1 | `Corpus` + fixovaný korpus v JSON | hotovo (v cb_field 0.6.0) |
| 2 | `KnowledgeGraph` — paměť faktů | hotovo |
| 3 | `Matcher` — párování otázky s korpusem (vč. skórování 3b) | **částečně**: pokrytí, mrtvá osa a obě nuly ablace sedí; přesnost 10/30 proti 14/30 (`docs/prirucka.md`) |
| 4 | `AnswerField` — gaussovské čtení pole | hotovo |
| 7 | `RelationMiner` — definice a derivace | hotovo (94 vazeb sedí) |
| 8 | `Responder` — dialogová vrstva | hotovo (průběh o dálnici sedí) |
| 5, 6, 9, 10 | trénink · promoce · zrcadlo · měření | zbývá |

Vědomě zatím **není** plný modul podle README-MODULES § 2: chybí
konfigurace se schématem, logování přes cb-logger, `api.py`,
`control.py` + `cb-bond.py` a klient. Doplní se podle § 16, až se tvar
usadí — stejně jako u cb_field.

## Rozhraní (veřejné API)

| jméno | co to je |
|---|---|
| `KnowledgeGraph` | graf faktů: `add_sentence`, `node_stat`, `edges`, `statistics`, `select_verticals`, `illuminate`, `sentence_nodes` |
| `NodeStat` | statistika uzlu: `occurrences`, `edges`, `neighbours`, `distinct`, `ratio` |
| `NODE_UPOS` | slovní druhy, které se stávají uzlem |
| `Matcher` | párování: `given_axes`, `coverage`, `recall`, `match` |
| `MatchResult` | kandidáti, východisko (answer/ask/silent), algebra košů `&` `\|` `~` |
| `ScoreCandidate` | token ve větě se skóre a líným rozkladem po členech |
| `ScoreWeights` | páky členů skóre (center, cover, topic, given, fit) |
| `LinkOperator`, `saturate` | šíření po vazbách bez husté matice L |
| `semantic_bag` | součet řádků přes semantickou masku (strukturní osy vypadnou) |
| `AnswerField` | čtení pole: `tokens`, `spans`, `sentences`, `gaussian_peaks` |
| `gaussian_kernel` | normované jádro o poloměru int(3σ) |
| `RelationMiner` | těžba vztahů: `mine_definitions`, `mine_derivations` |
| `kmen` | společný kmen dvou lemmat po složení diakritiky |
| `Responder`, `Reply` | dialog: `gaps`, `reply`, `append_context` |
| `DefinitionResolver` | opatří definici: korpus → úložiště → slovník → dialog |
| `QuestionExpander`, `Expansion` | rozšíření otázky o oblast kolem jejích slov |

## Závislosti

| na čem | proč |
|---|---|
| `cb_field` | pole věty, registr vertikál, korpus |
| `cb_udpipe` | rozbor věty — **předává se parametrem**, modul si klienta nevytváří |

Na registru cb_fieldu smí cb_bond volat jen `link` / `unlink` /
`get_link` / `spread` / `set_custom_axes` / `snapshot` / `restore`
(§ 3 zadání).

## Testy

```
./run-python -m unittest discover -s cb_bond -t .     # 84 testů
```

Zmražené rozbory v `tests/vzorky.py` (skutečné výstupy UDPipe
z 2026-08-04); žádný test nepotřebuje běžící službu.

Přejímka na skutečném korpusu (potřebuje UDPipe a data mimo git):

```
./run-python cb_bond/scripts/prejimka-graf.py       # krok 2 — sedí
./run-python cb_bond/scripts/prejimka-matcher.py    # krok 3 — vč. ablace členů
./run-python cb_bond/scripts/prejimka-answer.py     # krok 4 — sedí
./run-python cb_bond/scripts/prejimka-vztahy.py     # krok 7 — sedí
./run-python cb_bond/scripts/prejimka-dialog.py     # krok 8 — sedí
```

Porovnají naměřené se zmraženými hodnotami § 6 zadání a skončí
nenulově, když se něco rozejde. Přejímka kroku 3 dnes rozdíl hlásí:
pokrytí a obě nulové hodnoty ablace sedí, plná přesnost je 10/30 proti
očekávaným 14/30 (bez řezu; s řezem je referenční hodnota 11/30).

## Co modul vědomě neřeší

- **Vlastní parsování.** Rozbor dodává cb_udpipe, vždy parametrem.
- **Vlastní perzistenci grafu.** Graf se staví z korpusu; co má přežít
  restart, drží registr cb_fieldu (`save`/`load`).
- **Kreslení.** Graf jen emituje delty; kreslí viewBase2 (krok 9).
