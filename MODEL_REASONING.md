# MODEL_REASONING — prostor modelů a modální dotazy (návrh, fáze 6–7)

**Stav:** implementováno (`cb_logic/models.py`); dokument odpovídá implementaci.
**Vzniká z:** zadání §25–§31; KNOWLEDGE_MODEL.md § 8, § 11; CONSTRAINT_MODEL.md;
INFERENCE_ENGINE.md.

Klíč celé fáze: **possible / necessary / impossible je obecná vlastnost enginu**,
ne vlastnost úloh. Zebra §29, protipříklady §27 i meta-dotazy §30 jsou dotazy nad
týmž prostorem modelů.

---

## 1 · Model a jeho scope

**Model** = úplné ohodnocení `Atom → {TRUE, FALSE}` nad konečnou množinou atomů
(**scope**), které:

1. souhlasí s doloženými čteními báze (atomy s `truth_of ∈ {TRUE, FALSE}` na
   úrovni ≥ DOCUMENTED jsou předobsazené; karanténované konfliktní atomy se
   **nepředobsazují** — obě možnosti se prozkoumají a odpověď nese `conflicted`),
2. splňuje všechny constrainty báze (CONSTRAINT_MODEL § 2),
3. splňuje všechny ground instance pravidel jako implikace `body → head`
   (pravidlo je v modelové sémantice materiální implikace; forward chaining
   z fáze 5 je jen její jednosměrný výpočet).

**Scope** se počítá relevančním uzávěrem (`model_scope(kb, seed_atoms)`):
začni atomy dotazu + atomy constraintů + atomy doložených faktů; přidávej atomy
ground instancí pravidel, které se s množinou protínají, do fixpointu; strop
`max_scope_atoms` (registr prahů) ⇒ `INCOMPLETE`. Uzávěr je zároveň obecný
mechanismus **identifikace relevantní části báze** (zadání §44) — irelevantní
znalost do scope nevstoupí, a proto výsledek nezmění.

Ground instance pravidla, jejíž atomy leží částečně mimo scope po uzávěru,
neexistuje (uzávěr ji přitáhne celou) — vlastnost, na kterou je test.

## 2 · Enumerace modelů

`enumerate_models(kb, scope, limits) → ModelSearchResult(models, status,
nodes_explored, eliminated)`:

- DFS v kanonickém pořadí atomů (atom_key), hodnoty False < True;
- po každém přiřazení propagace ořezáním: `truth_partial` každého constraintu
  a K3 vyhodnocení každé ground implikace — `FALSE` ⇒ řez větve; volitelná
  jednotková propagace kardinalit je optimalizace, jejíž korektnost se měří
  proti čisté DFS (referenční orákulum, T-11);
- `eliminated`: u řezu se zaznamená, který constraint / která instance pravidla
  větev zabila (materiál pro meta-dotazy § 4 — „která informace odstranila
  model");
- limity `max_models`, `max_nodes` ⇒ `INCOMPLETE`; počty modelů a jednoznačnost
  (`len(models) == 1`) jsou čtení výsledku, ne zvláštní mechanismus.

## 3 · Modální dotazy

`modal(kb, expr, scope?, limits) → ModalResult`:

```
POSSIBLE     ∃ M: expr TRUE v M     svědek = první takový model
NECESSARY    ¬∃ M: expr FALSE v M   protipříklad-hledání; nález = NOT necessary
IMPOSSIBLE   ¬∃ M: expr TRUE v M
```

- Hledání protipříkladu (zadání §27) **je** dotaz NECESSARY: „vyplývá, že Boris
  hraje na housle?" = neexistuje konzistentní model, kde nehraje; nalezený model
  je protipříklad a vrací se jako svědek.
- `INCOMPLETE` při limitu — nikdy se nevydává za verdikt; prázdný prostor modelů
  (nesplnitelná báze) se hlásí zvlášť (`UNSATISFIABLE` — vadné zadání, zadání
  §20.7 návrhu: úloha bez modelu není úloha s odpovědí NE).
- Vztah k UNKNOWN z fáze 5: K3 čtení `TruthQuery` je rychlá horní vrstva; modální
  dotaz je úplnější (a dražší) odpověď na totéž — konzistence obou cest je
  testovaná vlastnost (K3 TRUE ⇒ NECESSARY nad scope obsahujícím premisy).

## 4 · Vlastnosti napříč modely a meta-dotazy (zadání §30–§31)

Všechno jsou čtení výsledku enumerace, žádné zvláštní motory:

- `classify_atoms(models, scope)`: atom TRUE ve všech = nutný; FALSE ve všech =
  nemožný; jinak možný. („Co musí / může / nemůže platit.")
- „Která informace odstranila model M": vyhodnoť constrainty a instance pravidel
  nad M — vrácené porušené položky s proveniencí; při enumeraci navíc
  `eliminated` z řezů.
- **Redundance podmínky** (§31): constraint `c` je logicky redundantní ⇔ prostor
  modelů bez `c` je týž; zjišťuje se přepočtem bez `c` a porovnáním množin
  (s limity). Odpověď rozlišuje `logical redundancy` od `computational
  usefulness` — redundantní `c` smí zůstat kvůli propagaci; systém to jen hlásí.
- „Rozhodující podmínka pro jednoznačnost": bez které `c` má prostor > 1 model.
- What-if (odebrání/přidání podmínky): přepočet nad upravenou kopií báze —
  báze je hodnota, kopie je levná, nic se nemutuje.

## 5 · Determinismus a limity

Pořadí modelů je dané DFS nad kanonickým pořadím atomů — táž báze ⇒ týž seznam.
Limity deterministické (uzly, modely, scope); vše INCOMPLETE-schopné.
Referenční orákulum: čistá DFS bez propagace (a pro malé scope plná enumerace
2^n přes `truth_table`); produkční cesta se měří proti němu na generovaných
problémech.
