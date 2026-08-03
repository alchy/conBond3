#!/usr/bin/env bash
#
# fetch-models.sh — pořídí model UDPipe 2 a embedding model RobeCzech.
#
# Velká binární data do repozitáře nepatří: git s nimi neumí zacházet, `diff`
# na nich nic neřekne a historie by narostla o stovky megabajtů, které nikdo
# nikdy nebude potřebovat zpětně (README-MODULES.md § 19). Tenhle skript je ta
# druhá polovina pravidla — jasný postup, jak je získat.
#
# Použití:
#
#   ./fetch-models.sh --from-conbond2 ../conBond2    # kopie ze sousedního projektu
#   ./fetch-models.sh --check                        # jen ověří, co chybí
#
# Stahování z LINDATu skript NEDĚLÁ. Je to vědomé: URL bez ověření do skriptu
# nepatří a ruční postup je popsaný v cb_udpipe/README.md. Nástroj se navíc
# nikdy nestahuje za běhu — je to samostatný krok, který udělá člověk vědomě,
# ne vedlejší účinek prvního dotazu.
#
# Licence: model je CC BY-NC-SA (NEKOMERČNÍ), RobeCzech dle ÚFAL.
# Podrobnosti v ZDROJ.md.

set -euo pipefail

MODUL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_JMENO="cs_all-ud-2.17-251125.model"
CIL_MODEL="$MODUL/data-persistent/models/$MODEL_JMENO"
CIL_HF="$MODUL/data-persistent/models/hf"
ROBECZECH="hub/models--ufal--robeczech-base"

chyba() { printf '%s\n' "$@" >&2; exit 2; }

stav() {
  local chybi=0
  if [ -d "$CIL_MODEL" ]; then
    printf 'model      OK   %s\n' "$CIL_MODEL"
  else
    printf 'model      CHYBÍ %s\n' "$CIL_MODEL"; chybi=1
  fi
  if [ -d "$CIL_HF/$ROBECZECH" ]; then
    printf 'RobeCzech  OK   %s\n' "$CIL_HF/$ROBECZECH"
  else
    printf 'RobeCzech  CHYBÍ %s\n' "$CIL_HF/$ROBECZECH"; chybi=1
  fi
  if [ -f "$MODUL/vendor/udpipe2-src/udpipe2_server.py" ]; then
    printf 'zdrojáky   OK   %s\n' "$MODUL/vendor/udpipe2-src"
  else
    printf 'zdrojáky   CHYBÍ %s\n' "$MODUL/vendor/udpipe2-src"
    printf '           pořídíš: git submodule update --init\n'; chybi=1
  fi
  return $chybi
}

kopiruj() {
  local zdroj="$1"
  [ -d "$zdroj" ] || chyba "adresář neexistuje: $zdroj"

  local zdroj_model="$zdroj/models/udpipe2/$MODEL_JMENO"
  local zdroj_hf="$zdroj/models/hf"

  [ -d "$zdroj_model" ] || chyba \
    "v $zdroj chybí model: $zdroj_model" \
    "" \
    "Zkontroluj, že ukazuješ na kořen conBondu2."
  [ -d "$zdroj_hf/$ROBECZECH" ] || chyba \
    "v $zdroj chybí RobeCzech: $zdroj_hf/$ROBECZECH"

  mkdir -p "$(dirname "$CIL_MODEL")" "$CIL_HF"

  printf 'kopíruji model (357 MB)…\n'
  cp -R "$zdroj_model" "$CIL_MODEL"
  printf 'kopíruji RobeCzech (484 MB)…\n'
  cp -R "$zdroj_hf/hub" "$CIL_HF/"

  printf '\nkontrola:\n'
  stav || chyba "kopie nedopadla — něco pořád chybí"
  printf '\nhotovo. Licence: model CC BY-NC-SA (nekomerční), viz ZDROJ.md\n'
}

case "${1:---check}" in
  --check)
    stav
    ;;
  --from-conbond2)
    [ $# -ge 2 ] || chyba "chybí cesta: ./fetch-models.sh --from-conbond2 ../conBond2"
    kopiruj "$2"
    ;;
  *)
    chyba "neznámý přepínač: $1" \
      "" \
      "Použití:" \
      "  ./fetch-models.sh --from-conbond2 ../conBond2" \
      "  ./fetch-models.sh --check"
    ;;
esac
