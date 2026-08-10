# INTERPRETATION_IR — obecná sémantická interpretace (návrh + implementace)

**Stav:** implementováno (`cb_interpret/predication.py`, `interpret.py`,
`learner.py`); dokument odpovídá implementaci. Kopulové věty pokryté;
slovesné složené přísudky a genitivní `nmod` jsou další iterace (HANDOVER).
Vzniká ze specifikace J. „od jednotlivých tvrzení k obecnému formálnímu
modelu"; INTERPRETATION.md, LANGUAGE_LEARNING.md, kap. 8 návrhu, INV‑11.

Zásada: **tichého zjednodušení, které mění význam, se vrstva nesmí dopustit.**
Buď vytvoří strukturovanou reprezentaci, nebo část označí za neznámou, nebo
si vyžádá doplnění. Rozhoduje **struktura stromu** (deprel/upos/feats), ne
konkrétní slova; každý formální kus nese **provenienci** (které tokeny ho
vytvořily).

---

## 1 · Sémantická mezireprezentace (Predication)

Mezi strom a logiku vstupuje strukturovaný objekt — kopulová predikace
„podmět JE hlava s vlastnostmi a vztahy":

```
Predication
  subject     Reference(lemma, upos, kind, token)
  head        predikátové jméno (lemma, token)
  modifiers   [Modifier(lemma, token, negated)]        ← amod (vlastnosti)
  relations   [RelationMod(předložka, cíl, token)]      ← nmod+case (vztahy)
  negated     polarita spony
  is_question
```

`Reference.kind ∈ {INDIVIDUAL, CLASS, AMBIGUOUS}`.

## 2 · Obecná extrakce (ne pravidlo pro „dopravní")

Nad kopulovým stromem (kořen NOUN/PROPN + `cop`):

- `nsubj` → **podmět** (Reference).
- kořen → **hlava** (predikátové jméno).
- každý `amod` (ADJ) kořene → **Modifier** (vlastnost; nese vlastní polaritu).
- každý `nmod` kořene s dítětem `case` (ADP) → **RelationMod** (vztah pojmenovaný
  předložkou, cíl = jméno nmod).

Rekurzivně, podle role vazby — žádný seznam slov.

## 3 · Snížení do logiky (zachová VŠECHNY části)

Podmět jako term: INDIVIDUAL → `Entity`; CLASS → proměnná `X` (univerzál).
Konjunkty:

```
hlava:      head(subj)
vlastnost:  modifier(subj)         pro každý amod
vztah:      předložka(subj, cíl)   pro každý nmod+case
```

Snížení podle typu:

| podmět × mood | výsledek |
|---|---|
| INDIVIDUAL · tvrzení | **fakta** (konjunkce): `head(e) ∧ mod(e) ∧ prep(e, cíl)` |
| CLASS · tvrzení | **pravidla**: `subj(X) → head(X)`, `subj(X) → mod(X)`, … (Horn: konjunktivní hlava = víc pravidel) |
| INDIVIDUAL · otázka | **dotaz**: konjunkce atomů, TRUE ⇔ platí všechny |
| CLASS/obecné jméno · otázka | **nejednoznačné** → doptání (§ 5) |

Příklady (obecně, ne ad‑hoc):
```
Auto je dopravní prostředek.   → auto(X) → prostředek(X);  auto(X) → dopravní(X)
Silnice je cesta pro vozidla.  → silnice(X) → cesta(X);    silnice(X) → pro(X, vozidlo)
Petr je zkušený programátor.   → programátor(petr) ∧ zkušený(petr)   (fakta)
Kniha je dárek pro Petra.      → dárek(kniha) ∧ pro(kniha, petr)     (fakta)
```
**„dopravní" ani „pro vozidla" se neztrácejí.**

## 4 · Jednotlivina vs. třída

- **PROPN** → INDIVIDUAL (Petr).
- **obecné jméno bez determinantu, tvrzení** → CLASS (auta obecně → pravidlo).
- **determinant Tot/Neg** → univerzální/negované pravidlo (stávající).
- **obecné jméno, otázka** → **AMBIGUOUS**: nesmí se svévolně zvolit. Systém
  označí nejednoznačnost a **doptá se** (§ 5).

## 5 · Doptání na referenci

`Je auto dopravní prostředek?` → nejednoznačné → dotaz:
> „Ptáš se na **konkrétní auto** (instanci), nebo na **auta obecně** (třídu)?"

- **instance** → dotaz `prostředek(auto) ∧ dopravní(auto)` nad bází.
- **třída** → „platí ∀x auto(x) → …?" ověří se **arbitrární instancí** (probe):
  předpokládej `auto(probe)`, odvoď, a je‑li konjunkce pro probe splněná ve
  všech modelech, univerzál platí (assumptions + inference — už existují).

## 6 · Modalita: „našel model" ≠ „nic to nezakazuje"

Modální `possible` = ANO musí rozlišit **doložené odvození** od **neúplnosti
báze**. Výsledek nese `grounded`: je‑li true, propozice se dotýká nějaké
znalosti (fakt/pravidlo/constraint); je‑li false, kladná možnost plyne jen
z prázdného prostoru — a to se **sdělí** („nic tomu nebrání", ne „vyplývá to").

## 7 · Provenance interpretace

Každý formální kus nese `(text_kusu, token_id)` — z kterých tokenů vznikl.
Umožní zpětně zjistit, proč vznikl vztah `pro(silnice, vozidlo)` i proč byl
podmět označen za třídu. Je to podmínka bezpečného učení: chyba se lokalizuje
(parser × neznámý vzor × mapování × nejednoznačnost × reasoning), ne zakryje.

## 8 · Měření = obecnost, ne příklady

Úspěch NENÍ „projde ‚Auto je dopravní prostředek'". Úspěch je, že **týž
mechanismus** zvládne strukturálně nové věty: jiné hlavy, jiná adjektiva,
jiné předložky, jiné entity, negace, kvantifikátory. Testy proto obsahují
věty **nepoužité při implementaci** (generalizační sada).
