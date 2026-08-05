# Zdroje a licence

Co do projektu přišlo odjinud, odkud, a pod jakou licencí. Vede se tady proto,
že **licencovaná data se nesmí dostat do repozitáře** a kontrola toho je
automatická, ne slib — slib jednou selže (návrh, kap. 40.2; `T-8`).

Soubor se přenáší s daty. Kdo si projekt zkopíruje, musí z něj poznat, co smí
a co ne, aniž by se ptal.

---

## cb-udpipe

| co | odkud | licence | v gitu? |
|---|---|---|---|
| **UDPipe 2** (zdrojáky) | [github.com/ufal/udpipe](https://github.com/ufal/udpipe), větev `udpipe-2` | MPL 2.0 | ano, jako submodul |
| **cs_all-ud-2.17-251125** (model) | [LINDAT/CLARIN](http://hdl.handle.net/11234/1-6046) | **CC BY-NC-SA 4.0** | **ne** |
| **RobeCzech** (embeddingy) | [ufal/robeczech-base](https://huggingface.co/ufal/robeczech-base) | dle ÚFAL | **ne** |

### Model je nekomerční

`cs_all-ud-2.17-251125` je pod **CC BY-NC-SA 4.0**, tedy k nekomerčnímu
použití, s uvedením původu a se stejným sdílením. Server to sám vypisuje do
hlavičky každého rozboru:

```
# udpipe_model_licence = CC BY-NC-SA
```

Pro projekt to znamená dvě věci. Model **nesmí do repozitáře** — pořizuje ho
`cb_udpipe/scripts/fetch-models.sh` a cesta k němu je v `.gitignore`. A kdyby
se conBond3 měl někdy použít komerčně, musí se model vyměnit za jiný;
architektura s tím počítá, protože jméno modelu je součástí klíče cache
a rozbory dvou modelů se nemají jak potkat.

### Jak model pořídit

```bash
# z conBondu2, když je po ruce (rychlé, offline)
cb_udpipe/scripts/fetch-models.sh --from-conbond2 ../conBond2

# jinak ručně z LINDATu:
#   1. stáhnout z http://hdl.handle.net/11234/1-6046
#   2. rozbalit cs_all-ud-2.17-251125.model do
#      cb_udpipe/data-persistent/models/
#   3. RobeCzech z huggingface.co/ufal/robeczech-base do
#      cb_udpipe/data-persistent/models/hf/hub/models--ufal--robeczech-base
```

Skript stahování z LINDATu **nedělá schválně**: URL, kterou jsem neověřil, do
skriptu nepatří. A nástroj se nikdy nestahuje za běhu — je to samostatný krok,
který udělá člověk vědomě, ne vedlejší účinek prvního dotazu. *(V conBondu2 si
UDPipe bez tohohle pravidla sahal na HuggingFace do `~/.cache` a při prvním
spuštění bez sítě spadl.)*

---

## Data převzatá z předchozích projektů

| co | odkud | poznámka |
|---|---|---|
| seznam českých zkratek | jellyAI3 `jellyai/text.py` + měření na korpusu conBondu2 | v `cb-udpipe-config.json`, je to jazykové datum |
| pravidlo pro tečkované zkratky | conBond `core/normalize.py`, jellyAI3 `jellyai/normalize.py` | obě verze shodné: běh ≥2 párů ⟨písmeno⟩⟨tečka⟩ |
| prahy dávkování a timeoutů | conBond2 `core/ingest.py` | zapsané v registru prahů |

---

## Korpusy

Platí pro ně totéž co pro model:

* **Wikipedie** — CC BY-SA 4.0, přenáší se s údajem o zdroji.
* **Ekumenický překlad Bible** — autorský, **do veřejného repozitáře nesmí**
  (jen Kralická).

Odtud plyne dělení, které je vidět v adresářích: co je licencované, leží
v `data-persistent/` (gitignorováno), co je vlastní text, leží v `tests/data/`
(v gitu). Rozvod je záměrný a **nesmí se obrátit** — soupis dole říká, co kam
patří, aby to při dalším ingestu nikdo nemusel dohadovat.

| co | kde | odkud | v gitu? |
|---|---|---|---|
| `korpus-101…107.json` (2 912 vět) | `<data_root>/corpus/` | převod textů z `data-persistent/corpora/` (conBond2, `scripts/fetch-korpusy.sh`): Markovo evangelium, fyzika, spisovatelé | **ne** |
| `korpus-201.json` (605) · `korpus-202.json` (600) | tamtéž | Wikipedie — vesmír, hudba | **ne** |
| `korpus-301…326.json` (8 141) | tamtéž | Nový zákon po knihách | **ne** |
| `korpus-001…003.json` (295 vět) | `cb_field/tests/data/korpus/` | vlastní texty (doprava, příroda, dějiny) + 54 vlastních otázek | ano |
| `otazky-201.json` · `otazky-202.json` (2×60) | tamtéž | vlastní otázky k 201/202; soubor nese jen `questions` + `"corpus": …` | ano |
| `trenink-otazky-korpusy.jsonl` (120) | `cb_field/tests/data/` | vlastní supervize (75 zodpověditelných) | ano |
| `etalon-otazky-korpusy.jsonl` (40) | tamtéž | vlastní etalon (30 zodpověditelných) — **nikdy do tréninku** | ano |

Otázkové soubory jsou vlastní tvorba, i když míří do licencovaného korpusu:
nesou index věty a lemma odpovědi, ne její text. Kdo si projekt zkopíruje,
dostane tedy měřicí aparát celý a texty k němu si pořídí sám.
