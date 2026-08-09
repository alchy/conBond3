# KNOWLEDGE_MODEL — formální model znalosti (návrh, fáze 1)

**Stav:** implementováno (fáze 2–8, `cb_logic/`) včetně modelových dotazů
a persistence; zbývá interpretace jazyka (fáze 9) a integrace (fáze 11).
Dokument odpovídá implementaci.
**Vzniká z:** zadání §7–§11, ARCHITECTURE_REVIEW §13–14, README-ARCHITECTURE_OVERVIEW
(invarianty INV-1…14, mřížka provenience 14.3).
**Kam míří:** nový balík **`cb_logic`** — čistá knihovna (vzor cb_config/cb_field),
pouze stdlib, bez globálního stavu, deterministická. Identifikátory anglicky,
dokumentace česky (politika § 17; dluh českých jmen z cb_bond se neopakuje).

Tento dokument definuje **objekty a jejich vztahy**. Sémantiku výrazů a pravdivosti
definuje `LOGIC_SEMANTICS.md`. Nic z tohoto dokumentu nezná přirozený jazyk —
jazyková vrstva (interpretace vět) je klient tohoto modelu, ne jeho součást.

---

## 1 · Přehled objektů

```
Term      = Entity | Value | Variable          argument atomu
Atom      = Relation(Term, …)                  nejmenší tvrditelná jednotka
Literal   = Atom | NOT Atom                    atom s polaritou
Expression                                     AST nad literály (LOGIC_SEMANTICS)
Fact      = přijatý ground Literal + Provenance
Assertion = kandidátní tvrzení + Evidence      před validací; není znalost
Rule      = ∀vars: Expression(body) → Literal(head) + Provenance
Constraint= omezení prostoru modelů            (kardinality, exkluze, …)
Assumption= pojmenovaný dočasný předpoklad     kontext odvozování
Evidence  = záznam o původu informace          evidence ≠ pravda
Derivation= závěr + premisy + použité pravidlo uzel derivačního grafu
Provenance= úroveň + evidence + derivace       odpověď na „odkud to je"
Query     = otázka nad znalostí                (truth / possible / necessary / why …)
TruthState= TRUE | FALSE | UNKNOWN             (+ konflikt jako stav báze, viz § 8)
Model     = úplné ohodnocení atomů             konzistentní s bází a constrainty
KnowledgeBase                                  kontejner všeho výše, bez globálů
```

Jediný zákon, který drží celek pohromadě: **všechno, co může ovlivnit odpověď, je
objekt s identitou a proveniencí.** Nic se neodvozuje z řetězců za běhu; jména jsou
neprůhledné identifikátory (renaming test zadání §43 je tím splnitelný z konstrukce).

## 2 · Term: Entity, Value, Variable

- **`Entity`** — identita jednotlivin (osoba, věc). Nese `id` (neprůhledný, stabilní)
  a volitelný lidský popisek; **rovnost výhradně podle `id`**, popisek nesmí vstupovat
  do žádného rozhodnutí (anti-overfitting §46: žádná sémantika ve jménech).
- **`Value`** — literální hodnota z domény (řetězec/číslo/symbol). Hodnoty se
  porovnávají kanonicky; normalizace hodnot je věc interpretační vrstvy.
- **`Variable`** — proměnná pravidel a dotazů; existuje jen uvnitř `Rule`/`Query`,
  do báze nikdy nevstupuje volná proměnná.
- **`Domain`** — pojmenovaná konečná množina termů (např. nástroje v úloze §29).
  Domény jsou data báze, ne kód; kvantifikace pravidel běží přes ně (LOGIC_SEMANTICS § 6).

## 3 · Relation a Atom

- **`Relation`** — pojmenovaný predikát s aritou a volitelnými doménami rolí.
  `programmer/1`, `lives_in/2`, `instrument/2`. Relace se **deklaruje** (jméno, arita),
  aby překlep založil hlasitou chybu, ne tichou novou relaci (poučení z INV-9).
- **`Atom`** — aplikace relace na termy správné arity: `programmer(Petr)`,
  `instrument(Anna, housle)`. **Ground atom** nemá proměnné. Atom je *jednotka
  pravdivosti*: modely přiřazují hodnoty právě atomům.
