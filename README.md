# conBond3

Systém, který se v českém textu dopracuje k odpovědi — a umí ukázat, **čím**
se rozhodl. Otázka jde dovnitř jako věta, ven jde kandidátní věta, slovo
a rozklad skóre po pojmenovaných členech.

```
? Kde byl pokřtěn Ježíš?
  → 'říci'  (answer, skóre 2.366)
  meet +1.23 · cover +0.60 · topic +0.54 · given -0.00 · fit +0.00 · spectral +0.00
   [přijít] 2.27  V těch dnech přišel Ježíš z Nazareta v Galileji a byl
                  v Jordánu od Jana pokřtěn.
```

Tenhle soubor je **rozcestník a návod ke spuštění**. Proč je systém postavený
takhle, stojí v `README-ARCHITECTURE_OVERVIEW.md`; pravidla, kterými se řídí
každý modul, v `README-MODULES.md`.

---

## Rychlý start

Za předpokladu, že prostředí i data už na stroji jsou (jinak viz níže):

```bash
./cb-bond.py start      # zvedne VŠECHNO: logger → udpipe → sebe
./cb-bond.py status     # co systém má v hlavě
```

Otevře se REST API na `42400` a okna v prohlížeči na
**http://127.0.0.1:42401** — graf faktů, dialog, kandidátní věty a použité
vertikály. Zeptat se jde tam, nebo z terminálu:

```bash
./run-python -m cb_bond.console
```

`cb-bond` je vrcholová služba, takže si spustí i ty pod sebou. Pořadí není
libovolné: **logger první, pak udpipe** — udpipe do loggeru loguje už při
vlastním startu, takže obrácené pořadí by první záznamy zahodilo.
`--no-deps` to vypne, když si služby řídíš sám.

```bash
./cb-bond.py stop       # zastaví JEN cb-bond; logger a udpipe běží dál
./cb-udpipe.py stop     # ty se zastavují vlastními programy
./cb-logger.py stop
```

---

## Kam patří data

**Data nejsou v repozitáři.** Leží v jednom adresáři mimo něj, členěném podle
modulu. Repozitář se tím dá zkopírovat, zazálohovat i smazat nezávisle na
tom, co se v něm naměřilo — data přežívají kód a mají jiný životní cyklus.

```
/Users/j/Projects/conBondCorpus/        ← data_root
    corpus/                    2,6 MB   korpusy a otázky (sdílené všemi)
    cb_logger/persistent-log/  220 MB   záznamy
    cb_udpipe/persistent-cache/         rozbory vět (cache UDPipe)
    cb_udpipe/persistent-models/888 MB  model UDPipe + RobeCzech
    cb_bond/persistent-registry/        registr os
```

Adresu určuje **`data_root`, jediná absolutní cesta v konfiguraci**. Je
v každém modulu zvlášť a musí být ve všech stejná — pozor, klíč nesedí
ve stejné hloubce:

| soubor | kde klíč je |
|---|---|
| `cb_logger/cb-logger-config.json` | `data_root` (kořen) |
| `cb_udpipe/cb-udpipe-config.json` | `data_root` (kořen) |
| `cb_bond/cb-bond-config.json` | `module.data_root` |

*(Ta nesourodost je dluh z přestěhování dat 5. 8. 2026, ne záměr. Sjednotit
se má na kořen; do té doby platí tabulka.)*

Přenos instalace jinam je tedy změna jednoho řádku ve třech souborech.
Všechno ostatní je relativní vůči kořeni a nic si cestu nevyrábí za běhu.

Ověřit, kam který modul sahá, jde ze `status` — vypisuje `data_root`
schválně, protože bez toho člověk hledá chybu v datech, která služba vůbec
nečte:

```bash
./cb-logger.py status | grep data
./cb-bond.py corpus status        # co konkrétně leží v korpusovém adresáři
```

**Co ven nejde:** `run/` (PID a port — stav procesu, ne datum, mizí s ním)
a `cb_udpipe/vendor/` (zdrojáky UDPipe, tedy kód). Ty zůstávají v repozitáři.

---

## Instalace od nuly

### 1 · Prostředí

