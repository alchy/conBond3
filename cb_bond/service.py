"""`BondService` — jeden vstup do systému.

Dnes si každý skript pipeline skládá sám: načti korpusy, postav pole,
postav graf, vytěž vztahy, udělej matcher. Osm skriptů to dělá osmkrát
a pokaždé o kousek jinak — a rozdíl v naměřeném čísle se pak nedá
přiřknout ani datům, ani kódu.

Fasáda z toho dělá jedno místo. Vrací **slovníky**, ne objekty modulu:
totéž pak jde do REST odpovědi i do logu, aniž by se to muselo cestou
překládat. Objekty (`Reply`, `MatchResult`) zůstávají uvnitř.

## Proč `state()` a ne osm getterů

`state()` je jediný zdroj čísel pro `status`, viewBase i log. Kdyby si
je každé místo počítalo samo, rozešla by se — a nikdo by rozdíl nehledal
v tom, že se totéž měří dvakrát jinak. `build()` proto vrací tentýž
slovník, ne svůj vlastní.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from cb_bond.graph import KnowledgeGraph
from cb_field.corpusfile import build_corpus

#: Klíče stavu, které existují i před stavbou. Zbytek je `None`, dokud
#: se nepostaví — nepostavená služba čísla NEVYMÝŠLÍ, protože „0 hran"
#: a „nevím" jsou dvě různé věci a jen jedna z nich je chyba.
_PRAZDNY_STAV = {
    "built": False,
    "sentences": None,
    "files": None,
    "edges": None,
    "lemmas": None,
    "nodes": None,
    "degree": None,
    "axes": None,
    "custom_axes": None,
    "axis_version": None,
    "links": None,
    "link_version": None,
}


class BondService:
    """Sestavený systém: korpus, graf, párování, dialog.

    Vstup:
        config: načtená konfigurace (`cb_bond.config.load`). Bere se
            hotová zvenčí, ne že si ji fasáda načte sama — jinak by test
            neměl jak ukázat jinam než na provozní data.
        parser: klient rozboru (`cb_udpipe.UdpipeClient` nebo atrapa).
            Předává se, protože služba nemá určovat, kde parser běží;
            adresa je v konfiguraci volajícího (§ 3 politiky).
        log: klient loggeru, nebo `None`. Nepovinná závislost — bez něj
            systém funguje, jen tišeji (§ 9).
        verbose: hlásit průběh i na konzoli. Zapnuto schválně (rozhodnutí
            J.: člověk má vidět, co se děje a proč). Testy si to vypínají,
            aby výstup sady zůstal čistý — hlášky uprostřed teček skryjí
            skutečnou chybu.
    """

    def __init__(self, config: dict, parser, log=None, *,
                 verbose: bool = True) -> None:
        self.config = config
        self.parser = parser
        self.log = log
        self.verbose = verbose
        self.corpus = None
        self.graph = None
        self.logic = None
        self._files: tuple[Path, ...] = ()
        self._matcher = None
        self._responder = None

    # --- stavba ---------------------------------------------------------

    def corpus_paths(self) -> tuple[Path, ...]:
        """Soubory korpusu podle konfigurace, seřazené.

        Řazení není kosmetika: pořadí souborů určuje pozice vět a ty
        stojí ve zmražených hodnotách přejímek.
        """
        modul = self.config["module"]["corpus"]
        adresar = Path(modul["directory"])
        nalezene: list[Path] = []
        for vzor in modul["patterns"]:
            nalezene.extend(adresar.glob(vzor))
        return tuple(sorted(set(nalezene)))

    def build(self) -> dict[str, Any]:
        """Postaví korpus a graf; vrátí tentýž slovník jako `state()`.

        Je to drahé (2 912 vět ≈ 5 s, 12 258 ≈ 23 s), takže se to dělá
        jednou při startu služby, ne při dotazu. To je hlavní důvod, proč
        z toho vůbec služba je.

        Při chybě:
            `FileNotFoundError`, když korpusový adresář nic nedá. Mlčky
            postavit prázdný systém by znamenalo službu, která na všechno
            odpoví „nevím" a tváří se zdravě.
        """
        cesty = self.corpus_paths()
        if not cesty:
            adresar = self.config["module"]["corpus"]["directory"]
            raise FileNotFoundError(
                f"korpusový adresář {adresar} nedal žádný soubor "
                f"(vzory {self.config['module']['corpus']['patterns']}); "
                f"prázdný systém by na všechno odpověděl „nevím\" a "
                f"tvářil se zdravě")

        modul = self.config["module"]["corpus"]
        # Začátek práce jde na `debug` — je to vnitřek metody. Na `info`
        # by potřeboval `result`, a žádný by nebyl pravdivý: „skipped"
        # znamená, že se práce přeskočila, což se nestalo.
        self._oznam(f"stavím korpus z {len(cesty)} souborů…",
                    method="build", result="ok", level="debug")
        self.corpus = build_corpus(cesty, self.parser,
                                   r=modul["radius"],
                                   r_sentences=modul["sentence_radius"])
        self._files = cesty

        self.graph = KnowledgeGraph()
        for pole in self.corpus:
            self.graph.add_sentence(pole)
        self.invalidate()

        # Formální vrstva stojí VEDLE retrieval cesty; bez konfigurace
        # (testovací fixtury) služba běží jako dřív a `logic` je None.
        nastaveni_logiky = self.config["module"].get("logic")
        if nastaveni_logiky is not None:
            from cb_bond.logic import LogicBridge
            self.logic = LogicBridge(self.parser,
                                     nastaveni_logiky["kb_file"])

        stav = self.state()
        self._oznam(f"postaveno: {stav['sentences']} vět · "
                    f"{stav['edges']} hran · {stav['axes']} os",
                    method="build", result="ok", output=stav)
        return stav

    # --- dotaz ----------------------------------------------------------

    def ask(self, text: str, *, top: int | None = None) -> dict[str, Any]:
        """Otázka → odpověď, rozklad skóre a kandidátní věty.

        Vstup:
            text: otázka v češtině.
            top: kolik kandidátních vět vrátit; `None` bere z konfigurace.

        Výstup:
            Slovník s odpovědí (`answer`, `outcome`), **rozkladem skóre**
            (`decomposition` — pojmenované členy, jejichž součet dá
            `score`), kandidátními větami v konvenci viewBase2
            (`[slovo] Věta`) a osami otázky s jejich pokrytím.

            Rozklad je součást odpovědi, ne příloha: bez něj by člověk
            viděl výsledek a neměl jak poznat, čím vznikl (princip 6).

        Při chybě:
            `RuntimeError`, když systém není postavený. Odpovídat
            z prázdné hlavy by znamenalo „nevím" na všechno a tvářit
            se přitom zdravě.
        """
        if self.corpus is None or self.graph is None:
            raise RuntimeError(
                "systém není postavený — nejdřív build(); odpovídat "
                "z prázdné hlavy by znamenalo „nevím\" na všechno")

        nastaveni = self.config["module"]["matching"]
        kolik = top if top is not None else nastaveni["top_sentences"]
        otazka = self._pole_otazky(text)
        odpovidac = self.responder()

        odpoved = odpovidac.reply(otazka)
        vysledek = self.matcher().match(otazka)
        pokryti = self.matcher().coverage(otazka)

        vystup = {
            "question": text,
            "answer": odpoved.lemma,
            "outcome": odpoved.outcome,
            "missing": list(odpoved.missing),
            "score": float(vysledek.best.score) if vysledek.best else 0.0,
            "decomposition": ({klic: float(hodnota) for klic, hodnota
                               in vysledek.best.decomposition().items()}
                              if vysledek.best else {}),
            "sentences": self._kandidatni_vety(vysledek, kolik),
            "axes": [{"axis": osa, "coverage": float(hodnota)}
                     for osa, hodnota in pokryti.items()],
            "logic": (self.logic.ask(text)
                      if self.logic is not None else None),
        }
        self._oznam(
            f"otázka {text!r} → {vystup['answer']!r} ({vystup['outcome']})",
            method="ask", result="ok" if odpoved.lemma else "empty",
            output={"answer": vystup["answer"],
                    "outcome": vystup["outcome"],
                    "score": vystup["score"]})
        return vystup

    def context(self, text: str) -> dict[str, Any]:
        """Přidá větu od člověka do korpusu i grafu; vrátí nový stav.

        Žádná zvláštní cesta pro dialogová data: táž stavba pole, týž
        registr, týž graf. Liší se jen **zdroj hrany**, aby šlo poznat,
        odkud fakt přišel — jinak by po týdnu nikdo nevěděl, co je
        z korpusu a co dopsal člověk.

        Při chybě:
            `RuntimeError`, když systém není postavený.
        """
        if self.corpus is None or self.graph is None:
            raise RuntimeError(
                "systém není postavený — nejdřív build()")

        pred = self.state()
        self.responder().append_context(text, self.parser)
        # Párovač drží pytle vět nad starým korpusem. Bez zneplatnění by
        # nová věta v odpovědi nebyla vidět a vypadalo by to jako chyba
        # párování, ne jako zapomenutá invalidace.
        self.invalidate()
        stav = self.state()
        # Přírůstek, ne celek: dialog o dálnici se popisuje jako „+9 hran"
        # a celek se znaménkem plus by znamenal něco úplně jiného.
        stav["added_sentences"] = stav["sentences"] - pred["sentences"]
        stav["added_edges"] = stav["edges"] - pred["edges"]
        stav["logic"] = (self.logic.context(text)
                         if self.logic is not None else None)
        self._oznam(f"kontext: {text!r} → korpus {stav['sentences']} vět "
                    f"(+{stav['added_sentences']}) · "
                    f"graf +{stav['added_edges']} hran",
                    method="context", result="ok", output=stav)
        return stav

    def _kandidatni_vety(self, vysledek, kolik: int) -> list[dict[str, Any]]:
        """Kandidátní věty v konvenci viewBase2 — `[slovo] Věta`.

        Věta se bere podle **nejlepšího** kandidáta v ní, ne podle
        prvního nalezeného: v okně má stát to slovo, kvůli kterému se
        věta dostala nahoru.
        """
        nejlepsi: dict[int, Any] = {}
        for kandidat in vysledek.candidates:
            drzitel = nejlepsi.get(kandidat.sentence)
            if drzitel is None or kandidat.score > drzitel.score:
                nejlepsi[kandidat.sentence] = kandidat

        poradi = sorted(nejlepsi.values(), key=lambda k: -k.score)[:kolik]
        return [{"position": k.sentence,
                 "lemma": k.lemma,
                 "score": float(k.score),
                 "text": self.corpus[k.sentence].source,
                 "decomposition": {klic: float(hodnota) for klic, hodnota
                                   in k.decomposition().items()}}
                for k in poradi]

    def teach_pattern(self, lemma: str, operation: str, *,
                      learned_from: str = "") -> dict[str, Any]:
        """Naučí jazykový vzor operátoru (LANGUAGE_LEARNING.md).

        Při chybě: `RuntimeError`, když formální vrstva neběží — učit vzor
        do neexistující vrstvy by bylo tiché nedorozumění.
        """
        if self.logic is None:
            raise RuntimeError("formální vrstva neběží (chybí module.logic)")
        vysledek = self.logic.teach_pattern(lemma, operation,
                                            learned_from=learned_from)
        self._oznam(f"naučen vzor {lemma!r} → {operation}",
                    method="teach_pattern", result="ok", output=vysledek)
        return vysledek

    def forget_word(self, lemma: str) -> dict[str, Any]:
        """Odvolá jazykový vzor slova; formální operace zůstává."""
        if self.logic is None:
            raise RuntimeError("formální vrstva neběží (chybí module.logic)")
        vysledek = self.logic.forget_word(lemma)
        self._oznam(f"odvolán vzor {lemma!r}",
                    method="forget_word", result="ok", output=vysledek)
        return vysledek

    def resolve_reference(self, choice: str) -> dict[str, Any]:
        """Dokončí poslední doptání formální vrstvy na referenci (§ 5)."""
        if self.logic is None:
            raise RuntimeError("formální vrstva neběží (chybí module.logic)")
        vysledek = self.logic.resolve_reference(choice)
        self._oznam(f"reference rozřešena: {choice} → "
                    f"{vysledek.get('answer') or vysledek['kind']}",
                    method="resolve_reference", result="ok",
                    output=vysledek)
        return vysledek

    def _pole_otazky(self, text: str):
        """Otázka jako pole nad TÝMŽ registrem jako korpus.

        Vlastní registr by znamenal jiné šířky matic a osy, které se
        nemají kde potkat — otázka by se ptala do prázdna.
        """
        from cb_field import SentenceField
        return SentenceField.from_text(
            text, self.parser,
            r=self.config["module"]["corpus"]["radius"],
            registry=self.corpus.registry)

    # --- díly systému (staví se při první potřebě) ----------------------

    def matcher(self):
        """Párovač s pákami z konfigurace.

        Staví se jednou a drží: `Matcher` si při první otázce postaví
        pytle vět nad celým korpusem, což je drahé. Znovu se postaví
        až tehdy, když se korpus změní (dialogem) — o tom rozhoduje
        `invalidate()`.
        """
        if self._matcher is None:
            from cb_bond.matcher import Matcher, ScoreWeights
            from cb_bond.recall import GraphRecall
            nastaveni = self.config["module"]["matching"]
            self._matcher = Matcher(
                self.corpus,
                spread_depth=nastaveni["spread_depth"],
                weights=ScoreWeights(**nastaveni["weights"]),
                theta=nastaveni["theta"],
                epsilon=nastaveni["epsilon"],
                top_k=nastaveni["top_k"],
                spectral_k=nastaveni["spectral_k"],
                graph_recall=GraphRecall(
                    self.graph, self.corpus,
                    depth=nastaveni["graph_recall_depth"]))
        return self._matcher

    def responder(self):
        """Dialogová vrstva nad párováním a grafem."""
        if self._responder is None:
            from cb_bond.dialog import Responder
            self._responder = Responder(self.matcher(), self.graph)
        return self._responder

    def invalidate(self) -> None:
        """Zahodí postavené díly — korpus se změnil.

        Volá se po přidání věty dialogem. Bez toho by párovač počítal
        nad starými pytli a nová věta by v odpovědi nebyla vidět, což
        vypadá jako chyba párování, ne jako zapomenutá invalidace.
        """
        self._matcher = None
        self._responder = None

    # --- co o sobě služba ví --------------------------------------------

    def state(self) -> dict[str, Any]:
        """Čísla, která uvidí člověk ve `status`, viewBase i v logu.

        Výstup:
            Slovník **celý JSONovatelný** — jde rovnou do REST odpovědi
            i do logu. Objekt modulu by tam spadl až u klienta, tedy
            daleko od příčiny.

            Před stavbou jsou obsahová čísla `None`, ne nuly: „nevím" a
            „nic tam není" jsou dvě různé věci a jen jedna je chyba.
        """
        modul = self.config["module"]
        stav: dict[str, Any] = dict(_PRAZDNY_STAV)
        stav.update(
            corpus_dir=str(modul["corpus"]["directory"]),
            patterns=list(modul["corpus"]["patterns"]),
            data_root=str(modul.get("data_root", "?")),
            config_fingerprint=self.config.get("_meta", {}).get(
                "fingerprint", "?"),
        )
        if self.corpus is None or self.graph is None:
            return stav

        statistiky = self.graph.statistics()
        hran = len(self.graph.edges())
        # Lemmata, ne uzly: `NOUN:vedení` a `VERB:vedení` jsou dva uzly,
        # ale jedno lemma. Přejímka § 6 zmrazila 5 695 LEMMAT — kdyby se
        # tady počítaly uzly, stálo by pod tímtéž jménem 5 727 a nikdo by
        # ten rozdíl nehledal v definici.
        lemmata = {klic.split(":", 1)[1] for klic in statistiky}
        lemmat = len(lemmata)
        registr = self.corpus.registry
        stav.update(
            built=True,
            sentences=len(self.corpus),
            files=len(self._files),
            edges=hran,
            lemmas=lemmat,
            nodes=len(statistiky),
            # Průměrný stupeň: každá hrana se dotýká DVOU uzlů, proto
            # dvojka. Zaokrouhleno na desetinu — přesnější číslo předstírá
            # přesnost, kterou průměr přes tisíce uzlů nemá. Vzorec je
            # tentýž jako v přejímce § 6, aby se čísla dala porovnat.
            degree=round(2 * hran / lemmat, 1) if lemmat else 0.0,
            axes=len(registr),
            custom_axes=len(registr.custom_axes),
            axis_version=registr.axis_version,
            links=len(registr.links()),
            link_version=registr.link_version,
        )
        return stav

    def health(self) -> dict[str, Any]:
        """Stav pro `GET /v1/health` a pro `status`.

        Rozlišuje **„běžím"** od **„umím odpovídat"**. Nepostavená služba
        je `degraded`, ne `ok`: port odpovídá, ale v hlavě nic není, a
        kdyby se tvářila zdravě, poznalo by se to až prvním dotazem —
        daleko od příčiny (§ 9 politiky).
        """
        stav = self.state()
        return {
            "status": "ok" if stav["built"] else "degraded",
            "built": stav["built"],
            "sentences": stav["sentences"],
            "edges": stav["edges"],
            "lemmas": stav["lemmas"],
            "reason": None if stav["built"] else "korpus není postavený",
        }

    # --- pomocné --------------------------------------------------------

    def _oznam(self, zprava: str, *, method: str, result: str,
               output: dict | None = None, level: str = "info") -> None:
        """Hlasitě na obě strany — do loggeru i na konzoli.

        Rozhodnutí J.: člověk má vidět, co se děje a proč, i když zrovna
        nečte log. Logger je nepovinný, konzole ne.

        Vstup:
            method, result: **jméno metody a výsledek, ne hláška.** Souhrn
                se počítá podle komponenta × metoda × result; kdyby
                v `method` skončil text zprávy, byl by každý záznam
                vlastní řádek a čísla by ztratila smysl.
            output: čísla k záznamu. Do logu jde totéž, co do `status` —
                jinak by se dvě cesty k témuž číslu rozešly.
            level: `info` je hranice komponenty (metoda doběhla), `debug`
                její vnitřek (postup uvnitř). Průběžné hlášky patří na
                `debug`, jinak by souhrn počítal jednu práci vícekrát.

        Při chybě:
            Nevyhazuje. Padlé logovátko nesmí shodit modul: byla by
            nejméně důležitá součást zároveň nejkřehčí (§ 4).
        """
        if self.verbose:
            print(f"           {zprava}", flush=True)
        if self.log is None:
            return
        try:
            zapis = self.log.debug if level == "debug" else self.log.info
            zapis(method=method, result=result, message=zprava,
                  output=output)
        except Exception as e:                # noqa: BLE001
            print(f"           log se nezapsal ({e})", file=sys.stderr,
                  flush=True)
