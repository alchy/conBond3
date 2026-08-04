"""Učení vah propojení — fáze 4c (kontrastivně na etalonu) + mlčení.

Fáze 4b (Hebb) je z přejímací cesty VYŘAZENÁ (J. 2026-08-04): nad
surovými souvýskyty blokuje (korpusy 0,43 → 0,17). Mechanismus hebb()
zůstává a vrátí se až nad strukturou (dluh D4).

Spuštění celého protokolu s měřením před/po každou fází:

    ./run-python -m cb_field.learning

Koeficient propojení je učitelný parametr součinu (P-B spec): čím
silnější propojení, tím větší parametr. Učí se výhradně hrany se
zdrojem hebb/etalon — axiomy jsou definice jazyka a registr je chrání.
Protiváha (§ 6 spec): učení, které zvedne přesnost a shodí
NEVÍM-správnost, se nepřijímá — výsledek se hlásí, ne zamlčí.

Pozn. k poctivosti: 4c se v této fázi ladí a měří na TÉMŽE etalonu
(jiný zatím není) — číslo po 4c je tedy horní odhad, ne generalizace.
Zapsáno i v reportu; rozdělení etalonu přijde s jeho růstem.
"""

import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np

from cb_field.matching import MATCH_PREFIXES, W_CENTER, match

MODULE_DIR = Path(__file__).resolve().parent
REPORT = MODULE_DIR / "docs" / "mereni-uceni.md"
REPORT_KORPUSY = MODULE_DIR / "docs" / "mereni-uceni-korpusy.md"
LEARNED = MODULE_DIR / "data-persistent" / "verticals-learned.json"
LEARNED_KORPUSY = (MODULE_DIR / "data-persistent"
                   / "verticals-learned-korpusy.json")

#: Rychlost učení a spodní práh souvýskytů pro Hebba. Startovní hodnoty
#: (registr prahů modulu); kalibruje protokol níže.
ETA_HEBB = 0.5
#: Krok Adamu je ~η na hranu bez ohledu na surový gradient (druhý moment
#: normalizuje). Odvození: hrana je aktivní ~1× na epochu, běh má ~3
#: epochy a mosty u SGD stavěly celkové posuny řádu 0,01–0,03 na hranu
#: (η_sgd 0,15 × scale ~0,03) → η = 0,01. S η = 0,15 Adam divergoval:
#: loss 0,40 → 0,53, trefy 16 → 8 (naměřeno 2026-08-04).
ETA_CONTRAST = 0.01
#: Strop epoch je jen pojistka — trénink končí konvergencí: korekcí=0
#: (marže všude splněna), nebo odvoláním epochy, která zhoršila loss.
MAX_EPOCHS = 10

#: Zobecnění se měří na odložené sadě (J. 2026-08-04): 30 % otázek se
#: při učení nepoužije a loss na nich řídí odvolání epochy. Rozdělení
#: je deterministické (semínko — § 13, žádná náhoda bez semínka)
#: a vrstvené po zodpověditelnosti.
VALIDATION_SHARE = 0.3
SPLIT_SEED = 328


def split_etalon(entries, share: float = VALIDATION_SHARE,
                 seed: int = SPLIT_SEED) -> tuple:
    """(trénink, validace) — vrstveně po zodpověditelnosti, se semínkem."""
    import random
    rng = random.Random(seed)
    train, valid = [], []
    for answerable in (True, False):
        stratum = [e for e in entries
                   if bool(e["zodpoveditelna"]) == answerable]
        rng.shuffle(stratum)
        held_out = round(len(stratum) * share)
        valid.extend(stratum[:held_out])
        train.extend(stratum[held_out:])
    return train, valid


def sentence_hit(result, expected_lemma, top: int = 3) -> bool:
    """Úspěch posílení (J. 2026-08-04): VALIDNÍ VĚTA je mezi kandidáty
    — v top větách podle větné aktivace leží token s očekávaným
    lemmatem. Cíl je vybrat kandidátní věty s odpovědí; token je jen
    jemnější čtení téhož pole."""
    from cb_field.query import sentence_activation
    for sentence, _activation, _cands in sentence_activation(result)[:top]:
        if any(t.lemma == expected_lemma for t in sentence.tokens):
            return True
    return False


