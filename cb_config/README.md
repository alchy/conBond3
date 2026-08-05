# cb_config — sdílené načítání a ověřování konfigurace

Modul dělá jednu věc: přečte konfiguraci modulu, ověří ji proti schématu,
rozvine relativní cesty a spočítá otisk obsahu. Používá ho **každý** modul
dřív, než cokoli jiného udělá.

Vývojářský průvodce není potřeba — modul má jedinou vstupní funkci.
Návrhová rozhodnutí: `docs/koncepce.md`.

## Stav: knihovna, ne služba (verze 0.1.0)

Nemá port, REST API ani ovládací program, a **nemá je mít**: konfiguraci
potřebuje každý modul *před* startem, takže kdyby ji poskytovala služba,
nešlo by ji použít k jejímu vlastnímu startu.

Je to zároveň druhý **sdílený** modul vedle `cb-logger` (§ 4 politiky) —
rozšíření seznamu je vědomá změna, ne rozhodnutí jednoho modulu.

## Rozhraní (veřejné API)

| jméno | co to je |
|---|---|
| `load(config_path, schema_path, *, supported_version, checks, path_specs, post_resolve)` | celý průchod: přečti → ověř → rozviň cesty → otisk |
| `validate(config, schema)` | seznam českých hlášek; prázdný = v pořádku |
| `resolve_paths(config, path_specs)` | rozvine relativní cesty proti zadaným základnám |
| `fingerprint(config)` | krátký otisk nezávislý na pořadí klíčů |
| `read_json(path, co=…)` | JSON objekt; každá vada je `ConfigError` s adresou |
| `check_schema_supported(schema)` | schéma nesmí použít klíč, kterému validátor nerozumí |
| `ConfigError` | neplatná konfigurace; ovládací program z ní dělá návratový kód 2 |

## Co modul vědomě neřeší

- **Celé JSON Schema.** Umí jen tu část, kterou naše schémata používají;
  na cokoli jiného hlasitě upozorní. Nedostatečný validátor, který mlčí,
  je horší než žádný.
- **Zápis konfigurace.** Konfiguraci píše člověk, ne program.
- **Slučování vrstev nastavení.** Jedna konfigurace, jeden soubor.

## Testy

```
./run-python -m unittest discover -s cb_config -t .     # 18 testů
```
