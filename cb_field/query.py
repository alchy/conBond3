"""Logické operace mezi koši — AND, OR, NOT nad výsledky otázek.

Zadání J. (2026-08-04): *„otázka sama vybere kandidáty, druhá též, pak
logická operace nad nimi."* Každá otázka projde párováním samostatně
a dá svým kandidátům skóre; operace se dělá až nad výsledky, po
složkách — kandidáti jsou u všech otázek titíž (každý token korpusu je
kandidát, § matching), takže se skóre dají skládat přímo.

    kdo = match(SentenceField.from_text("Kdo napsal Principia?", …), corpus)
    kdy = match(SentenceField.from_text("Kdy vyšla kniha?", …), corpus)
    oba = AND(kdo, kdy)          # kandidát musí sedět oběma otázkám
    jine = NOT(kdo)              # co odpovědí NENÍ

Operace vahami, ne větvením (§ registr): AND je součin, OR součet,
NOT obrácené znaménko. Výsledkem je zase MatchResult, takže se dá
řetězit — AND(kdo, NOT(kdy)) je legitimní výraz. Východisko
(odpoved/dotaz/nevim) se přepočítá týmiž řezy θ a ε; nikde jinde se
neřeže.

Pozn. ke skládání skóre: členy skóre jsou kosiny (−1…+1) a součin dvou
záporných by dal kladné — „ani jedné otázce nesedí" by vyšlo jako
„sedí oběma". AND proto pracuje se zápornou částí zvlášť: součin platí
pro kladné, jinak rozhoduje horší z obou (min). Je to táž logika jako
u pokrytí: konjunkce je nejslabší článek.
"""

from cb_field.matching import EPSILON, THETA, Candidate, MatchResult


def _key(candidate) -> tuple:
    return (id(candidate.sentence), candidate.center)


def _rebuild(scores: dict, source: dict, theta: float,
             epsilon: float) -> MatchResult:
    """Ze skóre a předloh kandidátů poskládá seřazený výsledek."""
    candidates = []
    for key, score in scores.items():
        original = source[key]
        candidates.append(Candidate(
            sentence=original.sentence, center=original.center,
            score=score, meet_score=original.meet_score,
            cover_score=original.cover_score, fit_score=original.fit_score,
            topic_score=original.topic_score,
            given_score=original.given_score,
            decomposition=original.decomposition))   # rozklad zůstává líný
    candidates.sort(key=lambda c: -c.score)
    if not candidates or candidates[0].score < theta:
        return MatchResult(outcome="nevim", candidates=candidates)
    if len(candidates) > 1 and \
            candidates[0].score - candidates[1].score < epsilon:
        return MatchResult(outcome="dotaz", candidates=candidates)
    return MatchResult(outcome="odpoved", candidates=candidates)


def _pair(left: MatchResult, right: MatchResult):
    """Skóre obou výsledků na společných kandidátech + jejich předlohy."""
    left_scores = {_key(c): c.score for c in left.candidates}
    right_scores = {_key(c): c.score for c in right.candidates}
    source = {_key(c): c for c in left.candidates}
    source.update({_key(c): c for c in right.candidates})
    return left_scores, right_scores, source


def AND(left: MatchResult, right: MatchResult, theta: float = THETA,
        epsilon: float = EPSILON) -> MatchResult:
    """Kandidát musí sedět oběma otázkám (průnik).

    Kladná skóre se násobí (obojí musí svítit), jinak rozhoduje horší
    z obou — konjunkce je nejslabší článek a dvě záporná se nesmějí
    vynásobit na kladné.
    """
    left_scores, right_scores, source = _pair(left, right)
    scores = {}
    for key in left_scores.keys() & right_scores.keys():
        a, b = left_scores[key], right_scores[key]
        scores[key] = a * b if a > 0 and b > 0 else min(a, b)
    return _rebuild(scores, source, theta, epsilon)


def OR(left: MatchResult, right: MatchResult, theta: float = THETA,
       epsilon: float = EPSILON) -> MatchResult:
    """Stačí jedna z otázek (sjednocení): skóre se sčítají."""
    left_scores, right_scores, source = _pair(left, right)
    scores = {}
    for key in left_scores.keys() | right_scores.keys():
        scores[key] = left_scores.get(key, 0.0) + right_scores.get(key, 0.0)
    return _rebuild(scores, source, theta, epsilon)


