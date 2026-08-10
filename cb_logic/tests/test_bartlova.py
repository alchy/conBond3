"""Unseen benchmark: 13 řešených úloh z Bartlová (2014), PedF UK.

Kurátorovaná sada, kterou nikdo nepsal s ohledem na tento systém
(kap. 20.8 návrhu; zadání §45/§60): úlohy z roku 2014, engine je při
implementaci neviděl. Každá úloha je zapsaná ČISTĚ DATY (deklarace,
constrainty, fakta) a očekávaná odpověď je ta z práce [B]. Odkazy
[B, př. N] míří na čísla příkladů v kapitole 4.

Př. 11 se vynechává — je to týž problém jako př. 3 řešený jinou metodou
(pro engine je metoda pohled, ne úloha).
"""
import unittest

from cb_logic.constraints import (ExpressionConstraint, at_least_one,
                                  atom_family, exactly_one, requires)
from cb_logic.expressions import AtomRef, Equiv, Implies, Not, conj, disj
from cb_logic.knowledge import KnowledgeBase, Rule
from cb_logic.provenance import (Assertion, Evidence, EvidenceKind,
                                 LEVEL_DEFINITION, LEVEL_DOCUMENTED,
                                 Provenance)
from cb_logic.semantics import Truth
from cb_logic.terms import (Atom, Domain, Entity, Literal, Relation, Value,
                            Variable)
from cb_logic.models import (ModalVerdict, ModelLimits, classify_atoms,
                             classify_query, enumerate_models)

USER = Evidence(EvidenceKind.USER_ASSERTION, source="zadani [B]")
DEF = Provenance(LEVEL_DEFINITION, USER)
LIMITS = ModelLimits(max_scope_atoms=64, max_nodes=2_000_000)


def prop_kb(names):
    """Výroková báze: unární relace nad jednou entitou „svět"."""
    kb = KnowledgeBase()
    world = Entity("svet")
    kb.declare_domain(Domain("svet", (world,)))
    atoms = {}
    for name in names:
        kb.declare_relation(Relation(name, 1))
        atoms[name] = Atom(kb.relation(name), (world,))
    return kb, atoms


def say(kb, atom, positive=True):
    kb.assert_candidate(Assertion(Literal(atom, positive), USER,
                                  LEVEL_DOCUMENTED))


def model_values(model, atoms, names):
    env = dict(model)
    return tuple(env[atoms[n]] for n in names)


class TestPriklad1RozbiteOkno(unittest.TestCase):
    """[B, př. 1] Žáci A, B, C — kdo rozbil okno?"""

    def build(self):
        kb, a = prop_kb(("a", "b", "c"))
        kb.add_constraint(ExpressionConstraint(
            disj(Not(AtomRef(a["a"])), Not(AtomRef(a["b"])))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(Not(AtomRef(a["b"])), Not(AtomRef(a["a"])))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Equiv(AtomRef(a["c"]), Not(AtomRef(a["a"])))), DEF)
        return kb, a

    def test_dva_modely_a_klasifikace(self):
        kb, a = self.build()
        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual({model_values(m, a, "abc") for m in result.models},
                         {(False, True, True), (False, False, True)})
        cls = classify_atoms(result)
        self.assertIn(a["c"], cls.necessary)    # C byl u okna v obou
        self.assertIn(a["a"], cls.impossible)   # A tam nebyl nikdy

    def test_prave_jeden_urci_pachatele_jednoznacne(self):
        kb, a = self.build()
        kb.add_constraint(exactly_one(tuple(a[n] for n in "abc")), DEF)
        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual(len(result.models), 1)  # odpověď [B]: jednoznačně C
        self.assertEqual(model_values(result.models[0], a, "abc"),
                         (False, False, True))


class TestPriklad2TriStroje(unittest.TestCase):
    """[B, př. 2] (a⇒b) ∧ (b∨c) ∧ (¬a⇒¬c) — tři možnosti práce strojů."""

    def test_tri_modely_dle_prace(self):
        kb, a = prop_kb(("a", "b", "c"))
        kb.add_constraint(ExpressionConstraint(
            Implies(AtomRef(a["a"]), AtomRef(a["b"]))), DEF)
        kb.add_constraint(ExpressionConstraint(
            disj(AtomRef(a["b"]), AtomRef(a["c"]))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(Not(AtomRef(a["a"])), Not(AtomRef(a["c"])))), DEF)
        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual({model_values(m, a, "abc") for m in result.models},
                         {(True, True, True), (True, True, False),
                          (False, True, False)})
        self.assertIn(a["b"], classify_atoms(result).necessary)