Projekt stojí na **Pythonu 3.11** a jednom sdíleném `.venv`. Do prostředí se
vstupuje **výhradně přes `./run-python`** — nikdy holým `python`:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run-python                      # bez argumentů vypíše stav prostředí
```

`./run-python` zaručí správný interpret, ověří závislosti proti
`requirements.txt` a dá kořen projektu na `PYTHONPATH`. Ovládací programy
(`./cb-*.py`) se na projektový interpret přepnou samy — zapsáno po chybě, kdy
služba běžela na 3.14 a testy na 3.11, takže se měřilo proti něčemu jinému,
než se tvrdilo.

### 2 · Datový kořen

```bash
mkdir -p /kam/chces/conBondCorpus
```

a do všech tří konfiguračních souborů zapsat `"data_root"` s touhle cestou.
Konfigurace se ověřuje **při startu** proti schématu, takže překlep je hlasitá
chyba, ne tiché nedorozumění.

### 3 · Model UDPipe (888 MB)

Model **nesmí do repozitáře** — je pod CC BY-NC-SA, tedy nekomerční
(podrobnosti v `ZDROJ.md`). Pořizuje se zvlášť:

```bash
git submodule update --init                    # zdrojáky UDPipe 2
./cb_udpipe/scripts/fetch-models.sh --check    # co chybí a kam patří
./cb_udpipe/scripts/fetch-models.sh --from-conbond2 ../conBond2
```

Skript cíl **čte z konfigurace**, takže vždy uloží tam, kam se služba dívá.
Stahování z LINDATu vědomě nedělá — ruční postup je v `cb_udpipe/README.md`.

### 4 · Korpusy

Korpusy jsou licencované a v gitu nejsou (`ZDROJ.md`). Patří do
`<data_root>/corpus/` jako `korpus-1NN.json` (2 912 vět, na nich jsou
naměřené zmražené hodnoty přejímek) a `korpus-2NN` / `korpus-3NN`
(dohromady 12 258 vět).

### 5 · Zkouška, že to sedí

```bash
./run-python -m unittest discover -s . -p "test_*.py" -t .   # 787 testů
./cb-bond.py start
./run-python cb_bond/scripts/prejimka-graf.py                # zmražené hodnoty
```

Přejímka musí dát přesně `16 074 hran · 5 695 lemmat · stupeň 5,6`. Když ne,
rozešlo se něco v datech — čísla jsou zmražená schválně.

---

## Z čeho se to skládá

| modul | co dělá | ovládá se | porty |
|---|---|---|---|
| `cb-logger` | strukturovaný log celého systému | `./cb-logger.py` | 42100 API · 42101 kukátko na text · 42102 na objekty |
| `cb-udpipe` | rozbor českých vět (vlastní instance UDPipe 2) | `./cb-udpipe.py` | 42200 API · 42201 UDPipe |
| `cb-field` | věta jako pole vážených aktivací na osách | knihovna | 42300 rezervováno (službou zatím není) |
| `cb-bond` | graf faktů, párování, odpověď, dialog | `./cb-bond.py` | 42400 API · 42401 okna |
| `cb-config` | načtení a ověření konfigurace | knihovna | — |

Adresář bez `cb-*.py` v kořeni je knihovna — nemá co obsluhovat.

Závislosti vedou jedním směrem: `cb-bond` → `cb-field` → `cb-udpipe`, a na
`cb-logger` a `cb-config` smí kdokoli. Cizí modul se volá **jen jeho
klientem** (`BondClient`, `UdpipeClient`, `LogClient`), nikdy importem
vnitřku.

---

## Kudy dál

| chci vědět | čti |
|---|---|
| proč je systém takhle navržený | `README-ARCHITECTURE_OVERVIEW.md` |
| pravidla, která platí pro každý modul | `README-MODULES.md` |
| jak se ptát a co znamená rozklad skóre | `README-BOND.md` |
| co je pole věty a jak vzniká | `README-FIELD.md` |
| jak se loguje a jak číst log | `README-LOGGER.md` |
| jak běží parser | `README-UDPIPE.md` |
| odkud data přišla a co s nimi smím | `ZDROJ.md` |

---

## Když se něco nedaří

| co vidíš | co s tím |
|---|---|
| `cb-bond nenaběhl do 300 s` | spusť `./cb-bond.py start --foreground` a uvidíš proč |
| `zdraví degraded` | služba běží, ale systém nemá postavený — nejčastěji chybí korpusy |
| `korpusový adresář … nedal žádný soubor` | `data_root` míří jinam, než si myslíš; ověř `./cb-bond.py corpus status` |
| okna na 42401 se neotevřou | `viewbase` není nainstalovaný; služba běží dál, jen bez oken (příkaz je ve výpisu startu) |
| přejímka končí nenulově | naměřené se rozešlo se zmraženým — **to je účel**, netlač to zpátky vahami |
