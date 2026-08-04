# Implementace dialogového učení — handover po krocích

Rozpracování návrhu z `dialog-graf.md` do kroků, které jdou dělat
a měřit jeden po druhém. Každý krok je samostatný: dokud se nezapne,
nic nemění. Odsouhlasené kroky se sem zapisují postupně (J.).

Řada kroků:

1. **Graf faktů jako vrstva** — uzly a hrany ze závislostí, statistika
   stupně a poměru · *odsouhlaseno 2026-08-04*
2. **Promoce do custom vertikál** — `promote_verticals()`, limit 328,
   kritérium různých²/hran, vratná · *odsouhlaseno 2026-08-04*
3. **Promoční cyklus** — invalidace, přeučení a odvolání jako jedna
   atomická operace · *odsouhlaseno 2026-08-04*
4. **Detekce mezery a dialog** — `fact_gaps()`, `reply()`,
   `append_context()` · *odsouhlaseno 2026-08-04*
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

---

## Krok 3 · Promoční cyklus (invalidace + přeučení + odvolání)

Původně jsem to navrhoval jako dva kroky (technická invalidace zvlášť,
přeučení zvlášť). **J. to sloučil, a má pravdu**: promoce bez přeučení
nechá systém v horším stavu, než v jakém byl — dostane nové osy, na
kterých nemá naučeno nic, zatímco stará váha platila pro jinou
reprezentaci. A hlavně: odvolání promoce potřebuje měření, které dává
smysl teprve po přeučení. Jinak by se odvolávalo podle čísla z
mezistavu.

Cyklus je proto **atomický**: buď projde celý, nebo se nestalo nic.

    1. snapshot osy i vazeb
    2. promote_verticals() → cílový stav osy
    3. zápis os · axis_version++ · invalidace všeho, co drží sloupce
    4. přeučení nad novými osami
    5. měření (přesnost × NEVÍM-správnost × recall v dosahu)
    6. horší než před cyklem → návrat na snapshot, jinak přijmout

### Invalidace: nejnebezpečnější místo návrhu

Dnes je registr append-only, sloupec znamená navždy totéž a matice vět
se na ta čísla cachují. S limitem 328 se sloupce uvolňují
a přeobsazují, takže stará matice ukazuje na sloupec, který mezitím
znamená něco jiného. **Neprojeví se to pádem, jen tichou záměnou
významu** — systém bude vypadat, že funguje, a bude se plynule
zhoršovat.

Proto `registry.axis_version` — čítač změn OBSAZENÍ os, vedle dnešního
`link_version` (změny vazeb). Verzi nese každý, kdo si pamatuje
sloupcová čísla: cache matic vět, cache pytlů faktů v párování, uložený
registr na disku. Čtení cache jde jedinou funkcí, která verzi porovná,
aby na to nešlo v novém kódu zapomenout; `load()` odmítne soubor s cizí
verzí osy hlasitě, ne tiše.

**Naučené hrany jsou zvláštní případ.** V registru jsou uložené podle
klíčů (`_links[(src, dst)]`), ne indexů, takže je přeobsazení sloupce
nerozbije — jen jim zmizí osa, do které ukazovaly. Uvolněná vertikála
proto musí odejít i se svými hranami, jinak zůstanou viset do
neexistujících os. Je to jediné místo, kde promoce **maže naučené**,
a patří do testu.

### Přejímací kritérium

- test: postavit korpus, promovat, uvolnit sloupec — stará matice se
  musí odmítnout použít (ne vrátit špatná data);
- test: po uvolnění vertikály nezůstanou v registru hrany, které na ni
  ukazují;
- test: cyklus, který zhorší měření, vrátí registr bit po bitu do
  stavu před sebou (snapshot + `unlink`);
- regrese: bez promoce se nesmí změnit žádné dnešní číslo.

---

## Krok 4 · Detekce mezery a dialog

**Co vzniká.** Tři funkce, kód anglicky jako zbytek modulu:
`fact_gaps()` řekne, které osy otázky korpus vůbec nemá; `reply()`
odpoví a zároveň chybějící osy ohlásí; `append_context()` připojí větu
od uživatele.

