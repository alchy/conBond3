"""cb_interpret — interpretace jazyka a učení z dialogu.

Klient rozboru (cb_udpipe) a formálního jádra (cb_logic): věta →
kandidátní tvrzení → validace → inference → provenience. Vrstva jen
navrhuje (INV-11); o pravdivosti rozhoduje jádro. Specifikace:
INTERPRETATION.md v kořeni repozitáře.
"""
from cb_interpret.profile import LanguageProfile, cs_profile, load_profile
from cb_interpret.interpret import Candidate, interpret_sentence
from cb_interpret.learner import AskResult, DialogueLearner, LearnResult
from cb_interpret.render import (render_explanation, render_literal,
                                 render_truth)

__all__ = [
    "LanguageProfile", "cs_profile", "load_profile",
    "Candidate", "interpret_sentence",
    "AskResult", "DialogueLearner", "LearnResult",
    "render_explanation", "render_literal", "render_truth",
]
