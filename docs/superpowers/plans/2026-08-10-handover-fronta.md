# Fronta z HANDOVER + expanze zadání — implementační plán

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dokončit frontu z HANDOVER.md podle expanze zadání J. (10. 8. 2026):
(1) dluhy retrieval vrstvy (rozbité skripty, `MatchResult`), (2) interaktivní
rozřešení reference v UI/konzoli/REST, (3) bezztrátová extrakce slovesných
vět (advmod, více argumentů) a genitivního `nmod`.

**Architecture:** Tři nezávislé bloky v pořadí podle harmonogramu expanze
(dluh → reference → extrakce). Formální vrstva stojí dál VEDLE retrievalu;
stav „poslední nejednoznačný dotaz" žije v `LogicBridge` (jeden slot, bez
hodin — determinismus). Extrakce sloves kopíruje mechanismus `build_conjuncts`:
každý kus věty dostane vlastní konjunkt, nebo věta poctivě odmítne
(`unparsed` s důvodem) — nikdy tiché zahození.

**Tech Stack:** Python 3.11 stdlib, unittest, zmražené UDPipe rozbory
(cs_all-ud-2.17, vygenerované 2026-08-10 živou službou — už hotové, jsou
v tomto plánu). Žádná nová závislost.

## Global Constraints

- Spouštění výhradně `./run-python …`; plná sada: `./run-python -m unittest discover -s . -p "test_*.py" -t .` (před začátkem 1008 zeleně).
- Import guardy: `cb_logic` neimportuje `cb_*`; `cb_interpret` jen `cb_logic` + `cb_udpipe` (grepy z HANDOVER § 7 musí zůstat prázdné).
- Modalita NIKDY jako operátor objektového jazyka — jen dotazy nad modely (hlídá `test_pattern_guard.py`).
- Tiché zjednodušení měnící význam je nepřípustné: buď strukturovaná reprezentace, nebo `unparsed`/`needs_pattern`/`reference_ambiguous` s důvodem.
- Determinismus: žádné hodiny (`PendingClarification.timestamp` z expanze se NEpřebírá — porušil by guard), žádná neseedovaná náhoda, kanonická pořadí.
- Statistika/jazyk navrhuje, nerozhoduje (INV‑11); konflikt se hlásí (INV‑5); UNKNOWN ≠ FALSE (INV‑9).
- REST kontrakt: do objektů se klíče PŘIDÁVAJÍ (§ 7) — existující klíč `kind: reference_ambiguous` se nemění na `status: NEEDS_CLARIFICATION` z expanze; sémantika expanze (strukturované volby s příkazy) se naplní přidáním klíče `command` do `options`. Nový endpoint je `POST /v1/logic/resolve`.
- Komentáře a docstringy česky, ve stylu okolního kódu (vysvětlují PROČ).
- Každý nový interpretační vzor má renaming + unseen test (§ 60); generalizační věty se přidávají do `cb_interpret/tests/vzorky_struct.py`.
- Commity česky ve stylu repa (`oblast: co`), zakončené `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Práce na větvi `feature/handover-fronta` (z `main`).

## Odchylky od expanze zadání (vědomé, s důvodem)

1. **Žádný `timestamp` ani `query_id` v pending stavu** — hodiny porušují
   guard determinismu; služba je jednouživatelský dialog a HANDOVER žádá
   „poslední nejednoznačný dotaz" (jeden slot). Korelaci dává `source_text`
   v odpovědi.
2. **`kind` místo `status`** v JSON — stabilita kontraktu § 7 (přidat klíč
   ano, přejmenovat ne). Obsahově je odpověď shodná s expanzí (options
   s `choice/command/popis`).
3. **Bez událostní reifikace (`Event(jede)`)** — plná Davidsonovská
   reprezentace vyžaduje existenční kvantifikaci v dotazech, a to je hranice
   jádra (HANDOVER 4.2.3: „nerozšiřovat bez rozhodnutí"). „Vlastnost děje"
   z expanze se reprezentuje konjunktem `sloveso_příslovce(podmět)` (např.
   `jet_rychle(petr)`) — jméno relace nese sloveso i příslovce, takže se
   význam neztrácí ani neslévá s `rychlý(petr)`. Konjunktivní čtení je týž
   mechanismus, jakým už dnes kopulová vrstva čte „zkušený programátor".
4. **Genitiv jako relace pojmenovaná pádem (`gen`)**, ne `rel_of` — jméno
   z UD hodnoty `Case=Gen` je strukturální a nepodsouvá posesivní sémantiku
   (expanze sama říká „přivlastňovací NEBO asociační"); mechanismus je týž
   pro ostatní holé pády (`jet_ins` u sloves). Pojistka z expanze platí:
   `nmod` bez předložky i pádu → `unparsed` s důvodem.
5. **Tlačítka ve web UI** — okno je terminál (viewbase `TerminalWindow`),
   tlačítka nemá; interakci nesou příkazy `:instance` / `:trida`, které
   odpověď zobrazuje jako nápovědu (a REST je vrací v `options[].command`
   pro budoucí klikací klienty).

---

### Task 1: Oprava měřicích skriptů + smoke test

**Files:**
- Modify: `cb_bond/scripts/protokol.py:21-24`
- Modify: `cb_bond/scripts/rozklad-skore.py:26-28`
- Test: `cb_bond/tests/test_scripts.py` (nový)

**Interfaces:**
- Produces: oba skripty jdou naimportovat (SyntaxError pryč); `test_scripts.py` to hlídá trvale.

Příčina: řádek `from cb_bond.config import corpus_dir` je vložený DOPROSTŘED
závorkového importu. Navíc `ArmResult`, `ThresholdCalibrator` a `sentence_hit`
nejsou v `cb_bond.__init__` — importují se přímo z podmodulů (skript je
součást balíku, šev klienta platí pro cizí moduly). POZOR: smoke test smí
importovat jen `protokol.py` a `rozklad-skore.py` — `prejimka-zrcadlo.py`
nemá `__main__` guard a import by ho spustil.

- [ ] **Step 1: Napsat failing test**

```python
"""Měřicí skripty musí jít aspoň naimportovat.

SyntaxError v měřicím skriptu se jinak pozná až při spuštění protokolu
(ARCHITECTURE_REVIEW příloha A) — tenhle test ho sráží do běžné testovací
smyčky. Nespouští `main()`: modul se jen načte, takže nepotřebuje korpusy
ani běžící UDPipe. Importují se jen skripty s `__main__` guardem —
`prejimka-zrcadlo.py` ho nemá a import by ho spustil.
"""
import importlib.util
import unittest
from pathlib import Path

SKRIPTY = Path(__file__).parent.parent / "scripts"
MERICI = ("protokol.py", "rozklad-skore.py")


class TestMericiSkriptyJdouNacist(unittest.TestCase):
    def test_merici_skripty_jdou_naimportovat(self):
        for jmeno in MERICI:
            with self.subTest(skript=jmeno):
                cesta = SKRIPTY / jmeno
                spec = importlib.util.spec_from_file_location(
                    cesta.stem.replace("-", "_"), cesta)
                modul = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(modul)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ověřit, že padá** — `./run-python -m unittest cb_bond.tests.test_scripts -v` → FAIL (SyntaxError).

- [ ] **Step 3: Opravit importy.** V `protokol.py` nahradit rozbitý blok:

```python
from cb_bond import (BenchmarkProtocol, ContrastiveTrainer, GraphRecall,
                     KnowledgeGraph, Matcher, PromotionCycle)
from cb_bond.benchmark import ArmResult, ThresholdCalibrator
from cb_bond.config import corpus_dir
from cb_bond.training import sentence_hit
```

V `rozklad-skore.py`:

```python
from cb_bond import AnswerField, KnowledgeGraph, Matcher, ScoreWeights
from cb_bond.config import corpus_dir
from cb_bond.relations import RelationMiner
```

Pak zkontrolovat tělem skriptu, že se všechna importovaná jména skutečně
používají — nepoužívaná smazat (mrtvý import je taky dluh).

