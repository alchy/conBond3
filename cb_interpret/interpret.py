"""Interpretace věty — strukturální vzory nad UD (INTERPRETATION.md § 1).

Kód nezná jediné slovo přirozeného jazyka: rozhoduje strom (deprel),
slovní druhy (upos) a rysy (PronType, Polarity). Jména relací a entit
vznikají z lemmat vstupu — vrstva jen NAVRHUJE (INV-11); o přijetí
rozhoduje validace báze. Co vzor neunese, je poctivě `unparsed`
s důvodem — žádné hádání.

Operátorová slovesa (moci, chtít…) mají VLASTNÍ cestu: jejich mapování na
formální operaci je UČENÉ (LANGUAGE_LEARNING.md) — nezná ho kód, nese ho
store vzorů. Bez naučeného vzoru vzniká `needs_pattern` (systém se doptá),
nikdy hádání.
"""
from __future__ import annotations

from dataclasses import dataclass

from cb_logic import (Atom, AtomRef, Entity, Literal, Relation, Rule, Value,
                      Variable)
from cb_interpret.patterns import Operation, StructuralSignature

NOMINAL_UPOS = {"NOUN", "PROPN", "ADJ"}


@dataclass(frozen=True)
class Candidate:
    """Kandidátní interpretace jedné věty; není to znalost."""
    kind: str    # fact | rule | query | modal_query | needs_pattern | unparsed
    source_text: str
    literal: Literal | None = None
    rule: Rule | None = None
    relations: tuple[Relation, ...] = ()
    entities: tuple[Entity, ...] = ()
    note: str | None = None
    operation: Operation | None = None            # jen modal_query
    signature: StructuralSignature | None = None  # modal_query / needs_pattern
    negated: bool = False


def interpret_sentence(tokens, text: str, *, patterns=None,
                       domain: str = "entita",
                       question_mark: str = "?") -> Candidate:
    children: dict[int, list] = {}
    root = None
    for token in tokens:
        if token.head == 0:
            root = token
        children.setdefault(token.head, []).append(token)
    if root is None:
        return _unparsed(text, "chybí kořen rozboru")
    question = text.rstrip().endswith(question_mark)

    if root.upos in NOMINAL_UPOS and _kids(children, root, "cop"):
        return _copular(children, root, text, question, domain)
    if root.upos == "VERB" and _kids(children, root, "xcomp"):
        return _operator(children, root, text, patterns)
    if root.upos == "VERB":
        return _verbal(children, root, text, question)
    return _unparsed(text, f"vzor věty mimo rozsah (kořen {root.upos})")


def _copular(children, root, text, question, domain) -> Candidate:
    subjects = _kids(children, root, "nsubj")
    if not subjects:
        return _unparsed(text, "kopula bez podmětu")
    subject = subjects[0]
    negated = _negated(root) or any(_negated(c)
                                    for c in _kids(children, root, "cop"))
    determiners = _kids(children, subject, "det")
    prontypes: set[str] = set()
    for det in determiners:
        prontypes |= _prontype(det)
    class_relation = Relation(root.lemma, 1)

    universal = "Tot" in prontypes
    negative_universal = "Neg" in prontypes
    generic = subject.upos == "NOUN" and not determiners
    if universal or negative_universal or generic:
        if question:
            return _unparsed(text, "dotaz na obecné pravidlo mimo rozsah")
        # dvojí zápor češtiny („žádný … není") je jedna logická negace
        head_positive = not (negated or negative_universal)
        subject_relation = Relation(subject.lemma, 1)
        x = Variable("X")
        rule = Rule(((x, domain),),
                    AtomRef(Atom(subject_relation, (x,))),
                    Literal(Atom(class_relation, (x,)), head_positive))
        return Candidate("rule", text, rule=rule,
                         relations=(subject_relation, class_relation))
    if prontypes:
        return _unparsed(text, "determinant podmětu mimo rozsah")
    if subject.upos == "PROPN":
        entity = _entity(subject)
        literal = Literal(Atom(class_relation, (entity,)), not negated)
        return Candidate("query" if question else "fact", text,
                         literal=literal, relations=(class_relation,),
                         entities=(entity,))
    return _unparsed(text, "podmět kopulové věty mimo rozsah")