def sentence_activation(result: MatchResult, mean: bool = True) -> list:
    """Aktivace po VĚTÁCH: kladné aktivace kandidátů, NORMALIZOVANĚ.

    Odpověď nemusí být jediný střed (J. 2026-08-04) — aktivace se smí
    cílit na větu nebo skupinu slov. Věta je koš jako každý jiný, jen
    širší. Záporné příspěvky se nezapočítávají: věta nemá být trestána
    za to, že obsahuje i slova mimo odpověď (to řeší NOT na úrovni
    výrazu).

    Normalizace délkou je nutná, ne kosmetická: prostý součet měří
    počet slov, ne shodu. Naměřeno na „Kde byl pokřtěn Ježíš?" —
    nejaktivnější věta vyšla dlouhá pasáž o znesvěcující ohavnosti
    (52,1) jen proto, že má nejvíc tokenů; věta s odpovědí byla níž.
    Je to táž chyba, jakou u skóre kandidáta opravil kosinus.

    mean=False vrátí surový součet (mohutnost aktivace ve větě), když
    ho volající vědomě chce — normalizovaný je výchozí.

    Vrací [(věta, aktivace, [kandidáti sestupně])] seřazené sestupně.
    """
    per_sentence: dict = {}
    for candidate in result.candidates:
        entry = per_sentence.setdefault(
            id(candidate.sentence), [candidate.sentence, 0.0, []])
        entry[1] += max(candidate.score, 0.0)
        entry[2].append(candidate)
    out = []
    for sentence, activation, candidates in per_sentence.values():
        candidates.sort(key=lambda c: -c.score)
        if mean and candidates:
            activation /= len(candidates)
        out.append((sentence, activation, candidates))
    out.sort(key=lambda row: -row[1])
    return out


def span(result: MatchResult, width: int = 2) -> list:
    """Aktivace souvislých SKUPIN slov (odpověď o víc slovech).

    Skupina je okno width sousedních tokenů jedné věty; její aktivace
    je součet kladných aktivací jejích středů. Sousedství nese význam
    („Bohumil Hrabal", „v devět hodin"), takže víceslovná odpověď
    nepotřebuje nový mechanismus — jen širší koš.

    Vrací [(věta, od, do, aktivace)] seřazené sestupně.
    """
    out = []
    for sentence, _activation, candidates in sentence_activation(result):
        by_center = {c.center: max(c.score, 0.0) for c in candidates}
        length = len(sentence.tokens)
        for start in range(max(length - width + 1, 1)):
            stop = min(start + width, length)
            total = sum(by_center.get(i, 0.0) for i in range(start, stop))
            out.append((sentence, start, stop, total))
    out.sort(key=lambda row: -row[3])
    return out


def activation_field(result: MatchResult, sentence=None):
    """Výsledek jako POLE: aktivace na každý řádek věty (J. 2026-08-04).

    Nejobecnější tvar odpovědi — nic se nevybírá ani neřeže, vrací se
    rozložení aktivace přes pole, tak jak vyšlo. Token, skupina i věta
    jsou jen čtení téhož pole v jiném rozlišení (argmax / okno / součet).

    sentence: pole jedné věty; None = nejaktivnější věta výsledku.
    Vrací (věta, vektor aktivací délky len(věta.tokens)).
    """
    import numpy as np

    if sentence is None:
        ranked = sentence_activation(result)
        if not ranked:
            return None, np.zeros(0, dtype=np.float32)
        sentence = ranked[0][0]
    field = np.zeros(len(sentence.tokens), dtype=np.float32)
    for candidate in result.candidates:
        if candidate.sentence is sentence:
            field[candidate.center] = candidate.score
    return sentence, field


def NOT(result: MatchResult, theta: float = THETA,
        epsilon: float = EPSILON) -> MatchResult:
    """Koš „co odpovědí NENÍ": obrácené znaménko skóre.

    Není to filtr — nic se nezahazuje. Kandidát, který otázce seděl,
    má teď zápornou váhu a dá se s ním dál počítat: AND(kdo, NOT(kdy))
    hledá to, co odpovídá první otázce a druhé ne.
    """
    scores = {_key(c): -c.score for c in result.candidates}
    source = {_key(c): c for c in result.candidates}
    return _rebuild(scores, source, theta, epsilon)
