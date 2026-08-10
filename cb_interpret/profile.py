"""Jazykový profil — jediné místo, kde žije přirozený jazyk.

Kód interpretace rozhoduje podle UD struktur; profil nese otazník
a šablony renderování (kap. 6 návrhu: jazyk v profilech, ne v kódu).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

FORMAT_VERSION = 1


@dataclass(frozen=True)
class LanguageProfile:
    language: str
    question_mark: str
    templates: dict


def load_profile(path: str | Path) -> LanguageProfile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    version = data.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(f"neznámá verze profilu: {version!r}")
    return LanguageProfile(data["language"], data["question_mark"],
                           data["templates"])


def cs_profile() -> LanguageProfile:
    return load_profile(Path(__file__).parent / "profiles" / "cs.json")
