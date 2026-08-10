# cb_logic Fáze 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Postavit jádro balíku `cb_logic`: termy/atomy/literály, AST logických výrazů a pravdivostní sémantiku (dvouhodnotovou + K3) s pravdivostní tabulkou jako referenčním orákulem — přesně rozsah LOGIC_SEMANTICS.md § 10.

**Architecture:** Čistá knihovna (vzor cb_config): tři zdrojové soubory s jednou odpovědností (`terms.py` datový model, `expressions.py` AST + strukturální operace, `semantics.py` evaluace + rozhodovací dotazy), frozen dataclasses, deterministické pořadí přes stabilní klíče. Specifikace: `KNOWLEDGE_MODEL.md` (§ 2–3) a `LOGIC_SEMANTICS.md` (§ 1–5, § 8, § 10).

**Tech Stack:** Python 3.11, výhradně stdlib (`dataclasses`, `enum`, `itertools`, `random` se semínkem). Testy `unittest`, spouštěné `./run-python -m unittest`.

## Global Constraints

- Žádná závislost mimo stdlib; **žádný import z `cb_*`** v `cb_logic/` (jádro je pod všemi vrstvami).
- Testovací framework: výhradně `unittest` (politika README-MODULES § testy; žádný pytest).
- Identifikátory anglicky, docstringy česky (politika § 17).
- Determinismus: žádné hodiny, žádná neseedovaná náhoda; iterace v kanonickém pořadí stabilních klíčů (LOGIC_SEMANTICS § 8).
- Rovnost Entity **výhradně podle `id`** — popisek `label` mimo porovnání (KNOWLEDGE_MODEL § 2).
- `INCOMPLETE` se nikdy nevydává za `NO`/`FALSE` (zadání § 24).
- Spouštění testů: `./run-python -m unittest discover -s cb_logic -t .`
- Commity malé, česky, ve stylu repozitáře.

---

### Task 1: Datový model termů (`cb_logic/terms.py`)

**Files:**
- Create: `cb_logic/__init__.py` (zatím prázdný docstring)
- Create: `cb_logic/terms.py`
- Create: `cb_logic/tests/__init__.py` (prázdný)
- Test: `cb_logic/tests/test_terms.py`

**Interfaces:**
- Consumes: —
- Produces (pro Task 2+):
  - `Entity(id: str, label: str | None = None)` — frozen, eq/hash jen dle `id`
  - `Value(value: object)` — frozen; hodnota musí být hashovatelná
  - `Variable(name: str)` — frozen
  - `Term = Entity | Value | Variable` (type alias)
  - `term_key(term: Term) -> str` — stabilní řadicí klíč (`"E:…"`, `"V:…"`, `"?:…"`)
  - `is_ground(term: Term) -> bool`
  - `Domain(name: str, members: tuple[Term, ...])` — frozen; členové ground, jinak `ValueError`
  - `Relation(name: str, arity: int)` — frozen; `arity >= 1` jinak `ValueError`
  - `Atom(relation: Relation, args: tuple[Term, ...])` — frozen; kontrola arity (`ValueError`); property `ground: bool`; `atom_key(atom) -> str`
  - `Literal(atom: Atom, positive: bool = True)` — frozen; metoda `negated() -> Literal`

- [ ] **Step 1: Napsat padající testy**

