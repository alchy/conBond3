# ARCHITECTURE_REVIEW — revize architektury před stavbou obecného reasoning systému

**Stav:** fáze 0 (audit) zadání „obecný systém pro reprezentaci znalosti, učení a logický reasoning".
**Vzniká z:** auditu codebase k commitu `1bea15a` (čistý strom), větev `feature/general-reasoning`.
**Metoda:** čtyři nezávislé hloubkové průchody (reasoning jádro cb_bond · služba a dialog cb_bond ·
cb_field + cb_udpipe · infrastruktura a závislosti) + čtení veškeré koncepční dokumentace.
Každé klíčové tvrzení nese odkaz `soubor:řádek`.

**Hlavní závěr jednou větou:** conBond3 má výbornou provozní a měřicí infrastrukturu a velmi
kvalitní *návrh* reasoning systému (`README-ARCHITECTURE_OVERVIEW.md`), ale **implementovaný
systém dnes neobsahuje žádnou logickou inferenci** — je to skórovací vyhledávač odpovědí nad
korpusem. Formální vrstva (tvrzení, pravidla, pravdivost, constrainty, modely, provenience
odvození) musí vzniknout nová; existující kód poslouží jako jazykový vstup, retrieval
a provozní obal, nikoli jako reasoning jádro.

---

## 1 · Současná architektura

Pět balíků v jednom repozitáři, jeden sdílený `.venv` (Python 3.11, vstup výhradně přes
`./run-python`), data mimo repozitář pod jediným kořenem `data_root`
(`/Users/j/Projects/conBondCorpus`).

| modul | druh | porty | co dělá |
|---|---|---|---|
| `cb_logger` | služba | 42100–42102 | strukturovaný log jako měření (Level × Result), kukátka |
| `cb_udpipe` | služba | 42200–42201 | rozbor českých vět vlastní instancí UDPipe 2 + RobeCzech, trvalá cache |
| `cb_field` | knihovna | (42300 rezervováno) | věta jako matice vážených aktivací nad registrem vertikál |
| `cb_bond` | služba | 42400–42401 | graf faktů, párování, odpověď, dialog, čtyři okna viewBase |
| `cb_config` | knihovna | — | načtení a validace konfigurace (jsonschema, Draft 7) |

Ustálený vzor služby: `service.py` (doména bez I/O) + `api.py` (REST) + `client.py` +
`control.py` (lifecycle) + `config.schema.json`. Obě tváře (v procesu / přes síť) hlídá
zkouška parity `T-K3`. Zdravotní stav rozlišuje „běžím" od „umím odpovídat" (`degraded`),
chyby jsou typované, „nemá odpověď" se nikdy neslévá s „nepodařilo se odpovědět".

Vedle kódu existuje **návrhový dokument `README-ARCHITECTURE_OVERVIEW.md` (v2.2)** — plán
systému s invarianty INV-1…14, logickými schopnostmi C-1…C-14, mřížkou provenience a konceptem
„pohledů". Je to hypotéza, nikoli stav: z reasoning části není implementováno nic.

## 2 · Hlavní komponenty

**cb_udpipe:** `Upstream` (jediný mluvčí s UDPipe 2; segmentace bez sítě, dorozbor bez
tokenizace), `retokenize` (5 pravidel z konfigurace, fingerprint pravidel = verze tokenizéru),
`ParseCache` (JSONL, klíč = NFC(věta) × model × fingerprint), `UdpipeClient` (shodná tvář se
službou). Vrací **všech deset sloupců CoNLL-U** včetně `head`, `deprel`, `feats`
(`cb_udpipe/conllu.py:27-61`) — bezztrátově, trvale.

**cb_field:** `SentenceField` (matice tokeny × vertikály, `cb_field/field.py:91-213`),
`VerticalRegistry` (append-only adresní prostor os + vážené vazby −1…+1, snapshot/restore,
save/load, `cb_field/registry.py`), `Corpus`/`corpusfile` (fixované korpusy s etalonovými
otázkami), pravidla aktivací (`cb_field/service.py:307-438` — LEM/WORD/ANCHOR/QANCHOR/
Polarity/SUBPOS…).

**cb_bond:** `KnowledgeGraph` (uzly `UPOS:lemma`, hrany = přímé závislosti, provenience
text/dictionary/dialog, `cb_bond/graph.py`), `GraphRecall` (předvýběr vět šířením záře),
`Matcher` (skóre = meet + cover + topic + given + fit + spectral, `cb_bond/matcher.py:498-526`),
`AnswerField` (čtyři čtení téhož pole, gaussovské vrcholy), `Responder` (outcome + mezery
s přesnou nulou), `BondService`/REST/okna; mimo provoz: `RelationMiner`, `ContrastiveTrainer`,
`PromotionCycle`, `SpectralMember`, `BenchmarkProtocol`, `DefinitionResolver`, `QuestionExpander`.

