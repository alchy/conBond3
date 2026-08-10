"""Konzole — textový prompt nad `BondService`.

Tenká vrstva: přečte řádek, zavolá `ask` a vypíše odpověď **i rozklad
skóre**. Tím se naplní princip 6 — člověk vidí, proč systém odpověděl,
aniž by četl kód.

Příkazy navíc, bez kterých by dialogová vrstva nešla vyzkoušet jinak než
skriptem:

    :context <věta>   přidá větu do korpusu i grafu (dialogové doplnění)
    :state            vypíše, co má systém v hlavě
    :quit             konec

Vstup i výstup se předávají (§ 3), aby šly v testu nahradit soubory —
jinak by test potřeboval člověka u klávesnice.
"""

from __future__ import annotations

import sys
from typing import Any

from cb_bond.window import format_answer, format_axes, format_sentence

PROMPT = "? "


class Console:
    """Interaktivní prompt nad fasádou."""

    def __init__(self, service, *, vstup=None, vystup=None) -> None:
        self.service = service
        self.vstup = vstup if vstup is not None else sys.stdin
        self.vystup = vystup if vystup is not None else sys.stdout

    def run(self) -> int:
        """Čte řádky, dokud je co číst. Vrací návratový kód."""
        self._pis("cb-bond — zeptej se česky, :quit ukončí")
        for radek in self.vstup:
            text = radek.strip()
            if not text:
                continue
            if text.startswith(":"):
                if not self._prikaz(text):
                    return 0
                continue
            self._otazka(text)
        return 0

    # --- co konzole umí -------------------------------------------------

    def _otazka(self, text: str) -> None:
        """Otázka → odpověď, rozklad, kandidátní věty a osy."""
        try:
            odpoved = self.service.ask(text)
        except Exception as e:                # noqa: BLE001
            self._pis(f"  chyba: {type(e).__name__}: {e}")
            return
        for radek in format_answer(odpoved):
            self._pis(radek)
        for veta in odpoved["sentences"]:
            self._pis("   " + format_sentence(veta))
        for radek in format_axes(odpoved["axes"]):
            self._pis("   " + radek)

    def _prikaz(self, text: str) -> bool:
        """Zpracuje příkaz; `False` znamená skončit.

        Neznámý příkaz je **hláška**, ne otázka: tiché položení `:neco`
        jako otázky by vypadalo jako chyba párování, ne jako překlep.
        """
        jmeno, _, zbytek = text[1:].partition(" ")
        if jmeno in ("quit", "exit"):
            return False
        if jmeno == "state":
            for klic, hodnota in self.service.state().items():
                self._pis(f"   {klic:20} {hodnota}")
            return True
        if jmeno == "context":
            if not zbytek.strip():
                self._pis("  :context chce větu")
                return True
            stav = self.service.context(zbytek.strip())
            self._pis(f"  přidáno — korpus {stav.get('sentences')} vět "
                      f"(+{stav.get('added_sentences')}) · "
                      f"graf +{stav.get('added_edges')} hran")
            logika = stav.get("logic")
            if logika and logika.get("outcome"):
                # Formální vrstva se z věty učí vedle korpusu — ať je
                # vidět, co přijala a co z toho odvodila.
                self._pis(f"  logika — {logika['kind']}: {logika['outcome']}")
                for fakt in logika.get("derived", ()):
                    self._pis(f"    odvozeno: {fakt}")
                if logika.get("conflicts"):
                    self._pis(f"    rozporů v bázi: {logika['conflicts']}")
            elif logika and logika.get("note"):
                self._pis(f"  logika — neinterpretováno: {logika['note']}")
            return True
        self._pis(f"  neznámý příkaz {jmeno!r}; umím :context, :state, :quit")
        return True

    def _pis(self, text: str) -> None:
        print(text, file=self.vystup, flush=True)


def main(argv: list[str] | None = None) -> int:
    """Konzole nad běžící službou přes klienta.

    Přes klienta schválně, ne přes vlastní stavbu: konzole má mluvit
    s tím, co skutečně běží. Vlastní stavba by trvala vteřiny a ukázala
    by jiný systém, než na který se člověk dívá v okně.
    """
    from cb_bond.client import BondClient, ServiceUnavailable
    try:
        klient = BondClient()
        klient.version()
    except ServiceUnavailable as e:
        print(e, file=sys.stderr)
        return 3
    return Console(_KlientJakoSluzba(klient)).run()


class _KlientJakoSluzba:
    """Klient v šatech fasády — konzole nepozná rozdíl.

    Existuje proto, aby `Console` měla jednu cestu k systému, ať běží
    v procesu služby (okna viewBase2) nebo vedle ní (terminál).
    """

    def __init__(self, klient) -> None:
        self.klient = klient

    def ask(self, text: str, *, top: int | None = None) -> dict[str, Any]:
        return self.klient.ask(text, top=top)

    def state(self) -> dict[str, Any]:
        return self.klient.state()

    def context(self, text: str) -> dict[str, Any]:
        return self.klient.context(text)


if __name__ == "__main__":
    sys.exit(main())
