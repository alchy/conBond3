"""Provenience — původ informace, derivace a konflikt (KNOWLEDGE_MODEL § 7, § 10).

Evidence není pravda: báze uchovává tvrzení a jejich původ; pravdivost je
věc čtení a dotazů. Confidence je metadata — nikdy nevstupuje do logického
výsledku (zadání § 48–49).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cb_logic.terms import Atom, Literal


class EvidenceKind(Enum):
    USER_ASSERTION = "user_assertion"
    OBSERVATION = "observation"
    EXTERNAL = "external"
    ASSUMPTION = "assumption"
    HYPOTHESIS = "hypothesis"
    DERIVED = "derived"


@dataclass(frozen=True)
class Evidence:
    """Druh původu + volitelný zdroj a síla; síla nemění sémantiku."""
    kind: EvidenceKind
    source: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence mimo [0,1]: {self.confidence}")


# Mřížka provenience (kap. 14.3 návrhu): vyšší úroveň přebíjí ve čtení,
# nižší strana zůstává a konflikt se eviduje (INV-5).
LEVEL_HYPOTHESIS = 0
LEVEL_DERIVED = 1
LEVEL_DOCUMENTED = 2
LEVEL_DEFINITION = 3
LEVEL_CORRECTION = 4


@dataclass(frozen=True)
class Provenance:
    """Úroveň mřížky + evidence + případný odkaz na derivaci."""
    level: int
    evidence: Evidence
    derivation_id: int | None = None

    def __post_init__(self) -> None:
        if not LEVEL_HYPOTHESIS <= self.level <= LEVEL_CORRECTION:
            raise ValueError(f"úroveň mimo mřížku 0–4: {self.level}")
        if self.level == LEVEL_DERIVED and self.derivation_id is None:
            raise ValueError("odvozený fakt musí nést derivaci (INV-2)")


@dataclass(frozen=True)
class Assertion:
    """Kandidátní tvrzení — jediné, co smí vyrábět interpretační vrstva.

    Do báze vstupuje výhradně validací (KnowledgeBase.assert_candidate).
    """
    literal: Literal
    evidence: Evidence
    level: int


@dataclass(frozen=True)
class Derivation:
    """Krok odvození: závěr + premisy + pravidlo + jmenovky předpokladů."""
    id: int
    conclusion: Literal
    premises: tuple[Literal, ...]
    rule_index: int | None
    assumptions: frozenset[str]


@dataclass(frozen=True)
class Conflict:
    """Atom tvrzený oběma polaritami; obě provenience zůstávají viditelné."""
    atom: Atom
    positive: Provenance
    negative: Provenance
