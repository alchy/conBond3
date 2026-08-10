# cb_logic Fáze 6–8 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prostor modelů s relevančním scope, possible/necessary/impossible s protipříklady, meta-dotazy (redundance), why/why-not vysvětlení a JSON persistence — dle `MODEL_REASONING.md` a `PROVENANCE.md`.

**Architecture:** Tři nové soubory: `models.py` (scope, enumerace, modální klasifikace, meta-dotazy), `explain.py` (why/why-not/konflikt), `serialize.py` (round-trip). Malé doplnění `knowledge.py` (`documented_truth`). Testy zrcadlí + `test_models_properties.py` s plnou 2^n referencí a cross-layer vlastností „K3 TRUE ⇒ NECESSARY".

**Tech Stack:** Python 3.11, stdlib, `unittest`, `./run-python`.

**Forma plánu:** jako u fáze 3–5 — úplná rozhraní + taxativní chování + reprezentativní testy; vykonavatel je autor návrhu.

## Global Constraints

Shodné s fází 3–5 (stdlib, žádný `cb_*` import, unittest, determinismus, INCOMPLETE nikdy jako verdikt) + `SEED=328`.

---

### Task 1: Scope a enumerace modelů (`cb_logic/models.py`)

**Files:** Create `cb_logic/models.py`; Modify `cb_logic/knowledge.py` (přidat `documented_truth`); Test `cb_logic/tests/test_models.py`.

**Interfaces (Produces):**
- `KnowledgeBase.documented_truth(atom) -> Truth` — čtení JEN z vlastních evidencí úrovně ≥ DOCUMENTED (mřížka mezi nimi; rovnost = UNKNOWN)
- `ModelLimits(max_scope_atoms=24, max_nodes=200_000, max_models=10_000)` — frozen
- `SearchStatus(Enum)`: `COMPLETE, INCOMPLETE`
- `Model = tuple[tuple[Atom, bool], ...]` (kanonicky dle atom_key)
- `ScopeResult(atoms: tuple[Atom, ...], instances: tuple[Expression, ...], status: SearchStatus)` — instance = ground `Implies(body, head)` pravidel zahrnutých uzávěrem
- `model_scope(kb, seed_atoms: tuple[Atom, ...], limits) -> ScopeResult` — semínka: seed + atomy constraintů + atomy stran s vlastní evidencí; uzávěr přes ground instance pravidel protínající množinu; nad `max_scope_atoms` INCOMPLETE
- `ModelSearchResult(models: tuple[Model, ...], status, nodes: int, scope: tuple[Atom, ...], conflicted: tuple[Atom, ...], eliminated: tuple[tuple[str, int], ...])`
- `enumerate_models(kb, *, seed_atoms=(), limits=ModelLimits(), skip_constraint: int | None = None) -> ModelSearchResult` — DFS v kanonickém pořadí (False < True); pinned = `documented_truth`; konfliktní atomy nepinované + vyjmenované; řez: `truth_partial` constraintu / K3 instance = FALSE (eliminated čítá popisky `constraint[i]`/`label` a `rule[i]`); plný přířad = model
- `classify_atoms(result) -> AtomClassification(necessary, impossible, possible)` — TRUE ve všech / FALSE ve všech / jinak (nad `models`; prázdné modely ⇒ vše prázdné)

**Taxativní chování (testy):** mini-přiřazovací úloha daty (2 osoby × 2 nástroje, `exactly_one` oběma směry) ⇒ 2 modely; + doložený zápor ⇒ 1 model a `classify_atoms` dá oba nutné atomy; pinned fakt drží ve všech modelech; pravidlo `p→q` + fakt p ⇒ q nutné; nesplnitelné constrainty ⇒ 0 modelů, COMPLETE; irelevantní pravidlo nad cizí relací se do scope nedostane; `max_nodes=1` ⇒ INCOMPLETE; konfliktní atom nepinovaný a hlášený.

**Commit:** `cb_logic: prostor modelů — relevanční scope, enumerace s propagací, klasifikace atomů`

### Task 2: Modální dotazy a redundance (`models.py`)

