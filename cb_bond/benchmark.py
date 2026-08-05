"""BenchmarkProtocol — měření po ramenech nad TÝMŽ korpusem.

Protokol nic nepočítá sám; skládá hotové díly a hlídá dvě věci, které
se jinak snadno pokazí: aby se všechna ramena měřila nad **týmž
korpusem** (jinak se porovnávají dvě různá měření) a aby se **etalon
nikdy nedostal do tréninku**.

## Ramena a proč právě tahle

    A  baseline           čistý stav, žádné učení, hloubka 1
    B  učení              A + kontrastivní trénink
    D  hloubka            hloubka 2 na ČISTÉM baselinu (bez učení)
    C  promoce            promoční cyklus nad B — rozhodne sám
    E  hloubka nad C      hloubka 2 nad přijatým stavem
    F  kalibrované θ      provozní bod s řezem na mlčení

**B je kontrola k C.** Obě ramena mají učení, liší se jen promocí —
takže rozdíl C−B je čistý příspěvek promovaných os, ne směs vlivů.

**D měří hloubku samotnou.** Na čistém baselinu, aby šlo poznat, kolik
přidá sama a kolik až ve složení s učením a promocí (naměřeno
v referenci: hloubka se skládá NADADITIVNĚ).

**F je provozní bod, ne vítěz.** Kalibrované θ přesnost SRAZÍ a mlčení
zvedne — systém raději mlčí, než aby tipoval. Které rameno je „to
pravé", je rozhodnutí, ne měření.

## Kalibruje se na TRÉNINKU, měří na etalonu

θ se hledá nad supervizí, nikdy nad etalonem — jinak by se práh vybral
podle testu, který má měřit, a číslo by lhalo.
"""

from dataclasses import dataclass, field as _field


@dataclass
class ArmResult:
    """Výsledek jednoho ramene."""

    label: str
    presnost: float
    mlceni: float
    veta: int
    zodpoveditelnych: int
    pozn: str = ""

    def __repr__(self) -> str:
        return (f"{self.label}: přesnost {self.presnost:.4f} · mlčení "
                f"{self.mlceni:.2f} · věta {self.veta}/"
                f"{self.zodpoveditelnych}"
                + (f" · {self.pozn}" if self.pozn else ""))


@dataclass
class BenchmarkReport:
    """Celý protokol: ramena v pořadí a vylosované příklady."""

    arms: list = _field(default_factory=list)
    examples: list = _field(default_factory=list)

    def arm(self, label: str):
        return next((a for a in self.arms if a.label == label), None)


class ThresholdCalibrator:
    """Hledá θ, které nejlépe dělí odpověď od mlčení.

    Zásluha (`merit`) je průměr dvou protivah — přesnosti na
    zodpověditelných a správného mlčení na svodech. Jedno bez druhého
    se dá získat triválně: θ = 0 dá přesnost bez mlčení, θ = ∞ mlčení
    bez přesnosti. Teprve jejich průměr má maximum uvnitř.

    Kalibruje se nad SUPERVIZÍ, nikdy nad etalonem.
    """

    def calibrate(self, entries, results) -> dict:
        skore = sorted({float(v.best.score) for v in results if v.best},
                       reverse=True)
        if not skore:
            return {"theta": 0.0, "presnost": 0.0, "mlceni": 0.0,
                    "merit": 0.0}
        # Kandidáti na práh: každé pozorované skóre a kousek pod ním,
        # aby šlo θ položit i těsně pod nejnižší trefu.
        kandidati = [0.0] + skore + [min(skore) - 1e-6]
        nejlepsi = {"theta": 0.0, "presnost": 0.0, "mlceni": 0.0,
                    "merit": -1.0}
        for theta in kandidati:
            presne = zodp = mlcelo = nezodp = 0
            for zaznam, vysledek in zip(entries, results):
                odpovida = (vysledek.best is not None
                            and float(vysledek.best.score) >= theta)
                if zaznam.get("zodpoveditelna"):
                    zodp += 1
                    presne += bool(
                        odpovida and vysledek.best.lemma
                        == zaznam.get("odpoved_lemma"))
                else:
                    nezodp += 1
                    mlcelo += not odpovida
            presnost = presne / zodp if zodp else 0.0
            mlceni = mlcelo / nezodp if nezodp else 0.0
            merit = (presnost + mlceni) / 2
            if merit > nejlepsi["merit"]:
                nejlepsi = {"theta": float(theta),
                            "presnost": round(presnost, 4),
                            "mlceni": round(mlceni, 4),
                            "merit": round(merit, 4)}
        return nejlepsi


class BenchmarkProtocol:
    """Projde ramena A–F nad týmž korpusem a vydá report.

    Závislosti parametrem (§ 3): protokol dostane funkce, které umí
    měřit, učit a promovat — sám neví, čím se to dělá.
    """

    #: Pořadí ramen je závazné; každé má důvod (viz docstring modulu).
    ARMS = [
        ("A", "baseline — čistý stav, hloubka 1, bez učení"),
        ("B", "učení — kontrastivní trénink nad A"),
        ("D", "hloubka 2 na ČISTÉM baselinu (bez učení)"),
        ("C", "promoce — promoční cyklus nad B, rozhodne sám"),
        ("E", "hloubka 2 nad přijatým stavem C"),
        ("F", "kalibrované θ — provozní bod s mlčením"),
    ]

    def __init__(self, measure, train, promote, calibrate=None,
                 seed: int = 328) -> None:
        self.measure = measure
        self.train = train
        self.promote = promote
        self.calibrate = calibrate
        self.seed = seed

    def run(self) -> BenchmarkReport:
        """Projde ramena v předepsaném pořadí; vrátí report."""
        report = BenchmarkReport()

        report.arms.append(self.measure("A", depth=1))
        self.train()
        report.arms.append(self.measure("B", depth=1))
        report.arms.append(self.measure("D", depth=2))
        vysledek = self.promote()
        report.arms.append(self.measure(
            "C", depth=1,
            pozn="PŘIJATO" if vysledek.accepted else "vráceno"))
        report.arms.append(self.measure("E", depth=2))
        if self.calibrate is not None:
            report.arms.append(self.calibrate("F"))
        return report
