# cb_logic Fáze 3–5 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementovat provenienci, constrainty, KnowledgeBase s validací a mřížkou, forward chaining do fixpointu s derivacemi a konflikty, invalidaci derivací, backward proof a assumptions — přesně dle `CONSTRAINT_MODEL.md` a `INFERENCE_ENGINE.md`.

**Architecture:** Čtyři nové soubory s jednou odpovědností: `provenance.py` (původ, derivace, konflikt), `constraints.py` (omezení, dvě čtení jedné sémantiky), `knowledge.py` (báze + jediná zapisovací cesta), `inference.py` (grounding, forward, retract, prove, assumptions). Testy zrcadlí soubory + `test_inference_properties.py` s generátorem bází a naivním referenčním orákulem.

**Tech Stack:** Python 3.11, stdlib, `unittest`, `./run-python`.

**Pozn. k formě plánu:** testy jsou uvedeny jako úplný spustitelný kód (jsou to specifikace chování); implementace je dána přesnými rozhraními + sémantikou z návrhových dokumentů — vykonavatel je autor návrhu, plná duplikace implementačního kódu v plánu by jen riskovala drift.

## Global Constraints

- Pouze stdlib; žádný import z `cb_*` mimo `cb_logic`; `unittest`; identifikátory anglicky, docstringy česky.
- Determinismus: kanonická pořadí (term_key/atom_key, pořadí vložení pravidel), žádné hodiny, náhoda jen `random.Random(328)`.
- `INCOMPLETE` se nikdy nevydává za verdikt; z absence se nic neodvozuje (INV-1, žádná CWA); konflikt se hlásí, nepřepisuje (INV-5); hypotéza (úroveň 0) nevstupuje do čtení pravdivosti.
- Spouštění: `./run-python -m unittest discover -s cb_logic -t .`; na konci celoprojektový běh.

---

### Task 1: Provenience (`cb_logic/provenance.py`)

**Files:** Create `cb_logic/provenance.py`; Test `cb_logic/tests/test_provenance.py`.

**Interfaces (Produces):**
- `EvidenceKind(Enum)`: `USER_ASSERTION, OBSERVATION, EXTERNAL, ASSUMPTION, HYPOTHESIS, DERIVED`
- `Evidence(kind, source: str | None = None, confidence: float | None = None)` — frozen; confidence mimo [0,1] = `ValueError`; docstring: confidence nikdy nevstupuje do logiky
- Konstanty úrovní: `LEVEL_HYPOTHESIS = 0, LEVEL_DERIVED = 1, LEVEL_DOCUMENTED = 2, LEVEL_DEFINITION = 3, LEVEL_CORRECTION = 4`
- `Provenance(level: int, evidence: Evidence, derivation_id: int | None = None)` — frozen; level mimo 0–4 = `ValueError`; `level == LEVEL_DERIVED` vyžaduje `derivation_id`
- `Assertion(literal: Literal, evidence: Evidence, level: int)` — frozen; kandidát pro validační cestu
- `Derivation(id: int, conclusion: Literal, premises: tuple[Literal, ...], rule_index: int | None, assumptions: frozenset[str])` — frozen
- `Conflict(atom: Atom, positive: Provenance, negative: Provenance)` — frozen

**Steps:** (1) testy: validace confidence a úrovní, DERIVED bez derivation_id = chyba, rovnost hodnot; (2) červená; (3) implementace; (4) zelená; (5) commit `cb_logic: provenience — evidence, úrovně mřížky, derivace, konflikt`.

```python
# jádro testů (test_provenance.py)
class TestEvidence(unittest.TestCase):
    def test_confidence_mimo_rozsah_je_chyba(self):
        with self.assertRaises(ValueError):
            Evidence(EvidenceKind.OBSERVATION, confidence=1.5)

class TestProvenance(unittest.TestCase):
    def test_uroven_mimo_mrizku_je_chyba(self):
        with self.assertRaises(ValueError):
            Provenance(5, Evidence(EvidenceKind.OBSERVATION))
    def test_derived_vyzaduje_derivaci(self):
        with self.assertRaises(ValueError):
            Provenance(LEVEL_DERIVED, Evidence(EvidenceKind.DERIVED))
        Provenance(LEVEL_DERIVED, Evidence(EvidenceKind.DERIVED), derivation_id=0)
```

### Task 2: Constrainty (`cb_logic/constraints.py`)

**Files:** Create `cb_logic/constraints.py`; Test `cb_logic/tests/test_constraints.py`.

