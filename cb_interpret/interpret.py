"""Interpretace věty — obecné strukturální vzory nad UD.

Kód nezná jediné slovo přirozeného jazyka: rozhoduje strom (deprel),
slovní druhy (upos) a rysy (PronType, Polarity). Jména relací a entit
vznikají z lemmat vstupu — vrstva jen NAVRHUJE (INV-11).

Zásada (INTERPRETATION_IR.md): tichého zjednodušení, které mění význam,
se vrstva nedopustí. Kopulová věta se složeným přísudkem se rozloží na
strukturovanou reprezentaci (predikace) a sníží do konjunkce faktů/pravidel
tak, aby se NEZTRATILY přívlastky ani předložkové vztahy. Co vzor neunese,
je `unparsed` s důvodem; nejednoznačná reference je doptání, ne hádání.
Každý formální kus nese provenienci (které tokeny ho vytvořily).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from cb_logic import (Atom, AtomRef, Entity, Expression, Literal, Not,
                      Relation, Rule, Value, Variable, conj, from_literal)
from cb_interpret.patterns import Operation, StructuralSignature
from cb_interpret.predication import (Predication, Reference, ReferenceKind,
                                      extract_copular)

NOMINAL_UPOS = {"NOUN", "PROPN", "ADJ"}


@dataclass(frozen=True)
class Candidate:
    """Kandidátní interpretace jedné věty; není to znalost.

    kind: fact | rule | query | modal_query | needs_pattern |
          reference_ambiguous | unparsed
    """
    kind: str
    source_text: str
    literals: tuple[Literal, ...] = ()             # fact: konjunkce faktů
    rules: tuple[Rule, ...] = ()                   # rule: konjunkce pravidel
    query_expr: Expression | None = None           # query: výraz k vyhodnocení
    query_atoms: tuple[Atom, ...] = ()             # atomy dotazu (vysvětlení)
    literal: Literal | None = None                 # modal: propozice
    relations: tuple[Relation, ...] = ()
    entities: tuple[Entity, ...] = ()
    provenance: tuple[tuple[str, int], ...] = ()   # (formální kus, token)
    note: str | None = None
    operation: Operation | None = None
    signature: StructuralSignature | None = None
    negated: bool = False
    predication: Predication | None = None         # reference_ambiguous


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
        pred = extract_copular(children, root, question)
        if pred is None:
            return _unparsed(text, "kopula bez podmětu")
        return _lower_copular(pred, text, domain)
    if root.upos == "VERB" and _kids(children, root, "xcomp"):
        return _operator(children, root, text, patterns)
    if root.upos == "VERB":
        return _verbal(children, root, text, question)
    return _unparsed(text, f"vzor věty mimo rozsah (kořen {root.upos})")


# --- kopulová predikace (obecná, se složeným přísudkem) -----------------

def _lower_copular(pred: Predication, text: str, domain: str) -> Candidate:
    """Predikace → konjunkce faktů/pravidel/dotazu; zachová VŠE."""
    if pred.blockers:
        # Tiché zahození mění význam — kus, který extrakce neunese,
        # větu poctivě shodí (pojistka, expanze § 2.3).
        return _unparsed(text, pred.blockers[0])
    head_positive = not (pred.negated or "Neg" in pred.determiner_prontypes)
    has_extra = bool(pred.modifiers or pred.relations)
    # Negace složeného přísudku má nejednoznačný dosah (De Morgan) — raději
    # unparsed než tiché zjednodušení, které mění význam.
    if not head_positive and has_extra:
        return _unparsed(text, "negace složeného přísudku mimo rozsah")

    subj = pred.subject
    if subj.kind is ReferenceKind.INDIVIDUAL:
        subj_term: object = _entity_from(subj)
    else:
        subj_term = Variable("X")
    conjuncts, relations, entities = build_conjuncts(pred, subj_term)
    provenance = tuple((popis, token) for _, _, token, popis in conjuncts)

    if subj.kind is ReferenceKind.AMBIGUOUS:
        # obecné jméno v otázce — nejednoznačná reference → doptání (§5)
        return Candidate("reference_ambiguous", text, predication=pred,
                         relations=tuple(relations), provenance=provenance,
                         note=f"reference {subj.lemma!r}: instance, nebo třída?")

    if subj.kind is ReferenceKind.INDIVIDUAL and not pred.is_question:
        literals = tuple(Literal(atom, pos) for atom, pos, _, _ in conjuncts)
        return Candidate("fact", text, literals=literals,
                         relations=tuple(relations),
                         entities=tuple(entities), provenance=provenance)

    if subj.kind is ReferenceKind.CLASS and not pred.is_question:
        subject_rel = Relation(subj.lemma, 1)
        relations.append(subject_rel)
        x = subj_term  # Variable("X")
        rules = tuple(
            Rule(((x, domain),), AtomRef(Atom(subject_rel, (x,))),
                 Literal(atom, pos))
            for atom, pos, _, _ in conjuncts)
        return Candidate("rule", text, rules=rules,
                         relations=tuple(relations), provenance=provenance)

    # INDIVIDUAL otázka → dotaz nad konjunkcí atomů
    exprs = tuple(_ref(atom, pos) for atom, pos, _, _ in conjuncts)
    query_expr = conj(*exprs) if len(exprs) > 1 else exprs[0]
    return Candidate("query", text, query_expr=query_expr,
                     query_atoms=tuple(a for a, _, _, _ in conjuncts),
                     relations=tuple(relations), entities=tuple(entities),
                     provenance=provenance)


def build_conjuncts(pred: Predication, subject_term):
    """Konjunkty predikace pro daný podmět — sdílené lowering i probe.

    Vrací (konjunkty, relace, entity), kde konjunkt je
    (atom, positive, token, popis). Podmět přichází zvenčí, takže totéž
    jde použít pro entitu i pro arbitrární instanci (třídní čtení).
    """
    head_positive = not (pred.negated or "Neg" in pred.determiner_prontypes)
    conjuncts: list[tuple[Atom, bool, int, str]] = []
    relations: list[Relation] = []
    entities: list = []
    if isinstance(subject_term, Entity):
        entities.append(subject_term)

    head_rel = Relation(pred.head_lemma, 1)
    relations.append(head_rel)
    conjuncts.append((Atom(head_rel, (subject_term,)), head_positive,
                      pred.head_token, _txt(pred.head_lemma, pred.subject)))
    for mod in pred.modifiers:
        rel = Relation(mod.lemma, 1)
        relations.append(rel)
        conjuncts.append((Atom(rel, (subject_term,)), not mod.negated,
                          mod.token_id, _txt(mod.lemma, pred.subject)))
    for rmod in pred.relations:
        rel = Relation(rmod.marker, 2)
        relations.append(rel)
        if rmod.target_upos == "PROPN":
            target: object = Entity(rmod.target_lemma.lower(),
                                    label=rmod.target_lemma)
            entities.append(target)
        else:
            target = Value(rmod.target_lemma)
        conjuncts.append((Atom(rel, (subject_term, target)), True,
                          rmod.token_id,
                          f"{rmod.marker}(…, {rmod.target_lemma})"))
    return conjuncts, relations, entities


def _ref(atom: Atom, positive: bool) -> Expression:
    ref = AtomRef(atom)
    return ref if positive else Not(ref)


def _txt(lemma: str, subj: Reference) -> str:
    return f"{lemma}({subj.lemma})"


def _entity_from(ref: Reference) -> Entity:
    return Entity(ref.lemma.lower(), label=ref.lemma)


# --- slovesné věty ------------------------------------------------------

def _verbal(children, root, text, question) -> Candidate:
    subjects = _kids(children, root, "nsubj")
    if not subjects:
        return _unparsed(text, "sloveso bez podmětu")
    subject = subjects[0]
    if _kids(children, subject, "det"):
        return _unparsed(text, "určený podmět slovesné věty mimo rozsah")
    if subject.upos != "PROPN":
        return _unparsed(text, "obecný podmět slovesné věty mimo rozsah")
    negated = _negated(root)
    conjuncts, relations, entities, blocker = verb_conjuncts(
        children, root, _entity(subject), subject)
    if blocker is not None:
        return _unparsed(text, blocker)
    if negated and len(conjuncts) > 1:
        # Negace složeného přísudku má nejednoznačný dosah (De Morgan) —
        # týž guard jako u kopuly.
        return _unparsed(text, "negace složeného přísudku mimo rozsah")
    lowered = tuple((atom, pos and not negated, tok, popis)
                    for atom, pos, tok, popis in conjuncts)
    provenance = tuple((popis, tok) for _, _, tok, popis in lowered)
    if question:
        exprs = tuple(_ref(atom, pos) for atom, pos, _, _ in lowered)
        query_expr = conj(*exprs) if len(exprs) > 1 else exprs[0]
        return Candidate("query", text, query_expr=query_expr,
                         query_atoms=tuple(a for a, _, _, _ in lowered),
                         relations=tuple(relations),
                         entities=tuple(entities), provenance=provenance)
    literals = tuple(Literal(atom, pos) for atom, pos, _, _ in lowered)
    return Candidate("fact", text, literals=literals,
                     relations=tuple(relations), entities=tuple(entities),
                     provenance=provenance)


def verb_conjuncts(children, verb, subject_term, subject_token):
    """Bezztrátový rozklad slovesné věty na konjunkty (HANDOVER 4.1.1).

    Týž mechanismus jako build_conjuncts: každý kus věty dostane vlastní
    konjunkt, nebo věta odmítne s důvodem — nikdy tiché zahození.

        obj          sloveso(podmět, předmět)
        obl+case     sloveso_předložka(podmět, cíl)
        obl bez case sloveso_pád(podmět, cíl)          jet_ins(petr, auto)
        advmod       sloveso_příslovce(podmět)         jet_rychle(petr)

    Vlastnost děje se jmenuje SLOVESEM i příslovcem: holé `rychlý(petr)`
    by tvrdilo vlastnost podmětu, ne děje — to by význam měnilo. Bez
    argumentů zůstává unární sloveso(podmět) jako dosud.

    Vrací (konjunkty, relace, entity, blocker); konjunkt je
    (atom, positive, token_id, popis). blocker je důvod odmítnutí, jinak
    None.
    """
    conjuncts: list[tuple[Atom, bool, int, str]] = []
    relations: list[Relation] = []
    entities: list = []
    if isinstance(subject_term, Entity):
        entities.append(subject_term)
    seen_obj = False
    has_argument = False
    for child in children.get(verb.id, []):
        deprel = (child.deprel or "").split(":", 1)[0]
        if deprel == "punct":
            continue
        if deprel == "nsubj":
            if child is subject_token:
                continue
            return [], [], [], "druhý podmět slovesné věty mimo rozsah"
        if deprel == "obj":
            if seen_obj:
                return [], [], [], "více předmětů slovesné věty mimo rozsah"
            seen_obj = True
            blocker = _argument_blocker(children, child, allowed=())
            if blocker is not None:
                return [], [], [], blocker
            relation = Relation(verb.lemma, 2)
            second, extra = _term_for(child)
            entities.extend(extra)
            relations.append(relation)
            conjuncts.append((Atom(relation, (subject_term, second)), True,
                              child.id, f"{verb.lemma}(…, {child.lemma})"))
            has_argument = True
        elif deprel == "obl":
            blocker = _argument_blocker(children, child, allowed=("case",))
            if blocker is not None:
                return [], [], [], blocker
            cases = _kids(children, child, "case")
            if cases:
                marker = cases[0].lemma
            elif child.feats and child.feats.get("Case"):
                # holý pád (instrumentál, dativ…) pojmenuje vztah sám —
                # strukturálně, žádný seznam slov
                marker = child.feats["Case"].lower()
            else:
                return [], [], [], (f"vazba obl bez předložky i pádu "
                                    f"({child.lemma!r}) mimo rozsah")
            relation = Relation(f"{verb.lemma}_{marker}", 2)
            second, extra = _term_for(child)
            entities.extend(extra)
            relations.append(relation)
            conjuncts.append((Atom(relation, (subject_term, second)), True,
                              child.id,
                              f"{verb.lemma}_{marker}(…, {child.lemma})"))
            has_argument = True
        elif deprel == "advmod":
            if child.upos != "ADV":
                return [], [], [], (f"advmod {child.lemma!r} není příslovce "
                                    f"— mimo rozsah")
            relation = Relation(f"{verb.lemma}_{child.lemma}", 1)
            relations.append(relation)
            conjuncts.append((Atom(relation, (subject_term,)),
                              not _negated(child), child.id,
                              f"{verb.lemma}_{child.lemma}(…)"))
        else:
            return [], [], [], (f"vazba {child.deprel!r} slovesné věty "
                                f"mimo rozsah")
    if not has_argument:
        relation = Relation(verb.lemma, 1)
        relations.append(relation)
        conjuncts.insert(0, (Atom(relation, (subject_term,)), True,
                             verb.id, f"{verb.lemma}(…)"))
    return conjuncts, relations, entities, None


def _argument_blocker(children, token, *, allowed) -> str | None:
    """Rozvitý argument nejde bez událostí věrně snížit — poctivé odmítnutí."""
    for child in children.get(token.id, []):
        deprel = (child.deprel or "").split(":", 1)[0]
        if deprel not in allowed and deprel != "punct":
            return (f"rozvitý argument {token.lemma!r} "
                    f"({child.deprel}) mimo rozsah")
    return None


def _operator(children, root, text, patterns) -> Candidate:
    """Operátorové sloveso s xcomp: matrix podmět řídí vložený přísudek."""
    subjects = _kids(children, root, "nsubj")
    if not subjects:
        return _unparsed(text, "operátorové sloveso bez podmětu")
    subject = subjects[0]
    xcomp = _kids(children, root, "xcomp")[0]
    conjuncts, relations, entities, blocker = verb_conjuncts(
        children, xcomp, _entity(subject), subject)
    if blocker is not None:
        return _unparsed(text, blocker)
    negated = _negated(root)
    signature = StructuralSignature(
        root.lemma, has_xcomp=True,
        has_obj=bool(_kids(children, xcomp, "obj")),
        has_obl=bool(_kids(children, xcomp, "obl")))
    exprs = tuple(_ref(atom, pos) for atom, pos, _, _ in conjuncts)
    common = dict(
        literal=Literal(conjuncts[0][0], conjuncts[0][1]),
        query_expr=conj(*exprs) if len(exprs) > 1 else exprs[0],
        query_atoms=tuple(a for a, _, _, _ in conjuncts),
        negated=negated, relations=tuple(relations),
        entities=tuple(entities), signature=signature)

    matched = patterns.match(signature) if patterns is not None else None
    if matched is not None:
        return Candidate("modal_query", text,
                         operation=matched.operation, **common)
    return Candidate("needs_pattern", text,
                     note=f"neznámé mapování operátoru {root.lemma!r}",
                     **common)


def _kids(children, token, deprel):
    return [c for c in children.get(token.id, [])
            if c.deprel and (c.deprel == deprel
                             or c.deprel.startswith(deprel + ":"))]


def _negated(token) -> bool:
    return bool(token.feats) and token.feats.get("Polarity") == "Neg"


def _entity(token) -> Entity:
    return Entity(token.lemma.lower(), label=token.form)


def _term_for(token):
    if token.upos == "PROPN":
        entity = _entity(token)
        return entity, (entity,)
    return Value(token.lemma), ()


def _unparsed(text: str, note: str) -> Candidate:
    return Candidate("unparsed", text, note=note)