**cb_logger:** `LogRecord` (dvě osy: Level info/debug × Result ok/empty/skipped/error —
`empty` a `error` se nesmí slít, `cb_logger/record.py:40-55`), objektový proud, asynchronní
klient se spoolem, kukátka (SSE), souhrn přežívající restart.

**cb_config:** jediná funkce `load()` (schéma → checks → rozvinutí cest → `_meta` s otiskem).

## 3 · Odpovědnosti

| vrstva | odpovědnost | kdo |
|---|---|---|
| rozbor | text → tokeny s morfologií a závislostmi | cb_udpipe |
| kódování | tokeny → matice aktivací nad společným registrem | cb_field |
| „znalost" | graf sousedství + vazby registru | cb_bond.graph + cb_field.registry |
| odpovídání | otázka → kandidáti se skóre a rozkladem | cb_bond.matcher/answer |
| dialog | mezera → doplnění kontextu | cb_bond.dialog |
| provoz | lifecycle, REST, okna, log, konfigurace | control/api/window + cb_logger + cb_config |

Rozlišení **otázka × sdělení není nikde v kódu** — rozhoduje volající (REST cesta
`/v1/ask` × `/v1/context`, v konzoli prefix `:context`). Sémantická interpretace vstupu
neexistuje.

## 4 · Datové struktury

| struktura | tvar | poznámka |
|---|---|---|
| `Token` | frozen dataclass, 10 sloupců CoNLL-U | jediné místo se zachovanou větnou strukturou |
| `SentenceField` | matice float32 (tokeny × vertikály), váhy −1…+1 | `head` se do matice **nedostane** (`cb_field/service.py:326-327` ho uchová, `activations()` neemituje) |
| `VerticalRegistry` | append-only `klíč→index`, `_links: (src,dst)→float`, custom sloty | dvě verze (osa/vazby), atomický save/load `format_version: 2` |
| `KnowledgeGraph` | uzel `"UPOS:lemma"`, hrana `(src,dst,deprel,weight,source)` | `weight` je vždy 1.0; `deprel` se ukládá, ale nikdy nečte; sousedství neorientované (`cb_bond/graph.py:238-241`) |
| `MatchResult`/`ScoreCandidate` | kandidáti s rozkladem skóre (součet členů = skóre) | rozklad je provenience *rankingu*, ne odvození |
| `LogRecord` | frozen, Level × Result, `trace` povinně viditelná i jako `None` | v produkci 98,7 % záznamů bez `trace` |
| korpusový soubor | JSON `format_version:1`, bloky vět + etalonové otázky | měřicí infrastruktura hotová |

Neexistuje žádná struktura pro: tvrzení (predikát + argumenty), pravidlo, logický výraz,
pravdivostní hodnotu, constraint, model, předpoklad, derivaci.

## 5 · Dependency graph

Podrobně v `CURRENT_DEPENDENCIES.md`. Souhrn (produkční importy, ověřeno grepem):

```
cb_bond ──→ cb_field ──→ cb_udpipe
   │            │            │
   └────────────┴────────────┴──→ cb_logger ──→ cb_config
```

Směr sedí s deklarací v README; cizí *služby* se volají výhradně klientem. Výjimka:
**cb_field nemá klientskou hranici** (je to knihovna bez služby) a cb_bond do něj importuje
i mimo `__init__.py` (`cb_bond/matcher.py:48` `from cb_field.service import Representation` —
přesně tvar, který `README-MODULES.md:391-393` zakazuje). Nejhorší nález:
`cb_bond/tests/test_graph.py:214` importuje fixturu z **testů** cizího modulu.

## 6 · Datové toky

**Dotaz:** `POST /v1/ask` → validace → `BondService.ask` → pole otázky **nad registrem
korpusu** → `Responder.reply` (match + coverage) → *znovu* match + coverage v service
(`cb_bond/service.py:169-171` — dvojitá práce) → kandidátní věty + rozklad + osy → JSON.

**Sdělení:** `POST /v1/context` → `append_context` → věta do korpusu (zdroj `dialog`) + hrany
do grafu → `invalidate()` → přírůstky v odpovědi. **Jen RAM — restart vše zahodí** (persistence
registru navržená a nezapojená, § 13/P5).

**Stavba:** korpusy z `data_root` → parse (cache) → `Corpus` + registr → `KnowledgeGraph` →
Matcher. Učení/promoce/těžba vztahů do stavby ani provozu zapojené nejsou — jen skripty.