class TestPriklad3PadousiAPoctivci(unittest.TestCase):
    """[B, př. 3 = 11] A: „Oba jsme poctivci." B: „A je padouch."

    Výrok mluvčího je pravdivý právě tehdy, když je mluvčí poctivec —
    kódovací pravidlo v datech (C-14), žádná větev v enginu.
    """

    def test_a_padouch_b_poctivec(self):
        kb, a = prop_kb(("a", "b"))  # X je poctivec
        kb.add_constraint(ExpressionConstraint(
            Equiv(AtomRef(a["a"]), conj(AtomRef(a["a"]), AtomRef(a["b"])))),
            DEF)
        kb.add_constraint(ExpressionConstraint(
            Equiv(AtomRef(a["b"]), Not(AtomRef(a["a"])))), DEF)
        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual(len(result.models), 1)
        self.assertEqual(model_values(result.models[0], a, "ab"),
                         (False, True))


class TestPriklad4Budovy(unittest.TestCase):
    """[B, př. 4] Divadlo, kino, škola: ¬(d∧k) ∧ (s⇒d) + aspoň jedna."""

    def test_tri_moznosti_mesta(self):
        kb, a = prop_kb(("d", "k", "s"))
        kb.add_constraint(ExpressionConstraint(
            Not(conj(AtomRef(a["d"]), AtomRef(a["k"])))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(AtomRef(a["s"]), AtomRef(a["d"]))), DEF)
        kb.add_constraint(at_least_one(tuple(a[n] for n in "dks")), DEF)
        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual({model_values(m, a, "dks") for m in result.models},
                         {(False, True, False),   # pouze kino
                          (True, False, True),    # divadlo a škola
                          (True, False, False)})  # pouze divadlo


class TestPriklad5Pracoviste(unittest.TestCase):
    """[B, př. 5] (¬b⇒¬a) ∧ (b⇒(a∧c)); účastní-li se A, musí se C?"""

    def test_c_je_nutne(self):
        kb, a = prop_kb(("a", "b", "c"))
        kb.add_constraint(ExpressionConstraint(
            Implies(Not(AtomRef(a["b"])), Not(AtomRef(a["a"])))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(AtomRef(a["b"]),
                    conj(AtomRef(a["a"]), AtomRef(a["c"])))), DEF)
        say(kb, a["a"])  # pracoviště A se účastní
        result = classify_query(kb, AtomRef(a["c"]), limits=LIMITS)
        self.assertEqual(result.verdict, ModalVerdict.NECESSARY)


class TestPriklad6Vestkyne(unittest.TestCase):
    """[B, př. 6] ¬a⇒b, b⇒¬c, c⇒d; zaplatil jsem — co mi prozradila?"""

    def test_jednoznacne_reseni(self):
        kb, a = prop_kb(("a", "b", "c", "d"))
        kb.add_constraint(ExpressionConstraint(
            Implies(Not(AtomRef(a["a"])), AtomRef(a["b"]))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(AtomRef(a["b"]), Not(AtomRef(a["c"])))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(AtomRef(a["c"]), AtomRef(a["d"]))), DEF)
        say(kb, a["c"])  # zaplatil jsem
        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual(len(result.models), 1)
        self.assertEqual(model_values(result.models[0], a, "abcd"),
                         (True, False, True, True))


class TestPriklad7Vnoucata(unittest.TestCase):
    """[B, př. 7] Mám za vnukem jet? Dvě varianty první informace."""

    def test_varianta_a_jistota_neni(self):
        kb, a = prop_kb(("j", "k", "t"))
        kb.add_constraint(ExpressionConstraint(
            Implies(AtomRef(a["j"]), Not(AtomRef(a["t"])))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(AtomRef(a["k"]), AtomRef(a["t"]))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(Not(AtomRef(a["k"])), AtomRef(a["j"]))), DEF)
        result = classify_query(kb, AtomRef(a["j"]), limits=LIMITS)
        self.assertEqual(result.verdict, ModalVerdict.POSSIBLE)
        self.assertIsNotNone(result.counterexample)  # nejedu — nejsem si jist

    def test_varianta_b_jakub_je_doma_v_kazdem_pripade(self):
        kb, a = prop_kb(("j", "k", "t"))
        kb.add_constraint(ExpressionConstraint(
            Implies(Not(AtomRef(a["j"])), Not(AtomRef(a["t"])))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(AtomRef(a["k"]), AtomRef(a["t"]))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(Not(AtomRef(a["k"])), AtomRef(a["j"]))), DEF)
        result = classify_query(kb, AtomRef(a["j"]), limits=LIMITS)
        self.assertEqual(result.verdict, ModalVerdict.NECESSARY)  # jedu


