# INTERPRETATION_IR — obecná sémantická interpretace (návrh + implementace)

**Stav:** implementováno (`cb_interpret/predication.py`, `interpret.py`,
`learner.py`); dokument odpovídá implementaci. Pokryté jsou kopulové věty,
slovesné složené přísudky (`verb_conjuncts` — advmod, více argumentů, holé
pády; § 2b) i genitivní/holopádový `nmod` (§ 2). Doptání na referenci (§ 5)
je zapojené v okně/konzoli (`:instance`/`:trida`) a REST
(`POST /v1/logic/resolve`).
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
- `nmod` bez `case` s featem `Case` → **RelationMod** pojmenovaný pádem
  (`gen`, `dat`, …): „hlavní město **Česka**" → `gen(město, česko)`. Jméno
  z UD hodnoty je strukturální — nepodsouvá posesivní čtení. Bez předložky
  i pádu → `blockers` → `unparsed` s důvodem (pojistka).

Rekurzivně, podle role vazby — žádný seznam slov.

## 2b · Slovesné věty (`verb_conjuncts`)

Týž mechanismus pro kořen VERB (`_verbal` i vložený přísudek `_operator`):

```
obj          sloveso(podmět, předmět)          znát(petr, jana)
obl+case     sloveso_předložka(podmět, cíl)    jet_po(petr, dálnice)
obl bez case sloveso_pád(podmět, cíl)          jet_ins(petr, auto)
advmod       sloveso_příslovce(podmět)         jet_rychle(petr)
bez argumentů  sloveso(podmět)                 spát(petr)
```

Vlastnost děje se jmenuje slovesem i příslovcem — holé `rychlý(petr)` by
tvrdilo vlastnost podmětu, ne děje. Událostní reifikace (`Event(jede)`) by
chtěla existenční kvantifikaci v dotazech, a to je hranice jádra
(HANDOVER 4.2.3) — konjunktivní čtení je vědomá aproximace, táž jako
u kopulového složeného přísudku. Vazba mimo výčet (`iobj`, `ccomp`, `aux`,
rozvitý argument, …) → `unparsed` s důvodem. Negace složeného přísudku →
`unparsed` (De Morgan guard). U `_operator` jde konjunkce jako JEDEN
modální dotaz nad výrazem (`jet_po ∧ jet_do`).

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

- **instance** → dotaz `prostředek(a) ∧ dopravní(a)` nad kopií báze
  s **presupozicí členství** `auto(a)`: kdo se ptá na „konkrétní auto",
  jeho auto‑ství nezpochybňuje — členství zakládá reference sama, takže
  pravidla třídy se na referent vztahují a doptání „je auto auto?"
  nemůže vzniknout.
- **třída** → „platí ∀x auto(x) → …?" ověří se **arbitrární instancí** (probe):
  předpokládej `auto(probe)`, odvoď, a je‑li konjunkce pro probe splněná ve
  všech modelech, univerzál platí (assumptions + inference — už existují).

Obě čtení tedy sdílejí týž mechanismus (kopie báze + assumption +
inference); liší se jen tím, čí členství se předpokládá — referentu,
nebo arbitrární instance.

**Zapojení v UI (hotové):** `LogicBridge` drží **poslední nejednoznačný
dotaz** (jeden slot, bez hodin — determinismus; nová otázka ho přepíše,
`:context` ho nechává). Okno i konzole odpověď dokončí příkazem
`:instance` / `:trida`; REST přes `POST /v1/logic/resolve`
`{"choice": "instance"|"class"}`. Volby v odpovědi nesou i `command`
pro klikací klienty. Slot se nepersistuje — je to rozpracovaný dialog,
ne znalost.

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
