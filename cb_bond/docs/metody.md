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

## Matcher (matcher.py)

| metoda | co dělá / na čem visí |
|---|---|
| `Matcher(corpus, *, spread_depth=2, weights, theta, epsilon, top_k=50)` | páruje otázku s korpusem; otázka musí být pole nad TÝMŽ registrem |
| `given_axes(question)` | slovní osy, které otázka dává — bez tázacích slov (QLEM=) a bez interpunkce |
| `coverage(question)` | `{daná osa: nejlepší pokrytí přes věty}`; neznámá osa dá **přesnou nulu** |
| `recall(question, top_k)` | pozice vět ke jemnému čtení — jeden součin (§ 5/S1) |
| `match(question)` | `MatchResult` se seřazenými kandidáty a východiskem |
| `links` | řídký operátor vazeb registru (postaví se při první potřebě) |
| `question_vector(question)` | pytel CELÉ otázky: součet řádků → maska → saturace |
| `candidate_vectors(sentence, token)` | `(okno, střed)` — harmonicky vážené, saturované, JEDNOTKOVÉ |
| `sentence_coverage(question)` | `{věta: pokrytí}` — mohutnost, ne kosinus; člen řadící VĚTY |
| `question_words(question)` | `{slovní osa: váha}` toho, co otázka TVRDÍ — bez tázacího slova a interpunkce; stojí na tom `topic` a `given` |
| `semantic_bag(rows)` (funkce modulu) | součet řádků přes semantickou masku |

| objekt | co to je |
|---|---|
| `ScoreWeights` | páky členů skóre: `center` 2,0 · `cover` 1,0 · `topic` 1,0 · `given` −3,0 · `fit` 0,0 |
| `ScoreCandidate` | token ve větě: `sentence`, `token`, `lemma`, `score`, `decomposition()` (líný rozklad) |
| `MatchResult` | `candidates`, `outcome` (answer/ask/silent), `best`, `sentences()`, algebra `&` `\|` `~` |
| `LinkOperator` | vazby registru jako tři pole (řádky/sloupce/váhy) — v·L bez husté matice (§ 5/S3) |
| `saturate(v, links, steps)` | šíření s tanh po KAŽDÉM kroku |
| `SEMANTIC_PREFIXES` | co projde maskou: WORD=, LEM=, QLEM=, ANCHOR=, QANCHOR=, Polarity=, CUSTOM= |

| co | jak |
|---|---|
| přejímka kroku 3 | `./run-python cb_bond/scripts/prejimka-matcher.py` |

## AnswerField (answer.py)

| metoda | co dělá / na čem visí |
|---|---|
| `AnswerField(result)` | rozloží kandidáty `MatchResult` po větách na pozice tokenů; mezery drží nulu |
| `tokens()` | nejjemnější čtení — kandidáti, jak přišli ze skórování |
| `spans(width=2)` | `(věta, počátek, součet)` seřazené sestupně |
| `sentences()` | `(věta, součet pole)` — BEZ dělení délkou (to je ten degenerát) |
| `gaussian_peaks(sigma=1.5)` | `(věta, vrchol, index)`; index vždy uvnitř věty i u vět kratších než jádro |
| `gaussian_kernel(sigma)` | normované jádro o poloměru `int(3σ)` |

| co | jak |
|---|---|
| přejímka kroku 4 | `./run-python cb_bond/scripts/prejimka-answer.py` — protiváha krátkých vět při tokenovém × gaussovském čtení |

## RelationMiner (relations.py)

| metoda | co dělá / na čem visí |
|---|---|
| `mine_definitions(corpus, registry)` | kopulární vzor (root NOUN/PROPN v nominativu + nsubj + cop) → vazba 0,7; vrací počet NOVÝCH |
| `mine_derivations(graph, registry, around=None)` | kmenové páry: váha `0,7·(síla/2 + překryv/2)`; **bez `around` těží plošně**, což je naměřeně horší |
| `definitions` / `derivations` | vytěžené vazby i se zdrojem (`definition` / `derivation`) |
| `kmen(a, b)` (funkce modulu) | společný začátek po složení diakritiky |
| `bez_diakritiky(text)` | text malými písmeny bez diakritiky |

| konstanta | hodnota | proč |
|---|---|---|
| `DEFINIENS_UPOS` | NOUN, PROPN | vlastní jméno smí být definiens (91 vs 94 vazeb) |
| `DEFINITION_WEIGHT` | 0,7 | silný, ale ne totožnostní vztah |
| `MIN_STEM` / `MIN_STEM_SHARE` | 5 znaků / 75 % | pod tím spojuje náhodné shody (naléhavý × náledí) |

| co | jak |
|---|---|
| přejímka kroku 7 | `./run-python cb_bond/scripts/prejimka-vztahy.py` |

## VerticalRegistry — co k tomu přibylo v cb_field

| metoda | proč |
|---|---|
| `get_link(src, dst)` | váha vazby, nebo **None** — nula je platná váha (naučená bezvýznamnost), „vazba tu není" je jiná skutečnost |
| `unlink(src, dst)` | odstraní vztah, klíče nechá (osa je append-only); potřebuje promoce při uvolnění slotu |

