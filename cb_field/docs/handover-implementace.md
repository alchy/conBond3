# Implementace dialogového učení — handover po krocích

Rozpracování návrhu z `dialog-graf.md` do kroků, které jdou dělat
a měřit jeden po druhém. Každý krok je samostatný: dokud se nezapne,
nic nemění. Odsouhlasené kroky se sem zapisují postupně (J.).

Řada kroků:

1. **Graf faktů jako vrstva** — uzly a hrany ze závislostí, statistika
   stupně a poměru · *odsouhlaseno 2026-08-04*
2. **Promoce do custom vertikál** — `promote_verticals()`, limit 328,
   kritérium různých²/hran, vratná · *odsouhlaseno 2026-08-04*
3. Verze osy a invalidace — ošetření přeobsazeného sloupce
4. Přeučení po promoci — s odvoláním kola, které uškodí
5. Detekce mezery a dialog — „nemám rychlost, doplň kontext"
6. Odpověď jako věta — zapojit úroveň, která už měřením funguje
7. Náhled — které uzly se rozsvítily

---

## Krok 1 · Graf faktů jako vrstva

**Co vzniká.** Nový modul `cb_field/graph.py` s třídou `FactGraph` —
samostatná vrstva vedle registru, ne uvnitř něj. Registr zůstává osou
systému, graf je paměť faktů. Míchat je dohromady by znamenalo, že se
konkrétní svět dostane do os dřív, než o tom rozhodne promoce.

**Co v něm je.** Uzel = lemma se slovním druhem (`NOUN:rok`). Hrana =
závislost mezi dvěma obsahovými uzly, nesoucí `deprel`, váhu a **zdroj**
(`text` / `dialog`) — táž trojice jako u vazeb v registru, aby se s tím
dalo zacházet jednotně a šlo dialogové hrany kdykoli odlišit od
korpusových.

**Co umí.** Přijmout větu (`add_sentence`) a vydat statistiku na uzel:
počet hran, počet různých sousedů a jejich **poměr** — diskriminátor
obecnosti naměřený 2026-08-04. Nic víc: žádná promoce, žádný zásah do
párování. Krok jde vypnout tím, že se nezavolá.

**Co záměrně nedělá.** Neřeší koreference (uzel „on" je vlastní uzel,
ne odkaz), neslučuje synonyma, nesahá na skóre. To je práce pozdějších
kroků; smíchat to sem by znemožnilo měřit, co za co může.

### Příklad na reálných datech

Věta z korpusu (bible_markus), na které stojí celý dnešní rozbor:

> V těch dnech přišel Ježíš z Nazareta v Galileji a byl v Jordánu
> pokřtěn od Jana.

**Uzly (8):** `den`, `přijít`, `Ježíš`, `Nazareto`, `Galilej`,
`Jordán`, `pokřtěný`, `Jan`

**Hrany (7):**

    Ježíš     --nsubj----> přijít
    den       --obl------> přijít
    Nazareto  --obl------> přijít
    Galilej   --obl------> přijít
    pokřtěný  --conj-----> přijít
    Jordán    --obl------> pokřtěný      ← nese odpověď
    Jan       --obl:arg--> pokřtěný

**Uzlem se nestanou:** `V`, `těch`, `z`, `v`, `a`, `byl`, `od`, `.` —
předložky, determinátor, spojka, pomocné sloveso a interpunkce. To nese
gramatika a graf by je držel podruhé.

**Proč je to zajímavé pro naši potíž.** Párování dnes neodliší `Jordán`
(2,088) od `Galileje` (2,068), protože obojí je „místo v téže větě".
Graf je odlišuje **strukturně a bez jediné váhy**: `Jordán` visí na
`pokřtěný`, `Galilej` na `přijít`. Otázka „Kde byl pokřtěn Ježíš?" míří
na `pokřtěný`, takže po hraně vede k Jordánu a ke Galileji ne. To je ta
správná hrana, na kterou má systém zaostřit — v datech je, jen ji
dnešní pytel zahazuje, protože v koši leží obojí stejně blízko.

**Mez kroku 1** je na téže větě vidět taky: `Jan` visí na `pokřtěný`
úplně stejnou hranou jako `Jordán` (obě `obl`), takže na otázku „Kdo
pokřtil Ježíše?" by graf sám nestačil — rozlišit je musí typ uzlu
(`Jan` osoba, `Jordán` místo), což dodává patro kotev. Krok 1 nemá
ambici odpovídat; staví strukturu, na které to půjde.

### Jak se ověří, že funguje

- test na zmražené scéně: graf o známém tvaru dá známé stupně;
- přeběhnutí korpusu musí zopakovat naměřená čísla ze 4. 8. 2026 —
  **5 695 uzlů, 16 074 hran, průměrný stupeň 5,6**, průměr různých
  sousedů 4,6, `rok` s poměrem 0,85 a `Ježíš` s 0,54.

Když se čísla rozejdou, je chyba v implementaci, ne v konceptu.

### Referenční statistika (korpus 2 912 vět, 4. 8. 2026)

