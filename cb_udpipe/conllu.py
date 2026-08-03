"""Čtení a psaní CoNLL-U.

Čistá funkce nad textem — nezná HTTP, cesty ani konfiguraci. To je záměr:
největší část logiky modulu se tím dá testovat na zmražených datech bez
běžícího UDPipe.

Bere se **všech deset sloupců**, ne jen ty dnes potřebné. conBond2 bral sedm
(`core/ingest.py`) a `MISC` vynechával úplně, takže `SpaceAfter=No` se ztratilo
a původní text už z tokenů nešlo složit. Cache je dlouhodobá sbírka a chybějící
sloupec se pozná až za půl roku, kdy je jediná cesta k němu pustit celý korpus
znovu (koncepce, § 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

#: Prázdná hodnota v CoNLL-U. V našich datech je z ní `None` — „nemá hodnotu"
#: je stav, ne řetězec (INV-9).
EMPTY = "_"

#: Kolik sloupců má řádek CoNLL-U. Kratší řádek je rozsypaný vstup.
COLUMNS = 10


@dataclass(frozen=True)
class Token:
    """Jeden token věty se všemi deseti sloupci CoNLL-U.

    Neměnný schválně: token je pozorování, ne stav. Kdo ho chce změnit
    (například scelit dva do jednoho), vyrobí nový — tím je vyloučené, že se
    tentýž objekt tiše změní pod rukama někomu, kdo si ho odložil.
    """

    id: int
    form: str
    lemma: str | None = None
    upos: str | None = None
    xpos: str | None = None
    feats: dict[str, str] | None = None
    head: int | None = None
    deprel: str | None = None
    deps: str | None = None
    misc: dict[str, str] | None = None

    @property
    def space_after(self) -> bool:
        """Následuje za tokenem v původním textu mezera?

        Proč vlastnost a ne čtení `misc` u volajícího: `SpaceAfter=No` je
        jediný způsob, jak z tokenů složit původní text, a kdyby si ho každý
        četl sám, rozejde se to při první změně tvaru `misc`.

        Výstup:
            `False`, když token nese `SpaceAfter=No`; jinak `True`.

        Při chybě:
            Nevyhazuje.
        """
        return not (self.misc or {}).get("SpaceAfter") == "No"


@dataclass(frozen=True)
class Multiword:
    """Víceslovný tvar, který se rozpadl na víc tokenů („Abys" → Aby + bys).

    Drží se mimo `tokens` schválně: vrstvy nad námi počítají s tím, že token
    má celočíselné `id`. Zahodit ho ale nelze — bez něj nejde poznat, že
    v textu stálo „Abys", a ne „Aby bys" (koncepce, § 5).
    """

    id: tuple[int, int]
    form: str
    misc: dict[str, str] | None = None


@dataclass(frozen=True)
class Sentence:
    """Jedna rozebraná věta.

    `source` je text věty tak, jak stojí v původním dokumentu. Je to **klíč
    cache** (koncepce, § 4), takže se nesmí měnit ani při opravě tokenizace.
    """

    source: str
    tokens: tuple[Token, ...]
    multiword: tuple[Multiword, ...] = ()
    sent_id: str | None = None


def parse(text: str) -> list[Sentence]:
    """Přečte CoNLL-U a vrátí věty.

    Proč nikdy nevyhazuje na rozsypaném řádku: vstup přichází ze sítě a jediná
    vadná věta nesmí shodit celou dávku. Řádek, který nedává smysl, se
    přeskočí; věta bez tokenů se nevrací vůbec.

    Vstup:
        text: obsah CoNLL-U, jedna nebo víc vět oddělených prázdným řádkem.

    Výstup:
        Seznam vět v pořadí vstupu. Prázdný vstup dá prázdný seznam — prázdno
        není chyba.

    Při chybě:
        Nevyhazuje.
    """
    vety: list[Sentence] = []
    tokeny: list[Token] = []
    viceslovne: list[Multiword] = []
    source: str | None = None
    sent_id: str | None = None

    def uzavri() -> None:
        nonlocal tokeny, viceslovne, source, sent_id
        if tokeny:
            vety.append(Sentence(
                source=source if source is not None else _slozit_text(tokeny),
                tokens=tuple(tokeny),
                multiword=tuple(viceslovne),
                sent_id=sent_id,
            ))
        tokeny, viceslovne, source, sent_id = [], [], None, None

    for radek in text.splitlines():
        if not radek.strip():
            uzavri()
            continue
        if radek.startswith("#"):
            klic, _, hodnota = radek[1:].partition("=")
            klic = klic.strip()
            if klic == "text":
                source = hodnota.strip()
            elif klic == "sent_id":
                sent_id = hodnota.strip()
            continue

        sloupce = radek.split("\t")
        if len(sloupce) < COLUMNS:
            continue                    # rozsypaný řádek

        identifikator = sloupce[0]
        if _je_cele_cislo(identifikator):
            tokeny.append(_token(sloupce))
        elif "-" in identifikator:
            rozsah = _rozsah(identifikator)
            if rozsah is not None:
                viceslovne.append(Multiword(
                    id=rozsah, form=sloupce[1], misc=_pole(sloupce[9])
                ))
        # Prázdný uzel (`1.1`) se přeskakuje: vrstvy nad námi počítají
        # s celočíselným id a elidovaný uzel žádný token v textu nemá.

    uzavri()
    return vety


def write(sentences: Sequence[Sentence]) -> str:
    """Zapíše věty do CoNLL-U.

    Proč to musí být přesný protějšek `parse`: 4. fáze rozboru posílá výstup
    téhle funkce zpátky serveru. Kdyby se cestou něco ztratilo, ztratí se to
    z rozboru — a segmentace, kterou vstup určuje, je celý důvod, proč se
    posílá CoNLL-U místo textu (koncepce, § 2).

    Vstup:
        sentences: věty k zapsání.

    Výstup:
        Text CoNLL-U. Každá věta nese `# sent_id` a `# text`; věty odděluje
        prázdný řádek. Prázdný vstup dá prázdný řetězec.

    Při chybě:
        Nevyhazuje.
    """
    kusy: list[str] = []
    for poradi, veta in enumerate(sentences, 1):
        radky = [
            f"# sent_id = {veta.sent_id or poradi}",
            f"# text = {veta.source}",
        ]
        # Víceslovný řádek stojí před tokeny, které pokrývá — jinak není
        # platný CoNLL-U.
        podle_zacatku = {m.id[0]: m for m in veta.multiword}
        for token in veta.tokens:
            m = podle_zacatku.get(token.id)
            if m is not None:
                radky.append(_radek_multiword(m))
            radky.append(_radek_token(token))
        kusy.append("\n".join(radky))
    return "\n\n".join(kusy) + "\n\n" if kusy else ""


def _token(sloupce: list[str]) -> Token:
    """Sestaví token z deseti sloupců jednoho řádku.

    Vstup:
        sloupce: rozdělený řádek CoNLL-U, aspoň deset položek.

    Výstup:
        `Token` s prázdnými sloupci převedenými na `None`.

    Při chybě:
        Nevyhazuje. Nečitelná hlava skončí jako `None`, ne jako výjimka —
        chybějící vazba je stav, ne pád.
    """
    return Token(
        id=int(sloupce[0]),
        form=sloupce[1],
        lemma=_hodnota(sloupce[2]),
        upos=_hodnota(sloupce[3]),
        xpos=_hodnota(sloupce[4]),
        feats=_pole(sloupce[5]),
        head=int(sloupce[6]) if _je_cele_cislo(sloupce[6]) else None,
        deprel=_hodnota(sloupce[7]),
        deps=_hodnota(sloupce[8]),
        misc=_pole(sloupce[9]),
    )


def _radek_token(token: Token) -> str:
    """Zapíše token jako řádek CoNLL-U o deseti sloupcích."""
    return "\t".join([
        str(token.id),
        token.form,
        _zpet(token.lemma),
        _zpet(token.upos),
        _zpet(token.xpos),
        _zpet_pole(token.feats),
        EMPTY if token.head is None else str(token.head),
        _zpet(token.deprel),
        _zpet(token.deps),
        _zpet_pole(token.misc),
    ])


def _radek_multiword(m: Multiword) -> str:
    """Zapíše víceslovný tvar. Vyplňují se jen FORM a MISC, zbytek je prázdný —
    tak to CoNLL-U předepisuje."""
    return "\t".join([
        f"{m.id[0]}-{m.id[1]}", m.form,
        EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
        _zpet_pole(m.misc),
    ])


def _je_cele_cislo(s: str) -> bool:
    """Dá se ten tvar přečíst jako celé číslo?

    NE `isdigit()`. Ten vrací `True` i pro „²", takže `int()` na něm spadne —
    a spadl: článek o betonu má „m²" a shodil stavbu celého korpusu na
    86 článcích (conBond2, `core/agents/base.py`). `isdecimal()` je právě ten
    predikát, po kterém `int()` projde vždycky.

    Je to jediné místo v modulu, kde se tenhle test dělá.

    Vstup:
        s: tvar z prvního nebo sedmého sloupce.

    Výstup:
        `True`, když `int(s)` projde.

    Při chybě:
        Nevyhazuje.
    """
    return s.isdecimal()


def _rozsah(identifikator: str) -> tuple[int, int] | None:
    """Přečte rozsah víceslovného tvaru („1-2").

    Výstup:
        Dvojice čísel, nebo `None`, když to rozsah není.

    Při chybě:
        Nevyhazuje.
    """
    od, _, do = identifikator.partition("-")
    if _je_cele_cislo(od) and _je_cele_cislo(do):
        return int(od), int(do)
    return None


def _hodnota(s: str) -> str | None:
    """Prázdné podtržítko na `None`, jinak text beze změny."""
    return None if s == EMPTY else s


def _zpet(hodnota: str | None) -> str:
    """`None` zpátky na podtržítko."""
    return EMPTY if hodnota is None else hodnota


def _pole(s: str) -> dict[str, str] | None:
    """Rozloží `FEATS` nebo `MISC` na slovník.

    Proč slovník a ne seznam řetězců: conBond2 měl `["Case=Nom", …]`
    a rozebíral to při každém čtení. Rozdělení dvojice na klíč a hodnotu je
    práce, kterou stačí udělat jednou — při čtení.

    Hodnota se dělí jen na **prvním** rovnítku: `SpacesAfter=\\n\\n` a podobné
    hodnoty rovnítko obsahovat můžou.

    Vstup:
        s: obsah sloupce, například `Case=Nom|Gender=Fem`.

    Výstup:
        Slovník, nebo `None` u prázdného sloupce. Položka bez rovnítka se
        přeskočí — je to rozsypaný vstup, ne příznak bez hodnoty.

    Při chybě:
        Nevyhazuje.
    """
    if s == EMPTY or not s:
        return None
    vysledek: dict[str, str] = {}
    for kus in s.split("|"):
        klic, oddelovac, hodnota = kus.partition("=")
        if oddelovac:
            vysledek[klic] = hodnota
    return vysledek or None


def _zpet_pole(pole: dict[str, str] | None) -> str:
    """Složí slovník zpátky do sloupce CoNLL-U.

    Pořadí klíčů se zachovává tak, jak přišly — CoNLL-U sice předepisuje
    abecední, ale přeskládat je by znamenalo, že round-trip nevrátí totéž,
    co přišlo, a rozdíl by pak vypadal jako změna dat.
    """
    if not pole:
        return EMPTY
    return "|".join(f"{k}={v}" for k, v in pole.items())


def _slozit_text(tokeny: Sequence[Token]) -> str:
    """Složí text věty z tokenů podle `SpaceAfter`.

    Proč to je potřeba: vlastní CoNLL-U posílané ve 4. fázi nemusí nést
    `# text`, ale `source` je klíč cache a prázdný být nesmí.

    Vstup:
        tokeny: tokeny věty v pořadí.

    Výstup:
        Text věty. Za posledním tokenem se mezera nepřidává.

    Při chybě:
        Nevyhazuje.
    """
    kusy: list[str] = []
    for i, token in enumerate(tokeny):
        kusy.append(token.form)
        if token.space_after and i < len(tokeny) - 1:
            kusy.append(" ")
    return "".join(kusy)