- [ ] **Step 4: Testy zeleně** — tentýž příkaz → PASS.

- [ ] **Step 5: Commit** — `skripty: oprava rozbitých importů protokol/rozklad-skore + smoke test`.

---

### Task 2: `MatchResult` — sjednocení, přeřazení po negaci, rozklad přežívá kompozici

**Files:**
- Modify: `cb_bond/matcher.py:198-230` (`__or__`, `__invert__`, `_spoj`)
- Test: `cb_bond/tests/test_matcher.py` (přidat do sekce algebry košů)

**Interfaces:**
- Consumes: `ScoreCandidate(sentence, token, lemma, score, members)`, `MatchResult(candidates, outcome, question)` — beze změny tvaru.
- Produces: `a | b` = sjednocení kandidátů (společní se sčítají, ostatní přežívají); `~a` seřazený podle nového skóre; kompozice nese rozklad se zachovaným invariantem `sum(members) == score`.

Stávající testy PINUJÍ: `&` je průnik (`test_and_zachova_jen_spolecne_kandidaty`),
součin kladných/minimum se záporným, `~` obrací znaménko. To zůstává.

- [ ] **Step 1: Napsat failing testy** (do `test_matcher.py`, vedle stávající algebry košů; `_vysledek` je tamní helper):

```python
    def test_or_je_sjednoceni_ne_prunik(self):
        a = _vysledek({(0, 0): 0.5, (0, 1): 0.4})
        b = _vysledek({(0, 1): 0.2, (1, 0): 0.3})

        sjednoceni = a | b

        podle = {k.key: k.score for k in sjednoceni.candidates}
        self.assertEqual(set(podle), {(0, 0), (0, 1), (1, 0)})
        self.assertAlmostEqual(podle[(0, 1)], 0.6)   # společný se sčítá
        self.assertAlmostEqual(podle[(0, 0)], 0.5)   # jen v a — přežije
        self.assertAlmostEqual(podle[(1, 0)], 0.3)   # jen v b — přežije

    def test_invert_preradi_kandidaty(self):
        puvodni = _vysledek({(0, 0): 0.5, (0, 1): -0.2})

        obraceny = ~puvodni

        skore = [k.score for k in obraceny.candidates]
        self.assertEqual(skore, sorted(skore, reverse=True))
        self.assertEqual(obraceny.best.key, (0, 1))   # −0,2 → +0,2 vede

    def test_or_zachova_rozklad_po_clenech(self):
        a = MatchResult([ScoreCandidate(0, 0, "x", 0.5,
                                        {"meet": 0.3, "cover": 0.2})],
                        "answer")
        b = MatchResult([ScoreCandidate(0, 0, "x", 0.2,
                                        {"meet": 0.1, "topic": 0.1})],
                        "answer")

        soucet = (a | b).best

        self.assertAlmostEqual(sum(soucet.decomposition().values()),
                               soucet.score)
        self.assertAlmostEqual(soucet.decomposition()["meet"], 0.4)

    def test_and_rozklad_secte_na_skore(self):
        a = MatchResult([ScoreCandidate(0, 0, "x", 0.5, {"meet": 0.5})],
                        "answer")
        b = MatchResult([ScoreCandidate(0, 0, "x", 0.2, {"meet": 0.2})],
                        "answer")

        soucin = (a & b).best

        self.assertAlmostEqual(sum(soucin.decomposition().values()),
                               soucin.score)
```

Import `ScoreCandidate` nahoře testu: `from cb_bond.matcher import ScoreCandidate` (je-li tam už import z matcheru, rozšířit).

- [ ] **Step 2: Ověřit, že padají** — `./run-python -m unittest cb_bond.tests.test_matcher -v`.

- [ ] **Step 3: Implementace.** V `matcher.py` nahradit `__or__`, `__invert__`, `_spoj`:

```python
    def __or__(self, other: "MatchResult") -> "MatchResult":
        return self._spoj(other, lambda a, b: a + b,
                          prunik=False, po_clenech=True)

    def __and__(self, other: "MatchResult") -> "MatchResult":
        return self._spoj(other, _and, prunik=True, po_clenech=False)

    def __invert__(self) -> "MatchResult":
        obraceni = [
            ScoreCandidate(k.sentence, k.token, k.lemma, -k.score,
                           {jmeno: -hodnota
                            for jmeno, hodnota in k._members.items()})
            for k in self.candidates]
        obraceni.sort(key=lambda k: -k.score)
        return MatchResult(obraceni, self.outcome, self.question)

    def _spoj(self, other: "MatchResult", operace, *, prunik: bool,
              po_clenech: bool) -> "MatchResult":
        """Složí dva koše kandidátů.

        prunik: kandidát bez protějšku se zahodí (&), nebo přežije se svým
        skóre (|) — sjednocení, ne průnik; `a | b` dřív fakticky průnik
        vracelo (audit, příloha A).

        po_clenech: sčítání jde složit po členech rozkladu (invariant
        „součet členů dá skóre" drží). Součin/minimum po členech složit
        nejde — složené skóre dostane jeden explicitní člen `and`, ať
        rozklad nelže.
        """
        druhy = {k.key: k for k in other.candidates}
        spojene = []
        for kandidat in self.candidates:
            protejsek = druhy.pop(kandidat.key, None)
            if protejsek is None:
                if not prunik:
                    spojene.append(kandidat)
                continue
            slozene = operace(kandidat.score, protejsek.score)
            if po_clenech:
                cleny = dict(kandidat._members)
                for jmeno, hodnota in protejsek._members.items():
                    cleny[jmeno] = cleny.get(jmeno, 0.0) + hodnota
            else:
                cleny = {"and": slozene}
            spojene.append(ScoreCandidate(
                kandidat.sentence, kandidat.token, kandidat.lemma,
                slozene, cleny))
        if not prunik:
            spojene.extend(druhy.values())
        spojene.sort(key=lambda k: -k.score)
        return MatchResult(spojene, self.outcome, self.question)
```

- [ ] **Step 4: Testy zeleně** — celé `cb_bond.tests.test_matcher` (staré pinující testy nesmí spadnout).

- [ ] **Step 5: Commit** — `matcher: | je sjednocení, ~ přeřazuje, kompozice nese rozklad (audit A)`.

---

### Task 3: `LogicBridge` — stav „poslední nejednoznačný dotaz" + `resolve_reference`

**Files:**
- Modify: `cb_bond/logic.py`
- Test: `cb_bond/tests/test_logic.py`

**Interfaces:**
- Consumes: `DialogueLearner.resolve_reference(candidate, choice)` (hotové, choice `"instance"|"class"`), `Candidate` z `cb_interpret`.
- Produces: `LogicBridge.resolve_reference(choice: str) -> dict` s klíči `kind: "reference_resolved"|"no_pending_reference"`, `choice`, `subject`, `source_text`, `truth`, `answer`, `explanations`, `conflicted` (+ `missing`/`why_not_kind` při UNKNOWN); `ask()` u `reference_ambiguous` nově vrací v každé volbě i `command` (`:instance`/`:trida`); `state()` nese `pending_reference: bool`.

Sémantika slotu (dokumentovat v docstringu): `ask()` slot na začátku vyprázdní
a naplní jen při `reference_ambiguous` — volba se vztahuje k poslednímu
doptání. `context()` slot NECHÁVÁ: člověk si smí před volbou doplnit znalost.
Slot se nepersistuje (je to rozpracovaný dialog, ne znalost).

- [ ] **Step 1: Failing testy.** Do `test_logic.py` přidat zmražené rozbory (kopie — testy cizího modulu se nečtou) a věty do `VETY`:

