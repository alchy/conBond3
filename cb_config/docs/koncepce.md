# Koncepce cb_config — proč je to postavené takhle a ne jinak

## 1 · Proč vznikl: tři kopie téhož

Validátor konfigurace stál v `cb_logger`, `cb_udpipe` i `cb_bond`, pokaždé
skoro doslova stejný. Dohromady 1 190 řádků, z nichž se ~1 000 opakovalo;
lišily se jen konstanty (rozsah portů, seznam cest) a u dvou modulů jedna
kontrola navíc.

Kopie tam byly **úmyslně**: politika § 4 měla konečný seznam sdílených
modulů (jen `cb-logger`) a rozšířit ho znamenalo změnit politiku. To
pravidlo řešilo, aby moduly nezačaly na sobě viset kvůli maličkostem —
a bylo správné, dokud byly kopie dvě.

U třetí se poměr obrátil (rozhodnutí J. 2026-08-05). Validátor je čistá
funkce bez stavu, bez sítě a bez závislostí, kterou potřebuje **každý**
modul dřív, než cokoli udělá. Sdílet ji nestojí nic, co by pravidlo
chránilo.

Po sloučení: 362 řádků v modulech + 375 sdílených místo 1 190, a hlavně
jedna implementace — oprava chyby ve validátoru už neznamená tři commity.

## 2 · Knihovna, ne služba

Nemá port, REST API ani ovládací program. Konfiguraci potřebuje každý
modul *před* startem, takže kdyby ji poskytovala služba, nešlo by ji
použít k jejímu vlastnímu startu — kruh, který by se rozbil až za provozu.

Je to nová kategorie v projektu: sdílený modul, který není služba. Politika
§ 2 popisuje tvar modulu, který službou je; tenhle z něj vynechává
`api.py`, `client.py`, `control.py`, `run/` a porty, protože nemá co
obsluhovat.

## 3 · Implementace je PŘEVZATÁ, ne napsaná znovu

Sdílený validátor je doslovný přenos toho z `cb_logger`, který se
osvědčil — včetně znění hlášek. Důvod je praktický a naměřený: při první
verzi jsem hlášky přeformuloval („čekám integer" místo „očekáván
integer") a spadlo **53 testů** sourozenců, které na jejich znění stojí.
Stěhování a přeformulování jsou dvě změny; dělat je najednou znamená
nevědět, která rozbila co.

## 4 · Tři místa, kde se moduly liší — a jak se to řeší

Sloučení neznamená, že jsou moduly stejné. Liší se v trojím a pro každé
je jeden parametr:

**`checks`** — kontroly, které schéma vyjádřit neumí. cb-udpipe hlídá
rozsah portů, cb-bond navíc to, že `data_root` je absolutní a datové
cesty relativní.

**`path_specs`** — dvojice (klíče, základna). Většina modulů má jednu
základnu, cb-bond dvě: běhové cesty patří k modulu (PID není datum, je to
stav procesu), datové leží mimo repozitář.

**`post_resolve`** — dorovnání cest, které seznamem klíčů vyjádřit nejde.
cb-logger má cesty UVNITŘ pravidel směrování, tedy v poli proměnné délky;
vyjmenovat je předem nejde a hádat podle jména klíče by se rozešlo
s obsahem, jakmile přibude pravidlo s klíčem, který cestu nenese.

## 5 · Otisk patří do `_meta`, ne do konfigurace

`fingerprint` a `path` jsou **odvozené**, ne nastavené. Kdyby stály vedle
skutečných klíčů, přestalo by na výstupu platit `additionalProperties:
false` ze schématu — validace by zakazovala klíč, který si tam funkce sama
přidá.
