"""Učicí dotaz — systém popíše konstrukci, které nerozumí, a nabídne menu.

Zná‑li parser strukturu, ale ne sémantické mapování operátoru, NEHÁDÁ:
vytvoří dotaz a nabídne JEN operace z uzavřeného menu (LANGUAGE_LEARNING.md).
Tím dialog nemůže vytvořit novou nedefinovanou sémantiku.
"""
from __future__ import annotations

from dataclasses import dataclass

from cb_interpret.patterns import OPERATION_MENU, Operation, StructuralSignature


@dataclass(frozen=True)
class ClarificationRequest:
    signature: StructuralSignature
    question: str
    options: tuple[tuple[Operation, str], ...]

    def to_json_object(self) -> dict:
        return {
            "root_lemma": self.signature.root_lemma,
            "question": self.question,
            "options": [{"operation": op.value, "popis": popis}
                        for op, popis in self.options],
        }


def build_clarification(signature: StructuralSignature) -> ClarificationRequest:
    """Sestaví učicí dotaz ze strukturní signatury."""
    lemma = signature.root_lemma
    question = (f"Strukturu věty znám (sloveso {lemma!r} + vložený přísudek), "
                f"ale neznám jeho sémantické mapování. "
                f"Jakou operaci tato konstrukce vyjadřuje?")
    return ClarificationRequest(signature, question, OPERATION_MENU)


@dataclass(frozen=True)
class ReferenceClarification:
    """Doptání na referenci: konkrétní instance, nebo třída (§5)."""
    subject_lemma: str
    question: str
    options: tuple[tuple[str, str], ...]

    def to_json_object(self) -> dict:
        return {"subject": self.subject_lemma, "question": self.question,
                "options": [{"choice": c, "popis": p}
                            for c, p in self.options]}


def build_reference_clarification(subject_lemma: str) -> ReferenceClarification:
    """Systém nesmí význam svévolně zvolit — nabídne obě čtení."""
    return ReferenceClarification(
        subject_lemma,
        f"Ptáš se na konkrétní {subject_lemma} (instanci), nebo na "
        f"{subject_lemma} obecně (třídu)?",
        (("instance", f"konkrétní {subject_lemma}"),
         ("class", f"{subject_lemma} obecně (třída)")))