```python
"""Testy datového modelu termů — KNOWLEDGE_MODEL.md § 2–3."""
import unittest

from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Value,
                            Variable, atom_key, is_ground, term_key)


class TestEntity(unittest.TestCase):
    def test_rovnost_jen_podle_id(self):
        self.assertEqual(Entity("petr", label="Petr N."), Entity("petr"))
        self.assertNotEqual(Entity("petr"), Entity("pavel"))

    def test_hash_konzistentni_s_rovnosti(self):
        self.assertEqual(len({Entity("petr", label="A"), Entity("petr", label="B")}), 1)


class TestTermKey(unittest.TestCase):
    def test_klice_jsou_stabilni_a_ruzne_druhy_nekoliduji(self):
        self.assertEqual(term_key(Entity("petr")), "E:petr")
        self.assertEqual(term_key(Variable("X")), "?:X")
        self.assertNotEqual(term_key(Value("petr")), term_key(Entity("petr")))

    def test_hodnoty_ruznych_typu_nekoliduji(self):
        self.assertNotEqual(term_key(Value(1)), term_key(Value("1")))


class TestGround(unittest.TestCase):
    def test_promenna_neni_ground(self):
        self.assertTrue(is_ground(Entity("e")))
        self.assertTrue(is_ground(Value(3)))
        self.assertFalse(is_ground(Variable("X")))


class TestDomain(unittest.TestCase):
    def test_clen_s_promennou_je_hlasita_chyba(self):
        with self.assertRaises(ValueError):
            Domain("osoby", (Entity("a"), Variable("X")))


class TestRelation(unittest.TestCase):
    def test_arita_pod_jedna_je_chyba(self):
        with self.assertRaises(ValueError):
            Relation("nic", 0)


class TestAtom(unittest.TestCase):
    def setUp(self):
        self.programmer = Relation("programmer", 1)
        self.lives = Relation("lives_in", 2)

    def test_spatna_arita_je_hlasita_chyba(self):
        with self.assertRaises(ValueError):
            Atom(self.programmer, (Entity("a"), Entity("b")))

    def test_ground_a_klic(self):
        a = Atom(self.lives, (Entity("petr"), Value("Praha")))
        self.assertTrue(a.ground)
        self.assertFalse(Atom(self.programmer, (Variable("X"),)).ground)
        self.assertEqual(atom_key(a), "lives_in/2(E:petr,V:str:'Praha')")

    def test_atom_je_hashovatelny(self):
        a = Atom(self.programmer, (Entity("petr"),))
        self.assertEqual(len({a, Atom(self.programmer, (Entity("petr"),))}), 1)


class TestLiteral(unittest.TestCase):
    def test_negace_obraci_polaritu_a_je_involuce(self):
        lit = Literal(Atom(Relation("p", 1), (Entity("a"),)))
        self.assertTrue(lit.positive)
        self.assertFalse(lit.negated().positive)
        self.assertEqual(lit.negated().negated(), lit)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ověřit, že padají**

Run: `./run-python -m unittest cb_logic.tests.test_terms -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: cb_logic.terms`

- [ ] **Step 3: Implementovat `cb_logic/terms.py`**

```python
"""Termy, relace, atomy a literály — datový model dle KNOWLEDGE_MODEL.md § 2–3.

Rovnost Entity je výhradně podle id: popisek je pro člověka a nesmí
vstoupit do žádného rozhodnutí (anti-overfitting, zadání § 43/46).
Stabilní klíče (term_key, atom_key) nesou determinismus všech iterací
(LOGIC_SEMANTICS § 8) — při shodě rozhoduje klíč, ne pořadí v paměti.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entity:
    """Jednotlivina se stabilní identitou; label je jen popisek."""
    id: str
    label: str | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Value:
    """Literální hodnota domény; musí být hashovatelná."""
    value: object


@dataclass(frozen=True)
class Variable:
    """Proměnná pravidel a dotazů; do báze nikdy nevstupuje volná."""
    name: str


Term = Entity | Value | Variable


def term_key(term: Term) -> str:
    """Stabilní řadicí klíč termu; druhy termů nekolidují prefixem."""
    if isinstance(term, Entity):
        return f"E:{term.id}"
    if isinstance(term, Value):
        return f"V:{type(term.value).__name__}:{term.value!r}"
    return f"?:{term.name}"


def is_ground(term: Term) -> bool:
    """Ground = bez proměnné."""
    return not isinstance(term, Variable)


@dataclass(frozen=True)
class Domain:
    """Pojmenovaná konečná množina ground termů (kvantifikační obor)."""
    name: str
    members: tuple[Term, ...]

    def __post_init__(self) -> None:
        for member in self.members:
            if not is_ground(member):
                raise ValueError(
                    f"doména {self.name!r}: člen {member!r} není ground")


@dataclass(frozen=True)
class Relation:
    """Deklarovaný predikát; překlep arity je hlasitá chyba, ne nová relace."""
    name: str
    arity: int

    def __post_init__(self) -> None:
        if self.arity < 1:
            raise ValueError(f"relace {self.name!r}: arita musí být >= 1")


@dataclass(frozen=True)
class Atom:
    """Aplikace relace na termy; jednotka pravdivosti."""
    relation: Relation
    args: tuple[Term, ...]

    def __post_init__(self) -> None:
        if len(self.args) != self.relation.arity:
            raise ValueError(
                f"atom {self.relation.name}: {len(self.args)} argumentů, "
                f"arita je {self.relation.arity}")

    @property
    def ground(self) -> bool:
        return all(is_ground(a) for a in self.args)


def atom_key(atom: Atom) -> str:
    """Stabilní řadicí klíč atomu."""
    args = ",".join(term_key(a) for a in atom.args)
    return f"{atom.relation.name}/{atom.relation.arity}({args})"


@dataclass(frozen=True)
class Literal:
    """Atom s polaritou; záporný literál je plnohodnotné tvrzení (INV-1)."""
    atom: Atom
    positive: bool = True

    def negated(self) -> "Literal":
        return Literal(self.atom, not self.positive)
```

- [ ] **Step 4: Ověřit, že testy procházejí**

Run: `./run-python -m unittest cb_logic.tests.test_terms -v`
Expected: PASS (všech 10)

- [ ] **Step 5: Commit**

```bash
git add cb_logic/__init__.py cb_logic/terms.py cb_logic/tests/
git commit -m "cb_logic: termy, relace, atomy a literály (fáze 2, KNOWLEDGE_MODEL § 2–3)"
```

---

### Task 2: AST výrazů (`cb_logic/expressions.py`)

**Files:**
- Create: `cb_logic/expressions.py`
- Test: `cb_logic/tests/test_expressions.py`

**Interfaces:**
- Consumes: `Atom`, `Literal`, `Variable`, `Term`, `atom_key` z Task 1.
- Produces (pro Task 3+):
  - Frozen uzly: `Const(value: bool)`, `AtomRef(atom: Atom)`, `Not(operand)`, `And(operands: tuple)`, `Or(operands: tuple)`, `Implies(antecedent, consequent)`, `Equiv(left, right)`; alias `Expression`
  - `conj(*exprs) -> Expression`, `disj(*exprs) -> Expression` — zploští vnořené And/And a Or/Or; jeden operand → vrací jej; nula operandů → `ValueError`
  - `from_literal(lit: Literal) -> Expression`
  - `atoms(expr) -> tuple[Atom, ...]` — deduplikované, seřazené dle `atom_key`
  - `substitute(expr, binding: dict[Variable, Term]) -> Expression` — dosazení v argumentech atomů; nenavázaná proměnná zůstává
  - `to_text(expr) -> str` — kanonický uzávorkovaný zápis

- [ ] **Step 1: Napsat padající testy**

```python
"""Testy AST výrazů — LOGIC_SEMANTICS.md § 1."""
import unittest

from cb_logic.terms import Atom, Entity, Literal, Relation, Value, Variable
from cb_logic.expressions import (And, AtomRef, Const, Equiv, Implies, Not,
                                  Or, atoms, conj, disj, from_literal,
                                  substitute, to_text)

P = Relation("p", 1)
Q = Relation("q", 1)
A_ = Atom(P, (Entity("a"),))
B_ = Atom(Q, (Entity("b"),))


class TestConstruction(unittest.TestCase):
    def test_vyrazy_jsou_hodnoty(self):
        self.assertEqual(Not(AtomRef(A_)), Not(AtomRef(A_)))
        self.assertEqual(len({conj(AtomRef(A_), AtomRef(B_)),
                              conj(AtomRef(A_), AtomRef(B_))}), 1)

    def test_conj_zplosti_a_jeden_operand_vraci_primo(self):
        inner = conj(AtomRef(A_), AtomRef(B_))
        flat = conj(inner, AtomRef(A_))
        self.assertIsInstance(flat, And)
        self.assertEqual(len(flat.operands), 3)
        self.assertEqual(conj(AtomRef(A_)), AtomRef(A_))

    def test_disj_nula_operandu_je_chyba(self):
        with self.assertRaises(ValueError):
            disj()

    def test_implies_se_neprepisuje(self):
        e = Implies(AtomRef(A_), AtomRef(B_))
        self.assertIsInstance(e, Implies)  # strukturu nese vysvětlení

    def test_from_literal(self):
        self.assertEqual(from_literal(Literal(A_)), AtomRef(A_))
        self.assertEqual(from_literal(Literal(A_, positive=False)),
                         Not(AtomRef(A_)))


class TestAtoms(unittest.TestCase):
    def test_deduplikovane_a_deterministicky_serazene(self):
        e = disj(AtomRef(B_), Not(AtomRef(A_)), AtomRef(B_))
        self.assertEqual(atoms(e), (A_, B_))  # p/1 < q/1 dle atom_key

    def test_const_nema_atomy(self):
        self.assertEqual(atoms(Const(True)), ())


class TestSubstitute(unittest.TestCase):
    def test_dosazeni_promenne(self):
        x = Variable("X")
        e = Implies(AtomRef(Atom(P, (x,))), AtomRef(Atom(Q, (x,))))
        g = substitute(e, {x: Entity("petr")})
        self.assertEqual(
            g, Implies(AtomRef(Atom(P, (Entity("petr"),))),
                       AtomRef(Atom(Q, (Entity("petr"),)))))

    def test_nenavazana_promenna_zustava(self):
        x, y = Variable("X"), Variable("Y")
        e = AtomRef(Atom(P, (x,)))
        self.assertEqual(substitute(e, {y: Entity("a")}), e)

    def test_substituce_nemutuje(self):
        x = Variable("X")
        e = AtomRef(Atom(P, (x,)))
        substitute(e, {x: Entity("a")})
        self.assertEqual(e, AtomRef(Atom(P, (x,))))


class TestToText(unittest.TestCase):
    def test_kanonicky_zapis(self):
        e = disj(conj(AtomRef(A_), AtomRef(B_)), Not(AtomRef(A_)))
        self.assertEqual(
            to_text(e),
            "((p(E:a) AND q(E:b)) OR (NOT p(E:a)))")

    def test_konstanty_a_ekvivalence(self):
        self.assertEqual(to_text(Const(True)), "TRUE")
        self.assertEqual(to_text(Equiv(AtomRef(A_), Const(False))),
                         "(p(E:a) EQUIV FALSE)")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ověřit, že padají**

Run: `./run-python -m unittest cb_logic.tests.test_expressions -v`
Expected: FAIL — `ModuleNotFoundError: cb_logic.expressions`

- [ ] **Step 3: Implementovat `cb_logic/expressions.py`**

```python
"""AST logických výrazů — LOGIC_SEMANTICS.md § 1.

