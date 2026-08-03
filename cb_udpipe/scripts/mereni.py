#!/usr/bin/env python3
"""Měření modulu cb-udpipe na zmraženém vzorku.

Měření je **podmínka přijetí modulu** (`K-6`), ne příloha. Bez naměřeného
čísla se nedá poznat, jestli modul dělá to, kvůli čemu vznikl.

    ./run-python cb_udpipe/scripts/mereni.py

Vzorek je zmražený v `tests/data/mereni.jsonl` a v gitu. Sada, která se
přepočítává při každém běhu, tiše zmenší sama sebe, když ji chyba připraví
o položky — a pak pochválí právě tu chybu, kterou má chytat
(README-MODULES.md § 11).

Každé číslo nese verzi dat, konfigurace a tokenizéru; bez nich jsou dvě čísla
nesrovnatelná.

**Zrychlení se měří jen od studené cache.** Druhý běh nad plnou cache vrátí
zrychlení 1,0 — první průchod totiž taky bere z cache. Není to vlastnost
modulu, je to artefakt měření, a kdo ho neodliší, zapíše si číslo, které nic
neznamená. Před měřením zrychlení proto:

    ./cb-udpipe.py stop
    rm cb_udpipe/data-persistent/cache/*.jsonl
    ./cb-udpipe.py start

Ostatní čísla (podíl oprav, poměr fází, shoda cache) na stavu cache nezávisí.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(KOREN))

from cb_udpipe import client, config, upstream  # noqa: E402

VZOREK = Path(__file__).parent.parent / "tests" / "data" / "mereni.jsonl"


def zmer() -> dict:
    """Provede celé měření proti **běžící službě** a vrátí čísla.

    Proč přes klienta a ne přímo přes `UdpipeService`: služba drží cache
    otevřenou pro zápis a dva zapisovatelé nad jedním souborem znamenají
    ztrátu dat (README-MODULES.md § 8). Vedlejší zisk je, že se tím měří
    skutečná cesta, kterou půjde provoz — včetně serializace a sítě.

    Výstup:
        Slovník s naměřenými hodnotami a s verzemi, které k nim patří.

    Při chybě:
        `ServiceUnavailable`, když služba neběží. Měření bez ní nedává smysl
        a tichá nula by lhala.
    """
    cfg = config.load()
    vety = [json.loads(r) for r in
            VZOREK.read_text(encoding="utf-8").splitlines() if r.strip()]

    klient = client.UdpipeClient(
        endpoint=f"http://{cfg['service']['host']}:{cfg['service']['port']}",
        timeout_s=cfg["module"]["upstream"]["request_timeout_s"],
    )
    return _projdi(klient, vety, cfg)


def _projdi(k: "client.UdpipeClient", vety: list[dict], cfg: dict) -> dict:
    """Projde vzorek dvakrát a spočítá čísla."""
    print(f"vzorek: {len(vety)} vět", file=sys.stderr)

    # --- první průchod: co se dá opravit a jak dlouho to trvá ------------
    t0 = time.monotonic()
    oprav_celkem = vet_s_opravou = vet_celkem = 0
    preskoceno = 0
    for i, v in enumerate(vety, 1):
        r = k.parse(text=v["text"], trace=f"b-mereni{i:04d}")
        vet_celkem += len(r.sentences)
        preskoceno += len(r.skipped)
        for veta in r.sentences:
            oprav_celkem += veta.retokenized
            vet_s_opravou += 1 if veta.retokenized else 0
        if i % 100 == 0:
            print(f"  {i}/{len(vety)}", file=sys.stderr)
    prvni_s = time.monotonic() - t0

    # --- druhý průchod: podíl zásahů a jak je rychlý --------------------
    t0 = time.monotonic()
    zasahu = rozboru = 0
    for i, v in enumerate(vety, 1):
        r = k.parse(text=v["text"], trace=f"b-cache{i:04d}")
        zasahu += r.cached
        rozboru += r.parsed
    druhy_s = time.monotonic() - t0

    # --- poměr fází: na tom stojí dvoufázový postup ----------------------
    tokenizace_s, dorozbor_s = _zmer_faze(cfg, vety[:50])

    # --- protiváha: shoduje se cache s čerstvým rozborem? ---------------
    neshod = _zmer_shodu(cfg, k, vety[:50])

    zdravi = k.health()
    cache = zdravi["cache"]
    return {
        "kdy": time.strftime("%Y-%m-%d %H:%M"),
        "vzorek": {"vet": len(vety), "zdroj": str(VZOREK.name)},
        "verze": {
            "model": cfg["module"]["upstream"]["model"],
            "tokenizer": zdravi["tokenizer"],
            "config": cfg["_meta"]["fingerprint"],
        },
        "tokenizace": {
            "vet_po_segmentaci": vet_celkem,
            "vet_s_opravou": vet_s_opravou,
            "podil_vet_s_opravou": _pomer(vet_s_opravou, vet_celkem),
            "oprav_celkem": oprav_celkem,
            "preskoceno": preskoceno,
        },
        "cache": {
            "podil_zasahu_druhy_pruchod": _pomer(zasahu, zasahu + rozboru),
            "vet_v_cache": cache["sentences"],
            "bajtu": cache["bytes"],
            "bajtu_na_vetu": (cache["bytes"] // cache["sentences"]
                              if cache["sentences"] else 0),
            "poskozenych": cache["corrupt"],
            "neshod_s_cerstvym_rozborem": neshod,
        },
        "doba": {
            "prvni_pruchod_s": round(prvni_s, 1),
            "druhy_pruchod_s": round(druhy_s, 1),
            "zrychleni": (round(prvni_s / druhy_s, 1) if druhy_s else None),
            "tokenizace_50_vet_s": round(tokenizace_s, 2),
            "dorozbor_50_vet_s": round(dorozbor_s, 2),
            "podil_tokenizace": _pomer(tokenizace_s,
                                       tokenizace_s + dorozbor_s),
        },
    }


def _zmer_faze(cfg: dict, vety: list[dict]) -> tuple[float, float]:
    """Změří zvlášť dobu tokenizace a dobu dorozboru.

    **Na tomhle stojí celý dvoufázový postup** (koncepce, § 2). Kdyby byl
    poměr blízko 1:1, je návrh špatně a je lepší klíčovat cache celým
    vstupním blokem.

    Vstup:
        cfg: konfigurace.
        vety: vzorek vět.

    Výstup:
        Dvojice (sekundy tokenizace, sekundy dorozboru).
    """
    from cb_udpipe import conllu, tokenize

    u = cfg["module"]["upstream"]
    klient = upstream.Upstream(
        endpoint=f"http://{u['host']}:{u['port']}",
        timeout_s=u["request_timeout_s"],
    )
    text = "\n\n".join(v["text"] for v in vety)
    pravidla = tokenize.Rules.from_config(cfg)

    t0 = time.monotonic()
    hrube = klient.tokenize(text, trace="b-faze")
    tokenizace_s = time.monotonic() - t0

    opravene = [tokenize.retokenize(v, pravidla)[0]
                for v in conllu.parse(hrube)]

    t0 = time.monotonic()
    klient.tag_and_parse(conllu.write(opravene), trace="b-faze")
    dorozbor_s = time.monotonic() - t0

    return tokenizace_s, dorozbor_s


def _zmer_shodu(cfg: dict, k: "client.UdpipeClient",
                vety: list[dict]) -> int:
    """Protiváha k podílu zásahů: vrací počet vět, kde se cache liší.

    Podíl zásahů jde nafouknout tím, že se cache klíčuje volněji — bez
    modelu, bez diakritiky. Proti tomu stojí tenhle test: u vzorku vět se
    porovná, co vrátila cache, s tím, co vrátí čerstvý rozbor. **Rozdíl je
    chyba klíče, ne remíza** (koncepce, § 11).

    Výstup:
        Počet vět, kde se tokeny liší. Nula je jediná správná hodnota.
    """
    from cb_udpipe import conllu, tokenize

    u = cfg["module"]["upstream"]
    klient = upstream.Upstream(
        endpoint=f"http://{u['host']}:{u['port']}",
        timeout_s=u["request_timeout_s"],
    )
    pravidla = tokenize.Rules.from_config(cfg)
    neshod = 0

    for v in vety:
        z_cache = k.parse(text=v["text"], trace="b-shoda")
        hrube = conllu.parse(klient.tokenize(v["text"], trace="b-shoda"))
        opravene = [tokenize.retokenize(x, pravidla)[0] for x in hrube]
        cerstve = conllu.parse(
            klient.tag_and_parse(conllu.write(opravene), trace="b-shoda")
        )
        if len(z_cache.sentences) != len(cerstve):
            neshod += 1
            continue
        for a, b in zip(z_cache.sentences, cerstve):
            if [t.form for t in a.tokens] != [t.form for t in b.tokens]:
                neshod += 1
                break
    return neshod


def _pomer(cast: float, celek: float) -> float | None:
    """Podíl v procentech na jedno desetinné místo; `None` při nulovém celku.

    `None` schválně, ne nula: „nemá hodnotu" a „je to nula" jsou různé stavy
    (INV-9).
    """
    return round(100 * cast / celek, 1) if celek else None


def main() -> int:
    try:
        vysledek = zmer()
    except (client.ServiceUnavailable, upstream.UpstreamUnavailable) as e:
        print(f"měření nelze provést:\n{e}", file=sys.stderr)
        return 1
    print(json.dumps(vysledek, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
