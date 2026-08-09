# LOGIC_SEMANTICS — reprezentace a sémantika logických výrazů (návrh, fáze 2)

**Stav:** návrh ke schválení, před implementací.
**Vzniká z:** zadání §12–§17, §21–§24, §33; KNOWLEDGE_MODEL.md; README-ARCHITECTURE_OVERVIEW
kap. 16 (C-3, C-4, C-12), kap. 20 (pohledy, orákulum).

Zásada celku: **jedno IR, více pohledů.** Pravdivostní tabulka, Quineovo částečné
vyhodnocení, šipkový diagram i množinové operace jsou různá čtení téhož stromu,
ne samostatné motory. Booleova algebra jako druhý přepisovací kalkul se nezavádí
(kap. 41); algebraické zákony (§ 5) jsou **testovatelné vlastnosti evaluace**,
ne přepisovací engine.

---

## 1 · AST výrazů

```
Expression = Const(TRUE | FALSE)
           | AtomRef(atom)          list — odkaz na Atom (KNOWLEDGE_MODEL § 3)
           | Not(Expression)
           | And(Expression, …)     n-ární, n ≥ 1
           | Or(Expression, …)      n-ární, n ≥ 1
           | Implies(antecedent, consequent)
           | Equiv(left, right)
```

Vlastnosti reprezentace:

- **Neměnné hodnoty** (frozen), rovnost strukturální, hash konzistentní s rovností.
- **Kanonický textový zápis** pro každý uzel (deterministický, uzávorkovaný) —
  slouží ladění a stabilnímu řazení, **nikdy** parsování za běhu; výraz není string
  (zadání §12).
- `atoms(expr)` vrací množinu atomů v **deterministickém pořadí** (stabilní klíč
  atomu), na tom stojí reprodukovatelnost tabulek.
- `substitute(expr, binding)` — dosazení termů za proměnné (pro instanciaci pravidel);
  vrací nový výraz, nikdy nemutuje.
- Pomocné konstruktory zploští vnořené `And`/`Or` téhož druhu; `Implies`/`Equiv`
  se **nepřepisují** na AND/OR/NOT při konstrukci — strukturu, kterou uživatel
  vyslovil, nese vysvětlení (přepis je až věc pohledů/normalizace).

## 2 · Vyhodnocení: dvouhodnotové jádro

`evaluate(expr, assignment) → TRUE | FALSE` pro **úplné** ohodnocení
`assignment: Atom → {TRUE, FALSE}`. Standardní sémantika spojek; `Implies(a, b)` =
materiální implikace; `Equiv` = rovnost hodnot. Chybějící atom v úplném ohodnocení
je chyba volajícího (hlasitá), ne UNKNOWN — dvě různé situace se nesmí slít (INV-9).

## 3 · Pravdivostní tabulka a rozhodovací dotazy (referenční orákulum)

`truth_table(expr) → [(assignment, value)]` — enumerace všech 2ⁿ ohodnocení atomů
výrazu v kanonickém pořadí (atomy dle stabilního klíče, ohodnocení jako binární
čítač). Nad tím:

```
is_tautology(expr)      všechna ohodnocení TRUE
is_contradiction(expr)  všechna ohodnocení FALSE
is_satisfiable(expr)    aspoň jedno TRUE (+ vrací svědka)
```

- **Strop:** enumerace nad `max_atoms` (registr prahů; výchozí návrh 20 atomů =
  1M řádků) vrací `INCOMPLETE`, nikdy nepravdivý verdikt (zadání §24). Volající
  dostane, kolik bylo prozkoumáno.
- Tabulka je **pohled a orákulum** (kap. 20.6): pomalá, zjevně správná — referenční
  implementace pro testy rychlejších cest (zadání §41). Chytřejší rozhodování
  (propagace, Quine) přijde ve fázích 5–7 a měří se **proti ní**.

## 4 · Parciální vyhodnocení: silná Kleeneho logika (K3)

`evaluate_partial(expr, partial) → TRUE | FALSE | UNKNOWN` pro částečné ohodnocení.
Silné Kleeneho tabulky:

```
NOT U = U
U AND F = F     U AND T = U     U AND U = U
U OR  T = T     U OR  F = U     U OR  U = U
A IMPLIES B ≡ NOT A OR B        A EQUIV B = U, je-li kterákoli strana U
```