**Interfaces (Produces):**
- `CardinalityConstraint(atoms: tuple[Atom, ...], at_least: int, at_most: int | None, label: str | None = None)` — frozen; validace: atomy ground, unikátní, neprázdné; `0 ≤ at_least ≤ len(atoms)`; `at_most` None nebo `at_least ≤ at_most`
- `ExpressionConstraint(expr: Expression, label: str | None = None)` — frozen
- `Constraint = CardinalityConstraint | ExpressionConstraint`
- Zkratky: `exactly_one(atoms)`, `at_least_one(atoms)`, `at_most_one(atoms)`, `excludes(a, b)`, `requires(a, b)`, `equivalent(a, b)` (a, b jsou `Expression`)
- `MAX_EXPANSION_ATOMS = 12`
- `to_expression(constraint, *, max_expansion_atoms=MAX_EXPANSION_ATOMS) -> Expression` — nad limit `ValueError`
- `satisfied_by(constraint, assignment: Mapping[Atom, bool]) -> bool` — kardinalita počítáním
- `truth_partial(constraint, partial: Mapping[Atom, bool]) -> Truth` — CONSTRAINT_MODEL § 3
- `atom_family(relation: Relation, template: tuple[Term | None, ...], over: Domain) -> tuple[Atom, ...]` — právě jedno `None` v šabloně (jinak `ValueError`), doplňuje se členy domény v pořadí `term_key`

**Klíčové testy:** exactly_one splněno právě jednou pravdou; křížová shoda `satisfied_by` × `evaluate(to_expression)` přes všechna ohodnocení malých rodin (T-11); parciální čtení dle § 3 vč. vlastnosti „ne-UNKNOWN se doplněním nezmění" (enumerací doplnění); `atom_family` deterministické pořadí; expanze nad limit = `ValueError`, počítání funguje dál.

**Commit:** `cb_logic: constrainty — kardinality a výrazová omezení, dvě čtení jedné sémantiky`

### Task 3: KnowledgeBase (`cb_logic/knowledge.py`)

**Files:** Create `cb_logic/knowledge.py`; Test `cb_logic/tests/test_knowledge.py`.

**Interfaces (Produces):**
- `Rule(var_domains: tuple[tuple[Variable, str], ...], body: Expression, head: Literal)` — frozen
- Výsledky validace (frozen): `Accepted(literal)`, `Rejected(reason: str)`, `Conflicted(conflict: Conflict)`
- `class KnowledgeBase:`
  - `declare_relation(relation)`, `declare_domain(domain)`; přístup `relation(name)`, `domain(name)` — neznámé jméno = `KeyError`; dvojí deklarace se stejným obsahem OK, s jiným = `ValueError`
  - `assert_candidate(assertion) -> Accepted | Rejected | Conflicted` — jediná zapisovací cesta faktů; Rejected: nedeklarovaná relace, ne-ground literál
  - mřížka: protistrana s podporou — vyšší úroveň vítězí ve čtení (obě strany zůstávají, konflikt se eviduje, vrací se Accepted); stejná úroveň = Conflicted + karanténa
  - `add_rule(rule, provenance) -> int` — validace: proměnné těla i hlavy ⊆ var_domains, domény a relace deklarované, hlava je literál s proměnnými jen z var_domains; `add_constraint(constraint, provenance) -> int` (atomy s deklarovanými relacemi)
  - `truth_of(atom) -> Truth`; `is_conflicted(atom) -> bool`; hypotéza (úroveň 0) nedává čtení
  - `supported(literal) -> bool`; `own_facts() -> tuple[tuple[Literal, Provenance], ...]` (kanonické pořadí)
  - vnitřně: `_sides: dict[tuple[Atom, bool], _Side]`, `_Side.own: Provenance | None`, `_Side.derivations: list[int]`; `derivations: list[Derivation]`; `conflicts: list[Conflict]`; `rules/constraints` s proveniencí
  - `copy() -> KnowledgeBase` — hluboká kopie stavu (frozen objekty se sdílejí)

**Klíčové testy:** odmítnutí nedeklarované relace a ne-ground literálu; čtení TRUE/FALSE/UNKNOWN; hypotéza nedává čtení; mřížka — oprava (4) přebije doložené (2), obě strany zůstávají, konflikt evidován; táž úroveň → Conflicted, `truth_of` = UNKNOWN, `is_conflicted` = True; `copy()` nezávislá.

**Commit:** `cb_logic: KnowledgeBase — deklarace, validační zápis, mřížka provenience, karanténa konfliktu`

### Task 4: Forward chaining (`cb_logic/inference.py`)

**Files:** Create `cb_logic/inference.py`; Test `cb_logic/tests/test_inference.py`.