```python
AUTO_PROSTREDEK = (  # Auto je dopravní prostředek.
    Token(id=1, form='Auto', lemma='auto', upos='NOUN',
          xpos='NNNS1-----A----',
          feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'},
          head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--',
          feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing',
                 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres',
                 'VerbForm': 'Fin', 'Voice': 'Act'},
          head=4, deprel='cop', deps=None, misc=None),
    Token(id=3, form='dopravní', lemma='dopravní', upos='ADJ',
          xpos='AAIS1----1A----',
          feats={'Animacy': 'Inan', 'Case': 'Nom', 'Degree': 'Pos',
                 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'},
          head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='prostředek', lemma='prostředek', upos='NOUN',
          xpos='NNIS1-----A----',
          feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc',
                 'Number': 'Sing'},
          head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------',
          feats=None, head=4, deprel='punct', deps=None,
          misc={'SpaceAfter': 'No'}),
)

JE_AUTO_PROSTREDEK = (  # Je auto dopravní prostředek?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--',
          feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing',
                 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres',
                 'VerbForm': 'Fin', 'Voice': 'Act'},
          head=4, deprel='cop', deps=None, misc=None),
    Token(id=2, form='auto', lemma='auto', upos='NOUN',
          xpos='NNNS1-----A----',
          feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'},
          head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='dopravní', lemma='dopravní', upos='ADJ',
          xpos='AAIS1----1A----',
          feats={'Animacy': 'Inan', 'Case': 'Nom', 'Degree': 'Pos',
                 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'},
          head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='prostředek', lemma='prostředek', upos='NOUN',
          xpos='NNIS1-----A----',
          feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc',
                 'Number': 'Sing'},
          head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------',
          feats=None, head=4, deprel='punct', deps=None,
          misc={'SpaceAfter': 'No'}),
)
```

Do `VETY` přidat `"Auto je dopravní prostředek.": AUTO_PROSTREDEK` a
`"Je auto dopravní prostředek?": JE_AUTO_PROSTREDEK`. Nová třída testů:

```python
class TestReferenceResolution(unittest.TestCase):
    """Plný kruh doptání na referenci — HANDOVER 4.1 bod 3, expanze § 1."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.kb_file = Path(self._tmp.name) / "logic" / "kb.json"
        self.bridge = LogicBridge(_Parser(), self.kb_file)

    def tearDown(self):
        self._tmp.cleanup()

    def test_otazka_se_dopta_a_nabidne_prikazy(self):
        self.bridge.context("Auto je dopravní prostředek.")
        odpoved = self.bridge.ask("Je auto dopravní prostředek?")
        self.assertEqual(odpoved["kind"], "reference_ambiguous")
        self.assertEqual({o["choice"] for o in odpoved["options"]},
                         {"instance", "class"})
        self.assertEqual({o["command"] for o in odpoved["options"]},
                         {":instance", ":trida"})
        self.assertTrue(self.bridge.state()["pending_reference"])

    def test_volba_trida_dokonci_dotaz_pres_probe(self):
        self.bridge.context("Auto je dopravní prostředek.")
        self.bridge.ask("Je auto dopravní prostředek?")
        vysledek = self.bridge.resolve_reference("class")
        self.assertEqual(vysledek["kind"], "reference_resolved")
        self.assertEqual(vysledek["truth"], "TRUE")
        self.assertEqual(vysledek["answer"], "Ano.")
        self.assertEqual(vysledek["subject"], "auto")
        self.assertFalse(self.bridge.state()["pending_reference"])

    def test_volba_instance_bez_znalosti_je_nevim(self):
        self.bridge.context("Auto je dopravní prostředek.")
        self.bridge.ask("Je auto dopravní prostředek?")
        vysledek = self.bridge.resolve_reference("instance")
        self.assertEqual(vysledek["truth"], "UNKNOWN")
        self.assertEqual(vysledek["answer"], "Nevím.")

    def test_bez_cekajiciho_doptani_je_hlaska_ne_chyba(self):
        vysledek = self.bridge.resolve_reference("class")
        self.assertEqual(vysledek["kind"], "no_pending_reference")

    def test_jina_otazka_doptani_zrusi(self):
        self.bridge.context("Auto je dopravní prostředek.")
        self.bridge.ask("Je auto dopravní prostředek?")
        self.bridge.ask("Je Petr člověk?")
        self.assertEqual(self.bridge.resolve_reference("class")["kind"],
                         "no_pending_reference")

    def test_tvrzeni_mezi_doptanim_a_volbou_slot_nerusi(self):
        # Člověk si smí PŘED volbou doplnit znalost — kontext slot nechává.
        self.bridge.ask("Je auto dopravní prostředek?")
        self.bridge.context("Auto je dopravní prostředek.")
        vysledek = self.bridge.resolve_reference("class")
        self.assertEqual(vysledek["truth"], "TRUE")

    def test_neplatna_volba_je_chyba(self):
        self.bridge.context("Auto je dopravní prostředek.")
        self.bridge.ask("Je auto dopravní prostředek?")
        with self.assertRaises(ValueError):
            self.bridge.resolve_reference("cokoliv")
```

- [ ] **Step 2: Ověřit, že padají** — `./run-python -m unittest cb_bond.tests.test_logic -v`.

- [ ] **Step 3: Implementace v `cb_bond/logic.py`.**

Import: `from cb_interpret import (Candidate, DialogueLearner, …)` (rozšířit
stávající import). Modulová konstanta a `__init__`:

```python
#: Příkaz okna/konzole pro každou volbu doptání — REST je posílá v
#: `options[].command`, aby klikací klient věděl, co odeslat.
COMMAND_OF_CHOICE = {"instance": ":instance", "class": ":trida"}
```

Do `__init__` (za `self.learner = …`):

```python
        #: Poslední nejednoznačný dotaz (rozpracovaný dialog, ne znalost —
        #: nepersistuje se). Jeden slot: volba se vztahuje k poslednímu
        #: doptání, nová otázka ho přepíše.
        self.pending_reference: Candidate | None = None
```

`ask()`: na začátek metody (hned za docstring) přidat
`self.pending_reference = None`; ve větvi `reference_ambiguous` před
`return` přidat `self.pending_reference = result.candidate` a do options
přidat command:

```python
        if kind == "reference_ambiguous":
            ref = result.reference
            self.pending_reference = result.candidate
            return {"kind": "reference_ambiguous",
                    "subject": ref.subject_lemma,
                    "question": ref.question,
                    "options": [{"choice": c, "popis": p,
                                 "command": COMMAND_OF_CHOICE[c]}
                                for c, p in ref.options]}
```

Konec `ask()` (od `output = {…}` po `return output`) vytáhnout do helperu a
zavolat ho:

```python
        output: dict[str, Any] = {"kind": kind}
        output.update(self._query_output(result))
        return output

    def _query_output(self, result) -> dict[str, Any]:
        """Formální odpověď na dotaz — sdílí ji ask() i resolve_reference()."""
        output: dict[str, Any] = {
            "truth": result.truth.name if result.truth is not None else None,
            "answer": (render_truth(result.truth, self.profile)
                       if result.truth is not None else None),
            "explanations": [render_explanation(e, self.profile)
                             for e in result.explanations],
            "conflicted": result.conflicted,
        }
        if result.why_not is not None:
            output["why_not_kind"] = result.why_not.kind
            output["missing"] = [
                render_literal(lit, self.profile)
                for suggestion in result.why_not.suggestions
                for lit in suggestion.missing]
        return output
```

Nová metoda (za `ask()`):

```python
    def resolve_reference(self, choice: str) -> dict[str, Any]:
        """Dokončí poslední doptání na referenci volbou člověka (§ 5).

        Bez čekajícího doptání vrací hlášku, ne chybu: „není nač
        odpovídat" je platný stav dialogu, ne rozbitá služba.
        """
        if choice not in COMMAND_OF_CHOICE:
            raise ValueError(f"volba musí být instance|class, ne {choice!r}")
        pending = self.pending_reference
        if pending is None:
            return {"kind": "no_pending_reference",
                    "note": "žádné doptání na referenci nečeká"}
        self.pending_reference = None
        result = self.learner.resolve_reference(pending, choice)
        output: dict[str, Any] = {
            "kind": "reference_resolved", "choice": choice,
            "subject": pending.predication.subject.lemma,
            "source_text": pending.source_text,
        }
        output.update(self._query_output(result))
        return output
```

