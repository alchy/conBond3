# Krok 4 — Propojení: koš otázky × koše faktů, učení vah a růst vertikál

Implementační dokument. Principy, odvození, metakód. Bez kódu.
Navazuje na README-EXTRAKCNI_VRSTVA.md (krok 1) a na naměřený stav
cb_field (šablony, kotvy, vazby — docs/mereni.md). Vznikl z dialogu
2026-08-03; u každého principu je uvedeno, z čeho plyne.

---

## 0 · Zadání a kritérium úspěchu

Propojit koš otázky s koši faktů tak, aby odpověď vznikala součinem
vah, síla propojení byla **učitelný koeficient**, a systém uměl sám
rozpoznat, **kdy má ladit váhy a kdy rozšířit reprezentaci**. Vše
deterministické při vyhodnocení, interpretovatelné po hranách,
měřené na zmraženém etalonu.

Úspěch nejsou dojmy z ukázek, ale tři čísla na etalonu otázek (§ 6):
přesnost@1 na zodpověditelných, správnost NEVÍM na nezodpověditelných,
a rozklad chyb na slabé/nepřesné (§ 5) — protože ten řídí, co se
stane dál.

---

## 1 · Principy

### P-A · Koš je pytel: pořadí nenese význam, osy ano

Koš se smí „zatřást" — obsah se přeskupí a nesmí se ztratit nic, co
nese význam. Důsledek: co bylo dřív v pozici (směr „do" vs. „z"),
musí být v ose (`ANCHOR=dir:to/from/at/through`), a příznaky předložek
se **přenášejí na jádro** (case-dítě → hlava), aby v zatřeseném koši
nepatřily náhodnému sousedovi. *(Odvozeno z konceptu starého pole:
koš/basket — „v koši se vše může nacházet jinak, když se s ním
zatřese."; naměřený případ: „z Prahy do Brna" bylo v pytli bez osy
směru nerozlišitelné.)*

### P-B · Propojení = koeficient součinu

Skóre spojení dvou košů je bilineární forma

```
skóre(q, a) = qᵀ · W · a = Σᵢⱼ qᵢ · W[i,j] · aⱼ
```

kde `q`, `a` jsou vektory košů (agregace řádků okna) a `W[i,j]` je
**síla propojení vertikál i↔j: čím silnější, tím větší parametr pro
součin**. W žije v registru jako vážené hrany (`link`); `spread` je
jeden krok téhož. Je to jednohlavá attention nad pojmenovanými osami —
rozdíl proti neuronce není v matematice, ale v tom, že osy mají jména.

### P-C · Dvě vrstvy W: axiomy a naučené koeficienty

Axiomy (hierarchie kotev, mosty QANCHOR↔ANCHOR, @1.0) se **neučí** —
jsou to definice jazyka systému. Naučené koeficienty leží vedle nich
a každá hrana nese `zdroj` (axiom | hebb | etalon). Učení nesmí axiom
přepsat; audit musí umět obě vrstvy oddělit.

### P-D · Interpretovatelnost je invariant

Každý koeficient je pojmenovaná hrana mezi dvěma pojmenovanými
vertikálami. Skóre každé odpovědi jde **rozložit na sčítance**
`qᵢ·W[i,j]·aⱼ` a ukázat top příspěvky — odpověď bez rozkladu se
nevydává. (To je P8 — stopa — přenesený do párování.)

### P-E · Růstový zákon: kdy ladit a kdy rozšiřovat

Jádro celého kroku. Dva druhy selhání, dvě různé nápravy:

| selhání | příčina | lék |
|---|---|---|
| aktivace **slabé** (skóre nízké, ale směr správný) | signál existuje, jen má malý koeficient | **učení vah** — W[i,j] naroste |
| aktivace **nepřesné** (skóre vysoké u špatné odpovědi) | signál v žádné vertikále není — reprezentace ho neunese | **rozšířit vertikály** — nová osa |

Operacionalizace (§ 5) je matematicky přesná: **bilineární forma
neumí oddělit dva kandidáty s identickými vektory.** Když se správná
a vítězná (špatná) odpověď v existujících osách neliší, žádné W je
nerozliší — to je důkaz chybějící osy, ne záminka k dalšímu ladění.
Naopak nenulový rozdíl je vždy učitelný. *(Prototyp: osa `dir:` —
zatřesení zahodilo pozici, ladění by nepomohlo, pomohla nová osa.)*

