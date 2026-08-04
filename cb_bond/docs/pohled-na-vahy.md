# Pohled na váhy — jak zjistit, co se model naučil

Souhrnná čísla epochy (loss, korekcí, hran) řeknou, že se něco dělo.
Neřeknou **co**. Tenhle nástroj to ukazuje: mezi kterými vrstvami
reprezentace učení pracovalo a které konkrétní hrany o tom rozhodly.

```
./run-python cb_bond/scripts/pohled-na-vahy.py         # 10 hran na pohled
./run-python cb_bond/scripts/pohled-na-vahy.py 25      # podrobněji
```

Potřebuje běžící cb-udpipe a korpusy v `data-persistent` (mimo git).
Nic nemění — postaví korpus, doučí a vypíše; stav se nikam neukládá.

**Trvá to zhruba minutu** (2 912 vět, 6 epoch po 85 otázkách) a průběh
se hlásí na stderr, takže je vidět, že to běží:

```
stavím korpus z 7 souborů…
  2912 vět · osa 6671 vertikál · 5 s
učím: 85 otázek (+35 odložených na validaci)
  výchozí validační loss 0.1144
  epocha 1:  40/85 ·     4 s · V kterých vojenských objektech se narodi
  epocha 1 ponechána  loss 0.4248 · valid 0.3343 · učeno z 19/85 · hran 664
```

V terminálu se postup přepisuje na jednom řádku; při přesměrování do
souboru se hlásí každá desátá otázka na svém řádku (jinak by `\r`
nepřepsal nic a vznikl by kilometrový výpis).

---

## Co se vypisuje

### 1 · Po vrstvách — čte se první

```
ANCHOR       → LEM            614 hran
QLEM         → ANCHOR         268 hran
QLEM         → LEM            246 hran
LEM          → ANCHOR         236 hran
```

Řekne, mezi kterými vrstvami reprezentace hrany vznikly. **Tohle je
první kontrola: učí se to, co má?**

| dvojice | co znamená | čekání |
|---|---|---|
| `QLEM → ANCHOR` | typ otázky → souřadnice odpovědi | **tohle chceme** — „odkud" hledá zdroj |
| `QANCHOR → ANCHOR` | kotva otázky → kotva odpovědi | taky dobré, jen hrubší |
| `LEM → ANCHOR` | zavřené slovo → souřadnice | užitečné (předložka nese směr) |
| `ANCHOR → LEM` | souřadnice → zavřené slovo | podezřelé — viz níže |
| `X → X` | osa na sebe | **nesmí vzniknout**, hlídá test |

Že je `ANCHOR → LEM` nejpočetnější, je vlastnost gradientu, ne
záměr: krok je vnější součin `pytel otázky ⊗ (fitující − soupeř)`,
a pytel otázky nese i vlastní oznamovací kotvy (sloveso otázky dá
`ANCHOR=time:past`). Ty se pak párují se vším, co odlišuje obě věty.
Je to šum kolem užitečného jádra — pokud `QLEM → ANCHOR` mezi prvními
třemi chybí, učení jde vedle.

### 2 · Po epochách — i ta odvolaná

```
epocha 1 [ponechána]  loss 0.4248 · valid 0.3343 · učeno z 19/85 · hran 664
     Polarity=Pos      → ANCHOR=time:past   +0.0000 → +0.0089  (+0.0089)
     LEM=ADP:v         → ANCHOR=space:loc   +0.0000 → -0.0038  (-0.0038)
```

Největší kroky v epoše, se starou i novou vahou. **Odvolaná epocha se
vypisuje taky** — je stejně zajímavá jako ponechaná, protože ukazuje,
co se systém pokusil naučit, než ho validace zastavila.

### 3 · Výsledek — nejsilnější hrany po celém běhu

Seřazené podle velikosti, se znaménkem.

---

## Jak to číst

**Znaménko je důležitější než velikost.** Na tom se pozná učení od
šumu:

```
QLEM=ADV:odkud  → ANCHOR=space:from   +0.0114   ✓ „odkud" CHCE zdroj
QLEM=ADV:kde    → ANCHOR=space:loc    +0.0061   ✓ „kde" CHCE polohu
QLEM=ADV:kam    → ANCHOR=space:loc    -0.0060   ✓ „kam" polohu NECHCE
```

Tři hrany se správným znaménkem stojí za víc než tři sta hran
s náhodným. Kdo čte jen velikosti, nepozná jedno od druhého.

**Magnitudy kolem 0,01 znamenají, že se model sotva hnul.** Váhy mají
meze ±1, takže setiny jsou opatrné ťuknutí. Metrikou se to neprojeví
a nemá to ani očekávat — je to signál, že učení jde správným směrem,
ne že už něco umí.

**Nulová stará váha znamená NOVOU hranu.** `+0.0000 → +0.0089` je vznik
vazby, ne posílení existující; existující vazby se poznají podle
nenulového levého čísla.

**Co se v epochách opakuje, je nosné.** Když táž hrana roste ve všech
epochách stejným směrem (`+0.0089 → +0.0166 → …`), je to konzistentní
signál z dat. Hrana, která jednou nahoru a podruhé dolů, je šum
z jednotlivých otázek.

## Na co si dát pozor

**Nesmí tam být `WORD=`.** Ani na jedné straně, ani jednou. To je
invariant 1 (učení jen nad metadaty vertikál) a hlídá ho pojistkový
test — ale tenhle výpis je jeho lidsky čitelná kontrola. Konkrétní
slovo se do učení dostane jedině jako `CUSTOM=` po promoci.

**Osa sama na sebe** (`LEM=ADP:v → LEM=ADP:v`) při šíření jen zesiluje
aktivaci samu ze sebe a vztah nenese. Učení ji nezakládá; kdyby se ve
výpisu objevila, je něco rozbité.

**„Učeno z 19/85" je nejdůležitější číslo na řádku.** Říká, kolik
otázek šlo vůbec skórovat — u zbylých 66 se v shortlistu nenašla věta
s odpovědí, takže není co kontrastovat. Nízký loss při nízkém
„učeno z" neznamená, že systém umí; znamená, že se nemá z čeho učit,
a to je úkol pro recall, ne pro trenéra.

(Loss se proto dělí SKÓROVANÝMI. Dokud se dělil všemi, vycházel
0,0949 místo 0,4248 — vypadal 4,5× lépe, než jaká byla skutečnost.)

**Když je hran nula**, učení se nekonalo — buď se všechny epochy
odvolaly (validace), nebo byla marže splněná (konvergence). Pohled na
váhy to rozliší: odvolaná epocha má `zmeny` neprázdné, konvergovaná
má `korekcí 0`.

## Kde to sedí v kódu

Data pro výpis nese `TrainingReport.epochs[i]`:

| klíč | co je uvnitř |
|---|---|
| `zmeny` | `[(zdroj, cíl, stará, nová)]` seřazeno podle velikosti kroku |
| `vrstvy` | `{(prefix zdroje, prefix cíle): počet hran}` |
| `odvolano` | vrátila se epocha kvůli validaci? |
| `loss`, `loss_valid`, `korekci`, `hran`, `vrchol_median` | souhrn |

Kolik změn si epocha pamatuje, řídí `ContrastiveTrainer.top_changes`
(výchozí 20). Není to strop učení, jen strop výpisu.
