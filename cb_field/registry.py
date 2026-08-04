"""Append-only registr vertikál — pevná osa x maticové podoby koše.

Vertikála je dvojice atribut=hodnota ("UPOS=NOUN", "Case=Gen", "LEM=do").
Registr jí přiděluje sloupcový index; jednou přidělený index se už nikdy
nemění a nic se nemaže — uložené matice se na sloupce odkazují číslem
a přečíslování by je tiše rozbilo (§ 14 politiky).

Serializace do pole a zpět (vectorize/unvectorize) je zároveň zkouška
funkčnosti: z vektoru vah jde přes registr zrekonstruovat tentýž JSON
objekt {vertikála: váha}, který do něj vstoupil.

Numpy je vědomá, zdůvodněná výjimka z pravidla „moduly bez závislostí"
(§ 19): koše jsou matice vah a maticové počítání je přesně to, k čemu
numpy je. Zapsáno v requirements.txt.
"""

import json
import os
from pathlib import Path
from typing import Iterable, Iterator, Mapping

import numpy as np

#: Verze formátu souboru registru; neznámou verzi čtečka odmítne (§ 14).
#: v2 přidává verzi osy a uvolněné sloupce (krok 3 handoveru); v1 se
#: čte dál — starší soubory žádné custom vertikály nemají.
FORMAT_VERSION = 2
READABLE_VERSIONS = (1, FORMAT_VERSION)

#: Prefix custom vertikál — jediné osy, které soutěží o místo (limit
#: v grafu, krok 2). Osy z UDPipe stojí vedle a set_custom_axes na ně
#: nesmí sáhnout.
CUSTOM_PREFIX = "CUSTOM="

#: Datový typ vektorů a matic. float32 stačí na váhy v rozsahu −1…+1
#: a matice jsou poloviční proti float64.
DTYPE = np.float32


