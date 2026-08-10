"""Most k formálnímu jádru — učení z dialogu a formální odpovědi.

Nová vrstva stojí VEDLE retrieval cesty (migrace, ARCHITECTURE_REVIEW § 15):
odpovídá, když umí; mlčí-li (unparsed), jede párování jako dřív a klíč
`logic` v odpovědi je None. Znalost z dialogu se persistuje JSON
round-tripem a přežívá restart — poprvé (dluh P5 pro novou vrstvu).

Při chybě: poškozený soubor báze je hlasitá chyba startu, ne tichý
začátek od nuly — ztráta naučeného se nesmí zamlčet.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cb_logic import KnowledgeBase, Truth, kb_from_json, kb_to_json
from cb_interpret import (DialogueLearner, cs_profile, render_explanation,
                          render_literal, render_truth)


class LogicBridge:
    """Jedna formální báze nad službou; parser se předává, nevyrábí."""

    def __init__(self, parser, kb_file: str | Path) -> None:
        self.parser = parser
        self.kb_file = Path(kb_file)
        self.profile = cs_profile()
        kb = KnowledgeBase()
        if self.kb_file.exists():
            kb = kb_from_json(json.loads(
                self.kb_file.read_text(encoding="utf-8")))
        self.learner = DialogueLearner(kb, self.profile)

    # --- dialog ---------------------------------------------------------

    def context(self, text: str) -> dict[str, Any]:
        """Věta od člověka → interpretace → validace → inference → uložení."""
        tokens = self._tokens(text)
        if tokens is None:
            return {"kind": "unparsed", "note": "rozbor nedal žádnou větu"}
        result = self.learner.learn(tokens, text)
        summary: dict[str, Any] = {
            "kind": result.candidate.kind,
            "note": result.candidate.note,
            "outcome": (type(result.outcome).__name__.lower()
                        if result.outcome is not None else None),
            "derived": ([render_literal(l, self.profile)
                         for l in result.inference.new_facts]
                        if result.inference is not None else []),
            "conflicts": len(self.learner.kb.conflicts),
        }
        if result.outcome is not None:
            self.save()
        return summary

    def ask(self, text: str) -> dict[str, Any] | None:
        """Formální odpověď, nebo None — pak odpovídá retrieval."""
        tokens = self._tokens(text)
        if tokens is None:
            return None
        result = self.learner.ask(tokens, text)
        if result.candidate.kind == "unparsed":
            return None
        output: dict[str, Any] = {
            "kind": result.candidate.kind,
            "truth": result.truth.name if result.truth is not None else None,
            "answer": (render_truth(result.truth, self.profile)
                       if result.truth is not None else None),
            "explanations": [render_explanation(e, self.profile)
                             for e in result.explanations],
            "conflicted": result.conflicted,
        }
        if result.why_not is not None:
            output["missing"] = [
                render_literal(lit, self.profile)
                for suggestion in result.why_not.suggestions
                for lit in suggestion.missing]
        return output

    # --- stav a persistence --------------------------------------------

    def state(self) -> dict[str, int]:
        kb = self.learner.kb
        return {"facts": len(kb.own_facts()), "rules": len(kb.rules),
                "derivations": len(kb.derivations),
                "conflicts": len(kb.conflicts)}

    def save(self) -> None:
        """Atomicky přes .tmp + replace (vzor registry/cache)."""
        self.kb_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.kb_file.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(kb_to_json(self.learner.kb), ensure_ascii=False,
                       sort_keys=True, separators=(",", ":")),
            encoding="utf-8")
        os.replace(temporary, self.kb_file)

    def _tokens(self, text: str):
        result = self.parser.parse(text=text)
        if not result.sentences:
            return None
        return result.sentences[0].tokens