#: Relativní marže (krok 3 refaktoru, J. 2026-08-03): o kolik má správná
#: vést nad nejlepším špatným, vyjádřeno podílem soupeřova skóre — na
#: absolutní čísla se neváže. 0,2 je přenesená proporce staré absolutní
#: marže (1,0 proti mediánu vítězných skóre 4,9), ne nové číslo od oka.
#: Na typickém skóre ~1,1 dává marži ~0,22 > ε: učení míří bezpečně za
#: pásmo DOTAZ, ne na jeho hranici.
MARGIN_RATIO = 0.2

#: Adam (krok 4 refaktoru, rozhodl J.: „adam bude"): momenty na hranu,
#: řídce, bez frameworku (§ 19). Druhý moment přebírá i normalizaci
#: délky pytle, kterou dřív dělal ruční `scale` — krok na hraně je ~η
#: bez ohledu na mohutnost surového gradientu.
BETA1 = 0.9
BETA2 = 0.999
ADAM_EPS = 1e-8


#: Na čem se učí. Pravidlo J. (2026-08-04): *„učení probíhá nad
#: metadaty — nevstupují do něj konkrétní slova z korpusu, jen vše,
#: co je ve vertikálách a lexikální analýze. Učení páruje otázku
#: s větou jen jako METADATOVÝ MODEL, bez konkrétního lemmatu, s
#: výjimkou, kdy se slovo dostalo do vertikál."*
#:
#: WORD= proto v učicích pytlích NENÍ: jedinou branou konkrétního
#: slova do učení je promoce do custom slotů (aktivace CUSTOM= při
#: přegenerování korpusu). LEM=/QLEM= zůstávají — nesou jen zavřené
#: třídy (předložky, tázací slova), tedy lexikální analýzu, ne svět.
#: Dřívější mezistav (WORD= v pytlích s útlumem synonymních párů
#: SYNONYM_DAMPING=0,1) tím končí: párové mosty slovo↔slovo se mezi
#: otázkami stejně nepřenášely (§ 15) a povýšení slova řeší promoce.
LEARN_PREFIXES = ("LEM=", "QLEM=", "ANCHOR=", "QANCHOR=",
                  "Polarity=", "CUSTOM=")


def _semantic_bag(sentence, rows, center=None, prefixes=None) -> dict:
    """{vertikála: váha} přes dané řádky, jen učicí vertikály — SUROVÉ.

    center: řádek se zdůrazněním W_CENTER — týž profil, jaký má koš
    kandidáta v match(). Gradient se musí počítat nad touž geometrií,
    kterou optimalizuje: bez zdůraznění se odpověď ležící v okně obou
    kandidátů v rozdílu pytlů vyruší a most na ni nikdy nevznikne.

    Pytle jsou SUROVÉ schválně: šíření pytlů maticí před gradientem
    je zavržené měřením (2026-08-04: po tanh(v + v·L) na obou stranách
    22,9M hran, přesnost 0,43 → 0,17, dosah 10 → 5 — společný kontext
    se rozlije po poli dřív, než ho subtrakce stihne vyrušit).
    Promované osy do pytle vstupují AKTIVACÍ řádků (promoční cyklus),
    ne šířením.
    """
    allowed = LEARN_PREFIXES if prefixes is None else prefixes
    bag = {}
    for i in rows:
        emphasis = W_CENTER if i == center else 1.0
        for key, weight in sentence.complete[i].items():
            if key.startswith(allowed) \
                    and not key.startswith("WORD=PUNCT"):
                bag[key] = bag.get(key, 0.0) + weight * emphasis
    return bag


