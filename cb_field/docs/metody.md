# Metody cb_field — co dělá, proč existuje, na čem visí

Pracovní úroveň nahoře, ladicí vrstvy dole. Signatury viz docstringy;
tady je smysl a závislosti.

## SentenceField (field.py)

| metoda / atribut | co dělá | proč existuje / na čem visí |
|---|---|---|
| `from_text(text, parser, r=2, registry=None)` | rozparsuje text a postaví pole | hlavní vstup; pole = jedna věta, víc vět = ValueError; visí na předaném parseru (běžící cb-udpipe) |
| `from_sentence(sentence, …)` | z už rozebrané věty | když parse proběhl jinde; bere `.tokens` a `.source` |
| `question` | tázacost věty | spočtena jednou (otazník), řídí QLEM/QANCHOR a rozřešení PronType |
| `metadata` / `complete` | aktivace řádků jako slovníky | čitelný pohled; COMPLETE navíc `WORD=`; METADATA je primární |
| `array` | matice vah věty (METADATA) | počítání; zkratka za `matrix()` |
| `matrix(representation)` | obecná matice | dvoufázově: napřed růst registru přes všechny řádky, pak vektorizace — jednotná šířka |
| `baskets[i]` | koš (FieldBasket) | okno ±r kolem slova i |
| `activations[i]` | `Activations` slova i | getter/setter vah |
| `rows[i]` | rozvinutý řádek (dict s MetaValue) | ladicí pohled pod aktivace |
| `show()` | publikace do kukátka | visí na běžící službě viewer (jinak jen vypíše návod); zapisuje `run/current.json` |

## FieldBasket (field.py)

| metoda / atribut | co dělá | pozn. |
|---|---|---|
| `center`, `r`, `rows`, `center_token` | geometrie koše | `rows` jsou tokeny okna, na kraji věty jich je méně |
| `metadata` / `complete` | slovníky řádků okna | jen skutečné řádky |
| `array` / `matrix(repr)` | matice koše | **pevný tvar 2r+1 řádků**, nuly za hranicí, střed na y=r — porovnatelnost |

## VerticalRegistry (registry.py)

| metoda | co dělá | proč / na čem visí |
|---|---|---|
| `add(key)` | index vertikály; neznámou připíše | append-only, idempotentní — indexy se nikdy nepřečíslují (§ 14) |
| `index(key)` / `key(i)` | překlad klíč↔sloupec | `key(i)` rekonstruuje význam sloupců uložené matice |
| `vectorize(weights, grow=True)` | {vertikála: váha} → vektor float32 | `grow=False` pro čtení proti zmrazenému registru |
| `unvectorize(vector)` | vektor → {vertikála: váha} | zkouška funkčnosti round-trip; zaokrouhluje na 6 míst (float32) |
| `link(src, dst, weight)` | vážená vazba vertikála→vertikála | hierarchie kotev, budoucí synonymie; váha ±1 |
| `spread(vector)` | jeden krok šíření: v + v·L | párování otázka↔odpověď (q·L·a); kratší vektor doplní nulami |
| `save(path)` / `load(path)` | JSON s format_version | atomický zápis; cizí verze = hlasitá chyba; `load` staví holý registr (indexy bitově přesné) |
| `VerticalRegistry(anchors=True)` | konstruktor | rodí se s kotevními vazbami; `anchors=False` = holý (testy, load) |

## Activations (service.py)

| metoda | co dělá | pozn. |
|---|---|---|
| `from_row(row, question=False)` | postaví aktivace z rozvinutého řádku | jediná cesta dovnitř; question řídí Q-stranu |
| `get(key)` / `set(key, weight)` | čtení/ladění váhy | set hlídá −1…+1 a existenci klíče (přidání aktivace = stavba, ne ladění) |
| `weights(representation)` | slovník pro danou reprezentaci | kopie, ne vnitřek |
| `as_array(registry, representation, grow)` | vektor přes registr | zpět vede `registry.unvectorize` |

## Ladicí vrstvy (service.py)

| funkce | co dělá |
|---|---|
| `is_question(tokens)` | tázacost podle otazníku (nepřímé otázky nevidí — zapsaná mez) |
| `build_baskets(tokens, r)` | syrové koše z tokenů (na krajích menší) |
| `expand_token(token)` / `expand_basket(basket)` | vážené řádky: MetaValue, FEAT_SLOTS předalokovaných slotů |
| `activations(row, question)` | pravidla vertikál na jednom místě: UPOS/DEPREL/feats, SUBPOS, jmenná negace, LEM/QLEM, kotvy |
| `seed_anchor_links(registry)` | hierarchie kotev jako vazby (volá konstruktor registru) |

## Viewer (viewer.py)

| co | jak |
|---|---|
| spuštění | `./run-python -m cb_field.viewer` → http://127.0.0.1:42301/ |
| publikace | `sentence.show()`; starší cesta `visualize.sentence(parsed_sentence)` |
| kontrakt | `GET /` stránka · `GET /data` aktuální záznam · `GET /health` |
| data | `run/current.json` — soukromá přepravka, aktivace počítá Python, stránka jen kreslí |