class VerticalRegistry:
    """Přiděluje vertikálám stabilní sloupcové indexy; jen roste.

    Dvě instance nad týmž souborem dají tytéž indexy — o pořadí rozhoduje
    pořadí prvního přidání, ne obsah klíče.
    """

    def __init__(self, keys: Iterable[str] = (), anchors: bool = True) -> None:
        self._keys: list[str] = []
        self._index: dict[str, int] = {}
        #: Vážené vazby mezi vertikálami: (od, do) → váha. Jeden mechanismus
        #: pro hierarchii kotev, mosty otázka↔odpověď i budoucí synonymii.
        self._links: dict = {}
        self._matrix_cache = None
        #: Čítač změn vazeb — levný klíč pro cache odvozené z L (rozšířené
        #: pytle v matching). Růst klíčů starou cache neruší (nové sloupce
        #: mají ve starých větách nulu); změna vazby ano.
        self.link_version = 0
        #: Čítač změn OBSAZENÍ os (krok 3 handoveru): s limitem custom
        #: vertikál se sloupce uvolňují a přeobsazují, takže číslo
        #: sloupce už neznamená navždy totéž. Verzi nese každý, kdo si
        #: sloupcová čísla pamatuje (cache matic vět, pytle faktů,
        #: soubor na disku) — čtení s cizí verzí je chyba, ne hádání.
        self.axis_version = 0
        #: Uvolněné sloupce (díry po odebraných custom vertikálách),
        #: vzestupně; přeobsadí je příští zápis osy. V _keys je díra
        #: None — osa se nezkracuje, indexy za ní se nehýbou.
        self._free: list[int] = []
        for key in keys:
            self.add(key)
        # Hierarchie kotev je součást jazyka systému, ne volitelný doplněk —
        # registr se s ní rodí, aby ji nikdo nemusel pamatovat. anchors=False
        # dá holý registr (testy mechanismu, load — ten indexy rekonstruuje
        # ze souboru a nesmí mu do nich nic mluvit).
        if anchors:
            from cb_field.service import seed_anchor_links
            seed_anchor_links(self)

    # --- osa x ----------------------------------------------------------

    def add(self, key: str) -> int:
        """Vrátí index vertikály; neznámou připíše na konec.

        Idempotentní: existující klíč vrací svůj původní index a nic
        nemění — přesně tím je registr append-only.
        """
        i = self._index.get(key)
        if i is None:
            i = len(self._keys)
            self._keys.append(key)
            self._index[key] = i
            self._matrix_cache = None
        return i

    def index(self, key: str) -> int:
        """Index existující vertikály; neznámá je KeyError, nepřidává se."""
        try:
            return self._index[key]
        except KeyError:
            raise KeyError(f"vertikála {key!r} v registru není") from None

    def key(self, i: int) -> str:
        """Klíč podle pozičního argumentu: sloupec i → atribut=hodnota.

        Tudy se z uložené matice rekonstruuje, co který sloupec znamená.
        Čtení uvolněného sloupce je hlasitá chyba: kdo se ptá na díru,
        drží sloupcové číslo z jiné verze osy.
        """
        if not 0 <= i < len(self._keys):
            raise IndexError(
                f"sloupec {i} v registru není (má {len(self._keys)} vertikál)")
        if self._keys[i] is None:
            raise ValueError(
                f"sloupec {i} je uvolněná custom vertikála (osa verze "
                f"{self.axis_version}) — číslo pochází z jiné verze osy")
        return self._keys[i]

    def keys(self) -> tuple:
        """Všechny vertikály v pořadí indexů; díra po uvolněné custom
        vertikále je „UVOLNĚNO=<sloupec>" — zástupka bez systémového
        prefixu, aby hromadné masky (startswith) mlčky nepasovaly."""
        return tuple(k if k is not None else f"UVOLNĚNO={i}"
                     for i, k in enumerate(self._keys))

    def __len__(self) -> int:
        return len(self._keys)

    def __contains__(self, key: str) -> bool:
        return key in self._index

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    # --- custom osy (krok 3 handoveru) ----------------------------------

    def set_custom_axes(self, target: Iterable[str]) -> dict:
        """Zapíše CÍLOVÝ stav osy custom vertikál — stav proti stavu.

        Jediné místo, kde se sloupce uvolňují a přeobsazují: kdo z
        cílového stavu vypadl, uvolní sloupec (díra None) a odejde
        I SE SVÝMI HRANAMI — vazby jsou klíčované jmény, přeobsazení
        by je nerozbilo, jen by ukazovaly do neexistující osy. Nově
        promovaní obsazují díry vzestupně, pak konec osy. Změna
        obsazení zvedá axis_version — staré matice a pytle se tím
        odmítnou, ne tiše přečtou.

        Při chybě:
            ValueError na klíč bez prefixu CUSTOM= — osy z UDPipe
            do soutěže o místo nevstupují a zápis na ně nesmí sáhnout.
        """
        target = tuple(target)
        for key in target:
            if not key.startswith(CUSTOM_PREFIX):
                raise ValueError(
                    f"vertikála {key!r} není custom ({CUSTOM_PREFIX}…) — "
                    f"cílový stav osy smí mluvit jen do custom vertikál")
        wanted = set(target)
        to_remove = [k for k in self._keys
                     if k is not None and k.startswith(CUSTOM_PREFIX)
                     and k not in wanted]
        to_add = [k for k in target if k not in self._index]
        removed = set(to_remove)
        dead_links = [pair for pair in self._links
                      if pair[0] in removed or pair[1] in removed]
        for pair in dead_links:
            del self._links[pair]
        if dead_links:
            self.link_version += 1
        for key in to_remove:
            i = self._index.pop(key)
            self._keys[i] = None
            self._free.append(i)
        self._free.sort()
        for key in to_add:
            if self._free:
                i = self._free.pop(0)
                self._keys[i] = key
            else:
                i = len(self._keys)
                self._keys.append(key)
            self._index[key] = i
        if to_remove or to_add:
            self.axis_version += 1
            self._matrix_cache = None
        return {"pridano": len(to_add), "odebrano": len(to_remove),
                "hran_odebrano": len(dead_links)}

    def snapshot(self) -> dict:
        """Úplný stav osy i vazeb — krok 1 promočního cyklu."""
        return {"keys": list(self._keys), "index": dict(self._index),
                "free": list(self._free), "links": dict(self._links),
                "axis_version": self.axis_version,
                "link_version": self.link_version}

    def restore(self, snapshot: dict) -> None:
        """Vrátí registr bit po bitu do stavu snapshotu — odvolání
        promočního cyklu, který zhoršil měření. Vrací se i verze:
        osa je po návratu TATÁŽ, takže cache z doby před cyklem
        znovu platí a cache z cyklu selžou na verzi."""
        self._keys = list(snapshot["keys"])
        self._index = dict(snapshot["index"])
        self._free = list(snapshot["free"])
        self._links = dict(snapshot["links"])
        self.axis_version = snapshot["axis_version"]
        self.link_version = snapshot["link_version"]
        self._matrix_cache = None

    # --- vazby mezi vertikálami -----------------------------------------

    def link(self, src: str, dst: str, weight: float = 1.0,
             source: str = "axiom") -> None:
        """Vážená vazba vertikála→vertikála; neznámé klíče připíše.

        Váha nese sílu i znaménko vztahu (maska by byla jen její binární
        degenerát). Každá hrana nese zdroj (axiom | hebb | etalon |
        dialog) — axiomy jsou definice jazyka systému a učení je nesmí
        přepsat (P-C spec): pokus o přepis axiomu jiným zdrojem se tiše
        ignoruje (učení jich zkouší tisíce; hlasitost patří do statistik
        učení, ne sem).

        Při chybě:
            ValueError na váhu mimo −1…+1 (tytéž meze jako u aktivací).
        """
        if not -1.0 <= weight <= 1.0:
            raise ValueError(f"váha vazby {weight} je mimo rozsah -1.0 … 1.0")
        existing = self._links.get((src, dst))
        if existing and existing[1] == "axiom" and source != "axiom":
            return
        self.add(src)
        self.add(dst)
        self._links[(src, dst)] = (weight, source)
        self._matrix_cache = None
        self.link_version += 1

    def links(self) -> tuple:
        """Všechny vazby jako čtveřice (od, do, váha, zdroj)."""
        return tuple((s, d, w, src) for (s, d), (w, src)
                     in self._links.items())

    def unlink(self, src: str, dst: str) -> None:
        """Odebere vazbu — slouží odvolání epochy učení (rollback na
        stav před ní), ne mazání znalostí. Axiom se neodvolává (P-C);
        neexistující vazba je tiché nic (rollback jich zkouší tisíce).
        """
        existing = self._links.get((src, dst))
        if existing is None or existing[1] == "axiom":
            return
        del self._links[(src, dst)]
        self._matrix_cache = None
        self.link_version += 1

    def get_link(self, src: str, dst: str):
        """(váha, zdroj) vazby, nebo None, když neexistuje."""
        return self._links.get((src, dst))

    def link_matrix(self) -> np.ndarray:
        """Vazby jako matice L: L[i, j] = váha vazby key(i) → key(j).

        Cache: na velkém registru je L drahá (n²) a párování ji chce
        pro každou otázku — přestaví se jen po růstu nebo změně vazeb.
        Vrácená matice se nesmí mutovat (čtou ji všichni).
        """
        if self._matrix_cache is None:
            n = len(self._keys)
            matrix = np.zeros((n, n), dtype=DTYPE)
            for (src, dst), (weight, _source) in self._links.items():
                matrix[self._index[src], self._index[dst]] = weight
            self._matrix_cache = matrix
        return self._matrix_cache

    def spread(self, vector) -> np.ndarray:
        """Jeden krok šíření aktivace po vazbách: v + v·L.

        Kratší vektor (vznikl nad menším registrem) se doplní nulami —
        nula je „žádná aktivace", takže doplnění nic netvrdí. Tudy se
        potkává otázka s odpovědí: QANCHOR=time:when i ANCHOR=time:fut
        stečou do ANCHOR=time.
        """
        vec = np.asarray(vector, dtype=DTYPE)
        if vec.ndim != 1:
            raise ValueError(f"čekám vektor, dostal jsem tvar {vec.shape}")
        if len(vec) > len(self._keys):
            raise ValueError(
                f"vektor má {len(vec)} sloupců, registr jen "
                f"{len(self._keys)} — vznikl nad jiným registrem?")
        padded = np.zeros(len(self._keys), dtype=DTYPE)
        padded[:len(vec)] = vec
        return padded + padded @ self.link_matrix()

    # --- serializace aktivací -------------------------------------------

    def vectorize(self, weights: Mapping[str, float],
                  grow: bool = True) -> np.ndarray:
        """Aktivace → vektor: sloupec = index vertikály, hodnota = váha.

        Vstup:
            weights: {"atribut=hodnota": váha} — výstup activations().
            grow: True nové vertikály připíše (stavba pole); False je
                odmítne ValueError (čtení proti zmrazenému registru).

        Výstup:
            Vektor float32 o délce registru po případném růstu; buňky
            bez aktivace mají 0.0 (= žádný vliv).
        """
        if grow:
            for key in weights:
                self.add(key)
        vec = np.zeros(len(self._keys), dtype=DTYPE)
        for key, weight in weights.items():
            i = self._index.get(key)
            if i is None:
                raise ValueError(
                    f"vertikála {key!r} v registru není a grow=False")
            vec[i] = weight
        return vec

    def unvectorize(self, vector) -> dict:
        """Vektor → {vertikála: váha}; jen nenulové buňky.

        Zkouška funkčnosti registru: co vectorize zapsal, tohle vrátí
        jako JSON-ovatelný objekt. Váhy se zaokrouhlují na 6 míst —
        float32 drží 0.7 jako 0.69999999 a to do JSONu nepatří; u vah
        v rozsahu −1…+1 je 6 míst pod rozlišením float32, nic se neztrácí.

        Při chybě:
            ValueError na ne-vektor a na vektor delší než registr —
            takový vznikl nad jiným (novějším) registrem a sloupce
            navíc by se tiše zahodily.
        """
        vec = np.asarray(vector)
        if vec.ndim != 1:
            raise ValueError(f"čekám vektor, dostal jsem tvar {vec.shape}")
        if len(vec) > len(self._keys):
            raise ValueError(
                f"vektor má {len(vec)} sloupců, registr jen "
                f"{len(self._keys)} — vznikl nad jiným registrem?")
        out = {}
        for i, w in enumerate(vec):
            if w == 0.0:
                continue               # nula v díře nic netvrdí
            if self._keys[i] is None:
                raise ValueError(
                    f"vektor aktivuje uvolněný sloupec {i} — vznikl "
                    f"nad jinou verzí osy (teď {self.axis_version})")
            out[self._keys[i]] = round(float(w), 6)
        return out

    # --- trvalost -------------------------------------------------------

    def save(self, path: Path) -> Path:
        """Uloží registr jako JSON; zápis je atomický (§ 8)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps({"format_version": FORMAT_VERSION,
                        "axis_version": self.axis_version,
                        "keys": self._keys,      # díra = null
                        "links": [[s, d, w, src] for (s, d), (w, src)
                                  in self._links.items()]},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, path: Path,
             expected_axis_version: int | None = None) -> "VerticalRegistry":
        """Načte registr; cizí verze formátu je hlasitá chyba, ne hádání.

        expected_axis_version: verze osy, se kterou volající drží
        sloupcová čísla (uložené matice). Soubor s jinou verzí se
        odmítne hlasitě — tichá záměna významu sloupců je přesně to,
        co axis_version hlídá.
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        version = data.get("format_version")
        if version not in READABLE_VERSIONS:
            raise ValueError(
                f"neznámá verze formátu registru {version!r}; "
                f"tahle čtečka umí {READABLE_VERSIONS}")
        axis_version = data.get("axis_version", 0)
        if expected_axis_version is not None \
                and axis_version != expected_axis_version:
            raise ValueError(
                f"registr v {path} má osu verze {axis_version}, "
                f"čekána {expected_axis_version} — sloupcová čísla "
                f"volajícího pocházejí z jiné osy")
        registry = cls((), anchors=False)
        for key in data["keys"]:
            if key is None:            # díra po uvolněné custom vertikále
                registry._free.append(len(registry._keys))
                registry._keys.append(None)
            else:
                registry.add(key)
        for entry in data.get("links", []):
            src, dst, weight = entry[0], entry[1], entry[2]
            source = entry[3] if len(entry) > 3 else "axiom"
            registry.link(src, dst, weight, source=source)
        registry.axis_version = axis_version
        registry.link_version = 0      # čerstvá instance, žádné cache
        return registry