def hebb(corpus, eta: float = ETA_HEBB) -> dict:
    """4b: Hebbovské koeficienty ze souaktivací — „co se aktivuje spolu,
    to se propojí".

    Jednotka souaktivace je koš věty (celá věta jako pytel). Síla hrany
    je normalizovaný souvýskyt nad náhodu (NPMI ∈ −1…1) × eta — prosté
    počty by posilovaly frekvenci, ne vztah (protiváha měřítka). Hrany
    se zapisují oběma směry se zdrojem hebb; axiomy registr ochrání.
    """
    registry = corpus.registry
    bags = []
    for sentence in corpus:
        # Hebb je mimo přejímací cestu a pracuje na souvýskytech slov
        # (proto MATCH_PREFIXES, ne LEARN_PREFIXES) — až se vrátí nad
        # strukturu (D4), rozhodne se, na které úrovni má běžet.
        bags.append(frozenset(_semantic_bag(
            sentence, range(len(sentence.tokens)),
            prefixes=MATCH_PREFIXES)))
    total = len(bags)
    count = Counter()
    pair_count = Counter()
    for bag in bags:
        for key in bag:
            count[key] += 1
        ordered = sorted(bag)
        for a_i, a in enumerate(ordered):
            for b in ordered[a_i + 1:]:
                pair_count[(a, b)] += 1

    added = 0
    for (a, b), n_ab in pair_count.items():
        pmi = math.log(total * n_ab / (count[a] * count[b]))
        denominator = -math.log(n_ab / total)
        npmi = pmi / denominator if denominator > 0 else 0.0
        # Bez prahu a bez zahození záporných: málo dokladů = slabší
        # váha (n/(n+1)), záporné NPMI = záporná hrana. Týž útlum jako
        # u typů — filtr nahrazený vahou (J.: „žádné filtry").
        weight = max(-1.0, min(1.0, eta * npmi * n_ab / (n_ab + 1)))
        for src, dst in ((a, b), (b, a)):
            if registry.get_link(src, dst) is None:
                added += 1
            registry.link(src, dst, weight, source="hebb")
    return {"vet": total, "paru": len(pair_count), "hran": added}


def learn_types(corpus, eta: float = 0.5) -> dict:
    """Typ obecného jména z jeho okolí: „řeka je místo" (J. 2026-08-04).

    Řetěz, který J. ukázal: *kde → místo ← řeka*. Uzel „místo"
    v systému je (`ANCHOR=space`) a tázací „kde" k němu vede axiomem;
    chybí druhá půlka — obecná jména dimenzi nedostávají. Vlastní jméno
    „Jordán" má space z NameType=Geo, ale „řeka" nemá nic než dir:at
    z předložky, takže se s otázkou nikdy nepotká.

    Typ se proto UČÍ z textu, ne z tabulky (zákaz konkrétna): slovo
    dostane hranu ke kotvě, se kterou opakovaně stojí v jednom koši,
    silou NPMI (týž princip jako Hebb, jen cílený na strukturu, ne na
    souvýskyt slov — tím se naplňuje dluh D4 „Hebb až nad strukturou").
    Hrana vede WORD= → ANCHOR=, tedy slovo se povyšuje na typ; hrany
    slovo↔slovo tu nevznikají, zákaz synonym platí.
    """
    from collections import Counter
    registry = corpus.registry
    pair = Counter()
    word_count = Counter()
    anchor_count = Counter()
    total = 0
    for sentence in corpus:
        rows = sentence.complete
        for center in range(len(rows)):
            window = _window_rows(sentence, center, corpus.r)
            words = {k for k in rows[center]
                     if k.startswith("WORD=") and "PUNCT" not in k}
            # dimenze, ne upřesnění: space/time/entity/quantity —
            # „dir:at" nese předložka a o typu jména nevypovídá
            anchors = {k for i in window for k in rows[i]
                       if k.startswith("ANCHOR=") and ":" not in k}
            if not words:
                continue
            total += 1
            for w in words:
                word_count[w] += 1
                for a in anchors:
                    pair[(w, a)] += 1
            for a in anchors:
                anchor_count[a] += 1

    added = 0
    for (word, anchor), n in pair.items():
        expected = word_count[word] * anchor_count[anchor] / max(total, 1)
        if expected <= 0:
            continue                  # dvojice se v korpusu nepotkala
        pmi = math.log(n / expected)
        denominator = -math.log(n / max(total, 1))
        npmi = pmi / denominator if denominator > 0 else 0.0
        # Žádný práh doložení a žádné zahození záporné vazby (J. se
        # ptal na filtry — oba tu byly a oba byly moje):
        #   · málo dokladů = slabší váha, ne vyloučení (n/(n+1));
        #   · záporné NPMI = záporná hrana, ne ticho — „tohle slovo
        #     k té kotvě NEPATŘÍ" je stejně platný doklad jako opak
        #     a učení o něj nesmí přijít.
        weight = max(-1.0, min(1.0, eta * npmi * n / (n + 1)))
        if registry.get_link(word, anchor) is None:
            added += 1
        registry.link(word, anchor, weight, source="hebb")
    return {"kosu": total, "dvojic": len(pair), "typovych_hran": added}