| uzel | různých sousedů | hran | výskytů | poměr |
|---|---|---|---|---|
| mít | 185 | 260 | 118 | 0,71 |
| říci | 177 | 308 | 160 | 0,57 |
| rok | 162 | 191 | 93 | **0,85** |
| jít | 129 | 174 | 78 | 0,74 |
| přijít | 124 | 168 | 71 | 0,74 |
| moci | 119 | 147 | 60 | 0,81 |
| stát | 85 | 93 | 42 | **0,91** |
| stroj | 79 | 144 | 81 | 0,55 |
| Karel | 75 | 152 | 70 | **0,49** |
| začít | 62 | 67 | 30 | **0,93** |
| Ježíš | 60 | 111 | 106 | **0,54** |
| Bohumil | 60 | 120 | 55 | **0,50** |

Poměr různých sousedů k počtu hran odděluje obecné od konkrétního:
vysoký (0,81–0,93) znamená, že skoro každá hrana jde jinam, tedy uzel
nese **tvar** (`začít`, `stát`, `rok`); nízký (0,49–0,55) znamená
opakované hrany do týchž míst, tedy **konkrétní svět** (`Karel`,
`Ježíš`, `Bohumil`). `Ježíš` má nejvíc výskytů (106) a přesto poměr
0,54 — frekvence ani rozmanitost samy vlastní jména neodfiltrují,
poměr ano.

---

## Krok 2 · Promoce do custom vertikál

**Co vzniká.** Funkce `promote_verticals()` — vezme statistiku
z `FactGraph` a vrátí, které uzly se mají stát **custom vertikálami**.
Žije vedle grafu; registr jen dostává hotový cílový stav osy k zapsání.

**Kritérium: `skóre = různých² / hran`** (efektivní počet různých
sousedů). Odměňuje rozmanitost i obecnost zároveň — uzel musí mít
mnoho sousedů A ZÁROVEŇ se neopakovat do týchž míst.

**Limit 328** platí na custom vertikály; osy z UDPipe stojí vedle
a nesoutěží. Co je už zastoupené, se nepromuje: kandidát, který
nerozliší dvě místa se stejným UDPipe popisem, místo nedostane.

**Vratnost.** Promoce není zápis navždy. Při přepočtu se pořadí sestaví
znovu a kdo vypadne z 328, uvolní sloupec. Funkce proto vrací **celý
cílový stav osy**, ne přírůstek — porovnává se stav proti stavu.

**Co záměrně nedělá.** Nesahá na cache ani na indexy (krok 3)
a nespouští přeučení (krok 4). Do té doby se testuje na čerstvém
registru, kde přeobsazení nehrozí.

### Zavržená varianta (naměřeno, ne odhadnuto)

Nejdřív jsem navrhl skóre `poměr × n/(n+1)`, tedy poměr různých
sousedů k hranám s tlumením za málo dokladů. **Simulace ho vyvrátila:**
tlumení saturuje už při dvaceti hranách, takže nahoru vyplavaly uzly
s poměrem 1,00 a dvaceti hranami (`muset`, `lékař`, `mnohý`,
`organismus`), zatímco nejsilnější uzly grafu vypadly úplně —
`rok`, `mít`, `moci` se do 328 nevešly. Vlastní jména sice padala
správně, ale to samo nestačí.

### Příklad na reálných datech (korpus 2 912 vět)

Prvních dvanáct podle `různých² / hran`:

| # | uzel | různých | hran | skóre |
|---|---|---|---|---|
| 1 | rok | 162 | 191 | 137,4 |
| 2 | mít | 185 | 260 | 131,6 |
| 3 | říci | 177 | 308 | 101,7 |
| 4 | moci | 119 | 147 | 96,3 |
| 5 | jít | 129 | 174 | 95,6 |
| 6 | přijít | 124 | 168 | 91,5 |
| 7 | stát | 85 | 93 | 77,7 |
| 8 | část | 88 | 100 | 77,4 |
| 9 | život | 90 | 110 | 73,6 |
| 10 | vyjít | 82 | 97 | 69,3 |

Hranice 328. místa je na skóre **12,1** (uzel `hodnota`), tedy
s rezervou nad šumem.

Kam padla vlastní jména: `Praha` 19., `Karel` 35., `Ježíš` 45.,
`Bohumil` 52., **`Hrabal` až 332.** — mimo limit. V celých 328 místech
je jmen jen **18 (5 %)**, zbytek jsou nositelé tvaru.

### Přejímací kritérium

- prvních 328 obsahuje `rok`, `mít`, `moci`, `stát`, `začít`, `dílo`;
- `Hrabal` se do limitu nevejde; podíl vlastních jmen v limitu ≤ 10 %;
- dvojí zavolání nad týmž korpusem dá **identický** seznam (promoce je
  deterministická);
- funkce vrací cílový stav, takže odebrání uzlu z korpusu ho z osy
  po přepočtu odstraní.

### Otevřené k rozhodnutí

Dělení rozpočtu mezi **slova** a **typy vztahů**. V jedné soutěži slova
typy přehlasují počtem, ačkoli typ je cennější (platí pro celý druh
otázek). Buď pevné dělení (např. 200/128), nebo násobek pro typy.
