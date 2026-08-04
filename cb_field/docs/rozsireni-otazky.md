# Sebe-rozšíření otázky o vztahové entity — rozpracovaný návrh

Návrh J. (2026-08-04, večer), rozpracování s měřenými sondami.
**Nic z toho není zapnuté** — kroky čekají na odsouhlasení (vzor
handover-implementace.md).

## 1 · Zadání

Pro identifikaci kandidátů jsou kromě vertikál i další **vztahové
vazby**: křest–křtít (derivace), dálnice–silnice (nadřazený pojem).
**Otázka si sama zajistí rozšíření svého koše** o vztahové entity:
„Kolik se smí jezdit po dálnici?" nejdřív položí pod-otázku
„Co je to dálnice?" → „silnice pro motorová vozidla" — a celá tahle
výměna se **složí do koše otázky** a použije při tréninku.

Má tak dojít k **posílení — aktivaci oblasti kolem textu otázky**.
Při aplikaci generovaného vzoru NN pak **klouzavým oknem** nad textem
dojde k vypíchnutí faktu nebo věty nesoucí odpověď **gaussovskou
normálovou distribucí**.

Cíl zůstává: vybrat kandidátní věty, které obsahují odpověď; učení
generuje vazby s maximálním záchytem kandidátů a NN zobecňuje
(metadatový model, slova jen přes promoci).

## 2 · Sondy na korpusu 12 258 vět (naměřeno 2026-08-04)

**Definiční věty.** Kopulární vzor (root NOUN/PROPN + nsubj + cop)
dává **218 různých definovaných lemmat** — wikipedické úvody jsou
systematický zdroj definic:

    hudba   → systém   („Hudba je organizovaný systém zvuků…")
    opera   → druh     („Opera je druh západního divadla…")
    galaxie → systém   („Galaxie je gravitačně vázaný systém hvězd…")

**Překryv sousedství v grafu** (|A∩B| / min stupňů):

| dvojice | překryv | druh |
|---|---|---|
| křtít × pokřtěný | **0,44** | derivace |
| křest × křtít | 0,17 | derivace |
| hudba × hudební | 0,15 | derivace |
| stavba × stavět | 0,11 | derivace |
| zpěv × zpívat | 0,09 | derivace |
| hudba × galaxie | 0,10 | náhodná |
| dálnice × silnice | **0,00** | nadřazený pojem |

Dva závěry: (1) **samotný překryv sousedství nestačí** — zpěv×zpívat
je na úrovni náhodné dvojice; signál vznikne až složením se
**slovotvorným kmenem** (derivační dvojice sdílejí začátek lemmatu —
vážený součin, ne práh). (2) **Nadřazený pojem v sousedství není
vůbec** (0,00) — hyponymie musí přijít z definičních vět, ne z grafu
souvýskytů. Návrh proto stojí na dvou zdrojích vztahů, každý na svůj
druh.

## 3 · Mechanismus (kroky k odsouhlasení)

### Krok A · Definiční hrany

Kopulární vzor se čte jako **vztahová vazba subjekt → predikátové
jméno** se zdrojem `definice`: `dálnice → silnice` (z dialogové věty
kroku 4 už dnes vzniká jako hrana grafu `nsubj`). Krok ji povyšuje
na vazbu v registru (vážená hrana, váhu doladí učení), aby po ní
teklo šíření. Přejímka: z korpusu vznikne ~218 definičních vazeb;
`dálnice → silnice` vznikne z věty dialogu; bez zapnutí se nezmění
žádné dnešní číslo.

### Krok B · Sebe-rozšíření koše otázky

Nová funkce `expand_question(question, corpus, graph)`:

1. pro každou danou obsahovou osu otázky se hledá **definiční věta**
   (kopulární hrana v grafu / korpusu);
2. když není, položí se pod-otázka `Co je to X?` přes `reply()` —
   outcome `needs_context` ji pošle do dialogu (krok 4 mechanika,
   žádná nová větev);
3. koš pod-otázky **a koš vítězné definiční věty** se PŘIČTE do koše
   otázky s vahou `W_EXPAND` (vážený člen, ne filtr) — tím se
   aktivuje OBLAST kolem textu otázky, ne bod.

Hloubka expanze na start 1 (parametr; řetězení definic je měřitelné
rozšíření, ne výchozí stav). Přejímka: „Kolik se smí jezdit po
dálnici?" po rozšíření zvýší pokrytí a `sentence_hit` na větách
o silnici; měří se před/po na etalonu, s protiváhou (NEVÍM, dosah).

### Krok C · Trénink nad rozšířeným košem

Expanze běží PŘED stavbou učicího pytle otázky — „taková otázka se
skládá celá do koše otázky a použije se při tréninku." Platí
metadatový model: z definiční věty vstupují metadata a promované
CUSTOM= osy, ne surová slova. Validace 30 % hlídá, že rozšíření
zobecňuje a nekupuje si trénink; učicí smyčka s odvoláním epochy
už existuje.

### Krok D · Gaussovské vypíchnutí odpovědi

Výstupní čtení pole: vygenerovaný vzor (koš rozšířené otázky) se
aplikuje klouzavým oknem a aktivační pole se čte **gaussovským
profilem** N(centrum, σ) — vedle dnešního 1/(1+d). Kandidátní
věta/fakt = lokální maximum vyhlazeného pole (integrál zvonu přes
větu), takže odpověď „svítí" jako oblast s normálovým rozdělením,
ne jako osamělý token. σ je parametr ke kalibraci měřením; tokenové
i větné čtení se uvádějí vedle sebe (§ B5).

## 4 · Rizika a pojistky

- **Rozšíření = víc šumu v koši.** Řeší váha `W_EXPAND` a protiváhy
  v měření (přesnost × NEVÍM × dosah); zhoršení kterékoli metriky
  cyklus odvolává.
- **Řetězení pod-otázek donekonečna.** Hloubka 1 jako výchozí,
  hlubší expanze jen s naměřeným přínosem.
- **Definiční vzor chytí i nedefinice** („Asynchronní motor je …
  elektromotorem"). Není to filtr, ale váha — nepřesná definice
  přidá slabý člen, měření rozhodne.

## 5 · Otevřená rozhodnutí (J.)

1. Váha `W_EXPAND` (startovní hodnota, učitelnost).
2. Kdy klást pod-otázku dialogem (uživateli) vs. jen korpusem.
3. Vztah kroku D k dnešnímu profilu okna 1/(1+d): nahradit, nebo
   vést vedle sebe jako druhé čtení.
4. Derivační vazby: stačí kmen × překryv sousedství z grafu, nebo
   počkat na typy vztahů z rozpočtu 328?