**Zákaz konkrétna.** Rozšiřuje se výhradně o osy obecné — gramatické
kategorie, typy, směry, vztahy. Nikdy o nic konkrétního: žádná
vertikála pro konkrétní osobu, konkrétní číslo, konkrétní místo.
Konkrétní obsah patří do vrstvy WORD (COMPLETE) a do hodnot slotů;
kdyby prosákl do os bezeslovné matice, rostla by se světem místo
s gramatikou a přestala by zobecňovat. Když se pár nerozlišitelných
kandidátů nedá oddělit žádnou obecnou osou, **úniková páka je r**:
hypoteticky se pracuje s větším poloměrem — do koše se přibere víc
kontextu a rozdíl se hledá tam. Teprve když nepomůže ani obecná osa,
ani r, je to přiznaná mez reprezentace, ne důvod k výjimce.

### P-F · NEVÍM je odpověď

Pod prahem skóre θ, nebo když žádný příspěvek nejde přes dimenzní uzel
otázky, se odpovídá NEVÍM. Mlčení je levnější než chyba a etalon ho
měří zvlášť (§ 6).

---

## 2 · Mechanika párování (fáze 4a — ruční W)

* **Koš otázky** = celá otázka jako pytel (reprezentace COMPLETE —
  obsahová slova poutají kandidáty přes sdílené `WORD=` vertikály).
* **Koše faktů** = okna r kolem středů R1, pytle COMPLETE (střed
  uvnitř — v pytlovém světě není díra potřeba: most QANCHOR↔ANCHOR
  je párování středu).
* Vektor pytle = **suma** vektorů řádků (agregace je páka, § 7).
* skóre = `spread(q_pytel) · spread(a_pytel)` — obsahuje obsahový
  překryv (sdílené WORD/LEM), strukturní překryv (UPOS/DEPREL/FEATS)
  i souřadnicové setkání (QANCHOR↔ANCHOR přes vazby).
* **Odpověď = střed nejlepšího koše**; doložení = věta, koš, rozklad
  skóre (top hrany). Kandidují všechny koše korpusu — žádný
  předvýběr, dokud měření neřekne, že je ho třeba.

---

## 3 · Datový model

* **W v registru**: hrany `(od, do, váha, zdroj)`; save/load už umí,
  přibývá `zdroj`. Váhy ±1, znaménko = druh vazby.
