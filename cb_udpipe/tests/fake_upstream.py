"""Podstrčený UDPipe pro testy služby.

Tokenizuje hrubě jako skutečný UDPipe (odděluje tečky a čárky), aby testy
opravy tokenizace měly co opravovat. Nesnaží se být přesný — snaží se být
předvídatelný a rychlý.
"""

from __future__ import annotations

import re

from cb_udpipe import conllu, upstream

#: Hranice vět: tečka, otazník nebo vykřičník s mezerou za sebou.
#:
#: Nedělí se po **jednopísmenné** zkratce ani po číslici — skutečný UDPipe to
#: taky nedělá (ověřeno: `R.U.R. je drama.` i `28. 3. 1592` zůstanou jednou
#: větou) a bez toho by podstrčený server rozsekal právě ty věty, kvůli kterým
#: modul vzniká. Pravidlo je z jellyAI3 (`jellyai/text.py`).
_HRANICE = re.compile(r"(?<=[.!?])\s+")
_NEDELIT_PO = re.compile(r"(?:^|[\s(.])(?:\w|\d+)\.$")

#: Interpunkce, kterou hrubá tokenizace odděluje jako samostatný token —
#: stejně jako to dělá UDPipe.
_INTERPUNKCE = ".,;:!?()„“\"–-"


class FakeUpstream:
    """Tváří se jako `upstream.Upstream`, ale nechodí na síť."""

    def __init__(self, *, nedostupny: bool = False,
                 dlouha_veta: bool = False):
        self.nedostupny = nedostupny
        self.dlouha_veta = dlouha_veta
        self.pocet_tokenize = 0
        self.pocet_tag_and_parse = 0
        self.posledni_conllu = ""

    def reset(self) -> None:
        """Vynuluje počitadla, aby šlo měřit druhý průchod zvlášť."""
        self.pocet_tokenize = 0
        self.pocet_tag_and_parse = 0

    def models(self) -> dict:
        self._zkontroluj()
        return {"models": {"czech": ["tokenizer", "tagger", "parser"]},
                "default_model": "czech"}

    def tokenize(self, text: str, *, trace: str | None = None) -> str:
        """Fáze 1: rozdělí text na věty a věty na tokeny."""
        self._zkontroluj()
        self.pocet_tokenize += 1
        if not text.strip():
            return ""
        vety = []
        for poradi, kus in enumerate(_segmentuj(text.strip()), 1):
            if not kus.strip():
                continue
            tokeny = _tokenizuj(kus)
            if self.dlouha_veta:
                tokeny = tokeny * 300        # bezpečně přes mez 1000 slov
            vety.append(conllu.Sentence(
                source=kus, tokens=tuple(tokeny), sent_id=str(poradi)
            ))
        return conllu.write(vety)

    def tag_and_parse(self, conllu_text: str, *,
                      trace: str | None = None) -> str:
        """Fáze 4: doplní tagy. Segmentaci ani tokenizaci nemění — přesně
        proto se posílá CoNLL-U a ne text."""
        self._zkontroluj()
        self.pocet_tag_and_parse += 1
        self.posledni_conllu = conllu_text
        vety = conllu.parse(conllu_text)
        hotove = []
        for v in vety:
            tokeny = tuple(
                conllu.Token(
                    id=t.id, form=t.form, lemma=t.form.lower(),
                    upos="PUNCT" if t.form in _INTERPUNKCE else "X",
                    head=0 if t.id == 1 else 1,
                    deprel="root" if t.id == 1 else "dep",
                    misc=t.misc,
                )
                for t in v.tokens
            )
            hotove.append(conllu.Sentence(
                source=v.source, tokens=tokeny,
                multiword=v.multiword, sent_id=v.sent_id,
            ))
        return conllu.write(hotove)

    def _zkontroluj(self) -> None:
        if self.nedostupny:
            raise upstream.UpstreamUnavailable(
                "modul cb-udpipe: vlastní instance UDPipe neodpovídá.\n"
                "Spusť ji: ./cb-udpipe.py start"
            )


def _segmentuj(text: str) -> list[str]:
    """Rozdělí text na věty; hranici po zkratce nebo číslici zahodí.

    Bez toho by se `R.U.R. je drama.` rozsekalo na dvě věty a testy opravy
    tokenizace by měřily chování podstrčeného serveru, ne našeho kódu.
    """
    vety: list[str] = []
    zbytek = text
    while True:
        shoda = _HRANICE.search(zbytek)
        if shoda is None:
            break
        hlava = zbytek[:shoda.start()]
        if _NEDELIT_PO.search(hlava):
            # Hranice je falešná — hledá se další, ale text se nedělí.
            dalsi = _HRANICE.search(zbytek, shoda.end())
            if dalsi is None:
                break
            shoda = dalsi
            hlava = zbytek[:shoda.start()]
        vety.append(hlava)
        zbytek = zbytek[shoda.end():]
    if zbytek:
        vety.append(zbytek)
    return vety


def _tokenizuj(veta: str) -> list[conllu.Token]:
    """Rozdělí větu na tokeny a nastaví `SpaceAfter` podle původních mezer."""
    tokeny: list[conllu.Token] = []
    i = 0
    poradi = 1
    while i < len(veta):
        if veta[i].isspace():
            i += 1
            continue
        if veta[i] in _INTERPUNKCE:
            forma, delka = veta[i], 1
        else:
            j = i
            while j < len(veta) and not veta[j].isspace() \
                    and veta[j] not in _INTERPUNKCE:
                j += 1
            forma, delka = veta[i:j], j - i
        konec = i + delka
        mezera = konec < len(veta) and veta[konec].isspace()
        tokeny.append(conllu.Token(
            id=poradi, form=forma,
            misc=None if mezera else {"SpaceAfter": "No"},
        ))
        poradi += 1
        i = konec
    return tokeny


class FakeLog:
    """Zaznamenává volání místo odesílání do logovátka."""

    def __init__(self):
        self.zaznamy: list[dict] = []
        self.objekty: list[dict] = []

    def info(self, **kw):
        self.zaznamy.append({**kw, "level": "info"})

    def debug(self, **kw):
        self.zaznamy.append({**kw, "level": "debug"})

    def json(self, **kw):
        self.objekty.append(kw)


class RozbityLog:
    """Logovátko, které při každém volání spadne.

    Nepovinná závislost při výpadku znamená degradaci, ne pád
    (README-MODULES.md § 9) — a to se musí dát otestovat.
    """

    def info(self, **kw):
        raise OSError("logovátko neodpovídá")

    def debug(self, **kw):
        raise OSError("logovátko neodpovídá")

    def json(self, **kw):
        raise OSError("logovátko neodpovídá")
