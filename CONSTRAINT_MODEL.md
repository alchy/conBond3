# CONSTRAINT_MODEL — model omezení (návrh, fáze 4)

**Stav:** implementováno (`cb_logic/constraints.py`); dokument odpovídá implementaci.
**Vzniká z:** zadání §25–§29; KNOWLEDGE_MODEL.md § 6; LOGIC_SEMANTICS.md.
**Předpoklad:** implementované jádro fáze 2 (termy, výrazy, sémantika).

Zásada: **jedna sémantika, více výpočetních čtení.** Každý constraint umí vydat
ekvivalentní `Expression` — to je jeho *definice* (a zdroj pro referenční orákulum
i vysvětlení). Efektivnější vyhodnocení (počítání místo expanze) je optimalizace,
která se **měří proti expanzi** (zkouška křížové shody, T-11).

---

## 1 · Druhy constraintů

```
CardinalityConstraint(atoms: tuple[Atom,...], at_least: int, at_most: int | None)
    exactly_one(atoms)  = Cardinality(atoms, 1, 1)
    at_least_one(atoms) = Cardinality(atoms, 1, None)
    at_most_one(atoms)  = Cardinality(atoms, 0, 1)
ExpressionConstraint(expr: Expression, label: str | None)
    obecný výraz, který musí platit ve všech modelech; pojmenované zkratky:
    excludes(a, b)   = Not(And(a, b))
    requires(a, b)   = Implies(a, b)
    equivalent(a, b) = Equiv(a, b)
```

Všechny atomy v constraintu musí být **ground** (hlasitá chyba jinak) a jejich
relace deklarované v bázi. `Same`/`Distinct` ze zadání §28 se nereprezentují
zvláštním druhem: identita termů je v konečných doménách vyjádřitelná kardinalitami
a exkluzemi nad atomy přiřazení („patří / nepatří" = polarita literálu; „stejné
entitě" = `Equiv` atomů; „různé entitě" = `Excludes`) — nový druh constraintu se
zavede, až selže vyjádření stávajícími (YAGNI, kap. 39 návrhu: žádný objekt bez
odběratele).

## 2 · Sémantika

Model `M: Atom → {TRUE, FALSE}` (úplné ohodnocení scope, viz MODEL_REASONING
ve fázi 6) **splňuje**:

- `CardinalityConstraint` ⇔ `at_least ≤ |{a ∈ atoms : M(a)}| ≤ at_most`
  (`at_most = None` = bez horní meze),
- `ExpressionConstraint` ⇔ `evaluate(expr, M) == True`.

`to_expression()`:

- `ExpressionConstraint` → svůj výraz.
- `Cardinality(atoms, k, k)` → disjunkce přes k-prvkové podmnožiny konjunkcí
  (vybrané kladně, zbylé negované). Kombinatorická expanze je přípustná jen pro
  malé rodiny — nad `max_expansion_atoms` (registr prahů, návrh 12) vrací
  `to_expression()` hlasitou chybu a orákulum použije **přímé počítání** podle
  definice výše. Obě cesty (expanze × počítání) se testují na shodu (T-11).

## 3 · Parciální čtení (pro propagaci ve fázích 5–7)

Kardinalita nad částečným ohodnocením vrací `Truth`:

```
known_true  = |{a : partial[a] = True}|      known_false = |{a : partial[a] = False}|
open        = |atoms| − known_true − known_false

FALSE  pokud known_true > at_most  nebo  known_true + open < at_least
TRUE   pokud at_least ≤ known_true  a  (at_most je None nebo known_true + open ≤ at_most)
UNKNOWN jinak
```

Vlastnost k testování (obdoba K3 monotonie): ne-UNKNOWN výsledek se nezmění
žádným doplněním. Propagační důsledky (např. „zbývá jediný otevřený atom a
at_least nesplněno ⇒ musí být TRUE") jsou věc solveru ve fázi 6 — tady se
definuje jen pravdivost.

## 4 · Rodiny atomů (pomocník, ne sémantika)

`atom_family(relation, fixed: dict[pozice → Term], over: Domain) → tuple[Atom,...]`
— vygeneruje rodinu ground atomů („nástroj Anny: instrument(Anna, x) pro x
z domény nástrojů"). Čistá funkce nad deklaracemi; žádná znalost úloh. Zebra §29
se pak **zapisuje daty**: 4 osoby × 4 domény × kardinality + 10 výrokových
podmínek — bez jediného řádku speciálního kódu.

## 5 · Provenience

Constraint je objekt báze s proveniencí jako fakt či pravidlo (KNOWLEDGE_MODEL
§ 7). Vysvětlení „proč model nevyhovuje" ukazuje na konkrétní constraint
a řádek jeho definice — to je základ meta-dotazů §30 (která podmínka vyřadila
model; redundance podmínek je fáze 7).