**Není to nová mechanika.** `cover` už dnes počítá nejslabší danou osu
a mrtvá osa dává nulu — signál v poli je, jen se utopí ve skóre. Krok
ho vytáhne na povrch.

**Práh není potřeba** a moje obava o něj byla lichá (naměřeno níž):
mrtvá osa dává PŘESNĚ nulu, protože v registru vůbec není, zatímco
pokryté osy začínají na 0,604. Mezi tím je propast, ne škála.

**Odpovídá se vždy**, i při mezeře: `reply()` vrátí nejlepšího
kandidáta a k tomu `outcome="needs_context"` se seznamem chybějícího.
Při experimentu je to užitečnější než mlčení (vidíš, kam systém sáhl)
a nic to nezakrývá, protože chybějící osa je vypsaná. Čisté mlčení je
jednořádková změna na volající straně.

**Věta od uživatele jde stejnou cestou jako každý text**, jen se
zdrojem `dialog`. Žádná zvláštní větev — pak se na ni vztahuje všechno
ostatní (koše, promoce, učení) bez výjimek, a přitom jde kdykoli
zjistit, odkud je, a případně ji odebrat.

### Příklad na reálných datech (korpus 2 912 vět)

    Jak je omezena rychlost na dálnici?
       WORD=AUX:být          pokrytí 1,000
       WORD=ADJ:omezený      pokrytí 0,604
       WORD=NOUN:rychlost    pokrytí 0,604   ← korpus JI ZNÁ (fyzika)
       WORD=ADP:na           pokrytí 1,000
       WORD=NOUN:dálnice     pokrytí 0,000   ← MRTVÁ OSA

    Kde byl pokřtěn Ježíš?
       WORD=AUX:být          pokrytí 1,000
       WORD=ADJ:pokřtěný     pokrytí 0,604
       WORD=PROPN:Ježíš      pokrytí 0,885   ← vše pokryto, neptá se

Systém se tedy zeptá přesněji než původní náčrt: „rychlost" zná
z fyzikálního korpusu, chybí mu jen „dálnice" — ptá se na jednu věc,
ne na dvě.

### Metakód

    def fact_gaps(question, corpus):
        """Axes of the question the corpus does not have at all."""
        gaps = []
        for axis in given_axes(question):      # WORD= rows without QLEM=
            coverage = max(tanh(spread(s))[axis] for s in corpus)
            if coverage == 0:
                gaps.append(axis)
        return gaps

    def reply(question, corpus, graph):
        gaps = fact_gaps(question, corpus)
        result = match(question, corpus)       # always searches
        return Reply(best=result.best,
                     outcome="needs_context" if gaps else result.outcome,
                     missing=gaps)

    def append_context(text, corpus, graph, parser):
        """User-supplied sentence enters the same way any text does —
        no separate path, only a different source."""
        field = corpus.add_text(text, parser, document="dialog")
        graph.add_sentence(field, source="dialog")
        return field

### Průběh dialogu

    q:  Jak je omezena rychlost na dálnici?
    a:  Neznám „dálnice". („rychlost" mám z fyziky.) Doplň kontext.
    u:  Dálnice je silnice pro motorová vozidla, kde je stanovena
        rychlost na 130 km/h.
    →   corpus += věta (document="dialog")
    →   graph  += uzly: dálnice, silnice, vozidlo, rychlost,
                        stanovený, 130
               += hrany: silnice --nsubj--> dálnice
                         vozidlo --nmod--> silnice
                         rychlost --nsubj--> stanovený
                         130 --obl--> stanovený
    a:  Přijato: dálnice ~ silnice, rychlost → stanovený → 130.

### Přejímací kritérium

- `fact_gaps` označí `dálnice` a NEoznačí `rychlost`, `Ježíš`,
  `pokřtěný`, `Jordán`;
- po `append_context` má `dálnice` nenulové pokrytí a v grafu přibudou
  uzly i hrany se zdrojem `dialog`;
- `reply` vrací kandidáta i při mezeře (nemlčí), a `missing` je prázdné
  u otázek, které korpus pokrývá.
