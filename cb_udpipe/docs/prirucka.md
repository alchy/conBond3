# cb-udpipe — příručka

Otázky, které padly při stavbě, a pasti, do kterých se dá spadnout. Psáno
proto, aby je nikdo nemusel objevovat podruhé.

---

## Pasti, na které se doplatilo

### `isdigit()` proti `isdecimal()`

> `int(c[0])` spadlo na tokenu `²`, protože `"²".isdigit()` je `True`, ale
> `int()` na tom spadne. Článek o betonu má `m²` a shodil stavbu celého
> korpusu na 86 článcích. *(conBond2, `core/agents/base.py`)*

V `conllu.py` je proto `_je_cele_cislo()` na jednom místě a používá
`isdecimal()`. Má vlastní regresní test.

### Interpret pro vendorovaný nástroj

`./cb-udpipe.py` se spouští **systémovým** Pythonem přes shebang. UDPipe
v něm nenajde ani numpy, natož TensorFlow. Proces UDPipe se proto spouští
interpretem z `.venv`, ne `sys.executable`.

Je to ta hranice z § 19 politiky v praxi: náš kód nepotřebuje nic a běží
kdekoli, vendorovaný nástroj si nese těžké závislosti. **Hranice vede po
procesu, ne po prostředí.**

### Rodičovský strop musí být větší než potomkův

`start` se odpojí na pozadí a čeká, až služba odpoví na `/version`. Potomek
mezitím čeká na UDPipe (až 120 s). Když rodič čekal jen 15 s, ohlásil
neúspěch nad procesem, který normálně startoval — a v `run/` zůstal běžící
proces, o kterém `start` tvrdil, že nenaběhl.

Rodičovský strop je teď `start_timeout_s + 20 s`.

### Jméno modelu a `default_model`

Server ze jména modelu odvozuje prefixy po pomlčkách:

```
czech-pdtc-ud-2.17-251125 → czech-pdtc-ud-2.17 → czech-pdtc-ud → czech-pdtc → czech
```

Proto v conBondu2 fungovalo `default_model = czech`. Náš model se ale jmenuje
`cs_all-ud-2.17-251125` a ten `czech` nedá — server spadl na
`assert self.default_model in self.models_by_names`.

Jméno `czech` se teď uvádí mezi jmény napřímo, takže to nezávisí na tom, jak
se model jmenuje.

### Vnořený submodul

UDPipe má vlastní submodul `wembedding_service`. Bez něj server spadne na
`ModuleNotFoundError: No module named 'wembedding_service.wembeddings'`.

```bash
git submodule update --init --recursive
```

`--recursive` je nutné. A submodul `ufal/udpipe` musí být na větvi
**`udpipe-2`** — master je UDPipe 1 a `udpipe2_server.py` tam vůbec není.

### České uvozovky v `git commit -m`

Rozbíjejí bash. Commit zprávy tohohle modulu se píšou přes soubor
(`git commit -F`). *(Zapsáno i v jellyAI3 jako past č. 7.)*

### Inline `-F data=` ořezává vstup

> Data se posílají PŘES SOUBOR, NE inline: inline `-F data=…` ořezává velký
> vstup na ~485 znaků — past, kvůli které bible ztrácela 95 % textu.
> *(conBond, `core/annotate.py`)*

Nás se netýká přímo (posíláme `application/x-www-form-urlencoded`), ale test
na dlouhý vstup v `test_upstream.py` je levný a ta past stála dva projekty
hodně času.

---

## Otázky, které padly při stavbě

### Proč se cache neptá dřív než UDPipe?

Protože **segmentaci dělá UDPipe**. Před fází 1 není známo, jaké věty ve
vstupu jsou, takže se nedá zjistit, na co se cache ptát. Fáze 1 je proto
nevyhnutelná — naštěstí stojí jen 2,7 % času (naměřeno).

### Proč se do fáze 4 posílá CoNLL-U a ne text?

