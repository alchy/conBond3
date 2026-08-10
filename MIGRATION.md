# MIGRATION — jak reasoning vrstva vznikla a co zbývá

**Stav:** fáze 0–12 dokončeny na větvi `feature/general-reasoning`.
Strategie z ARCHITECTURE_REVIEW § 15 byla dodržena: nová vrstva se stavěla
**vedle** stávající, žádná změna chování retrieval cesty (787 původních
testů beze změny zeleně po celou dobu).

## 1 · Co se stalo, po fázích

| fáze | commit(y) | výsledek |
|---|---|---|
| 0 | `f934539` | audit, ARCHITECTURE_REVIEW, CURRENT_DEPENDENCIES |
| 1–2 | `c5507e5`…`0eac558` | KNOWLEDGE_MODEL, LOGIC_SEMANTICS; `cb_logic`: termy, AST, K3, tabulkové orákulum |
| 3–5 | `7fd1c58`…`ec7cb96` | CONSTRAINT_MODEL, INFERENCE_ENGINE; provenience, constrainty, KnowledgeBase, forward/backward, retract, assumptions |
| 6–8 | `d08ba94`…`5b66aa2` | MODEL_REASONING, PROVENANCE; prostor modelů, modální dotazy, why/why-not, persistence |
| 9–11 | `11da81f`…`24b348d` | INTERPRETATION; `cb_interpret`, `extend_domain`, `cb_bond/logic.py`, `module.logic` v konfiguraci |
| 12 | `a471931`+ | Bartlová benchmark, akceptační test §59, tato dokumentace |

## 2 · Integrační body v cb_bond (jediné dotčené místo starého kódu)

- `service.build()` — vytvoření `LogicBridge`, pokud je `module.logic`
  v konfiguraci; bez klíče (testovací fixtury) služba běží jako dřív.
- `service.ask()` — přidán klíč `logic` do odpovědi (aditivní).
- `service.context()` — přidán klíč `logic`; formální báze se učí
  a persistuje vedle korpusu.
- `config.schema.json` + `cb-bond-config.json` + `DATA_PATH_KEYS` —
  `module.logic.kb_file` (klíč validovaný **i čtený** — žádné opakování P6).

**Rollback:** odebrání klíče `module.logic` z konfigurace vrstvu vypne;
odpovědi mají `logic: null` a systém se chová jako před migrací. Soubor
báze zůstává na disku (data přežívají kód).

## 3 · Vědomé odchylky a rozhodnutí zapsaná cestou

- BOTH se nezavádí jako pravdivostní hodnota (KNOWLEDGE_MODEL § 8).
- Kvantifikace jen přes konečné domény (LOGIC_SEMANTICS § 6).
- `Same/Distinct` nejsou zvláštní constrainty (CONSTRAINT_MODEL § 1, YAGNI).
- Návrhy chybějících premis unifikují hlavu, negroundují přes doménu —
  oprava obecného mechanismu nalezená testem (commit `347ac96`), přesný
  postup dle §60: nejdřív chybějící obecná schopnost, pak úprava mechanismu.
- Booleova algebra jako druhý kalkul se nestaví (kap. 41 návrhu); zákony
  jsou property testy.

## 4 · Co zbývá (evidované dluhy, mimo rozsah této práce)

| položka | odkaz | poznámka |
|---|---|---|
| persistence registru retrieval vrstvy (P5) | ARCHITECTURE_REVIEW § 13 | mechanika hotová v cb_field, nezapojená |
| trace 1,3 % (P7) | tamtéž | provozní stopa; provenience reasoning vrstvy na logu nezávisí |
| vady přílohy A (SyntaxError skriptů, `__or__`, …) | ARCHITECTURE_REVIEW příloha A | malé oddělené opravy |
| kvantifikované slovesné věty, souvětí, koreference | INTERPRETATION § 1 | poctivě unparsed; další vrstva interpretace |
| scelování lemmat („lidé" ≠ „člověk"), zmínka/entita | kap. 14.7 návrhu | budoucí vrstva identity |
| modální dotazy z jazyka („může/musí…") | INTERPRETATION | dnes jen dotaz na literál |
| formální odpověď jako primární v Responderu, okna | — | dnes aditivní klíč `logic`; povýšení až po zkušenostech z provozu |
| AST hlídač směru závislostí (T-12) | TARGET_DEPENDENCIES § 3 | |
| doptání v dialogu z `why_not.suggestions` | PROVENANCE § 3 | formální podklad hotový |
