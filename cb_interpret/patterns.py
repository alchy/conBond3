"""Učené jazykové vzory — mapování povrchového tvaru na PEVNÉ operace jádra.

Zásada (LANGUAGE_LEARNING.md): dialog učí, KTERÉ slovo spouští KTEROU už
existující formální operaci — nikdy nemění význam operace. Menu operací je
uzavřené a neobsahuje žádný modální operátor: modální slovesa spouštějí
DOTAZY nad prostorem modelů (∃M / ∀M / ¬∃M), ne osu pravdivosti (kap. 41).

Vzor je DATA (JSON), ne kód. Nese provenienci, status (hypotéza → potvrzeno)
a je odvolatelný — odvolání maže mapování, ne operaci.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Operation(Enum):
    """Uzavřené menu operací, na které smí vzor mapovat.

    Jsou to DOTAZY nad prostorem modelů (MODEL_REASONING), ne pravdivostní
    hodnoty a ne modální operátory objektového jazyka.
    """
    POSSIBLE = "possible"      # ∃ konzistentní model, kde P platí
    NECESSARY = "necessary"    # ∀ konzistentní modely: P platí
    IMPOSSIBLE = "impossible"  # ¬∃ konzistentní model, kde P platí


#: Menu pro učicí dotaz — jen operace z jádra, s lidským popisem.
OPERATION_MENU: tuple[tuple[Operation, str], ...] = (
    (Operation.POSSIBLE, "platí alespoň v jednom řešení"),
    (Operation.NECESSARY, "platí ve všech řešeních"),
    (Operation.IMPOSSIBLE, "neplatí v žádném řešení"),
)


class PatternStatus(Enum):
    HYPOTHESIS = "hypothesis"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    REVOKED = "revoked"


@dataclass(frozen=True)
class StructuralSignature:
    """Strukturní popis konstrukce nezávislý na entitách a predikátech.

    Klíčuje se lemmatem operátoru a přítomností vloženého přísudku —
    tím je vzor obecný přes všechny věty téže struktury (renaming test).
    """
    root_lemma: str
    has_xcomp: bool
    has_obj: bool = False
    has_obl: bool = False

    def key(self) -> str:
        return f"{self.root_lemma}|xcomp={int(self.has_xcomp)}"


@dataclass(frozen=True)
class Trigger:
    """Strukturní spouštěč: sedí na lemma operátoru + tvar, ne na větu."""
    root_lemma: str
    requires_xcomp: bool = True

    def matches(self, signature: StructuralSignature) -> bool:
        if self.root_lemma != signature.root_lemma:
            return False
        return (not self.requires_xcomp) or signature.has_xcomp

    def key(self) -> str:
        return f"{self.root_lemma}|xcomp={int(self.requires_xcomp)}"


@dataclass(frozen=True)
class LearnedPattern:
    """Mapování trigger → operace, s proveniencí a statusem."""
    trigger: Trigger
    operation: Operation
    learned_from: str                 # utterance / dialog_id
    learned_at: str | None = None     # předává volající (determinismus)
    status: PatternStatus = PatternStatus.HYPOTHESIS

    def with_status(self, status: PatternStatus) -> "LearnedPattern":
        return LearnedPattern(self.trigger, self.operation, self.learned_from,
                              self.learned_at, status)

    def to_json_object(self) -> dict:
        return {
            "trigger": {"root_lemma": self.trigger.root_lemma,
                        "requires_xcomp": self.trigger.requires_xcomp},
            "operation": self.operation.value,
            "learned_from": self.learned_from,
            "learned_at": self.learned_at,
            "status": self.status.value,
        }

    @staticmethod
    def from_json_object(obj: dict) -> "LearnedPattern":
        t = obj["trigger"]
        return LearnedPattern(
            Trigger(t["root_lemma"], t["requires_xcomp"]),
            Operation(obj["operation"]), obj["learned_from"],
            obj.get("learned_at"), PatternStatus(obj["status"]))


class PatternStore:
    """Sbírka učených vzorů; klíčováno triggerem. Žádný globální stav."""

    def __init__(self) -> None:
        self._by_key: dict[str, LearnedPattern] = {}

    def add(self, pattern: LearnedPattern) -> None:
        self._by_key[pattern.trigger.key()] = pattern

    def teach(self, signature: StructuralSignature, operation: Operation, *,
              learned_from: str, learned_at: str | None = None) -> LearnedPattern:
        """Naučí vzor ze strukturní signatury jako HYPOTÉZU."""
        pattern = LearnedPattern(
            Trigger(signature.root_lemma, requires_xcomp=signature.has_xcomp),
            operation, learned_from, learned_at, PatternStatus.HYPOTHESIS)
        self.add(pattern)
        return pattern

    def match(self, signature: StructuralSignature) -> LearnedPattern | None:
        """Aktivní vzor (hypotéza/potvrzený) pro danou strukturu, nebo None."""
        for pattern in self._by_key.values():
            if pattern.status in (PatternStatus.REVOKED,
                                  PatternStatus.REJECTED):
                continue
            if pattern.trigger.matches(signature):
                return pattern
        return None

    def confirm(self, root_lemma: str) -> LearnedPattern | None:
        return self._set_status(root_lemma, PatternStatus.CONFIRMED)

    def revoke(self, root_lemma: str) -> LearnedPattern | None:
        """Odvolá mapování; operace v jádru zůstává nedotčená."""
        return self._set_status(root_lemma, PatternStatus.REVOKED)

    def _set_status(self, root_lemma: str,
                    status: PatternStatus) -> LearnedPattern | None:
        for key, pattern in list(self._by_key.items()):
            if pattern.trigger.root_lemma == root_lemma:
                updated = pattern.with_status(status)
                self._by_key[key] = updated
                return updated
        return None

    def all(self) -> tuple[LearnedPattern, ...]:
        return tuple(sorted(self._by_key.values(),
                            key=lambda p: p.trigger.key()))

    def to_json(self) -> list[dict]:
        return [p.to_json_object() for p in self.all()]

    @staticmethod
    def from_json(data: list[dict]) -> "PatternStore":
        store = PatternStore()
        for obj in data:
            store.add(LearnedPattern.from_json_object(obj))
        return store
