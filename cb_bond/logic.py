"""Most k formálnímu jádru — učení z dialogu, formální odpovědi, doptávání.

Nová vrstva stojí VEDLE retrieval cesty (migrace, ARCHITECTURE_REVIEW § 15):
odpovídá, když umí; mlčí-li (unparsed), jede párování jako dřív a klíč
`logic` v odpovědi je None. Znalost i naučené jazykové vzory se persistují
a přežívají restart (dluh P5 pro novou vrstvu).

Systém se doptává dvěma způsoby (LANGUAGE_LEARNING.md, PROVENANCE.md § 3):
neznámý operátor → nabídne menu operací; UNKNOWN dotaz nad pravidlem →
vrátí chybějící premisy (neexistující vztahy, které by odpověď umožnily).

Při chybě: poškozený soubor báze je hlasitá chyba startu, ne tichý
začátek od nuly — ztráta naučeného se nesmí zamlčet.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cb_logic import KnowledgeBase, kb_from_json, kb_to_json
from cb_interpret import (Candidate, DialogueLearner, Operation, PatternStore,
                          StructuralSignature, cs_profile, render_explanation,
                          render_literal, render_truth)

FORMAT = "conbond-logic/1"

#: Příkaz okna/konzole pro každou volbu doptání — REST je posílá v
#: `options[].command`, aby klikací klient věděl, co odeslat.
COMMAND_OF_CHOICE = {"instance": ":instance", "class": ":trida"}


class LogicBridge:
    """Jedna formální báze + store vzorů nad službou; parser se předává."""

    def __init__(self, parser, kb_file: str | Path) -> None:
        self.parser = parser
        self.kb_file = Path(kb_file)
        self.profile = cs_profile()
        kb = KnowledgeBase()
        patterns = PatternStore()
        if self.kb_file.exists():
            data = json.loads(self.kb_file.read_text(encoding="utf-8"))
            if "kb" in data:                       # nový formát {kb, patterns}
                kb = kb_from_json(data["kb"])
                patterns = PatternStore.from_json(data.get("patterns", []))
            else:                                  # starý formát: holá báze
                kb = kb_from_json(data)
        self.learner = DialogueLearner(kb, self.profile, patterns=patterns)
        #: Poslední nejednoznačný dotaz (rozpracovaný dialog, ne znalost —
        #: nepersistuje se). Jeden slot: volba se vztahuje k poslednímu
        #: doptání, nová otázka ho přepíše.
        self.pending_reference: Candidate | None = None

    # --- dialog ---------------------------------------------------------

    def context(self, text: str) -> dict[str, Any]:
        """Věta od člověka → interpretace → validace → inference → uložení."""
        tokens = self._tokens(text)
        if tokens is None:
            return {"kind": "unparsed", "note": "rozbor nedal žádnou větu"}
        result = self.learner.learn(tokens, text)
        summary: dict[str, Any] = {
            "kind": result.candidate.kind,
            "note": result.candidate.note,
            "outcome": (type(result.outcome).__name__.lower()
                        if result.outcome is not None else None),
            "derived": ([render_literal(l, self.profile)
                         for l in result.inference.new_facts]
                        if result.inference is not None else []),
            "conflicts": len(self.learner.kb.conflicts),
        }
        if result.outcome is not None:
            self.save()
        return summary

    def ask(self, text: str) -> dict[str, Any] | None:
        """Formální odpověď, doptání, nebo None — pak odpovídá retrieval."""
        self.pending_reference = None
        tokens = self._tokens(text)
        if tokens is None:
            return None
        result = self.learner.ask(tokens, text)
        kind = result.candidate.kind
        if kind == "unparsed":
            return None
        if kind == "reference_ambiguous":
            ref = result.reference
            self.pending_reference = result.candidate
            return {"kind": "reference_ambiguous", "subject": ref.subject_lemma,
                    "question": ref.question,
                    "options": [{"choice": c, "popis": p,
                                 "command": COMMAND_OF_CHOICE[c]}
                                for c, p in ref.options]}
        if kind == "needs_pattern":
            clar = result.clarification
            return {
                "kind": "needs_pattern",
                "lemma": clar.signature.root_lemma,
                "question": clar.question,
                "options": [{"operation": op.value, "popis": popis}
                            for op, popis in clar.options],
            }
        if kind == "definition_query":
            # výčet z báze: „Kdo je Hrabal?" → co o něm víme (po demu)
            return {"kind": "definition",
                    "subject": result.candidate.subject_lemma,
                    "known": [render_literal(lit, self.profile)
                              for lit in result.definition]}
        if kind == "modal_query":
            modal = result.modal
            answer = ("Ano." if modal["answer"] is True
                      else "Ne." if modal["answer"] is False else "Nevím.")
            return {"kind": "modal_query", "operation": modal["operation"],
                    "answer": answer, "verdict": modal["verdict"],
                    "models_true": modal["models_true"],
                    "models_false": modal["models_false"],
                    "has_counterexample": modal["has_counterexample"]}
        output: dict[str, Any] = {"kind": kind}
        output.update(self._query_output(result))
        return output

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
            "subject": pending.subject_lemma,
            "source_text": pending.source_text,
        }
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
            # dict.fromkeys: bez duplicit, v pořadí návrhů — táž premisa
            # od více pravidel by se jinak vypsala vícekrát
            output["missing"] = list(dict.fromkeys(
                render_literal(lit, self.profile)
                for suggestion in result.why_not.suggestions
                for lit in suggestion.missing))
        return output

    # --- učení jazykových vzorů ----------------------------------------

    def teach_pattern(self, lemma: str, operation: str, *,
                      learned_from: str = "",
                      learned_at: str | None = None) -> dict[str, Any]:
        """Naučí mapování operátoru na operaci z menu (jako hypotézu)."""
        signature = StructuralSignature(lemma, has_xcomp=True)
        pattern = self.learner.teach_pattern(
            signature, Operation(operation), learned_from=learned_from,
            learned_at=learned_at)
        self.save()
        return {"lemma": lemma, "operation": pattern.operation.value,
                "status": pattern.status.value}

    def forget_word(self, lemma: str) -> dict[str, Any]:
        """Odvolá mapování slova; operace v jádru zůstává."""
        pattern = self.learner.revoke_pattern(lemma)
        self.save()
        return {"lemma": lemma,
                "revoked": pattern is not None}

    # --- stav a persistence --------------------------------------------

    def state(self) -> dict[str, Any]:
        kb = self.learner.kb
        return {"facts": len(kb.own_facts()), "rules": len(kb.rules),
                "derivations": len(kb.derivations),
                "conflicts": len(kb.conflicts),
                "patterns": len(self.learner.patterns.all()),
                "pending_reference": self.pending_reference is not None}

    def save(self) -> None:
        """Atomicky přes .tmp + replace (vzor registry/cache)."""
        self.kb_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format": FORMAT,
                   "kb": kb_to_json(self.learner.kb),
                   "patterns": self.learner.patterns.to_json()}
        temporary = self.kb_file.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")),
            encoding="utf-8")
        os.replace(temporary, self.kb_file)

    def _tokens(self, text: str):
        result = self.parser.parse(text=text)
        if not result.sentences:
            return None
        return result.sentences[0].tokens