def _window_rows(sentence, center, r):
    return range(max(0, center - r), min(len(sentence.tokens),
                                         center + r + 1))


def _restore_links(registry, snapshot: dict) -> None:
    """Vrátí vazby do stavu snapshotu — odvolání epochy učení."""
    for src, dst, weight, source in registry.links():
        kept = snapshot.get((src, dst))
        if kept is None:
            registry.unlink(src, dst)
        elif kept != (weight, source):
            registry.link(src, dst, kept[0], source=kept[1])


def contrastive_step(registry, question_bag: dict, correct_bag: dict,
                     wrong_bag: dict, eta: float = ETA_CONTRAST,
                     state: dict | None = None) -> int:
    """Jeden kontrastivní krok Adamem: posílit hrany otázka→správná,
    oslabit otázka→nejlepší špatná. Jen na souaktivovaných dvojicích
    (qᵢ·aⱼ ≠ 0); meze ±1; axiomy chrání registr. Vrací počet upravených
    hran.

    state: momenty Adamu {(od, do): (m, v, t)} — drží je volající po
    dobu tréninku. None = každý krok začíná bez paměti (první krok
    Adamu je krok znaménka, ±η).
    """
    # Gradient marže: g = q ⊗ (a⁺ − a⁻). Rozdíl schválně: co mají
    # správný a špatný kandidát společné, o vítězi nerozhoduje — a bez
    # filtrů je „špatný" obvykle soused ve stejné větě, takže sdílených
    # klíčů je většina. Učit se na nich znamená vyrábět šum (naměřeno:
    # bez rozdílu spadla přesnost 0,21 → 0,00).
    difference = {}
    for key, weight in correct_bag.items():
        difference[key] = difference.get(key, 0.0) + weight
    for key, weight in wrong_bag.items():
        difference[key] = difference.get(key, 0.0) - weight
    difference = {k: v for k, v in difference.items() if abs(v) > 1e-9}
    if not difference:
        return 0                       # kandidáti jsou v osách totožní

    if state is None:
        state = {}
    q_items = tuple(question_bag.items())
    a_items = tuple(difference.items())
    gradients = np.outer([w for _, w in q_items],
                         [d for _, d in a_items])
    changed = 0
    for row, (q_key, _q_weight) in enumerate(q_items):
        for col, (a_key, _delta) in enumerate(a_items):
            if q_key == a_key:
                continue
            existing = registry.get_link(q_key, a_key)
            if existing and existing[1] == "axiom":
                continue
            old = existing[0] if existing else 0.0
            gradient = float(gradients[row, col])
            m, v, t = state.get((q_key, a_key), (0.0, 0.0, 0))
            t += 1
            m = BETA1 * m + (1 - BETA1) * gradient
            v = BETA2 * v + (1 - BETA2) * gradient * gradient
            state[(q_key, a_key)] = (m, v, t)
            m_hat = m / (1 - BETA1 ** t)
            v_hat = v / (1 - BETA2 ** t)
            new = max(-1.0, min(1.0,
                                old + eta * m_hat
                                / (v_hat ** 0.5 + ADAM_EPS)))
            if new != old:
                registry.link(q_key, a_key, new, source="etalon")
                changed += 1
    return changed


