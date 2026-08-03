"""Doménová logika modulu cb-field: koše posuvného okna nad větou.

První malý krok extrakční vrstvy (README-EXTRAKCNI_VRSTVA.md): posuvné okno
o poloměru r postupuje po větě a na každém tokenu vytvoří jeden koš — slovo
a jeho okolí do vzdálenosti r, s úplnými metadaty z rozboru. Z jedné věty
tak vznikne tolik košů, kolik má tokenů. Na začátku a na konci věty, kde
okolí chybí, jsou koše menší — žádné vycpávkové řádky.

Mockup vědomě bez logování, bez konfigurace a bez REST vrstvy; zůstává ale
čistou funkcí nad daty (bez HTTP, bez cest), aby se z něj plný modul stavěl
přidáváním, ne přepisováním.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from cb_udpipe import Token

#: Kolik slotů se předalokuje pro hodnoty jednoho klíče metadat.
#: Parser vrací u víceznačných rysů hodnoty slepené čárkou (naměřeno:
#: Gender='Fem,Neut', Number='Plur,Sing' u „šla" — 2 hodnoty); 4 je
#: dvojnásobná rezerva, aby tvar řádku nezměnila první neobvyklá věta.
#: Až vznikne konfigurace modulu, přestěhuje se do registru prahů (§ 5).
FEAT_SLOTS = 4

#: Váha, se kterou se hodnota metadat rodí. Stanovená startovní hodnota;
#: upravovat ji bude až pozdější vrstva, rozsah drží WEIGHT_MIN/WEIGHT_MAX.
DEFAULT_WEIGHT = 0.7

#: Meze váhy. Znaménko nese druh vazby: kladná váha = pozitivní vazba
#: (hodnota platí a podporuje), záporná = negativní vazba (hodnota platí
#: obráceně / proti — např. popřený vztah). Nula = žádný vliv.
WEIGHT_MIN = -1.0
WEIGHT_MAX = 1.0


@dataclass
class MetaValue:
    """Jedna hodnota metadat s váhou.

    Váha vyjadřuje, jak silně hodnota platí / jak moc se s ní má počítat;
    rodí se na DEFAULT_WEIGHT a žije v rozsahu −1.0 … +1.0. Znaménko nese
    druh vazby: kladné = pozitivní vazba, záporné = negativní vazba
    (hodnota působí proti, např. popření). Prázdný slot (value=None) má
    váhu 0.0 — nenese informaci, nemá vliv.

    Schválně není frozen: váhy bude pozdější vrstva upravovat na místě.

    Při chybě:
        ValueError, když je váha mimo rozsah — tichá hodnota mimo meze by
        se projevila až v počítání, daleko od místa vzniku.
    """

    value: str | None
    weight: float = DEFAULT_WEIGHT

    def __post_init__(self) -> None:
        if not WEIGHT_MIN <= self.weight <= WEIGHT_MAX:
            raise ValueError(
                f"váha {self.weight} je mimo rozsah "
                f"{WEIGHT_MIN} … {WEIGHT_MAX}")

    def __repr__(self) -> str:
        # Kompaktní tvar kvůli čitelnosti košů v konzoli: 'Fem'@0.7, prázdno '·'.
        if self.value is None:
            return "·"
        return f"{self.value}@{self.weight:g}"


def _empty_slot() -> MetaValue:
    """Prázdný slot: bez hodnoty, bez vlivu."""
    return MetaValue(value=None, weight=0.0)


@dataclass(frozen=True)
class Basket:
    """Koš jednoho zastavení okna: slovo věty a jeho okolí do poloměru r.

    Koš nese tokeny tak, jak přišly z parse — nic se nezahazuje ani
    nepřekládá. Kde okno přesahuje hranici věty, řádky prostě nejsou:
    koš u kraje je menší (nejméně r+1 řádků), plný koš má 2r+1 řádků.

    Obsah:
        r:      poloměr, se kterým je koš postavený.
        center: index středu v seznamu tokenů věty (0 = první token).
        rows:   tokeny s indexy center-r … center+r, oříznuté na větu.
    """

    r: int
    center: int
    rows: tuple

    @property
    def center_token(self) -> Token:
        """Token, kolem kterého je koš postavený.

        U plného koše je to prostřední řádek; u koše na začátku věty je
        středový token posunutý doleva o to, kolik řádků před ním chybí.
        """
        left = max(0, self.center - self.r)
        return self.rows[self.center - left]


def build_baskets(tokens: Sequence[Token], r: int = 2) -> tuple:
    """Projde větu posuvným oknem a na každém tokenu postaví jeden koš.

    Proč je středem každý token a ne jen root/jádra: kritérium středů (R1)
    je pozdější rozhodnutí; v tomhle kroku se koše staví všude a výběr
    středů se doplní jako filtr nad hotovými koši, ne jako podmínka uvnitř.

    Vstup:
        tokens: tokeny jedné věty z ParsedSentence.tokens (cb_udpipe).
        r:      poloměr okna; výchozí 2 podle měření (statisticky nejlepší
                výsledky pro navazující kroky).

    Výstup:
        Tolik košů, kolik má věta tokenů, v pořadí středů. Plný koš má
        2r+1 řádků; na krajích věty, kde okolí chybí, jsou koše menší.

    Při chybě:
        ValueError pro r < 0. Prázdná věta není chyba: vrátí prázdnou
        n-tici.
    """
    if r < 0:
        raise ValueError(f"poloměr okna musí být >= 0, dostal jsem r={r}")

    rows = tuple(tokens)
    return tuple(
        Basket(r=r, center=i, rows=rows[max(0, i - r):i + r + 1])
        for i in range(len(rows))
    )


def expand_token(token: Token, slots: int = FEAT_SLOTS) -> dict:
    """Rozvine token na řádek s váženými metadaty a pevným tvarem hodnot.

    Proč pole s předalokovanými sloty: parser vrací u víceznačných rysů
    hodnoty slepené čárkou ('Fem,Neut'); string se špatně porovnává a každý
    odběratel by ho rozvíjel jinak. Každý klíč feats má proto n-tici pevné
    délky slots: hodnoty od začátku (každá jako MetaValue s výchozí vahou),
    zbytek prázdné sloty. Jednohodnotový klíč má tentýž tvar — odběratel
    nerozlišuje dva případy.

    Bez váhy zůstává provenience a struktura: id, form, head — to nejsou
    tvrzení o slově, ale adresy. Všechno ostatní (lemma, upos, xpos,
    deprel, feats) váhu nese.

    Vstup:
        token: řádek věty z parse.
        slots: kolik slotů se předalokuje na klíč; výchozí FEAT_SLOTS.

    Výstup:
        dict: id, form, head beze změny; lemma, upos, xpos, deprel jako
        MetaValue; feats jako dict {klíč: n-tice MetaValue délky slots}.
        Token bez rysů má feats {}.

    Při chybě:
        ValueError, když má klíč víc hodnot než slots — hlasité selhání
        je lepší než tiché zahození hodnoty (§ 9 politiky).
    """
    feats = {}
    for key, raw in (token.feats or {}).items():
        values = raw.split(",")
        if len(values) > slots:
            raise ValueError(
                f"klíč {key}={raw!r} má {len(values)} hodnot, "
                f"předalokováno je jen {slots} slotů")
        feats[key] = tuple(
            [MetaValue(value=v) for v in values]
            + [_empty_slot() for _ in range(slots - len(values))]
        )
    return {
        "id": token.id,
        "form": token.form,
        "head": token.head,
        "lemma": MetaValue(value=token.lemma),
        "upos": MetaValue(value=token.upos),
        "xpos": MetaValue(value=token.xpos),
        "deprel": MetaValue(value=token.deprel),
        "feats": feats,
    }


def expand_basket(basket: Basket, slots: int = FEAT_SLOTS) -> tuple:
    """Rozvine všechny řádky koše; pořadí odpovídá basket.rows.

    Vstup i chování viz expand_token; koše se nemění, rozvinutí je nový
    pohled na tatáž data.
    """
    return tuple(expand_token(t, slots) for t in basket.rows)


#: Zavřené třídy UD (všech 8): lemma je u nich mluvnice, ne obsah — bez
#: LEM vertikály jsou „do lesa" a „u dveří" nerozlišitelné.
CLOSED_UPOS = frozenset(
    {"ADP", "AUX", "CCONJ", "DET", "NUM", "PART", "PRON", "SCONJ"})


#: Kotvy tázacích/vztažných slov: kterou souřadnici slovo poptává
#: (otázka), resp. ke které se vztahuje (vztažné užití). Konečná tabulka
#: zavřených slov — „text dodá strukturu, konečná tabulka dodá význam";
#: UD dimenzi nenese (kde je jen ADV+PronType). Upřesnění podle funktorů
#: PDT: kde=LOC, kam=DIR3, odkud=DIR1, kudy=DIR2; kdy=TWHEN, odkdy=TSIN,
#: dokdy=TTILL; kolik=EXT; kdo/co=ACT/PAT; jak=MANN; proč=CAUS.
INTERROGATIVE_ANCHORS = {
    "kde": "space:loc", "kam": "space:to", "odkud": "space:from",
    "kudy": "space:through",
    "kdy": "time:when", "odkdy": "time:since", "dokdy": "time:till",
    "kolik": "quantity",
    "kdo": "entity", "co": "entity", "čí": "entity",
    "jak": "manner", "proč": "cause",
}

#: Kotvy ukazovacích příslovcí: strana odpovědi (ukazují do prostoru
#: a času, i záporně — „nikde" je také výrok o prostoru). Bez upřesnění
#: tam, kde ho slovo samo nenese („tam" může být poloha i směr; rozhodne
#: až slovesná skupina) — vazby v registru kotvu stejně svedou do dimenze.
DEICTIC_ANCHORS = {
    "tam": "space", "tady": "space", "zde": "space",
    "tudy": "space:through", "odtud": "space:from",
    "všude": "space", "nikde": "space", "někde": "space",
    "tehdy": "time", "teď": "time", "nyní": "time", "vždy": "time",
    "nikdy": "time", "někdy": "time", "pak": "time", "potom": "time",
    "tak": "manner", "proto": "cause",
}

#: Zájmenná příslovce se zápornou polaritou: jejich kotva svítí záporně
#: (negativní vazba) — „nikde" je výrok o prostoru, ale proti němu.
NEGATIVE_DEICTICS = frozenset({"nikde", "nikdy", "nijak", "nikam"})

#: Dimenze kotev a jejich upřesnění — zdroj hierarchických vazeb
#: v registru (ANCHOR=dim:ref → ANCHOR=dim @1.0; QANCHOR → ANCHOR=dim).
ANCHOR_DIMENSIONS = {
    "space": ("loc", "to", "from", "through"),
    "time": ("when", "since", "till", "past", "pres", "fut"),
    "quantity": ("sing", "plur", "count"),
    "entity": (),
    "manner": (),
    "cause": (),
}


def seed_anchor_links(registry) -> None:
    """Zapíše hierarchii kotev do registru jako vážené vazby.

    Proč vazby a ne dvojí buňky v řádcích: hierarchie je vztah mezi
    vertikálami, ne vlastnost řádku — a vztah s vahou už umíme (maska by
    byla jen binární degenerát váhy). Párování otázka↔odpověď pak je
    jeden krok šíření aktivace: QANCHOR=time:when i ANCHOR=time:fut
    stečou po vazbách do ANCHOR=time a tam se potkají.
    """
    for dim, refs in ANCHOR_DIMENSIONS.items():
        registry.link(f"QANCHOR={dim}", f"ANCHOR={dim}", 1.0)
        for ref in refs:
            registry.link(f"ANCHOR={dim}:{ref}", f"ANCHOR={dim}", 1.0)
            registry.link(f"QANCHOR={dim}:{ref}", f"ANCHOR={dim}", 1.0)

#: Slovní druhy, jejichž Number je výrok o množství. Shoda na ADJ/DET je
#: jen echo jména — kotvu nedostane, aby se množství nepočítalo dvakrát.
QUANTITY_UPOS = frozenset({"NOUN", "PROPN", "PRON", "VERB", "AUX"})


def is_question(tokens: Sequence[Token]) -> bool:
    """Věta je tázací, když v ní stojí otazník.

    Kódování otazníkem je vědomě jednoduché: nepřímé otázky („Nevím,
    kde je.") otazník nemají a tahle funkce je neuvidí — zapsaná mez,
    řešit ji bude až otázková vrstva.
    """
    return any(t.form == "?" for t in tokens)


def activations(row: dict, question: bool = False) -> dict:
    """Aktivace řádku: {"atribut=hodnota": váha} — vstup pro registr.

    Vertikála je dvojice atribut=hodnota; multiatribut (víc naplněných
    slotů) dá víc vertikál. LEM vertikálu dostane jen slovo, u kterého
    je lemma mluvnice, ne obsah: zavřená třída UD (NUM jen bez číslic
    v lemmatu — „pět" ano, „125" ne, číslice jsou nekonečná množina)
    a zájmenné příslovce (ADV s PronType: kde/kdy/jak/proč, tam, nikdy…).

    Otázková strana: tázací „kde" je jiné „kde" než to, které ukazuje
    konkrétní pozici. V tázací větě (question=True) proto slovo
    s PronType obsahujícím Int dostane vertikálu QLEM= místo LEM= —
    a víceznačné PronType=Int,Rel rozhodne kontext vahami: v otázce
    Int kladně a Rel záporně (negativní vazba: „tohle NENÍ vztažné"),
    v oznamovací větě obráceně. „tam" (Dem) zůstává LEM=tam vždy —
    ukazuje konkrétní místo i uvnitř otázky.

    Bez aktivace zůstávají adresy a povrch (id, head, form) — nejsou to
    vážená tvrzení a do matice nepatří; xpos je provenience (duplikuje
    feats).

    Vstup:
        row: rozvinutý řádek z expand_token.
        question: zda řádek stojí v tázací větě (is_question).

    Výstup:
        dict {vertikála: váha}; váhy nese MetaValue, výchozí 0.7.
    """
    acts = {
        f"UPOS={row['upos'].value}": row["upos"].weight,
        f"DEPREL={row['deprel'].value}": row["deprel"].weight,
    }
    prontype = [s.value for s in row["feats"].get("PronType", ())
                if s.value is not None]
    ambiguous = "Int" in prontype and "Rel" in prontype
    for key, slots in row["feats"].items():
        for slot in slots:
            if slot.value is None:
                continue
            weight = slot.weight
            if key == "PronType" and ambiguous:
                # Parser si nebyl jistý; věta ano. Prohraný výklad dostane
                # zápornou vazbu, ne ticho — chybějící a popřené se nesmí slít.
                losing = "Rel" if question else "Int"
                if slot.value == losing:
                    weight = -abs(weight)
            acts[f"{key}={slot.value}"] = weight
    lemma = row["lemma"]
    upos = row["upos"].value
    xpos = row["xpos"].value or ""
    closed = (upos in CLOSED_UPOS
              or (upos == "ADV" and "PronType" in row["feats"]))
    if (lemma is not None and closed
            and not any(ch.isdigit() for ch in lemma.value)):
        # Klíč nese i UPOS: spojkové „jak" (SCONJ) je jiné „jak" než
        # příslovečné (ADV) — naměřená kolize, jedna vertikála by je slila.
        prefix = "QLEM" if question and "Int" in prontype else "LEM"
        acts[f"{prefix}={upos}:{lemma.value}"] = lemma.weight

    # SubPOS (první dva znaky pozičního tagu): třídy, které feats nemají —
    # Db zájmenné příslovce, P7 zvratné se/si, C= číslice vs Cl slovní
    # číslovka, Vc kondicionál. Zbytek xpos feats kryjí a svítit dvakrát
    # nesmí (jedna skutečnost = jedna vertikála).
    if len(xpos) >= 2 and xpos[1] != "-":
        acts[f"SUBPOS={xpos[:2]}"] = row["xpos"].weight

    # Jmenná negace z pozice 11 tagu: feats nesou Polarity jen u sloves,
    # „přítel/nepřítel" je vidět jen tady. Jen příznakové N — kladný stav
    # je výchozí a svítil by na každém jménu bez informace.
    if "Polarity" not in row["feats"] and len(xpos) >= 11 and xpos[10] == "N":
        acts["Polarity=Neg"] = row["xpos"].weight

    # --- kotvy: ukotvení v prostoru, čase, množství a entitě ------------
    # Čas: každý finitní děj je ukotven svým Tense; dokonavý prézens míří
    # do budoucnosti („přijde" má tvar Pres, ale čas Fut) — kotva jde po
    # smyslu, ne po tvaru (Reichenbach: vztah E–S).
    aspects = {s.value for s in row["feats"].get("Aspect", ())
               if s.value is not None}
    verbforms = {s.value for s in row["feats"].get("VerbForm", ())
                 if s.value is not None}
    for slot in row["feats"].get("Tense", ()):
        if slot.value is None:
            continue
        ref = slot.value.lower()
        if ref == "pres" and "Perf" in aspects and "Fin" in verbforms:
            ref = "fut"
        acts[f"ANCHOR=time:{ref}"] = slot.weight

    # Množství: Number jen tam, kde je výrokem (jména, slovesa) — shoda
    # na ADJ/DET je echo jména a hlasovala by dvakrát.
    if upos in QUANTITY_UPOS:
        for slot in row["feats"].get("Number", ()):
            if slot.value is not None:
                acts[f"ANCHOR=quantity:{slot.value.lower()}"] = slot.weight
    if upos == "NUM":
        acts["ANCHOR=quantity:count"] = row["upos"].weight

    # Entita a prostor z vlastních jmen: Geo je místo, Giv/Sur osoba.
    # Upřesnění prostoru tu nedáváme — zda „Praha" je poloha, cíl nebo
    # zdroj, řekne pád s předložkou, ne jméno samo.
    for slot in row["feats"].get("NameType", ()):
        if slot.value == "Geo":
            acts["ANCHOR=space"] = slot.weight
        elif slot.value in ("Giv", "Sur"):
            acts["ANCHOR=entity"] = slot.weight

    # Tázací/vztažná a ukazovací slova: strana otázky (QANCHOR) jen
    # v tázací větě u slov s Int; jinak strana odpovědi. Záporná
    # zájmenná příslovce kotví záporně — „nikde" je výrok o prostoru,
    # ale proti němu.
    if lemma is not None and prontype:
        dimension = INTERROGATIVE_ANCHORS.get(lemma.value)
        if dimension:
            side = "QANCHOR" if question and "Int" in prontype else "ANCHOR"
            acts[f"{side}={dimension}"] = lemma.weight
        dimension = DEICTIC_ANCHORS.get(lemma.value)
        if dimension:
            weight = (-abs(lemma.weight)
                      if lemma.value in NEGATIVE_DEICTICS else lemma.weight)
            acts[f"ANCHOR={dimension}"] = weight
    return acts


class Representation(Enum):
    """Dvě reprezentace aktivací slova.

    METADATA — jen váhy vertikál gramatiky; žádná konkrétní data.
    COMPLETE — navíc slovní vertikála WORD=<lemma> („Petr").
    """

    METADATA = "metadata"
    COMPLETE = "complete"


class Activations:
    """Vážené aktivace jednoho slova: getter/setter vah + pohled jako pole.

    Drží dvě vrstvy: gramatické vertikály (výstup activations()) a slovní
    vertikálu WORD=<lemma>. Reprezentace METADATA vydá jen gramatiku,
    COMPLETE obojí — z COMPLETE jde METADATA kdykoli odvodit, obráceně ne.

    Slovní vertikálu dostává každé slovo včetně zavřených tříd (tam se
    s LEM= překrývá — vědomá jednoduchost, dokud měření neřekne jinak).
    """

    def __init__(self, meta: dict, word_key: str | None = None,
                 word_weight: float = DEFAULT_WEIGHT) -> None:
        self._meta = dict(meta)
        self._word = {word_key: word_weight} if word_key else {}

    @classmethod
    def from_row(cls, row: dict, question: bool = False) -> "Activations":
        """Postaví aktivace z rozvinutého řádku (expand_token).

        question říká, že řádek stojí v tázací větě (is_question) —
        rozhoduje o QLEM a o rozřešení PronType=Int,Rel vahami.
        Slovní klíč nese i UPOS ze stejného důvodu jako LEM: „stát"
        (NOUN) a „stát" (VERB) jsou dvě různá slova.
        """
        lemma = row["lemma"]
        if lemma is None:
            return cls(activations(row, question))
        return cls(activations(row, question),
                   word_key=f"WORD={row['upos'].value}:{lemma.value}",
                   word_weight=lemma.weight)

    # --- getter a setter vah -------------------------------------------

    def get(self, key: str) -> float:
        """Váha vertikály; neznámá vertikála je KeyError s hláškou."""
        for layer in (self._meta, self._word):
            if key in layer:
                return layer[key]
        raise KeyError(f"vertikála {key!r} v aktivacích není")

    def set(self, key: str, weight: float) -> None:
        """Změní váhu existující vertikály.

        Mění se jen váha, ne množina vertikál — přidání nové aktivace je
        stavba řádku (from_row), ne ladění vah. Rozsah hlídá stejně jako
        MetaValue: mimo −1…+1 je ValueError hned tady, ne až v počítání.
        """
        if not WEIGHT_MIN <= weight <= WEIGHT_MAX:
            raise ValueError(f"váha {weight} je mimo rozsah "
                             f"{WEIGHT_MIN} … {WEIGHT_MAX}")
        for layer in (self._meta, self._word):
            if key in layer:
                layer[key] = weight
                return
        raise KeyError(f"vertikála {key!r} v aktivacích není")

    # --- pohledy --------------------------------------------------------

    def weights(self,
                representation: Representation = Representation.METADATA
                ) -> dict:
        """{vertikála: váha} pro danou reprezentaci (kopie, ne vnitřek)."""
        if representation is Representation.COMPLETE:
            return {**self._meta, **self._word}
        return dict(self._meta)

    def as_array(self, registry,
                 representation: Representation = Representation.METADATA,
                 grow: bool = True):
        """Poskytne aktivace jako pole (vektor float32) přes registr.

        Sloupec = index vertikály v registru, hodnota = váha, 0.0 = bez
        aktivace. grow=True nechá registr vyrůst o neznámé vertikály;
        zpět na JSON vede registry.unvectorize(vektor).
        """
        return registry.vectorize(self.weights(representation), grow=grow)