Výraz je strom hodnot, nikdy string. Implies/Equiv se při konstrukci
nepřepisují na AND/OR/NOT — strukturu, kterou uživatel vyslovil, nese
vysvětlení; normalizace je věc pohledů. Pomocné konstruktory conj/disj
jen zplošťují týž druh spojky.
"""
from __future__ import annotations

from dataclasses import dataclass

from cb_logic.terms import Atom, Literal, Term, Variable, atom_key


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
    from cb_logic.terms import term_key
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
```

- [ ] **Step 4: Ověřit, že testy procházejí**

Run: `./run-python -m unittest cb_logic.tests.test_expressions -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cb_logic/expressions.py cb_logic/tests/test_expressions.py
git commit -m "cb_logic: AST výrazů — konstrukce, atomy, substituce, kanonický zápis"
```

---

### Task 3: Dvouhodnotová sémantika a tabulkové orákulum (`cb_logic/semantics.py`)

**Files:**
- Create: `cb_logic/semantics.py`
- Test: `cb_logic/tests/test_semantics.py`

**Interfaces:**
- Consumes: `Expression` a uzly z Task 2, `Atom`, `atom_key` z Task 1.
- Produces (pro Task 4–5):
  - `Truth(Enum)`: `TRUE`, `FALSE`, `UNKNOWN`
  - `Decision(Enum)`: `YES`, `NO`, `INCOMPLETE`
  - `class UnboundAtomError(LookupError)`
  - `evaluate(expr, assignment: Mapping[Atom, bool]) -> bool` — chybějící atom = `UnboundAtomError` (hlasitě, INV-9)
  - `truth_table(expr) -> Iterator[tuple[dict[Atom, bool], bool]]` — řádky v lexikografickém pořadí hodnot `(False < True)` nad atomy dle `atom_key`; výraz bez atomů → jeden řádek s prázdným ohodnocením
  - `DEFAULT_MAX_ATOMS = 20`
  - `DecisionResult(verdict: Decision, witness: tuple[tuple[Atom, bool], ...] | None, explored: int)` — frozen; witness = protipříklad (tautologie NO) / splňující ohodnocení (satisfiable YES, contradiction NO)
  - `is_tautology(expr, *, max_atoms=DEFAULT_MAX_ATOMS) -> DecisionResult`
  - `is_contradiction(expr, *, max_atoms=DEFAULT_MAX_ATOMS) -> DecisionResult`
  - `is_satisfiable(expr, *, max_atoms=DEFAULT_MAX_ATOMS) -> DecisionResult`

- [ ] **Step 1: Napsat padající testy**

```python
"""Testy dvouhodnotové sémantiky a tabulky — LOGIC_SEMANTICS.md § 2–3."""
import unittest

from cb_logic.terms import Atom, Entity, Relation
from cb_logic.expressions import (AtomRef, Const, Equiv, Implies, Not, conj,
                                  disj)
from cb_logic.semantics import (Decision, UnboundAtomError, evaluate,
                                is_contradiction, is_satisfiable,
                                is_tautology, truth_table)

A_ = Atom(Relation("p", 1), (Entity("a"),))
B_ = Atom(Relation("q", 1), (Entity("b"),))
a, b = AtomRef(A_), AtomRef(B_)


class TestEvaluate(unittest.TestCase):
    def test_spojky(self):
        env = {A_: True, B_: False}
        self.assertFalse(evaluate(conj(a, b), env))
        self.assertTrue(evaluate(disj(a, b), env))
        self.assertFalse(evaluate(Not(a), env))
        self.assertFalse(evaluate(Implies(a, b), env))
        self.assertTrue(evaluate(Implies(b, a), env))
        self.assertFalse(evaluate(Equiv(a, b), env))
        self.assertTrue(evaluate(Const(True), {}))

    def test_chybejici_atom_je_hlasita_chyba(self):
        with self.assertRaises(UnboundAtomError):
            evaluate(conj(a, b), {A_: True})


class TestTruthTable(unittest.TestCase):
    def test_pocet_a_poradi_radku(self):
        rows = list(truth_table(conj(a, b)))
        self.assertEqual(len(rows), 4)
        self.assertEqual([r[0][A_] for r in rows], [False, False, True, True])
        self.assertEqual([r[0][B_] for r in rows], [False, True, False, True])
        self.assertEqual([r[1] for r in rows], [False, False, False, True])

    def test_vyraz_bez_atomu_ma_jeden_radek(self):
        rows = list(truth_table(Const(False)))
        self.assertEqual(rows, [({}, False)])


class TestDecisions(unittest.TestCase):
    def test_tautologie(self):
        r = is_tautology(disj(a, Not(a)))
        self.assertEqual(r.verdict, Decision.YES)
        self.assertIsNone(r.witness)

    def test_tautologie_ne_s_protiprikladem(self):
        r = is_tautology(a)
        self.assertEqual(r.verdict, Decision.NO)
        self.assertEqual(dict(r.witness), {A_: False})

    def test_kontradikce(self):
        self.assertEqual(is_contradiction(conj(a, Not(a))).verdict, Decision.YES)
        r = is_contradiction(a)
        self.assertEqual(r.verdict, Decision.NO)
        self.assertEqual(dict(r.witness), {A_: True})

    def test_splnitelnost_se_svedkem(self):
        r = is_satisfiable(conj(a, Not(b)))
        self.assertEqual(r.verdict, Decision.YES)
        self.assertEqual(dict(r.witness), {A_: True, B_: False})

    def test_limit_vraci_incomplete_ne_verdikt(self):
        exprs = [AtomRef(Atom(Relation("r", 1), (Entity(f"e{i}"),)))
                 for i in range(3)]
        r = is_tautology(disj(*exprs), max_atoms=2)
        self.assertEqual(r.verdict, Decision.INCOMPLETE)
        self.assertEqual(r.explored, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ověřit, že padají**

Run: `./run-python -m unittest cb_logic.tests.test_semantics -v`
Expected: FAIL — `ModuleNotFoundError: cb_logic.semantics`

- [ ] **Step 3: Implementovat `cb_logic/semantics.py`** (dvouhodnotová část)

```python
"""Pravdivostní sémantika — LOGIC_SEMANTICS.md § 2–4.

