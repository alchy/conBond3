"""Okna viewBase2 — rozhraní cb-bondu k člověku.

Čtyři okna (rozhodnutí J., 5. 8. 2026):

    graf        uzly a hrany; po otázce se kandidátní věty ROZSVÍTÍ
    dialog      otázka a odpověď s rozkladem skóre; přijímá vstup
    věty        top 5 kandidátních vět v konvenci `[slovo] Věta`
    vertikály   osy otázky a jak dobře je korpus zná

Proč čtyři a ne jedno: v jednom okně by se rozklad skóre, kandidátní
věty a osy překrývaly a člověk by musel skrolovat, aby porovnal, co
spolu souvisí. Rozdělené se dají číst vedle sebe — a o to jde: princip 6
chce, aby bylo vidět **proč** systém odpověděl, bez čtení kódu.

## Co je tady a co ne

`viewbase` je **nepovinná** závislost. Import je proto až uvnitř funkcí:
modul musí jít naimportovat i tam, kde frontend nainstalovaný není —
jinak by na něm viselo i to, co s okny nesouvisí. Formátovací funkce
(`format_*`) jsou čisté a testují se bez něj.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

#: Otisk frontendu, proti kterému se tohle psalo (2026-08-04).
#: Neshoda není chyba — je to upozornění, že běží jiná generace.
#: Starý projekt viewBase už jednou podvrhl starou generaci bundlu.
EXPECTED_BUNDLE = "39a833cc57f74bb4"

#: Jména oken. Píše se do nich podle `window_id`, takže musí být stálá.
DIALOG_ID = "dialog"
SENTENCES_ID = "sentences"
AXES_ID = "axes"


def bundle_fingerprint() -> tuple[str, str]:
    """(jméno bundlu, prvních 16 znaků sha256) z instalovaného viewbase.

    Kdo vidí jiný otisk než očekávaný, ví hned, že mu běží jiná generace
    frontendu — a nehledá chybu ve svém kódu.
    """
    import viewbase

    static = Path(viewbase.__file__).parent / "static"
    index = (static / "index.html").read_text(encoding="utf-8")
    shoda = re.search(r'src="(/assets/[^"]+\.js)"', index)
    if not shoda:
        return ("?", "?")
    soubor = static / shoda.group(1).lstrip("/")
    otisk = hashlib.sha256(soubor.read_bytes()).hexdigest()[:16]
    return (soubor.name, otisk)


# --- formátování (čisté funkce, bez viewbase) ---------------------------


def format_sentence(veta: dict[str, Any]) -> str:
    """Kandidátní věta v dohodnuté konvenci `[slovo] Věta`.

    Skóre je součástí řádku: bez něj nejde poznat, jak daleko je druhá
    volba od první, a člověk nepozná těsné rozhodnutí od jasného.
    """
    return (f"[{veta['lemma']}] {veta['score']:.2f}  {veta['text']}")


def format_axes(osy: list[dict[str, Any]]) -> list[str]:
    """Osy otázky a jejich pokrytí, jeden řádek na osu.

    Nula je propast, ne malé číslo — proto se vypisují všechny, i ty
    nulové: právě ony říkají, co korpus vůbec nezná.
    """
    return [f"{osa['axis']:32} {osa['coverage']:.3f}" for osa in osy]


def format_answer(odpoved: dict[str, Any]) -> list[str]:
    """Odpověď s rozkladem skóre, řádek po řádku.

    Rozklad je součástí odpovědi, ne přílohy: bez něj by člověk viděl
    výsledek a neměl jak poznat, čím vznikl.
    """
    radky = [f"? {odpoved['question']}"]
    if odpoved.get("answer") is None:
        radky.append(f"  systém mlčí ({odpoved.get('outcome', '?')})")
    else:
        radky.append(f"  → {odpoved['answer']!r}  "
                     f"({odpoved['outcome']}, skóre {odpoved['score']:.3f})")
    if odpoved.get("decomposition"):
        radky.append("  " + " · ".join(
            f"{jmeno} {hodnota:+.2f}"
            for jmeno, hodnota in odpoved["decomposition"].items()))
    if odpoved.get("missing"):
        radky.append(f"  chybí: {', '.join(odpoved['missing'])}")
    radky.extend(format_logic(odpoved.get("logic")))
    return radky


def format_logic(logika: dict[str, Any] | None) -> list[str]:
    """Řádky formální vrstvy — podle druhu: odpověď, modalita, doptání.

    Formální vrstva stojí vedle retrieval cesty; když má co říct, patří
    její verdikt, řetěz i doptání do téhož okna, ne do logu.
    """
    if not logika:
        return []
    kind = logika.get("kind")
    if kind == "needs_pattern":
        # Systém zná strukturu, ne mapování — ptá se z uzavřeného menu.
        radky = [f"  logika se ptá: {logika['question']}"]
        for volba in logika.get("options", ()):
            radky.append(f"    · {volba['operation']} — {volba['popis']}")
        radky.append(f"    (nauč příkazem  :vzor {logika['lemma']} "
                     f"<possible|necessary|impossible>)")
        return radky
    if kind == "modal_query":
        return [f"  logika ({logika['operation']}): {logika['answer']}"]
    radky = []
    if logika.get("answer"):
        radky.append(f"  logika: {logika['answer']}")
    for vysvetleni in logika.get("explanations", ()):
        radky.append(f"    {vysvetleni}")
    for chybejici in logika.get("missing", ()):
        radky.append(f"    chybí vědět: {chybejici}")
    if logika.get("conflicted"):
        radky.append("    pozor: k dotazu eviduji rozpor")
    return radky


# --- okna ---------------------------------------------------------------


class BondWindows:
    """Tři textová okna vedle grafu, přepisovaná po každé otázce.

    Vstup:
        service: fasáda (`BondService`) nebo cokoli s `ask(text, top=)`.
        graph_window: okno grafu z `viewbase`; do něj se otevírají
            terminály a v něm se rozsvěcují uzly.
        mirror: `GraphMirror`, nebo `None`. Bez zrcadla se okna píší
            dál, jen se nerozsvěcuje graf — okna a graf jsou dvě různé
            věci a jedna nemá padat na druhé.
        top: kolik vět se ukazuje. Pět je dohodnutá velikost okna.
    """

    def __init__(self, service, graph_window, *, mirror=None,
                 top: int = 5) -> None:
        self.service = service
        self.window = graph_window
        self.mirror = mirror
        self.top = top

    def attach(self) -> None:
        """Otevře tři terminály vedle grafu a napíše úvodní řádek."""
        from viewbase import TerminalWindow

        self.window.open_terminal(
            TerminalWindow(DIALOG_ID, title="dialog", prompt="? ",
                           input=True),
            on_input=self._na_vstup)
        self.window.open_terminal(
            TerminalWindow(SENTENCES_ID, title="kandidátní věty",
                           input=False))
        self.window.open_terminal(
            TerminalWindow(AXES_ID, title="použité vertikály", input=False))
        self._pis(DIALOG_ID, ["zeptej se česky; odpověď přijde s rozkladem"])

    def ask(self, text: str) -> dict[str, Any]:
        """Otázka → přepsaná okna a rozsvícený graf.

        Okna se přepisují **všechna tři naráz**, protože patří k téže
        otázce. Kdyby se přepisovala postupně, šlo by přečíst rozklad
        jedné otázky vedle vět jiné.
        """
        odpoved = self.service.ask(text, top=self.top)
        self._pis(DIALOG_ID, format_answer(odpoved))
        self._pis(SENTENCES_ID,
                  [format_sentence(v) for v in odpoved["sentences"]]
                  or ["(žádná kandidátní věta)"])
        self._pis(AXES_ID, format_axes(odpoved["axes"]))
        self._rozsvit(odpoved)
        return odpoved

    def _rozsvit(self, odpoved: dict[str, Any]) -> None:
        """Rozsvítí v grafu uzly kandidátních vět.

        Váhy se normují na nejlepší větu, aby jas znamenal „jak moc
        proti vítězi", ne absolutní skóre — to by při jiné otázce
        znamenalo jiný jas pro tutéž jistotu.
        """
        if self.mirror is None or not odpoved["sentences"]:
            return
        nejvyssi = max(v["score"] for v in odpoved["sentences"])
        vahy = {v["position"]: (max(0.0, v["score"]) / nejvyssi
                                if nejvyssi > 0 else 0.0)
                for v in odpoved["sentences"]}
        lemmata = {osa["axis"].split(":", 1)[-1] for osa in odpoved["axes"]}
        self.mirror.illuminate(self.service.graph, vahy, lemmata)

    def _na_vstup(self, event) -> None:
        """Obsluha řádku z dialogového okna.

        Dostává **objekt události** s `window_id` a `line`, ne řetězec.
        Zapsáno po chybě: brala se sem přímo věta a volalo se na ní
        `.strip()`, což na `SimpleNamespace` spadne — a viewbase výjimku
        handleru spolkne (zaloguje si ji a běží dál), takže okno mlčelo
        bez jediné stopy.

        Chyba se proto **píše do okna**, ne jen na konzoli: člověk, který
        sedí u prohlížeče, jinak vidí, že se nestalo nic, a neví proč.
        """
        radek = (getattr(event, "line", "") or "").strip()
        if not radek:
            return
        try:
            if radek.startswith(":"):
                self._prikaz(radek)
            elif radek.rstrip().endswith("?"):
                self.ask(radek)          # otázka → odpověď
            else:
                self._sdel(radek)        # tvrzení → uč se (kap. 19.1)
        except Exception as e:                # noqa: BLE001
            self._pis(DIALOG_ID, [f"  chyba: {type(e).__name__}: {e}"])

    def _prikaz(self, radek: str) -> None:
        """Příkazy okna — táž sada jako konzole (:context/:vzor/:zapomen/:state).

        Bez nich by v prohlížeči nešlo systému nic sdělit ani ho učit;
        okno by umělo jen otázky a dialog by byl jednosměrný.
        """
        jmeno, _, zbytek = radek[1:].partition(" ")
        zbytek = zbytek.strip()
        if jmeno == "context" and zbytek:
            self._sdel(zbytek)
        elif jmeno == "vzor":
            casti = zbytek.split()
            if len(casti) != 2 or casti[1] not in (
                    "possible", "necessary", "impossible"):
                self._pis(DIALOG_ID,
                          ["  :vzor <slovo> <possible|necessary|impossible>"])
                return
            v = self.service.teach_pattern(casti[0], casti[1])
            self._pis(DIALOG_ID, [f"  naučeno: {v['lemma']!r} → "
                                  f"{v['operation']} ({v['status']})"])
        elif jmeno == "zapomen" and zbytek:
            v = self.service.forget_word(zbytek)
            self._pis(DIALOG_ID, [f"  odvoláno: {v['lemma']!r}"
                                  + ("" if v["revoked"] else " (nebyl naučen)")])
        elif jmeno == "state":
            self._pis(DIALOG_ID, [f"  {k}: {v}"
                                  for k, v in self.service.state().items()])
        else:
            self._pis(DIALOG_ID,
                      [f"  neznámý příkaz {jmeno!r}; "
                       f"umím :context :vzor :zapomen :state"])

    def _sdel(self, text: str) -> None:
        """Tvrzení od člověka → korpus, graf a formální báze se z něj učí.

        Věta bez otazníku je sdělení, ne otázka (kap. 19.1): systém ji
        má přijmout a naučit se z ní, ne ji hledat v korpusu. Co přijala
        formální vrstva a co z toho odvodila, se ukáže v okně.
        """
        stav = self.service.context(text)
        logika = stav.get("logic") or {}
        radky = [f"! {text}",
                 f"  korpus +{stav.get('added_sentences', 0)} vět · "
                 f"graf +{stav.get('added_edges', 0)} hran"]
        if logika.get("outcome"):
            radky.append(f"  logika — {logika['kind']}: {logika['outcome']}")
            for fakt in logika.get("derived", ()):
                radky.append(f"    odvozeno: {fakt}")
        elif logika.get("note"):
            radky.append(f"  logika — neinterpretováno: {logika['note']}")
        self._pis(DIALOG_ID, radky)

    def _pis(self, window_id: str, radky: list[str]) -> None:
        self.window.terminal_write(window_id, "\n".join(radky))
