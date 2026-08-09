# INTERPRETATION — interpretace jazyka, učení z dialogu, integrace (návrh, fáze 9–11)

**Stav:** návrh; implementuje se v témž kroku (pokyn „pokračuj s implementací").
**Vzniká z:** zadání §8–§10, §47; ARCHITECTURE_REVIEW P1/P2; KNOWLEDGE_MODEL § 4
(Assertion); README-ARCHITECTURE_OVERVIEW kap. 6 (jazyk v profilech), INV-11.

Pipeline (zadání § 9):

```
věta (text) → rozbor (cb_udpipe, bezztrátový strom)
           → INTERPRETACE (strukturální vzory nad UD) → Candidate
           → validace (KnowledgeBase.assert_candidate / add_rule)
           → detekce konfliktu (mřížka) → inference → provenience
```

Interpretační vrstva **jen navrhuje** (Candidate); o pravdivosti rozhoduje
jádro (INV-11, zadání § 47). Nový balík **`cb_interpret`** (knihovna):
smí importovat `cb_udpipe` (typ Token) a `cb_logic`; jádro o něm neví.

---

## 1 · Strukturální vzory (žádné jazykové slovo v kódu)

Detekce běží nad **UD kategoriemi**, ne nad českými slovy: `deprel` (`root`,
`cop`, `nsubj`, `det`, `obj`, `obl`, `case`), `upos` (`PROPN/NOUN/ADJ/VERB/ADP`),
`feats` (`PronType=Tot/Neg/Dem`, `Polarity=Neg`). Jazykový profil
(`profiles/cs.json`) nese pouze: otazník a **šablony renderování** odpovědí.

| vzor | příklad | výstup |
|---|---|---|
| kopula + PROPN podmět | „Petr je programátor." | fakt `programátor(petr)` |
| kopula + negace | „Petr není student." | fakt `NOT student(petr)` |
| kopula + `PronType=Tot` det | „Každý programátor je člověk." | pravidlo `programátor(X) → člověk(X)` |
| kopula + `PronType=Neg` det | „Žádný pták není savec." | pravidlo `pták(X) → NOT savec(X)` (dvojí zápor češtiny = jedna logická negace) |
| kopula + holý NOUN podmět | „Pes je savec." | generické čtení: pravidlo `pes(X) → savec(X)` |
| kopulová otázka | „Je Petr člověk?" | dotaz na literál |
| VERB + PROPN podmět (+ obj/obl+case) | „Petr bydlí v Praze." / „Petr zná Janu." | fakt `bydlet_v(petr, praha)` / `znát(petr, jana)`; bez argumentu unární |
| jiné | „Kolik je hodin?" | **unparsed s důvodem** — poctivé odmítnutí, žádné hádání |

Jména relací a entit vznikají z lemmat (normalizace: lowercase id entity);
systém je **data-driven** — žádný seznam povolených slov. Vědomé meze (poctivě
unparsed): ukazovací determinanty, kvantifikované slovesné věty, NOUN podmět
slovesné věty, souvětí, vztažné věty, synonymie lemmat („lidé" ≠ „člověk" —
scelování je budoucí vrstva zmínky/entity, kap. 14.7 návrhu).

## 2 · Candidate a učení (`cb_interpret`)

```
Candidate(kind: fact|rule|query|unparsed, literal?, rule?, relations, entities,
          source_text, note?)
interpret_sentence(tokens, text, profile, domain) -> Candidate

DialogueLearner(kb, profile, domain="entita")
  .learn(tokens, text, source, level) -> LearnResult(candidate, outcome, inference)
      deklarace relací (idempotentní) + růst domény entit
      fakt → assert_candidate (evidence USER_ASSERTION, úroveň dle mřížky)
      pravidlo → add_rule (úroveň DEFINITION)
      poté infer_forward → nové odvozené fakty, konflikty
  .ask(tokens, text) -> AskResult(candidate, truth, explanations, why_not)
      READ-ONLY: truth_of + why; při UNKNOWN why_not (chybějící premisy
      = formální podklad doptání)
```

Nové v jádru: `KnowledgeBase.extend_domain(name, members)` — **append-only
růst domény** (dialog přináší nové entity; růst je monotónní, groundingy jen
přibývají). Zapsáno i v KNOWLEDGE_MODEL § 2.

## 3 · Vysvětlení v jazyce (fáze 10, `render.py`)

Šablonové renderování stromu `Explanation` do češtiny (unární/binární
literály, protože-řetěz, předpoklady, zdroj) — šablony v profilu, kód bez
českých slov. Vědomá mez: lemmata bez morfologie („petr bydlet v praha") —
plnohodnotná formulace může přijít z LLM, ale **důkazem zůstává strom**
(zadání § 36, § 47).

## 4 · Integrace do cb-bond (fáze 11)

Zásada z migrace: **vedle, ne místo** — formální cesta odpovídá, když umí;
retrieval beze změny.

- `cb_bond/logic.py`: `LogicBridge(parser, kb_file)` — drží KnowledgeBase +
  DialogueLearner; `context(text)` učí a **persistuje** (JSON round-trip,
  atomicky), `ask(text)` vrací formální odpověď nebo None, `load()` při
  startu.
- `BondService.context()` navíc volá bridge.context → klíč `logic` v odpovědi.
- `BondService.ask()` navíc volá bridge.ask → klíč `logic` v odpovědi
  (truth + vysvětlení + render); stávající pole beze změny.
- Konfigurace: `module.logic.kb_file` (datová cesta pod `data_root`),
  validovaná schématem — **a čtená kódem** (poučení z P6).
- Tím je poprvé splněno: znalost z dialogu **přežije restart** (P5 pro novou
  vrstvu; dluh registru retrieval vrstvy zůstává evidován zvlášť).