Tabulka je pohled a referenční orákulum (kap. 20.6 návrhu): pomalá,
zjevně správná. Rychlejší rozhodovací cesty (fáze 5–7) se měří proti ní.
Limit vrací INCOMPLETE — nedopočítaný výsledek se nikdy nevydává za
verdikt (zadání § 24).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Mapping

from cb_logic.expressions import (And, AtomRef, Const, Equiv, Expression,
                                  Implies, Not, Or, atoms)
from cb_logic.terms import Atom


class Truth(Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class Decision(Enum):
    YES = "yes"
    NO = "no"
    INCOMPLETE = "incomplete"


DEFAULT_MAX_ATOMS = 20


class UnboundAtomError(LookupError):
    """Úplné ohodnocení nezná atom — chyba volajícího, ne UNKNOWN (INV-9)."""


def evaluate(expr: Expression, assignment: Mapping[Atom, bool]) -> bool:
    """Dvouhodnotové vyhodnocení nad úplným ohodnocením."""
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, AtomRef):
        try:
            return assignment[expr.atom]
        except KeyError:
            raise UnboundAtomError(expr.atom) from None
    if isinstance(expr, Not):
        return not evaluate(expr.operand, assignment)
    if isinstance(expr, And):
        return all(evaluate(o, assignment) for o in expr.operands)
    if isinstance(expr, Or):
        return any(evaluate(o, assignment) for o in expr.operands)
    if isinstance(expr, Implies):
        return (not evaluate(expr.antecedent, assignment)
                or evaluate(expr.consequent, assignment))
    return evaluate(expr.left, assignment) == evaluate(expr.right, assignment)