`state()`: změnit anotaci na `dict[str, Any]` a přidat
`"pending_reference": self.pending_reference is not None`.

Pozn.: `resolve_reference` u volby `class` vrací `AskResult` bez `why_not`
(jen truth) — `_query_output` to unese (explanations prázdné, why_not None).

- [ ] **Step 4: Testy zeleně** — `./run-python -m unittest cb_bond.tests.test_logic -v`.

- [ ] **Step 5: Commit** — `logika: stav posledního doptání na referenci + resolve_reference (4.1.3)`.

---

### Task 4: Služba, REST a klient — `resolve_reference`

**Files:**
- Modify: `cb_bond/service.py` (za `forget_word`)
- Modify: `cb_bond/api.py` (`do_POST` + nový handler)
- Modify: `cb_bond/client.py` (za `forget_word`)
- Test: `cb_bond/tests/test_service.py`, `cb_bond/tests/test_api.py`

**Interfaces:**
- Consumes: `LogicBridge.resolve_reference(choice)` z Task 3.
- Produces: `BondService.resolve_reference(choice) -> dict` (RuntimeError bez formální vrstvy); `POST /v1/logic/resolve` `{"choice": "instance"|"class"}`; `BondClient.resolve_reference(choice)`.

- [ ] **Step 1: Failing testy.** Do `test_service.py` (třída s testy `teach_pattern`/logiky, nebo nová):

```python
    def test_resolve_reference_bez_logiky_je_chyba(self):
        # učit/rozřešit do neexistující vrstvy by bylo tiché nedorozumění
        self.service.build()
        with self.assertRaises(RuntimeError):
            self.service.resolve_reference("class")
```

Do `test_api.py` (do `TestDotaz` stylu; `post` helper už existuje):

```python
class TestLogicResolve(Zaklad):
    """`POST /v1/logic/resolve` — dokončení doptání na referenci."""

    def post(self, cesta: str, telo: dict):
        data = json.dumps(telo, ensure_ascii=False).encode("utf-8")
        pozadavek = urllib.request.Request(
            self.adresa + cesta, data=data, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(pozadavek, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def test_spatna_volba_je_400(self):
        with self.assertRaises(urllib.error.HTTPError) as chyba:
            self.post("/v1/logic/resolve", {"choice": "cokoliv"})
        self.assertEqual(chyba.exception.code, 400)

    def test_bez_formalni_vrstvy_je_503(self):
        # fixtura nemá module.logic → služba to řekne typovaně, ne 500
        self.service.build()
        with self.assertRaises(urllib.error.HTTPError) as chyba:
            self.post("/v1/logic/resolve", {"choice": "class"})
        self.assertEqual(chyba.exception.code, 503)
        telo = json.loads(chyba.exception.read().decode("utf-8"))
        self.assertEqual(telo["error"]["type"], "not_built")
```

- [ ] **Step 2: Ověřit, že padají** (`AttributeError` / 404).

- [ ] **Step 3: Implementace.** `service.py` za `forget_word`:

```python
    def resolve_reference(self, choice: str) -> dict[str, Any]:
        """Dokončí poslední doptání formální vrstvy na referenci (§ 5)."""
        if self.logic is None:
            raise RuntimeError("formální vrstva neběží (chybí module.logic)")
        vysledek = self.logic.resolve_reference(choice)
        self._oznam(f"reference rozřešena: {choice} → "
                    f"{vysledek.get('answer') or vysledek['kind']}",
                    method="resolve_reference", result="ok",
                    output=vysledek)
        return vysledek
```

`api.py` — v `do_POST` rozšířit podmínku:

```python
        if cesta in ("/v1/logic/pattern", "/v1/logic/forget"):
            self._logic_pattern(cesta)
            return
        if cesta == "/v1/logic/resolve":
            self._logic_resolve()
            return
```

a nový handler vedle `_logic_pattern`:

```python
    def _logic_resolve(self) -> None:
        """Dokončení doptání na referenci — volba instance|class (§ 5)."""
        telo = self._precti_telo()
        if telo is None:
            return
        choice = telo.get("choice")
        if choice not in ("instance", "class"):
            self._chyba(HTTP_BAD_REQUEST, "invalid_request",
                        "klíč 'choice' musí být instance|class")
            return
        try:
            self._json(HTTP_OK,
                       self.server.service.resolve_reference(choice))
        except RuntimeError as e:
            self._chyba(HTTP_UNAVAILABLE, "not_built", str(e))
        except Exception as e:               # noqa: BLE001
            self._neocekavana(e)
```

`client.py` za `forget_word`:

```python
    def resolve_reference(self, choice: str) -> dict[str, Any]:
        """Dokončí doptání na referenci volbou instance|class (§ 5)."""
        return self._post("/v1/logic/resolve", {"choice": choice})
```

- [ ] **Step 4: Testy zeleně** — `./run-python -m unittest cb_bond.tests.test_api cb_bond.tests.test_service -v`.

- [ ] **Step 5: Commit** — `služba+REST: /v1/logic/resolve — dokončení doptání na referenci`.

---

### Task 5: Konzole a okno — `:instance` / `:trida` + zobrazení

**Files:**
- Modify: `cb_bond/window.py` (`format_logic`, `BondWindows._prikaz`, docstringy)
- Modify: `cb_bond/console.py` (`_prikaz`, `_KlientJakoSluzba`, docstring, import)
- Test: `cb_bond/tests/test_window.py`, `cb_bond/tests/test_console.py`

**Interfaces:**
- Consumes: `service.resolve_reference(choice)` (Task 4), `format_logic` (window).
- Produces: doptání v okně/konzoli ukazuje příkazy; `:instance`/`:trida` dokončí dotaz a vypíše odpověď; `format_logic` umí `reference_resolved` a `no_pending_reference`.

- [ ] **Step 1: Failing testy.** `test_window.py` — do `_Sluzba` přidat:

```python
    def resolve_reference(self, choice):
        self.resolved = choice
        return {"kind": "reference_resolved", "choice": choice,
                "subject": "auto", "source_text": "Je auto prostředek?",
                "truth": "TRUE", "answer": "Ano.",
                "explanations": ["auto je prostředek (doloženo: dialog)"],
                "conflicted": False}
```

a testy (do `TestFormatovani` / třídy s příkazy okna):

```python
    def test_doptani_na_referenci_ukaze_prikazy(self):
        radky = format_logic({
            "kind": "reference_ambiguous", "subject": "auto",
            "question": "Ptáš se na konkrétní auto, nebo na auta obecně?",
            "options": [
                {"choice": "instance", "popis": "konkrétní auto",
                 "command": ":instance"},
                {"choice": "class", "popis": "auto obecně (třída)",
                 "command": ":trida"}]})
        text = "\n".join(radky)
        self.assertIn(":instance", text)
        self.assertIn(":trida", text)

    def test_rozresena_reference_ukaze_odpoved_i_dolozeni(self):
        radky = format_logic({
            "kind": "reference_resolved", "choice": "class",
            "subject": "auto", "truth": "TRUE", "answer": "Ano.",
            "explanations": ["auto je prostředek (doloženo: dialog)"],
            "conflicted": False})
        self.assertIn("Ano.", radky[0])
        self.assertTrue(any("doloženo" in r for r in radky))

    def test_bez_cekajiciho_doptani_je_hlaska(self):
        radky = format_logic({"kind": "no_pending_reference",
                              "note": "žádné doptání na referenci nečeká"})
        self.assertIn("nečeká", radky[0])
```

a v třídě obsluhy vstupu okna (kde se testují `:vzor`/`:state`):

```python
    def test_prikaz_trida_dokonci_doptani(self):
        self.okno_vstup(":trida")     # použít tamní helper pro vstup řádku
        self.assertEqual(self.sluzba.resolved, "class")
        self.assertIn("Ano.", self.okno.texty(DIALOG_ID))
```

