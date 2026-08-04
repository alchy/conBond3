"""ContrastiveTrainer — učení vztahu otázka(meta) → věta(meta).

## Invariant 1, neporušitelný

**Učí se výhradně nad metadaty z vertikál.** Konkrétní slovo se do
učení dostane jedině promocí do custom slotu (`CUSTOM=`). Důvod je
naměřený: párové mosty slovo↔slovo se mezi otázkami nepřenášejí —
naučí se, že „Jordán" patří ke „křtu", a další otázce to není k ničemu.
Typ se přenáší, dvojice slov ne.

Hlídá to `LEARN_PREFIXES` a pojistkový test, který hledá `WORD=`
v učicím pytli a v každé naučené hraně.

## Větný kontrast

Učicí vztah je otázka(meta) → věta(meta), ne otázka → token:

    fitující věta = nejvýš položená s lemmatem odpovědi
                    (answer_position má přednost, když je)
    soupeř        = nejvýš položená BEZ něj
    vrcholy       = gaussovské čtení obou (krok 4)

Pytle jsou CELÉ věty bez zdůrazněného středu — **poziční nezávislost**:
pozice zůstává jen v tom, KTERÁ věta fituje, ne kde v ní odpověď leží.
Roli nese pád, čeština si to může dovolit.

## Hinge s relativní marží

    marže = margin · |vrchol soupeře|
    loss  = max(0, marže + soupeř − správná)

Marže je RELATIVNÍ, ne pevná: absolutní marže by u slabých vrcholů
žádala nesmyslně velký odstup a u silných skoro žádný. Když je marže
splněna, krok se NEDĚLÁ — proto „korekcí 0" znamená skutečnou
konvergenci, ne zaseknutí.

Při porušení je gradient `q_bag ⊗ (pytel fitující − pytel soupeře)`,
Adam na hraně registru, meze ±1. **Axiomy se chrání**: hierarchie
kotev je jazyk systému, ne parametr.

## Validace řídí konec

30 % otázek se odloží (deterministický vrstvený los, semínko 328).
Validace se měří i PŘED učením, aby měla první epocha s čím porovnávat
— jinak by prošla, i kdyby zhoršila všechno, a právě ta bývá nejdivočejší.
Epocha, která zlepšila trénink a ZNATELNĚ zhoršila validaci, se
**odvolá** — vazby se vrátí bit po bitu. Bez toho by se učení upsalo
tréninku a zobecnění by nikdo nehlídal.

„Znatelně" je tam schválně: odvolávat při jakémkoli růstu znamená
odvolávat i šum v poslední cifře. Naměřeno — epocha srazila trénink
0,1144 → 0,0950 a validaci zhoršila o 0,00006; bez tolerance se
odvolala a systém se nenaučil nic. Mez je relativní (1 %), aby
nezávisela na měřítku lossu.

## lr je páka s křivkou, ne konstanta

Naměřeno na 2 912 větách a 120 otázkách supervize (validace 30 %):

    lr       ponecháno epoch  naučených hran  z toho prostorových
    0,003        4            388                  82
    0,001        6            386                  81
    0,0005       6            373                  78
    0,0002       6            373                  78

Provozní bod je **0,001**: ponechá se celý rozpočet epoch. Naučené
hrany mají správná znaménka — `QLEM=ADV:odkud → ANCHOR=space:from`
+0,011, `QLEM=ADV:kde → ANCHOR=space:loc` +0,006, `QLEM=ADV:kam →
ANCHOR=space:loc` −0,006. Magnitudy jsou zatím malé, takže se metrika
nehne, ale směr sedí.

## Zavržené cesty (nezkoušet znovu)

- šíření učicích pytlů maticí (22,9M hran, 0,43 → 0,17),
- `WORD=` v pytlích (memorování),
- kontrast tokenových oken místo vět.
"""

import math
from dataclasses import dataclass, field as _field

