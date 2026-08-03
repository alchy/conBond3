# Krok 1 — Extrakční vrstva: z textu na atomy a koše

Implementační dokument. Principy, odvození, zdůvodnění, metakód. Bez kódu.
Vychází z dialogu nad projektem conBond2 (pole2 — aktivační pole) a z jeho tří
ověřovacích prototypů; každý princip níže má uvedeno, z čeho byl odvozen,
včetně chyb, které k němu vedly.

---

## 0. Zadání kroku a kritérium úspěchu

Krok 1 je deterministická extrakce: česká věta → morfologicko-syntaktická
metadata (UDPipe) → pole → šablony → atomární vzory → koš věty. Výstupem je
reprezentace, nad kterou pozdější vrstvy (definice, logické hrany, aktivace)
mohou pracovat, aniž by se musely vracet k povrchu textu.

Krok 1 vědomě neřeší: rozbor definic, logické spojky, správnost aktivace,
čas a intervaly, odkazy typu „tam, kde je Karel". Datový model však musí být
na tyto vrstvy připraven — proto obsahuje trojhodnotovou polaritu, zakládané
prázdné sloty a slot schopný nést odkaz, i když je krok 1 zatím neplní.

Úspěch kroku není „funguje na ukázce", ale čtyři měřitelná čísla definovaná
v §5. Nejdůležitější z nich je poměr šablon k větám: je to jediné měření,
které může koncept vyvrátit, nikoli jen odhalit opravitelný detail.

---

## 1. Principy a jejich odvození

### P1 — Vztah je tvar, ne jméno

Instance nenese label typu `lokace`. Vztah je zakódován tvarem vektoru:
`(v, Loc, misto) = praha` říká „v místě Praha" sám o sobě, žádné pojmenování
nepotřebuje. Porovnávání (a později match definic) probíhá forma na formu.

Zdůvodnění: pojmenovací tabulka (povrch → jméno vztahu) je sémantická vrstva,
která roste s doménou a musí ji někdo udržovat. Tvarů je naproti tomu konečně
mnoho — jsou to kombinace pádů a typů — a rostou jen s gramatikou, ne
s obsahem. První prototyp tabulku PREKLAD obsahoval a byla to chyba směru:
vnesla význam tam, kde měla zůstat forma. Pojmenování je interpretace; smí
přijít později, nebo nikdy.

Důsledek pro pozdější vrstvy: definice „být na stejném místě" nevytvoří odkaz
na jméno, ale pod-vzor `(*, Loc, misto)`, který se v instancích hledá jako
tvar. Krok 1 proto musí tvar v instanci uchovat celý, ne jeho překlad.

### P2 — Dvě geometrie: okno určuje šablonu, hrany plní role

Lineární okno o poloměru r kolem středu určuje identitu šablony — které věty
jsou týž vzor. Role (kdo, jádro, kdy) se však plní po závislostních hranách
head/deprel, kde lineární vzdálenost nehraje roli.