(Přesný tvar volání vstupu převzít z okolních testů příkazů v souboru —
`_na_vstup` se volá přes `SimpleNamespace(line=…)` nebo tamní helper.)

`test_console.py` — do `_Sluzba` přidat tutéž `resolve_reference` a test:

```python
    def test_instance_a_trida_dokonci_doptani(self):
        vystup = _konzole(":trida\n:quit\n")
        self.assertIn("Ano.", vystup)
```

(`_konzole` je tamní helper; ověřit jeho návratový tvar a přizpůsobit
aserci okolním testům.)

- [ ] **Step 2: Ověřit, že padají.**

- [ ] **Step 3: Implementace.** `window.py` — ve `format_logic` rozšířit
větev `reference_ambiguous` a přidat dvě nové větve (před obecnou):

```python
    if kind == "reference_ambiguous":
        radky = [f"  logika se ptá: {logika['question']}"]
        for volba in logika.get("options", ()):
            prikaz = volba.get("command", volba["choice"])
            radky.append(f"    · {prikaz} — {volba['popis']}")
        radky.append("    (odpověz příkazem :instance, nebo :trida)")
        return radky
    if kind == "no_pending_reference":
        return [f"  logika: {logika['note']}"]
    if kind == "reference_resolved":
        radky = [f"  logika ({logika['choice']}): {logika['answer']}"]
        for vysvetleni in logika.get("explanations", ()):
            radky.append(f"    {vysvetleni}")
        for chybejici in logika.get("missing", ()):
            radky.append(f"    chybí vědět: {chybejici}")
        if logika.get("conflicted"):
            radky.append("    pozor: k dotazu eviduji rozpor")
        return radky
```

`BondWindows._prikaz` — nová větev (před `else`) + rozšířit hlášku
neznámého příkazu o `:instance :trida`:

```python
        elif jmeno in ("instance", "trida"):
            volba = "instance" if jmeno == "instance" else "class"
            self._pis(DIALOG_ID, format_logic(
                self.service.resolve_reference(volba)))
```

`console.py` — import rozšířit o `format_logic`; do `_prikaz` (před
neznámý příkaz) přidat:

```python
        if jmeno in ("instance", "trida"):
            volba = "instance" if jmeno == "instance" else "class"
            for radek in format_logic(self.service.resolve_reference(volba)):
                self._pis(radek)
            return True
```

hlášku neznámého příkazu a modulový docstring doplnit o
`:instance` / `:trida` (odpověď na doptání reference). Do
`_KlientJakoSluzba` přidat:

```python
    def resolve_reference(self, choice: str) -> dict[str, Any]:
        return self.klient.resolve_reference(choice)
```

- [ ] **Step 4: Testy zeleně** — `./run-python -m unittest cb_bond.tests.test_window cb_bond.tests.test_console -v`.

- [ ] **Step 5: Commit** — `okna+konzole: :instance/:trida dokončí doptání na referenci (4.1.3)`.

---

### Task 6: Slovesné složené přísudky — bezztrátový rozklad (4.1.1)

**Files:**
- Modify: `cb_interpret/interpret.py` (`_verbal`, nový `verb_conjuncts`, smazat `_predicate_atom`)
- Modify: `cb_interpret/tests/vzorky_struct.py` (nové zmražené rozbory)
- Test: `cb_interpret/tests/test_interpret.py`

**Interfaces:**
- Consumes: `_kids`, `_negated`, `_entity`, `_term_for`, `_ref`, `Candidate`, `conj` — beze změny.
- Produces: `verb_conjuncts(children, verb, subject_term, subject_token) -> (conjuncts, relations, entities, blocker)`; konjunkt je `(atom, positive, token_id, popis)`, `blocker` je důvod odmítnutí nebo `None`. Task 7 ho použije pro xcomp.

Rozklad (mechanismus `build_conjuncts`, expanze § 2.2):

```
obj                sloveso(podmět, předmět)          znát(petr, jana)
obl + case         sloveso_předložka(podmět, cíl)    jet_po(petr, dálnice)
obl bez case       sloveso_pád(podmět, cíl)          jet_ins(petr, auto)
advmod (ADV)       sloveso_příslovce(podmět)         jet_rychle(petr)
bez argumentů      sloveso(podmět)                   spát(petr)
```

Vazba mimo tento výčet (`iobj`, `ccomp`, `advcl`, `aux`, `expl`, druhý
`obj`, rozvitý argument, `obl` bez předložky i pádu…) → `unparsed`
s důvodem — pojistka z expanze § 2.3. Negace s VÍCE konjunkty → `unparsed`
(týž De Morgan guard jako u kopuly). Zpětná kompatibilita: „Petr bydlí
v Praze." dává dál JEDINÝ literál `bydlet_v(petr, praha)` (žádný nový holý
konjunkt `bydlet(petr)` u vět s argumenty).

- [ ] **Step 1: Nové zmražené rozbory do `vzorky_struct.py`** (skutečný UDPipe cs_all-ud-2.17, 2026-08-10):

```python
PETR_JEDE_AUTEM = (  # Petr jede autem po dálnici.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='jede', lemma='jet', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='autem', lemma='auto', upos='NOUN', xpos='NNNS7-----A----', feats={'Case': 'Ins', 'Gender': 'Neut', 'Number': 'Sing'}, head=2, deprel='obl', deps=None, misc=None),
    Token(id=4, form='po', lemma='po', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='dálnici', lemma='dálnice', upos='NOUN', xpos='NNFS6-----A----', feats={'Case': 'Loc', 'Gender': 'Fem', 'Number': 'Sing'}, head=2, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

JEDE_PETR_AUTEM = (  # Jede Petr autem po dálnici?
    Token(id=1, form='Jede', lemma='jet', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=2, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=1, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='autem', lemma='auto', upos='NOUN', xpos='NNNS7-----A----', feats={'Case': 'Ins', 'Gender': 'Neut', 'Number': 'Sing'}, head=1, deprel='obl', deps=None, misc=None),
    Token(id=4, form='po', lemma='po', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='dálnici', lemma='dálnice', upos='NOUN', xpos='NNFS6-----A----', feats={'Case': 'Loc', 'Gender': 'Fem', 'Number': 'Sing'}, head=1, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=1, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_RYCHLE_JEDE = (  # Petr rychle jede po dálnici.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='rychle', lemma='rychle', upos='ADV', xpos='Dg-------1A----', feats={'Degree': 'Pos', 'Polarity': 'Pos'}, head=3, deprel='advmod', deps=None, misc=None),
    Token(id=3, form='jede', lemma='jet', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='po', lemma='po', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='dálnici', lemma='dálnice', upos='NOUN', xpos='NNFS6-----A----', feats={'Case': 'Loc', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_DAL_PAVLOVI = (  # Petr dal Pavlovi knihu.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='dal', lemma='dát', upos='VERB', xpos='VpYS----R-AAP--', feats={'Aspect': 'Perf', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos', 'Tense': 'Past', 'VerbForm': 'Part', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='Pavlovi', lemma='Pavel', upos='PROPN', xpos='NNMS3-----A----', feats={'Animacy': 'Anim', 'Case': 'Dat', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='obl:arg', deps=None, misc=None),
    Token(id=4, form='knihu', lemma='kniha', upos='NOUN', xpos='NNFS4-----A----', feats={'Case': 'Acc', 'Gender': 'Fem', 'Number': 'Sing'}, head=2, deprel='obj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_RIDI_AUTO = (  # Petr řídí červené auto.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='řídí', lemma='řídit', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='červené', lemma='červený', upos='ADJ', xpos='AANS4----1A----', feats={'Case': 'Acc', 'Degree': 'Pos', 'Gender': 'Neut', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='auto', lemma='auto', upos='NOUN', xpos='NNNS4-----A----', feats={'Case': 'Acc', 'Gender': 'Neut', 'Number': 'Sing'}, head=2, deprel='obj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

MARIE_PRACUJE = (  # Marie pracuje v Brně.   (generalizace — unseen)
    Token(id=1, form='Marie', lemma='Marie', upos='PROPN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='pracuje', lemma='pracovat', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='v', lemma='v', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=4, deprel='case', deps=None, misc=None),
    Token(id=4, form='Brně', lemma='Brno', upos='PROPN', xpos='NNNS6-----A----', feats={'Case': 'Loc', 'Gender': 'Neut', 'NameType': 'Geo', 'Number': 'Sing'}, head=2, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)
```