def train_on_etalon(corpus, etalon_entries, parser,
                    eta: float = ETA_CONTRAST,
                    max_epochs: int = MAX_EPOCHS) -> dict:
    """4c: kontrastivní doladění na porušeních relativní marže.

    Učí se tam, kde správná odpověď kandiduje a nevede s marží —
    prohry (SLABÁ), tenké výhry (DOTAZ) i výhry těsně nad ε; přesně
    kategorie „signál existuje, jen má malý koeficient" z růstového
    zákona. NEPOKRYTÉ chyby se neučí (patří růstu os / dalším krokům).

    Nezodpověditelné otázky učí MLČENÍ (zadání J. 2026-08-04: odpověď
    = nemá odpověď): jejich vítěz se vede POD skóre správných odpovědí
    — hinge proti mediánu správných skóre epochy s touž relativní
    marží. Cíl je párový (rozdělení od sebe), žádná absolutní kotva:
    θ zůstává jen řez a kalibruje se na trénovací sadě, ne v učení.
    Bez zodpověditelných otázek v sadě se mlčení učit nemá proti čemu.
    """
    from cb_field.field import SentenceField
    # Zobecnění: 30 % otázek stranou, loss na nich řídí odvolání epochy
    # (J. 2026-08-04). Malá sada bez validační části se řídí tréninkovým
    # lossem jako dřív.
    train_entries, valid_entries = split_etalon(etalon_entries)
    stats = {"epoch": 0, "kroku": 0, "hran": 0, "epochy": [],
             "trenink": len(train_entries), "validace": len(valid_entries)}
    adam_state = {}                    # momenty (m, v, t) na hranu
    previous_watch = None
    answerable = [e for e in train_entries if e["zodpoveditelna"]]
    silent = [e for e in train_entries if not e["zodpoveditelna"]]
    from cb_field.matching import _fact_bags
    for epoch in range(max_epochs):
        snapshot = {(s, d): (w, src)
                    for s, d, w, src in corpus.registry.links()}
        corrections = 0
        loss_sum = 0.0
        correct_now = 0
        seen = 0
        train_hits = 0                 # věta s odpovědí mezi kandidáty
        correct_scores = []            # reference pro učení mlčení
        edges_before = stats["hran"]
        # Epocha běží nad pytli faktů zmraženými při jejím začátku
        # (targets); vazby se učí online a otázková strana je šíří
        # čerstvé. Bez zmražení stála přestavba pytlů celou epochu.
        _fact_bags(corpus)
        corpus._fact_cache_freeze = True
        for entry in answerable:
            question = SentenceField.from_text(
                entry["otazka"], parser, r=corpus.r,
                registry=corpus.registry)
            result = match(question, corpus)
            if not result.candidates:
                continue
            winner = result.best
            expected = entry["odpoved_lemma"]
            seen += 1
            if sentence_hit(result, expected):
                train_hits += 1        # úspěch posílení: věta v kandidátech
            correct = next((c for c in result.candidates
                            if c.token.lemma == expected), None)
            if correct is not None:
                correct_scores.append(correct.score)
            # Soupeř pro kontrast je nejlepší ŠPATNÝ kandidát — když
            # vítězí správná s malým odstupem (DOTAZ), je to druhý
            # v pořadí; kontrast proti vítězi by byl správná proti sobě
            # (prázdný rozdíl, žádné učení).
            rival = next((c for c in result.candidates
                          if c.token.lemma != expected), None)
            if winner.token.lemma == expected \
                    and result.outcome == "odpoved":
                correct_now += 1
            if correct is None or rival is None:
                continue                     # NEPOKRYTÁ — učení nepatří
            # Hinge s relativní marží: učí se KAŽDÉ porušení marže —
            # i správná výhra s tenkým odstupem (DOTAZ i odpoved těsně
            # nad ε). Splněná marže znamená nulový loss a žádný krok;
            # tím je „korekcí 0" skutečná konvergence, ne artefakt.
            margin = MARGIN_RATIO * abs(rival.score)
            loss = max(0.0, margin + rival.score - correct.score)
            loss_sum += loss
            if loss == 0.0:
                continue                     # marže splněna
            q_bag = _semantic_bag(question, range(len(question.tokens)))
            correct_bag = _semantic_bag(
                correct.sentence,
                _window_rows(correct.sentence, correct.center, corpus.r),
                center=correct.center)
            wrong_bag = _semantic_bag(
                rival.sentence,
                _window_rows(rival.sentence, rival.center, corpus.r),
                center=rival.center)
            stats["hran"] += contrastive_step(
                corpus.registry, q_bag, correct_bag, wrong_bag, eta,
                state=adam_state)
            corrections += 1

        # Učení mlčení: vítěz nezodpověditelné otázky se vede pod
        # medián správných skóre epochy (párový cíl, táž relativní
        # marže). Medián schválně — minimum by za referenci bralo
        # nejtěžší dosud nenaučený případ.
        quiet_now = 0
        quiet_seen = 0
        reference = (sorted(correct_scores)[len(correct_scores) // 2]
                     if correct_scores else None)
        if reference is not None:
            for entry in silent:
                question = SentenceField.from_text(
                    entry["otazka"], parser, r=corpus.r,
                    registry=corpus.registry)
                result = match(question, corpus)
                winner = result.best
                if winner is None:
                    continue
                quiet_seen += 1
                margin = MARGIN_RATIO * abs(reference)
                loss = max(0.0, margin + winner.score - reference)
                loss_sum += loss
                if loss == 0.0:
                    quiet_now += 1
                    continue                 # vítěz už je dost nízko
                q_bag = _semantic_bag(question,
                                      range(len(question.tokens)))
                winner_bag = _semantic_bag(
                    winner.sentence,
                    _window_rows(winner.sentence, winner.center,
                                 corpus.r),
                    center=winner.center)
                stats["hran"] += contrastive_step(
                    corpus.registry, q_bag, {}, winner_bag, eta,
                    state=adam_state)
                corrections += 1
        # Validační průchod (bez gradientu): loss a věta-v-kandidátech
        # na 30 % otázek, které učení nevidělo — měří ZOBECNĚNÍ.
        valid_loss_sum = 0.0
        valid_seen = 0
        valid_hits = 0
        valid_answerable = 0
        for entry in valid_entries:
            question = SentenceField.from_text(
                entry["otazka"], parser, r=corpus.r,
                registry=corpus.registry)
            result = match(question, corpus)
            if entry["zodpoveditelna"]:
                expected = entry["odpoved_lemma"]
                valid_answerable += 1
                if sentence_hit(result, expected):
                    valid_hits += 1
                correct = next((c for c in result.candidates
                                if c.token.lemma == expected), None)
                rival = next((c for c in result.candidates
                              if c.token.lemma != expected), None)
                if correct is None or rival is None:
                    continue
                valid_seen += 1
                margin = MARGIN_RATIO * abs(rival.score)
                valid_loss_sum += max(0.0,
                                      margin + rival.score - correct.score)
            elif reference is not None and result.best is not None:
                valid_seen += 1
                margin = MARGIN_RATIO * abs(reference)
                valid_loss_sum += max(0.0,
                                      margin + result.best.score
                                      - reference)
        corpus._fact_cache_freeze = False

        stats["epoch"] = epoch + 1
        stats["kroku"] += corrections
        loss = loss_sum / max(seen + quiet_seen, 1)
        valid_loss = (valid_loss_sum / max(valid_seen, 1)
                      if valid_entries else None)
        hit = correct_now / max(seen, 1)
        stats["epochy"].append(
            {"epocha": epoch + 1, "loss": round(loss, 3),
             "loss_valid": (round(valid_loss, 3)
                            if valid_loss is not None else None),
             "trefy": f"{correct_now}/{seen}", "trefy_podil": round(hit, 2),
             "veta_trenink": f"{train_hits}/{seen}",
             "veta_validace": f"{valid_hits}/{valid_answerable}",
             "ticho": f"{quiet_now}/{quiet_seen}",
             "korekci": corrections,
             "hran": stats["hran"] - edges_before})
        print(f"    epocha {epoch + 1}: loss {loss:7.3f} · valid "
              f"{'—' if valid_loss is None else format(valid_loss, '.3f')}"
              f" · věta T {train_hits}/{seen} · věta V "
              f"{valid_hits}/{valid_answerable} · trefy "
              f"{correct_now}/{seen} · ticho {quiet_now}/{quiet_seen} "
              f"· korekcí {corrections} "
              f"· hran {stats['hran'] - edges_before}", flush=True)
        if corrections == 0:
            break
        # Druhé kritérium konvergence: relativní marže nemusí být pro
        # všechny otázky splnitelná najednou (korekce nespadnou na 0)
        # a další epochy pak rozvracejí, co jiné otázky postavily —
        # naměřeno: U-křivka s minimem a divergencí dál. Epocha, která
        # zhoršila VALIDAČNÍ loss (zobecnění, J. 2026-08-04; bez
        # validační části tréninkový), se ODVOLÁ a trénink končí na
        # minimu, ne za ním.
        watch = valid_loss if valid_loss is not None else loss
        if previous_watch is not None and watch >= previous_watch:
            _restore_links(corpus.registry, snapshot)
            stats["epochy"][-1]["odvolana"] = True
            print(f"    epocha {epoch + 1} odvolána (validační loss "
                  f"se zhoršil) — vazby vráceny", flush=True)
            break
        previous_watch = watch
    return stats


def calibrate_theta(corpus, entries, parser) -> dict:
    """Kalibrace řezu θ na TRÉNOVACÍ sadě (splátka dluhu D2).

    Kandidáti řezu jsou středy mezi sousedními top-skóre; vybírá se θ
    maximalizující přesnost@1 + NEVÍM-správnost na trénovacích otázkách
    (obě složky rovným dílem — protiváha je součást kritéria, ne
    dodatek). Etalon do kalibrace nevstupuje.
    """
    from cb_field.field import SentenceField
    tops = []
    for entry in entries:
        question = SentenceField.from_text(entry["otazka"], parser,
                                           r=corpus.r,
                                           registry=corpus.registry)
        result = match(question, corpus, theta=float("-inf"), epsilon=0.0)
        if result.best is None:
            continue
        answerable = entry["zodpoveditelna"]
        tops.append((result.best.score, answerable,
                     answerable and result.best.token.lemma
                     == entry["odpoved_lemma"]))
    scores = sorted({score for score, _a, _c in tops})
    cuts = [scores[0] - 0.1] + [(a + b) / 2 for a, b
                                in zip(scores, scores[1:])] \
        + [scores[-1] + 0.1]
    n_answerable = sum(1 for _s, a, _c in tops if a)
    n_silent = len(tops) - n_answerable
    best = None
    for cut in cuts:
        accuracy = sum(1 for s, a, c in tops if a and c and s >= cut) \
            / max(n_answerable, 1)
        silence = sum(1 for s, a, _c in tops if not a and s < cut) \
            / max(n_silent, 1)
        merit = accuracy + silence
        if best is None or merit > best["merit"]:
            best = {"theta": round(cut, 3), "merit": round(merit, 3),
                    "presnost": round(accuracy, 2),
                    "mlceni": round(silence, 2)}
    best["otazek"] = len(tops)
    return best


def main() -> None:
    from cb_udpipe import UdpipeClient
    from cb_field.evaluate import (build_complex_corpus, build_corpus,
                                   evaluate_corpus, load_etalon,
                                   load_etalon_korpusy)

    import json
    korpusy = "korpusy" in sys.argv[1:]
    parser = UdpipeClient()
    if korpusy:
        corpus = build_complex_corpus(parser)
        etalon = load_etalon_korpusy()
        # Trénink a měření na ODDĚLENÝCH sadách: trénuje se na
        # parafrázích (otázka neopisuje větu — jinak se systém učí grep),
        # měří se na etalonu. Zapsaná mez z minula tím padá.
        trenink_path = (MODULE_DIR / "tests" / "data"
                        / "trenink-otazky-korpusy.jsonl")
        trenink = [json.loads(line) for line
                   in trenink_path.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    else:
        corpus = build_corpus(parser)
        etalon = load_etalon()
        trenink = etalon

    phases = []

    def measure(label, theta=None):
        counts, presnost, mlceni, _details = evaluate_corpus(
            corpus, etalon, parser, theta=theta)
        phases.append((label, presnost, mlceni, dict(counts)))
        print(f"{label:<28} přesnost@1 {presnost:.2f} · "
              f"NEVÍM-správnost {mlceni:.2f} · {counts}")

    measure("baseline (axiomy)")
    # 4b (Hebb) VYŘAZEN z přejímací cesty (rozhodl J. 2026-08-04):
    # nad surovými souvýskyty prokazatelně blokuje — korpusy 0,43 →
    # 0,17 a zvedá vstupní loss učení (0,87 vs 0,64). Mechanismus
    # hebb() zůstává; vrátí se až nad strukturou s prahem NPMI
    # odvozeným z dat (dluh D4, postup-krok4 § 15).
    train_stats = train_on_etalon(corpus, trenink, parser)
    print(f"4c kontrastivně: {train_stats}")
    measure("po 4c (etalon)")
    kalibrace = calibrate_theta(corpus, trenink, parser)
    print(f"kalibrace θ na trénovací sadě: θ={kalibrace['theta']} "
          f"(trénink: přesnost {kalibrace['presnost']} · mlčení "
          f"{kalibrace['mlceni']})")
    measure(f"po 4c, θ={kalibrace['theta']}", theta=kalibrace["theta"])

    corpus.registry.save(LEARNED_KORPUSY if korpusy else LEARNED)

    # Přejímka srovnává srovnatelné: baseline a stav po učení při TÉMŽ
    # výchozím θ. Fáze s kalibrovaným θ je provozní bod (jiný řez mění
    # směnu přesnost×mlčení záměrně), ne přejímací brána.
    baseline, final = phases[0], phases[1]
    protivaha_ok = final[2] >= baseline[2]
    verdict = ("PŘIJATO" if protivaha_ok and final[1] >= baseline[1]
               else "NEPŘIJATO — protiváha" if not protivaha_ok
               else "NEPŘIJATO — přesnost klesla")
    print(f"\nprotiváha (NEVÍM-správnost neklesla): "
          f"{'ano' if protivaha_ok else 'NE'} → {verdict}")

    lines = ["# Měření učení vah (4c kontrastivně + mlčení; 4b vyřazen)"
             + (" — komplexní korpusy" if korpusy else ""), ""]
    lines.append(f"- datum: {date.today().isoformat()} "
                 f"· η_kontrast={ETA_CONTRAST} · epochy≤{MAX_EPOCHS}")
    lines.append("- 4b (Hebb) vyřazen z přejímací cesty (J. 2026-08-04; "
                 "D4 — vrátí se až nad strukturou)")
    lines.append(f"- kontrastivně: epoch={train_stats['epoch']} "
                 f"kroků={train_stats['kroku']} hran={train_stats['hran']}")
    lines.append(f"- kalibrace θ na trénovací sadě (D2): "
                 f"θ={kalibrace['theta']} · trénink přesnost "
                 f"{kalibrace['presnost']} · mlčení {kalibrace['mlceni']}")
    lines.append("")
    lines.append("| epocha | loss (hinge marže) | trefy na tréninku "
                 "| ticho (nezodp.) | korekcí | nových/změněných hran |")
    lines.append("|---|---|---|---|---|---|")
    for e in train_stats.get("epochy", []):
        lines.append(f"| {e['epocha']} | {e['loss']} | {e['trefy']} "
                     f"({e['trefy_podil']}) | {e.get('ticho', '—')} "
                     f"| {e['korekci']} | {e['hran']} |")
    lines.append(f"- trénink: {len(trenink)} otázek · měření: "
                 f"{len(etalon)} otázek"
                 + (" (oddělené sady — parafráze vs. etalon)" if korpusy
                    else " (TÁŽ sada — horní odhad, ne generalizace)"))
    lines.append("")
    lines.append("| fáze | přesnost@1 | NEVÍM-správnost |")
    lines.append("|---|---|---|")
    for label, presnost, mlceni, _counts in phases:
        lines.append(f"| {label} | {presnost:.2f} | {mlceni:.2f} |")
    lines.append("")
    lines.append(f"Výrok protokolu: **{verdict}** (učení, které shodí "
                 f"NEVÍM-správnost, se nepřijímá — § 6 spec). Naučený "
                 f"registr: `data-persistent/verticals-learned.json`.")
    report_path = REPORT_KORPUSY if korpusy else REPORT
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"zapsáno: {report_path.relative_to(MODULE_DIR.parent)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
