# LANGUAGE_LEARNING — učení jazykových mapování, ne logické sémantiky

**Stav:** implementováno (`cb_interpret/patterns.py`, `clarify.py`,
`interpret.py`, `learner.py`; integrace `cb_bond/logic.py`, REST, konzole,
okno); dokument odpovídá implementaci. Vzniká ze specifikace J. + kap. 22–27
návrhu (meta‑učení referenčního jazyka), INV‑11, kap. 41 (žádná modální logika).

## Zásada

conBond se během dialogu učí, **jak přirozený jazyk vyjadřuje již existující
formální operace** — nikdy neučí ani nemění samotné operace.

```
Language layer  ──learned mapping──▶  existing formal operation  ──▶  reasoning
```

Nikdy: `Language layer ──▶ nová ad-hoc logická pravidla`.

## A · Formální operace (pevné jádro, NEUČITELNÉ)

Uzavřené menu primitiv s pevně definovaným významem (LOGIC_SEMANTICS,
MODEL_REASONING):

```
POSSIBLE(P)    ∃ konzistentní model, kde P platí
NECESSARY(P)   ∀ konzistentní modely: P platí
IMPOSSIBLE(P)  ¬∃ konzistentní model, kde P platí
```

Jejich význam nesmí dialog změnit. Menu je uzavřené — učený vzor si z něj jen
vybírá, nový význam vytvořit nelze.

## B · Jazykové spouštěče (učitelné, DATA)

Mapování povrchového tvaru na operaci z menu:

```
trigger:    root.lemma = "moci",  má xcomp
operation:  POSSIBLE
binding:    matrix nsubj → podmět vloženého přísudku (kontrola)
            xcomp → dotazovaná propozice
```

Reprezentováno jako **data** (JSON), ne generovaný kód. Jádro o slově „moci"
nikdy neví.

## Vzor je strukturní, ne věta

Z „Auto může jet na silnici." se NEučí ta věta, ale
`root.lemma=moci ∧ xcomp` → POSSIBLE. Tentýž vzor musí platit pro „Petr může
přijít.", „Anna může hrát na housle.", „Stroj může pracovat." — pro libovolné
entity a predikáty téže syntakticko‑sémantické struktury. Ověřuje se renaming
testem (jinak je to skryté hardcodování jedné věty, §60).

## Systém se ptá (uzavřené menu)

Zná‑li parser strukturu, ale ne sémantické mapování slovesa, **nehádá** —
vytvoří učicí dotaz a nabídne **jen operace z menu**:

```
„Auto může jet na silnici." — strukturu znám, sloveso 'moci' neznám.
Jakou operaci to vyjadřuje?
  (a) POSSIBLE   – platí aspoň v jednom řešení
  (b) NECESSARY  – platí ve všech řešeních
  (c) IMPOSSIBLE – neplatí v žádném řešení
```

## Životní cyklus vzoru

```
HYPOTHESIS → CONFIRMED → (REJECTED) → REVOKED
```

První naučení je **hypotéza**. Při dalším výskytu se smí použít, ověřit
konzistence, případně znovu zeptat, a podle potvrzení změnit status.

## Provenance a odvolatelnost

Každý vzor nese `trigger · operation · learned_from · learned_at · status`.
Na „Proč conBond rozumí slovu *moci* takhle?" odpoví zdrojem. „Zapomeň, jak
jsi rozuměl slovu moci." vzor odstraní/deaktivuje — **operace POSSIBLE zůstává**,
mizí jen mapování `moci → POSSIBLE`.

## Hranice, kterou to NEsmí prolomit (guard)

Modální sloveso je **spouštěč dotazu nad modely**, ne modální operátor:
`∃M P(M) ≠ ◇P`. Osa pravdivosti zůstává TRUE/FALSE/UNKNOWN; POSSIBLE/NECESSARY/
IMPOSSIBLE jsou verdikty dotazu, ne pravdivostní hodnoty propozice.

**Strojově vynucené invarianty** (testy):
1. Menu operací neobsahuje žádný modální operátor — jen dotazy nad modely.
2. Modální vzor produkuje **dotaz** (`classify_query`), nikdy uložené tvrzení
   (`assert_candidate`).
3. `Expression` (objektový jazyk) nikdy neobsahuje uzel modality.
4. Negace operátoru („nemůže") mění **který dotaz**, ne pravdivostní osu:
   `¬POSSIBLE = IMPOSSIBLE`, `¬NECESSARY(P) = POSSIBLE(¬P)`.

## Obecnost

Týž mechanismus učí mapování i pro jiné konstrukce, pokud jejich cílová operace
už v jádru existuje. Modalita je první případ, ne jediný.
