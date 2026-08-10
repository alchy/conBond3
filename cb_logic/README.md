# cb_logic — formální jádro znalosti a logiky

Čistá knihovna: termy, atomy, literály, AST logických výrazů,
pravdivostní sémantika (dvouhodnotová + Kleeneho K3) s tabulkovým
orákulem, provenience s mřížkou úrovní, constrainty (dvě čtení jedné
sémantiky), KnowledgeBase s jedinou zapisovací cestou, forward chaining
do fixpointu s derivacemi a konflikty, well-founded invalidace,
backward proof, assumptions jako pohled, prostor modelů s relevančním
scope (possible/necessary/impossible, protipříklady, redundance),
vysvětlení why/why-not a JSON persistence.

Specifikace: `KNOWLEDGE_MODEL.md`, `LOGIC_SEMANTICS.md`,
`CONSTRAINT_MODEL.md`, `INFERENCE_ENGINE.md`, `MODEL_REASONING.md`,
`PROVENANCE.md` v kořeni.

Zásady: pouze stdlib, žádný import z `cb_*`, žádný globální stav,
determinismus (stabilní klíče, žádné hodiny, náhoda jen se semínkem).

## Testy

    ./run-python -m unittest discover -s cb_logic -t .

## Co modul vědomě neřeší (zatím)

Interpretaci přirozeného jazyka (dialog → kandidátní tvrzení, fáze 9)
a integraci do služby cb-bond (fáze 11). Přirozený jazyk nikdy:
interpretace je klient tohoto jádra.
