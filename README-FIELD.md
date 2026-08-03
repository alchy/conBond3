# cb-field — vývojářské README

Jak z české věty udělat **pole**: vážené aktivace, koše posuvného okna
a matice, se kterými se dá počítat. Všechny ukázky jsou spustitelné
a ověřené; zkopíruj a jeď.

Tohle je jen to nejnutnější. Hloubka je v `cb_field/docs/`:

| soubor | co v něm je |
|---|---|
| `docs/koncepce.md` | proč je modul postavený takhle a ne jinak |
| `docs/metody.md` | každá veřejná metoda: co dělá, proč existuje, na čem visí |
| `docs/prirucka.md` | otázky ze stavby a pasti, do kterých se dá spadnout |
| `cb_field/README.md` | rozhraní, porty, prahy, závislosti modulu |

**Stav: mockup.** Modul zatím nemá vlastní REST API, logování ani
konfiguraci (doplní se podle README-MODULES § 16). Používá se importem.

---

## Než začneš

```bash
./cb-udpipe.py status               # parser vět musí běžet
./run-python -m cb_field.viewer     # volitelně: obrazovka pole (127.0.0.1:42301)
./run-python cli                    # konzole — nikdy holé `python`
```

## Celé to jsou čtyři řádky

```python
from cb_udpipe import UdpipeClient
from cb_field import SentenceField

parser = UdpipeClient()             # jednou při startu programu
sentence = SentenceField.from_text("Kde byli psi a kdy se vrátí?", parser)
sentence.array                      # matice vah (8 slov × N vertikál)
sentence.show()                     # obrázek na http://127.0.0.1:42301/
```

`SentenceField` je pracovní úroveň — jedna konstrukce udělá vše:

```
SentenceField(8 tokenů, r=2, question=True, registr 38 vertikál)
```

- pozná **otázkovost** věty (otazník) a promítne ji do všech aktivací,
- postaví **koše** posuvného okna (r=2, jeden na token),
- rozvine **vážené aktivace** každého slova,
- zrodí **registr vertikál** s kotevní hierarchií.

**Pole = jedna věta.** Text s více větami je `ValueError` — rozděl ho
a stav pole na každou větu zvlášť. Máš-li už rozebranou větu, použij
`SentenceField.from_sentence(s)`.

---

## Tři pohledy — na věte i na koši stejné

