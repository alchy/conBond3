# PROVENANCE — derivační graf, vysvětlení a persistence (návrh, fáze 8)

**Stav:** návrh ke schválení, před implementací.
**Vzniká z:** zadání §35–§39, §54; KNOWLEDGE_MODEL.md § 7, § 10; INFERENCE_ENGINE.md
§ 6–7; MODEL_REASONING.md.

Většina mechaniky už stojí (fáze 3–5): derivace s premisami a pravidlem, mřížka
provenience, konflikty s oběma stranami, well-founded invalidace, backward proof.
Fáze 8 doplňuje **čtení** (why/why-not/what-would), skládání vysvětlení
a persistenci beze ztráty sémantiky.

---

## 1 · Derivační graf

Ledger `kb.derivations` + strany faktů tvoří orientovaný acyklický graf:
uzel = podporovaný literál, hrana = derivace (premisy → závěr, štítek pravidla,
jmenovky předpokladů). `derivation_graph(kb, literal) → DerivationGraph` vrací
podgraf dosažitelný z literálu směrem k listům (vlastní evidence); jeden závěr
smí mít víc derivací — graf je nese všechny (řetěz má druhy, kap. 18.1 návrhu).

## 2 · WHY (zadání §35–§36)

`why(kb, literal) → tuple[Explanation, ...]`:

- fakt s vlastní evidencí ⇒ list: evidence + úroveň + zdroj;
- odvozený ⇒ pro každou derivaci: pravidlo (s proveniencí) + rekurzivně premisy;
- pod předpokladem ⇒ jmenovky předpokladů viditelné na každém kroku (INV-2);
- konfliktní atom ⇒ obě strany s proveniencí (vysvětlení konfliktu, zadání §39).

`Explanation` je strom hodnot serializovatelný do JSON — přirozený jazyk z něj
smí generovat vyšší vrstva (LLM), ale **důkaz je tento strom**, ne text (§36, §47).

## 3 · WHY NOT a WHAT WOULD MAKE IT TRUE

`why_not(kb, literal, scope?, limits?) → WhyNotResult`, tři poctivé odpovědi:

1. **IMPOSSIBLE** — modální dotaz našel, že literál neplatí v žádném modelu:
   vysvětlení = porušené constrainty/pravidla z protipříkladového hledání
   (MODEL_REASONING § 4).
2. **UNKNOWN s chybějícími premisami** — literál není odvoditelný: pro pravidla
   s odpovídající hlavou se vrátí, které literály těla jsou UNKNOWN
   (kandidáti „co by to učinilo pravdou"; rekurzivně do hloubky limitu).
   To je formální podklad pro doptání v dialogu (fáze 9).
3. **FALSE doloženě** — protistrana s proveniencí.

## 4 · Invalidace (už implementováno — dokumentační srovnání)

`retract` (INFERENCE_ENGINE § 6) je well-founded: podpora se přepočítá uzávěrem
z vlastních evidencí, vzájemná podpora odvozených se sama neudrží, zánik je
tranzitivní (INV-12). Ledger derivací zůstává historií — `Explanation` starých
běhů tedy zůstává rekonstruovatelná.

## 5 · Persistence (zadání §54)

`kb_to_json(kb) → dict` / `kb_from_json(data) → KnowledgeBase` — úplný
round-trip bez ztráty sémantiky:

- deklarace (relace, domény), fakta s proveniencí (obě strany, včetně
  hypotéz), pravidla a constrainty s proveniencí, derivace, konflikty;
- kanonické pořadí všech seznamů (deterministický výstup — diffovatelnost);
- `format_version` v kořeni; cizí verze = hlasitá chyba (vzor registry/cache);
- modely se **nepersistují** — jsou odvozeniny (INV-14, kap. 14.6: doložené +
  pravidla jsou totéž s menší entropií); persistuje se, z čeho jdou
  rekonstruovat.
- Zápis atomicky přes `.tmp` + `os.replace` (vzor `cb_field/registry.py`).
- Kde soubor leží, určuje volající (data_root patří servisní vrstvě, ne jádru).

Test: round-trip identita (`kb_from_json(kb_to_json(kb))` ≡ původní báze na
čteních, derivacích i konfliktech) na generovaných bázích.

## 6 · Zkoušky fáze 8

- why: řetěz A→B→C dá strom s listem A a oběma pravidly; víc derivací téhož
  závěru dá víc vysvětlení.
- why_not: tři větve (impossible / chybějící premisy / doloženě false) na
  konstruovaných i generovaných bázích.
- Metamorfní: přejmenování zachovává izomorfii vysvětlení; serializace je
  deterministická (dva zápisy téže báze bajtově shodné).
- Křížová shoda: `why` z ledgeru ≡ strom z `prove` (kde obě cesty existují).
