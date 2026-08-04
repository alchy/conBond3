# Handover — další posun kvality (návrhy k odsouhlasení)

Navazuje na handover-implementace.md (kroky 1–4 hotové) a
rozsireni-otazky.md (A–I hotové). Každý krok stojí sám, má naměřený
důvod a přejímku; odsouhlasené sem zapisuje J.

**Větev vývoje (J. 2026-08-05): postupujeme po E — promoce + učení
+ hloubka.** E je provozní konfigurace systému: hloubka šíření k=2
je výchozí, promoční cyklus s přeučením běží nad rostoucím korpusem
a jeho přijatý stav se ukládá (registr s verzí osy). Všechny K-kroky
níže se MĚŘÍ NAD STAVEM E, ne nad holým baselinem.

Výchozí čísla větve E (2026-08-05, korpus 12 258 vět, 240 otázek
supervize): přesnost 0,467 / mlčení 0 / dosah 10 / vad 0;
s tokenovým θ=2,494 přesnost 0,233 / mlčení 1,00 (→ K1); věta
v kandidátech na validaci 24–28/50.

## K1 · Kalibrace θ/ε na VĚTNÉ úrovni

**Proč (naměřeno).** Mezi 0,467/0,00 a 0,233/1,00 leží provozní bod;
dnešní kalibrace řeže tokenová skóre, ale učení i cíl žijí na
gaussovských vrcholech vět. Na tréninku dala tokenová kalibrace
přesnost 0,02 — řez a signál mluví každý jiným jazykem.

**Co vzniká.** calibrate_theta nad vrcholy vět (gaussian_peaks);
ε (DOTAZ) kalibrovat spolu s θ; volitelně vážený merit
(w·přesnost + mlčení).

**Přejímka.** Provozní bod s přesností ≥ 0,40 při mlčení ≥ 0,67
na etalonu; obě čísla vedle sebe s tokenovým čtením.

## K2 · Expanze otázky do odpovědní cesty

**Proč (naměřeno).** expand_question existuje, ale reply() ani měření
ji nevolají — mezera smět↔povolený (dálnice) zůstává neuzavřená
a definice/derivace se v provozu neuplatní.

**Co vzniká.** reply(…, expand=True) volá expand_question před
match(); measure_nn dostane rameno „E + expanze". Slovníková hesla
se fixují do korpus-401.json (store je hotový).

**Přejímka.** Otázka o dálnici dostane větu F do top 3 (sentence_hit);
dosah na etalonu neklesne; počet cílených derivací na otázku
v reportu.

## K3 · Hygiena korpusu — degeneráty a citační smetí

**Proč (naměřeno).** Holé řádky beletrie („Paul Verlaine") jsou
atraktory nezodpověditelných otázek; citační bloky (Válka.cz) už
jednou rozbily fixaci. Kvalita výstupu stojí na kvalitě korpusu
(zadání J.).

**Co vzniká.** Oprava u ZDROJE (fixované JSONy): bloky, které nejsou
věty (bez slovesa, < 4 slova, citační vzory), dostanou v bloku
příznak `balast: true` — program je dál nese (žádné mazání, fixace
platí), ale koš věty s příznakem dostane vážený člen W_BALAST < 0.
Váha, ne filtr.

**Přejímka.** „Kdo zformuloval zákony termodynamiky?" už nevyhraje
Paul Verlaine; přesnost/dosah neklesnou; počet označených bloků
v reportu (ručně zkontrolovaný vzorek 20).

## K4 · Vyvážení promoce vůči žánru korpusu

**Proč (naměřeno).** Hranice promoce plave se skladbou korpusu
(12,1 → 41,9 po NZ); rychlost (33,8) a smět (41,7) vypadly těsně —
biblická záplava vytlačila doménové osy, které otázky potřebují.

**Co vzniká.** Promoce vážená po doménách: skóre uzlu se normalizuje
rozložením jeho dokladů přes bloky/dokumenty (uzel nesený jedinou
doménou soutěží ve své lize), NEBO dělení rozpočtu 328 po doménách.
Rozhodnutí o mechanismu je J.

**Přejímka.** rychlost a smět v limitu; jmen ≤ 10 %; stabilizační
křivka výměn dál klesá.

## K5 · Růst supervize a parafrázová validace

**Proč (naměřeno).** 240 otázek: validační věta-v-kandidátech ~50 %,
ale staré tvrdé otázky táhnou trénink dolů; zisk rozšíření supervize
byl vidět okamžitě (E 0,40 → 0,467).

**Co vzniká.** Další agentní dávky: otázky k NZ knihám (301–326)
a zapojení korpusů 001–003 (295 vět + 54 otázek s indexy) do
baselinu; k tomu PARAFRÁZOVÉ dvojice (táž odpověď, jiná slova —
vzor: dálnice v korpus-001) rozdělené záměrně mezi trénink
a validaci, aby se měřil přenos typu, ne zapamatování.

**Přejímka.** ≥ 500 otázek celkem; parafrázový přenos ≥ 0,5
(zodpovězená parafráza, jejíž dvojče bylo v tréninku); rozptyl
validace mezi semínky ≤ 5 b.

## K6 · DeriNet pro derivace

**Proč (naměřeno).** Kmenová heuristika nechytí střídání samohlásek
(křtít–pokřtěný 0,44 překryv, ale kmen je nespáruje; zpěv–zpívat,
smět–povolený vůbec). Přesně tahle třída mostů chybí otázce
o dálnici.

**Co vzniká.** Pořizovací skript pro DeriNet (ÚFAL; licence třídy
CC BY-NC-SA — mimo git jako model, ZDROJ.md) a derivační vazby ze
slovotvorných rodin místo/vedle kmenové heuristiky; dál CÍLENĚ při
expanzi, ne plošně.

**Přejímka.** křtít–pokřtěný a zpěv–zpívat dostanou vazbu; vzorek
20 náhodných rodin bez falešného páru; baseline se nehne (cílené
nasazení).

## K7 · Křivky hyperparametrů (levné, cyklus existuje)

**Proč.** σ Gaussu, limit 328 a hloubka k jsou jediné ruční
konstanty nové vrstvy — každá si zaslouží křivku místo dojmu;
měřicí smyčka s odvoláním už stojí, běh je ~10 min/bod.

**Co vzniká.** measure_sweep: σ ∈ {1, 1,5, 2, 3}, limit ∈ {164, 328,
656}, k ∈ {1, 2} × strana (jen otázka / obě). Report křivek.

**Přejímka.** Zvolené hodnoty doložené křivkou; žádná zvolená
v lokálním minimu sousedů.

## K8 · Typy vztahů do rozpočtu 328

**Proč.** Druhá polovina promoce (trvá z handoveru 1–4); typ platí
pro celý druh otázek. Teprve s typy dává dělení rozpočtu smysl
a graf začne nést odvozování (šipkový diagram z query-basket).

**Co vzniká.** Uzly typů v grafu (vzory deprel cest, např.
X --nsubj--> Y s kopulí = definice; X --obl--> V(pokřtít) = místo
děje), jejich statistika a promoce vedle slov.

**Přejímka.** Aspoň jeden promovaný typ prokazatelně zvýší záchyt
třídy otázek (kde/kdy) na validaci; rozpočet slova × typy zapsán.

## Doporučené pořadí

K1 (provozní bod) → K3 (hygiena) → K2 (expanze v cestě) → K5
(supervize) → K4 (promoce×žánr) → K7 (křivky) → K6 (DeriNet) → K8
(typy). K1+K3 jsou levné a odblokují čtení všech dalších měření.
