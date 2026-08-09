"""KnowledgeBase — báze znalostí s jedinou zapisovací cestou (INFERENCE_ENGINE § 1).

Zápis faktů jde výhradně validací (assert_candidate): kontrola deklarací,
groundness a mřížka provenience. Konflikt se hlásí a eviduje, nikdy tiše
neřeší (INV-5); obě strany zůstávají. Hypotéza (úroveň 0) do čtení
pravdivosti nevstupuje. Žádný globální stav — dvě báze vedle sebe musí jít.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from cb_logic.constraints import Constraint
from cb_logic.expressions import Expression, atoms
from cb_logic.provenance import (Assertion, Conflict, Derivation,
                                 LEVEL_DERIVED, LEVEL_DOCUMENTED,
                                 LEVEL_HYPOTHESIS, Provenance)
from cb_logic.semantics import Truth
from cb_logic.terms import (Atom, Domain, Literal, Relation, Variable,
                            atom_key)


@dataclass(frozen=True)
class Rule:
    """∀ přes var_domains: body → head (KNOWLEDGE_MODEL § 5)."""
    var_domains: tuple[tuple[Variable, str], ...]
    body: Expression
    head: Literal


@dataclass(frozen=True)
class Accepted:
    literal: Literal


@dataclass(frozen=True)
class Rejected:
    reason: str


@dataclass(frozen=True)
class Conflicted:
    conflict: Conflict


@dataclass
class _Side:
    """Podpora jedné polarity atomu: vlastní evidence + derivace."""
    own: Provenance | None = None
    derivations: list[int] = field(default_factory=list)

    def supported(self) -> bool:
        return self.effective_level() is not None

    def effective_level(self) -> int | None:
        """Úroveň strany pro mřížku; hypotéza a prázdno nedávají čtení."""
        if self.own is not None and self.own.level > LEVEL_HYPOTHESIS:
            return self.own.level
        if self.derivations:
            return LEVEL_DERIVED
        return None


class KnowledgeBase:
    """Deklarace + fakta + pravidla + constrainty + konflikty + derivace."""

    def __init__(self) -> None:
        self._relations: dict[str, Relation] = {}
        self._domains: dict[str, Domain] = {}
        self._sides: dict[tuple[Atom, bool], _Side] = {}
        self.rules: list[tuple[Rule, Provenance]] = []
        self.constraints: list[tuple[Constraint, Provenance]] = []
        self.conflicts: list[Conflict] = []
        self.derivations: list[Derivation] = []

    # -- deklarace ----------------------------------------------------------

    def declare_relation(self, relation: Relation) -> None:
        existing = self._relations.get(relation.name)
        if existing is not None and existing != relation:
            raise ValueError(f"relace {relation.name!r} už je deklarovaná "
                             f"s aritou {existing.arity}")
        self._relations[relation.name] = relation

    def declare_domain(self, domain: Domain) -> None:
        existing = self._domains.get(domain.name)
        if existing is not None and existing != domain:
            raise ValueError(f"doména {domain.name!r} už je deklarovaná jinak")
        self._domains[domain.name] = domain

    def relation(self, name: str) -> Relation:
        return self._relations[name]

    def domain(self, name: str) -> Domain:
        return self._domains[name]

    # -- zápis faktů (jediná cesta) ----------------------------------------

    def assert_candidate(self,
                         assertion: Assertion) -> Accepted | Rejected | Conflicted:
        literal = assertion.literal
        atom = literal.atom
        declared = self._relations.get(atom.relation.name)
        if declared is None:
            return Rejected(f"nedeklarovaná relace {atom.relation.name!r}")
        if declared != atom.relation:
            return Rejected(f"relace {atom.relation.name!r} nesedí "
                            f"s deklarací (arita)")
        if not atom.ground:
            return Rejected(f"literál není ground: {atom}")

        provenance = Provenance(assertion.level, assertion.evidence)
        side = self._side(atom, literal.positive)
        if side.own is None or assertion.level > side.own.level:
            side.own = provenance
        # slabší/rovná vlastní evidence téže strany: silnější už tam je

        opposite = self._sides.get((atom, not literal.positive))
        if opposite is not None and opposite.supported():
            conflict = self._record_conflict(atom)
            if opposite.effective_level() == side.effective_level():
                return Conflicted(conflict)
        return Accepted(literal)

    def _side(self, atom: Atom, positive: bool) -> _Side:
        key = (atom, positive)
        if key not in self._sides:
            self._sides[key] = _Side()
        return self._sides[key]

    def _record_conflict(self, atom: Atom) -> Conflict:
        pos = self._sides.get((atom, True))
        neg = self._sides.get((atom, False))
        conflict = Conflict(atom,
                            self._best_provenance(pos),
                            self._best_provenance(neg))
        self.conflicts.append(conflict)
        return conflict

    def _best_provenance(self, side: _Side | None) -> Provenance:
        if side is None or not side.supported():
            raise ValueError("konflikt bez podpory strany")
        if side.own is not None and side.own.level > LEVEL_HYPOTHESIS:
            return side.own
        derivation_id = side.derivations[0]
        return Provenance(LEVEL_DERIVED,
                          self._derived_evidence(),
                          derivation_id=derivation_id)

    @staticmethod
    def _derived_evidence():
        from cb_logic.provenance import Evidence, EvidenceKind
        return Evidence(EvidenceKind.DERIVED)

    # -- pravidla a constrainty --------------------------------------------

    def add_rule(self, rule: Rule, provenance: Provenance) -> int:
        declared_vars = {v for v, _ in rule.var_domains}
        for _, domain_name in rule.var_domains:
            if domain_name not in self._domains:
                raise ValueError(f"nedeklarovaná doména {domain_name!r}")
        for atom in atoms(rule.body) + (rule.head.atom,):
            if atom.relation.name not in self._relations:
                raise ValueError(
                    f"nedeklarovaná relace {atom.relation.name!r} v pravidle")
            for arg in atom.args:
                if isinstance(arg, Variable) and arg not in declared_vars:
                    raise ValueError(
                        f"proměnná {arg.name!r} bez domény (LOGIC_SEMANTICS § 6)")
        self.rules.append((rule, provenance))
        return len(self.rules) - 1

    def add_constraint(self, constraint: Constraint,
                       provenance: Provenance) -> int:
        from cb_logic.constraints import CardinalityConstraint
        constraint_atoms = (constraint.atoms
                            if isinstance(constraint, CardinalityConstraint)
                            else atoms(constraint.expr))
        for atom in constraint_atoms:
            if atom.relation.name not in self._relations:
                raise ValueError(
                    f"nedeklarovaná relace {atom.relation.name!r} v constraintu")
        self.constraints.append((constraint, provenance))
        return len(self.constraints) - 1

    # -- čtení --------------------------------------------------------------

    def truth_of(self, atom: Atom) -> Truth:
        """Čtení pravdivosti dle mřížky; konflikt na téže úrovni = UNKNOWN."""
        pos = self._sides.get((atom, True))
        neg = self._sides.get((atom, False))
        pos_level = pos.effective_level() if pos else None
        neg_level = neg.effective_level() if neg else None
        if pos_level is None and neg_level is None:
            return Truth.UNKNOWN
        if neg_level is None:
            return Truth.TRUE
        if pos_level is None:
            return Truth.FALSE
        if pos_level > neg_level:
            return Truth.TRUE
        if neg_level > pos_level:
            return Truth.FALSE
        return Truth.UNKNOWN

    def documented_truth(self, atom: Atom) -> Truth:
        """Čtení JEN z vlastních evidencí úrovně ≥ DOCUMENTED.

        Slouží pinování atomů v prostoru modelů: odvozené se nepinuje
        (regenerují ho instance pravidel), hypotézy nikdy.
        """
        pos = self._sides.get((atom, True))
        neg = self._sides.get((atom, False))
        pos_level = (pos.own.level if pos is not None and pos.own is not None
                     and pos.own.level >= LEVEL_DOCUMENTED else None)
        neg_level = (neg.own.level if neg is not None and neg.own is not None
                     and neg.own.level >= LEVEL_DOCUMENTED else None)
        if pos_level is None and neg_level is None:
            return Truth.UNKNOWN
        if neg_level is None:
            return Truth.TRUE
        if pos_level is None:
            return Truth.FALSE
        if pos_level > neg_level:
            return Truth.TRUE
        if neg_level > pos_level:
            return Truth.FALSE
        return Truth.UNKNOWN

    def is_conflicted(self, atom: Atom) -> bool:
        pos = self._sides.get((atom, True))
        neg = self._sides.get((atom, False))
        return (pos is not None and pos.supported()
                and neg is not None and neg.supported())

    def supported(self, literal: Literal) -> bool:
        side = self._sides.get((literal.atom, literal.positive))
        return side is not None and side.supported()

    def own_facts(self) -> tuple[tuple[Literal, Provenance], ...]:
        """Fakta s vlastní evidencí v kanonickém pořadí."""
        entries = []
        for (atom, positive), side in self._sides.items():
            if side.own is not None:
                entries.append((Literal(atom, positive), side.own))
        entries.sort(key=lambda e: (atom_key(e[0].atom), not e[0].positive))
        return tuple(entries)

    # -- kopie ---------------------------------------------------------------

    def copy(self) -> "KnowledgeBase":
        """Nezávislá kopie; frozen hodnoty se sdílejí, stav se kopíruje."""
        clone = KnowledgeBase()
        clone._relations = dict(self._relations)
        clone._domains = dict(self._domains)
        clone._sides = {key: _Side(side.own, list(side.derivations))
                        for key, side in self._sides.items()}
        clone.rules = list(self.rules)
        clone.constraints = list(self.constraints)
        clone.conflicts = list(self.conflicts)
        clone.derivations = list(self.derivations)
        return clone
