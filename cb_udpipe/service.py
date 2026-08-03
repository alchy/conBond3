"""Doménová logika modulu: čtyři fáze rozboru.

Nezná HTTP, nezná cesty k souborům mimo konfiguraci a testuje se přímo, bez
spuštěné služby (README-MODULES.md § 1).

```
1 · SEGMENTACE     UDPipe s `tokenizer` — síť se nenačte, je to levné
    a hrubá        → věty s `# text`, ze kterého vzejde klíč cache
    tokenizace

2 · OPRAVA         naše pravidla (tokenize.py)
    tokenizace     → 23. místo 23 | . ; R.U.R. místo šesti tokenů

3 · CACHE          klíč = (text věty, model, verze tokenizéru)
                   HIT  → tokeny z disku
                   MISS → do fronty

4 · DOROZBOR       UDPipe s `tagger` a `parser`, BEZ `tokenizer`
                   → server čte vstup jako CoNLL-U a segmentaci nemění
```

Fázi 1 nelze přeskočit ani při plném zásahu cache: segmentaci dělá UDPipe,
takže bez ní není známo, na které věty se cache vůbec ptát.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from cb_udpipe import cache as cache_modul
from cb_udpipe import conllu, tokenize, upstream as upstream_modul
from cb_udpipe.conllu import Multiword, Sentence, Token

#: Důvod, se kterým se přeskakuje věta delší než mez serveru. Je to typovaná
#: hodnota, ne volný text: počítá se v souhrnu a filtruje se podle ní v logu.
REASON_TOO_LONG = "sentence_too_long"


@dataclass(frozen=True)
class ParsedSentence:
    """Jedna rozebraná věta i s tím, odkud se vzala.

    `from_cache` je tam schválně: bez něj by nešlo změřit podíl zásahů jinak
    než dopočítáváním ze souhrnu, a spotřeba signálu se má měřit tam, kde
    vzniká (návrh, kap. 30).
    """

    source: str
    tokens: tuple[Token, ...]
    multiword: tuple[Multiword, ...] = ()
    from_cache: bool = False
    retokenized: int = 0


@dataclass(frozen=True)
class ParseResult:
    """Výsledek jednoho volání `parse`."""

    sentences: tuple[ParsedSentence, ...] = ()
    cached: int = 0
    parsed: int = 0
    skipped: tuple[dict[str, Any], ...] = ()


@dataclass
class _Souhrn:
    """Počty podle metody a výsledku pro `GET /v1/summary`.

    Rozložení `ok / empty / skipped / error` je nejlevnější zdravotní ukazatel,
    jaký systém má, a plyne z logu zadarmo (README-MODULES.md § 11).
    """

    podle_metody: dict[str, dict[str, int]] = field(default_factory=dict)

    def pricti(self, method: str, result: str, kolik: int = 1) -> None:
        self.podle_metody.setdefault(method, {}).setdefault(result, 0)
        self.podle_metody[method][result] += kolik

    def snimek(self) -> dict[str, dict[str, int]]:
        return {m: dict(v) for m, v in self.podle_metody.items()}


class UdpipeService:
    """Rozbor vět s cache. Jádro modulu.

    Instance drží otevřenou cache, takže se musí `close()`. Dvě instance nad
    týmž adresářem cache znamenají ztrátu dat; brání tomu PID soubor služby
    jako zámek (README-MODULES.md § 8).
    """

    def __init__(self, config: dict[str, Any], *,
                 upstream: Any = None,
                 log: Any = None,
                 clock: Callable[[], str] | None = None):
        """Vstup:
            config: konfigurace z `config.load()`.
            upstream: klient UDPipe. `None` znamená postavit ho z konfigurace;
                testy si sem podstrčí vlastní a běží pak bez UDPipe.
            log: `LogClient`, nebo `None`. Logovátko je nepovinná závislost.
            clock: funkce vracející čas v ISO 8601. Předává se, aby šla cache
                deterministicky otestovat — funkce, která si sama zavolá
                `time.time()`, se testovat nedá (README-MODULES.md § 3).
        """
        self.config = config
        self.log = log
        self._clock = clock if clock is not None else _ted
        modul = config["module"]

        self.rules = tokenize.Rules.from_config(config)
        self.tokenizer_version = tokenize.fingerprint(self.rules)
        self.max_sentence_words = modul["tokenizer"]["max_sentence_words"]
        self.batch_sentences = modul["cache"]["batch_sentences"]
        self.log_objects = modul["log_objects"]

        self.upstream = (upstream if upstream is not None
                         else _upstream_z_konfigurace(config, log))
        self.cache = cache_modul.Cache(
            directory=modul["cache"]["dir"],
            model=modul["upstream"]["model"],
            tokenizer=self.tokenizer_version,
        )
        self._souhrn = _Souhrn()

    # ------------------------------------------------------------- rozbor

    def parse(self, text: str, *, trace: str | None = None) -> ParseResult:
        """Rozebere text a vrátí věty s tokeny.

        Vstup:
            text: jedna nebo víc vět. Segmentaci určuje UDPipe.
            trace: identifikátor průchodu. Modul ho **nikdy nerazí**, jen
                přebírá — kdyby si ho razil každý modul, rozpadl by se řetěz
                na tolik kusů, kolik je modulů, a to je horší než žádná stopa.

        Výstup:
            `ParseResult` s větami v pořadí vstupu, s počty zásahů a rozborů
            a se seznamem přeskočených vět i s důvodem. Prázdný vstup dá
            prázdný výsledek — **není to chyba** (INV-9).

        Při chybě:
            `UpstreamUnavailable`, když UDPipe neběží; `UpstreamError` na jeho
            ostatní chyby. Nikdy prázdný výsledek místo chyby — ten by se slil
            s platným prázdným rozborem.
        """
        zacatek = time.monotonic()

        try:
            vety = self._segmentuj(text, trace)
        except Exception as e:
            self._zaloguj("parse", trace, result="error", message=str(e),
                          vstup={"chars": len(text)})
            self._souhrn.pricti("parse", "error")
            raise

        if not vety:
            self._zaloguj("parse", trace, result="empty",
                          vstup={"chars": len(text)},
                          vystup={"sentences": 0})
            self._souhrn.pricti("parse", "empty")
            return ParseResult()

        opravene = self._oprav_tokenizaci(vety, trace)
        zasahy, k_rozboru, preskocene = self._roztrid(opravene)

        try:
            rozebrane = self._dorozbor(
                {i: opravene[i][0] for i in k_rozboru}, trace
            )
        except Exception as e:
            self._zaloguj("parse", trace, result="error", message=str(e),
                          vstup={"chars": len(text)})
            self._souhrn.pricti("parse", "error")
            raise

        vysledek = self._slozit(opravene, zasahy, rozebrane, preskocene)
        self._souhrn.pricti("parse", "ok")
        self._zaloguj(
            "parse", trace, result="ok",
            vstup={"chars": len(text), "sentences": len(vety)},
            vystup={"sentences": len(vysledek.sentences),
                    "cached": vysledek.cached, "parsed": vysledek.parsed,
                    "skipped": len(vysledek.skipped)},
            duration_ms=int((time.monotonic() - zacatek) * 1000),
        )
        return vysledek

    def tokenize_only(self, text: str, *,
                      trace: str | None = None) -> list[Sentence]:
        """Jen segmentace a tokenizace, bez tagů.

        Levné volání: síť se nenačte. Hodí se, když volajícího zajímají jen
        hranice vět nebo tokenů.

        Do cache **nezapisuje**: tokenizace bez tagů není rozbor a uložit ji
        by znamenalo, že příští zásah vrátí věty bez značek.

        Vstup:
            text: jedna nebo víc vět.
            trace: identifikátor průchodu.

        Výstup:
            Věty s opravenou tokenizací a prázdnými sloupci tagů.

        Při chybě:
            `UpstreamUnavailable` nebo `UpstreamError`.
        """
        vety = self._segmentuj(text, trace)
        opravene = [v for v, _ in self._oprav_tokenizaci(vety, trace)]
        self._souhrn.pricti("tokenize_only", "ok" if opravene else "empty")
        return opravene

    # -------------------------------------------------------------- fáze

    def _segmentuj(self, text: str, trace: str | None) -> list[Sentence]:
        """Fáze 1: text → věty s hrubou tokenizací."""
        if not text.strip():
            return []
        return conllu.parse(self.upstream.tokenize(text, trace=trace))

    def _oprav_tokenizaci(self, vety: Sequence[Sentence],
                          trace: str | None) -> list[tuple[Sentence, int]]:
        """Fáze 2: naše pravidla. Vrací dvojice (věta, počet sloučení)."""
        vysledek = []
        celkem = 0
        for v in vety:
            nova, n = tokenize.retokenize(v, self.rules)
            vysledek.append((nova, n))
            celkem += n
        if celkem:
            self._zaloguj("retokenize", trace, result="ok",
                          vstup={"sentences": len(vety)},
                          vystup={"merges": celkem})
        return vysledek

    def _roztrid(self, opravene: Sequence[tuple[Sentence, int]]
                 ) -> tuple[dict[int, Sentence], list[int],
                            list[dict[str, Any]]]:
        """Fáze 3: rozdělí věty na zásahy cache, věty k rozboru a přeskočené.

        Věta přes mez serveru se vyjme **před** odesláním. Kdyby šla s dávkou,
        server by vrátil chybu na celou dávku kvůli jedné větě.

        Výstup:
            Trojice (index → věta z cache, indexy k rozboru, přeskočené).
        """
        zasahy: dict[int, Sentence] = {}
        k_rozboru: list[int] = []
        preskocene: list[dict[str, Any]] = []

        for i, (veta, _) in enumerate(opravene):
            if len(veta.tokens) > self.max_sentence_words:
                preskocene.append({
                    "source": veta.source[:200],
                    "reason": REASON_TOO_LONG,
                    "words": len(veta.tokens),
                    "limit": self.max_sentence_words,
                })
                continue
            z_cache = self.cache.get(veta.source)
            if z_cache is not None:
                zasahy[i] = z_cache
            else:
                k_rozboru.append(i)
        return zasahy, k_rozboru, preskocene

    def _dorozbor(self, vety: dict[int, Sentence],
                  trace: str | None) -> dict[int, Sentence]:
        """Fáze 4: pošle chybějící věty k dorozboru, po dávkách.

        Věty se párují podle `sent_id`, do kterého se dá **index ve vstupu**.
        Pořadí by stačilo taky, ale jistota zadarmo je lepší než jistota
        z úvahy — a ověřeno je, že `sent_id` cestu tam a zpět přežije
        (koncepce, § 13.4).

        Vstup:
            vety: index ve vstupu → věta k rozboru.
            trace: identifikátor průchodu.

        Výstup:
            Index ve vstupu → rozebraná věta.

        Při chybě:
            Propouští výjimky upstreamu — rozbor, který se nepovedl, nesmí
            skončit jako prázdný výsledek.
        """
        vysledek: dict[int, Sentence] = {}
        for davka in _po_davkach(sorted(vety), self.batch_sentences):
            k_odeslani = [
                Sentence(source=vety[i].source, tokens=vety[i].tokens,
                         multiword=vety[i].multiword, sent_id=str(i))
                for i in davka
            ]
            odpoved = self.upstream.tag_and_parse(
                conllu.write(k_odeslani), trace=trace
            )
            for veta in conllu.parse(odpoved):
                if veta.sent_id is not None and veta.sent_id.isdecimal():
                    vysledek[int(veta.sent_id)] = veta
        return vysledek

    def _slozit(self, opravene: Sequence[tuple[Sentence, int]],
                zasahy: dict[int, Sentence],
                rozebrane: dict[int, Sentence],
                preskocene: list[dict[str, Any]]) -> ParseResult:
        """Fáze 5: složí výsledek v pořadí vstupu a zapíše nové věty do cache."""
        ts = self._clock()
        vysledek: list[ParsedSentence] = []

        for i, (puvodni, zasahu) in enumerate(opravene):
            z_cache = zasahy.get(i)
            hotova = z_cache if z_cache is not None else rozebrane.get(i)
            if hotova is None:
                continue                # přeskočená věta
            if z_cache is None:
                self.cache.put(hotova, ts=ts)
                self._zaloguj_objekt(hotova, zasahu)
            elif self.log_objects == "all":
                self._zaloguj_objekt(hotova, zasahu)
            vysledek.append(ParsedSentence(
                source=hotova.source,
                tokens=hotova.tokens,
                multiword=hotova.multiword,
                from_cache=z_cache is not None,
                retokenized=zasahu,
            ))

        if preskocene:
            self._souhrn.pricti("parse", "skipped", len(preskocene))

        return ParseResult(
            sentences=tuple(vysledek),
            cached=len(zasahy),
            parsed=len(rozebrane),
            skipped=tuple(preskocene),
        )

    # ------------------------------------------------------------- stav

    def summary(self) -> dict[str, Any]:
        """Počty podle metody a výsledku plus stav cache.

        Podíl `empty` **není chybovost** — u některých vstupů je prázdný
        výsledek správný. Chybovost je podíl `error` (README-MODULES.md § 11).
        """
        return {**self._souhrn.snimek(), "cache": self.cache.stats()}

    def health(self) -> dict[str, Any]:
        """Stav služby pro `GET /v1/health` a pro `status`.

        UDPipe je **povinná** závislost, takže jeho výpadek znamená
        `degraded`, ne `ok` — a musí to být vidět dřív, než na to narazí
        první dotaz (README-MODULES.md § 9).
        """
        dostupny, duvod = True, None
        try:
            self.upstream.models()
        except Exception as e:
            dostupny, duvod = False, str(e)

        return {
            "status": "ok" if dostupny else "degraded",
            "upstream": {
                "available": dostupny,
                "endpoint": getattr(self.upstream, "endpoint", None),
                "model": self.config["module"]["upstream"]["model"],
                "reason": duvod,
            },
            "tokenizer": self.tokenizer_version,
            "cache": self.cache.stats(),
            "config": self.config.get("_meta", {}).get("fingerprint"),
        }

    def close(self) -> None:
        """Zavře cache. Volá se při ukončení služby."""
        self.cache.close()

    # ------------------------------------------------------------- log

    def _zaloguj(self, method: str, trace: str | None, *, result: str,
                 vstup: dict[str, Any] | None = None,
                 vystup: dict[str, Any] | None = None,
                 message: str | None = None,
                 duration_ms: int | None = None) -> None:
        """Zapíše textový záznam, pokud je logovátko k dispozici.

        Nedostupné ani rozbité logovátko **nesmí shodit modul**: je to
        nepovinná závislost a její výpadek znamená degradaci
        (README-MODULES.md § 9). Kdyby padlé logovátko shodilo systém, byla by
        nejméně důležitá součást zároveň nejkřehčí.
        """
        if self.log is None:
            return
        udaje: dict[str, Any] = {"method": method, "trace": trace,
                                 "result": result}
        for jmeno, hodnota in (("input", vstup), ("output", vystup),
                               ("message", message),
                               ("duration_ms", duration_ms)):
            if hodnota is not None:
                udaje[jmeno] = hodnota
        try:
            self.log.info(**udaje)
        except Exception:
            # Vědomá výjimka ze zákazu `except: pass` (§ 9 politiky): tohle
            # JE ta obsluha chyby. Zapsat ji nejde — zapisovač je právě to,
            # co selhalo.
            pass

    def _zaloguj_objekt(self, veta: Sentence, zasahu: int) -> None:
        """Zapíše celý rozbor do objektového kukátka podle nastavení.

        Výchozí `miss` loguje jen věty, které se skutečně rozebíraly:
        logovat cache zásah jako objekt znamená psát podruhé to, co už
        v cache leží (koncepce, § 10).
        """
        if self.log is None or self.log_objects == "off":
            return
        if self.log_objects == "retokenized" and not zasahu:
            return
        try:
            self.log.json(
                method="parse", label="rozbor věty", kind="parse",
                obj={
                    "source": veta.source,
                    "retokenized": zasahu,
                    "tokens": [
                        {"id": t.id, "form": t.form, "lemma": t.lemma,
                         "upos": t.upos, "feats": t.feats,
                         "head": t.head, "deprel": t.deprel}
                        for t in veta.tokens
                    ],
                },
            )
        except Exception:
            pass


def _po_davkach(polozky: Sequence[int], velikost: int) -> Iterable[list[int]]:
    """Rozdělí položky na dávky dané velikosti.

    Dávkuje se proto, že jedno volání na celý článek je pro UDPipe moc
    a jedno na větu zbytečně pomalé (conBond2, `Prijem.rozebrat`).
    """
    for i in range(0, len(polozky), velikost):
        yield list(polozky[i:i + velikost])


def _upstream_z_konfigurace(config: dict[str, Any], log: Any):
    """Postaví klienta UDPipe z konfigurace.

    Adresa se předává, ne hledá: modul se nikoho neptá, kde služba běží —
    dostal to v nastavení (README-MODULES.md § 4).
    """
    u = config["module"]["upstream"]
    return upstream_modul.Upstream(
        endpoint=f"http://{u['host']}:{u['port']}",
        timeout_s=u["request_timeout_s"],
        log=log,
    )


def _ted() -> str:
    """Aktuální čas v ISO 8601 s Z na konci.

    Používá se jen jako výchozí hodnota `clock`; testy si podstrčí vlastní.
    """
    from datetime import datetime, timezone
    return (datetime.now(timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}Z")