from cb_bond.answer import AnswerField

#: Co smí do učicího pytle. WORD= tam NENÍ a nikdy nebude — konkrétní
#: slovo se do učení dostane jedině promocí do CUSTOM= slotu.
LEARN_PREFIXES = ("LEM=", "QLEM=", "ANCHOR=", "QANCHOR=", "Polarity=",
                  "CUSTOM=")

#: Meze váhy hrany — tytéž jako u aktivací.
WEIGHT_MIN, WEIGHT_MAX = -1.0, 1.0


def learning_bag(rows) -> dict:
    """Součet řádků přes učicí masku — surový pytel, bez šíření.

    Šíření pytlů maticí bylo zkoušeno a zavrženo měřením (22,9M hran,
    přesnost 0,43 → 0,17): učí se vztah, ne rozmazaná oblast.
    """
    pytel: dict[str, float] = {}
    for radek in rows:
        for klic, vaha in radek.items():
            if klic.startswith(LEARN_PREFIXES):
                pytel[klic] = pytel.get(klic, 0.0) + vaha
    return pytel


def sentence_hit(result, lemma: str, corpus, top: int = 3) -> bool:
    """Nese některá z TOP vět lemma odpovědi?

    Měřítko úspěchu na úrovni VĚTY: nezávisí na tom, který token systém
    nakonec vybral, takže roste dřív a spojitěji než přesnost@1.
    """
    videne = []
    for kandidat in result.candidates:
        if kandidat.sentence not in videne:
            videne.append(kandidat.sentence)
        if len(videne) >= top:
            break
    return any(lemma in {t.lemma for t in corpus[pozice].tokens}
               for pozice in videne)


class ValidationSplit:
    """Vrstvený deterministický los — 30 % otázek stranou.

    Vrstvený podle zodpověditelnosti: kdyby se do validace dostaly samé
    zodpověditelné, nikdo by nehlídal mlčení. Deterministický, protože
    dvě měření musejí porovnávat totéž (princip 8).
    """

    def __init__(self, share: float = 0.3, seed: int = 328) -> None:
        self.share = share
        self.seed = seed

    def split(self, entries) -> tuple:
        train, held = [], []
        for zodpoveditelne in (True, False):
            vrstva = [z for z in entries
                      if bool(z.get("zodpoveditelna")) is zodpoveditelne]
            poradi = sorted(range(len(vrstva)),
                            key=lambda i: _hash(f"{self.seed}:{i}:"
                                                f"{vrstva[i].get('otazka')}"))
            kolik = int(len(vrstva) * self.share)
            odlozene = set(poradi[:kolik])
            held.extend(vrstva[i] for i in sorted(odlozene))
            train.extend(vrstva[i] for i in range(len(vrstva))
                         if i not in odlozene)
        return train, held


@dataclass
class TrainingReport:
    """Průběh učení po epochách — a čím se která epocha zdůvodnila."""

    epochs: list = _field(default_factory=list)

    @property
    def trained_epochs(self) -> int:
        """Kolik epoch zůstalo (odvolané se nepočítají)."""
        return sum(1 for e in self.epochs if not e["odvolano"])


