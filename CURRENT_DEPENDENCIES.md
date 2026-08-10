# CURRENT_DEPENDENCIES — skutečné závislosti k commitu 1bea15a

Ověřeno grepem importů v produkčním kódu (bez testů a skriptů, není-li řečeno jinak).
Formát dle zadání §51: komponenta → závislost → důvod → směr/mechanismus.
Stav po stavbě reasoning vrstvy (cb_logic, cb_interpret): `TARGET_DEPENDENCIES.md`.

## 1 · Graf mezi moduly

```
cb_bond ──→ cb_field ──→ cb_udpipe
   │            │            │
   └────────────┴────────────┴──→ cb_logger ──→ cb_config
```

Žádný cyklus. Žádná hrana proti směru vrstev. Sdílené moduly (`cb_logger`, `cb_config`)
neimportují z nesdílených.

## 2 · Tabulka závislostí

| komponenta | závislost | důvod | směr / mechanismus |
|---|---|---|---|
| cb_config | jsonschema (externí) | validace Draft 7 | import (`cb_config/loader.py:28`) |
| cb_logger | cb_config | načtení vlastní konfigurace | import (`cb_logger/config.py:19-21`) |
| cb_udpipe | cb_config | konfigurace | import (`cb_udpipe/config.py:19-21`) |
| cb_udpipe | cb_logger | provozní log služby | **klient** `LogClient`, líný import, výpadek nepadá (`cb_udpipe/control.py:377-381`) |
| cb_udpipe | UDPipe 2 + RobeCzech (vendor) | rozbor | **vlastní proces** vedle sebe; tensorflow/transformers importuje jen vendor |
| cb_field | cb_udpipe | typ `Token`; CLI validace korpusu | import typu (`cb_field/service.py:18`); **klient** `UdpipeClient` líně (`cb_field/corpusfile.py:220`) |
| cb_field | numpy (externí) | matice vah float32 | import |
| cb_bond | cb_field | pole, registr, korpusy | **přímý import, bez klienta** — cb_field službu nemá (`cb_bond/service.py:27`, `matcher.py:48`, `control.py:428`) |
| cb_bond | cb_udpipe | rozbor otázek a korpusu | **klient** `UdpipeClient` (`cb_bond/control.py:296`) |
| cb_bond | cb_logger | provozní log | **klient** `LogClient`, degradace bez pádu (`cb_bond/control.py:300-330`) |
| cb_bond | cb_config | konfigurace | import (`cb_bond/config.py:28-30`) |
| cb_bond | numpy (externí) | matcher/answer/spectral | import — **v rozporu s deklarací** `requirements.txt:31` („jen cb_field") |
| cb_bond | viewbase (externí, bez pinu) | okna 42401 | líný import, bez oken běží dál (`cb_bond/control.py:246-258`) |
| cb-bond služba | cb-udpipe služba, cb-logger služba | běhové závislosti | `ServiceStack` spouští **jejich ovládacími programy**, pořadí logger → udpipe z konfigurace (`cb_bond/stack.py`, `cb-bond-config.json` dependencies.services) |

## 3 · Klientská hranice — stav

| hranice | dodrženo? |
|---|---|
| cb_bond → cb_udpipe jen přes `UdpipeClient` | ✅ |
| cb_field → cb_udpipe jen přes `UdpipeClient` (+ typ Token z `__init__`) | ✅ |
| * → cb_logger jen přes `LogClient` | ✅ |
| cb_bond → cb_field | ⚠️ přímé importy do vnitřku: `from cb_field.service import Representation` (`cb_bond/matcher.py:48`), `from cb_field.corpusfile import …` (`service.py:27`, `control.py:428`, 11× skripty) — jména jsou veřejná, cesta obchází `__init__.py`, což `README-MODULES.md:391-393` výslovně zakazuje |
| testy | ❌ `cb_bond/tests/test_graph.py:214` importuje fixturu z `cb_field/tests/test_registry` — závislost na testech cizího modulu |

## 4 · Vnitřní závislosti s rizikem

| vazba | riziko |
|---|---|
| `registry ↔ service` v cb_field | potenciální cyklus rozbit líným importem (`cb_field/registry.py:66`) |
| `graph._sentences` ↔ pozice korpusu | poziční index bez kontroly shody délek (`cb_bond/recall.py:128-137`) |
| `SEMANTIC_PREFIXES` v cb_bond | cb_bond zná nazpaměť slovník os cb_field (`cb_bond/matcher.py:66-67`) |
| `xpos[10]`, `xpos[:2]` v cb_field | poziční kontrakt pražského tagsetu v kódu (`cb_field/service.py:370-377`) |
| `DefinitionResolver` ↔ váha 0.7 | typ relace rekonstruovaný z hodnoty váhy (`cb_bond/dialog.py:143-144`) |

## 5 · Externí závislosti (requirements.txt)

| balík | verze | pro koho | poznámka |
|---|---|---|---|
| tensorflow, tf_keras | 2.21.0 | vendor UDPipe 2 | náš kód neimportuje |
| transformers | 4.49.0 | vendor (RobeCzech) | náš kód neimportuje |
| ufal.udpipe / morphodita / chu_liu_edmonds | pinned | vendor | |
| numpy | 2.4.6 | cb_field **+ cb_bond** | deklarace v requirements zastaralá |
| viewbase | **bez pinu** | cb_bond okna | otisk frontendu se kontroluje až za běhu |
| jsonschema | 4.26.0 | cb_config | jediný řádek v tabulce schválených závislostí README-MODULES |

**Žádný solver / logická knihovna není** (z3, pysat, ortools, sympy, networkx, rdflib: nic).
Property-based testování (hypothesis): není. Prostředí obsahuje navíc nedeklarované
transitivní balíky viewbase (fastapi, pydantic, rich, …) — `run-python` kontroluje jen
jedním směrem.

## 6 · Chybějící pojistky

1. **AST test směru závislostí** slíbený v `README-MODULES.md:419-424` neexistuje —
   graf hlídá jen dokumentace. (Kandidát: zavést spolu s novou vrstvou, T-12 návrhu.)
2. Tři nezávislé definice `ServiceUnavailable` (logger/udpipe/bond) — `except` chytí jen
   jednu; pro vrstvu orchestrující víc služeb past.
3. `cb_field` nemá config/log/klienta — každá budoucí vrstva nad ním začíná mimo
   infrastrukturu (viz ARCHITECTURE_REVIEW § 10).