| pohled | co vrací | k čemu |
|---|---|---|
| `.metadata` | aktivace bez slov — `{vertikála: váha}` na řádek | čtení okem, bezeslovná reprezentace (primární) |
| `.complete` | totéž + `WORD=<UPOS>:<lemma>` | když je potřeba i slovo („Petr") |
| `.array` | matice vah `float32` | počítání; bezeslovná |

```python
sentence.metadata[0]        # aktivace slova „Kde"
# {'UPOS=ADV': 0.7, 'DEPREL=root': 0.7, 'PronType=Int': 0.7,
#  'PronType=Rel': -0.7, 'QLEM=ADV:kde': 0.7, 'SUBPOS=Db': 0.7,
#  'QANCHOR=space:loc': 0.7}

sentence.complete[0]        # navíc jen {'WORD=ADV:kde': 0.7}
sentence.array.shape        # (8, 85) — 8 slov × 85 vertikál
```

Z COMPLETE jde METADATA vždy odvodit; **obráceně ne** — co se do
bezeslovné podoby nezapsalo, už nikdo nezrekonstruuje. Obecná metoda:
`sentence.matrix(Representation.COMPLETE)`.

## Koše (baskets)

Koš = zastavení posuvného okna: slovo + okolí do vzdálenosti r.

```python
sentence.baskets[1]                 # FieldBasket(center=1 'byli', r=2, 4 řádků)
sentence.baskets[1].center_token.form   # 'byli'
[t.form for t in sentence.baskets[1].rows]   # ['Kde', 'byli', 'psi', 'a']

sentence.baskets[1].metadata        # táž trojice pohledů jako u věty
sentence.baskets[1].complete
sentence.baskets[1].array           # (5, 85) — VŽDY 2r+1 řádků
```

Slovníkové pohledy ukazují jen skutečné řádky věty (na kraji 3–4);
`array` má **pevný tvar**: za hranicí věty nulové řádky (0.0 = žádná
aktivace), střed vždy na řádku `r`. Koše jsou tak tvarově porovnatelné.

## Co znamenají váhy

Každá aktivace je `hodnota@váha`. Váha se rodí na **0.7**, žije
v rozsahu **−1.0 … +1.0** a znaménko nese druh vazby: kladná =
pozitivní, **záporná = negativní vazba** (hodnota působí proti).
Nula = žádná aktivace, proto se nuly nikde neukládají ani nekreslí.

```python
sentence.activations[1].get('ANCHOR=time:past')     # 0.7
sentence.activations[1].set('ANCHOR=time:past', 0.9)  # hlídá rozsah
```

## Vertikály — co může svítit

| skupina | příklad | odkud |
|---|---|---|
| `UPOS=`, `DEPREL=` | `UPOS=NOUN`, `DEPREL=nsubj` | rozbor |
| feats `Klíč=Hodnota` | `Case=Gen`, `Gender=Fem` | rozbor; multiatribut (`Fem,Neut`) dá dvě vertikály |
| `SUBPOS=` | `SUBPOS=Db`, `SUBPOS=P7` | poziční tag — třídy, které feats nemají |
| `LEM=` | `LEM=ADP:do`, `LEM=ADV:tam` | lemma zavřené třídy — strana odpovědi |
| `QLEM=` | `QLEM=ADV:kde` | tázací slovo v tázací větě — strana otázky |
| `ANCHOR=` | `ANCHOR=time:past`, `ANCHOR=quantity:plur` | kotvy: ukotvení v prostoru/čase/množství/entitě |
| `QANCHOR=` | `QANCHOR=space:loc` | co otázka poptává (kde=poloha, kam=cíl…) |
| `WORD=` | `WORD=PROPN:Petr` | jen v COMPLETE — lexikální obsah |

Klíče LEM/QLEM/WORD nesou i UPOS (`LEM=ADV:jak` ≠ `LEM=SCONJ:jak` —
spojkové „jak" je jiné „jak"). Kotvy jdou po smyslu, ne po tvaru:
dokonavý prézens „přijde" kotví `time:fut`; „nikdy" kotví `time`
záporně; „byli" kotví čas i množství najednou.

## Registr a párování otázky s odpovědí

Osu sloupců drží **registr** — append-only: jednou přidělený index se
nikdy nemění. Sdílí se přes věty parametrem:

```python
from cb_field import VerticalRegistry
reg = VerticalRegistry()
q = SentenceField.from_text("Kdy se psi vrátí?", parser, registry=reg)
a = SentenceField.from_text("Psi se vrátí zítra.", parser, registry=reg)
q.array; a.array                     # první čtení nechá registr dorůst
q.array.shape[1] == a.array.shape[1] # True — společné osy
# (šířka matice = registr v okamžiku čtení; po přečtení obou jsou stejné)

reg.key(30)                  # sloupec → vertikála
reg.save("cb_field/data-persistent/verticals.json")
```

Registr nese i **vážené vazby** mezi vertikálami (hierarchie kotev:
`ANCHOR=time:fut →1.0→ ANCHOR=time`). Párování je pak jeden krok šíření
aktivace a skalární součin:

```python
import numpy as np
qv = reg.spread(q.array[0])          # „Kdy" (QANCHOR=time:when)
av = reg.spread(a.array[2])          # „vrátí" (ANCHOR=time:fut)
float(np.dot(qv, av))                # > 0 — potkaly se v uzlu ANCHOR=time
```

## Obrazovka pole (viewer)

```bash
./run-python -m cb_field.viewer      # http://127.0.0.1:42301/
```

`sentence.show()` publikuje větu; stránka se obnovuje sama. Tři pohledy:
**kompletní** (se slovy) · **jen atributy** (bezeslovné) · **matrix**
(jen čísla vah, záporné červeně). Nahoře věta jako pole, pod ní
jednotlivé koše se svisle zarovnanými sloupci.

## Pod kapotou (ladicí vrstvy)

Nižší vrstvy jsou veřejné, ale běžně je nepotřebuješ:

```python
from cb_field import build_baskets, expand_basket, activations, MetaValue
```

`build_baskets` (syrové koše z tokenů), `expand_token/expand_basket`
(vážené řádky se sloty), `activations(row, question)` (pravidla
vertikál na jednom místě). Viz `docs/metody.md`.

## Nejčastější omyly

| omyl | správně |
|---|---|
| `python skript.py` | `./run-python skript.py` — jinak jiný interpret |
| pole z textu o více větách | `ValueError`; rozděl text po větách |
| každá věta vlastní registr a pak porovnávání matic | sdílený registr parametrem `registry=` |
| vektor uložený dnes, čtený proti jinému registru | registry se ukládají (`save/load`) a indexy se nikdy nepřečíslují — používej týž soubor |
| „chybí mi hodnota, dám None/NaN" | v matici není NULL; 0.0 = žádná aktivace a nic jiného tam nepatří |
| váha 1.5, „ať to víc váží" | rozsah je −1…+1 a hlídá se hned při zápisu |