**Rozbor:** text → segmentace (bez sítě) → retokenizace → cache → dorozbor po dávkách →
`ParseResult`.

## 7 · Silné vazby (coupling)

1. **Otázka musí být pole nad týmž registrem** jako korpus — jinak jsou osy nesouměřitelné.
   Implicitní kontrakt předávaný parametrem (`registry=corpus.registry`).
2. **`graph._sentences[position]` ↔ pozice v korpusu** — poziční index bez kontroly;
   `GraphRecall` předpokládá shodu délek, při rozejití `IndexError` (`cb_bond/recall.py:128-137`).
3. **Sémantická maska prefixů** (`cb_bond/matcher.py:66-67`) — cb_bond zná nazpaměť slovník
   os definovaný v cb_field; změna prefixu v jednom modulu tiše změní chování druhého.
4. **Poziční kontrakt pražského tagu** — `xpos[10] == "N"` (`cb_field/service.py:376`),
   `xpos[:2]` jako SUBPOS; vazba na konkrétní tagset v kódu.
5. **`DefinitionResolver` pozná definici podle váhy 0.7** (`cb_bond/dialog.py:143-144`) —
   kolizní heuristika nahrazující ztracený typ relace (§ 13/P3).

## 8 · Circular dependencies

**Mezi moduly žádné nejsou** (ověřeno importy). Uvnitř cb_field je potenciální cyklus
`registry ↔ service` rozbit líným importem (`cb_field/registry.py:66`).
`README-MODULES.md:419-424` slibuje AST test hlídající směr závislostí — **neexistuje**;
graf je dnes hlídán jen dokumentací.

## 9 · Duplicity

| duplicita | kde | verdikt |
|---|---|---|
| servisní kostra `api.py`/`control.py` 3× | shodných ~60 řádků api, ~10 primitiv control | kandidát na sdílenou abstrakci (vzor: úspěšné sloučení do `cb_config`) |
| `_logovatko()` doslovně 2× | `cb_udpipe/control.py:356` × `cb_bond/control.py:300` | existuje `cb_logger.from_config` právě proto — nepoužívá se |
| `ServiceUnavailable` 3× nezávisle | tři klienty | `except` chytí jen jednu — past pro orchestraci |
| konstanty v kódu i konfiguraci | `min_stem`, `seed 328` (3×), `sigma`, `limit 328`, `START_TIMEOUT_S` 2× | konfigurace se validuje, kód čte vlastní defaulty (§ 13/P6) |
| dvě implementace šíření | hustá `registry.spread` (870 MB při n=14 748) × řídký `LinkOperator` v matcheru | druhá vznikla, protože první neškáluje |
| dvojité párování na dotaz | `service.ask` volá match+coverage po `reply()`, které je už volalo | 2× práce na každém dotazu |

DRY se zde nemá aplikovat mechanicky — kostra služeb je „shoda tvaru" placená vědomě;
skutečný problém jsou rozešlá pojmenování (`_send_json` × `_json`) a konstanty na dvou místech.

## 10 · Problematické hranice abstrakcí

1. **cb_field stojí mimo infrastrukturu** — bez konfigurace, bez logování, port vieweru
   natvrdo (`cb_field/viewer.py:41-42`), `run/` a `tmp/` v repozitáři. Extrakční vrstva je
   v měření slepé místo.
2. **Mrtvá polovina konfiguračního schématu cb_bond** — `module.training/promotion/relations/
   state`, `question_patterns`, `seed`, `sigma`, `request_timeout_s`, `max_request_bytes` se
   validují a nikdy nečtou; páky žijí jako defaulty v konstruktorech. Přesný opak deklarace
   schématu (`cb_bond/config.schema.json:4`).
3. **Odpojené komponenty** — `RelationMiner`, `DefinitionResolver`, `QuestionExpander`,
   trénink, promoce: hotové, otestované, v provozní cestě nevolané.
4. **Typ relace se ztrácí v registru** — definice i derivace končí jako holý skalár
   (`cb_bond/relations.py:110`).
5. **Jazyková data v kódu** — kotevní tabulky, deiktika, tázací tvary
   (`cb_field/service.py:206-290`) proti zásadě „v kódu ani slovo přirozeného jazyka"
   (README-ARCHITECTURE_OVERVIEW kap. 6); cb_udpipe má zkratky správně v konfiguraci.
6. **Stopa (`trace`) se nepředává** — koncepce loggeru na ní staví řetěz doložení, produkce:
   850 930 z 862 261 záznamů bez ní.

## 11 · Současný knowledge model

