# cb-udpipe — vývojářské README

Jak si z kódu nechat rozebrat větu. Všechny ukázky jsou spustitelné a ověřené;
zkopíruj a jeď.

Tohle je jen to nejnutnější. Hloubka je v `cb_udpipe/docs/`:

| soubor | co v něm je |
|---|---|
| `docs/koncepce.md` | proč je modul postavený takhle, včetně všech měření |
| `docs/metody.md` | každá metoda: co dělá, proč existuje, na čem visí |
| `docs/prirucka.md` | otázky, které padly při stavbě, a pasti |
| `cb_udpipe/README.md` | rozhraní, porty, prahy, závislosti |

---

## Než začneš

```bash
./cb-udpipe.py start        # zvedne UDPipe i službu
./cb-udpipe.py status       # ověření + porty
```

| adresa | co tam je |
|---|---|
| `http://127.0.0.1:42200` | REST API |
| `http://127.0.0.1:42201` | vlastní instance UDPipe 2 |

První start trvá **desítky sekund**: UDPipe načítá model o 357 MB a
předehřívá síť. Další jsou rychlejší jen o to předehřátí.

Když služba neběží, klient to řekne **při vytvoření**, ne až u prvního
rozboru — jinak by ses to dozvěděl uprostřed dávky s polovinou zapsaných
výsledků.

---

## Rozbor věty

```python
from cb_udpipe import UdpipeClient

parser = UdpipeClient(endpoint="http://127.0.0.1:42200")
vysledek = parser.parse(text="R.U.R. je drama Karla Čapka.", trace="q-7f3a91")

for veta in vysledek.sentences:
    print(veta.source, "| z cache:", veta.from_cache)
    for t in veta.tokens:
        print(" ", t.form, t.lemma, t.upos, t.deprel)
```

```
R.U.R. je drama Karla Čapka. | z cache: False
  R.U.R. R.U.r. PROPN nsubj
  je být AUX cop
  drama drama NOUN root
  Karla Karel PROPN nmod
  Čapka Čapek PROPN flat
  . . PUNCT punct
```

Všimni si, že `R.U.R.` je **jeden token** a `PROPN`. Bez opravy tokenizace by
z něj UDPipe udělal šest tokenů a podmětem věty by bylo poslední písmeno `R`.

---

## Co se vrací

```python
vysledek.sentences      # věty v pořadí vstupu
vysledek.cached         # kolik jich přišlo z cache
vysledek.parsed         # kolik se jich muselo rozebrat
vysledek.skipped        # věty přes mez serveru, s důvodem
```

U každé věty:

| pole | co v něm je |
|---|---|
| `source` | text věty tak, jak stojí v dokumentu — **klíč cache** |
| `tokens` | tokeny se všemi deseti sloupci CoNLL-U |
| `multiword` | víceslovné tvary (`Abys` = `Aby` + `bys`) |
| `from_cache` | přišla z cache, nebo se rozebírala? |
| `retokenized` | kolik oprav tokenizace v ní modul udělal |

U každého tokenu je `id`, `form`, `lemma`, `upos`, `xpos`, `feats`, `head`,
`deprel`, `deps` a `misc`. `feats` a `misc` jsou **slovníky**, ne seznamy
řetězců:

```python
veta = vysledek.sentences[0]
veta.tokens[0].feats    # {'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc',
                        #  'NameType': 'Giv', 'Number': 'Sing'}
veta.tokens[0].misc     # None        ← za tokenem je mezera
veta.tokens[0].space_after   # True

veta.tokens[-2].misc         # {'SpaceAfter': 'No'}   ← před tečkou mezera není
veta.tokens[-2].space_after  # False
```

`misc` je `None`, když token žádnou poznámku nenese — „nemá hodnotu" je stav,
ne prázdný slovník. Z `space_after` se skládá původní text zpátky.

---

## Co modul opravuje

Změřeno na korpusu: **17,6 % vět** vypadá po opravě jinak.

| vstup | UDPipe sám | s cb-udpipe |
|---|---|---|
| `R.U.R. je drama.` | `R . U . R .` | `R.U.R.` |
| `ve 20. století` | `20 \| .` | `20.` |
| `tzv. obrození` | `tzv \| .` | `tzv.` |
| `30 000 dělnic` | `30 \| 000` | `30 000` |
| `hodnota 3,14` | `3 \| , \| 14` | `3,14` |