class TestPriklad8Vecirek(unittest.TestCase):
    """[B, př. 8] j⇔p, k∨v, ¬j⇒k, l⇒¬v; Kateřina nedorazí."""

    def test_kdo_prijde(self):
        kb, a = prop_kb(("j", "p", "k", "v", "l"))
        kb.add_constraint(ExpressionConstraint(
            Equiv(AtomRef(a["j"]), AtomRef(a["p"]))), DEF)
        kb.add_constraint(ExpressionConstraint(
            disj(AtomRef(a["k"]), AtomRef(a["v"]))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(Not(AtomRef(a["j"])), AtomRef(a["k"]))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Implies(AtomRef(a["l"]), Not(AtomRef(a["v"])))), DEF)
        say(kb, a["k"], positive=False)  # Kateřina nedorazí
        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual(len(result.models), 1)
        self.assertEqual(model_values(result.models[0], a, "jpkvl"),
                         (True, True, False, True, False))


class TestPriklad9Lichobezniky(unittest.TestCase):
    """[B, př. 9] Kvantifikované třídy: úsudek NEPLYNE (monotonie, INV-1)."""

    def test_usudek_neni_spravny_ale_neni_ani_vylouceny(self):
        kb = KnowledgeBase()
        for name in ("lichobeznik", "ctyruhelnik", "rovnobeznik"):
            kb.declare_relation(Relation(name, 1))
        utvar = Entity("utvar")
        kb.declare_domain(Domain("utvary", (utvar,)))
        x = Variable("X")
        for lower in ("lichobeznik", "rovnobeznik"):
            kb.add_rule(Rule(((x, "utvary"),),
                             AtomRef(Atom(kb.relation(lower), (x,))),
                             Literal(Atom(kb.relation("ctyruhelnik"),
                                          (x,)))), DEF)
        say(kb, Atom(kb.relation("rovnobeznik"), (utvar,)))
        # „Všechny rovnoběžníky jsou lichoběžníky"? — na svědkovi:
        result = classify_query(
            kb, AtomRef(Atom(kb.relation("lichobeznik"), (utvar,))),
            limits=LIMITS)
        self.assertEqual(result.verdict, ModalVerdict.POSSIBLE)
        self.assertIsNotNone(result.counterexample)  # úsudek neplyne
        # ... a K3 čtení poctivě NEVÍ (nelže „ne"):
        self.assertEqual(
            kb.truth_of(Atom(kb.relation("lichobeznik"), (utvar,))),
            Truth.UNKNOWN)


class TestPriklad10Auticko(unittest.TestCase):
    """[B, př. 10] Jirkovo přání: h ∧ ((s∧v) ∨ (p∧h)) ∧ ¬(p∧¬v)."""

    def build(self):
        kb, a = prop_kb(("h", "s", "v", "p"))
        kb.add_constraint(ExpressionConstraint(AtomRef(a["h"])), DEF)
        kb.add_constraint(ExpressionConstraint(
            disj(conj(AtomRef(a["s"]), AtomRef(a["v"])),
                 conj(AtomRef(a["p"]), AtomRef(a["h"])))), DEF)
        kb.add_constraint(ExpressionConstraint(
            Not(conj(AtomRef(a["p"]), Not(AtomRef(a["v"]))))), DEF)
        return kb, a

    def test_tri_moznosti_a_otec_prani_splnil(self):
        kb, a = self.build()
        result = enumerate_models(kb, limits=LIMITS)
        expected = {(True, True, True, False),   # neplechové s h, s, v
                    (True, True, True, True),    # plechové s h, s, v
                    (True, False, True, True)}   # plechové h, v, bez s
        self.assertEqual({model_values(m, a, "hsvp") for m in result.models},
                         expected)
        koupene = (True, False, True, True)      # co otec koupil
        self.assertIn(koupene,
                      {model_values(m, a, "hsvp") for m in result.models})

    def test_prodavacka_neodhadla(self):
        """Její odhad (h∧s∧v) pokrývá jen 2 ze 3 možností."""
        kb, a = self.build()
        result = classify_query(
            kb, conj(AtomRef(a["h"]), AtomRef(a["s"]), AtomRef(a["v"])),
            limits=LIMITS)
        self.assertEqual(result.verdict, ModalVerdict.POSSIBLE)  # ne NUTNĚ