**Interfaces (Produces):**
- `Limits(max_rounds: int = 100, max_derivations: int = 10_000, max_ground_instances: int = 100_000)` — frozen
- `InferenceStatus(Enum)`: `FIXPOINT, INCOMPLETE`
- `InferenceResult(status, new_facts: tuple[Literal, ...], conflicts: tuple[Conflict, ...], rounds: int, derivations_added: int)` — frozen
- `ground_rule(rule, kb) -> Iterator[tuple[dict[Variable, Term], Expression, Literal]]` — proměnné v pořadí `var_domains`, členové domén dle `term_key`, `itertools.product`
- `infer_forward(kb, limits = Limits()) -> InferenceResult` — mutuje kb; kolo dle INFERENCE_ENGINE § 3; čtení atomu: `truth_of` (karanténa ⇒ UNKNOWN); tělo TRUE ⇒ derivace hlavy; premisy = literály z rozhodující větve (And: všechny; Or: první TRUE disjunkt; Not: vnitřek; Implies: FALSE antecedent nebo TRUE konsekvent; Equiv: obě strany); duplicitní derivace (stejný závěr + premisy + pravidlo) se nezapisuje
- konflikt odvozené × doložené: derivace i konflikt se zaznamenají, čtení drží doložené; odvozené × odvozené opačné: konflikt + karanténa

**Klíčové testy:** řetěz A→B→C→D→E z jednoho faktu (zadání §21); cyklus A→B, B→A terminuje (§22); fixpoint idempotentní (§23); tělo UNKNOWN nevystřelí — z absence nic (INV-1), negace v těle jen z doloženého záporu; limity → INCOMPLETE (§24); derivace nese premisy a pravidlo; konfliktní odvození dle mřížky.

```python
# reprezentativní test řetězu (test_inference.py)
def _rule(kb, body_rel, head_rel, dom="things"):
    x = Variable("X")
    return Rule(((x, dom),),
                AtomRef(Atom(kb.relation(body_rel), (x,))),
                Literal(Atom(kb.relation(head_rel), (x,))))

class TestChains(unittest.TestCase):
    def test_retez_bez_pevneho_poctu_kroku(self):
        kb = KnowledgeBase()
        for r in "abcde":
            kb.declare_relation(Relation(r, 1))
        kb.declare_domain(Domain("things", (Entity("t1"),)))
        for lo, hi in (("a","b"),("b","c"),("c","d"),("d","e")):
            kb.add_rule(_rule(kb, lo, hi),
                        Provenance(LEVEL_DEFINITION,
                                   Evidence(EvidenceKind.USER_ASSERTION)))
        kb.assert_candidate(Assertion(
            Literal(Atom(kb.relation("a"), (Entity("t1"),))),
            Evidence(EvidenceKind.USER_ASSERTION), LEVEL_DOCUMENTED))
        result = infer_forward(kb)
        self.assertEqual(result.status, InferenceStatus.FIXPOINT)
        for r in "bcde":
            self.assertEqual(kb.truth_of(Atom(kb.relation(r), (Entity("t1"),))),
                             Truth.TRUE)
```

**Commit:** `cb_logic: forward chaining — grounding, fixpoint, derivace s premisami, konflikty, limity`

### Task 5: Invalidace derivací (`retract` v `inference.py`)

**Interfaces (Produces):**
- `RetractResult(removed: tuple[Literal, ...])` — frozen; kanonické pořadí
- `retract(kb, literal) -> RetractResult` — odstraní vlastní evidenci strany; poté **well-founded přepočet**: podporované strany = uzávěr z vlastních evidencí přes derivace (derivace drží, jen když drží všechny premisy); nepodložené derivace se deaktivují, strany bez podpory zanikají — tranzitivně (INV-12); vzájemná podpora dvou odvozených se nesmí udržet sama (test)

**Klíčové testy:** scénář §38 (A→B→C, odstraň A ⇒ B, C zanikají); fakt s vlastní evidencí i derivací přežije retract derivační premisy; **cyklus vzájemné podpory zanikne** (A odvozeno z B, B z A, kořen odstraněn); shoda `retract` s „zahodit odvozené + infer_forward" (recompute ekvivalence).

**Commit:** `cb_logic: invalidace derivací — well-founded retract s tranzitivním zánikem`

### Task 6: Backward proof a assumptions (`inference.py`)

