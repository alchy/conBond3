# cb-bond — vývojářské README

Jak se z otázky v české větě dostat ke **kandidátním větám, které nesou
odpověď** — a jak si nechat ukázat, čím se to rozhodlo. Všechny ukázky
jsou spustitelné a ověřené; zkopíruj a jeď.

Tohle je jen to nejnutnější. Hloubka je v `cb_bond/docs/`:

| soubor | co v něm je |
|---|---|
| `docs/zadani.md` | zadání celé stavby: deset kroků, zmražené přejímky, páky |
| `docs/koncepce.md` | proč je modul postavený takhle a ne jinak |
| `docs/metody.md` | každá veřejná metoda: co dělá, proč existuje, na čem visí |
| `docs/prirucka.md` | otázky ze stavby a pasti, do kterých se dá spadnout |
| `docs/rozklad-skore.md` | z čeho se odpověď skládá a jak číst členy skóre |
| `docs/trenink-vah.md` | jak zjistit, co se model naučil |
| `cb_bond/README.md` | rozhraní, závislosti, co modul vědomě neřeší |

**Stav: služba.** Modul má konfiguraci, REST API, klienta, ovládací
program, čtyři okna viewBase2 na portu 42401 a logování do cb-loggeru.

---

## Než začneš

```bash
./cb-bond.py start                        # zvedne i logger a udpipe pod sebou
./cb-bond.py status                       # co je v hlavě: vět, hran, lemmat, os
./run-python cli                          # konzole — nikdy holé `python`
```

`start` je jediný příkaz, který potřebuješ: cb-bond je vrcholová služba
a spustí si logger a udpipe sám, v tomhle pořadí (udpipe do loggeru
loguje už při vlastním startu). `--no-deps` to vypne, když si služby
řídíš sám.

Korpusy leží **mimo repozitář** (licence, `ZDROJ.md`) v datovém kořeni —
`module.data_root` v `cb_bond/cb-bond-config.json`, dnes
`/Users/j/Projects/conBondCorpus/corpus/`. Kde přesně, řekne
`cb_bond.config.corpus_dir()`; skripty se ptají tudy a cestu nehádají.
Bez korpusů fungují jen jednotkové testy, ne měřicí skripty.

## Přes službu to jsou dva řádky

Když cb-bond běží, nemusíš stavět nic — systém je postavený v něm.

```python
from cb_bond import BondClient

odpoved = BondClient().ask("Kde byl pokřtěn Ježíš?", top=3)

odpoved["answer"]           # 'říci'  — lemma, nebo None, když mlčí
odpoved["outcome"]          # 'answer' | 'silent' | 'needs_context'
odpoved["decomposition"]    # {'meet': 1.23, 'cover': 0.60, 'topic': 0.54, …}
odpoved["sentences"]        # [{'lemma': …, 'text': …, 'score': …}, …]
odpoved["axes"]             # osy otázky a jak dobře je korpus zná:
                            #   WORD=AUX:být        1.000
                            #   WORD=ADJ:pokřtěný   0.604
                            #   WORD=PROPN:Ježíš    0.885
odpoved["missing"]          # osy s pokrytím PŘESNĚ 0.0 — tady []
```

`missing` je propast, ne škála: osa, kterou korpus vůbec nezná, dá
přesnou nulu. Na tom stojí „nevím" — pozná se podle nuly, ne podle
prahu na malém čísle.

Součet členů `decomposition` dá `score` — je to rozklad, ne komentář
vedle čísla. Co který člen znamená, je v `docs/rozklad-skore.md`.

Totéž přes REST:

```bash
curl -s http://127.0.0.1:42400/v1/ask \
     -H 'Content-Type: application/json' \
     -d '{"text": "Kde byl pokřtěn Ježíš?", "top": 3}'

curl -s http://127.0.0.1:42400/v1/state    # vět, hran, lemmat, os, vazeb
curl -s http://127.0.0.1:42400/v1/health   # 'ok' vs 'degraded'
```

`degraded` znamená, že služba běží, ale systém nemá postavený — port
odpovídá a v hlavě nic není. `POST /v1/ask` na takovou službu vrátí
`503 not_built`, ne prázdnou odpověď: prázdná by se slila s platným
„nevím" a to jsou dvě různé věci.

## Bez služby to jsou čtyři řádky

Skripty přejímek si systém staví přímo — měření nemá viset na tom,
jestli zrovna něco běží.

```python
from cb_udpipe import UdpipeClient
from cb_field import SentenceField
from cb_field.corpusfile import build_corpus
from cb_bond import GraphRecall, KnowledgeGraph, Matcher, Responder
from cb_bond.config import corpus_dir

parser = UdpipeClient()
corpus = build_corpus(
    sorted(corpus_dir().glob("korpus-1*.json")),
    parser, r=1)                                  # 2 912 vět, ~5 s z cache

graf = KnowledgeGraph()
for pole in corpus:
    graf.add_sentence(pole)                       # 16 074 hran

matcher = Matcher(corpus, spread_depth=1, theta=0.0,
                  graph_recall=GraphRecall(graf, corpus, depth=2))
otazka = SentenceField.from_text("Kde byl pokřtěn Ježíš?", parser, r=1,
                                 registry=corpus.registry)
vysledek = matcher.match(otazka)
vysledek.best.lemma                               # 'říci' — nejlepší TOKEN
```

