# Koncepce cb_field — proč je to postavené takhle a ne jinak

Modul vznikal po malých krocích v dialogu (2026-08-03); u každého
rozhodnutí je zapsáno, z čeho plyne. Pravidlo projektu: rozhodnutí se
mění za číslo, ne za dojem.

## 1 · Pole je matice vah, ne objektový graf

Řádek = slovo, vertikála = dvojice **atribut=hodnota**, buňka = váha.
Aktivace vertikály je váha (výchozí 0.7); 0.0 = žádná aktivace.
Plyne ze zadání J.: „build_baskets by udělalo místo klasického objektu
takovéto matice, fixní x/y jako na vizualizaci." Důsledek: shoda šablon,
podobnost košů i šíření aktivace jsou lineární algebra (numpy —
schválená výjimka z § 19), ne procházení slovníků.

**Osa x je append-only registr** (`VerticalRegistry`): jednou přidělený
index se nikdy nepřečísluje, jinak by se rozbily uložené matice (§ 14).
**Osa y koše je fixní**: 2r+1 řádků, za hranicí věty nuly, střed vždy
na y=r — nula nic netvrdí (0.0 = žádný vliv), takže doplnění nelže.

## 2 · Váha: −1…+1, znaménko je druh vazby

Zadání J.: start 0.7, rozsah „−1.0f až +1.0f" (odtud float32), a
„důležité je, zda jde o negativní, nebo pozitivní vazbu". Záporná váha
se používá významově: prohraný výklad víceznačnosti (`PronType=Rel@−0.7`
v otázce), záporná deiktika (`nikdy → ANCHOR=time@−0.7` — výrok o čase,
ale proti). Meze se hlídají při zápisu, ne až v počítání.

## 3 · Dvě reprezentace: METADATA je primární

METADATA = bezeslovná matice (jen váhy vertikál gramatiky); COMPLETE
navíc `WORD=<UPOS>:<lemma>`. Z COMPLETE jde METADATA odvodit, obráceně
nikdy — proto se publikuje a ukládá COMPLETE a ořezává se při čtení.
Břitva, co do bezeslovné matice smí: **co roste s gramatikou, ano;
co roste se světem, ne** (P1: tvarů je konečně mnoho).

## 4 · Multiatribut se expanduje, sloty se předalokují

Parser vrací víceznačné rysy slepené čárkou (`Gender='Fem,Neut'`).
Každá hodnota = vlastní vertikála s vlastní vahou; v rozvinutých
řádcích má každý klíč `FEAT_SLOTS=4` slotů (naměřené maximum 2,
dvojnásobná rezerva). Víc hodnot než slotů = hlasitá chyba.

## 5 · LEM/QLEM: lemma jen tam, kde je mluvnice

LEM vertikálu dostane zavřená třída UD (všech 8; NUM jen bez číslic —
„pět" ano, „125" ne, číslice jsou nekonečná množina) a zájmenné
příslovce (ADV s PronType). Klíč nese i UPOS: **naměřená kolize**
„jak" ADV × SCONJ — jedna vertikála by slila dvě funkce. Stejný lék má
WORD (`stát` NOUN × VERB).

**Tázací kde je jiné kde**: v tázací větě (otazník — `is_question`)
dostane slovo s `PronType=Int` prefix `QLEM=` a víceznačné `Int,Rel`
rozhodnou váhy (v otázce Rel záporně, v oznamovací větě Int záporně).
Parser si nebyl jistý; věta ano.

## 6 · Kotvy: ukotvení v prostoru, čase, množství — podle PDT

Zadání J.: „LEM by měl umět pomoci ukotvit v prostoru a čase, ale
univerzálně… prostor a čas je vlastně též místo a činnost… abychom
neměli lemů moc ani málo." Řešení stojí na prior art (určitě to někdo
řešil): **funktory PDT** (kde=LOC, kam=DIR3, odkud=DIR1, kudy=DIR2;
kdy=TWHEN, odkdy=TSIN, dokdy=TTILL; kolik=EXT; jak=MANN; proč=CAUS),
**Reichenbach** pro čas (past/pres/fut = vztah E–S; dokonavý prézens
„přijde" → fut, kotva jde po smyslu, ne po tvaru) a **AMR**: otázka =
výrok s neznámou v jedné souřadnici (`QANCHOR=`), odpovídání = zaplnění.

Zdroje kotev: morfologie (Tense, Number na NOUN/PROPN/PRON/VERB/AUX,
NUM), NameType (Geo→space, Giv/Sur→entity) a dvě konečné tabulky
zavřených slov (tázací, ukazovací) — „text dodá strukturu, konečná
tabulka dodá význam". Obsahová slova přispívají jen dimenzí/typem,
hodnota zůstává ve WORD. Bilance: kotvy ≤ ~25 vertikál navždy.

## 7 · Hierarchie kotev jsou vazby, ne dvojí buňky ani masky

Otázka J.: „proč maska, když máme váhu?" — maska je binární degenerát
váhy. Hierarchie (`time:past` JE `time`) proto žije jako **vážené vazby
mezi vertikálami v registru** (`link`, ukládají se se save/load).
Párování otázka↔odpověď = jeden krok šíření (`spread`: v + v·L)
a skalární součin — obě strany stečou do dimenzního uzlu. Dvouúrovňové
klíče v řádcích (materializovaná hierarchie) byly zavrženy: redundance
bez užitku, když je matmul zadarmo.

## 8 · SUBPOS a jmenná negace: z xpos jen to, co jinde není

Empirie (baterie vět): poziční tag přidává proti feats **SubPOS**
(Db zájmenná příslovce, P7 zvratné se/si, C= číslice vs Cl slovní
číslovka, Vc kondicionál) a **Negation u jmen** (přítel/nepřítel;
feats Polarity u jmen nemají). Jen tyhle dvě věci se emitují — zásada
**jedna skutečnost = jedna vertikála** (dvojí hlas by nafoukl váhy).

## 9 · SentenceField: jedna pracovní úroveň

Revize po průchodu očima nového vývojáře („působí to zmateně —
jde o logiku tříd a metod"): volné funkce zůstaly jako ladicí vrstvy,
pracovní úroveň je třída. Konstruktor spočítá jednou otázkovost, koše,
aktivace; registr se rodí s kotevními vazbami (nic se nepamatuje);
matice se staví dvoufázově (napřed růst registru, pak vektorizace —
past různě širokých vektorů zmizela). **Pole = jedna věta** (`from_text`
odmítne víc vět — žádné tiché vzetí první). Trojice pohledů
`metadata`/`complete`/`array` je stejná na větě i koši (návrh J.).

## 10 · Kukátko: okno, ne ovládání

Viewer jen čte (`run/current.json`, poll 1 s), pravidla vertikál žijí
v Pythonu a stránka kreslí hotové aktivace — pravidla nesmí žít dvakrát.
Šířky mřížky se počítají explicitně v px (Firefox počítá intrinsic
šířky vnořeného flexu/gridu jinak než Chrome — naměřeno).
