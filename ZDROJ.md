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

Zatím žádné. Až přijdou, platí pro ně totéž co pro model:

* **Wikipedie** — CC BY-SA 4.0, přenáší se s údajem o zdroji.
* **Ekumenický překlad Bible** — autorský, **do veřejného repozitáře nesmí**
  (jen Kralická).

## cb-field — měřicí korpusy

| co | odkud | licence | v gitu? |
|---|---|---|---|
| testbed kdo-kde-kdy + etalon otázek | psáno ručně pro tento projekt | vlastní | ano (`cb_field/tests/data/`) |
| wiki životopisy a hesla (spisovatelé, fyzika) | česká Wikipedie, převzato z conBond2 `data/raw/` | **CC BY-SA 4.0** | **ne** — `cb_field/data-persistent/corpora/` |
| Nový zákon (Markovo evangelium) | moderní český překlad, převzato z conBond2 | **licencovaný text** | **ne** — `cb_field/data-persistent/corpora/` |
| `fyzika_gravitace.txt` | psáno ručně v conBond2 | vlastní | **ne** (drží se u ostatních korpusů) |
| doména vesmír (`korpus-201.json`) | česká Wikipedie, staženo přes API | **CC BY-SA 4.0** | **ne** — `cb_field/data-persistent/korpus/` |
| doména hudba (`korpus-202.json`) | česká Wikipedie, staženo přes API | **CC BY-SA 4.0** | **ne** — `cb_field/data-persistent/korpus/` |
| Nový zákon po knihách (`korpus-301…326.json`) | týž moderní překlad, převzato z conBond2 | **licencovaný text** | **ne** — `cb_field/data-persistent/korpus/` |

Pořízení: `./cb_field/scripts/fetch-korpusy.sh` (kopíruje z `~/Projects/conBond2/data/raw/`).
Měření (`docs/mereni-korpusy.md`) nese otisky souborů, aby čísla byla
srovnatelná i bez dat v gitu.

### Doména hudba

`korpus-202.json` pořizuje `./cb_field/scripts/fetch-hudba.py` — týž
mechanismus jako u vesmíru, články od hesla „Hudba": Hudba, Tón,
Melodie, Harmonie, Rytmus, Hudební nástroj, Klavír, Housle, Orchestr,
Opera, Jazz, Antonín Dvořák, Bedřich Smetana. **CC BY-SA 4.0**, mimo git.

### Nový zákon po knihách

`korpus-301…326.json` pořizuje `./cb_field/scripts/fetch-novy-zakon.py`
z `~/Projects/conBond2/data/raw/bible_*.txt` (bez Markova evangelia —
to je v korpusu-101 — a bez Exodu, který je Starý zákon). Je to týž
**licencovaný moderní překlad** jako u Marka, proto **mimo git**.

### Doména vesmír

`korpus-201.json` pořizuje `./cb_field/scripts/fetch-vesmir.py` — stáhne
plaintext extrakty (API `action=query&prop=extracts`) článků české
Wikipedie počínaje heslem „Vesmír“ a jeho klíčovými navazujícími tématy:
Vesmír, Velký třesk, Kosmologie, Galaxie, Mléčná dráha, Hvězda, Černá díra,
Sluneční soustava, Slunce, Planeta, Země. Text je pod **CC BY-SA 4.0**,
proto **do gitu nepatří** — soubor žije jen v gitignorované
`cb_field/data-persistent/korpus/`. Blok = odstavec extraktu (bez sekcí
Reference, Externí odkazy, Literatura, Poznámky, Související články),
věty vznikají rozparsováním celého odstavce parserem cb-udpipe.