Poslední dva řádky nejsou kosmetika: UDPipe dá z `30 000` **dvě samostatná
čísla**, takže vrstva, která počítá, naměří `30`.

**Text věty se nikdy nemění**, jen hranice tokenů. `source` zůstává tím, co
stálo v dokumentu.

---

## Jen tokenizace, bez tagů

Když stačí hranice vět a tokenů, je to řádově levnější — UDPipe při něm vůbec
nenačte síť:

```python
vety = parser.tokenize_only(text="R.U.R. je drama. Petr spí.")
print(len(vety), [t.form for t in vety[0].tokens])
```

```
2 ['R.U.R.', 'je', 'drama', '.']
```

Měřeno: tokenizace stojí **2,7 %** času, který zabere plný rozbor.

Do cache se **nezapisuje** — tokenizace bez tagů není rozbor a uložit ji by
znamenalo, že příští zásah vrátí věty bez značek.

---

## Cache

Rozbory se pamatují napořád, klíčem je **text věty + model + verze
tokenizéru**. Druhý průchod týmiž daty je **27× rychlejší**.

```python
prvni = parser.parse(text="Petr je v Praze.")
druhy = parser.parse(text="Petr je v Praze.")
print(prvni.sentences[0].from_cache, druhy.sentences[0].from_cache)
```

```
False True
```

Změna pravidel tokenizace cache **neznehodnotí**: staré záznamy zůstanou
platné pro svou verzi a nové se doplní vedle nich. Proto je verze tokenizéru
součástí klíče.

Soubor je čitelný očima, jeden JSON objekt na řádek:

```bash
head -1 cb_udpipe/data-persistent/cache/cs_all-ud-2.17-251125.jsonl | python3 -m json.tool | head -20
```

---

## Stopa (`trace`)

Drží pohromadě jeden průchod systémem. **Modul ji nikdy nerazí**, jen přebírá:

```python
parser.parse(text="Petr je v Praze.", trace="q-7f3a91")
```

Kdyby si ji razil každý modul, rozpadl by se řetěz na tolik kusů, kolik je
modulů — a to je horší než žádná stopa, protože to vypadá, že funguje.

---

## Když něco nefunguje

```python
from cb_udpipe import ServiceUnavailable, IncompatibleApi
```

| situace | co se stane |
|---|---|
| služba neběží | `ServiceUnavailable` **při vytvoření klienta**, hláška uvádí adresu i příkaz ke spuštění |
| služba běží, UDPipe ne | `ServiceUnavailable` při volání; služba vrací `503` |
| služba mluví jinou verzí | `IncompatibleApi` při vytvoření |
| prázdný vstup | **není chyba** — vrátí se prázdný seznam vět |
| věta přes 1000 slov | přeskočí se s důvodem v `skipped`, zbytek projde |

Prázdný výsledek a chyba se **nikdy neslévají**. Kdyby se slily, přenesl by se
ten problém do každého volajícího.

---

## Nejčastější omyly

| omyl | co se stane | jak správně |
|---|---|---|
| klient v cyklu | kontrola služby při každém průchodu | jeden klient při startu, předávaný parametrem |
| poziční argumenty | `TypeError` | všechny parametry se pojmenovávají: `parse(text=…)` |
| spoléhat na `sent_id` z cache | není zaručené napříč průchody | pořadí ve `sentences` odpovídá vstupu |
| scelovat jména v cb-udpipe | není to jeho práce | `Karel Čapek` jsou dva tokeny; entitní vrstva je jinde |
| měřit zrychlení nad plnou cache | vyjde 1,0× | před měřením smaž cache, viz `scripts/mereni.py` |

---

## Kontrola, že to funguje

```bash
./cb-udpipe.py status
curl -s http://127.0.0.1:42200/v1/summary | python3 -m json.tool
curl -s http://127.0.0.1:42200/v1/cache/stats | python3 -m json.tool
```

```bash
curl -s -X POST http://127.0.0.1:42200/v1/parse \
  -H 'Content-Type: application/json' \
  -d '{"text":"R.U.R. je drama Karla Čapka."}' | python3 -m json.tool
```
