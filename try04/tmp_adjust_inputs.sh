#!/usr/bin/env bash
set -euo pipefail

for d in "/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster" "/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate"; do
  f="$d/input.inp"
  [ -f "$f" ] || { echo "Missing: $f"; continue; }

  # MAX_SCF/ALPHA ??
  perl -i -pe 's/MAX_SCF\s+200/MAX_SCF 300/g; s/ALPHA\s+0\.15/ALPHA 0.05/' "$f"

  # NBUFFER ??: ?? ?? ????? ??
  perl -i -pe 'if(/ALPHA 0\.05/){ s/$/\n        NBUFFER 8/ }' "$f"

  # ?? OUTER_SCF? ??? ?? ???? ??
  if ! grep -q "&OUTER_SCF" "$f"; then
    perl -i -0pe 's/(\s*&PRINT\n\s*&RESTART ON)/    &OUTER_SCF T\n      MAX_SCF 10\n      EPS_SCF 5.0E-7\n    &END OUTER_SCF\n\n$1/' "$f"
  fi

done

echo "input files updated"
for d in "/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster" "/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate"; do
  echo "--- $d ---"
  grep -n "MAX_SCF\|ALPHA\|NBUFFER\|OUTER_SCF" "$d/input.inp"
done