- [ ] **Step 2: Failing testy** (nová třída v `test_interpret.py`):

```python
class TestVerbalCompound(unittest.TestCase):
    """Slovesná věta se rozkládá bezztrátově — HANDOVER 4.1.1, expanze § 2."""

    def test_dve_obliky_daji_dva_konjunkty(self):
        c = interpret_sentence(vs.PETR_JEDE_AUTEM,
                               "Petr jede autem po dálnici.")
        self.assertEqual(c.kind, "fact")
        rel = {l.atom.relation.name for l in c.literals}
        self.assertEqual(rel, {"jet_ins", "jet_po"})   # „autem" se neztrácí
        for l in c.literals:
            self.assertEqual(l.atom.args[0], Entity("petr"))

    def test_otazka_nad_konjunkci(self):
        c = interpret_sentence(vs.JEDE_PETR_AUTEM,
                               "Jede Petr autem po dálnici?")
        self.assertEqual(c.kind, "query")
        self.assertEqual({a.relation.name for a in c.query_atoms},
                         {"jet_ins", "jet_po"})

    def test_prislovce_je_vlastnost_deje(self):
        c = interpret_sentence(vs.PETR_RYCHLE_JEDE,
                               "Petr rychle jede po dálnici.")
        self.assertEqual(c.kind, "fact")
        rel = {l.atom.relation.name for l in c.literals}
        self.assertEqual(rel, {"jet_rychle", "jet_po"})  # „rychle" žije
        rychle = [l for l in c.literals
                  if l.atom.relation.name == "jet_rychle"][0]
        self.assertEqual(rychle.atom.args, (Entity("petr"),))

    def test_holy_dativ_je_vztah_pojmenovany_padem(self):
        c = interpret_sentence(vs.PETR_DAL_PAVLOVI, "Petr dal Pavlovi knihu.")
        self.assertEqual(c.kind, "fact")
        rel = {l.atom.relation.name for l in c.literals}
        self.assertEqual(rel, {"dát", "dát_dat"})
        dativ = [l for l in c.literals
                 if l.atom.relation.name == "dát_dat"][0]
        self.assertEqual(dativ.atom.args, (Entity("petr"), Entity("pavel")))

    def test_rozvity_argument_je_unparsed_ne_tichy(self):
        # „červené auto" jako předmět: amod nejde bez událostí věrně
        # snížit na Value — poctivé odmítnutí místo tichého zahození
        c = interpret_sentence(vs.PETR_RIDI_AUTO, "Petr řídí červené auto.")
        self.assertEqual(c.kind, "unparsed")

    def test_generalizace_unseen_veta(self):
        c = interpret_sentence(vs.MARIE_PRACUJE, "Marie pracuje v Brně.")
        self.assertEqual(c.kind, "fact")
        self.assertEqual(c.literals[0].atom.relation,
                         Relation("pracovat_v", 2))
        self.assertEqual(c.literals[0].atom.args,
                         (Entity("marie"), Entity("brno")))

    def test_generalizace_prejmenovani(self):
        import dataclasses
        mapa = {"Petr": "Karel", "jet": "letět", "auto": "vlak",
                "dálnice": "pole"}
        prejmenovano = tuple(
            dataclasses.replace(t, lemma=mapa.get(t.lemma, t.lemma))
            for t in vs.PETR_JEDE_AUTEM)
        c = interpret_sentence(prejmenovano, "Karel letí vlakem po poli.")
        self.assertEqual({l.atom.relation.name for l in c.literals},
                         {"letět_ins", "letět_po"})

    def test_negace_slozeneho_prisudku_je_unparsed(self):
        import dataclasses
        negovano = tuple(
            dataclasses.replace(t, feats=dict(t.feats, Polarity="Neg"))
            if t.deprel == "root" else t for t in vs.PETR_JEDE_AUTEM)
        c = interpret_sentence(negovano, "Petr nejede autem po dálnici.")
        self.assertEqual(c.kind, "unparsed")
```

- [ ] **Step 3: Ověřit, že padají** — `./run-python -m unittest cb_interpret.tests.test_interpret -v`.

