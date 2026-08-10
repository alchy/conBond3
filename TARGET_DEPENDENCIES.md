# TARGET_DEPENDENCIES — cílový (a nyní implementovaný) graf závislostí

**Stav:** odpovídá implementaci po fázi 11. Formát dle zadání §51:
komponenta → závislost → důvod → směr. Výchozí stav před stavbou popisuje
`CURRENT_DEPENDENCIES.md` (k commitu 1bea15a).

## 1 · Graf

```
cb_bond ──→ cb_interpret ──→ cb_logic        (nové vrstvy)
   │              │
   │              └────────→ cb_udpipe (typ Token)
   ├──→ cb_field ──→ cb_udpipe
   └──→ cb_udpipe (klient)
                všichni ──→ cb_logger, cb_config (sdílené)

cb_logic  →  NIC (jádro pod všemi vrstvami; pouze stdlib)
```

## 2 · Nové hrany

| komponenta | závislost | důvod | mechanismus |
|---|---|---|---|
| cb_logic | — | formální jádro nesmí znát NLP ani služby (zadání §50) | pouze stdlib; hlídáno grep testem v Task 6 fáze 2 a při každé fázi |
| cb_interpret | cb_logic | vyrábí Assertions/Rules pro validační cestu | import veřejného API |
| cb_interpret | cb_udpipe | typ `Token` (rozbor je vstup interpretace) | import typu z `__init__`; služba se nevolá (tokeny dodává volající) |
| cb_bond | cb_interpret | `LogicBridge` — učení z dialogu + formální odpovědi | import v `cb_bond/logic.py`; lazy v `service.build()` |
| cb_bond | cb_logic | persistence báze (serialize), typy | přes `cb_bond/logic.py` |

Směr je jednoznačný: jazyková vrstva je **klient** jádra, nikdy naopak;
retrieval (cb_field/matcher) zůstává paralelní cestou — statistika navrhuje,
nikdy nerozhoduje o pravdivosti (INV-11).

## 3 · Trvající dluhy z CURRENT_DEPENDENCIES (vědomě nezměněno)

1. Přímé importy cb_bond → vnitřek cb_field (mimo `__init__`) — beze změny;
   oprava je mechanická, mimo rozsah reasoning práce.
2. `cb_bond/tests/test_graph.py:214` importuje fixturu z testů cb_field.
3. Chybí AST test směru závislostí (T-12) — nové hrany zatím hlídá jen
   tento dokument + import guard cb_logic.
4. cb_field bez konfigurace/logování/klienta.
5. Tři nezávislé `ServiceUnavailable`.

## 4 · Pravidla pro budoucí hrany

- Do `cb_logic` nesmí přibýt žádný import z `cb_*` ani závislost mimo
  stdlib; případný SAT/CSP solver patří za šev (nová implementace
  rozhodovací cesty měřená proti orákulům), se jmenovitým schválením
  závislosti dle README-MODULES.
- `cb_interpret` nesmí vidět službu cb_bond (tokeny dodává volající).
- Statistické návrhy (budoucí LLM vrstva) smí vyrábět jen `Assertion`
  (úroveň HYPOTHESIS/DOCUMENTED dle zdroje) — nikdy zapisovat přímo.
