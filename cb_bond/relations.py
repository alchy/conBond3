"""RelationMiner — vztahy vytěžené z dat, ne vypsané ručně.

Dvě rodiny vazeb, obě zapsané do registru jako vážené hrany, takže je
párování dostane zadarmo šířením (`spread_depth`) — žádný zvláštní kód
v datové cestě.

## Definice: kopula s nominativem

„Gravitace **je** síla působící mezi tělesy." — root NOUN nebo PROPN
v NOMINATIVU + `nsubj` + `cop` dá vazbu
`WORD=NOUN:gravitace → WORD=NOUN:síla`.

Pád rootu je celý rozdíl: „Muž **byl** ve vězení" má tutéž kopuli, ale
root v LOKÁLU — říká, KDE muž byl, ne co muž je. Kdo vzor postaví na
přítomnosti kopule, nasype si do osy vazby typu muž→vězení.

Na 12 258 větách to dá 94 vazeb (foton→částice, elektromotor→stroj).

## Derivace: společný kmen × překryv sousedství

*rychlost* a *rychlostní* jsou totéž slovo v jiném kabátě; pytel je
nespojí, protože jsou to různá lemmata. Kmen je spojí — ale jen když
je dost dlouhý:

    kmen bez diakritiky ≥ 5 znaků A ZÁROVEŇ ≥ 75 % kratšího lemmatu
    síla   = délka kmene / délka delšího lemmatu
    váha   = 0,7 · (síla/2 + překryv sousedství/2)

    rychlost(8) × rychlostní(10): kmen 8 → síla 0,8 → váha 0,28
    naléhavý × náledí: kmen po složení diakritiky jen „nale" (4) → nic

**Nikdy plošně.** Plošné nasazení dalo 11 268 vazeb a stálo baseline
3,3 bodu — vazby mezi vším, co si je náhodou podobné, jsou šum. Proto
`around=` : těží se jen kolem slov otázky a její expanze.
"""

import unicodedata

#: Čím SMÍ být definiens (root kopulární věty). Vlastní jméno taky:
#: „Jméno té hvězdy je Pelyněk." je definice jako každá jiná. Kdo
#: připustí jen NOUN, přijde o celou třídu — naměřeno 91 vazeb místo
#: zmražených 94 na 12 258 větách.
DEFINIENS_UPOS = frozenset({"NOUN", "PROPN"})

#: Váha definiční vazby. Není to 1,0 schválně: definice je silný, ale
#: ne totožnostní vztah — gravitace je síla, síla není gravitace.
DEFINITION_WEIGHT = 0.7

#: Táž váha jako strop pro derivace; násobí se silou kmene a překryvem.
DERIVATION_WEIGHT = 0.7

#: Kmen musí mít aspoň tolik znaků. Pod tím spojuje náhodné shody
#: (naléhavý × náledí sdílí „nale") — naměřená mez, ne odhad.
MIN_STEM = 5

#: A zároveň musí pokrýt aspoň tolik z kratšího lemmatu.
MIN_STEM_SHARE = 0.75


def bez_diakritiky(text: str) -> str:
    """Text bez diakritiky, malými písmeny — pro porovnání kmenů.

    Diakritika v češtině nese rozdíl mezi *náledí* a *naléhavý*, ale
    taky mezi *kámen* a *kamení*, které jsou totéž slovo. Skládá se
    proto pryč a rozhodnutí nese délka kmene.
    """
    rozlozene = unicodedata.normalize("NFD", text.lower())
    return "".join(z for z in rozlozene if not unicodedata.combining(z))


def kmen(prvni: str, druhy: str) -> str:
    """Společný začátek dvou lemmat po složení diakritiky."""
    a, b = bez_diakritiky(prvni), bez_diakritiky(druhy)
    spolecne = 0
    for za, zb in zip(a, b):
        if za != zb:
            break
        spolecne += 1
    return a[:spolecne]


