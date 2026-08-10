# TEST_STRATEGY — jak se nová reasoning vrstva testuje

**Stav:** odpovídá implementaci (fáze 0–12).
**Rozsah:** `cb_logic`, `cb_interpret`, integrace v `cb_bond`; testy starších
modulů se nemění (jejich strategie popisuje README-MODULES a dokumentace modulů).

Zásada zadání §40/§60: klasické unit testy nestačí; důkazem generalizace je
kombinace vrstev níže. Vše `unittest`, spouštěno `./run-python -m unittest
discover -s <balík> -t .`; žádná náhoda bez semínka (SEED 328), žádné hodiny.

## 1 · Vrstvy testů

| vrstva | kde | co drží |
|---|---|---|
| jednotkové | `cb_logic/tests/test_{terms,expressions,semantics,provenance,constraints,knowledge,inference,retract,prove,modal,models,explain,serialize}.py`, `cb_interpret/tests/*`, `cb_bond/tests/test_logic.py` | chování každé komponenty vč. hlasitých chyb |
| property | `test_properties.py`, `test_inference_properties.py`, `test_models_properties.py` | algebraické zákony (dvojí negace, komutativita, absorpce, De Morgan, identity), K3 monotonie, monotonie inference bez negace, idempotence fixpointu, monotonie parciálního čtení kardinalit |
| generativní | `tests/generators.py` (výrazy), `tests/kb_generators.py` (báze), `random_constraint_kb` | náhodné vstupy se semínkem; engine pracuje nad strukturou, ne nad jmény |
| metamorfní | tamtéž + `test_acceptance.py` | přejmenování (§43), permutace pořadí (§40), irelevantní znalost (§44), permutace constraintů, kombinace transformací |
| referenční orákula | viz § 2 | produkce se měří proti nezávislé pomalé implementaci |
| unseen benchmarky | `test_bartlova.py` (13 úloh, 2014), `test_acceptance.py` (§59) | úlohy nevzniklé pro tento systém / vzniklé až po implementaci |

## 2 · Tři nezávislá orákula (zadání §41, G-36)

1. **Plná pravdivostní tabulka** (`semantics.truth_table`) — orákulum pro
   rozhodovací dotazy a pro ekvivalenci výrazů v property testech.
2. **Naivní forward** (`kb_generators.naive_forward_readings`) — množinové
   čtení bez derivací a optimalizací; shoda s `infer_forward` na 50
   náhodných bázích.
3. **Plná 2^n enumerace modelů** (`test_models_properties.reference_models`)
   — shoda s `enumerate_models` (včetně nesplnitelných a vícemodelových
   vzorků) na 30 náhodných constraint problémech.

Křížové vlastnosti mezi vrstvami: „K3 TRUE ⇒ NECESSARY" (fixpoint × modely
si nesmí odporovat — obdoba T-11); shoda `retract` s přepočtem od nuly.

## 3 · Pojistky proti vakuu (T-13)

Každý generativní test tvrdí, že jeho vzorek skutečně obsahoval jevy, které
hlídá: hluboké výrazy, negace, disjunkce, záporné literály v tělech,
nesplnitelné i vícemodelové problémy, netriviální počty ověřených případů
(`assertGreater(checked, …)`). Test, jehož podmínky nikdy nenastaly, spadne.

## 4 · Jazyková vrstva

Zemní pravdou interpretace jsou **zmražené rozbory skutečného UDPipe**
(`cb_interpret/tests/vzorky.py`, model cs_all-ud-2.17) — testy neběží proti
službě (politika § 13), ale ani proti vymyšleným stromům. Ekvivalent
renaming testu: přejmenování lemmat mění jen jména ve výstupu, ne strukturu.
`cb_bond/tests/test_logic.py` drží vlastní kopii vzorků (testy nesmí sahat
do testů cizího modulu) a testuje most včetně „restartu" (persistence).

## 5 · Determinismus

Táž báze + týž dotaz ⇒ týž výsledek včetně pořadí (stabilní klíče, DFS
v kanonickém pořadí); serializace je textově shodná mezi dvěma zápisy.
Confidence nikdy nevstupuje do logického výsledku (§48–49) — hlídá typová
struktura (Evidence.confidence není čteno žádnou rozhodovací cestou).

## 6 · Počty (k datu dokončení fáze 12)

787 testů původních modulů (beze změny) + 187 nových
(`cb_logic` 157 · `cb_interpret` 21 · `cb_bond/test_logic` 4 + akceptační 8
— minus překryv v discover) = **969 testů celkem, vše zeleně**. Přesné číslo
vrací `./run-python -m unittest discover -s . -p "test_*.py" -t .`.

## 7 · Co testy vědomě nekryjí

Lifecycle procesů (start/stop služeb) — jako dosud; výkonnostní stropy
(T-9) — limity jsou deterministické počty, čas se neměří; živý UDPipe —
kryto zmraženými vzorky + ručním protokolem.
