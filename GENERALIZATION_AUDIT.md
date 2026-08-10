# GENERALIZATION_AUDIT — anti-overfitting audit a závěrečných 20 otázek

**Stav:** k dokončení fáze 12; odpovídá implementaci.

## 1 · Anti-overfitting audit (zadání § 46)

Hledáno grepem i čtením v `cb_logic/`, `cb_interpret/`, `cb_bond/logic.py`
(engine; testy smí konkrétní jména obsahovat — jsou to data úloh):

| hledáno | nález |
|---|---|
| hardcoded entities / questions / answers | **žádné** — grep na jména z úloh (petr, anna, boris, jezis, housle, …) v enginu nic |
| special-case parsers / solvers | **žádné** — interpretace rozhoduje výhradně UD kategoriemi (deprel/upos/feats); enumerace nezná pojem „úloha" |
| hidden lookup tables | **žádné** — jediný zásah grepu je `UnboundAtomError(LookupError)` (jméno výjimky) |
| expected-output matching / fallback answers | **žádné** — při neúspěchu se vrací UNKNOWN/unparsed/INCOMPLETE s důvodem, nikdy náhradní odpověď |
| česká slova v řídicích podmínkách | **žádná** — jazyk žije v `cb_interpret/profiles/cs.json`; docstringy a komentáře jsou česky záměrně (politika § 17) |

**Vědomé, zdokumentované výjimky:** (a) generátor bází pro property testy
má kladné hlavy pravidel (zdůvodněno v `kb_generators.py` — úrovňová
jednoduchost orákula; záporné hlavy kryjí jednotkové testy); (b) zmražené
rozbory UDPipe v testech jsou zemní pravda, ne lookup enginu.

**Empirický důkaz generalizace (§ 60):** známé příklady + Bartlová 2014
(13 úloh, nikdo je nepsal pro tento systém — všechny prošly bez změny
enginu) + akceptační úloha vzniklá až po implementaci (§ 59) + náhodně
generované problémy proti třem nezávislým orákulům + přejmenování +
permutace + irelevantní šum + protipříkladové dotazy. Benchmark § 29 se
ukázal být přejmenovaným derivátem Bartlové př. 14 — engine řeší obě
strukturně identicky (a u § 29 poctivě hlásí 2 řešení: 844 uzlů z 2⁶⁴,
0,13 s).

## 2 · Závěrečných 20 otázek (zadání § 57)

1. **Skutečně obecné:** celé `cb_logic` — termy/výrazy/K3/constrainty/
   inference/modely/provenience/persistence pracují nad strukturou, jména
   jsou neprůhledná data (renaming testy).
2. **Heuristické:** interpretační vzory `cb_interpret` (které UD konstrukce
   se převádějí a jak — generické čtení holého NOUN podmětu, dvojí zápor);
   volba minimální množiny jmenovek předpokladů; pořadí DFS. Vše
   deterministické a zdokumentované.
3. **Kde může vzniknout overfitting:** v interpretační vrstvě (vzory šité
   na kopulové/slovesné věty) a u starého retrieval (hyperparametry na 30
   otázkách — evidováno v ARCHITECTURE_REVIEW P8). Jádro je vůči úlohám
   slepé.
4. **False positives:** chybná interpretace věty (špatný rozbor UDPipe,
   generické čtení tam, kde šlo o jednotlivinu) ⇒ chybný fakt v bázi —
   proto každý fakt nese provenienci a jde odvolat (retract). V jádru:
   materiální implikace může překvapit u přirozeného „jestliže".
5. **False negatives:** poctivá neúplnost — unparsed věty, INCOMPLETE po
   limitu, UNKNOWN při chybějící premise; nikdy se nevydávají za NE.
6. **UNKNOWN:** epistemické „nevím" — chybějící čtení atomu (K3), odlišené
   od doloženého záporu i od chyby (UnboundAtomError); INCOMPLETE je
   odlišený stav výpočtu, ne pravdivost.
7. **Konflikty:** obě strany zůstávají s proveniencí (`Conflict`), mřížka
   úrovní rozhoduje čtení; táž úroveň = karanténa (UNKNOWN + příznak),
   `explain_conflict` vydá obě strany; modely prozkoumají obě větve.
