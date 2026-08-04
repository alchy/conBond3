#!/usr/bin/env python3
"""Co se model naučil — pohled na váhy v průběhu učení.

Odpovídá na otázku, kterou report se souhrnnými čísly nezodpoví:
*mezi kterými vrstvami reprezentace se učilo a které konkrétní hrany
o tom rozhodly.*

    ./run-python cb_bond/scripts/pohled-na-vahy.py            # 10 hran
    ./run-python cb_bond/scripts/pohled-na-vahy.py 25         # víc

Tři pohledy, od hrubého k jemnému:

  1. PO VRSTVÁCH — mezi kterými prefixy hrany vznikly (QLEM→ANCHOR…).
     Tohle se čte první: řekne, jestli se učí to, co má.
  2. PO EPOCHÁCH — největší kroky v každé epoše, i v odvolané.
     Odvolaná epocha je stejně zajímavá: je vidět, co systém CHTĚL.
  3. VÝSLEDEK — nejsilnější naučené hrany po celém běhu, se znaménkem.

Znaménko je to hlavní. `QLEM=ADV:odkud → ANCHOR=space:from` má být
KLADNÉ (otázka „odkud" chce zdroj) a `QLEM=ADV:kam → ANCHOR=space:loc`
ZÁPORNÉ (otázka „kam" nechce polohu). Kdo čte jen velikosti, nepozná
učení od šumu.
"""

import json
import sys
import time
from pathlib import Path

from cb_bond import ContrastiveTrainer, Matcher
from cb_field.corpusfile import build_corpus
from cb_udpipe import UdpipeClient

TRENINK = Path("cb_field/tests/data/trenink-otazky-korpusy.jsonl")


def _hlasic(kazda: int = 10):
    """Průběh na stderr — učení běží desítky sekund a nesmí mlčet.

    V terminálu se postup přepisuje na jednom řádku (\r). Když stderr
    míří do souboru nebo roury, `\r` nic nepřepíše a vznikl by
    kilometrový výpis — tam se proto hlásí jen každá `kazda`-tá otázka,
    každá na svém řádku.
    """
    zacatek = [time.time()]
    terminal = sys.stderr.isatty()
    # Python 3.11 nepustí zpětné lomítko dovnitř f-stringu, tak si ho
    # připravíme dopředu; zároveň je pak vidět, čím se řádky liší.
    navrat = "\r" if terminal else "  "
    konec = "" if terminal else "\n"

    def hlas(zprava):
        faze = zprava["faze"]
        if faze == "start":
            print(f"učím: {zprava['trenink']} otázek "
                  f"(+{zprava['validace']} odložených na validaci)",
                  file=sys.stderr, flush=True)
        elif faze == "validace_pred":
            print(f"  výchozí validační loss {zprava['loss']:.4f}",
                  file=sys.stderr, flush=True)
        elif faze == "otazka":
            hotovo, celkem = zprava["hotovo"], zprava["celkem"]
            if not terminal and hotovo % kazda and hotovo != celkem:
                return
            print(f"{navrat}  epocha {zprava['epocha']}: "
                  f"{hotovo:3}/{celkem} "
                  f"· {time.time() - zacatek[0]:5.0f} s "
                  f"· {zprava['otazka'][:40]:42}",
                  end=konec, file=sys.stderr, flush=True)
        elif faze == "validace":
            print(f"{navrat}  epocha {zprava['epocha']}: validuji…"
                  f"{' ' * 50}", end=konec, file=sys.stderr, flush=True)
        elif faze == "epocha":
            stav = "ODVOLÁNA" if zprava["odvolano"] else "ponechána"
            print(f"{navrat}  epocha {zprava['epocha']} {stav:10} "
                  f"loss {zprava['loss']:.4f} · valid "
                  f"{zprava['loss_valid']:.4f} · učeno z "
                  f"{zprava['skorovano']}/"
                  f"{zprava['skorovano'] + zprava['preskoceno']}"
                  f" · hran {zprava['hran']:5}"
                  f"{' ' * 12}", file=sys.stderr, flush=True)

    return hlas


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    kolik = int(argv[0]) if argv else 10

    korpus = Path("cb_field/data-persistent/korpus")
    paths = sorted(korpus.glob("korpus-1*.json"))
    if not paths:
        print(f"chybí korpusy v {korpus} — viz ZDROJ.md", file=sys.stderr)
        return 2

    parser = UdpipeClient()
    print(f"stavím korpus z {len(paths)} souborů…", file=sys.stderr,
          flush=True)
    t0 = time.time()
    corpus = build_corpus(paths, parser, r=1)
    print(f"  {len(corpus)} vět · osa {len(corpus.registry)} vertikál "
          f"· {time.time() - t0:.0f} s", file=sys.stderr, flush=True)
    trenink = [json.loads(r) for r in TRENINK.read_text(encoding="utf-8").
               splitlines() if r.strip()]

    pred = {(src, dst): vaha
            for src, dst, vaha in corpus.registry.links()}
    trener = ContrastiveTrainer(corpus, Matcher(corpus, spread_depth=1,
                                                theta=0.0), parser,
                                progress=_hlasic())
    trener.top_changes = max(kolik, 20)
    zprava = trener.train(trenink, max_epochs=6)
    print(file=sys.stderr, flush=True)

    print("=" * 72)
    print("1) PO VRSTVÁCH — mezi kterými vrstvami reprezentace se učilo")
    print("=" * 72)
    celkem: dict = {}
    for epocha in zprava.epochs:
        for klic, pocet in epocha["vrstvy"].items():
            celkem[klic] = celkem.get(klic, 0) + pocet
    for (src, dst), pocet in sorted(celkem.items(), key=lambda d: -d[1]):
        print(f"   {src:12} → {dst:12} {pocet:5} hran")

    print("\n" + "=" * 72)
    print("2) PO EPOCHÁCH — největší kroky (i v odvolané epoše)")
    print("=" * 72)
    for i, epocha in enumerate(zprava.epochs, 1):
        stav = "ODVOLÁNA" if epocha["odvolano"] else "ponechána"
        print(f"\nepocha {i} [{stav}]  loss {epocha['loss']:.4f} "
              f"· valid {epocha['loss_valid']:.4f} "
              f"· učeno z {epocha['skorovano']}/"
              f"{epocha['skorovano'] + epocha['preskoceno']} otázek "
              f"· korekcí {epocha['korekci']} · hran {epocha['hran']}")
        for src, dst, stara, nova in epocha["zmeny"][:kolik]:
            print(f"     {src:26} → {dst:24} "
                  f"{stara:+.4f} → {nova:+.4f}  ({nova - stara:+.4f})")

    print("\n" + "=" * 72)
    print("3) VÝSLEDEK — nejsilnější naučené hrany (znaménko rozhoduje)")
    print("=" * 72)
    nove = [(src, dst, vaha) for src, dst, vaha in corpus.registry.links()
            if pred.get((src, dst), 0.0) != vaha]
    nove.sort(key=lambda z: -abs(z[2]))
    for src, dst, vaha in nove[:kolik]:
        print(f"   {src:26} → {dst:24} {vaha:+.4f}")
    print(f"\ncelkem naučeno {len(nove)} hran; z toho na prostorovou "
          f"souřadnici {sum(1 for _, d, _ in nove if 'space:' in d)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
