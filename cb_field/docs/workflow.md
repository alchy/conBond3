# Workflow — jak se v cb_field vyvíjí (revize po vlastních chybách)

Sepsáno na zadání J. (2026-08-03): *„kriticky projdi workflow a uprav
jej, aby přinášelo prospěch a ne poslalo kód do stoupy… pokud se budeš
držet konceptu a rozvíjet jej, to je ten směr. to že někde něco vyhodíš,
dáš tam if, není rozvoj. nejde o stavový automat."*

## A · Co bylo na dosavadním workflow špatně

| vada | jak se projevila | proč je zhoubná |
|---|---|---|
| **metrika jako cíl, ne jako kontrola** | po každém měření jsem sáhl po tom, co nejrychleji zvedne číslo — filtry | číslo šlo nahoru (0,06 → 0,79), schopnost dolů |
| **`if` místo váhy** | dimenzní brána, obsahový práh, jen jmenné středy, vyloučení daných slov | data se nedostala k vahám → učení nemělo z čeho stavět mosty |
| **stavový automat místo pole** | rozhodnutí „projde/neprojde" na několika místech řetězu | koncept je spojitý (váhy, součiny, šíření); větvení ho tříští |
| **učení před strukturou** | pustil jsem Hebb dřív, než graf existoval | 100k anonymních hran, přesnost klesla |
| **vlastní heuristiky bez odvození** | IDF, W_CENTER, θ nastavené od oka | nejsou z konceptu, nejdou vysvětlit, blokují učení |
| **testy zamykaly špatný návrh** | testovaly filtrovou sémantiku | každý návrat ke konceptu vypadal jako regrese |

## B · Workflow, který platí od teď

1. **Každá změna musí jmenovat, který princip konceptu rozvíjí**
   (P-A pytel, P-B koeficient, P-E růstový zákon, P-G graf…). Změna bez
   principu se nedělá.
2. **Rozvoj = přidat uzel, hranu nebo váhu.** Nikdy neubrat data z cesty.
   Zakázáno v datové cestě: `if` nad obsahem, práh, vyloučení, strop
   kandidátů. Povoleno pouze: nová vertikála (obecná), nová vážená hrana,
   nový vážený člen skóre — klidně se zápornou vahou.
3. **Řez existuje jen jeden a je na konci**: θ (NEVÍM) a ε (DOTAZ) nad
   hotovým skóre. Nikde jinde.
4. **Pořadí: struktura → učení → měření.** Nejdřív musí v grafu být, co
   se má učit; učení jen doostřuje váhy; měření je verifikace, ne cíl.
5. **Měření vždy s protiváhou** (přesnost × NEVÍM-správnost) a vždy
   se zveřejněným negativním výsledkem. Číslo bez protiváhy se neuvádí.
6. **Trénink ≠ měření**: trénovat na málu **těžkých** případů (most mezi
   tvary), měřit na širší směsi. Snadné případy do tréninku nepatří —
   učily by grep.
7. **Slepá ulička se zapisuje** (docs/postup-krok4.md), nesmaže.
8. **Testy testují koncept, ne implementaci**: rozklad skóre existuje,
   axiom se nepřepíše učením, most mezi tvary vznikne. Ne „filtr zahodil".

## C · Kontrolní otázky před každým zásahem

- Který princip to rozvíjí?
- Přidávám, nebo ubírám? (Ubírám → nedělat.)
- Co se tím přestane učit?
- Půjde výsledek přečíst jako hrana s pojmenovanými konci?
- Mám protiváhu, která odhalí, že jsem si číslo koupil?

## D · Aktuální dluhy z minula (k nápravě v tomhle duchu)

1. **IDF a W_CENTER** — moje heuristiky; nahradit naučenými koeficienty
   (jsou to jen počáteční hodnoty vah, ne pravidla).
2. **θ = 2.0, ε = 0.25** — nekalibrované; kalibrovat na oddělené sadě.
3. **Krok učení je mikroskopický**: naměřeno 2026-08-03 — loss klesá
   (867 → 810 → 764), ale trefy 0/32. Marže 1.0 je proti skóre ~20
   bezvýznamná a `scale` krok dále zmenšuje. Náprava v duchu konceptu:
   marži i krok odvodit z rozsahu skóre (relativní marže), ne přidat
   `if`.
4. **Hebb** — dnes nad surovými souvýskyty škodí; má běžet až nad
   strukturou a s NPMI prahem odvozeným z dat.
5. **Refaktor učení — rozhodnuto 2026-08-03 (J.), pořadí závazné:**
   1. **tanh po každém kroku šíření** — saturace do −1…+1, tedy do
      rozsahu, který váhy už mají; odstraní huby i potřebu IDF náplasti.
      Dnes systém běží zcela lineárně, což je hlavní příčina loss ve
      stovkách a trefů 0/32.
   2. **normalizace skóre** (kosinus nad pytlem) — délka věty přestane
      rozhodovat; loss spadne do jednotek a stane se čitelným.
   3. **relativní marže** místo absolutní 1,0.
   4. **Adam** místo dnešního SGD s konstantním η=0,15 (momenty m, v,
      β₁=0.9, β₂=0.999, ε=1e-8; pár řádků numpy nad řídkými hranami —
      žádný framework do modulu, § 19). Aktualizují se jen hrany se
      zdrojem hebb/etalon; axiomy zůstávají chráněné.
   Teprve po tomhle refaktoru dává smysl webová stránka s vysvětlením
   návrhu Q→A (zadání J.), protože bude popisovat mechaniku, která se
   sama nepřehlušuje.
6. **Dvojité r** (r_words × r_sentences) — rozebrané, nepostavené;
   je to čistý rozvoj konceptu (kontextové pytle + bonus tématu na
   konec), proto má přednost před dalším laděním.