class ContrastiveTrainer:
    """Učí vazby registru kontrastem fitující věty proti soupeřící."""

    def __init__(self, corpus, matcher, parser, *, split=None,
                 lr: float = 0.001, margin: float = 0.2,
                 sigma: float = 1.5, tolerance: float = 0.01) -> None:
        self.corpus = corpus
        self.matcher = matcher
        self.parser = parser
        self.split = split or ValidationSplit()
        self.lr = lr
        self.margin = margin
        self.sigma = sigma
        #: O kolik smí validační loss stoupnout, než se epocha odvolá.
        #: Bez tolerance odvolává i šum v poslední cifře: naměřeno,
        #: epocha srazila trénink 0,114 → 0,095 a validaci zhoršila
        #: o 0,00006 — a odvolala se, takže se systém neučil vůbec.
        self.tolerance = tolerance
        self.report = TrainingReport()
        self._adam: dict = {}

    # --- učení ----------------------------------------------------------

    def train(self, entries, max_epochs: int = 10) -> TrainingReport:
        """Odloží validaci, učí po epochách a hlídá zobecnění."""
        trenink, validace = self.split.split(entries)
        self.report = TrainingReport()
        # Validace se změří JEŠTĚ PŘED učením. Bez toho by první epocha
        # neměla s čím porovnávat a prošla by, i kdyby zhoršila všechno —
        # a právě první epocha bývá ta nejdivočejší.
        predchozi_valid = self._validacni_loss(validace)

        for _ in range(max_epochs):
            snap = self.corpus.registry.snapshot()
            statistika = self._epocha(trenink)
            valid = self._validacni_loss(validace)
            odvolat = valid > predchozi_valid * (1.0 + self.tolerance)
            if odvolat:
                self.corpus.registry.restore(snap)
            else:
                predchozi_valid = valid
            statistika.update({"loss_valid": round(valid, 4),
                               "odvolano": odvolat})
            self.report.epochs.append(statistika)
            if odvolat or not statistika["korekci"]:
                break
        return self.report

    def _epocha(self, entries) -> dict:
        loss_celkem = korekci = hran = 0
        vrcholy_spravnych = []
        for zaznam in entries:
            krok = self._krok(zaznam)
            if krok is None:
                continue
            loss, zmen, vrchol = krok
            loss_celkem += loss
            korekci += bool(zmen)
            hran += zmen
            if vrchol is not None:
                vrcholy_spravnych.append(vrchol)
        return {"loss": round(loss_celkem / max(1, len(entries)), 4),
                "korekci": korekci, "hran": hran,
                "vrchol_median": round(_median(vrcholy_spravnych), 4)}

    def _krok(self, zaznam):
        """Jeden učicí krok; None, když se nemá z čeho učit."""
        otazka = self._pole_otazky(zaznam["otazka"])
        vysledek = self.matcher.match(otazka)
        if not vysledek.candidates:
            return None

        vrcholy = AnswerField(vysledek).gaussian_peaks(self.sigma)
        lemma = zaznam.get("odpoved_lemma")
        pozice = zaznam.get("answer_position")
        spravna = soupere = None
        for veta, vrchol, _ in vrcholy:
            fituje = (veta == pozice) if pozice is not None \
                else (lemma is not None and lemma in
                      {t.lemma for t in self.corpus[veta].tokens})
            if fituje and spravna is None:
                spravna = (veta, vrchol)
            elif not fituje and soupere is None:
                soupere = (veta, vrchol)
            if spravna and soupere:
                break

        if spravna is None or soupere is None:
            # Bez soupeře se nemá co kontrastovat — a bez fitující věty
            # by se učilo proti ničemu.
            return None

        marze = self.margin * abs(soupere[1])
        loss = max(0.0, marze + soupere[1] - spravna[1])
        if loss <= 0.0:
            return loss, 0, spravna[1]

        q_bag = learning_bag(otazka.complete)
        rozdil = _rozdil_pytlu(learning_bag(self.corpus[spravna[0]].complete),
                               learning_bag(self.corpus[soupere[0]].complete))
        zmen = self._uprav_hrany(q_bag, rozdil)
        return loss, zmen, spravna[1]

    def _uprav_hrany(self, q_bag: dict, rozdil: dict) -> int:
        """Gradient q_bag ⊗ rozdíl pytlů → Adam na hraně, meze ±1."""
        registry = self.corpus.registry
        zmen = 0
        for q_osa, q_vaha in q_bag.items():
            for s_osa, s_vaha in rozdil.items():
                if q_osa == s_osa:
                    # Osa sama na sebe: šíření by aktivaci jen zesílilo
                    # samu ze sebe a vztah to nenese. Táž úvaha jako
                    # u smyček v grafu, jen o patro výš.
                    continue
                if _je_axiom(q_osa, s_osa):
                    continue     # hierarchie kotev je jazyk, ne parametr
                gradient = q_vaha * s_vaha
                if gradient == 0.0:
                    continue
                stara = registry.get_link(q_osa, s_osa) or 0.0
                nova = _mez(stara + self._adam_krok((q_osa, s_osa), gradient))
                if nova != stara:
                    registry.link(q_osa, s_osa, nova)
                    zmen += 1
        return zmen

    def _adam_krok(self, klic, gradient: float, beta1: float = 0.9,
                   beta2: float = 0.999, eps: float = 1e-8) -> float:
        """Adam na jedné hraně — vlastní, aby nebyl potřeba framework."""
        m, v, t = self._adam.get(klic, (0.0, 0.0, 0))
        t += 1
        m = beta1 * m + (1 - beta1) * gradient
        v = beta2 * v + (1 - beta2) * gradient * gradient
        self._adam[klic] = (m, v, t)
        m_hat = m / (1 - beta1 ** t)
        v_hat = v / (1 - beta2 ** t)
        return self.lr * m_hat / (math.sqrt(v_hat) + eps)

    def _validacni_loss(self, entries) -> float:
        """Průměrná hinge loss na odložených otázkách — bez učení."""
        if not entries:
            return 0.0
        celkem = 0.0
        for zaznam in entries:
            krok = self._krok_bez_uceni(zaznam)
            if krok is not None:
                celkem += krok
        return celkem / len(entries)

    def _krok_bez_uceni(self, zaznam):
        otazka = self._pole_otazky(zaznam["otazka"])
        vysledek = self.matcher.match(otazka)
        if not vysledek.candidates:
            return None
        vrcholy = AnswerField(vysledek).gaussian_peaks(self.sigma)
        lemma = zaznam.get("odpoved_lemma")
        pozice = zaznam.get("answer_position")
        spravna = soupere = None
        for veta, vrchol, _ in vrcholy:
            fituje = (veta == pozice) if pozice is not None \
                else (lemma is not None and lemma in
                      {t.lemma for t in self.corpus[veta].tokens})
            if fituje and spravna is None:
                spravna = vrchol
            elif not fituje and soupere is None:
                soupere = vrchol
            if spravna is not None and soupere is not None:
                break
        if spravna is None or soupere is None:
            return None
        return max(0.0, self.margin * abs(soupere) + soupere - spravna)

    def _pole_otazky(self, text: str):
        from cb_field import SentenceField
        return SentenceField.from_text(text, self.parser, r=self.corpus.r,
                                       registry=self.corpus.registry)


def _rozdil_pytlu(spravny: dict, soupere: dict) -> dict:
    """pytel(fitující) − pytel(soupeře); nuly se zahodí."""
    rozdil = {}
    for klic in set(spravny) | set(soupere):
        hodnota = spravny.get(klic, 0.0) - soupere.get(klic, 0.0)
        if hodnota:
            rozdil[klic] = hodnota
    return rozdil


def _je_axiom(src: str, dst: str) -> bool:
    """Hierarchie kotev — vazby, které učení nesmí přepsat."""
    return (src.startswith(("ANCHOR=", "QANCHOR="))
            and dst.startswith("ANCHOR="))


def _mez(vaha: float) -> float:
    return max(WEIGHT_MIN, min(WEIGHT_MAX, vaha))


def _median(hodnoty) -> float:
    if not hodnoty:
        return 0.0
    serazene = sorted(hodnoty)
    stred = len(serazene) // 2
    if len(serazene) % 2:
        return serazene[stred]
    return (serazene[stred - 1] + serazene[stred]) / 2


def _hash(text: str) -> int:
    """Determinističtější než hash() — ten se mezi běhy solí."""
    import hashlib
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