def _verbal(children, root, text, question) -> Candidate:
    subjects = _kids(children, root, "nsubj")
    if not subjects:
        return _unparsed(text, "sloveso bez podmětu")
    subject = subjects[0]
    if _kids(children, subject, "det"):
        return _unparsed(text, "určený podmět slovesné věty mimo rozsah")
    if subject.upos != "PROPN":
        return _unparsed(text, "obecný podmět slovesné věty mimo rozsah")
    entity = _entity(subject)
    negated = _negated(root)
    atom, entities, relation = _predicate_atom(children, root, entity)
    literal = Literal(atom, not negated)
    return Candidate("query" if question else "fact", text, literal=literal,
                     relations=(relation,), entities=entities)


def _operator(children, root, text, patterns) -> Candidate:
    """Operátorové sloveso s xcomp: matrix podmět řídí vložený přísudek.

    Mapování operátoru na formální operaci je UČENÉ — bez vzoru vzniká
    needs_pattern (systém se doptá z uzavřeného menu), nikdy hádání.
    """
    subjects = _kids(children, root, "nsubj")
    if not subjects:
        return _unparsed(text, "operátorové sloveso bez podmětu")
    subject_entity = _entity(subjects[0])          # kontrola podmětu
    xcomp = _kids(children, root, "xcomp")[0]
    atom, entities, relation = _predicate_atom(children, xcomp, subject_entity)
    negated = _negated(root)
    signature = StructuralSignature(
        root.lemma, has_xcomp=True,
        has_obj=bool(_kids(children, xcomp, "obj")),
        has_obl=bool(_kids(children, xcomp, "obl")))
    literal = Literal(atom)                        # vložená propozice (kladná)

    matched = patterns.match(signature) if patterns is not None else None
    if matched is not None:
        return Candidate("modal_query", text, literal=literal,
                         operation=matched.operation, negated=negated,
                         relations=(relation,), entities=entities,
                         signature=signature)
    return Candidate("needs_pattern", text, literal=literal, negated=negated,
                     relations=(relation,), entities=entities,
                     signature=signature,
                     note=f"neznámé mapování operátoru {root.lemma!r}")


def _predicate_atom(children, verb, subject_entity):
    """Postaví atom z přísudku + jeho argumentů; podmět je dán (kontrola).

    Předložka governující oblik se zataví do jména relace (`jet_na`) —
    táž zásada jako u prostých slovesných vět, jen podmět přichází zvenčí.
    """
    entities = [subject_entity]
    objects = _kids(children, verb, "obj")
    obliques = _kids(children, verb, "obl")
    if objects:
        relation = Relation(verb.lemma, 2)
        second, extra = _term_for(objects[0])
    else:
        with_case = [o for o in obliques if _kids(children, o, "case")]
        if with_case:
            oblique = with_case[0]
            adposition = _kids(children, oblique, "case")[0]
            relation = Relation(f"{verb.lemma}_{adposition.lemma}", 2)
            second, extra = _term_for(oblique)
        else:
            relation = Relation(verb.lemma, 1)
            second, extra = None, ()
    entities.extend(extra)
    args = (subject_entity,) if second is None else (subject_entity, second)
    return Atom(relation, args), tuple(entities), relation


def _kids(children, token, deprel):
    return [c for c in children.get(token.id, [])
            if c.deprel and (c.deprel == deprel
                             or c.deprel.startswith(deprel + ":"))]


def _negated(token) -> bool:
    return bool(token.feats) and token.feats.get("Polarity") == "Neg"


def _prontype(token) -> set[str]:
    if not token.feats or "PronType" not in token.feats:
        return set()
    return set(token.feats["PronType"].split(","))


def _entity(token) -> Entity:
    return Entity(token.lemma.lower(), label=token.form)


def _term_for(token):
    if token.upos == "PROPN":
        entity = _entity(token)
        return entity, (entity,)
    return Value(token.lemma), ()


def _unparsed(text: str, note: str) -> Candidate:
    return Candidate("unparsed", text, note=note)