class RelationMiner:
    """Těží vztahy z korpusu a grafu; zapisuje je do registru.

    Vytěžené vazby si pamatuje (`definitions`, `derivations`) i se
    zdrojem — registr drží jen váhu, ale odkud vazba přišla, je při
    ladění to první, na co se člověk ptá.
    """

    def __init__(self) -> None:
        self.definitions: list[tuple] = []
        self.derivations: list[tuple] = []

    # --- definice -------------------------------------------------------

    def mine_definitions(self, corpus, registry) -> int:
        """Projde korpus a zapíše definiční vazby; vrátí počet NOVÝCH.

        Podruhé nad týmž korpusem vrátí nulu — vazba, která už v ose je,
        se nepočítá znovu, jinak by číslo rostlo s počtem spuštění.
        """
        pocet = 0
        for pole in corpus:
            dvojice = _definicni_dvojice(pole.tokens)
            if dvojice is None:
                continue
            src, dst = dvojice
            if registry.get_link(src, dst) is not None:
                continue
            registry.link(src, dst, DEFINITION_WEIGHT)
            self.definitions.append((src, dst, DEFINITION_WEIGHT,
                                     "definition"))
            pocet += 1
        return pocet

    # --- derivace -------------------------------------------------------

    def mine_derivations(self, graph, registry, around=None) -> int:
        """Zapíše derivační vazby mezi uzly grafu; vrátí počet nových.

        `around` je množina lemmat, kolem kterých se má těžit — bez ní
        se těží plošně, což je naměřeně horší (11 268 vazeb, −3,3 bodu
        baseline). Volající má skoro vždy důvod ji předat.
        """
        uzly = [klic for klic in graph.nodes() if ":" in klic]
        pocet = 0
        for i, prvni in enumerate(uzly):
            lemma_a = prvni.split(":", 1)[1]
            for druhy in uzly[i + 1:]:
                lemma_b = druhy.split(":", 1)[1]
                if around is not None and not (
                        lemma_a in around or lemma_b in around):
                    continue
                vaha = self._derivacni_vaha(graph, prvni, druhy,
                                            lemma_a, lemma_b)
                if vaha is None:
                    continue
                src, dst = (f"WORD={prvni}", f"WORD={druhy}")
                if registry.get_link(src, dst) is not None:
                    continue
                registry.link(src, dst, vaha)
                self.derivations.append((src, dst, vaha, "derivation"))
                pocet += 1
        return pocet

    def _derivacni_vaha(self, graph, prvni, druhy, lemma_a, lemma_b):
        """Váha páru, nebo None, když pár neprojde kmenovou mezí."""
        spolecny = kmen(lemma_a, lemma_b)
        kratsi = min(len(bez_diakritiky(lemma_a)), len(bez_diakritiky(lemma_b)))
        delsi = max(len(bez_diakritiky(lemma_a)), len(bez_diakritiky(lemma_b)))
        if len(spolecny) < MIN_STEM or not kratsi:
            return None
        if len(spolecny) / kratsi < MIN_STEM_SHARE:
            return None
        sila = len(spolecny) / delsi
        prekryv = _prekryv_sousedstvi(graph, prvni, druhy)
        return DERIVATION_WEIGHT * (sila / 2 + prekryv / 2)


def _definicni_dvojice(tokens):
    """(zdroj, cíl) definiční vazby, nebo None.

    Vzor: root je NOUN v nominativu, má u sebe kopuli a podmět v nsubj.
    """
    root = next((t for t in tokens if t.head == 0), None)
    if root is None or root.upos not in DEFINIENS_UPOS:
        return None
    if (root.feats or {}).get("Case") != "Nom":
        return None                      # lokativ říká KDE, ne CO
    ma_kopuli = any(t.deprel == "cop" and t.head == root.id for t in tokens)
    if not ma_kopuli:
        return None
    podmet = next((t for t in tokens
                   if t.deprel == "nsubj" and t.head == root.id), None)
    if podmet is None or podmet.upos not in ("NOUN", "PROPN"):
        return None
    if podmet.lemma == root.lemma:
        # „Trpasličí galaxie je malá galaxie." — definiční tvar, ale
        # vazba by byla smyčka v ose a šíření by aktivaci zesilovalo
        # samu ze sebe. Informaci nenese žádnou.
        return None
    return (f"WORD={podmet.upos}:{podmet.lemma}",
            f"WORD={root.upos}:{root.lemma}")


def _prekryv_sousedstvi(graph, prvni: str, druhy: str) -> float:
    """Jaccard sousedství dvou uzlů — 0,0, když jeden sousedy nemá."""
    a = set(graph.node_stat(prvni).neighbours)
    b = set(graph.node_stat(druhy).neighbours)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
