# INFERENCE_ENGINE — báze znalostí a inferenční jádro (návrh, fáze 3+5)

**Stav:** implementováno (`cb_logic/knowledge.py`, `cb_logic/inference.py`);
dokument odpovídá implementaci.
**Vzniká z:** zadání §18–§24, §37–§39; KNOWLEDGE_MODEL.md; LOGIC_SEMANTICS.md § 6–7;
CONSTRAINT_MODEL.md.
**Předpoklad:** jádro fáze 2. Prostor modelů a modální dotazy jsou fáze 6–7
(MODEL_REASONING.md vznikne s nimi); tento dokument definuje bázi, validaci,
grounding a odvozování faktů.

---

## 1 · KnowledgeBase

Objekt bez globálního stavu (dvě báze vedle sebe musí jít). Obsah:

```
declarations   relace (jméno → Relation), domény (jméno → Domain),
               vazba proměnných pravidla na domény
facts          dict[Atom → FactEntry]; FactEntry nese oba směry:
               positive: Provenance | None, negative: Provenance | None
               (oba zároveň = konflikt, § 4)
rules          tuple[RuleEntry]  (Rule + Provenance)
constraints    tuple[ConstraintEntry]
conflicts      tuple[Conflict]   — nic se nemaže, jen eviduje (INV-5)
derivations    derivační graf (append-only; invalidace § 6)
```

**Jediná zapisovací cesta** je validace:

```
assert_candidate(assertion) → Accepted(fact) | Rejected(reason) | Conflicted(conflict)
```

Validace: relace deklarovaná, arita sedí, atom ground, evidence přítomná.
Konflikt (`p` proti `NOT p`): rozhoduje mřížka provenience (KNOWLEDGE_MODEL § 7) —
vyšší úroveň **přebije, ale nepřepíše** (obě strany zůstávají, konflikt se
eviduje a je vidět); táž úroveň ⇒ `Conflicted`, atom je pro odvozování
**karanténovaný** (§ 4). Přijetí pravidla navíc vyžaduje: každá proměnná má
doménu, hlava i tělo jen deklarované relace.

## 2 · Grounding

`ground_rule(rule, kb) → iterátor ground instancí (body_expr, head_literal, binding)`
— kartézský součin domén proměnných v kanonickém pořadí (stabilní klíče);
deterministický. Nedeklarovaná/prázdná doména = hlasitá chyba už při zápisu
pravidla (LOGIC_SEMANTICS § 6). Počet instancí se počítá předem a započítává
do rozpočtu (§ 5).

## 3 · Forward chaining (materializace)

```
infer_forward(kb, limits) → InferenceResult(new_facts, conflicts, status, rounds)
```

Kolo: pro každou ground instanci pravidla vyhodnoť tělo **K3 parciálně** nad
známými fakty (fakt `p` ⇒ TRUE, fakt `NOT p` ⇒ FALSE, jinak UNKNOWN; karanténa
§ 4 ⇒ UNKNOWN). Tělo `TRUE` ⇒ odvoď hlavu:

- nová ⇒ zapiš jako odvozený fakt (úroveň 1) + `Derivation(head, premises =
  fakta atomů těla, rule, assumptions)`; premisy = fakta použitá při vyhodnocení
  těla (sbírají se během evaluace),
- známá se shodnou polaritou ⇒ jen přidej další derivaci (řetěz má druhy),
- známá s opačnou polaritou ⇒ konflikt dle mřížky (§ 1): odvozené (1) ustupuje
  doloženému (2+), ale **derivace i konflikt se zaznamenají**.

Fixpoint: kolo bez nového faktu a nové derivace končí (`status = FIXPOINT`).
Terminace je zaručená konečností: ground literálů je konečně, každé kolo přidá
aspoň jeden, jinak končí. Cykly pravidel (`A → B`, `B → A`) tedy neškodí;
derivační graf zůstává DAG, protože derivace odkazuje jen na fakta existující
před jejím vznikem.