def truth_table(expr: Expression) -> Iterator[tuple[dict[Atom, bool], bool]]:
    """Všechna ohodnocení atomů výrazu v kanonickém pořadí.

    Atomy dle atom_key; řádky lexikograficky, False < True (poslední atom
    se mění nejrychleji). Výraz bez atomů má jeden řádek.
    """
    atom_list = atoms(expr)
    for values in itertools.product((False, True), repeat=len(atom_list)):
        assignment = dict(zip(atom_list, values))
        yield assignment, evaluate(expr, assignment)


@dataclass(frozen=True)
class DecisionResult:
    """Verdikt + svědek (protipříklad/model) + kolik řádků se prozkoumalo."""
    verdict: Decision
    witness: tuple[tuple[Atom, bool], ...] | None
    explored: int


def _decide(expr: Expression, *, max_atoms: int,
            stop_value: bool) -> DecisionResult:
    """Společné jádro: hledá řádek s hodnotou stop_value.

    Najde-li ho, verdikt je NO-pro-univerzální-otázku (svědek = ten řádek);
    projde-li vše bez nálezu, YES.
    """
    atom_list = atoms(expr)
    if len(atom_list) > max_atoms:
        return DecisionResult(Decision.INCOMPLETE, None, 0)
    explored = 0
    for assignment, value in truth_table(expr):
        explored += 1
        if value is stop_value:
            witness = tuple(sorted(assignment.items(),
                                   key=lambda kv: _key(kv[0])))
            return DecisionResult(Decision.NO, witness, explored)
    return DecisionResult(Decision.YES, None, explored)


def _key(atom: Atom) -> str:
    from cb_logic.terms import atom_key
    return atom_key(atom)


def is_tautology(expr: Expression, *,
                 max_atoms: int = DEFAULT_MAX_ATOMS) -> DecisionResult:
    """Platí ve všech ohodnoceních? NO nese protipříklad."""
    return _decide(expr, max_atoms=max_atoms, stop_value=False)


def is_contradiction(expr: Expression, *,
                     max_atoms: int = DEFAULT_MAX_ATOMS) -> DecisionResult:
    """Neplatí v žádném ohodnocení? NO nese splňující ohodnocení."""
    return _decide(expr, max_atoms=max_atoms, stop_value=True)


def is_satisfiable(expr: Expression, *,
                   max_atoms: int = DEFAULT_MAX_ATOMS) -> DecisionResult:
    """Existuje splňující ohodnocení? YES nese svědka."""
    inner = is_contradiction(expr, max_atoms=max_atoms)
    if inner.verdict is Decision.INCOMPLETE:
        return inner
    if inner.verdict is Decision.NO:
        return DecisionResult(Decision.YES, inner.witness, inner.explored)
    return DecisionResult(Decision.NO, None, inner.explored)
```

- [ ] **Step 4: Ověřit, že testy procházejí**

Run: `./run-python -m unittest cb_logic.tests.test_semantics -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cb_logic/semantics.py cb_logic/tests/test_semantics.py
git commit -m "cb_logic: dvouhodnotová evaluace, pravdivostní tabulka a rozhodovací orákulum s limitem"
```

---

### Task 4: Parciální vyhodnocení K3 (`evaluate_partial` v `semantics.py`)

**Files:**
- Modify: `cb_logic/semantics.py` (přidat `evaluate_partial`)
- Test: přidat do `cb_logic/tests/test_semantics.py`

**Interfaces:**
- Consumes: Task 3.
- Produces: `evaluate_partial(expr, partial: Mapping[Atom, bool]) -> Truth` — silná Kleeneho K3; atom mimo `partial` = `UNKNOWN` (zde legální — částečné ohodnocení je částečné z definice).

- [ ] **Step 1: Napsat padající testy** (přidat do `test_semantics.py`)

```python
from cb_logic.semantics import Truth, evaluate_partial


class TestEvaluatePartial(unittest.TestCase):
    def test_kleene_tabulky(self):
        self.assertEqual(evaluate_partial(Not(a), {}), Truth.UNKNOWN)
        self.assertEqual(evaluate_partial(conj(a, b), {A_: False}), Truth.FALSE)
        self.assertEqual(evaluate_partial(conj(a, b), {A_: True}), Truth.UNKNOWN)
        self.assertEqual(evaluate_partial(disj(a, b), {A_: True}), Truth.TRUE)
        self.assertEqual(evaluate_partial(disj(a, b), {A_: False}), Truth.UNKNOWN)
        self.assertEqual(evaluate_partial(Implies(a, b), {A_: False}), Truth.TRUE)
        self.assertEqual(evaluate_partial(Implies(a, b), {B_: True}), Truth.TRUE)
        self.assertEqual(evaluate_partial(Implies(a, b), {A_: True, B_: False}),
                         Truth.FALSE)
        self.assertEqual(evaluate_partial(Equiv(a, b), {A_: True}), Truth.UNKNOWN)

    def test_epistemicke_cteni_tautologie(self):
        # A OR NOT A s neznámým A je v K3 UNKNOWN — nutnost rozhoduje tabulka.
        self.assertEqual(evaluate_partial(disj(a, Not(a)), {}), Truth.UNKNOWN)
        self.assertEqual(is_tautology(disj(a, Not(a))).verdict, Decision.YES)

    def test_shoda_s_uplnym_ohodnocenim(self):
        env = {A_: True, B_: False}
        e = Equiv(Implies(a, b), disj(Not(a), b))
        expected = Truth.TRUE if evaluate(e, env) else Truth.FALSE
        self.assertEqual(evaluate_partial(e, env), expected)
