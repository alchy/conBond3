# cb-udpipe

Wrapper nad UDPipe 2: **pošle se věta, dostane se kvalitní rozbor.**

Podrobná dokumentace je v `docs/`; tenhle soubor je rozcestník pro toho, kdo
modul udržuje. Kdo ho jen volá, chce `README-UDPIPE.md` v kořeni projektu.

## K čemu je

Dvě práce, obě jádro modulu:

1. **Perfektně tokenizovat.** UDPipe tokenizuje česky špatně: rozseká řadové
   číslovky (`20 . století`), zkratky (`tzv .`, `R . U . R .`) i čísla
   s oddělovačem tisíců (`30 | 000`). Změřeno: **17,6 % vět** po opravě
   vypadá jinak.
2. **Pamatovat si rozbory.** Cache po větách; druhý průchod týmiž daty je
   **27× rychlejší**.

Cache má ještě druhého odběratele, a ten rozhoduje o jejím tvaru: je to
rostoucí sbírka rozebraných českých vět se zdrojem, tedy to, z čeho se dá
jednou trénovat vlastní model. Proto se ukládá všech deset sloupců CoNLL-U
a klíč nese model i verzi tokenizéru.

## Ovládání

```
./cb-udpipe.py start   [--config PATH] [--foreground]
./cb-udpipe.py stop    [--timeout SEC]
./cb-udpipe.py restart
./cb-udpipe.py reload
./cb-udpipe.py status  [--json]
```

Návratové kódy: `0` uspěl · `1` selhal · `2` špatné argumenty nebo
konfigurace · `3` služba neběží.

`start` zvedne **nejdřív UDPipe** a teprve po něm naši službu. Kdyby to bylo
naopak, odpovídala by `503` na každý dotaz, dokud by UDPipe nenaběhl — a
`start` by mezitím ohlásil úspěch.

## Porty

| port | co |
|---|---|
| 42200 | REST API |
| 42201 | vlastní instance UDPipe 2 |

Rozsah modulu je 42200–42299 (`README-MODULES.md` § 5). Konfigurace se při
startu ověřuje i proti němu: cizí port se jinak pozná až tím, že se dva moduly
poperou o totéž číslo.

## Rozhraní

| bod | co dělá |
|---|---|
| `GET /version` | verze modulu, rozhraní a tokenizéru — **mimo** `/v1/` |
| `GET /v1/health` | stav, dostupnost UDPipe, načtený model, velikost cache |
| `GET /v1/config` | skutečně použitá konfigurace včetně cesty |
| `GET /v1/summary` | počty podle metody a výsledku |
| `GET /v1/cache/stats` | počet vět, velikost, poškozené řádky |
| `POST /v1/parse` | `{"text": …, "trace": …}` → věty s tokeny |
| `POST /v1/tokenize` | jen segmentace a tokenizace, bez tagů |

## Závislosti

| závislost | povinná? | co při výpadku |
|---|---|---|
| **UDPipe 2** (vlastní instance, 42201) | **ano** | `503` s typem `upstream_unavailable`; nikdy prázdná odpověď |
| **cb-logger** (42100) | ne | degradace — klient spooluje a modul běží dál |

Rozdíl je záměrný: bez rozboru nemá modul co vracet, kdežto bez logu ano.
Kdyby padlé logovátko shodilo modul, byla by nejméně důležitá součást zároveň
nejkřehčí.

## Velká data mimo git

| co | velikost | licence |
|---|---|---|
| `cs_all-ud-2.17-251125` | 357 MB | **CC BY-NC-SA** (nekomerční) |
| RobeCzech (embeddingy) | 484 MB | dle ÚFAL |

```bash
cb_udpipe/scripts/fetch-models.sh --from-conbond2 ../conBond2
cb_udpipe/scripts/fetch-models.sh --check
```

Ruční postup a licence jsou v `ZDROJ.md`. Model **nesmí do repozitáře**; cesta
k němu je v `.gitignore` a `start` bez něj skončí kódem `2` s návodem.

Zdrojáky UDPipe 2 jsou submodul na větvi `udpipe-2` (master je UDPipe 1).
Po naklonování projektu:

```bash
git submodule update --init --recursive
```

`--recursive` je nutné: UDPipe má vlastní vnořený submodul
`wembedding_service`, bez kterého server nenaběhne.

## Registr prahů

Naměřeno 2026-08-03 na vzorku 500 vět, model `cs_all-ud-2.17-251125`,
tokenizér `6247b8b7a5c8`. Úplná data v `docs/mereni-2026-08-03.json`.

| id | hodnota | co ovlivňuje | odkud se vzala |
|---|---|---|---|
| `batch_sentences` | 60 | vět v jednom dorozboru | conBond2 `Prijem.rozebrat` — jedno volání na článek je moc, jedno na větu pomalé |
| `abbrev_min_pairs` | 2 | kolik párů ⟨písmeno⟩⟨tečka⟩ tvoří zkratku | conBond `normalize.py`, jellyAI3 — pod 2 by se chytila iniciála `K. Čapek` |
| `max_sentence_words` | 1000 | kdy se věta přeskočí | mez serveru UDPipe, ne naše volba; ve vzorku 500 vět se neuplatnila |
| `max_request_bytes` | 2 MiB | strop na požadavek | polovina serverového stropu (4 MB), ať chyba vznikne u nás s lepší hláškou |
| `request_timeout_s` | 600 | strop na volání UDPipe | conBond2; naměřeno 41,6 s na 500 vět, rezerva je velká |
| `start_timeout_s` | 120 | čekání na start UDPipe | *(neměřeno)* — načtení modelu 357 MB |

## Naměřená čísla

| co | hodnota |
|---|---|
| vět s opravou tokenizace | **17,6 %** (176 z 998) |
| podíl tokenizace na čase rozboru | **2,7 %** |
| zrychlení druhým průchodem | **27×** (41,6 s → 1,5 s) |
| cache na větu | 2 747 B (26 tisíc vět ≈ 70 MB) |
| neshod cache proti čerstvému rozboru | **0** |

Poslední řádek je protiváha: podíl zásahů jde nafouknout volnějším klíčem,
takže sám o sobě nic neneznamená. Nula neshod říká, že klíč je správně úzký.

## Co modul vědomě neřeší

* **Scelování jmen a entit.** `Karel Čapek` zůstávají dva tokeny — je to
  správně podle UD a scelení je práce entitní vrstvy.
* **Výklad konstrukcí.** Že `23.` je jeden token, je naše práce. Že levá půle
  životopisné závorky je narození, je výklad a patří `AG-BIO`.
* **Sjednocení pomlček, uvozovek a nezlomitelných mezer.** Změřeno, že by to
  nepomohlo (druh pomlčky hranice tokenů nemění) a něco by stálo (en-dash
  proti spojovníku nese informaci pro `AG-BIO`). Viz `docs/koncepce.md`
  § 13.6.
* **Doplňování diakritiky, detekci jazyka, víc modelů zároveň.**
* **Dotazovací rozhraní nad cache.** Kdo potřebuje vidět dovnitř, otevře
  JSONL — je to čitelné očima schválně.

## Testy a měření

```bash
./run-python -m unittest discover -s cb_udpipe -t .
./run-python cb_udpipe/scripts/mereni.py
```

Testy `conllu`, `tokenize` a `cache` **nepotřebují běžící UDPipe** — je to
čistá logika nad zmraženými daty a to je záměr, ne náhoda. Měření běží proti
běžící službě přes klienta, aby se neotvírala druhá cache nad týmž souborem.
