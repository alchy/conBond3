# Učení z dialogu a znalostní graf s promocí do vertikál

Návrh J. (2026-08-04), prověřený měřením. Navazuje na `query-basket.md`
a na chronologii `postup-krok4.md` § 12–22.

## 1 · Co se mění

Dosud: otázka → skóre → token. Systém odpovídá z toho, co v korpusu je,
a když tam fakt není, mlčí.

Nově: **otázka se mapuje na celou VĚTU**, ve které odpověď leží, učí se
z **dialogu** a chybějící znalost si vyžádá. Z dialogu roste **znalostní
graf**; hrany, které se v něm ukážou jako obecné, se **promují do
vertikál** — a tím se mění osa systému, ne jen váhy. Po promoci se učení
pouští znovu, aby nad novými osami našlo vzor.

Tři věci to opírají o naměřené, ne o dojem:

- **Věta jako cíl** je jediná úroveň, která dnes drží: výběr věty je
  správný (§ 22: 1,46 proti 1,45), výběr uvnitř věty ne (Jordán 2,088
  vs Galilej 2,068).
- **Detekci mezery systém už umí**: `cover` počítá nejslabší danou osu,
  takže neznámý pojem dá nulu. Dialogová otázka „doplň kontext" jen
  zveřejňuje signál, který v poli je.
- **Prostor je prázdný**: 6 716 dimenzí, 45,1 M buněk matice, 869
  naučených vazeb (hustota 0,002 %). Promoce je způsob, jak ho zhušťovat
  zdola.

## 2 · Tři patra paměti

| patro | co drží | příklad | promuje se |
|---|---|---|---|
| **vertikály** | osy systému | `ANCHOR=space`, `Case=Nom` | cíl promoce |
| **typy** | tvary vztahů doložené mnoha instancemi | „X má stanovenou hodnotu Y" | ano |
| **graf faktů** | konkrétní svět z textu a dialogu | dálnice → 130 | ne přímo |

## 3 · Kritérium promoce: frekvence, průběžně přepočítávaná

Námitka „registr nasaje konkrétní svět" **měřením neobstála**. Korpus
2 912 vět, 5 781 obsahových lemmat:

| promuje se | lemmat | pokryje výskytů | z toho vlastních jmen |
|---|---|---|---|
| top 1 % | 57 | 17 % | 9 (**16 %**) |
| top 2 % | 115 | 25 % | 11 (10 %) |
| top 5 % | 289 | 38 % | 16 (**6 %**) |

Nejčastější jsou `říci, mít, rok, jít, přijít, dílo, práce, člověk,
moci` — obecná slova nesoucí tvar sdělení. Podíl vlastních jmen
s rostoucím výběrem **klesá** (16 % → 6 %), takže širší promoce dává
obecnější směs, ne konkrétnější. A jména, která projdou (`Ježíš, Praha,
Čapek`), jsou osami svých textů, ne náhodnými fakty.