Odvození z konkrétního selhání: ve větě „Petr je v Praze" je subjekt od
jmenného rootu lineárně 3 pozice, takže okno r=2 na něj nedosáhne a slot kdo
zůstane prázdný, přestože šablona vznikla správně. U rozvité věty („Petr,
který se vrátil z Brna, je v Praze") subjekt žádné rozumné r nedožene — hrana
nsubj→root ano. Sloučení obou geometrií do jedné je chyba, která se projeví
až na delších větách, tedy pozdě.

Důsledek: každý token v poli musí nést sloupec head (index hlavy, přepočtený
na absolutní pozici v poli). UDPipe ho dává; nesmí se zahodit.

### P3 — Pád zobecňuje, předložka upřesňuje

Statickou polohu nese lokál: `v + Loc` i `na + Loc` jsou táž informace
(poloha), `z + Gen` je zdroj, `do + Gen` cíl. Match pod-vzorů proto probíhá
přes dvojici (pád, typ) a předložka je v matchi hvězdička; v instanci však
předložka zůstává jako upřesňovač pro jemnější vzory.

Zdůvodnění: definice říká „na stejném místě", fakta říkají „v Praze" —
kdyby match šel přes předložku, definice by fakta nenašla. Naopak zahodit
předložku úplně nelze: `v + Ak` (směr) vs `v + Loc` (poloha) rozlišuje pád,
ale `u + Gen` (blízkost) vs `z + Gen` (zdroj) rozlišuje jen předložka.
Ověřeno v prototypu: „Soňa odjela z Prahy" s jádrem `(z, Gen, misto)`
správně nematchla polohový pod-vzor `(*, Loc, misto)` a systém odpověděl
NEVÍM — čistě z pádu, bez jediného sémantického pravidla.

### P4 — Vertikála typ je nutná a plní se zvenčí

UD nerozliší „v Praze" od „v lednu": obojí je ADP + jméno v lokálu. Je to
týž problém jako tázací tvary v README projektu (jak/kdy/kam/kde/proč mají
jeden podpis). Proto existuje vertikála typ s hodnotami misto / cas / osoba /
vec, plněná zvenčí: nyní gazetteerem a NameType z UD, později clustery
z RobeCzech (šev ZdrojAktivaci je přesně na tuto výměnu).

Typ je součástí signatury šablony. Důsledek: „Petr je v lednu" padne do jiné
šablony než „Petr je v Praze", přestože UD podpis je identický — a to je
žádoucí, protože jde o jiný druh atomu (ukotvení v čase vs v prostoru).

Kritická poznámka: pokrytí gazetteeru je omezené. Token bez typu dostane
typ=? a založí variantu šablony; podíl takových atomů je nutné měřit (§5, T3),
protože vysoký podíl znamená, že typová vertikála reálně nepracuje.

### P5 — Povrch se odhazuje, ale ne beze stopy

Instance je komprimovaná: z věty zbývá dvojice (subjekt s vlastnostmi, jádro
s vlastnostmi) plus polarita. Vše, co komprese odstranila, se však uchová
jako provenience: id věty, pozice středu, zdrojový povrch (`[v, Loc]`),
tvar tokenů. Pro pravidla je provenience neviditelná; pro čtení chování
zpětně je klíčová. Toto je závazek celého projektu (debug log, na který se
dá pověsit), přenesený do datové vrstvy.

### P6 — Koš: víc středů na větu, svazek překrývajících se atomů

Sliding window neprochází větu s jedním středem, ale zastavuje na každém
středu (kritérium středů: §4, R1). Každé zastavení dá atomární vzor; koš je
svazek všech atomů nad jednou větou.

„Soňa odjela z Prahy a cestuje do Liberce" dá koš čtyř atomů:
[soňa+odjet], [odjet + z,Gen,praha], [cestovat + do,Gen,liberec],
[soňa+cestovat]. Atomy se překrývají ve sdílených tokenech (odjet je ve dvou)
a překryv je rys, ne redundance: je to vodivost, po které později poteče
aktivace — dotaz na dílčí atom rozsvítí sousedy a odpověď přijde s kontextem
(„kdo odjel z Prahy?" → Soňa → „a jela do Liberce").

Koš zároveň řeší dříve zaparkovanou otázku n-árních vztahů („jela z Prahy do
Brna" má tři argumenty). Rozpad na binární atomy se sdílenou kotvou je
správná cesta, ale kotvou není umělý identifikátor události — kotvou je koš
sám plus sdílené tokeny. Identita události = členství v koši. Žádné
vymyšlené event-id neexistuje, a proto se nemůže rozejít s daty.

Důsledek pro r: poloměr řídí dvě veličiny najednou — velikost atomu a míru
překryvu (vodivost koše). Volba r je proto měřené rozhodnutí, ne konstanta
(§4, R4).

### P7 — Trojhodnotovost a zakládané sloty od první vrstvy

Polarita atomu má tři stavy: + (tvrzeno), − (popřeno, z Polarity=Neg na
predikátu), ? (neznámo). Explicitní negace je tvrzení; chybějící atom je
díra. Sloučení obou znamená uzavřený svět, ve kterém vše nezapsané je
nepravda — to je pro korpus faktů nepřijatelné.

Sloty, které věta nenaplnila, se zakládají s hodnotou ? — zejména kdy.
Zdůvodnění: prázdný slot lze později doplnit z kontextu nebo z jiného atomu;
slot, který v šabloně vůbec není, už nedoplní nic. Slot musí být rovněž
schopen nést odkaz (na jinou instanci) — krok 1 odkazy neplní, ale datový
typ slotu s nimi počítá, aby se model nemusel později lámat.

### P8 — Stopa jako invariant

Každý artefakt kroku 1 (šablona, atom, koš) musí být zpětně vysvětlitelný:
z jakých řádků pole vznikl, kterou hranou se naplnil který slot, proč padl do
dané šablony. Log má dvě úrovně přesně podle projektu: info (že průchod
probíhá a kudy), debug (co, jak, kde, s jakým výsledkem — rozsáhlý schválně).
Jakákoli optimalizace, která stopu zneprůhlední, je v tomto kroku zakázaná.

---

## 2. Datový model

Ukázky jsou ilustrační zápisy, ne předpis serializace.

Řádek pole (token):

```
{ tvar: "Praze", lemma: "Praha", upos: "PROPN",
  pad: "Loc", polarita_tokenu: null,
  deprel: "root", head: null,            # absolutní index v poli, null = root
  typ: "misto",                          # z gazetteeru / NameType; jinak "?"
  veta: 4, pozice: 3 }                   # provenience
```

Pole: posloupnost řádků; každá věta odsazena r prázdnými řádky na obou
koncích, mezi větami tedy leží 2r prázdných řádků a okno nemá jak přelézt
hranici — hranici drží geometrie (převzato beze změny z projektu).

Signatura: n-tice hodnot okna kolem středu; prázdný řádek má hodnotu
`<empty>`. Které vertikály do signatury vstupují, je rozhodnutí R2.

```
("<empty>", "AUX.cop", "ADP.Loc.case", "PROPN.Loc.root.misto", "<empty>")
```

Šablona: záznam signatura → id. Id je odvozené (pořadí vzniku) a s každou
změnou r se přečísluje — proto se nikdy neukládá jako reference; referencí
je signatura (převzato z projektu: mapování se ukládá jako tvary a pořadí).

Atom:

```
{ sablona: <signatura>,
  sloty: {
    kdo:   { hodnota: "soňa",  typ: "osoba" },
    jadro: { tvar: ["z","Gen","misto"], hodnota: "praha" },
    kdy:   "?"                                # založen, nenaplněn
  },
  pol: "+",
  provenience: { veta: 4, stred: 29, povrch: ["z","Gen"] } }
```

Slot je sjednocení tří možností: hodnota s typem, "?" (neznámo), nebo odkaz
`{ref: <atom>}` / `{neg_ref: <atom>}` — krok 1 odkazy nevytváří, typ je však
součástí modelu od začátku (P7).

Koš:

```
{ veta: 4,
  atomy: [<atom>, <atom>, ...],
  sdilene: [ { token: 30, v_atomech: [0, 1] } ] }   # vodivost
```

---

## 3. Metakód

```
VSTUP: CoNLL-U z UDPipe (věty s head, deprel, feats), poloměr r
VYSTUP: šablony, koše atomů, stopa

POSTAV_POLE(vety, r):
    pole ← []
    pro každou větu:
        přidej r prázdných řádků
        zapamatuj začátek věty z
        pro každý token: přepočti head na z+head (root → null),
                         doplň typ z gazetteeru/NameType (jinak "?"),
                         ulož řádek s proveniencí
        přidej r prázdných řádků
    vrať pole

JE_STRED(řádek):                     # rozhodnutí R1, výchozí varianta:
    řádek je root věty,
    NEBO řádek je jmenný s vlastním case-dítětem (obl/nmod jádro),
    NEBO řádek je VERB (i nekořenový, u koordinace)

SIGNATURA(pole, i, r):
    pro j od i−r do i+r:
        prázdný řádek → "<empty>"
        jinak → spoj vybrané vertikály (R2): upos, pad, deprel, typ
    vrať n-tici

NAPLN_SLOTY(pole, i):                # POUZE po hranách, nikdy z okna (P2)
    sloty ← { kdy: "?" }             # zakládané sloty (P7)
    pro každý řádek j s head = i:
        deprel=nsubj  → sloty.kdo ← (lemma, typ)
        deprel=case   → povrch ← (lemma_předložky, pád středu)
        deprel=obj    → sloty.co ← (lemma, typ)
        deprel=obl a typ=cas → sloty.kdy ← (lemma, typ)
    je-li střed jmenný: sloty.jadro ← { tvar:(předložka, pád, typ_středu),
                                        hodnota: lemma_středu }
    je-li střed VERB:   sloty.děj ← lemma středu; jádra visí na obl dětech
    vrať sloty

POLARITA(pole, i):
    Polarity=Neg na středu nebo jeho AUX/cop dítěti → "−", jinak "+"

PRUCHOD(pole, r):
    pro každý řádek i, kde JE_STRED:
        sig ← SIGNATURA(pole, i, r)
        šablona ← najdi podle sig, jinak založ (log: nová šablona)
        atom ← { šablona=sig, sloty=NAPLN_SLOTY(pole,i),
                 pol=POLARITA(pole,i), provenience=(věta,i,povrch) }
        vlož atom do koše své věty (log: atom + hrany, kterými se plnil)
    pro každý koš: sdilene ← tokeny vyskytující se ve více atomech
    vrať šablony, koše
```

Poznámka k determinismu: průchod nemá žádný náhodný ani učený prvek. Jediná
místa s vnějším obsahem jsou gazetteer (typ) a kritérium středů — obojí je
konečné, ručně psané a vyměnitelné, v souladu s dohodou „text dodá strukturu,
konečná tabulka dodá význam".

---

## 4. Otevřená rozhodnutí

R1 — Co je střed. Minimalisticky jen root; to však u souvětí a u vět
s několika příslovečnými určeními dá jediný atom a koš ztratí smysl.
Doporučená výchozí varianta je uvedena v metakódu (root + jmenná jádra
s case + slovesa) s tím, že správnost rozhodne měření T1/T2 — příliš úzké
kritérium sníží pokrytí, příliš široké zaplaví koše triviálními atomy.

R2 — Které vertikály do signatury. Doporučení: upos, pad, deprel, typ ano;
lemma ne. Lemma v signatuře znamená šablonu na každé sloveso a explozi (T2).
Lemma patří do instance (sloty, provenience), ne do identity šablony.
Předložka rovněž ne (P3). Toto rozhodnutí je hlavní páka, pokud T2 selže.

R3 — Hranice koše. Věta = koš. Souvětí spojené koordinací kořenů je jeden
koš (sdílený subjekt drží spoj). Samostatné věty se stejným referentem se
nespojují; krok 1 pouze zaznamená referenty koše, aby pozdější vrstva mohla
postavit most se sníženou vodivostí. Volné rozlévání přes hranice vět je
vědomě zakázáno — hranici musí držet geometrie, ne dobrá vůle.

R4 — Volba r. Výchozí r=2; měří se T2 pro r ∈ {1, 2, 3}. Protože r řídí
i vodivost koše (P6), není vyloučeno, že správné r pro identitu šablon a pro
překryv atomů se rozejdou — pak je řešením dvojí r (r_šablony, r_překryvu),
což model připouští, ale krok 1 nezavádí.

R5 — Synonymie sloves. Zaparkováno rozhodnutím: jde/přijde/dorazí jsou pro
match formou tři různé atomy. Krok 1 to neřeší, pouze měří dopad (T5).
Budoucí řešení je vertikála synonymie (ručně nebo z RobeCzech), tedy další
sloupec, ne zásah do mechaniky.

---

## 5. Kritická místa a testy proveditelnosti

Testbed: jedna uzavřená doména (kdo-kde-kdy, 50–100 skutečných českých vět),
skutečný UDPipe projektu, žádná ručně učesaná metadata. Výstupem jsou čtyři
čísla a stopy k ručnímu čtení.

T1 — Pokrytí extrakce. Podíl vět, z nichž vznikl aspoň jeden atom s naplněným
kdo i jádrem. Kritérium: ≥ 70 % extrakce žije; 50–70 % opravitelné (mapování
deprel → role, kritérium středů); < 50 % problém je v přístupu k plnění rolí.

T2 — Poměr šablon k větám. Jediný test schopný koncept vyvrátit. Kolem 0,2
je zdravé zobecnění; 0,2–0,5 přijatelné; nad 0,7 okno nezobecňuje a je nutné
škrtat vertikály ze signatury (R2), zmenšit r, nebo — pokud nic nepomůže —
přiznat, že identita šablon přes lineární okno na volném českém slovosledu
nedrží (viz slabé místo S1 níže).

T3 — Podíl slotů "?". Zvlášť podíl atomů s typ=? (selhání gazetteeru) a
s kdy=? (očekávaně vysoký, není chyba — měří se pro pozdější vrstvu času).

T4 — Chyby parseru. Na ručním vzorku 20 vět: kolik chybných parsů UDPipe
rozbilo role. Odděluje chyby vlastní mechaniky od chyb vstupu; bez tohoto
rozlišení nelze T1 interpretovat.

T5 — Dopad synonymie. Kolik dvojic atomů se míjí pouze lemmatem predikátu.
Vysoké číslo posouvá R5 z „později" na „hned po kroku 1".

Slabá místa návrhu, přiznaně:

S1 — Volný slovosled. „Petr je v Praze" a „V Praze je Petr" dají různá okna,
tedy různé šablony. To nafukuje T2, ale nerozbíjí pozdější match: pravidla
matchují pod-vzor (pád, typ) v instanci, ne celou signaturu — dvě šablony
téhož vztahu koexistují a obě matchnou. Cena je tedy v počtu šablon
(a v počtu anotací definičních šablon později), ne v korektnosti. Mitigace,
pokud T2 selže právě na tomto: kanonizace pořadí okna podle deprel před
složením signatury — projekt už analogii má (vektor se před složením řadí do
pořadí sloupců); zde by se řadil do pořadí rolí.

S2 — Gazetteer nepokryje obecná jména („ve městě", „na venkově"). Typ zůstane
"?" a atomy se štěpí. Měří T3; řešení je výměna zdroje typu za clustery
(šev), ne úprava mechaniky.

S3 — Elipsy a vsuvky. „Petr je v Praze, Jindra v Brně" — druhá klauze nemá
sloveso a root parsuje různě. Krok 1 to nemusí umět; musí to však být vidět
ve stopě jako přeskočeno s důvodem, ne jako tichá díra (P8).

---

## 6. Co krok 1 vědomě neřeší

Definiční vrstva (věty se „znamená" jsou v tomto kroku obyčejné věty a
vytvoří obyčejné šablony — jejich anotace rolí je krok 2). Logické spojky
a meta-hrany (pokud/jen když/a/nebo jsou v kroku 1 jen tokeny). Aktivace a
její správnost (koš pouze ukládá sdílené tokeny jako budoucí vodiče).
Čas jako interval a skládání bod+bod→interval (krok 1 jen zakládá kdy=?).
Odkazy a jejich rozřešení (model slotu s nimi počítá, plnit je bude
pozdější vrstva).

Pořadí dalších kroků se odvíjí od výsledků testů: T2 v pořádku → krok 2
(definiční šablony a jejich anotace); T5 vysoké → nejdřív vertikála
synonymie; T1 nízké → revize kritéria středů a mapování rolí, opakovat.