class TestPriklad12PoctivecPadouchNormalni(unittest.TestCase):
    """[B, př. 12] Tři lidé, tři povahy; C-14 jako data."""

    def test_a_padouch_b_normalni_c_poctivec(self):
        kb = KnowledgeBase()
        typ = Relation("typ", 2)
        kb.declare_relation(typ)
        persons = tuple(Entity(n) for n in ("a", "b", "c"))
        kinds = tuple(Value(v) for v in ("poctivec", "padouch", "normalni"))
        kb.declare_domain(Domain("lide", persons))
        kb.declare_domain(Domain("povahy", kinds))
        for person in persons:
            kb.add_constraint(exactly_one(
                atom_family(typ, (person, None), kb.domain("povahy"))), DEF)
        for kind in kinds:
            kb.add_constraint(exactly_one(
                atom_family(typ, (None, kind), kb.domain("lide"))), DEF)

        def t(person, kind):
            return AtomRef(Atom(typ, (person, Value(kind))))

        a, b, c = persons
        statements = ((a, t(a, "normalni")),      # A: „Já jsem normální."
                      (b, t(a, "normalni")),      # B: „To je pravda."
                      (c, Not(t(c, "normalni"))))  # C: „Já nejsem normální."
        for speaker, statement in statements:
            kb.add_constraint(ExpressionConstraint(
                Implies(t(speaker, "poctivec"), statement)), DEF)
            kb.add_constraint(ExpressionConstraint(
                Implies(t(speaker, "padouch"), Not(statement))), DEF)

        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual(len(result.models), 1)
        env = dict(result.models[0])
        self.assertTrue(env[Atom(typ, (a, Value("padouch")))])
        self.assertTrue(env[Atom(typ, (b, Value("normalni")))])
        self.assertTrue(env[Atom(typ, (c, Value("poctivec")))])


class TestPriklad13Parta(unittest.TestCase):
    """[B, př. 13] Kdo nosí sekeru? — Jan Bílý."""

    def test_sekeru_nosi_jan_bily(self):
        kb = KnowledgeBase()
        prijmeni = Relation("prijmeni", 2)
        nastroj = Relation("nastroj", 2)
        kb.declare_relation(prijmeni)
        kb.declare_relation(nastroj)
        persons = tuple(Entity(n) for n in ("petr", "tomas", "jan"))
        kb.declare_domain(Domain("osoby", persons))
        kb.declare_domain(Domain("prijmeni",
                                 tuple(Value(v) for v in
                                       ("cerveny", "modry", "bily"))))
        kb.declare_domain(Domain("nastroje",
                                 tuple(Value(v) for v in
                                       ("sekera", "kotlik", "stan"))))
        for rel, dom in ((prijmeni, "prijmeni"), (nastroj, "nastroje")):
            for person in persons:
                kb.add_constraint(exactly_one(
                    atom_family(rel, (person, None), kb.domain(dom))), DEF)
            for value in kb.domain(dom).members:
                kb.add_constraint(exactly_one(
                    atom_family(rel, (None, value), kb.domain("osoby"))),
                    DEF)
        petr, tomas, jan = persons
        say(kb, Atom(prijmeni, (jan, Value("bily"))))     # 1. Jan je Bílý
        say(kb, Atom(nastroj, (petr, Value("stan"))))     # 2. Petr nosí stan
        for person in persons:                            # 3. Modrý nosí kotlík
            kb.add_constraint(requires(
                AtomRef(Atom(prijmeni, (person, Value("modry")))),
                AtomRef(Atom(nastroj, (person, Value("kotlik"))))), DEF)
        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual(len(result.models), 1)
        env = dict(result.models[0])
        self.assertTrue(env[Atom(nastroj, (jan, Value("sekera")))])
        self.assertTrue(env[Atom(prijmeni, (jan, Value("bily")))])
        self.assertTrue(env[Atom(prijmeni, (tomas, Value("modry")))])


