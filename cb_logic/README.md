# cb_logic — formální jádro znalosti a logiky

Čistá knihovna: termy, atomy, literály, AST logických výrazů,
pravdivostní sémantika (dvouhodnotová + Kleeneho K3) s tabulkovým
orákulem, provenience s mřížkou úrovní, constrainty (dvě čtení jedné
sémantiky), KnowledgeBase s jedinou zapisovací cestou, forward chaining
do fixpointu s derivacemi a konflikty, well-founded invalidace,
backward proof a assumptions jako pohled.

Specifikace: `KNOWLEDGE_MODEL.md`, `LOGIC_SEMANTICS.md`,
`CONSTRAINT_MODEL.md`, `INFERENCE_ENGINE.md` v kořeni.

Zásady: pouze stdlib, žádný import z `cb_*`, žádný globální stav,
determinismus (stabilní klíče, žádné hodiny, náhoda jen se semínkem).

## Testy

    ./run-python -m unittest discover -s cb_logic -t .

## Co modul vědomě neřeší (zatím)

Prostor modelů a modální dotazy (possible/necessary/impossible,
protipříklady), persistence — fáze 6+ dle ARCHITECTURE_REVIEW § 15.
Přirozený jazyk nikdy: interpretace je klient tohoto jádra.