Význam `UNKNOWN` je **epistemický** („nevím"), ne třetí ontologická hodnota:
platí, že je-li `evaluate_partial ≠ UNKNOWN`, pak každé úplné doplnění dá týž
výsledek (monotonie K3 — testovaná vlastnost, § 5). Proto smí inference používat
částečné vyhodnocení jako zkratku, aniž změní výsledek. `A OR NOT A` s neznámým
`A` je v K3 `UNKNOWN`, tautologii rozhoduje § 3 — obě čtení jsou správná a systém
je nesměšuje: **dotaz na platnost výrazu v situaci** (K3) vs. **dotaz na logickou
nutnost** (tabulka/modely).

## 5 · Algebraické vlastnosti = testy

Property-based testy nad generátorem náhodných výrazů (semínko fixní, stdlib
`random` — bez nové závislosti; rozhodnutí o `hypothesis` je otevřené, viz
ARCHITECTURE_REVIEW § 14):

```
identita        A AND TRUE ≡ A · A OR FALSE ≡ A
komutativita    A AND B ≡ B AND A · A OR B ≡ B OR A
asociativita    (A AND B) AND C ≡ A AND (B AND C) · totéž OR
dvojí negace    NOT(NOT A) ≡ A
absorpce        A OR (A AND B) ≡ A · A AND (A OR B) ≡ A
De Morgan       NOT(A AND B) ≡ NOT A OR NOT B · duálně
implikace       (A IMPLIES B) ≡ (NOT A OR B)
K3 monotonie    rozšíření částečného ohodnocení nemění ne-UNKNOWN výsledek
ekvivalence ≡   znamená: shodná hodnota pro VŠECHNA ohodnocení (přes tabulku),
                u K3 navíc shodná pro všechna částečná
```

Metamorfní testy (zadání §40, §43): přejmenování atomů zachovává tabulku
(modulo přejmenování); permutace argumentů And/Or zachovává hodnotu; přidání
nezávislého atomu nemění verdikt tautologie/kontradikce.

## 6 · Kvantifikátory — přesná hranice podpory

**Podporováno (konečné domény):**

- `∀` jako **schéma**: `Rule` s proměnnými se instanciuje přes deklarované konečné
  domény (grounding). `Každý programátor je člověk` ⇒ `programmer(X) → human(X)`
  ⇒ instance pro každé X z domény osob.
- `∃` jako **dotaz nad modely**: `∃x programmer(x)` = `Or` přes instanciace /
  possible-dotaz. `∃!` = `ExactlyK(…, 1)` (KNOWLEDGE_MODEL § 6).
- Negace kvantifikátorů přes konečné domény: `NOT ∀ ≡ ∃ NOT` (De Morgan přes
  instanciace) — platí konstrukcí.

**Nepodporováno:** neomezené domény, vnořená kvantifikace s funkčními symboly,
unifikace nad nekonečnými strukturami — tedy plná FOL. **Proč:** rozsah systému
je výroková logika + třídy nad konečnými světy (kap. 20.9); úlohy zadání (dedukce,
zebra, množiny) to pokrývá a rozhodnutelnost zůstává triviální.

**Jak se brání předstírání širší podpory:** instanciace přes doménu, která není
deklarovaná (nebo je prázdná), je **hlasitá chyba dotazu**, ne tiché `FALSE`;
`Rule` bez domény pro některou proměnnou se odmítne při zápisu do báze. Dokumentace
API u každého kvantifikačního místa odkazuje sem.

## 7 · Rekurze, cykly, fixpoint, limity

(Plná mechanika je fáze 5; sémantika se fixuje teď, aby na ni IR myslelo.)

- Forward chaining = opakovaná instanciace pravidel nad známými fakty do
  **fixpointu** (`K(n+1) = K(n)`); odvozený fakt je vstupem dalšího kola (kap. 21).
- **Cykly** (`A → B`, `B → A`) jsou bezpečné z konstrukce: odvození přidává jen
  ground literály do množiny, množina je konečná (konečné domény), fixpoint
  terminuje. Derivace nese premisy, takže cyklus nevyrobí kruhové zdůvodnění —
  derivační graf je DAG přes *kroky*, ne přes literály.
- **Limity** (`max_iterations`, `max_derivations`, `max_depth`, `max_atoms`,
  volitelně `time_budget`) žijí v registru prahů (kap. 29), výsledek po limitu je
  `INCOMPLETE` s údajem, co se stihlo — nikdy tiché `FALSE`.

## 8 · Determinismus

- Žádné čtení hodin ani neseedovaná náhoda v celém `cb_logic`.
- Iterace v kanonickém pořadí (stabilní klíče atomů/termů); při shodě rozhoduje
  klíč, ne pořadí v paměti (kap. 5 návrhu).
- Táž báze + týž dotaz ⇒ týž výsledek včetně pořadí modelů a svědků.

## 9 · Pohledy nad IR (výhled, neimplementuje se ve fázi 2)

| pohled | co čte | fáze |
|---|---|---|
| pravdivostní tabulka | § 3 | 2 (zároveň orákulum) |
| množinové operace / Venn | třídy jako unární relace; ∩∪\⊆ nad modely | 6–7 |
| šipkový diagram (C-3) | implikace + modus ponens/tollens | 5 |
| přiřazovací tabulka (C-7) | atomy `attr(e,v)` + kardinality | 6 |
| Quine (částečné vyhodnocení) | § 4 + větvení | 7 |

Zkouška T-11 (křížová shoda pohledů) platí od prvního dne: dva pohledy na táž
data si nesmějí odporovat; rozdíl je chyba pohledu, ne remíza.

## 10 · Rozsah implementace fáze 2 (definition of done)

1. `cb_logic/terms.py` — Entity, Value, Variable, Domain, Relation, Atom, Literal.
2. `cb_logic/expressions.py` — AST (§ 1), `atoms()`, `substitute()`, kanonický zápis.
3. `cb_logic/semantics.py` — `evaluate` (§ 2), `evaluate_partial` (§ 4),
   `truth_table`, `is_tautology/contradiction/satisfiable` (§ 3) s limitem.
4. Testy: jednotkové + property/metamorfní (§ 5) čistým `unittest` + stdlib
   `random(seed)`; pojistka proti vakuu (T-13): generátor musí doložit, že vyrobil
   i hluboké výrazy, negace i oba kvantifikační vzory.
5. Žádná závislost mimo stdlib; žádný import z cb_* (jádro je pod všemi vrstvami).

Mimo rozsah fáze 2: KnowledgeBase a validace (fáze 1 objektů se implementuje
v témž kroku jen datově — terms.py), inference, constrainty, modely, provenance
mechanika — fáze 3+.