class TestPriklad14MilovniciUmeni(unittest.TestCase):
    """[B, př. 14] Originál, jehož přejmenovaným derivátem je benchmark §29."""

    def test_antonin_hraje_na_basu_a_ma_haska_moneta_baroko(self):
        kb = KnowledgeBase()
        categories = {
            "hraje": ("housle", "viola", "cello", "basa"),
            "autor": ("capek", "hasek", "kundera", "seifert"),
            "malir": ("gogh", "gauguin", "monet", "cezanne"),
            "sloh": ("goticky", "romansky", "renesancni", "barokni"),
        }
        persons = tuple(Entity(n)
                        for n in ("josef", "antonin", "frantisek", "pavel"))
        josef, antonin, frantisek, pavel = persons
        kb.declare_domain(Domain("osoby", persons))
        for cat, values in categories.items():
            kb.declare_relation(Relation(cat, 2))
            kb.declare_domain(Domain(cat, tuple(Value(v) for v in values)))
            rel = kb.relation(cat)
            for person in persons:
                kb.add_constraint(exactly_one(
                    atom_family(rel, (person, None), kb.domain(cat))), DEF)
            for value in values:
                kb.add_constraint(exactly_one(
                    atom_family(rel, (None, Value(value)),
                                kb.domain("osoby"))), DEF)

        def has(cat, person, value):
            return AtomRef(Atom(kb.relation(cat), (person, Value(value))))

        for p in persons:
            kb.add_constraint(requires(       # 1. houslista má rád Kunderu
                has("hraje", p, "housle"), has("autor", p, "kundera")), DEF)
            kb.add_constraint(requires(       # 3. Gauguin ⇒ románský
                has("malir", p, "gauguin"), has("sloh", p, "romansky")), DEF)
            kb.add_constraint(ExpressionConstraint(  # 4. Hašek ⇔ Monet
                Equiv(has("autor", p, "hasek"), has("malir", p, "monet"))),
                DEF)
            kb.add_constraint(requires(       # 5. Cézanne ⇒ ne Kundera
                has("malir", p, "cezanne"),
                Not(has("autor", p, "kundera"))), DEF)
            kb.add_constraint(requires(       # 9. violista má rád Gogha
                has("hraje", p, "viola"), has("malir", p, "gogh")), DEF)
            kb.add_constraint(requires(       # 10. gotika ⇒ ne Cézanne
                has("sloh", p, "goticky"),
                Not(has("malir", p, "cezanne"))), DEF)
        say(kb, Atom(kb.relation("hraje"),                 # 2. František
                     (frantisek, Value("basa"))), positive=False)
        say(kb, Atom(kb.relation("sloh"),                  # 6. Antonín baroko
                     (antonin, Value("barokni"))))
        say(kb, Atom(kb.relation("autor"),                 # 7. Pavel Seifert
                     (pavel, Value("seifert"))))
        say(kb, Atom(kb.relation("malir"),                 # 8. František Céz.
                     (frantisek, Value("cezanne"))))

        result = enumerate_models(kb, limits=LIMITS)
        self.assertEqual(len(result.models), 1)  # [B]: jednoznačné řešení
        env = dict(result.models[0])
        # odpověď [B]: Antonín hraje na basu, má Haška, Moneta a baroko
        self.assertTrue(env[Atom(kb.relation("hraje"),
                                 (antonin, Value("basa")))])
        self.assertTrue(env[Atom(kb.relation("autor"),
                                 (antonin, Value("hasek")))])
        self.assertTrue(env[Atom(kb.relation("malir"),
                                 (antonin, Value("monet")))])
        # ... a celá tabulka 4.12 pro ostatní:
        self.assertTrue(env[Atom(kb.relation("hraje"),
                                 (josef, Value("housle")))])
        self.assertTrue(env[Atom(kb.relation("autor"),
                                 (josef, Value("kundera")))])
        self.assertTrue(env[Atom(kb.relation("hraje"),
                                 (frantisek, Value("cello")))])
        self.assertTrue(env[Atom(kb.relation("sloh"),
                                 (pavel, Value("goticky")))])


if __name__ == "__main__":
    unittest.main()
