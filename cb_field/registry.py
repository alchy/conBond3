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
FORMAT_VERSION = 1

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
        """
        if not 0 <= i < len(self._keys):
            raise IndexError(
                f"sloupec {i} v registru není (má {len(self._keys)} vertikál)")
        return self._keys[i]

    def keys(self) -> tuple:
        """Všechny vertikály v pořadí indexů."""
        return tuple(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def __contains__(self, key: str) -> bool:
        return key in self._index

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

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

    def links(self) -> tuple:
        """Všechny vazby jako čtveřice (od, do, váha, zdroj)."""
        return tuple((s, d, w, src) for (s, d), (w, src)
                     in self._links.items())

    def get_link(self, src: str, dst: str):
        """(váha, zdroj) vazby, nebo None, když neexistuje."""
        return self._links.get((src, dst))

    def link_matrix(self) -> np.ndarray:
        """Vazby jako matice L: L[i, j] = váha vazby key(i) → key(j)."""
        n = len(self._keys)
        matrix = np.zeros((n, n), dtype=DTYPE)
        for (src, dst), (weight, _source) in self._links.items():
            matrix[self._index[src], self._index[dst]] = weight
        return matrix

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
        return {self._keys[i]: round(float(w), 6)
                for i, w in enumerate(vec) if w != 0.0}

    # --- trvalost -------------------------------------------------------

    def save(self, path: Path) -> Path:
        """Uloží registr jako JSON; zápis je atomický (§ 8)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps({"format_version": FORMAT_VERSION,
                        "keys": self._keys,
                        "links": [[s, d, w, src] for (s, d), (w, src)
                                  in self._links.items()]},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, path: Path) -> "VerticalRegistry":
        """Načte registr; cizí verze formátu je hlasitá chyba, ne hádání."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        version = data.get("format_version")
        if version != FORMAT_VERSION:
            raise ValueError(
                f"neznámá verze formátu registru {version!r}; "
                f"tahle čtečka umí {FORMAT_VERSION}")
        registry = cls(data["keys"], anchors=False)
        for entry in data.get("links", []):
            src, dst, weight = entry[0], entry[1], entry[2]
            source = entry[3] if len(entry) > 3 else "axiom"
            registry.link(src, dst, weight, source=source)
        return registry
