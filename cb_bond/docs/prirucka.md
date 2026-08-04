# Příručka cb_bond — otázky ze stavby a pasti

## Otázky, které při stavbě padly

**Jak se pozná, že je pravidlo uzlu a hrany správně?** Zmraženými
přejímkami § 6 zadání. Na 2 912 větách se zkoušely čtyři varianty
a jen jedna sedla na 16 074 hran a 5 695 lemmat současně: uzly
NOUN/PROPN/VERB/ADJ/ADV/NUM (i zájmenná příslovce), hrana jen mezi
přímými sousedy, smyčka do součtu ano — do sousedství ne. Ostatní
varianty daly 15 202 až 16 233 hran. Čísla nejsou dekorace; jsou to
testy.

**Proč „5 695 lemmat", a ne 5 727 uzlů?** Zadání počítá **různá
lemmata**, ne klíče `UPOS:lemma`. Totéž lemma ve dvou slovních druzích
(*stát* jako VERB i NOUN) jsou dva uzly, ale jedno lemma. Přejímkový
skript to počítá stejně — kdo měří uzly, dostane 5 727 a bude si
myslet, že se něco pokazilo.

**Proč emitor, a ne metoda `draw()`?** Jádro nesmí mít I/O vrstvu
(README-MODULES § 1). Emitor je funkce v konstruktoru: v testu je to
`list.append`, v provozu `GraphMirror`. Graf o kreslítku neví nic.

**Proč `illuminate` počítá záři z ROZSVÍCENÍ, ne z průběžného jasu?**
Kdyby se zářilo z už zjasněných uzlů, bylo by to šíření do hloubky
a záleželo by na pořadí průchodu. Jeden průchod z rozsvícení je
deterministický a odpovídá výpočtu v zadání (Jordán 1,67, Galilej
1,20).

## Pasti

**Uzel s hranou ≠ uzel.** `nodes()` vrací i izolované uzly,
`statistics()` jen ty s hranou. Průměrný stupeň počítaný přes
`nodes()` vyjde tiše nižší — a nikdo si toho nevšimne, protože číslo
pořád vypadá rozumně.

**Hrany se sčítají s opakováním.** Přidat tutéž větu dvakrát znamená
dvojnásobek hranových instancí, ale týž počet různých sousedů — a tedy
poloviční `ratio`. Je to záměr (opakování je informace), ale kdo staví
graf z korpusu s duplicitami, dostane jiné skóre promoce.

**Zájmenná příslovce jsou v cb_field zavřená a tady otevřená.** Kdo
klasifikaci sjednotí „pro pořádek", rozejde graf s přejímkou o 121
hran. Je to vědomý rozdíl (koncepce § 3), ne nedopatření.

**Skript přejímky potřebuje data mimo git.** Korpusy 101–107 leží
v `cb_field/data-persistent/korpus/` (licence, viz ZDROJ.md). Bez nich
skript skončí s kódem 2 a řekne to — netváří se, že prošel.

## Krok 3: co sedí a co ne

**Sedí přesně.** Pokrytí otázky o křtu 1,000 / 0,604 / 0,885 a mrtvá
osa jako **přesná nula** (`WORD=NOUN:dálnice` v biblicko-fyzikálním
korpusu). Souhlasí i celá pětice ze vzorku kroku 8. Čísla dávají
smysl: `tanh(0,7) = 0,604` je jeden výskyt slovní osy, `tanh(1,4) =
0,885` dva.

Sedí i přejímka S1: čtení top-50 vět dá **touž přesnost** jako čtení
celého korpusu (2 912 vět) — předvýběr nic neztrácí.

**Dvě čísla, ne jedno.** Přejímkové 0,3667 je SPRÁVNĚ **s řezem**
(top-1 lemma a zároveň outcome „odpoved"); totéž **bez řezu** je
0,4667 (14/30), rozdíl jsou tři otázky spadlé do DOTAZ/NEVÍM. Kdo
měří s `theta=0`, poměřuje se se 14/30.

**Kde se přesnost ztrácela (vyřešeno).** Původní stavba hledala chybu
v členu *setkání* a sedm jeho variant skončilo mezi 2/30 a 6/30.
Ablace ukázala, že to bylo hledání na špatném místě — nosné jsou
`given` a `cover`, ne `meet`:

| konfigurace | reference | tady |
|---|---|---|
| plné skóre | 14/30 | 11/30 |
| bez tématu (topic=0) | 12/30 | 11/30 |
| bez zdůraznění středu (center=1) | 9/30 | 8/30 |
| bez pokrytí (cover=0) | 7/30 | 4/30 |
| bez postihu daného (given=0) | **0/30** | **0/30** |
| jen setkání | **0/30** | **0/30** |

Obě nulové hodnoty sedí přesně, a jsou to ty nejtvrdší: **bez postihu
−3 za střed, jehož slovo otázka sama uvádí, vyhrává vždycky ozvěna
otázky.** Proto se žádná varianta setkání nemohla k referenci
přiblížit — chyba byla jinde, než kam mířilo hledání.

**Co po doplnění kroku 3b zbývá.** Přesnost stoupla z 3/30 na 11/30
proti referenčním 14/30. Šest chyb je „pořadí 1" — správná odpověď
těsně druhá (např. „Kolem čeho obíhá Země?": měsíc 2,25 před slunce
2,13). Rozdíl je tedy v měřítku členů, ne v jejich skladbě.

Poslední zavřená mezera byla vlastní nedůslednost: harmonická váha
1/(1+|o|) existuje proto, aby okno NEMĚLO hranu, ale ořezával jsem ho
na ±r, čímž se hrana vrátila. Okno přes celou větu dá 11/30 místo
10/30. Ořez na ±3 dá totéž co celá věta — dozvuk za třetí pozicí už
váží málo, ale hrana tam být nesmí.
