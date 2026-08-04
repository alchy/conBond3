# Příručka cb_field — otázky ze stavby a pasti

Zapsáno při stavbě (2026-08-03). Když do některé pasti spadneš znovu,
připiš sem, jak ses z ní dostal.

## Otázky, které při stavbě padly

**Proč jsou koše na krajích věty menší, ale matice koše ne?**
Slovníkové pohledy ukazují, co ve větě opravdu je (čitelnost). Matice
potřebuje pevný tvar (porovnatelnost) — a nulový řádek nelže, protože
0.0 znamená „žádná aktivace". Střed je tak vždy na y=r.

**Proč `Gender='Fem,Neut'` nejsou dvě šablony, ale dvě vertikály?**
Parser si nebyl jistý; nejistota se nese dál jako dvě aktivace s vahami.
Kontext pak může jednu stranu potlačit (viz PronType v otázce), aniž se
cokoli zahodí.

**Proč tázací „kde" nekotví stejně jako „tam"?**
„Kde" poptává (QANCHOR — neznámá v souřadnici, po vzoru AMR
amr-unknown), „tam" poskytuje (ANCHOR). V oznamovací větě kotví „kde"
na straně odpovědi (vztažné užití). A kde ≠ kam ≠ odkud ≠ kudy — čtyři
funktory PDT (LOC, DIR3, DIR1, DIR2), čtyři upřesnění.

**Proč „přijde" kotví budoucnost, když má Tense=Pres?**
Dokonavý prézens v češtině míří do budoucnosti (Aspect=Perf + Fin).
Kotva jde po smyslu, ne po tvaru — jinak by se „Kdy přijde?" nikdy
nespároval s „Přijde zítra."

**Proč se hierarchie kotev nedělá maskou ani dvojími buňkami?**
„Proč maska, když máme váhu?" — maska je binární degenerát váhy.
Vážené vazby v registru jsou jeden mechanismus pro hierarchii,
mosty i budoucí synonymii; dvojí buňky by byly materializovaná
redundance, kterou by musel hlídat invariant.

**Proč pole odmítne text se dvěma větami?**
`.sentences[0]` v ukázkách sváděl k tichému zahození zbytku textu.
Pole = jedna věta; kdo má odstavec, rozdělí ho vědomě sám.

## Pasti

**Spuštění systémovým `python`.** Jiný interpret, jiné závislosti,
divné výsledky bez chybové hlášky. Vždy `./run-python` (nebo
`./run-python cli` pro konzoli).

**Vektory z různých okamžiků růstu registru.** `vectorize` vrací vektor
o délce registru *v té chvíli* — dva vektory z různých chvil nejdou
sečíst. `SentenceField.matrix()` to řeší dvoufázově; když pracuješ
s registrem ručně, napřed nech vyrůst, pak vektorizuj (`grow=False`),
nebo použij `spread`, který kratší vektor doplní nulami.

**Porovnávání matic dvou vět bez sdíleného registru.** Každá věta
s vlastním registrem má vlastní osy — sloupec 12 znamená pokaždé něco
jiného. Sdílej registr parametrem `registry=` a ukládej ho.

**float32 a 0.7.** V matici je 0.69999998…; `unvectorize` proto
zaokrouhluje na 6 míst. Nikdy neporovnávej buňky na přesnou rovnost
s Python floatem — používej round-trip přes `unvectorize`, nebo
`np.isclose`.

**`activations` bez `question`.** Volání nižší vrstvy napřímo s výchozím
`question=False` dá u tázací věty LEM místo QLEM — a nic nespadne.
Pracovní úroveň (`SentenceField`) to řeší; když saháš dolů, mysli na to.

**Přejmenování/přečíslování vertikál.** Nikdy. Registr je append-only;
změna jména klíče = nová vertikála. Uložené matice se odkazují indexem.

**Firefox a intrinsic šířky.** Gecko počítá max-content vnořeného
flexu/gridu jinak než Chrome — rámečky kukátka končily ve ¾. Řešení:
šířky mřížky se počítají explicitně v px. Když stránku upravuješ,
zachovej to.

**Kukátko „nic neukazuje".** Stránka čte `run/current.json` — dokud
nikdo nezavolá `sentence.show()`, není co kreslit. A `run/` je běhový
stav: smazání je neškodné, jen zmizí poslední publikovaná věta.

**Logy parse volání.** Každé `parse()` jde přes službu cb-udpipe a je
vidět v kukátku loggeru (http://127.0.0.1:42102/) včetně celých tokenů —
hodí se, když nevěříš vlastním očím.

**Index věty v souboru není pozice v korpusu.** Fixace čísluje od nuly
sama za sebe; složený korpus má věty za sebou. Převod dělá návratová
hodnota `add_to_corpus` (a `corpus.positions[jméno]`) — otázka
z `otazky-201.json` míří na index 6, ale v korpusu je to pozice 2918.
Kdo indexy zamění, měří na cizí větě a ničeho si nevšimne.

**Zadání cb_bond ukazuje větu o dálnici na indexu 12.** Ve skutečnosti
je v `korpus-001.json` na indexu 4 (vzorek v zadání je zkrácený). Test
se na 12 vázat nesmí.

**Jméno souboru nesmí nic znamenat.** Program ho bere jako neprůhledný
identifikátor. Žádné mapy klíčované doménou („3xx je bible") — co má
program vědět o obsahu, stojí uvnitř souboru.