**Otázka musí být pole nad TÝMŽ registrem** (`registry=corpus.registry`).
Bez toho se porovnávají různé osy a výsledek je nesmysl.

Ta odpověď je zároveň nejlepší ukázka toho, kde systém dnes stojí:
`match()` vrací **tokeny**, a nejlepší token je vedle. Věty na tom jsou
líp — přečti si je gaussovsky:

```python
from cb_bond import AnswerField

veta, vrchol, index = AnswerField(vysledek).gaussian_peaks()[0]
corpus[veta].source
# 'V těch dnech přišel Ježíš z Nazareta v Galileji a byl v Jordánu
#  od Jana pokřtěn.'                      ← správná věta, první
```

**Systém rozumí větě, ne roli.** Najde větu s odpovědí, ale vybrat z ní
správné slovo se teprve učí (`docs/rozklad-skore.md` § 5).

## Čtyři čtení téhož pole

Odpověď JE pole; token, okno, věta a vrchol jsou jen různé hrubosti.

```python
pole = AnswerField(vysledek)
pole.tokens()[:3]           # nejjemnější: kandidáti podle skóre
pole.spans(width=2)[:3]     # okna: (věta, počátek, součet)
pole.sentences()[:3]        # (věta, součet pole)
pole.gaussian_peaks()[:3]   # (věta, vrchol, index) — DOPORUČENÉ
```

Gaussovské čtení je to, které chceš: shluk souhlasných aktivací poráží
osamělou špičku, takže krátké věty nevyhrávají normalizací.

## Čím se to rozhodlo

```python
kandidat = vysledek.best
kandidat.decomposition()
# {'meet': 1.23, 'cover': 0.60, 'topic': 0.54,
#  'given': -0.00, 'fit': 0.0, 'spectral': 0.0}
```

Skóre je prostý součet vážených členů — žádná brána, žádný filtr. Dva
členy (`meet`, `given`) řadí TOKENY uvnitř věty, tři (`cover`, `topic`,
`spectral`) řadí VĚTY. Podrobně v `docs/rozklad-skore.md`.

Váhy jsou páky: `Matcher(weights=ScoreWeights(topic=0.0))` vypne téma,
neodstraní větev v kódu.

## Dialog: když systém neví, zeptá se

```python
from cb_bond import Responder

responder = Responder(matcher, graf)
reply = responder.reply(otazka)
reply.outcome        # 'answer' | 'ask' | 'needs_context' | 'silent'
reply.missing        # ['WORD=NOUN:dálnice'] — osy s PŘESNOU nulou
reply.lemma          # odpovídá VŽDY, i když hlásí needs_context

responder.append_context("Dálnice je silnice pro motorová vozidla.", parser)
# korpus +1 věta (zdroj dialog) · graf +N hran · mezera se zavře
```

Mezera je **přesná nula**, ne práh: osa známá slabě má 0,604, neznámá
0,000. Mezi tím je propast, takže se mezera pozná bez kalibrace.

## Co si spustit

| co chceš | čím |
|---|---|
| ověřit, že graf sedí | `./run-python cb_bond/scripts/prejimka-graf.py` |
| vidět, čím se rozhodly odpovědi | `./run-python cb_bond/scripts/rozklad-skore.py 8` |
| natrénovat a podívat se na váhy | `./run-python cb_bond/scripts/trenink-vah.py` |
| změřit celý systém po ramenech | `./run-python cb_bond/scripts/protokol.py` |
| živý graf a okna | `./cb-bond.py start` → http://127.0.0.1:42401 |
| konzole nad běžící službou | `./run-python -m cb_bond.console` |

Skripty, jejichž jméno začíná `prejimka-`, **nic nemění** a končí
nenulově, když se naměřené rozejde se zadáním. `trenink-vah.py`
a `protokol.py` naopak **učí a promují** — jméno to říká schválně.

## Nejčastější omyly

**Otázka nad jiným registrem než korpus.** Sloupec 12 pak znamená
v každém poli něco jiného. Vždycky `registry=corpus.registry`.

**Čekat, že `match()` vrátí větu.** Vrací kandidátní TOKENY seřazené
podle skóre. Věty z toho udělá `AnswerField.gaussian_peaks()`.

**Číst `sentences()` jako hlavní čtení.** Součet přes větu zvýhodňuje
dlouhé věty — proto je doporučené gaussovské.

**Spustit `protokol.py` a čekat rychlý výsledek.** Učí a promuje, běh
je v minutách; průběh se hlásí na stderr.

**Holé `python`.** Vždycky `./run-python`, jinak běží jiný interpret
s jinými závislostmi.