**Promoce je proto vratná** (J.: *„frekvence musí být přepočítávaná
průběžně, na tom to stojí"*). Tenhle korpus jsou tři životopisy, takže
„Čapek" je v top 1 %; v desetkrát větším spadne dolů. Kdyby promoce
byla trvalá, prvních tisíc vět by natrvalo určilo osy pro milion
dalších. Přepočet běží průběžně při zpracování textu a co přestane být
časté, se z vertikál uvolní — dokud se etalon neustálí v optimální
rovině, přepočítává se pořád.

**Vektor vertikál je LIMITOVANÝ** (J.: *„co se nevejde do limitovaného
vektoru vertikál, to se vyhodí"*). Tím se mění dosavadní pravidlo
„registr jen roste": osa dostane pevnou velikost a promoce je soutěž
o místo — kdo vypadne z frekvenčního pořadí, uvolní sloupec. Je to
zároveň to, co dělá z registru **vstupní vrstvu sítě s pevnou
dimenzí**, a tlak, který nutí k obecnosti: co se nevejde, nebylo dost
nosné.

Technický důsledek, který je nutné ošetřit: registr dnes je append-only
se stabilními indexy a matice vět se na ně cachují. S limitem se indexy
uvolňují a přeobsazují, takže matice vět už nejsou platné napořád —
musí nést verzi osy a při její změně se přestavět. Bez toho by staré
matice ukazovaly na sloupce, které mezitím znamenají něco jiného; to je
tiché poškození dat, ne výpadek, takže se to musí hlídat verzí, ne
kontrolou při čtení.

### Limit 328 platí na CUSTOM vertikály

Upřesnění J.: **328 je strop pro custom vertikály** — osy z UDPipe
(`UPOS`, `DEPREL`, `Case`, `Polarity`, kotvy) stojí vedle a do soutěže
o místo nevstupují. Celý rozpočet je tedy k dispozici promoci.

**Co už je zastoupené, se jako custom nepřidává** (pravidlo J.). Není
to úspora místa, ale ochrana před duplicitou: naměřeno, že podle čisté
frekvence by prvních sto míst obsadila slova `a, být, on, se, v, na, z,
ten, s, který, do` — a každé z nich už nese některá UDPipe osa
(`SUBPOS=RR`, `UPOS=CCONJ`, `UPOS=PRON`, `UPOS=AUX`). Systém by tutéž
informaci držel dvakrát, jen jednou pojmenovanou jinak, a rozpočet by
padl na balast. Pokrytí by přitom vypadalo výborně (150 nejčastějších
slov = 46 % výskytů), což je přesně ten druh čísla, které se kupuje
místo aby se vydělalo.

Provozní podoba pravidla: kandidát má cenu tehdy, když **rozliší dvě
místa, která mají stejný UDPipe popis** — `v Jordánu` × `v lednu` se
gramaticky neliší, liší se typem jména; `dálnice` × `silnice` totéž.
Je to táž logika jako rozmanitost konců, jen měřená proti existující
reprezentaci místo proti korpusu.

Nad obsahovými slovy je pak rozpočet pohodlný: 289 nejčastějších
obsahových lemmat pokrývá 38 % výskytů, takže se do 328 vejde skoro
celá ta množina i s rezervou na promované typy vztahů. Zbývá rozhodnout
dělení rozpočtu mezi slova a typy — v jedné společné soutěži by slova
typy přehlasovala počtem, ačkoli typ je cennější (platí pro celý druh
otázek, ne pro jedno slovo).

Doplňující mez k frekvenci: promuje se podle **rozmanitosti konců**, ne
podle počtu výskytů. `rychlost → 130` má jeden konec a nepromuje nikdy;
`X → stanovená hodnota` má konců mnoho a promuje jako typ. Je to táž
logika jako NPMI — měří se rozmanitost, ne četnost.

## 4 · Dialog jako zdroj

    q:  Jak je omezena rychlost na dálnici?
    a:  V korpusu nemám „rychlost" ani „dálnice". Doplň kontext.
    u:  Dálnice je silnice pro motorová vozidla, kde je stanovena
        rychlost na 130 km/h.
    a:  Beru: dálnice ~ silnice, dálnice → rychlost,
        rychlost → stanovena → 130.

Systém tedy nejdřív **ověří pokrytí** (nehledá), pak si vyžádá kontext,
z odpovědi postaví uzly a hrany se zdrojem `dialog` a teprve pak
odpovídá. Trénink běží jak na jednotlivé otázce, tak na celém dialogu:
vstupní aktivační pole je dost dimenzované, aby pobralo několik vět
dialogu naráz a ukotvilo aktivaci.

Výstupní strana míří na koše `r_word = 2`, `r_sentence = 2` a sama
vyrábí basket, kterým se fituje kandidát — pořád jen metadata.

## 5 · Fáze, každá s vlastní měřitelnou otázkou

1. **Detekce mezery** — *pozná chybějící pojem dřív, než začne hledat?*
2. **Dialogové doplnění** — věta od uživatele se parsuje jako každý text.
3. **Vložení do grafu** — uzly a hrany se zdrojem `dialog`.
4. **Statistika** — průběžná frekvence a rozmanitost konců.
5. **Promoce** — co překročí mez, stane se osou; mez z testu na velkém
   korpusu, ne od oka. Vratná.
6. **Přeučení** — nad novými osami se hledá vzor znovu.
7. **Náhled** — které uzly se rozsvítily; experiment, ne přesná odpověď.

## 6 · Dvě rizika k ošetření předem

**Cyklení.** Promoce → přeučení → nové hrany → další promoce poběží
donekonečna a bude vypadat jako pokrok. Potřebuje touž pojistku, jakou
má dnes učení: kolo, které zhorší měřenou schopnost, se **odvolá**
(`registry.unlink` nad snapshotem) a promoce se vrátí.

**Přeobsazení sloupce.** S limitovaným vektorem se index uvolní a dostane
nový význam. Všechno, co si pamatuje sloupcová čísla (cache matic vět,
uložené registry, naučené hrany), musí nést **verzi osy** a při její
změně se přestavět. Dnes je hlídaná jen změna vazeb (`link_version`).
Je to nejnebezpečnější místo celého návrhu: chyba se neprojeví pádem,
ale tichou záměnou významu.

## 7 · Nejlevnější ověření konceptu

Fáze 1 a 4 jdou změřit na dnešním korpusu bez jediného dialogu:
*umí `cover` spolehlivě označit chybějící pojem?* a *kolik hran by při
daném prahu promovalo?* Druhá otázka už odpověď má (tabulka v § 3);
první je na řadě.