8. **Cykly:** forward — konečnost ground literálů ⇒ fixpoint terminuje;
   backward — množina cílů na cestě; vzájemná podpora odvozených se při
   retractu neudrží (well-founded přepočet).
9. **Explosion search space:** relevanční scope (uzávěr), K3 řezy
   constraintů a instancí při DFS, deterministické limity (`max_nodes`,
   `max_models`, `max_scope_atoms`, `max_rounds`, `max_derivations`,
   `max_atoms`) ⇒ INCOMPLETE, nikdy tichý špatný verdikt.
10. **Model enumeration:** DFS v kanonickém pořadí atomů nad scope;
    pinning doložených čtení; instance pravidel jako implikace; měřeno
    proti plné 2^n referenci.
11. **Protipříklady:** hledání modelu, kde tvrzení neplatí, je součást
    `classify_query` — protipříklad se vrací jako svědek (NECESSARY padá
    právě jeho nálezem).
12. **Nutnost závěru:** tvrzení platí ve všech modelech scope (žádný
    protipříklad) — `ModalVerdict.NECESSARY`; konzistence s K3 („TRUE ⇒
    NECESSARY") je testovaná vlastnost.
13. **Provenience:** každý fakt nese úroveň+evidenci; každá derivace
    premisy+pravidlo+jmenovky předpokladů; `why` skládá strom až
    k listům; serializace vše zachovává.
14. **Invalidace derivací:** `retract` = odebrání vlastní evidence +
    well-founded uzávěr podpory; tranzitivní zánik (INV-12); shoda
    s přepočtem od nuly testovaná.
15. **Závislost na LLM:** žádná. Systém LLM nepoužívá; architektura mu
    vyhrazuje roli navrhovače Assertions (INV-11) a čtenáře
    Explanation stromů — obě za validační cestou.
16. **Deterministické:** celé `cb_logic` i `cb_interpret` (stabilní klíče,
    kanonická pořadí, semínka). Nedeterminismus nezavádí ani most —
    jediný externí vstup je rozbor UDPipe (deterministický model).
17. **Nový typ relace:** `declare_relation(Relation(jméno, arita))` — data,
    žádný kód; interpretace je zakládá z lemmat automaticky.
18. **Nový constraint:** nové kardinality/výrazy jsou data; nový *druh*
    constraintu = nový frozen typ + `to_expression` + `satisfied_by`
    + `truth_partial` + křížový test shody obou čtení (CONSTRAINT_MODEL).
19. **Nový typ inference:** nová rozhodovací cesta se přidává za princip
    „měří se proti orákulu" (tabulka / naivní forward / plná enumerace);
    pohledy (Quine, Venn, …) jsou čtení téhož IR, ne nové motory.
20. **Nový, nikdy neviděný problém:** deklaruj relace a domény, zapiš
    fakta/pravidla/constrainty (ručně či dialogem přes cb_interpret),
    polož dotaz — truth/why, possible/necessary/impossible
    s protipříkladem, enumerace, why-not s chybějícími premisami.
    Přesně tak vznikly testy Bartlové a akceptační úloha § 59: **jen
    data, žádná změna enginu.**

## 3 · Definition of Done (zadání § 58) — kontrola

Analýza codebase ✓ (ARCHITECTURE_REVIEW) · dependency mapy ✓ (CURRENT/
TARGET_DEPENDENCIES) · cílová architektura ✓ · formální knowledge model ✓ ·
logická reprezentace ✓ · truth semantics ✓ · constrainty ✓ · obecná
inference ✓ · prostor modelů ✓ · possible/necessary/impossible ✓ ·
protipříklady ✓ · provenience ✓ · explainabilita ✓ · učení z dialogu ✓
(vč. persistence) · property testy ✓ · generativní testy ✓ · metamorfní
testy ✓ · nezávislé referenční modely ✓ (tři) · unseen benchmark ✓
(Bartlová + § 59) · anti-overfitting audit ✓ (tento dokument) · speciální
implementace demonstračních příkladů ✗ neexistují (§ 1 výše).