* **Etalon otázek**: `cb_field/tests/data/etalon-otazky.jsonl`,
  zmražený v gitu. Záznam: `{"otazka": …, "odpoved_lemma": …,
  "zodpoveditelna": true/false}` — **nezodpověditelné otázky jsou
  povinná součást** („Kde bydlí Alois?" — nikdo takový v korpusu):
  jsou protiváhou učení (§ 6).
* Verze: každé měření nese otisk testbedu, etalonu a verzi W.

---

## 4 · Metakód

```
MATCH(otazka, korpus, W):
    q ← spread(pytel(otazka))
    pro každý koš a v korpusu (středy R1):
        s(a) ← q · spread(pytel(a))
    vítěz ← max s;  pokud s(vítěz) < θ nebo dimenze otázky bez
    příspěvku → NEVÍM
    vrať (střed vítěze, rozklad skóre, pořadí kandidátů)

UČENÍ_HEBB(korpus, W):                      # bez učitele, zdroj=hebb
    pro dvojice vertikál (i, j) souaktivované v témž koši:
        ΔW[i,j] ← η · (souvýskyt nad náhodu)   # PMI-styl normalizace
    ořež na ±1; axiomy nedotčeny

UČENÍ_ETALON(etalon, W):                    # kontrastivně, zdroj=etalon
    pro chybné odpovědi typu SLABÁ (viz DIAGNÓZA):
        W += η · (q ⊗ a_správná − q ⊗ a_vítěz)   # jen na souaktivovaných
        hranách (qᵢ·aⱼ ≠ 0), meze ±1, axiomy nedotčeny

DIAGNÓZA(vysledek etalonu):                 # operacionalizace P-E
    pro každou chybu:
        d ← |v(správná) − v(vítěz)|          # v existující reprezentaci
        d > 0  → SLABÁ    → do fronty učení
        d == 0 → NEPŘESNÁ → do fronty růstu: zapsat pár, který osy
                            nerozlišily; nová osa se navrhne z toho,
                            ČÍM se pár liší v surových datech
    hlas o růstu: nová vertikála vzniká, když se týž typ
    nerozlišitelnosti doloží ≥ k-krát (žádná osa kvůli jedné větě)
```

**Odkud nové osy brát** (pořadí, od nejlevnějšího): 1. data, která už
máme a neemitujeme (další pozice xpos, hrany k dětem — „má case-dítě
do", řetězce deprel); 2. konečné tabulky (typ z gazetteeru — krok 5
mapy); 3. vnější zdroje (clustery, R5); 4. **úniková páka r** — víc
kontextu do koše, když žádná obecná osa rozdíl nenese. Nikdy konkrétní
entita ani číslo (zákaz konkrétna, P-E). Každé rozšíření: append-only,
změřit před/po, zapsat do koncepce jako u osy `dir:`.

---

## 5 · Diagnóza selhání — přesná pravidla

* **SLABÁ**: správná odpověď kandiduje, prohrála skórem, ale její
  vektor se od vítězova liší (`d > 0`) → existuje W, které ji zvedne;
  jde do učení. Zvláštní případ: správná vyhrála s malým odstupem —
  taky do učení (posílení okraje).
* **NEPŘESNÁ**: `d == 0` — kandidáti jsou v použitých osách totožní.
  Důkaz chybějící osy. Jde do fronty růstu s dokladem (pár vět, pár
  košů, co je v surových datech odlišuje).
* **NEPOKRYTÁ**: otázka bez příspěvku přes svou dimenzi (např. „Kde
  pracuje Marie?" bez typu místa) → NEVÍM; eviduje se zvlášť — je to
  známá díra reprezentace (typicky čeká na krok 5), ne selhání W.

---

## 6 · Měření

Etalon ~30–50 otázek nad zmraženým testbedem (kde/kdo/kam/odkud/kdy/
kolik + nezodpověditelné). Čtyři čísla, vždy spolu:

| číslo | co měří | protiváha |
|---|---|---|
| přesnost@1 | podíl správných odpovědí na zodpověditelných | NEVÍM-správnost |
| NEVÍM-správnost | podíl nezodpověditelných, kde systém mlčel | přesnost@1 |
| podíl SLABÁ / NEPŘESNÁ / NEPOKRYTÁ | rozklad chyb — řídí další krok | — |
| rozklad skóre | u vzorku odpovědí ručně přečíst top hrany | — |

Protiváha je závazná: učení, které zvedne přesnost a shodí
NEVÍM-správnost, se nepřijímá — systém se naučil hádat, ne odpovídat.
Měří se před učením (baseline s axiomy), po Hebbovi, po etalonovém
doladění; každé číslo s verzí dat a W.

---

## 7 · Otevřená rozhodnutí (páky)

| id | rozhodnutí | výchozí | rozhodne |
|---|---|---|---|
| V-1 | agregace pytle | suma | měření (vs. max — suma nese počty, max drží meze) |
| V-2 | normalizace skóre | surový součin | měření (vs. kosinus — délkové zvýhodnění dlouhých košů) |
| V-3 | práh θ pro NEVÍM | kalibruje se na etalonu | registr prahů modulu |
| V-4 | η a normalizace Hebba | malé, PMI-styl | měření 4b |
| V-5 | koš otázky: celá věta vs. okno | celá věta | měření (krátké otázky ≈ totéž) |
| V-6 | k (počet dokladů pro novou osu) | 3 | registr prahů |
| V-7 | eskalace r u nerozlišitelných párů | r+1, jen doloženě | měření (T2 hlídá cenu) |

---

## 8 · Co krok 4 vědomě neřeší

Víceskokové otázky (spojování dvou vět), koreference a odkazy mezi
větami, čas jako interval, definiční vrstva. Typ z gazetteeru je
krok 5 — NEPOKRYTÁ kategorie na něj čeká a měří mu předem velikost
díry.

---

## Pořadí stavby a zkoušky

```
4a  match s ručním W (axiomy) + etalon + diagnóza     → baseline čísla
4b  Hebb ze souaktivací korpusu                        → přeměřit
4c  kontrastivní doladění na etalonu                   → přeměřit
4d  první běh růstu: fronta NEPŘESNÁ → návrh os        → přeměřit
```

Zkoušky: T-P1 správná odpověď s doložením („Kde bydlí Jana?" →
Brně); T-P2 NEVÍM na nezodpověditelné; T-P3 rozklad skóre sedí na
ruční kontrolu; T-P4 diagnóza odliší SLABÁ od NEPŘESNÁ na
konstruovaném páru; T-P5 učení nezhorší NEVÍM-správnost.