**Interfaces (Produces):**
- `ModalVerdict(Enum)`: `NECESSARY, POSSIBLE, IMPOSSIBLE, UNSATISFIABLE, INCOMPLETE`
- `ModalResult(verdict, witness: Model | None, counterexample: Model | None, models_true: int, models_false: int, status: SearchStatus)`
- `classify_query(kb, expr, *, limits=ModelLimits()) -> ModalResult` — semínka = atomy výrazu; enumerace + vyhodnocení výrazu v každém modelu; INCOMPLETE enumerace: verdikt POSSIBLE jen s nalezeným svědkem i protipříkladem, jinak INCOMPLETE
- `violations(kb, model: Model) -> tuple[str, ...]` — popisky constraintů a instancí porušených daným ohodnocením („která informace odstranila model")
- `is_redundant(kb, constraint_index: int, *, limits) -> Decision` — YES ⇔ množina modelů bez constraintu je táž; INCOMPLETE při limitu
- `uniqueness_critical(kb, *, limits) -> tuple[int, ...]` — má-li plný prostor právě 1 model: indexy constraintů, bez nichž modelů > 1

**Taxativní chování:** „vyplývá, že Boris hraje na housle?" bez faktů ⇒ POSSIBLE s protipříkladem (§27); s fakty vynucujícími ⇒ NECESSARY; vyloučené ⇒ IMPOSSIBLE; prázdný prostor ⇒ UNSATISFIABLE; `requires(a,b)+requires(b,c)+requires(a,c)` ⇒ třetí YES-redundantní, první dva NO (§31); `violations` vrací právě porušené popisky.

**Commit:** `cb_logic: modální dotazy s protipříklady, violations a redundance podmínek`

### Task 3: Vysvětlení (`cb_logic/explain.py`)

**Interfaces (Produces):**
- `Explanation(literal, kind: str, evidence: Evidence | None, level: int | None, rule_index: int | None, assumptions: tuple[str, ...], premises: tuple["Explanation", ...])` — frozen; kind ∈ {"fact","assumption","derived"}
- `why(kb, literal, *, max_explanations=3, max_depth=16) -> tuple[Explanation, ...]` — vlastní evidence (fact/assumption dle EvidenceKind) + jedna větev za každou derivaci (premisy rekurzivně, první vysvětlení); prázdné = bez podpory
- `explain_conflict(kb, atom) -> tuple[Explanation, ...] | None` — vysvětlení obou stran konfliktu
- `Suggestion(rule_index: int, missing: tuple[Literal, ...])` — frozen
- `WhyNotResult(kind: str, explanations: tuple[Explanation, ...], modal: ModalResult | None, suggestions: tuple[Suggestion, ...])` — kind ∈ {"documented_false","impossible","unknown"}
- `why_not(kb, literal, *, limits=ModelLimits(), max_depth=2) -> WhyNotResult` — (1) protistrana doložená ⇒ její why; (2) modálně IMPOSSIBLE ⇒ modal výsledek; (3) jinak návrhy: pravidla s odpovídající hlavou, UNKNOWN literály těla (rekurze do max_depth)

**Taxativní chování:** řetěz a→b→c dá strom s listem a; pod předpokladem nese jmenovku; conflict vysvětlí obě strany s proveniencí; tři větve why_not na konstruovaných bázích; serializovatelnost stromu do JSON (`json.dumps` na `dataclasses.asdict`-ekvivalentu — Explanation má `to_json_object()`).

**Commit:** `cb_logic: vysvětlení — why, explain_conflict, why_not se třemi poctivými větvemi`

### Task 4: Persistence (`cb_logic/serialize.py`)

**Interfaces (Produces):**
- `FORMAT_VERSION = 1`
- `kb_to_json(kb) -> dict` — deklarace, strany (own + aktivní derivace), pravidla, constrainty, derivace, konflikty; kanonická pořadí; `Value` jen JSON skaláry (jinak `ValueError`)
- `kb_to_json_text(kb) -> str` — `json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(",", ":"))` — bajtová determinističnost
- `kb_from_json(data) -> KnowledgeBase` — cizí `format_version` = `ValueError`; rekonstrukce beze ztráty

**Taxativní chování:** round-trip po `infer_forward` i po `retract` zachová čtení všech atomů, own_facts, derivace, konflikty, počty pravidel/constraintů; dva zápisy téže báze jsou textově shodné; cizí verze hlasitě; `Value(objekt)` hlasitě.

**Commit:** `cb_logic: JSON persistence báze — round-trip beze ztráty sémantiky`

### Task 5: Property testy, API a srovnání dokumentace

**Files:** Create `cb_logic/tests/test_models_properties.py`; Modify `__init__.py`, `README.md`, `MODEL_REASONING.md`, `PROVENANCE.md` (stav), `KNOWLEDGE_MODEL.md` (stav § Query).

- Referenční orákulum: plná 2^n enumerace (itertools nad scope + `satisfied_by`/`evaluate` všech constraintů a instancí) ≡ `enumerate_models` na náhodných constraint problémech (rodiny ≤ 6 atomů, náhodné kardinality + výrazové constrainty; SAMPLES=30).
- Cross-layer: na náhodných pravidlových bázích (kb_generators, negation_free): každý atom s K3 čtením TRUE je v `classify_atoms` nutný; FALSE ⇒ nemožný.
- Metamorfní: přejmenování zachová počet modelů; permutace constraintů zachová množinu modelů; serialize round-trip na náhodných bázích.
- T-13: doložit, že vzorky obsahovaly nesplnitelné i vícemodelové problémy.
- Závěrečné běhy: cb_logic discover, celoprojektový, import guard.

**Commit:** `cb_logic: property testy modelů a persistence, API fáze 6–8, srovnání dokumentace`

## Self-review

- **Coverage:** MODEL_REASONING § 1–2 → Task 1; § 3–4 → Task 2; PROVENANCE § 1–3 → Task 3; § 5 → Task 4; § 6 + MODEL_REASONING § 5 → Task 5. Zadání §25–27 → Task 2; §28–29 (data, ne kód) → Task 1 test; §30–31 → Task 2; §35–36 → Task 3; §54 → Task 4.
- **Typová konzistence:** `Decision` z fáze 2 se recykluje pro redundanci; `Model` je kanonická tuple; `classify_query` bere `Expression` (literál přes `from_literal`).
- **Placeholders:** žádné.
