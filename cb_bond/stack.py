"""`ServiceStack` — cb-bond jako řídicí vrstva nad službami pod sebou.

cb-bond je vrcholová služba: bez loggeru a udpipe nemá co dělat. Při
startu tedy ověří, co pod ním běží, a co neběží, spustí — a **oznámí to**.
Politika § 9 chce hlasitou chybu místo tichého obcházení; tady je ale
spuštění přesně to, co člověk chce, takže se udělá nahlas.

## Dvě pravidla, která tu stojí zadrátovaná

**Cizí službu spouští její vlastní ovládací program** (`./cb-udpipe.py
start`), ne import jejího vnitřku. Logika startu patří tomu modulu; kdyby
ji cb-bond duplikoval, existovala by dvakrát a rozešla by se — a rozdíl by
se projevil až ve chvíli, kdy si někdo změní jeden z nich.

**Pořadí je dané závislostmi:** logger první, protože udpipe do něj loguje
už při vlastním startu. Obrácené pořadí by první záznamy zahodilo — tiše,
protože logger je nepovinná závislost a výpadek znamená degradaci, ne pád.
Zastavuje se v opačném pořadí ze stejného důvodu.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Sequence

#: Kořen projektu — odsud se volají ovládací programy sourozenců.
#: Počítá se od souboru, ne od pracovního adresáře procesu: jinak by
#: `./cb-udpipe.py` znamenalo něco jiného podle toho, odkud se cb-bond
#: spustil, a to je chyba, kterou nikdo nehledá na správném místě.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Kolik vteřin se čeká na odpověď `/v1/health`. Krátce schválně: tohle
#: je otázka „běžíš?", ne práce. Když se neozve za tři vteřiny, chová se
#: to jako neběžící, protože pro volajícího je to totéž.
HEALTH_TIMEOUT_S = 3

#: Kolik vteřin se čeká na to, až spuštěná služba naběhne. Startuje se
#: jejím vlastním programem, který se sám vrací až po kontrole — tohle
#: je pojistka proti zaseknutí, ne běžná cesta.
START_TIMEOUT_S = 300


class Dependency:
    """Služba, na které cb-bond stojí.

    Vstup:
        name: jméno pro člověka i pro log („cb-logger").
        control: ovládací program relativně ke kořeni projektu.
        endpoint: adresa API. Je v konfiguraci volajícího, ne volaného
            (§ 3) — cb-bond se nikoho neptá, kde služba běží.
    """

    def __init__(self, name: str, control: str, endpoint: str) -> None:
        self.name = name
        self.control = control
        self.endpoint = endpoint

    def __repr__(self) -> str:
        return f"Dependency({self.name!r}, {self.endpoint!r})"


def _http_health(dependency: Dependency) -> dict[str, Any] | None:
    """Zeptá se `/v1/health`; `None` znamená neodpovídá.

    Nerozlišuje mezi „port je hluchý" a „služba je nemocná" — pro
    volajícího je obojí totéž a rozdíl patří do `status` té služby.
    """
    try:
        with urllib.request.urlopen(dependency.endpoint + "/v1/health",
                                    timeout=HEALTH_TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _subprocess_runner(dependency: Dependency, prikaz: str) -> bool:
    """Spustí ovládací program závislosti; vrátí, jestli uspěl.

    Výstup programu se **nepolyká** — jde na naši konzoli, protože to,
    co při startu udpipe říká udpipe, je pro člověka užitečnější než
    naše shrnutí.
    """
    hotovo = subprocess.run(
        [str(PROJECT_ROOT / dependency.control), prikaz],
        cwd=str(PROJECT_ROOT), timeout=START_TIMEOUT_S, check=False)
    return hotovo.returncode == 0


class ServiceStack:
    """Ověří a spustí služby pod cb-bondem, v pořadí závislostí.

    Vstup:
        dependencies: v pořadí, ve kterém se startuje. Zastavuje se
            pozpátku.
        health: čím se zjišťuje, že služba běží. Vyměnitelné kvůli
            testům — jinak by sada potřebovala běžící službu (§ 13).
        runner: čím se spouští. Totéž.
        verbose: hlásit na konzoli. Zapnuto schválně; testy vypínají.
    """

    def __init__(self, dependencies: Sequence[Dependency], *,
                 health: Callable[[Dependency], Any] = _http_health,
                 runner: Callable[[Dependency, str], bool]
                 = _subprocess_runner,
                 log=None, verbose: bool = True) -> None:
        self.dependencies = tuple(dependencies)
        self.health = health
        self.runner = runner
        self.log = log
        self.verbose = verbose

    def check(self) -> list[dict[str, Any]]:
        """Stav každé závislosti, v pořadí závislostí.

        Výstup:
            Seznam slovníků `{name, running, endpoint, health}` — totéž,
            co jde do `status` i do REST odpovědi.
        """
        stav = []
        for zavislost in self.dependencies:
            zdravi = self.health(zavislost)
            stav.append({"name": zavislost.name,
                         "running": zdravi is not None,
                         "endpoint": zavislost.endpoint,
                         "health": zdravi})
        return stav

    def ensure(self, start: bool = True) -> list[str]:
        """Zajistí, že závislosti běží; vrátí jména těch, které chyběly.

        Vstup:
            start: spouštět, co neběží. `False` (přepínač `--no-deps`)
                znamená jen ohlásit — pro případ, kdy si člověk služby
                řídí sám a nechce překvapení.

        Výstup:
            Jména služeb, které bylo potřeba spustit (nebo které chybějí,
            když se nespouští).

        Při chybě:
            `RuntimeError`, když služba nenaběhla. Tiché pokračování by
            znamenalo cb-bond, který se tváří zdravě a padne až u prvního
            rozboru — daleko od příčiny (§ 9).
        """
        chybejici: list[str] = []
        for zavislost in self.dependencies:
            if self.health(zavislost) is not None:
                self._oznam(f"{zavislost.name:10} BĚŽÍ      "
                            f"({zavislost.endpoint})")
                continue
            chybejici.append(zavislost.name)
            if not start:
                self._oznam(f"{zavislost.name:10} NEBĚŽÍ    "
                            f"({zavislost.endpoint}) — nespouštím, "
                            f"běží --no-deps")
                continue
            self._oznam(f"{zavislost.name:10} NEBĚŽÍ → spouštím…")
            if not self.runner(zavislost, "start"):
                raise RuntimeError(
                    f"{zavislost.name} se nepodařilo spustit "
                    f"({zavislost.control} start skončil chybou); "
                    f"cb-bond bez něj běžet nemá — tvářil by se zdravě "
                    f"a spadl až u prvního dotazu")
            self._oznam(f"{zavislost.name:10} OK        "
                        f"({zavislost.endpoint})")
        return chybejici

    def stop(self) -> list[str]:
        """Zastaví běžící závislosti v OPAČNÉM pořadí.

        Logger poslední: zastavení udpipe se do něj ještě má zapsat.
        """
        zastavene: list[str] = []
        for zavislost in reversed(self.dependencies):
            if self.health(zavislost) is None:
                continue
            self._oznam(f"{zavislost.name:10} zastavuji…")
            self.runner(zavislost, "stop")
            zastavene.append(zavislost.name)
        return zastavene

    def report(self) -> str:
        """Přehled pro člověka — jméno, stav, adresa."""
        radky = []
        for s in self.check():
            radky.append(f"{s['name']:10} {'BĚŽÍ' if s['running'] else 'NEBĚŽÍ':7}"
                         f"  {s['endpoint']}")
        return "\n".join(radky)

    def _oznam(self, zprava: str) -> None:
        """Hlasitě na obě strany — do loggeru i na konzoli."""
        if self.verbose:
            print(f"           {zprava}", flush=True)
        if self.log is not None:
            self.log.info(zprava, source="cb-bond.stack")