Dva důvody. Kdyby se poslal text, server by ho tokenizoval znovu po svém
a naše oprava by se zahodila. A druhý, doložený v conBondu2:

> „dávkou je tokenizér občas slepí a čísla vět by přestala odpovídat
> označení." *(`scripts/ukazka.py`)*

Když je vstup CoNLL-U, segmentace je dána vstupem a stát se to nemůže.

### Proč je verze tokenizéru v klíči cache?

Aby změna pravidel cache **neznehodnotila**. Staré záznamy zůstanou platné pro
svou verzi a nové se doplní vedle nich. Bez toho by se po každé úpravě
seznamu zkratek musela cache zahodit — a to je právě to, co má být hodnota,
ne odpad.

### Proč se nesjednocují pomlčky a uvozovky?

Vypadá to jako přesně ta práce, kterou má modul dělat. Měření ale ukázalo, že
**by nepomohlo a něco by stálo**:

* druh pomlčky hranice tokenů vůbec nemění (ověřeno na `1890–1938`,
  `1890-1938`, `1890 – 1938` i na nezlomitelné mezeře),
* en-dash proti spojovníku nese informaci, na které stojí `AG-BIO` —
  rozlišuje rozsah `1926 – 2011` od názvu `Praha - Libeň`.

Podrobně v `koncepce.md` § 13.6.

### Proč se scelují čísla, ale ne jména?

`30 000` je jeden údaj a UDPipe z něj dělá dvě samostatná čísla, takže vrstva,
která počítá, naměří `30`. To je vada tokenizace.

`Karel Čapek` jsou naproti tomu **správně** dva tokeny podle UD. Že jde
o jednu osobu, je vlastnost entity, ne tokenu — a scelování jmen má
v conBondu rozsáhlý měřený zápis o tom, jak snadno se pokazí (44 dvojic
z 2002 spojených přes `flat` byly ve skutečnosti dva různí lidé).

### Proč měření běží přes klienta a ne přímo?

Služba drží cache otevřenou pro zápis a dva zapisovatelé nad jedním souborem
znamenají ztrátu dat. Vedlejší zisk: měří se tím skutečná cesta včetně
serializace.

### Proč vyšlo zrychlení 1,0×?

Protože cache už byla plná z předchozího běhu — „první" průchod z ní taky
bral. **Zrychlení se měří jen od studené cache:**

```bash
./cb-udpipe.py stop
rm cb_udpipe/data-persistent/cache/*.jsonl
./cb-udpipe.py start
./run-python cb_udpipe/scripts/mereni.py
```

Ostatní čísla na stavu cache nezávisí.

---

## Co se osvědčilo

**Testy nad zmraženými daty ze skutečného UDPipe.** Odhalilo to detail, který
by vymyšlená data neměla: UDPipe píše do `MISC` hodnoty jako
`SpacesAfter=\n\n`, kde `\n` jsou dva znaky, ne zalomení. Naivní parsování by
rozbilo zápis zpátky — a na něm stojí fáze 4.

**Podstrčený upstream, který se chová jako skutečný.** První verze dělila věty
po každé tečce, takže rozsekala `R.U.R. je drama.` na dvě. Testy by pak měřily
chování falešného serveru místo našeho kódu. Pravidlo „nedělit po jednopísmenné
zkratce ani po číslici" je převzaté z jellyAI3.

**Zkouška shody tváří (`T-K3`).** Odhalila skutečnou vadu: `tokenize_only`
přes síť ztrácel `sent_id`, protože ho serializace neposílala. V procesu ho
věta nesla, po drátě ne — a bez té zkoušky by se to poznalo až tehdy, když by
na chybějící pole někdo sáhl.

**Ověřovat ukázky v README spuštěním.** Dvě hodnoty v prvním návrhu
neodpovídaly skutečnosti (`feats` mělo víc klíčů, `misc` bylo `None`, ne
slovník). Ukázka, která se rozejde s kódem, je horší než žádná.