- **Atribut** (zadání §7) není zvláštní druh objektu: „atribut entity s hodnotou
  z domény" je binární relace `attr(entity, value)` + kardinalitní constraint
  (`exactly_one` přes rodinu atomů). Tím má zebra i `programmer(Petr)` **jeden
  společný formát** a engine nezná rozdíl mezi „úlohou" a „znalostí".

## 4 · Fact vs. Assertion — co je znalost

Přesné definice (zadání §7 „nesmí existovat nekompatibilní interpretace"):

- **`Assertion`** je *kandidátní tvrzení*: ground `Literal` (nebo `Rule`) + `Evidence`.
  Vzniká interpretací dialogu/korpusu nebo návrhem statistické vrstvy. **Není to
  znalost** — do báze vstupuje až validací (kontrola deklarací, detekce konfliktu,
  zápis provenience). LLM/NLP vrstva smí vyrábět pouze Assertions (zadání §9, §47;
  INV-11).
- **`Fact`** je *přijaté* ground tvrzení: `Literal` + `Provenance`. Fakt s literálem
  `NOT p` je plnohodnotný záporný fakt (INV-1: zápor jen z doložené neslučitelnosti
  nebo výslovného tvrzení, nikdy z nepřítomnosti).
- **Odvozený fakt** je Fact s proveniencí úrovně `DERIVED` a odkazem na `Derivation`.
  Žije v **oddělené vrstvě** (INV-3, kap. 14.6 návrhu): smí být kdykoli zahozen
  a přepočítán; doložené + pravidla jsou totéž s menší entropií.

## 5 · Rule

`Rule = (vars, body: Expression, head: Literal, provenance)` — implicitní ∀ přes
všechny proměnné, doména kvantifikace = deklarované domény / entity báze
(LOGIC_SEMANTICS § 6). Příklady:

```
programmer(X) → human(X)
programmer(X) AND lives_in(X, Praha) → works_in_technology(X)
```

- Tělo je libovolný `Expression` nad literály (AND/OR/NOT/…); hlava je jeden literál
  (smí být záporný — pravidla umí vyvracet).
- Pravidlo **odvozuje, nikdy nepřepisuje doložené** (kap. 21 návrhu).
- Pravidlo je objekt s proveniencí jako každý jiný: definice od člověka (úroveň 3),
  indukce z dat (hypotéza, úroveň 0, do odpovědí nevstupuje).

## 6 · Constraint

Omezení prostoru modelů, které se nedá (nebo nevyplatí) vyjádřit jedním pravidlem:

| constraint | význam |
|---|---|
| `ExactlyK(atoms, k)` / `AtLeastK` / `AtMostK` | kardinalita nad rodinou atomů (k=1 dává „právě jeden") |
| `Excludes(a, b)` | ¬(a ∧ b) |
| `Requires(a, b)` | a → b |
| `Equivalent(a, b)` | a ↔ b |
| `Distinct(terms…)` / `Same(t1, t2)` | identita termů (pro přiřazovací úlohy) |
| `ExpressionConstraint(expr)` | obecný výraz, který musí platit ve všech modelech |

Prvních pět jsou **pojmenované zkratky téže sémantiky** — každý constraint umí vydat
svůj ekvivalentní `Expression` (pro referenční enumeraci a pro vysvětlení), ale
solver s ním smí pracovat efektivněji (propagace kardinalit). Jedna sémantika, více
výpočetních čtení — princip pohledů (zadání §33, INV-14).

## 7 · Evidence a Provenance — evidence není pravda

`Evidence` (zadání §10) nese **druh původu**:

```
USER_ASSERTION   uživatel to řekl          OBSERVATION   systém to pozoroval (korpus)
EXTERNAL         vnější zdroj              ASSUMPTION    explicitní předpoklad (§ 9)
HYPOTHESIS       návrh (indukce, LLM)      DERIVED       odvozeno pravidlem/constraintem
```

`Provenance` = úroveň mřížky (převzato z kap. 14.3 návrhu) + evidence + případná
derivace:

```
4  oprava od člověka      přebíjí, spor se zaznamená a je vidět
3  definice od člověka    přebíjí odvozené, ne doložené
2  doloženo               spor dvou doložených = hlášení (INV-5)
1  odvozeno               ustupuje čemukoli doloženému
0  hypotéza               do odpovědi nikdy nevstupuje
```

„Uživatel řekl, že `programmer(Petr)`" ⇒ Fact s literálem `programmer(Petr)`,
evidence `USER_ASSERTION`, úroveň 2–4 dle kontextu. Pravdivost je věc modelů
a dotazů; **báze uchovává tvrzení a jejich původ, ne „pravdu"**.

`confidence` je volitelné pole Evidence a **nikdy nevstupuje do logického výsledku**
(zadání §48–49) — smí řadit kandidáty ve vysvětlení, nic víc.

## 8 · TruthState a konflikt (analýza BOTH)

- Uvnitř **jednoho modelu** je atom `TRUE`/`FALSE` (úplné ohodnocení).
- **Odpověď na dotaz** je trojhodnotová: `TRUE` / `FALSE` / `UNKNOWN`
  (+ `INCOMPLETE`, když výpočet narazil na limit — nesmí se vydávat za FALSE,
  zadání §24). Parciální vyhodnocování používá silnou Kleeneho logiku
  (LOGIC_SEMANTICS § 4).
- **BOTH jako čtvrtá pravdivostní hodnota se nezavádí.** Analýza: paraconsistentní
  hodnota v evaluaci by prosákla do všech spojek a vyrobila druhý kalkul (proti
  kap. 41 návrhu). Konflikt je **epistemický stav báze**, ne hodnota výrazu:
  báze smí současně držet Fact `p` i Fact `NOT p` (oba s proveniencí, nic se
  nemaže — INV-5), a `Conflict(p, provenance₊, provenance₋)` je samostatný objekt.
  Dotaz, jehož vyhodnocení se konfliktu dotkne, ho **nese v odpovědi** (druh
  `conflicted` + obě provenience). Prostor modelů se počítá nad zvolenou
  konzistentní podmnožinou podle mřížky (vyšší úroveň přebíjí; táž úroveň ⇒
  atom se pro modelování vyjme a dotazy na něj hlásí konflikt).

## 9 · Assumption

`Assumption` = pojmenovaný ground literál (nebo množina) přidaný **do kontextu
dotazu**, ne do báze. Odvozování pod předpokladem nese předpokladové jmenovky
v derivaci: závěr `C` odvozený z `ASSUME A` je označen `derived under {A}`
(zadání §37). Odstranění předpokladu neinvaliduje bázi — kontext prostě zanikne.
(ATMS-styl jmenovek; plná správa víry je fáze 8.)

## 10 · Derivation a derivační graf

`Derivation = (conclusion: Literal, premises: [FactRef], rule: RuleRef | ConstraintRef,
assumptions: {AssumptionRef})` — orientovaný acyklický graf; jeden závěr smí mít
**víc derivací** (kap. 18.1 návrhu: řetěz má druhy). Invalidace: odstraněním premisy
zanikají derivace, které ji nesou; fakt bez zbylé derivace a bez vlastní evidence
přestává platit (zadání §38; mechanika ve fázi 8, datový tvar už teď).

## 11 · Query

Dotazy jsou data (objekty), ne metody s vedlejšími účinky:

```
TruthQuery(expr)                  platí výraz? (T/F/UNKNOWN + proč)
ModalQuery(expr)                  possible / necessary / impossible (∃M / ∀M / ¬∃M)
ModelQuery(constraints…)          enumerace konzistentních modelů, počet řešení
WhyQuery(literal)                 derivační řetěz(y)
WhyNotQuery(literal)              protipříklad / chybějící premisy
```

Vyhodnocení dotazů je věc fází 5–7; tvar odpovědi vždy: druh + obsah + řetěz +
provenience (kap. 18 návrhu).

## 12 · KnowledgeBase

Kontejner: deklarace (relace, domény, entity) + fakta + pravidla + constrainty +
konflikty. **Žádný globální stav** — dvě báze v jednom procesu musí jít (kap. 5
návrhu). Zápis pouze validační cestou (`assert_candidate(assertion) → přijato /
odmítnuto / konflikt`). Serializace: každý objekt ↔ JSON beze ztráty (persistence
je fáze 8+; tvar objektů na to myslí od začátku — žádné odkazy cyklem, jen id).

## 13 · Co tento model vědomě nedělá

- **Plná predikátová logika** — kvantifikace jen přes konečné deklarované domény
  (hranice přesně v LOGIC_SEMANTICS § 6, včetně toho, jak systém odmítne předstírat víc).
- **Modální/vícehodnotové logiky, aritmetika** (kap. 41 návrhu).
- **Pravděpodobnostní inference** — confidence je metadata, ne sémantika.
- **Temporalita** — čas je zatím hodnota v relacích, ne osa kalkulu.
