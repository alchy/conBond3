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
| 2 | `KnowledgeGraph` — paměť faktů | **hotovo** |
| 3–10 | Matcher · AnswerField · trénink · promoce · vztahy · dialog · zrcadlo · měření | zbývá |

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
./run-python -m unittest discover -s cb_bond -t .     # 17 testů
```

Zmražené rozbory v `tests/vzorky.py` (skutečné výstupy UDPipe
z 2026-08-04); žádný test nepotřebuje běžící službu.

Přejímka na skutečném korpusu (potřebuje UDPipe a data mimo git):

```
./run-python cb_bond/scripts/prejimka-graf.py
```

Porovná graf 2 912 vět se zmraženými hodnotami § 6 zadání a skončí
nenulově, když se něco rozejde.

## Co modul vědomě neřeší

- **Vlastní parsování.** Rozbor dodává cb_udpipe, vždy parametrem.
- **Vlastní perzistenci grafu.** Graf se staví z korpusu; co má přežít
  restart, drží registr cb_fieldu (`save`/`load`).
- **Kreslení.** Graf jen emituje delty; kreslí viewBase2 (krok 9).