Znalost žije ve **dvou nezávislých reprezentacích, které se nikdy nepotkají**:

- **Graf faktů** (`cb_bond/graph.py`): uzly = obsahová slova `UPOS:lemma`, hrany = přímé
  závislostní sousedství s proveniencí zdroje. Žádný pojem výroku — věta je množina klíčů
  uzlů; orientace, role a počty se agregují pryč. „Jan pokřtil Ježíše" a „Ježíš pokřtil Jana"
  jsou v sousedství nerozlišitelné.
- **Registr + pole** (`cb_field`): věta = matice vážených aktivací; sémantika nesená prefixy
  os; vazby mezi osami jsou netypované skaláry.

**Kde se ztrácí struktura (klíčové zjištění auditu):** UDPipe dodává úplný závislostní strom,
negaci (`Polarity`, `PronType=Neg`), koordinace (`conj`/`cc`), podřadicí vztahy (`mark`/`advcl`)
i kvantifikátory (`PronType=Tot/Ind/Neg` na DET). Extrakce v `activations()` zahodí `head`;
`semantic_bag` (`cb_bond/matcher.py:70-80`) pak sečte řádky do jednoho pytle. **Propoziční
struktura je v datech přítomna jako token, ale nikde jako vztah** — negace je lokální bit bez
dosahu, „a" × „nebo" jsou dvě lexikální osy bez strukturního důsledku, implikace nerozliší
antecedent od konsekventu. Evidence × pravda, předpoklad, hypotéza, konflikt: nereprezentováno.

## 12 · Současný reasoning model

**Není to inference, je to ranking.** Celá cesta: předvýběr vět šířením záře po grafu
(depth=2, skóre věty = max jasu uzlů) → saturace vektorů `tanh(v + v·L)` → součet šesti
skalárních členů na kandidáta (token) → sort → gaussovské čtení vět → dva prahy (θ, ε) nad
hotovým pořadím. Nosný člen je **postih `given = −3.0`** (bez něj přesnost 0/30) — systém
vítězí penalizací ozvěny otázky, ne odvozením.

Nejblíž „logice" je: outcome `{answer, ask, silent, needs_context}` (epistemický stav
odpovědi, ne pravdivost tvrzení), mezera jako **přesná nula** pokrytí (čistá hranice
neznám × znám slabě) a algebra `MatchResult.__and__/__or__/__invert__` — která je ale nad
skóre, ne nad tvrzeními, a má vady (`__or__` vrací fakticky průnik nosičů,
`cb_bond/matcher.py:219-230`; `__invert__` nepřeřazuje; kompozice zahazuje rozklad).

Detekce rozporu, dedukce, pravidla s proměnnými, kvantifikace, enumerace modelů,
protipříklady, invalidace odvozeného: **nic z toho neexistuje.** V závislostech není žádný
solver (žádné z3/pysat/ortools/sympy/networkx — ověřeno v `requirements.txt` i `.venv`).

---

## 13 · Zásadní problémy

### P1 · Propoziční struktura se ztrácí mezi rozborem a polem

```text
CURRENT        UDPipe vrací úplný strom (head, deprel, feats); expand_token head uchová,
               activations() ho neemituje; semantic_bag sečte řádky do pytle.
PROBLEM        Negace, koordinace, implikace a kvantifikace existují jen jako lexikální
               stopy bez argumentů. Z pole nelze rekonstruovat, KDO CO tvrdí o KOM.
CONSEQUENCE    Nad současnou reprezentací nelze postavit žádnou logickou inferenci —
               chybí jí vstup. Jakýkoli „reasoning" by byl heuristika nad slovy.
ALTERNATIVES   (a) protáhnout head do matice pole (další osy) — zachrání adresu, ne
               propozici; (b) nová extrakční vrstva strom → propozice/hrany (plán
               README-EXTRAKCNI_VRSTVA §3 NAPLN_SLOTY, SEAM-6 Hranovač); (c) obejít pole
               a stavět propozice přímo z ParsedSentence.
RECOMMENDATION (b)+(c): samostatný krok „věta → kandidátní tvrzení" nad ParsedSentence
               (zdroj je bezztrátový a trvale v cache), nezávislý na poli. Pole zůstává
               pro retrieval.
MIGRATION      Fáze 9 zadání (learning z dialogu) na tom stojí; stavět po fázích 1–2
               (formální model + IR), aby extrakce měla cílový typ, do kterého míří.
```

### P2 · Neexistuje formální vrstva tvrzení, pravidel a pravdivosti