```

- [ ] **Step 2: Ověřit, že padají**

Run: `./run-python -m unittest cb_logic.tests.test_semantics -v`
Expected: FAIL — `ImportError: cannot import name 'evaluate_partial'`

- [ ] **Step 3: Implementovat `evaluate_partial`** (přidat do `semantics.py`)

```python
def evaluate_partial(expr: Expression,
                     partial: Mapping[Atom, bool]) -> Truth:
    """Silná Kleeneho K3 nad částečným ohodnocením (LOGIC_SEMANTICS § 4).

    UNKNOWN je epistemické „nevím": není-li výsledek UNKNOWN, každé úplné
    doplnění dá touž hodnotu (monotonie — testovaná vlastnost).
    """
    if isinstance(expr, Const):
        return Truth.TRUE if expr.value else Truth.FALSE
    if isinstance(expr, AtomRef):
        if expr.atom not in partial:
            return Truth.UNKNOWN
        return Truth.TRUE if partial[expr.atom] else Truth.FALSE
    if isinstance(expr, Not):
        inner = evaluate_partial(expr.operand, partial)
        if inner is Truth.UNKNOWN:
            return Truth.UNKNOWN
        return Truth.FALSE if inner is Truth.TRUE else Truth.TRUE
    if isinstance(expr, And):
        values = [evaluate_partial(o, partial) for o in expr.operands]
        if Truth.FALSE in values:
            return Truth.FALSE
        if Truth.UNKNOWN in values:
            return Truth.UNKNOWN
        return Truth.TRUE
    if isinstance(expr, Or):
        values = [evaluate_partial(o, partial) for o in expr.operands]
        if Truth.TRUE in values:
            return Truth.TRUE
        if Truth.UNKNOWN in values:
            return Truth.UNKNOWN
        return Truth.FALSE
    if isinstance(expr, Implies):
        ante = evaluate_partial(expr.antecedent, partial)
        cons = evaluate_partial(expr.consequent, partial)
        if ante is Truth.FALSE or cons is Truth.TRUE:
            return Truth.TRUE
        if ante is Truth.TRUE and cons is Truth.FALSE:
            return Truth.FALSE
        return Truth.UNKNOWN
    left = evaluate_partial(expr.left, partial)
    right = evaluate_partial(expr.right, partial)
    if Truth.UNKNOWN in (left, right):
        return Truth.UNKNOWN
    return Truth.TRUE if left is right else Truth.FALSE
```

- [ ] **Step 4: Ověřit, že testy procházejí**

Run: `./run-python -m unittest cb_logic.tests.test_semantics -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cb_logic/semantics.py cb_logic/tests/test_semantics.py
git commit -m "cb_logic: parciální vyhodnocení silnou Kleeneho K3"
```

---

### Task 5: Property a metamorfní testy s vlastním generátorem

**Files:**
- Create: `cb_logic/tests/generators.py`
- Test: `cb_logic/tests/test_properties.py`

**Interfaces:**
- Consumes: vše z Tasků 1–4.
- Produces: `random_expression(rng: random.Random, atom_pool: tuple[Atom, ...], max_depth: int) -> Expression`; `SEED = 328` (tradice repozitáře), `SAMPLES = 200`.

- [ ] **Step 1: Napsat generátor**

```python
"""Deterministický generátor náhodných výrazů pro property testy.

Náhoda výhradně z předaného random.Random se semínkem — žádný globální
stav (LOGIC_SEMANTICS § 8).
"""
from __future__ import annotations

import random

from cb_logic.expressions import (AtomRef, Const, Equiv, Expression, Implies,
                                  Not, conj, disj)
from cb_logic.terms import Atom

SEED = 328
SAMPLES = 200


def random_expression(rng: random.Random, atom_pool: tuple[Atom, ...],
                      max_depth: int) -> Expression:
    """Rekurzivní generátor; listy jsou atomy (většina) a konstanty (zřídka)."""
    if max_depth <= 0 or rng.random() < 0.3:
        if rng.random() < 0.1:
            return Const(rng.random() < 0.5)
        return AtomRef(rng.choice(atom_pool))
    kind = rng.choice(("not", "and", "or", "implies", "equiv"))
    child = lambda: random_expression(rng, atom_pool, max_depth - 1)
    if kind == "not":
        return Not(child())
    if kind == "and":
        return conj(*(child() for _ in range(rng.randint(2, 3))))
    if kind == "or":
        return disj(*(child() for _ in range(rng.randint(2, 3))))
    if kind == "implies":
        return Implies(child(), child())
    return Equiv(child(), child())
```

- [ ] **Step 2: Napsat property testy** (`test_properties.py`)

Testy — každý běží přes `SAMPLES` výrazů z `random.Random(SEED)` nad poolem
4 atomů (`p(a) q(b) r(c) s(d)`), `max_depth=4`; ekvivalence dvou výrazů se
ověřuje shodou celých pravdivostních tabulek (nad sjednocením atomů obou stran):

```python
"""Property a metamorfní testy — LOGIC_SEMANTICS.md § 5.

Ekvivalence ≡ znamená: shodná hodnota pro VŠECHNA ohodnocení sjednocení
atomů obou stran. Pojistka proti vakuu (T-13): generátor musí doložit,
že vyrobil negace, implikace, ekvivalence i hluboké výrazy.
"""
import itertools
import random
import unittest

