# HANDOVER — obecný systém znalosti a logického reasoningu v conBond3

**Větev:** `feature/general-reasoning` (zamergováno do `main`); navazuje
`feature/handover-fronta` (expanze zadání J., 10. 8. 2026 — hotová,
viz § 3 a plán `docs/superpowers/plans/2026-08-10-handover-fronta.md`).
**Datum:** 2026‑08‑10.
**Rozsah:** stav práce na zadání „obecný systém pro reprezentaci znalosti,
učení a logický reasoning", co je hotové, a **co je nutné teď řešit** v každé
oblasti. Dokument je pro člověka, který práci přebírá bez kontextu konverzace.

---

## 1 · Co conBond3 teď je (dvě vrstvy vedle sebe)

Systém má **dvě odpovídací cesty, které běží současně** a nikdy se
nezaměňují (migrační zásada „vedle, ne místo"):

1. **Retrieval (původní cb_bond)** — statistický vyhledávač odpovědí nad
   korpusem: otázka → aktivační pole → graf závislostí → rozklad skóre
   (meet/cover/topic/given/…). Beze změny; 787 jeho testů zeleně po celou dobu.
2. **Formální reasoning (nové cb_logic + cb_interpret)** — přirozený jazyk →
   formální reprezentace → inference/modely → odpověď s důkazem. Odpovídá,
   **jen když si je jistý interpretací**; jinak mlčí a nechá odpovědět retrieval.

REST/okno/konzole vracejí obě: retrieval (skóre, kandidátní věty, graf) i
`logic` (verdikt + řetěz doložení / doptání). Klíč `logic` je `null`, když
formální vrstva větu neunese.

**Cesta výpočtu (formální):**
```
text → UDPipe rozbor → interpretace (cb_interpret) → kandidátní tvrzení
    → validace + knowledge base (cb_logic) → inference / modely
    → formální výsledek (TRUE/FALSE/UNKNOWN · POSSIBLE/NECESSARY/IMPOSSIBLE)
    → provenance → vysvětlení → odpověď
```

## 2 · Balíky a odpovědnosti

| balík | co dělá | závislosti |
|---|---|---|
| **cb_logic** | formální jádro: termy, výrazy (AST), pravdivost (2‑hod. + K3), constrainty, KnowledgeBase, inference (forward/backward, fixpoint, retract, assumptions), prostor modelů (possible/necessary/impossible, protipříklady), provenance, JSON persistence | **žádné** (stdlib; jádro pod vším) |
| **cb_interpret** | jazyk → tvrzení: kopulové/slovesné vzory, složené přísudky (predikace), jednotlivina/třída, učené jazykové vzory (modalita), doptání, renderování vysvětlení | cb_udpipe (typ Token), cb_logic |
| **cb_bond/logic.py** | most: učení z dialogu, formální odpovědi, doptání, persistence báze i vzorů; integrace do REST/okna/konzole | cb_interpret, cb_logic |

Import guard: `cb_logic` neimportuje nic z `cb_*`; `cb_interpret` jen
`cb_logic` + `cb_udpipe`. Hlídáno grepem (viz `run-python -m unittest` a
příkazy v § 8).

## 3 · Co je hotové (a otestované)

- **cb_logic (fáze 1–8), 157 testů.** Kompletní: knowledge model, IR výrazů,
  truth semantics (TRUE/FALSE/UNKNOWN, konflikt jako stav báze — BOTH se
  nezavádí), constrainty (kardinality + výraz, dvě čtení jedné sémantiky),
  forward chaining do fixpointu, well‑founded retract, backward proof,
  assumptions, prostor modelů + modální dotazy s protipříklady, redundance,
  why/why‑not, JSON round‑trip. **Tři nezávislá orákula** (plná tabulka,
  naivní forward, plná enumerace modelů).
- **cb_interpret, 44 testů.** Kopulové věty vč. **složených přísudků**
  (`amod` vlastnosti, `nmod`+`case` vztahy — nic se neztrácí), jednotlivina
  vs. třída s **doptáním na referenci**, třídní čtení přes probe, slovesné
  věty, **učené modální vzory** (moci → POSSIBLE …) jako data s hypotézou/
  proveniencí/odvolatelností, renderování do češtiny. Zmražené rozbory
  skutečného UDPipe jako zemní pravda.
- **Integrace cb_bond, 291 testů (275 + 16 nových).** LogicBridge, REST
  (`/v1/logic/pattern`, `/v1/logic/forget`), konzole (`:vzor`, `:zapomen`,
  `:context`) i okno (příkazy + rozlišení tvrzení/otázka podle otazníku).
  Znalost i vzory **přežívají restart** (P5 pro novou vrstvu).
- **Benchmark generalizace.** 13 úloh z Bartlové (2014) čistě daty; akceptační
  úloha §59 vytvořená po implementaci, invariantní přes přejmenování/permutaci/
  šum. Anti‑overfitting audit (GENERALIZATION_AUDIT.md).
- **Fronta z expanze zadání (10. 8. 2026) — hotová:**
  - *Interaktivní rozřešení reference v UI (4.1.3).* `LogicBridge` drží
    poslední nejednoznačný dotaz; `:instance`/`:trida` v okně i konzoli,
    `POST /v1/logic/resolve` v REST. Plný kruh „Auto je dopravní
    prostředek." → otázka → volba → Ano/Ne/Nevím funguje v prohlížeči.
  - *Slovesné složené přísudky (4.1.1).* `verb_conjuncts`: obj + všechny
    obl (předložka i holý pád → `jet_ins`) + advmod jako vlastnost děje
    (`jet_rychle`); operátorová cesta se ptá nad konjunkcí. Co rozklad
    neunese, je `unparsed` s důvodem — konec tichého zahazování.
  - *Genitivní `nmod` (4.1.2).* Holý pád pojmenuje vztah (`gen(město,
    česko)`); bez předložky i pádu → `unparsed` (pojistka).
  - *Dluhy 4.4 (první dvě odrážky).* Skripty `protokol.py` a
    `rozklad-skore.py` jdou spustit (+ smoke test); `MatchResult.__or__`
    je sjednocení, `__invert__` přeřazuje, kompozice nese rozklad.
- **Celkem 1046 testů zeleně** (`./run-python -m unittest discover -s . -p "test_*.py" -t .`).

## 4 · CO JE NUTNÉ TEĎ ŘEŠIT (podle oblastí)

Prioritizováno; každá položka nese, kde je popsaná a proč je důležitá.

### 4.1 Interpretační vrstva (cb_interpret) — nejaktivnější fronta

1. ~~**Slovesné složené přísudky.**~~ **HOTOVO** (viz § 3) —
   `verb_conjuncts` v `interpret.py`, INTERPRETATION_IR § 2b.
2. ~~**Genitivní `nmod` bez předložky.**~~ **HOTOVO** (viz § 3) —
   holopádový `RelationMod.marker`, INTERPRETATION_IR § 2.
3. ~~**Interaktivní rozřešení reference v UI.**~~ **HOTOVO** (viz § 3) —
   `:instance`/`:trida`, `/v1/logic/resolve`, INTERPRETATION_IR § 5.
4. **`chtít` a propoziční postoje.** Postoj → **referent + omezení**
   (úloha typu autíčko z Bartlové: „chci autíčko s houkačkou" → hledaný objekt
   splňuje `houkačka`). Jiná cílová operace než modelový dotaz; navazuje na
   constraint vrstvu. (INTERPRETATION.md, LANGUAGE_LEARNING § obecnost.)
5. **Scelování lemmat / zmínka vs. entita.** „lidé" ≠ „člověk", „auta" ≠
   „auto" jsou dnes různé relace/entity. Bez scelení se pravidla nepropojí.
   Vrstva zmínky/entity (kap. 14.7 návrhu) zatím není.
6. **Koreference a elipsa** („Čí?", „A on?") — mimo rozsah dnešní věty‑jako‑
   jednotky. (INTERPRETATION.md meze.)

### 4.2 Reasoning jádro (cb_logic) — stabilní, drobné otevřené body

1. **Modalita `grounded` do UI.** `_run_modal` už vrací `grounded`
   (rozliší „našel model" od „nic nezakazuje"), ale okno/konzole ho zatím
   nezobrazují jinak. → v odpovědi odlišit „ano, plyne to" od „ano, nic tomu
   nebrání". (INTERPRETATION_IR § 6.)
2. **Šev na externí solver.** Pro velké constraint problémy je DFS enumerace
   dostačující dnes, ne nutně do budoucna. Případný SAT/CSP solver patří
   **za šev** (nová rozhodovací cesta měřená proti orákulům), se **jmenovitým
   schválením závislosti** (README‑MODULES § schválené závislosti). Dnes žádný
   solver není a jádro nemá závislosti — to je záměr, ne dluh.
3. **Kvantifikace.** Rozsah je výroková logika + třídy nad konečnými doménami.
   Plná predikátová/temporální/deontická logika je vědomě mimo (LOGIC_SEMANTICS
   § 6, kap. 41). Nerozšiřovat bez rozhodnutí — je to hranice, ne mezera.

### 4.3 Integrace a služba (cb_bond)

1. **Formální odpověď jako primární v Responderu.** Dnes je `logic` aditivní
   klíč vedle retrievalu. Povýšení „když formální cesta odpoví, je to hlavní
   odpověď" je vědomě odloženo, až bude z provozu jistota. (MIGRATION § 4.)
2. **Persistence retrieval registru (P5).** Mechanika `registry.save/load` je
   hotová v cb_field, **nezapojená**; `module.state.*` v konfiguraci se
   validuje a nečte. Dialogové doplnění korpusu proto nepřežije restart
   (formální vrstva ANO). (ARCHITECTURE_REVIEW P5.)
3. **Trace (P7).** `trace` napříč moduly se v praxi nepředává (audit: 1,3 %).
   Provenance formální vrstvy na logu nezávisí, ale provozní stopa dotazu by
   měla existovat. (ARCHITECTURE_REVIEW P7.)

### 4.4 Dluhy z auditu retrieval vrstvy (ARCHITECTURE_REVIEW příloha A)

Malé, oddělené opravy — nebrání ničemu výše, ale visí:
- ~~`cb_bond/scripts/protokol.py` a `rozklad-skore.py` mají **SyntaxError**~~
  **HOTOVO** — importy opravené, hlídá `cb_bond/tests/test_scripts.py`.
- ~~`MatchResult.__or__` vrací fakticky průnik; `__invert__` nepřeřazuje;
  kompozice zahazuje rozklad.~~ **HOTOVO** (viz § 3).
- `training.py` čte `answer_position`, který v datech supervize není (mrtvá
  větev).
- Chybí AST test směru závislostí (T‑12); přímé importy do vnitřku cb_field.
- Drift dokumentace v `requirements.txt` (neexistující `graphview.py`, numpy).

### 4.5 Testy a generalizace (průběžně)

- Každý nový interpretační vzor musí projít **renaming + unseen** testem,
  jinak je to skryté hardcodování (§60). Generalizační sada je
  `cb_interpret/tests/vzorky_struct.py` — rozšiřovat o strukturálně nové věty,
  ne o parafráze.
- `hypothesis` v prostředí není; property testy jedou nad vlastním generátorem
  se semínkem. Rozhodnutí, zda přidat `hypothesis` jako schválenou dev
  závislost, je stále otevřené (TEST_STRATEGY, ARCHITECTURE_REVIEW § 14).

## 5 · Zásady, které se NESMÍ porušit (guardy)

- **Modální logika se nezavádí jako osa pravdivosti.** „může/musí/nemůže" jsou
  **dotazy nad modely** (∃M/∀M/¬∃M), ne operátory objektového jazyka: `∃M P(M)
  ≠ ◇P`. Strojově hlídáno (`cb_interpret/tests/test_pattern_guard.py`): menu
  bez modálních operátorů, modální vzor volá `classify_query` nikdy
  `assert_candidate`, `Expression` bez uzlu modality. (LANGUAGE_LEARNING.md.)
- **Statistika/jazyk navrhuje, nerozhoduje o pravdivosti (INV‑11).** Dialog
  učí jen mapování (slovo → existující operace), nikdy sémantiku operace.
- **Tiché zjednodušení, které mění význam, je nepřípustné.** Buď strukturovaná
  reprezentace, nebo `unparsed`/`needs_pattern`/`reference_ambiguous` s důvodem
  — nikdy hádání.
- **Determinismus.** Žádné hodiny, žádná neseedovaná náhoda; kanonická pořadí.
- **Konflikt se hlásí, nepřepisuje (INV‑5); UNKNOWN ≠ FALSE ≠ chyba (INV‑9).**

## 6 · Kudy číst dokumentaci

```
ARCHITECTURE_REVIEW.md   audit + 8 zásadních problémů + cílová architektura
KNOWLEDGE_MODEL.md       objekty znalosti (Entity/Fact/Rule/…)
LOGIC_SEMANTICS.md       AST výrazů, 2‑hod. + K3, tabulka jako orákulum
CONSTRAINT_MODEL.md      kardinality + výrazové constrainty
INFERENCE_ENGINE.md      KnowledgeBase, forward/backward, retract, assumptions
MODEL_REASONING.md       prostor modelů, possible/necessary/impossible
PROVENANCE.md            derivační graf, why/why‑not, persistence
INTERPRETATION.md        jazyk → tvrzení, učení z dialogu (fáze 9–11)
LANGUAGE_LEARNING.md     učené jazykové vzory (modalita), guard
INTERPRETATION_IR.md     obecná sémantická interpretace (složené přísudky, reference)
MIGRATION.md             průběh po fázích, rollback, co zbývá
TEST_STRATEGY.md         šest vrstev testů, tři orákula
GENERALIZATION_AUDIT.md  anti‑overfitting + 20 otázek §57
CURRENT/TARGET_DEPENDENCIES.md   graf závislostí před/po
```

## 7 · Jak spustit a ověřit

```bash
# všechny testy (1046)
./run-python -m unittest discover -s . -p "test_*.py" -t .

# jen nové vrstvy
./run-python -m unittest discover -s cb_logic -t .
./run-python -m unittest discover -s cb_interpret -t .

# služba + okno v prohlížeči
./cb-bond.py start
#   → REST 42400, okna http://127.0.0.1:42401
./run-python -m cb_bond.console        # dialog v terminálu (spolehlivější než okno)

# import guardy
grep -rn "^from cb_\|^import cb_" cb_logic/ --include='*.py' | grep -v "cb_logic"      # prázdné
grep -rhn "^from cb_\|^import cb_" cb_interpret/*.py | grep -vE "cb_interpret|cb_logic|cb_udpipe"  # prázdné
```

**Dialog v konzoli / okně:** věta bez `?` = tvrzení (učí se), věta s `?` =
otázka (odpoví). `:vzor <slovo> <possible|necessary|impossible>` naučí modální
vzor; `:zapomen <slovo>` ho odvolá; `:context <věta>` explicitně sdělí;
`:instance` / `:trida` odpoví na doptání „instance, nebo třída?";
`:state` vypíše stav. Persistence báze i vzorů: `<data_root>/cb_bond/
persistent-logic/kb.json`.

## 8 · Nejbližší doporučený krok

Body 4.1.1–3 i první dvě odrážky 4.4 jsou hotové (§ 3). Další fronta podle
priorit: **4.1 bod 4 (`chtít` a propoziční postoje)** — navazuje na
constraint vrstvu a nově i na slovesný rozklad; vedle toho drobnosti
**4.2 bod 1 (`grounded` do UI)** a zbytek dluhů **4.4** (mrtvá větev
`training.py`, T‑12 AST test, drift `requirements.txt`).
