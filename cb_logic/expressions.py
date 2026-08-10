"""AST logických výrazů — LOGIC_SEMANTICS.md § 1.

Výraz je strom hodnot, nikdy string. Implies/Equiv se při konstrukci
nepřepisují na AND/OR/NOT — strukturu, kterou uživatel vyslovil, nese
vysvětlení; normalizace je věc pohledů. Pomocné konstruktory conj/disj
jen zplošťují týž druh spojky.
"""
from __future__ import annotations

from dataclasses import dataclass

from cb_logic.terms import Atom, Literal, Term, Variable, atom_key, term_key


@dataclass(frozen=True)
class Const:
    value: bool


@dataclass(frozen=True)
class AtomRef:
    atom: Atom


@dataclass(frozen=True)
class Not:
    operand: "Expression"


@dataclass(frozen=True)
class And:
    operands: tuple["Expression", ...]

    def __post_init__(self) -> None:
        if not self.operands:
            raise ValueError("And bez operandů")


@dataclass(frozen=True)
class Or:
    operands: tuple["Expression", ...]

    def __post_init__(self) -> None:
        if not self.operands:
            raise ValueError("Or bez operandů")


@dataclass(frozen=True)
class Implies:
    antecedent: "Expression"
    consequent: "Expression"


@dataclass(frozen=True)
class Equiv:
    left: "Expression"
    right: "Expression"


Expression = Const | AtomRef | Not | And | Or | Implies | Equiv


def conj(*exprs: Expression) -> Expression:
    """Konjunkce: zploští vnořené And; jeden operand vrací přímo."""
    return _nary(And, exprs)


def disj(*exprs: Expression) -> Expression:
    """Disjunkce: zploští vnořené Or; jeden operand vrací přímo."""
    return _nary(Or, exprs)


def _nary(kind: type, exprs: tuple[Expression, ...]) -> Expression:
    if not exprs:
        raise ValueError(f"{kind.__name__} bez operandů")
    flat: list[Expression] = []
    for e in exprs:
        if isinstance(e, kind):
            flat.extend(e.operands)
        else:
            flat.append(e)
    if len(flat) == 1:
        return flat[0]
    return kind(tuple(flat))


def from_literal(lit: Literal) -> Expression:
    """Literál jako výraz: záporný dostane Not."""
    ref = AtomRef(lit.atom)
    return ref if lit.positive else Not(ref)


def atoms(expr: Expression) -> tuple[Atom, ...]:
    """Atomy výrazu, deduplikované, v kanonickém pořadí dle atom_key."""
    found: set[Atom] = set()
    _collect(expr, found)
    return tuple(sorted(found, key=atom_key))


def _collect(expr: Expression, out: set[Atom]) -> None:
    if isinstance(expr, AtomRef):
        out.add(expr.atom)
    elif isinstance(expr, Not):
        _collect(expr.operand, out)
    elif isinstance(expr, (And, Or)):
        for op in expr.operands:
            _collect(op, out)
    elif isinstance(expr, Implies):
        _collect(expr.antecedent, out)
        _collect(expr.consequent, out)
    elif isinstance(expr, Equiv):
        _collect(expr.left, out)
        _collect(expr.right, out)


def substitute(expr: Expression, binding: dict[Variable, Term]) -> Expression:
    """Dosazení termů za proměnné v argumentech atomů; nemutuje."""
    if isinstance(expr, Const):
        return expr
    if isinstance(expr, AtomRef):
        args = tuple(binding.get(a, a) if isinstance(a, Variable) else a
                     for a in expr.atom.args)
        if args == expr.atom.args:
            return expr
        return AtomRef(Atom(expr.atom.relation, args))
    if isinstance(expr, Not):
        return Not(substitute(expr.operand, binding))
    if isinstance(expr, And):
        return And(tuple(substitute(o, binding) for o in expr.operands))
    if isinstance(expr, Or):
        return Or(tuple(substitute(o, binding) for o in expr.operands))
    if isinstance(expr, Implies):
        return Implies(substitute(expr.antecedent, binding),
                       substitute(expr.consequent, binding))
    return Equiv(substitute(expr.left, binding),
                 substitute(expr.right, binding))


def _atom_text(atom: Atom) -> str:
    return f"{atom.relation.name}({','.join(term_key(a) for a in atom.args)})"


def to_text(expr: Expression) -> str:
    """Kanonický uzávorkovaný zápis; pro ladění a řazení, ne pro parsování."""
    if isinstance(expr, Const):
        return "TRUE" if expr.value else "FALSE"
    if isinstance(expr, AtomRef):
        return _atom_text(expr.atom)
    if isinstance(expr, Not):
        return f"(NOT {to_text(expr.operand)})"
    if isinstance(expr, And):
        return "(" + " AND ".join(to_text(o) for o in expr.operands) + ")"
    if isinstance(expr, Or):
        return "(" + " OR ".join(to_text(o) for o in expr.operands) + ")"
    if isinstance(expr, Implies):
        return f"({to_text(expr.antecedent)} IMPLIES {to_text(expr.consequent)})"
    return f"({to_text(expr.left)} EQUIV {to_text(expr.right)})"