- [ ] **Step 4: Implementace v `interpret.py`.** Smazat `_predicate_atom`,
nahradit `_verbal` a přidat `verb_conjuncts` (sekce „slovesné věty"):

```python
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
    (atom, positive, token_id, popis). blocker je důvod odmítnutí, jinak None.
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
                              child.id,
                              f"{verb.lemma}(…, {child.lemma})"))
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
```

- [ ] **Step 5: Testy zeleně** — celý `cb_interpret` + `cb_bond`
(`./run-python -m unittest discover -s cb_interpret -t .` a
`discover -s cb_bond -t .`) — staré slovesné testy (PETR_BYDLI, PETR_ZNA,
MUZE_AUTO_JET v cb_bond) nesmí spadnout. POZOR: `_operator` v tomto tasku
ještě volá staré `_predicate_atom` — smazat ho až v Tasku 7; tady ho
ponechat a odstranit až po přepnutí `_operator`. (Alternativně Task 6+7
commitovat spolu; rozhodne zelenost.)

- [ ] **Step 6: Commit** — `cb_interpret: bezztrátový rozklad slovesné věty (advmod, více argumentů, holé pády)`.

---

### Task 7: `_operator` — modální dotaz nad konjunkcí (4.1.1 pokr.)

**Files:**
- Modify: `cb_interpret/interpret.py` (`_operator`, smazat `_predicate_atom`)
- Modify: `cb_interpret/learner.py` (`_run_modal`, `_answer_modal`)
- Modify: `cb_interpret/tests/vzorky_struct.py` (jeden vzorek)
- Test: `cb_interpret/tests/test_learn_pattern.py` (nebo `test_learner.py`, dle umístění modálních testů)

**Interfaces:**
- Consumes: `verb_conjuncts` z Task 6.
- Produces: `modal_query`/`needs_pattern` Candidate nese `query_expr` + `query_atoms` (konjunkce) a dál i `literal` (první konjunkt, zpětná kompatibilita); `_run_modal(kb, atoms, expr, operation, negated)`.

- [ ] **Step 1: Vzorek do `vzorky_struct.py`:**

```python
AUTO_MUZE_JET_DO_MESTA = (  # Auto může jet po dálnici do města.
    Token(id=1, form='Auto', lemma='auto', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='může', lemma='moci', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='jet', lemma='jet', upos='VERB', xpos='Vf--------A-I--', feats={'Aspect': 'Imp', 'Polarity': 'Pos', 'VerbForm': 'Inf'}, head=2, deprel='xcomp', deps=None, misc=None),
    Token(id=4, form='po', lemma='po', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='dálnici', lemma='dálnice', upos='NOUN', xpos='NNFS6-----A----', feats={'Case': 'Loc', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='obl', deps=None, misc=None),
    Token(id=6, form='do', lemma='do', upos='ADP', xpos='RR--2----------', feats={'AdpType': 'Prep', 'Case': 'Gen'}, head=7, deprel='case', deps=None, misc=None),
    Token(id=7, form='města', lemma='město', upos='NOUN', xpos='NNNS2-----A----', feats={'Case': 'Gen', 'Gender': 'Neut', 'Number': 'Sing'}, head=3, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=8, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)
```

- [ ] **Step 2: Failing test** (k modálním testům learneru; importy dle souboru):

```python
    def test_slozeny_xcomp_je_modalni_dotaz_nad_konjunkci(self):
        learner = DialogueLearner(KnowledgeBase())
        learner.teach_pattern(
            StructuralSignature("moci", has_xcomp=True),
            Operation.POSSIBLE, learned_from="test")
        result = learner.ask(vs.AUTO_MUZE_JET_DO_MESTA,
                             "Auto může jet po dálnici do města.")
        self.assertEqual(result.candidate.kind, "modal_query")
        self.assertEqual({a.relation.name
                          for a in result.candidate.query_atoms},
                         {"jet_po", "jet_do"})       # „do města" se neztrácí
        self.assertIs(result.modal["answer"], True)  # nic to nezakazuje…
        self.assertFalse(result.modal["grounded"])   # …ale nic to nedokládá
```

- [ ] **Step 3: Ověřit, že padá.**

- [ ] **Step 4: Implementace.** `interpret.py` — `_operator` přepsat (a až
teď smazat `_predicate_atom`):

```python
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
    query_expr = conj(*exprs) if len(exprs) > 1 else exprs[0]
    query_atoms = tuple(a for a, _, _, _ in conjuncts)
    literal = Literal(conjuncts[0][0], conjuncts[0][1])
    common = dict(literal=literal, query_expr=query_expr,
                  query_atoms=query_atoms, negated=negated,
                  relations=tuple(relations), entities=tuple(entities),
                  signature=signature)
    matched = patterns.match(signature) if patterns is not None else None
    if matched is not None:
        return Candidate("modal_query", text,
                         operation=matched.operation, **common)
    return Candidate("needs_pattern", text,
                     note=f"neznámé mapování operátoru {root.lemma!r}",
                     **common)
```

`learner.py` — `_run_modal` a `_answer_modal`:

```python
def _run_modal(kb: KnowledgeBase, atoms, expr, operation: Operation,
               negated: bool):
    """Modální dotaz jako kvantifikace nad modely (∃M/∀M/¬∃M), ne operátor.

    Propozice smí být konjunkce atomů (složený vložený přísudek).
    `grounded` rozlišuje „našel model" od „nic to nezakazuje": je true,
    dotýká-li se KTERÝKOLI konjunkt nějaké znalosti.
    """
    mood = operation
    if negated:
        if operation is Operation.POSSIBLE:
            mood = Operation.IMPOSSIBLE
        elif operation is Operation.IMPOSSIBLE:
            mood = Operation.POSSIBLE
        else:
            mood, expr = Operation.POSSIBLE, Not(expr)
    result: ModalResult = classify_query(kb, expr)
    verdict = result.verdict
    if verdict is ModalVerdict.INCOMPLETE:
        answer: bool | None = None
    elif mood is Operation.POSSIBLE:
        answer = verdict in (ModalVerdict.POSSIBLE, ModalVerdict.NECESSARY)
    elif mood is Operation.NECESSARY:
        answer = verdict is ModalVerdict.NECESSARY
    else:
        answer = verdict in (ModalVerdict.IMPOSSIBLE,
                             ModalVerdict.UNSATISFIABLE)
    grounded = any(_touches_knowledge(kb, atom) for atom in atoms)
    return mood, result, answer, grounded
```

a v `_answer_modal`:

```python
    def _answer_modal(self, candidate: Candidate) -> AskResult:
        atoms = candidate.query_atoms or (candidate.literal.atom,)
        expr = candidate.query_expr or AtomRef(candidate.literal.atom)
        mood, result, answer, grounded = _run_modal(
            self.kb, atoms, expr, candidate.operation, candidate.negated)
```

(zbytek metody beze změny).

- [ ] **Step 5: Testy zeleně** — celé `cb_interpret` (vč.
`test_pattern_guard`!) + `cb_bond.tests.test_logic`
(MUZE_AUTO_JET má jediný obl → chování beze změny).

- [ ] **Step 6: Commit** — `cb_interpret: modální dotaz nad konjunkcí — složený vložený přísudek (4.1.1)`.

---

### Task 8: Genitivní / holopádový `nmod` jako vztah (4.1.2)

**Files:**
- Modify: `cb_interpret/predication.py` (`RelationMod`, `Predication`, `extract_copular`)
- Modify: `cb_interpret/interpret.py` (`build_conjuncts`, `_lower_copular`)
- Modify: `cb_interpret/tests/vzorky_struct.py` (nové vzorky)
- Test: `cb_interpret/tests/test_interpret.py`, `cb_interpret/tests/test_learner.py` (plný kruh)

**Interfaces:**
- Consumes: `Predication`, `build_conjuncts` (Task 6 se jich nedotkl).
- Produces: `RelationMod.marker` (přejmenované z `preposition` — nese předložku NEBO pádový marker `gen`/`dat`/…); `Predication.blockers: tuple[str, ...]`; `nmod` bez `case` s `Case` featem → vztah pojmenovaný pádem; bez obojího → `unparsed` (pojistka expanze § 2.3).

- [ ] **Step 1: Vzorky do `vzorky_struct.py`:**

```python
PRAHA_MESTO_CESKA = (  # Praha je hlavní město Česka.
    Token(id=1, form='Praha', lemma='Praha', upos='PROPN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'NameType': 'Geo', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=3, form='hlavní', lemma='hlavní', upos='ADJ', xpos='AANS1----1A----', feats={'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Neut', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='město', lemma='město', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=5, form='Česka', lemma='Česko', upos='PROPN', xpos='NNNS2-----A----', feats={'Case': 'Gen', 'Gender': 'Neut', 'NameType': 'Geo', 'Number': 'Sing'}, head=4, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

JE_PRAHA_MESTO_CESKA = (  # Je Praha hlavní město Česka?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=2, form='Praha', lemma='Praha', upos='PROPN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'NameType': 'Geo', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='hlavní', lemma='hlavní', upos='ADJ', xpos='AANS1----1A----', feats={'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Neut', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='město', lemma='město', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=5, form='Česka', lemma='Česko', upos='PROPN', xpos='NNNS2-----A----', feats={'Case': 'Gen', 'Gender': 'Neut', 'NameType': 'Geo', 'Number': 'Sing'}, head=4, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

KLIC_SOUCAST_ZAMKU = (  # Klíč je součást zámku.
    Token(id=1, form='Klíč', lemma='klíč', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='součást', lemma='součást', upos='NOUN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='zámku', lemma='zámek', upos='NOUN', xpos='NNIS2-----A----', feats={'Animacy': 'Inan', 'Case': 'Gen', 'Gender': 'Masc', 'Number': 'Sing'}, head=3, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

KNIHA_MAJETEK = (  # Kniha je majetek knihovny.   (generalizace — unseen)
    Token(id=1, form='Kniha', lemma='kniha', upos='NOUN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='majetek', lemma='majetek', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='knihovny', lemma='knihovna', upos='NOUN', xpos='NNFS2-----A----', feats={'Case': 'Gen', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

VLTAVA_REKA = (  # Vltava je řeka Česka.   (generalizace — unseen)
    Token(id=1, form='Vltava', lemma='Vltava', upos='PROPN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'NameType': 'Geo', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='řeka', lemma='řeka', upos='NOUN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='Česka', lemma='Česko', upos='PROPN', xpos='NNNS2-----A----', feats={'Case': 'Gen', 'Gender': 'Neut', 'NameType': 'Geo', 'Number': 'Sing'}, head=3, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)
```

- [ ] **Step 2: Failing testy** (nová třída v `test_interpret.py` + plný
kruh do `test_learner.py`):

```python
class TestGenitiveNmod(unittest.TestCase):
    """Holý genitiv je vztah, ne tiché zahození — HANDOVER 4.1.2."""

    def test_genitiv_jednotlivina_da_tri_fakty(self):
        c = interpret_sentence(vs.PRAHA_MESTO_CESKA,
                               "Praha je hlavní město Česka.")
        self.assertEqual(c.kind, "fact")
        rel = {l.atom.relation.name for l in c.literals}
        self.assertEqual(rel, {"město", "hlavní", "gen"})   # „Česka" žije
        gen = [l for l in c.literals if l.atom.relation.name == "gen"][0]
        self.assertEqual(gen.atom.args, (Entity("praha"), Entity("česko")))

    def test_genitiv_otazka(self):
        c = interpret_sentence(vs.JE_PRAHA_MESTO_CESKA,
                               "Je Praha hlavní město Česka?")
        self.assertEqual(c.kind, "query")
        self.assertEqual({a.relation.name for a in c.query_atoms},
                         {"město", "hlavní", "gen"})

    def test_genitiv_trida_da_pravidla(self):
        c = interpret_sentence(vs.KLIC_SOUCAST_ZAMKU, "Klíč je součást zámku.")
        self.assertEqual(c.kind, "rule")
        heads = {r.head.atom.relation.name for r in c.rules}
        self.assertEqual(heads, {"součást", "gen"})
        gen = [r for r in c.rules if r.head.atom.relation.name == "gen"][0]
        self.assertEqual(gen.head.atom.args[1], Value("zámek"))

    def test_nmod_bez_predlozky_i_padu_je_unparsed(self):
        import dataclasses
        bez_padu = tuple(
            dataclasses.replace(t, feats=None) if t.deprel == "nmod" else t
            for t in vs.PRAHA_MESTO_CESKA)
        c = interpret_sentence(bez_padu, "Praha je hlavní město Česka.")
        self.assertEqual(c.kind, "unparsed")   # pojistka, ne tiché zahození

    def test_generalizace_unseen_trida(self):
        c = interpret_sentence(vs.KNIHA_MAJETEK, "Kniha je majetek knihovny.")
        self.assertEqual(c.kind, "rule")
        self.assertEqual({r.head.atom.relation.name for r in c.rules},
                         {"majetek", "gen"})

    def test_generalizace_unseen_jednotlivina(self):
        c = interpret_sentence(vs.VLTAVA_REKA, "Vltava je řeka Česka.")
        self.assertEqual(c.kind, "fact")
        self.assertEqual({l.atom.relation.name for l in c.literals},
                         {"řeka", "gen"})
```

Plný kruh (do `test_learner.py`, styl okolních testů):

```python
    def test_plny_kruh_genitiv(self):
        learner = DialogueLearner(KnowledgeBase())
        r = learner.learn(vs.PRAHA_MESTO_CESKA, "Praha je hlavní město Česka.")
        self.assertEqual(r.candidate.kind, "fact")
        self.assertEqual(r.accepted, 3)
        result = learner.ask(vs.JE_PRAHA_MESTO_CESKA,
                             "Je Praha hlavní město Česka?")
        self.assertEqual(result.truth, Truth.TRUE)
```

- [ ] **Step 3: Ověřit, že padají.**

- [ ] **Step 4: Implementace.** `predication.py`:

```python
@dataclass(frozen=True)
class RelationMod:
    """Vazba nmod jako binární vztah k cíli.

    marker: co vztah pojmenovalo — předložka (nmod+case), nebo pádový
    marker holého pádu (`gen`, `dat`, …). Jméno z UD hodnoty Case je
    strukturální a nepodsouvá posesivní čtení, které věta nemá.
    """
    marker: str
    target_lemma: str
    target_upos: str
    token_id: int
```

`Predication` doplnit pole (na konec): `blockers: tuple[str, ...] = ()` —
kusy, které extrakce neunese; lowering je promění v `unparsed` s důvodem.
`extract_copular` — smyčka nmod:

```python
    relations = []
    blockers = []
    for nmod in _kids(children, root, "nmod"):
        cases = _kids(children, nmod, "case")
        if cases:
            relations.append(RelationMod(cases[0].lemma, nmod.lemma,
                                         nmod.upos, nmod.id))
        elif nmod.feats and nmod.feats.get("Case"):
            # holý pád (genitiv „město Česka") pojmenuje vztah sám
            relations.append(RelationMod(nmod.feats["Case"].lower(),
                                         nmod.lemma, nmod.upos, nmod.id))
        else:
            blockers.append(f"vazba nmod bez předložky i pádu "
                            f"({nmod.lemma!r}) mimo rozsah")
```

a `blockers=tuple(blockers)` do konstruktoru `Predication`. `interpret.py`:
v `build_conjuncts` nahradit `rmod.preposition` → `rmod.marker` (2 místa);
na začátek `_lower_copular` (před guard negace):

```python
    if pred.blockers:
        # Tiché zahození mění význam — kus, který extrakce neunese,
        # větu poctivě shodí (pojistka, expanze § 2.3).
        return _unparsed(text, pred.blockers[0])
```

- [ ] **Step 5: Testy zeleně** — plná sada
`./run-python -m unittest discover -s . -p "test_*.py" -t .`.

- [ ] **Step 6: Commit** — `cb_interpret: holý genitiv/pád u nmod jako vztah, pojistka unparsed (4.1.2)`.

---

### Task 9: Dokumentace, guardy, plná sada, merge

**Files:**
- Modify: `HANDOVER.md` (§ 3, § 4.1, § 4.4, § 7 — hotové položky, nové příkazy, nový počet testů)
- Modify: `INTERPRETATION_IR.md` (hlavička „Stav", § 2 tabulka extrakce o slovesné/genitivní řádky, § 5 pozn. o zapojení v UI)

**Interfaces:** —

- [ ] **Step 1: Dokumentace.** V `INTERPRETATION_IR.md` upravit úvodní
„Stav" (slovesné složené přísudky a genitivní `nmod` implementované),
do § 2 přidat slovesný rozklad a holopádový `nmod` (tabulka z Task 6 +
`gen`), do § 5 dopsat, že doptání je zapojené v okně/konzoli
(`:instance`/`:trida`) a REST (`/v1/logic/resolve`). V `HANDOVER.md`
označit 4.1 body 1–3 a 4.4 první dvě odrážky jako hotové (přesunout do
§ 3 se stručným popisem), do § 7 přidat příkazy `:instance`/`:trida`
a aktualizovat počet testů.

- [ ] **Step 2: Import guardy + plná sada:**

```bash
grep -rn "^from cb_\|^import cb_" cb_logic/ --include='*.py' | grep -v "cb_logic"      # prázdné
grep -rhn "^from cb_\|^import cb_" cb_interpret/*.py | grep -vE "cb_interpret|cb_logic|cb_udpipe"  # prázdné
./run-python -m unittest discover -s . -p "test_*.py" -t .
```

Všechno zeleně; zapsat nový počet testů do HANDOVER.md.

- [ ] **Step 3: Commit** — `handover + dokumentace: stav po dokončení fronty 4.1 a dluhů 4.4`.

- [ ] **Step 4: Merge.** Podle skillu `superpowers:finishing-a-development-branch`:
merge `feature/handover-fronta` do `main` (repo konvence: merge commit se
shrnutím), větev smazat.

---

## Self-review (hotovo při psaní plánu)

- **Pokrytí expanze:** § 1 reference → Tasky 3–5; § 2.2 slovesa → Tasky 6–7; § 2.3 genitiv → Task 8; § 3.1 skripty → Task 1; § 3.2 MatchResult → Task 2; § 4 pořadí dodrženo. Odchylky vyjmenované v hlavičce plánu s důvody.
- **Vědomě mimo:** `training.py answer_position`, T‑12 AST test, drift `requirements.txt` (HANDOVER 4.4 zbytek — expanze je nevybrala); `chtít`/postoje, scelování lemmat, koreference (4.1.4–6).
- **Typová konzistence:** `verb_conjuncts` vrací čtveřici i pro `_operator`; `RelationMod.marker` používá jen `predication.py` + `build_conjuncts`; `resolve_reference` choice `"instance"|"class"` shodně v bridge/service/REST/klientu/konzoli.
- **Rizika:** (a) tvar volání vstupu v `test_window` — převzít z okolních testů souboru; (b) Task 6 nechává `_predicate_atom` dočasně pro `_operator` (smaže Task 7) — pokud by lint/testy křičely na nepoužívané, commitnout T6+T7 spolu; (c) pořadí členů `options` je dané `ReferenceClarification.options` (instance, class) — testy porovnávají množiny.