**Interfaces (Produces):**
- `Proof(conclusion: Literal, rule_index: int | None, premises: tuple["Proof", ...])` — frozen; list = fakt báze
- `ProofStatus(Enum)`: `FOUND, NOT_FOUND, INCOMPLETE`
- `prove(kb, literal, *, max_depth: int = 32) -> tuple[Proof | None, ProofStatus]` — nejprve fakt; pak pravidla se sjednotitelnou hlavou (binding z hlavy, zbylé proměnné přes domény); tělo rekurzivně (And: vše; Or: první úspěch; Not(AtomRef): záporný literál; Implies/Equiv: interní přepis na NNF pohled); detekce cyklu množinou cílů na cestě (větev selže); hloubka nad limit ⇒ INCOMPLETE, ne NOT_FOUND
- `with_assumptions(kb, literals: tuple[Literal, ...]) -> KnowledgeBase` — kopie báze; předpoklad = fakt s Evidence(ASSUMPTION), úroveň LEVEL_DOCUMENTED, jmenovka = kanonický text literálu; derivace v kopii propagují jmenovky: sjednocení jmenovek premis + jmenovka premisy-předpokladu (INFERENCE_ENGINE § 8)

**Klíčové testy:** scénář §37 — `ASSUME A, A→B, B→C` ⊢ C s `assumptions == {"a(E:t1)"} `; báze po zániku pohledu nezměněná; prove najde řetěz a vrátí strom premis; cyklus pravidel v prove neskončí smyčkou; hloubkový limit vrací INCOMPLETE.

**Commit:** `cb_logic: backward proof s detekcí cyklu a assumptions jako pohled s jmenovkami`

### Task 7: Property a metamorfní testy + referenční orákulum

**Files:** Create `cb_logic/tests/kb_generators.py`, `cb_logic/tests/test_inference_properties.py`.

**Interfaces:** `random_kb(rng, *, entities=4, relations=4, facts=6, rules=5) -> KnowledgeBase` — náhodné ground fakty (úroveň 2) a pravidla (těla conj/disj 1–2 literálů, kladná i záporná, proměnná s doménou všech entit); `naive_forward(kb)` — nezávislé orákulum: opakuj všechna pravidla × groundingy s dvoufázovým čtením přímo přes strany báze, bez optimalizací, do stabilizace.

**Klíčové testy (SEED=328, vzorky ≥ 50):** shoda `infer_forward` × `naive_forward` na množině podporovaných stran; monotonie (přidání nekonfliktního faktu neubere odvozené); idempotence fixpointu; metamorfní — bijektivní přejmenování entit i relací ⇒ izomorfní výsledek (zadání §43), permutace pořadí faktů/pravidel ⇒ týž výsledek (§40), přidání pravidel nad disjunktními relacemi nemění čtení původních atomů (§44); T-13 pojistka: generátor doložil záporné literály v tělech, disjunkce i vícekrokové řetězy.

**Commit:** `cb_logic: generátor bází, naivní orákulum a property/metamorfní testy inference`

### Task 8: API, dokumentace, závěrečný běh

- `cb_logic/__init__.py`: doplnit exporty všech nových veřejných jmen; `cb_logic/README.md`: aktualizovat „co modul vědomě neřeší" (zbývá: prostor modelů, modální dotazy, persistence — fáze 6+).
- Přepnout stavové řádky `CONSTRAINT_MODEL.md` a `INFERENCE_ENGINE.md` z „návrh ke schválení" na „implementováno (fáze 3–5), dokument odpovídá implementaci" + zapracovat případné odchylky (dokumentace musí odpovídat implementaci, zadání §56).
- Běhy: `discover -s cb_logic` zeleně; celoprojektový beze změny; import guard `cb_*` čistý.
- **Commit:** `cb_logic: veřejné API fáze 3–5 a srovnání dokumentace s implementací`

## Self-review

- **Coverage:** CONSTRAINT_MODEL § 1–4 → Task 2 (provenience constraintů se ukládá v Task 3 add_constraint); INFERENCE_ENGINE § 1 → Task 3; § 2–5 → Task 4; § 6 → Task 5; § 7–8 → Task 6; § 9 → Task 7 + průřezově. Zadání §21–24 → Task 4; §37 → Task 6; §38 → Task 5; §40, §43–44 → Task 7.
- **Placeholders:** testovací kód reprezentativní + taxativní seznamy chování; implementace vázaná na rozhraní a návrhové dokumenty (vědomá volba, viz hlavička).
- **Typová konzistence:** `Provenance(LEVEL_DERIVED, …)` vždy s `derivation_id`; `truth_of` vrací `Truth` z fáze 2; `Rule.var_domains` jako tuple párů (hashovatelné); výsledky validace tři frozen typy.
