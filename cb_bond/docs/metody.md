# Metody cb_bond — co dělá, proč existuje, na čem visí

Veřejné API modulu. Co tady není, je vnitřek a smí se změnit
(README-MODULES § 3).

## KnowledgeGraph (graph.py)

| metoda | co dělá / na čem visí |
|---|---|
| `KnowledgeGraph(emit=None)` | `emit` je funkce, které chodí delty každé mutace (princip 6). Bez ní graf mlčí — jádro nesmí mít I/O vrstvu. |
| `add_sentence(sentence, source="text")` | přidá rozparsovanou větu (má `.tokens`), vrátí počet vzniklých hran. `source` se pamatuje u hrany: text × dictionary × dialog. |
| `node_stat(key)` | statistika uzlu `UPOS:lemma`; neznámý uzel dá prázdnou `NodeStat`, ne výjimku — volající nemá řešit „existuje?" |
| `edges()` | `(src, dst, deprel, váha, zdroj)` s opakováním, včetně smyček |
| `statistics()` | uzly, které mají aspoň jednu hranu; izolovaný uzel by v průměrném stupni dělal tichý posun dolů |
| `sentence_nodes(position)` | uzly věty na dané pozici — vstup pro `illuminate` |
| `select_verticals(limit=328, usage=None, w_usage=0.0, with_scores=False)` | cílový stav custom slotů, seřazený podle `distinct²/edges × (1 + w_usage·doklady)`. Vrací CELÝ stav, ne přírůstek — promoce je vratná. |
| `illuminate(ranked_sentences, question_lemmas, boost=2.0)` | `{uzel: jas}`: rozsvícení vahou věty, zesílení lemmaty otázky, záře po hranách úměrně podílu hrany na sousedových hranách |

## NodeStat (graph.py)

| co | jak |
|---|---|
| `occurrences` | kolikrát byl token uzlem (i bez hrany) |
| `edges` | hranové instance **s opakováním** — tentýž soused podruhé se počítá znovu |
| `neighbours` | soused → počet hranových instancí |
| `distinct` | kolik různých sousedů |
| `ratio` | `distinct/edges`; 1,0 = ani jednou se neopakoval |

## Konstanty

| jméno | hodnota | proč |
|---|---|---|
| `NODE_UPOS` | NOUN, PROPN, VERB, ADJ, ADV, NUM | obsahová slova; zbytek nese gramatika (viz koncepce § 3) |
| `TEXT_WEIGHT` | 1,0 | váha hrany z běžného textu; definice mají svou (krok 7) |

## Skripty

| co | jak |
|---|---|
| přejímka kroku 2 | `./run-python cb_bond/scripts/prejimka-graf.py` — porovná graf 2 912 vět se zmraženými hodnotami § 6 zadání, nenulový návrat při rozdílu |