```text
CURRENT        Reasoning = skórování a ranking (§ 12). Žádné TruthState, Rule, Expression,
               Constraint, Model, Derivation.
PROBLEM        Zadání žádá dedukci, negaci, rozpory, possible/necessary/impossible,
               protipříklady, provenienci odvození. Nic z toho nelze „dodělat" do
               matcheru — je to jiný výpočetní model.
CONSEQUENCE    Bez nové vrstvy by se logika falšovala skórem (přesně to, co zadání §47
               zakazuje LLM — a platí to i pro vlastní numeriku).
ALTERNATIVES   (a) externí solver (z3/pysat) za švem; (b) vlastní jádro (výroková logika
               + constrainty + enumerace) se solverem případně později za týmž švem;
               (c) ohnout matcher — nepřipadá v úvahu.
RECOMMENDATION (b): vlastní čisté jádro bez závislostí (stdlib), deterministické, s pomalou
               referenční implementací (plná pravdivostní tabulka / naivní enumerace) jako
               orákulem v testech. Šev na solver nechat otevřený (SEAM), ale nezačínat
               závislostí, kterou politika repozitáře schvaluje jmenovitě.
MIGRATION      Fáze 1–8 zadání; nový balík (knihovna po vzoru cb_field/cb_config, služba
               až podle potřeby integrace).
```

### P3 · Typ vztahu se ztrácí; znalost je netypovaná

```text
CURRENT        Definice i derivace končí jako skalár v registru (relations.py:110);
               DefinitionResolver typ rekonstruuje podle váhy 0.7 (dialog.py:143-144).
               Hrany grafu nesou deprel, který nikdo nečte; váha je konstantní 1.0.
PROBLEM        Nelze rozlišit „je-to" od „souvisí-s", implikaci od podobnosti. Ontologie
               (svaz podtříd pro C-10/C-13) nemá kam vzniknout.
CONSEQUENCE    Jakékoli pravidlo nad „vztahy" by hádalo, co hrana znamená.
ALTERNATIVES   (a) přidat typ do registru vazeb; (b) typované relace až ve formální vrstvě
               (P2), registr nechat rankingový.
RECOMMENDATION (b) — nerozšiřovat rankingový registr o sémantiku, kterou neunese; typ
               patří k tvrzení ve formálním modelu, s proveniencí.
MIGRATION      Fáze 1 (knowledge model) definuje Relation/Fact; miner definic se přepojí
               tak, aby vedle skalární vazby emitoval i typované tvrzení.
```

### P4 · Negace a rozpor jsou neviditelné

```text
CURRENT        Polarity=Neg je jeden sčítanec ve vektoru; kosinus „Petr přišel" ×
               „Petr nepřišel" ≈ 1. Rozpor nemá reprezentaci ani detekci.
PROBLEM        INV-5 („spor se hlásí, nepřepisuje") nelze dodržet, když spor není vidět.
CONSEQUENCE    Konfliktní znalost se tiše slije; dialogová oprava faktu nemá jak fungovat.
ALTERNATIVES   (a) záporné váhy os (existuje u deiktik) — kosmetika; (b) polarita jako
               vlastnost tvrzení ve formální vrstvě + explicitní stav konfliktu (BOTH).
RECOMMENDATION (b): pravdivostní sémantika TRUE/FALSE/UNKNOWN + reprezentace konfliktu
               s proveniencí obou stran (fáze 3), detekce konfliktu při zápisu znalosti
               (fáze 9).
MIGRATION      Nezávislé na retrieval vrstvě; napojení na dialog až po P1.
```

### P5 · Znalost z dialogu je efemérní; persistence navržená a nezapojená

```text
CURRENT        append_context zapisuje jen do RAM; module.state.* (povinné ve schématu)
               nikdo nečte; registry.save/load hotové v cb_field, nevolané; adresáře
               persistent-registry/ prázdné. Závazné pořadí načtení stavu je sepsáno
               (docs/navrh-sluzby.md:500-517) a neimplementováno.
PROBLEM        „Učení z dialogu" nepřežije restart; nelze budovat trvalou znalost.
CONSEQUENCE    Fáze 9 zadání (dialogue learning) nemá kam ukládat; jakákoli provenience
               by se ztrácela s procesem.
ALTERNATIVES   (a) dodělat zapojení registry.save/load dle zapsaného rozhodnutí;
               (b) novou persistenci až pro formální vrstvu a registr nechat efemérní.
CONSEQUENCE    (a) je malá, oddělená oprava dluhu; (b) by nechala dnešní funkci rozbitou.
RECOMMENDATION Obojí, odděleně: (a) jako samostatná oprava stávajícího dluhu; formální
               vrstva má vlastní persistenci (append-only žurnál tvrzení s proveniencí),
               protože sémantiku znalosti nesmí ztrácet (§ zadání 54).
MIGRATION      (a) kdykoli; persistence formální vrstvy ve fázi 1 (model) + 8 (provenance).
```

