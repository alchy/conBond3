# cb_logic — formální jádro znalosti a logiky

Čistá knihovna: termy, atomy, literály, AST logických výrazů
a pravdivostní sémantika (dvouhodnotová + Kleeneho K3) s pravdivostní
tabulkou jako referenčním orákulem.

Specifikace: `KNOWLEDGE_MODEL.md` a `LOGIC_SEMANTICS.md` v kořeni.

Zásady: pouze stdlib, žádný import z `cb_*`, žádný globální stav,
determinismus (stabilní klíče, žádné hodiny, náhoda jen se semínkem).

## Testy

    ./run-python -m unittest discover -s cb_logic -t .

## Co modul vědomě neřeší (zatím)

KnowledgeBase s validací, constrainty, inference, prostor modelů,
provenience — fáze 3+ dle ARCHITECTURE_REVIEW § 15. Přirozený jazyk
nikdy: interpretace je klient tohoto jádra.