## Responder · DefinitionResolver · QuestionExpander (dialog.py)

| metoda | co dělá / na čem visí |
|---|---|
| `Responder(matcher, graph, expander=None)` | dialogová vrstva; expander je volitelný |
| `gaps(question)` | osy s **přesnou nulou** — mezery ve znalosti |
| `reply(question, *, expand=False)` | `Reply(best, outcome, missing)`; odpovídá VŽDY, i když hlásí `needs_context` |
| `append_context(text, parser, source="dialog")` | věta uživatele standardní cestou do korpusu i grafu |
| `DefinitionResolver(corpus, graph, parser, *, lookup, store)` | `resolve(word_key)` → `corpus` / `dictionary` / `dialogue`; offline-first |
| `QuestionExpander(resolver, miner)` | `expand(question)` → `Expansion(definitions, derivations)` |

| objekt | co to je |
|---|---|
| `Reply` | `best`, `outcome` (answer/ask/needs_context/silent), `missing`, `lemma` |
| `Expansion` | `definitions` `{osa: odkud}`, `derivations` (počet) |

| co | jak |
|---|---|
| přejímka kroku 8 | `./run-python cb_bond/scripts/prejimka-dialog.py` — přehraje celý průběh o dálnici |

## PromotionCycle (promotion.py)

| metoda | co dělá / na čem visí |
|---|---|
| `PromotionCycle(measure, retrain, limit=328)` | měřič i přeučení parametrem (§ 3) — cyklus neví, čím se měří ani jak se učí |
| `run(corpus, graph)` | `CycleOutcome(accepted, before, after, axis_changes, retrained)` |

| co | jak |
|---|---|
| přejímka kroku 6 | `./run-python cb_bond/scripts/prejimka-promoce.py` |

## VerticalRegistry — custom sloty (cb_field)

| metoda | proč |
|---|---|
| `set_custom_axes(keys)` | přepíše obsazení na CÍLOVÝ STAV; vrací `{pridano, odebrano, hran_odebrano}`. Uvolněný slot přijde i o vazby — hrana do neobsazeného slotu ukazuje do prázdna |
| `axis_version` | verze OBSAZENÍ; roste jen při skutečné výměně, takže „nezvedla se" znamená „není co přeučovat" |
| `custom_axes` / `is_custom(key)` | co má dnes pojmenovaný neuron |
| `snapshot()` / `restore(snap)` | vratnost bit po bitu (vazby, obsazení, verze); klíče zůstávají — osa je append-only |

Soubor registru je od těchto změn `format_version` **2**: nese navíc
`custom_axes` a `axis_version`. Bez nich by se registr načetl bez
vstupní vrstvy a pole by tiše přestala aktivovat `CUSTOM=`.

## GraphMirror (mirror.py) a graphview

| metoda | co dělá / na čem visí |
|---|---|
| `GraphMirror(window)` | okno parametrem — jádro na viewBase nezávisí, testy si vystačí s atrapou |
| `emit(delta)` | jedna delta grafu → jedno volání okna; `KnowledgeGraph(emit=mirror.emit)` je celé zapojení |
| `mirror(graph)` | dožene graf, který vznikl bez zrcadla |
| `refresh(graph)` | doplní uzlům `sousede` a `stupen`; hromadně po ingestu, ne při každé hraně |
| `illuminate(graph, ranked, lemmas, boost=2.0)` | rozsvítí kandidáty a promítne jas do okna |
| `TYPE_STYLES` | barva podle slovního druhu — na obrázku je hned vidět, co uzel nese |

| co | jak |
|---|---|
| živý graf | `./run-python -m cb_bond.graphview "Kde byl pokřtěn Ježíš?"` (:8080) |
| přejímka kroku 9 | `./run-python cb_bond/scripts/prejimka-zrcadlo.py` — proti SKUTEČNÉMU oknu, ne atrapě |
| otisk frontendu | ověřuje `graphview.bundle_fingerprint()` při startu |

## ContrastiveTrainer (training.py)

| metoda / objekt | co dělá / na čem visí |
|---|---|
| `learning_bag(rows)` | součet řádků přes UČICÍ masku; `WORD=` tam není a nikdy nebude |
| `LEARN_PREFIXES` | LEM=, QLEM=, ANCHOR=, QANCHOR=, Polarity=, CUSTOM= |
| `ValidationSplit(share=0.3, seed=328)` | vrstvený deterministický los podle zodpověditelnosti |
| `ContrastiveTrainer(corpus, matcher, parser, *, split, lr=0.003, margin=0.2, sigma=1.5)` | učí vazby registru; parser i matcher parametrem |
| `train(entries, max_epochs=10)` | `TrainingReport`; epocha, která zhorší validaci, se odvolá |
| `sentence_hit(result, lemma, corpus, top=3)` | nese některá z TOP vět lemma odpovědi? |

| co | jak |
|---|---|
| přejímka kroku 5 | `./run-python cb_bond/scripts/prejimka-uceni.py` |