### P6 · Konfigurace deklaruje, kód si žije po svém

```text
CURRENT        Mrtvé sekce schématu (§ 10 bod 2); konstanty duplicitně v kódu
               (min_stem, seed, sigma, limit); odpojené komponenty (§ 10 bod 3).
PROBLEM        „Páky žijí v konfiguraci" platí jen zčásti; měření se nedá řídit deklarativně.
CONSEQUENCE    Dvě měření se mohou lišit, aniž jde poznat čím (přesně to, čemu má schéma
               bránit); noví čtenáři kódu dostávají lživou mapu.
ALTERNATIVES   (a) dočíst konfiguraci všude; (b) mrtvé sekce ze schématu vyřadit.
RECOMMENDATION Pro nový kód: pravidlo „klíč ve schématu = klíč čtený kódem" od prvního dne
               (registr prahů dle kap. 29 návrhu). Pro starý: rozhodnout u každé sekce
               zvlášť (training/promotion → dočíst při zapojení; state → P5).
MIGRATION      Průběžně; nová vrstva nesmí vzor opakovat.
```

### P7 · Řetěz doložení dnes nejde poskládat (trace 1,3 %)

```text
CURRENT        Koncepce loggeru staví na trace; produkce: 850 930 / 862 261 bez ní.
PROBLEM        Vysvětlitelnost je deklarovaná, ale neměřitelná; průchod dotazu nejde
               zrekonstruovat z logu.
CONSEQUENCE    Pro reasoning systém s povinnou explanací (zadání §35–36) je to slepá ulička
               už na úrovni infrastruktury.
ALTERNATIVES   (a) protáhnout trace vstupními body (service.ask ji má razit) — zapsaný
               nedodělek bodu 7 návrhu služby; (b) provenience nezávisle na logu.
RECOMMENDATION Obojí: provenience odvození je datová struktura (derivační graf, fáze 8),
               ne log; trace se dotáhne jako provozní stopa (levné, zapsané, hotový klient).
MIGRATION      (a) malá oprava v cb_bond._oznam + vstupních bodech; (b) fáze 8.
```

### P8 · Riziko overfittingu měření

```text
CURRENT        Etalon 30 zodpověditelných otázek; hyperparametry laděné na témž vzorku;
               dvě otázky uniklé z etalonu do supervize (přiznáno); zmražené přejímky
               vázané na konkrétní korpus mimo repozitář; ramena benchmarku nejsou
               nezávislá (sekvenční mutace stavu).
PROBLEM        Zadání §60 žádá důkaz generalizace; dnešní aparát měří stabilitu jednoho
               korpusu, ne obecnost.
CONSEQUENCE    Nové schopnosti by se snadno „doladily" na 30 bodů — přesný anti-vzor §2.
ALTERNATIVES   (a) rozšířit etalon; (b) generátor náhodných problémů + metamorfní testy
               + referenční orákulum pro novou vrstvu (zadání §40–45).
RECOMMENDATION (b) pro reasoning vrstvu od prvního dne (property-based/generativní testy;
               hypothesis dnes v prostředí není — rozhodnout: schválená dev závislost,
               nebo vlastní generátor nad stdlib); (a) nezávisle pro retrieval.
MIGRATION      TEST_STRATEGY.md ve fázi 1; unseen benchmark až po implementaci (fáze 12).
```

---

## 14 · Návrh cílové architektury

Zadání i `README-ARCHITECTURE_OVERVIEW.md` konvergují k témuž tvaru; audit ho potvrzuje
s jednou korekcí: **retrieval (dnešní cb_bond) není reasoning a nemá se jím stát.** Je to
jeden ze zdrojů kandidátní znalosti a záložní odpovídací cesta — v roli, kterou návrh
přisuzuje statistice: **navrhuje, nikdy nerozhoduje o pravdivosti (INV-11).**