from cb_logic.expressions import (And, AtomRef, Equiv, Implies, Not, Or,
                                  atoms, conj, disj)
from cb_logic.semantics import (Truth, evaluate, evaluate_partial,
                                is_tautology)
from cb_logic.terms import Atom, Entity, Relation
from cb_logic.tests.generators import SAMPLES, SEED, random_expression

POOL = tuple(Atom(Relation(n, 1), (Entity(e),))
             for n, e in (("p", "a"), ("q", "b"), ("r", "c"), ("s", "d")))


def all_assignments(atom_set):
    for values in itertools.product((False, True), repeat=len(atom_set)):
        yield dict(zip(atom_set, values))


def equivalent(e1, e2):
    """Shodná hodnota pro všechna ohodnocení sjednocení atomů."""
    union = tuple(sorted(set(atoms(e1)) | set(atoms(e2)),
                         key=lambda a: a.relation.name))
    return all(evaluate(e1, env) == evaluate(e2, env)
               for env in all_assignments(union))


class TestAlgebraicLaws(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(SEED)

    def samples(self, n=SAMPLES):
        for _ in range(n):
            yield random_expression(self.rng, POOL, max_depth=4)

    def test_dvoji_negace(self):
        for e in self.samples():
            self.assertTrue(equivalent(Not(Not(e)), e))

    def test_komutativita_a_absorpce(self):
        for e1 in self.samples(SAMPLES // 2):
            e2 = random_expression(self.rng, POOL, max_depth=3)
            self.assertTrue(equivalent(conj(e1, e2), conj(e2, e1)))
            self.assertTrue(equivalent(disj(e1, e2), disj(e2, e1)))
            self.assertTrue(equivalent(disj(e1, conj(e1, e2)), e1))
            self.assertTrue(equivalent(conj(e1, disj(e1, e2)), e1))

    def test_de_morgan_a_implikace(self):
        for e1 in self.samples(SAMPLES // 2):
            e2 = random_expression(self.rng, POOL, max_depth=3)
            self.assertTrue(equivalent(Not(conj(e1, e2)),
                                       disj(Not(e1), Not(e2))))
            self.assertTrue(equivalent(Not(disj(e1, e2)),
                                       conj(Not(e1), Not(e2))))
            self.assertTrue(equivalent(Implies(e1, e2), disj(Not(e1), e2)))


class TestK3Monotonicity(unittest.TestCase):
    def test_rozsireni_nemeni_neunknown_vysledek(self):
        rng = random.Random(SEED)
        checked = 0
        for _ in range(SAMPLES):
            e = random_expression(rng, POOL, max_depth=4)
            atom_list = atoms(e)
            known = {a: rng.random() < 0.5 for a in atom_list
                     if rng.random() < 0.5}
            partial_value = evaluate_partial(e, known)
            if partial_value is Truth.UNKNOWN:
                continue
            checked += 1
            missing = [a for a in atom_list if a not in known]
            for values in itertools.product((False, True),
                                            repeat=len(missing)):
                env = dict(known)
                env.update(zip(missing, values))
                total = Truth.TRUE if evaluate(e, env) else Truth.FALSE
                self.assertEqual(total, partial_value)
        self.assertGreater(checked, 20)  # T-13: vlastnost se skutečně měřila


class TestMetamorphic(unittest.TestCase):
    def test_prejmenovani_atomu_zachova_tabulku(self):
        rng = random.Random(SEED)
        renamed_pool = tuple(Atom(Relation(f"rel_{i}", 1), (Entity(f"x{i}"),))
                             for i in range(len(POOL)))
        for _ in range(SAMPLES // 2):
            e = random_expression(rng, POOL, max_depth=4)
            mapping = dict(zip(POOL, renamed_pool))
            renamed = _rename(e, mapping)
            for env in all_assignments(atoms(e)):
                renamed_env = {mapping[a]: v for a, v in env.items()}
                self.assertEqual(evaluate(e, env),
                                 evaluate(renamed, renamed_env))

    def test_irelevantni_atom_nemeni_verdikt_tautologie(self):
        rng = random.Random(SEED)
        extra = AtomRef(Atom(Relation("noise", 1), (Entity("z"),)))
        for _ in range(SAMPLES // 4):
            e = random_expression(rng, POOL, max_depth=3)
            padded = conj(e, disj(extra, Not(extra)))
            self.assertEqual(is_tautology(e).verdict,
                             is_tautology(padded).verdict)


def _rename(expr, mapping):
    if isinstance(expr, AtomRef):
        return AtomRef(mapping[expr.atom])
    if isinstance(expr, Not):
        return Not(_rename(expr.operand, mapping))
    if isinstance(expr, And):
        return And(tuple(_rename(o, mapping) for o in expr.operands))
    if isinstance(expr, Or):
        return Or(tuple(_rename(o, mapping) for o in expr.operands))
    if isinstance(expr, Implies):
        return Implies(_rename(expr.antecedent, mapping),
                       _rename(expr.consequent, mapping))
    if isinstance(expr, Equiv):
        return Equiv(_rename(expr.left, mapping),
                     _rename(expr.right, mapping))
    return expr


class TestGeneratorVacuumGuard(unittest.TestCase):
    """T-13: generátor musí doložit, že testy měly co měřit."""

    def test_pokryti_druhu_uzlu_a_hloubky(self):
        rng = random.Random(SEED)
        kinds = set()
        max_atoms_seen = 0
        deep = 0
        for _ in range(SAMPLES):
            e = random_expression(rng, POOL, max_depth=4)
            kinds |= {type(n).__name__ for n in _walk(e)}
            max_atoms_seen = max(max_atoms_seen, len(atoms(e)))
            if _depth(e) >= 4:
                deep += 1
        self.assertLessEqual({"Not", "And", "Or", "Implies", "Equiv"}, kinds)
        self.assertGreaterEqual(max_atoms_seen, 4)
        self.assertGreater(deep, 10)


def _walk(expr):
    yield expr
    for child in _children(expr):
        yield from _walk(child)


def _children(expr):
    if isinstance(expr, Not):
        return (expr.operand,)
    if isinstance(expr, (And, Or)):
        return expr.operands
    if isinstance(expr, Implies):
        return (expr.antecedent, expr.consequent)
    if isinstance(expr, Equiv):
        return (expr.left, expr.right)
    return ()


def _depth(expr):
    children = _children(expr)
    if not children:
        return 1
    return 1 + max(_depth(c) for c in children)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Spustit — testy musí projít; při pádu je to nález, ne důvod měnit test**

Run: `./run-python -m unittest cb_logic.tests.test_properties -v`
Expected: PASS (vlastnosti platí z konstrukce sémantiky; pád = chyba implementace, opravuje se implementace)

- [ ] **Step 4: Commit**

```bash
git add cb_logic/tests/generators.py cb_logic/tests/test_properties.py
git commit -m "cb_logic: property a metamorfní testy s deterministickým generátorem (T-13 pojistka)"
```

---

### Task 6: Veřejné API balíku a závěrečná kontrola

**Files:**
- Modify: `cb_logic/__init__.py`
- Create: `cb_logic/README.md`

**Interfaces:**
- Produces: veřejná jména balíku (jediná, na která smí mířit budoucí import z jiných modulů).

- [ ] **Step 1: Naplnit `cb_logic/__init__.py`**

```python
"""cb_logic — formální jádro znalosti a logiky.

Čistá knihovna (stdlib, žádný import z cb_*): termy, atomy, výrazy
a pravdivostní sémantika. Specifikace: KNOWLEDGE_MODEL.md,
LOGIC_SEMANTICS.md v kořeni repozitáře.
"""
from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Value,
                            Variable, atom_key, is_ground, term_key)
from cb_logic.expressions import (And, AtomRef, Const, Equiv, Expression,
                                  Implies, Not, Or, atoms, conj, disj,
                                  from_literal, substitute, to_text)
from cb_logic.semantics import (DEFAULT_MAX_ATOMS, Decision, DecisionResult,
                                Truth, UnboundAtomError, evaluate,
                                evaluate_partial, is_contradiction,
                                is_satisfiable, is_tautology, truth_table)

__all__ = [
    "Atom", "Domain", "Entity", "Literal", "Relation", "Value", "Variable",
    "atom_key", "is_ground", "term_key",
    "And", "AtomRef", "Const", "Equiv", "Expression", "Implies", "Not", "Or",
    "atoms", "conj", "disj", "from_literal", "substitute", "to_text",
    "DEFAULT_MAX_ATOMS", "Decision", "DecisionResult", "Truth",
    "UnboundAtomError", "evaluate", "evaluate_partial", "is_contradiction",
    "is_satisfiable", "is_tautology", "truth_table",
]
```

- [ ] **Step 2: Napsat `cb_logic/README.md`** (krátký: co modul je, odkaz na specifikace, jak spustit testy, co vědomě neřeší — inference/constrainty/modely jsou fáze 3+)

```markdown
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
```

- [ ] **Step 3: Celý testovací běh — nic se nesmí rozbít**

Run: `./run-python -m unittest discover -s cb_logic -t .` a poté celoprojektový
`./run-python -m unittest discover -s . -p "test_*.py" -t .`
Expected: cb_logic zeleně; celoprojektový běh beze změny proti stavu před fází 2
(787 + nové testy).

- [ ] **Step 4: Ověřit zákaz importů z cb_***

Run: `grep -rn "^from cb_\|^import cb_" cb_logic/ | grep -v "from cb_logic\|import cb_logic"`
Expected: prázdný výstup.

- [ ] **Step 5: Commit**

```bash
git add cb_logic/__init__.py cb_logic/README.md
git commit -m "cb_logic: veřejné API balíku a README"
```

---

## Self-review

- **Spec coverage:** LOGIC_SEMANTICS § 10 body 1–5 → Tasky 1, 2, 3+4, 5, (6 = API);
  § 1 AST → Task 2; § 2 → Task 3; § 3 tabulka+verdikt+limit → Task 3; § 4 K3 →
  Task 4; § 5 zákony+metamorfní+T-13 → Task 5; § 8 determinismus → průřezově
  (klíče v Task 1, semínko v Task 5). KNOWLEDGE_MODEL § 2–3 → Task 1.
  Mimo rozsah (fáze 3+): KnowledgeBase, constrainty, inference — vědomě.
- **Placeholders:** žádné.
- **Typová konzistence:** `DecisionResult.witness` je `tuple[tuple[Atom, bool], ...]`
  (testy używají `dict(r.witness)`); `Truth`/`Decision` oddělené enumy (K3 hodnota
  vs. verdikt rozhodnutí); `atoms()` vrací `tuple` seřazený dle `atom_key` —
  test v Task 2 spoléhá na `p/1 < q/1`, což platí lexikograficky.
