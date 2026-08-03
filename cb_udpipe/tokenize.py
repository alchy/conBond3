"""Oprava tokenizace UDPipe.

UDPipe tokenizuje česky špatně na třech místech a je to změřené na korpusu
conBondu2 (26 051 vět): řadová číslovka se rozpadne na číslo a tečku (4,3 %
vět), zkratka na písmena a tečky (4,9 %), číslo s oddělovačem tisíců na dvě
čísla. Dohromady zhruba **každá jedenáctá věta** (koncepce, § 1).

Že to jde spravit, aniž se zhorší rozbor, je taky změřené (koncepce, § 13.5):
model byl trénován na PDT-C, kde `23.` i `R.U.R.` **jsou** jeden token — vadný
je tokenizér, ne tagger. Oprava model k jeho trénovacím datům přibližuje,
nevzdaluje.

Zásada, ze které pravidla plynou (koncepce, § 3.0):

> Co jde udělat deterministicky nad jednou větou, bez znalosti světa, a co by
> jinak muselo dělat každé vyšší patro zvlášť — to udělá cb-udpipe.

S dvěma hranicemi: **nesmí to zahodit informaci** a **nesmí to vykládat**.
Proto se tu nesjednocují pomlčky ani uvozovky (§ 13.6) a nevykládá se, že
levá půle závorky je narození (to je práce AG-BIO).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from cb_udpipe.conllu import Sentence, Token

#: Kolik číslic tvoří skupinu za oddělovačem tisíců. Právě tři, ne „aspoň
#: dvě": bez toho řezu by se `roku 1890 12 lidí` chovalo jako číselná skupina.
GROUP_DIGITS = 3

#: Znak, kterým se v češtině odděluje desetinná část.
DECIMAL_SEPARATOR = ","

#: Jak dlouhý je otisk pravidel. Dvanáct hexadecimálních znaků je dost na
#: rozlišení a krátké na přečtení v logu i v klíči cache.
FINGERPRINT_LENGTH = 12


@dataclass(frozen=True)
class Rules:
    """Pravidla opravy tokenizace.

    Seznam zkratek je **jazykové datum, ne kód** (SEAM-8 návrhu): angličtina
    má jiné. Proto se předává z konfigurace, ne zapisuje do modulu.
    """

    abbreviations: frozenset[str]
    min_pairs: int = 2
    merge_number_groups: bool = True
    merge_decimal_comma: bool = True

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Rules":
        """Sestaví pravidla z načtené konfigurace.

        Vstup:
            config: konfigurace z `config.load()`.

        Výstup:
            `Rules`. Zkratky se srovnají na malá písmena, aby `Sv.` i `sv.`
            trefily tutéž položku seznamu.

        Při chybě:
            `KeyError`, když v konfiguraci chybí klíč — to je chyba, kterou
            měla chytit validace při startu, a tichý výchozí stav by ji jen
            odsunul dál.
        """
        t = config["module"]["tokenizer"]
        return cls(
            abbreviations=frozenset(z.lower() for z in t["abbreviations"]),
            min_pairs=t["abbrev_min_pairs"],
            merge_number_groups=t["merge_number_groups"],
            merge_decimal_comma=t["merge_decimal_comma"],
        )


def fingerprint(rules: Rules) -> str:
    """Vrátí otisk pravidel — verzi tokenizéru pro klíč cache.

    Proč otisk a ne ruční číslo: ruční verze zastará v první chvíli, kdy někdo
    přidá zkratku a zapomene ji zvednout — přesně ten druh tiché vady, kterou
    celý návrh loví. Otisk obsahu zastarat nemůže (návrh, kap. 26.2).

    Vstup:
        rules: pravidla, jejichž otisk se počítá.

    Výstup:
        Dvanáct hexadecimálních znaků. Je stabilní vůči pořadí zkratek —
        množina pořadí nemá a otisk se nesmí měnit mezi běhy.

    Při chybě:
        Nevyhazuje.
    """
    kanonicky = json.dumps(
        {
            "abbreviations": sorted(rules.abbreviations),
            "min_pairs": rules.min_pairs,
            "merge_number_groups": rules.merge_number_groups,
            "merge_decimal_comma": rules.merge_decimal_comma,
        },
        sort_keys=True, ensure_ascii=False,
    )
    otisk = hashlib.sha256(kanonicky.encode("utf-8")).hexdigest()
    return otisk[:FINGERPRINT_LENGTH]


def retokenize(sentence: Sentence, rules: Rules) -> tuple[Sentence, int]:
    """Opraví tokenizaci věty; vrátí novou větu a počet sloučení.

    Pořadí pravidel je významné:

    1. **běh písmen s tečkami** (`R.U.R.`) — musí být první, jinak by se
       `n. l.` rozpadlo na dvě jednoslovné zkratky,
    2. **jednoslovné zkratky** ze seznamu (`tzv.`, `sv.`),
    3. **řadové číslovky** (`20.`),
    4. **číselné skupiny** (`30 000`, `3,14`) — až po řadových číslovkách,
       jinak by se `20 . 000` sloučilo špatně.

    Text věty se **nikdy nemění** — mění se jen hranice tokenů. `source` je
    klíč cache a jeho změna by cache rozpadla (koncepce, § 6).

    Vstup:
        sentence: věta z tokenizace UDPipe.
        rules: pravidla, obvykle z `Rules.from_config`.

    Výstup:
        Dvojice (nová věta, počet sloučení). Počet jde do logu a do souhrnu;
        nula znamená, že věta byla v pořádku, což je nejčastější případ.

    Při chybě:
        Nevyhazuje. Věta, na kterou žádné pravidlo nesedí, se vrátí beze změny.
    """
    tokeny = list(sentence.tokens)
    if not tokeny:
        return sentence, 0

    nove: list[Token] = []
    sloučeno = 0
    i = 0
    posledni = len(tokeny) - 1

    while i < len(tokeny):
        delka = _beh_zkratky(tokeny, i, rules)
        if delka:
            nove.append(_slouc(tokeny[i:i + delka]))
            sloučeno += 1
            i += delka
            continue

        if _je_jednoslovna_zkratka(tokeny, i, rules, posledni):
            nove.append(_slouc(tokeny[i:i + 2]))
            sloučeno += 1
            i += 2
            continue

        if _je_radova_cislovka(tokeny, i, posledni):
            nove.append(_slouc(tokeny[i:i + 2]))
            sloučeno += 1
            i += 2
            continue

        delka = _delka_ciselne_skupiny(tokeny, i, rules)
        if delka:
            nove.append(_slouc(tokeny[i:i + delka], oddelovac=" "))
            sloučeno += 1
            i += delka
            continue

        if _je_desetinne_cislo(tokeny, i, rules):
            nove.append(_slouc(tokeny[i:i + 3]))
            sloučeno += 1
            i += 3
            continue

        nove.append(tokeny[i])
        i += 1

    if not sloučeno:
        return sentence, 0

    return (
        Sentence(
            source=sentence.source,
            tokens=tuple(_precisluj(nove)),
            multiword=sentence.multiword,
            sent_id=sentence.sent_id,
        ),
        sloučeno,
    )


def _beh_zkratky(tokeny: list[Token], od: int, rules: Rules) -> int:
    """Délka běhu ⟨jednopísmenný token⟩⟨tečka⟩ od dané pozice.

    Vyžaduje aspoň `min_pairs` párů a **těsné navazování** — ověřuje se přes
    `SpaceAfter=No`, ne mezerou v textu. Obě podmínky jsou zapsané po chybě:
    jediná iniciála (`K. Čapek`) je jméno, ne zkratka, a písmena oddělená
    mezerami (`a . b .`) jsou výčtové odrážky. conBond i jellyAI3 to mají
    shodně.

    Vstup:
        tokeny: tokeny věty.
        od: index, od kterého se běh hledá.
        rules: pravidla (bere se `min_pairs`).

    Výstup:
        Počet tokenů, které běh tvoří (vždy sudý), nebo 0.

    Při chybě:
        Nevyhazuje.
    """
    paru = 0
    i = od
    while (i + 1 < len(tokeny)
           and len(tokeny[i].form) == 1
           and tokeny[i].form.isalpha()
           and not tokeny[i].space_after
           and tokeny[i + 1].form == "."):
        paru += 1
        # Po tečce musí následovat další písmeno bez mezery, jinak běh končí.
        if tokeny[i + 1].space_after:
            i += 2
            break
        i += 2
    return paru * 2 if paru >= rules.min_pairs else 0


def _je_jednoslovna_zkratka(tokeny: list[Token], i: int, rules: Rules,
                            posledni: int) -> bool:
    """Je na pozici `i` zkratka ze seznamu následovaná těsnou tečkou?

    Výčtový seznam je nutný, protože bezvýčtově to nejde odlišit: `sv.` na
    konci věty vypadá stejně jako slovo a konec věty. Proto se také tečka,
    která je **posledním tokenem věty**, nikdy neslučuje — sloučit ji by
    znamenalo větu bez interpunkce.

    Vstup:
        tokeny: tokeny věty.
        i: zkoumaná pozice.
        rules: pravidla (bere se `abbreviations`).
        posledni: index posledního tokenu věty.

    Výstup:
        `True`, když se má sloučit.

    Při chybě:
        Nevyhazuje.
    """
    return (i + 1 <= posledni
            and i + 1 != posledni
            and tokeny[i + 1].form == "."
            and not tokeny[i].space_after
            and tokeny[i].form.lower() in rules.abbreviations)


def _je_radova_cislovka(tokeny: list[Token], i: int, posledni: int) -> bool:
    """Je na pozici `i` číslo následované těsnou tečkou uprostřed věty?

    ŘEZ, bez kterého bylo měření vady nadhodnocené o 1 062 vět: tečka jako
    **poslední token věty** ji ukončuje, ne označuje řadovou číslovku.
    `, 1985 .` je rok na konci věty (koncepce, § 13.1).

    Vstup:
        tokeny: tokeny věty.
        i: zkoumaná pozice.
        posledni: index posledního tokenu věty.

    Výstup:
        `True`, když se má sloučit.

    Při chybě:
        Nevyhazuje.
    """
    return (i + 1 <= posledni
            and i + 1 != posledni
            and tokeny[i + 1].form == "."
            and not tokeny[i].space_after
            and tokeny[i].form.isdecimal())


def _delka_ciselne_skupiny(tokeny: list[Token], od: int, rules: Rules) -> int:
    """Délka čísla psaného s oddělovačem tisíců (`30 000`, `1 250 000`).

    UDPipe z `30 000` dělá **dva samostatné `nummod:gov`**, takže AG-METRON
    vidí dvě čísla místo jednoho a naměří 30. conBond2 to má v etalonu jako
    doloženou mezeru u otázky po počtu dělnic v úlu (koncepce, § 3.4).

    Slučují se jen skupiny **právě tří číslic** — bez toho řezu by se
    `roku 1890 12 lidí` chovalo jako číselná skupina.

    Vstup:
        tokeny: tokeny věty.
        od: index prvního čísla.
        rules: pravidla (bere se `merge_number_groups`).

    Výstup:
        Počet tokenů, které skupina tvoří, nebo 0.

    Při chybě:
        Nevyhazuje.
    """
    if not rules.merge_number_groups:
        return 0
    # Za prvním číslem musí být mezera — bez ní to není oddělovač tisíců.
    if not tokeny[od].form.isdecimal() or not tokeny[od].space_after:
        return 0

    delka = 1
    i = od + 1
    while (i < len(tokeny)
           and tokeny[i].form.isdecimal()
           and len(tokeny[i].form) == GROUP_DIGITS
           and tokeny[i - 1].space_after):
        delka += 1
        i += 1
    return delka if delka > 1 else 0


def _je_desetinne_cislo(tokeny: list[Token], i: int, rules: Rules) -> bool:
    """Je na pozici `i` desetinné číslo rozsekané na tři tokeny (`3 , 14`)?

    Vstup:
        tokeny: tokeny věty.
        i: zkoumaná pozice.
        rules: pravidla (bere se `merge_decimal_comma`).

    Výstup:
        `True`, když se mají sloučit tři tokeny v jeden.

    Při chybě:
        Nevyhazuje.
    """
    return (rules.merge_decimal_comma
            and i + 2 < len(tokeny)
            and tokeny[i].form.isdecimal()
            and not tokeny[i].space_after
            and tokeny[i + 1].form == DECIMAL_SEPARATOR
            and not tokeny[i + 1].space_after
            and tokeny[i + 2].form.isdecimal())


def _slouc(tokeny: list[Token], *, oddelovac: str = "") -> Token:
    """Sloučí tokeny do jednoho.

    Nový token dědí `id` a syntaktické sloupce **prvního** tokenu a `misc`
    **posledního**. To druhé je podstatné: `SpaceAfter` posledního tokenu
    říká, jestli za sloučeným celkem následuje mezera — a bez toho by se
    z tokenů složil text s mezerou navíc.

    Tagy se nekopírují (`lemma`, `upos`, …): sloučení probíhá **před**
    dorozborem, takže je stejně nikdo nevyplnil, a nechat po sobě tag prvního
    písmene by bylo horší než prázdno.

    Vstup:
        tokeny: aspoň dva tokeny k sloučení, v pořadí.
        oddelovac: co se vloží mezi formy. Prázdno u zkratek a čísel
            s tečkou, mezera u oddělovače tisíců — tam mezera v textu byla
            a `source` ji musí umět složit zpět.

    Výstup:
        Nový `Token`. `lemma` se nastaví na výslednou formu, protože sloučený
        tvar je sám sobě základním tvarem, dokud ho tagger nepřepíše.

    Při chybě:
        Nevyhazuje.
    """
    forma = oddelovac.join(t.form for t in tokeny)
    return Token(
        id=tokeny[0].id,
        form=forma,
        lemma=None,
        upos=None,
        xpos=None,
        feats=None,
        head=None,
        deprel=None,
        deps=None,
        misc=tokeny[-1].misc,
    )


def _precisluj(tokeny: list[Token]) -> list[Token]:
    """Přečísluje `id` na souvislou řadu od jedné.

    Po sloučení v řadě vzniknou díry a CoNLL-U s dírami není platný — server
    by takový vstup odmítl.

    Vstup:
        tokeny: tokeny po sloučení, v pořadí.

    Výstup:
        Nový seznam tokenů se souvislými `id`. Hlavy se nepřepočítávají,
        protože sloučení probíhá před dorozborem a žádné ještě nejsou.

    Při chybě:
        Nevyhazuje.
    """
    return [
        t if t.id == i else Token(
            id=i, form=t.form, lemma=t.lemma, upos=t.upos, xpos=t.xpos,
            feats=t.feats, head=t.head, deprel=t.deprel, deps=t.deps,
            misc=t.misc,
        )
        for i, t in enumerate(tokeny, 1)
    ]