```text
                    DIALOG / KORPUS (text)
                            │
              cb_udpipe (beze změny: bezztrátový rozbor)
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
  cb_field (beze změny:                NOVĚ · INTERPRETACE
  pole → retrieval)                    strom → kandidátní tvrzení
        │                              (propozice, negace, spojky,
        │                               kvantifikátory, pravidla)
        │                                       │
  cb_bond matcher                      NOVĚ · FORMÁLNÍ JÁDRO (čistá knihovna, stdlib)
  (kandidáti, skóre)                   ├─ knowledge model: Entity/Relation/Fact/
        │                              │  Assertion/Rule/Assumption/Evidence
        │      návrhy ─────────────────►  (vše s proveniencí, evidence ≠ pravda)
        │                              ├─ logická IR: AST výrazů (NOT/AND/OR/
        │                              │  IMPLIES/EQUIV), CNF-pohled, tabulka-pohled
        │                              ├─ truth semantics: T/F/UNKNOWN (+konflikt)
        │                              ├─ constrainty: kardinality, exclusion, …
        │                              ├─ inference kernel: forward/backward,
        │                              │  fixpoint, meze zdrojů
        │                              ├─ model space: enumerace konzistentních
        │                              │  modelů; possible/necessary/impossible;
        │                              │  protipříklady; meta-dotazy
        │                              └─ provenance: derivační graf, invalidace
        │                                       │
        └───────────────┬───────────────────────┘
                        │
              cb_bond Responder / QueryPlanner (rozšířený)
              formální odpověď má přednost; retrieval je záloha;
              odpověď nese druh + řetěz doložení
                        │
              vysvětlení (z derivačního grafu) → REST /v1 → okna
```

Zásady převzaté z návrhu a potvrzené auditem:

- **Jedno IR, více pohledů** (zadání §33–34 = kap. 20 návrhu): pravdivostní tabulka, Vennův
  diagram, šipkový diagram i zebra tabulka jsou čtení téhož modelu, ne samostatné motory.
  Zdánlivý rozpor „Booleovu algebru neděláme" (kap. 41) × zadání §13–16 rozpor není: kap. 41
  odmítá *druhý kalkul* (přepisovací algebru jako alternativní metodu), zadání žádá
  *strukturální reprezentaci výrazů a jejich evaluaci* — to je C-3/C-4 + tabulka jako pohled
  a orákulum. Implementujeme jedno jádro; algebraické zákony (§14) jsou testy nad ním, ne
  druhý engine.
- **Kvantifikátory** (zadání §17): rozsah = výroková logika + třídy/kvantifikované výroky
  nad konečnými doménami (C-13), ne plná predikátová logika. Přesná hranice bude
  v LOGIC_SEMANTICS.md včetně toho, jak systém odmítne předstírat víc.
- **Pomalá referenční implementace jako orákulum** (G-36, zadání §41) od prvního dne.
- **Determinismus:** stabilní klíče při shodě, žádný čas/náhoda bez semínka; confidence
  odděleno od logického statutu (zadání §48–49).
- **Hranice vrstev** (zadání §50): jádro bez závislosti na NLP — dostává hotová tvrzení;
  interpretace je klient jádra. Kód jádra anglicky, jazyková data v profilech (poučení
  z § 10 bodu 5).

Otevřené k rozhodnutí během fáze 1 (zapíše se do dokumentace, ne do hlavy): jméno a umístění
nového balíku (pracovně `cb_logic` — knihovna po vzoru cb_config, služba až bude-li třeba);
zda hypothesis jako schválená dev závislost; formát persistence formální vrstvy.

## 15 · Migration strategy

Po etapách zadání §55, bez přepisování retrieval vrstvy:

| fáze | co vznikne | dotčené stávající |
|---|---|---|
| 0 | tento dokument + CURRENT_DEPENDENCIES.md | — |
| 1–2 | `cb_logic`: knowledge model + IR výrazů; KNOWLEDGE_MODEL.md, LOGIC_SEMANTICS.md | nic |
| 3–5 | truth semantics, constrainty, inference kernel; referenční orákulum; CONSTRAINT_MODEL.md, INFERENCE_ENGINE.md | nic |
| 6–8 | model space, possible/necessary/impossible, protipříklady, derivační graf; MODEL_REASONING.md, PROVENANCE.md | nic |
| 9 | interpretace: ParsedSentence → kandidátní tvrzení; validace, konflikt, update s proveniencí | cb_udpipe jen čtením; dialog cb_bond dostane druhou cestu vedle append_context |
| 10 | explanation z derivačního grafu | Responder: formální odpověď má přednost |
| 11 | integrace: REST rozšíření, okna, persistence | cb_bond service/api; oprava P5 (registr) nezávisle |
| 12 | generátor problémů, metamorfní testy, unseen benchmark, GENERALIZATION_AUDIT.md | — |

Zásady migrace: (1) žádná změna chování stávající odpovídací cesty bez měření na etalonu;
(2) nová vrstva se zapojuje **vedle**, ne místo — mlčí-li formální cesta, odpovídá retrieval
jako dnes; (3) opravy dluhů (P5 persistence, P7 trace, vady z přílohy A) jako oddělené,
malé commity mimo stavbu nové vrstvy; (4) každý řez odkazuje na INV-n / P-n, kvůli kterému
vznikl.

