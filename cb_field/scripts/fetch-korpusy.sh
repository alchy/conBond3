#!/bin/bash
# Pořídí měřicí korpusy cb-field z předchozího projektu conBond2.
#
# Texty jsou licencované (Wikipedie CC BY-SA 4.0, biblický překlad) —
# do repozitáře NEPATŘÍ (ZDROJ.md); žijí jen v data-persistent/corpora/
# (gitignorováno). Měření si zapisuje jejich otisky.
#
# Použití:  ./cb_field/scripts/fetch-korpusy.sh
set -euo pipefail

ZDROJ="$HOME/Projects/conBond2/data/raw"
CIL="$(cd "$(dirname "$0")/.." && pwd)/data-persistent/corpora"

if [ ! -d "$ZDROJ" ]; then
    echo "chybí zdroj: $ZDROJ (projekt conBond2)" >&2
    exit 2
fi
mkdir -p "$CIL"

# doména zákon — Nový zákon (Markovo evangelium; nejkratší, na start stačí)
# doména fyzika — gravitace (ručně psané), elektromotor, fotosyntéza (wiki)
# doména spisovatelé — wiki životopisy
SOUBORY=(
    "bible_markus.txt"
    "fyzika_gravitace.txt" "elektromotor.txt" "fotosyntéza.txt"
    "karel_čapek.txt" "jan_neruda.txt" "bohumil_hrabal.txt"
)
for f in "${SOUBORY[@]}"; do
    if [ ! -f "$ZDROJ/$f" ]; then
        echo "chybí $ZDROJ/$f" >&2; exit 2
    fi
    cp "$ZDROJ/$f" "$CIL/$f"
done
echo "pořízeno do $CIL:"
(cd "$CIL" && wc -w "${SOUBORY[@]}")