**Sémantika UNKNOWN v těle:** pravidlo s tělem UNKNOWN nevystřelí — z absence
se nic neodvozuje (INV-1). Negace v těle (`NOT p`) je pravdivá jen při
**doloženém** záporném faktu, nikdy z chybějícího kladného (žádná closed-world
assumption).

## 4 · Konflikt a karanténa

`Conflict(atom, provenance₊, provenance₋)`; obě strany zůstávají v bázi.
Karanténa (konflikt na téže úrovni): atom se v tělech pravidel čte jako UNKNOWN
a dotazy, jejichž vyhodnocení se ho dotklo, nesou příznak `conflicted` s oběma
proveniencemi. Konflikt **není** chyba běhu — je to legitimní stav znalosti,
který se hlásí (INV-5) a zkoumá dotazy (`WhyQuery` nad oběma stranami).

## 5 · Limity zdrojů

`Limits(max_rounds, max_derivations, max_ground_instances)` — deterministické
počty (žádné hodiny v jádru; time_budget může přidat volající vrstva). Překročení
⇒ `status = INCOMPLETE` + co se stihlo; **nikdy** se nevydává za fixpoint ani
za FALSE (zadání §24). Výchozí hodnoty do registru prahů (spolu s
`DEFAULT_MAX_ATOMS` z fáze 2) — jediné místo, kde čísla žijí.

## 6 · Invalidace derivací (zadání §38)

`retract(kb, fact) → RetractResult(removed, orphaned)`: odstranění faktu ruší
derivace, které ho nesou jako premisu; odvozený fakt, kterému nezbyla žádná
derivace ani vlastní evidence, zaniká — **tranzitivně** (INV-12). Odvozená
vrstva je kdykoli zahoditelná a přepočitatelná (`recompute = zahodit odvozené
+ infer_forward`); shoda obou cest je zkouška správnosti invalidace.

## 7 · Backward chaining (dotazová cesta)

Analýza §20: forward materializuje důsledky doložených faktů (levné, konečné,
umožňuje detekci konfliktů při učení — rozhodnutí kap. 14.6 návrhu: korpus
dopředu, dialog líně). Backward slouží dotazu: `prove(kb, literal, limits)`
hledá derivaci cílového literálu do hloubky `max_depth` s memoizací
a detekcí cyklu (cíl na vlastní cestě ⇒ větev selže, ne smyčka). Vrací
`ProofResult(found, derivation | None, status)`; s materializovanou bází je
backward hlavně **vysvětlovací** mechanismus (WhyQuery) a příprava pro líné
vyhodnocení dialogových vrstev. `TruthQuery(expr)` = K3 evaluace nad fakty
báze; `UNKNOWN` může zpřesnit až modální dotaz nad modely (fáze 6–7).

## 8 · Assumptions

`with_assumptions(kb, {literal…}) → pohled na bázi` — předpoklady se chovají
jako fakta úrovně kontextu (evidence ASSUMPTION), derivace vzniklé pod nimi
nesou jejich jmenovky; pohled zaniká s dotazem, báze se nemění (KNOWLEDGE_MODEL
§ 9). Zánik = žádná invalidace (nic v bázi nevzniklo).

## 9 · Determinismus a testy

- Kanonické pořadí instancí, pravidel i front; táž báze ⇒ týž průběh i výsledek.
- **Referenční orákulum:** naivní forward (opakuj všechna pravidla do stabilizace,
  bez optimalizací) jako nezávislá implementace; produkční cesta se s ním
  porovnává na generovaných bázích (zadání §41–42).
- Property testy: monotonie (přidání faktu nikdy neubere odvozené — v jádru bez
  konfliktů), idempotence fixpointu, `retract∘assert = identita` na náhodných
  bázích, shoda `recompute` × inkrementální invalidace.
- Metamorfní: přejmenování entit/relací, permutace pořadí faktů a pravidel,
  přidání irelevantních pravidel — výsledek izomorfní (zadání §42–44).