---

## Příloha A · Vady nalezené auditem (mimo hlavní problémy)

Kandidáti na samostatné malé opravy; nic z toho neblokuje fázi 1.

1. `cb_bond/scripts/protokol.py:21-24` a `scripts/rozklad-skore.py:26-28` — **SyntaxError**
   (import vložený doprostřed víceřádkového importu); po opravě by navíc selhaly na importu
   jmen mimo zúžené `__all__`. Měřicí protokol A–F dnes nejde spustit.
2. `cb_bond/matcher.py:219-230` — `MatchResult.__or__` vrací průnik nosičů (týž `_spoj` jako
   AND, kandidáty bez protějšku zahazuje); test pro OR neexistuje.
3. `cb_bond/matcher.py:204-210` — `__invert__` nepřeřazuje kandidáty; `_spoj` zahazuje rozklad.
4. `cb_bond/training.py:283,367` — čte `answer_position`, který v žádném JSONL supervize není;
   preferovaná větev je mrtvá, vždy jede proxy „věta obsahuje lemma".
5. `cb_bond/dialog.py:96` — `needs_context` maskuje `ask`; s `epsilon=0.0` v provozní
   konfiguraci navíc `ask` nemůže vzniknout vůbec (`matcher.py:536`).
6. `cb_bond/service.py:169-171` — dvojité párování na každý dotaz.
7. `cb_bond/api.py:117-127` — `max_request_bytes` se nevynucuje; víceslovný odstavec
   v `/v1/context` skončí 500 místo 400 (`cb_field/field.py:148-151`).
8. `cb_bond/stack.py:199` — `log.info(zprava, source=…)`: podpis, který `LogClient` nezná;
   dnes neškodné (log se nepředává), tatáž chyba už jednou zdokumentovaná jinde.
9. `cb_field/service.py:230` — `NEGATIVE_DEICTICS` obsahuje „nikam"/„nijak", které nemají
   kotvu v `DEICTIC_ANCHORS` — nedostanou ji nikdy.
10. `cb_field/service.py:495-500` — pro token bez tagů vznikne vertikála `WORD=None:None`
    (a `UPOS=None`), zapsaná do append-only registru natrvalo.
11. `cb_udpipe/service.py:298-315` — věta bez decimálního `sent_id` tiše zmizí z výsledku
    (není ani ve `skipped`).
12. `cb_logger/config.py:100-101` — konfigurační soubor se čte 6× místo 1×.
13. Drift dokumentace: `requirements.txt` odkazuje na neexistující `cb_bond/graphview.py`
    a tvrdí „numpy jen v cb_field"; tabulka schválených závislostí v README-MODULES uvádí
    jen jsonschema; `cb_config/README.md` uvádí 18 testů (je 19) a popisuje odstraněný
    validátor; `viewbase` bez pinu verze.
14. Chybí slíbený AST test na směr závislostí (README-MODULES.md:419-424); přímé importy
    do vnitřku cb_field (§ 5); `cb_bond/tests/test_graph.py:214` importuje fixturu z testů
    cizího modulu.
15. Mrtvý kód: `matcher.py:48` nepoužitý import `Representation`… vlastně používaný typ,
    ale importovaný obchvatem; `matcher.py:276` `_norms` počítané a nečtené;
    `spectral.py:109-118` `score()` bez volajícího; `console.py:25` `PROMPT`;
    `client.py:83` `self.api`; `IncompatibleApi` v cb_bond se nikdy nevyhazuje.

## Příloha B · Co se z dnešního systému přebírá do nové vrstvy

- **Kázeň rozkladu**: výsledek = součet pojmenovaných členů; v reasoning vrstvě obdobně —
  závěr = derivace rozložitelná na premisy a pravidla.
- **Přesná nula jako „neznám"** (× „znám slabě") — vzor pro UNKNOWN oddělené od confidence.
- **Provenience zdroje** (text/dictionary/dialog) na každé hraně — rozšíří se na mřížku
  provenience (kap. 14.3 návrhu).
- **Snapshot/restore + „jediná horší metrika vrací celek"** — vzor pro invalidaci derivací
  a experimentální vrstvu.
- **Result `empty` ≠ `error`** v loggeru — přesně rozlišení, které potřebuje „nevím" ×
  „selhal jsem" v odpovědích.
- **Vzor modulu** (service/api/client/control/schema + parita T-K3) a měřicí infrastruktura
  korpusů s etalony.
- **Zavržené cesty** (`cb_bond/docs/zadani.md:769-771`) — nezkouší se znovu.
