#!/usr/bin/env bash
set -euo pipefail

CLUSTER_DIR="/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster"
OT_PFX="$CLUSTER_DIR/test_output_ot.out"
SRC_INP="$CLUSTER_DIR/input.inp"

if [[ ! -f "$OT_PFX" ]]; then
  echo "ERROR: test_output_ot.out not found"
  exit 1
fi

find_latest_wfn() {
  local d="$1"
  ls -1t "$d"/*.wfn 2>/dev/null | head -n 1 || true
}

OT_WFN=$(find_latest_wfn "$CLUSTER_DIR")
if [[ -z "$OT_WFN" ]]; then
  OT_WFN=$(grep -Eo "[A-Za-z0-9_./-]+RESTART\\.wfn" "$OT_PFX" | tail -n 1 || true)
  if [[ -n "$OT_WFN" ]]; then
    OT_WFN="$CLUSTER_DIR/$OT_WFN"
  fi
fi

if [[ -z "$OT_WFN" ]]; then
  echo "WARN: no wfn found from OT run"
  OT_WFN="<path_to_ot_restart.wfn>"
fi

make_hybrid_input() {
  local src="$1"
  local dst="$2"
  local coord="$3"
  local project="$4"
  local guess="$5"
  local alpha="$6"
  local temp="$7"
  local added_mos="$8"
  local wfn="$9"

  python3 - "$src" "$dst" "$coord" "$project" "$guess" "$alpha" "$temp" "$added_mos" "$wfn" <<'PY'
import re
import sys
from pathlib import Path

src, dst, coord, project, guess, alpha, temp, added_mos, wfn = sys.argv[1:]
text = Path(src).read_text()

text = re.sub(r"^\s*PROJECT_NAME\s+\S+", f"    PROJECT_NAME {project}", text, flags=re.M)
text = re.sub(r"^\s*COORD_FILE_NAME\s+\S+", f"    COORD_FILE_NAME {coord}", text, flags=re.M)
text = re.sub(r"^\s*MAX_ITER\s+\d+", "      MAX_ITER 600", text, flags=re.M)
text = re.sub(r"\n\s*&SCF\b[\s\S]*?\n\s*&END SCF\n", "\n", text, count=1)

wfn_line = ""
if guess == "RESTART":
    wfn_line = f"      WFN_RESTART_FILE_NAME {Path(wfn).name}\n" if wfn != "<path_to_ot_restart.wfn>" else ""
scf = (
    "    &SCF\n"
    "      MAX_SCF 300\n"
    "      EPS_SCF 5.0E-7\n"
    f"      SCF_GUESS {guess}\n"
    f"      ADDED_MOS {added_mos}\n"
    wfn_line
    "      &DIAGONALIZATION\n"
    "        ALGORITHM STANDARD\n"
    "      &END DIAGONALIZATION\n"
    "      &MIXING\n"
    "        METHOD BROYDEN_MIXING\n"
    f"        ALPHA {alpha}\n"
    "        NBUFFER 8\n"
    "      &END MIXING\n"
    "      &OUTER_SCF\n"
    "        MAX_SCF 10\n"
    "        EPS_SCF 5.0E-7\n"
    "      &END OUTER_SCF\n"
    "      &SMEAR\n"
    "        METHOD FERMI_DIRAC\n"
    f"        ELECTRONIC_TEMPERATURE {temp}\n"
    "      &END SMEAR\n"
    "    &END SCF\n"
)

idx = text.find("&MOTION")
if idx >= 0:
    text = text[:idx] + scf + "\n" + text[idx:]
else:
    text += "\n" + scf

Path(dst).write_text(text)
PY
}

make_hybrid_input \
  "$SRC_INP" \
  "$CLUSTER_DIR/hybrid_broyden.inp" \
  "BAMOF_2IP_cluster_init.xyz" \
  "BAMOF_2IP_hybrid_broyden" \
  RESTART 0.13 500 170 "$OT_WFN"

make_hybrid_input \
  "$CLUSTER_DIR/hybrid_broyden.inp" \
  "$CLUSTER_DIR/production_from_hybrid.inp" \
  "BAMOF_2IP_cluster_init.xyz" \
  "BAMOF_2IP_hybrid_prod" \
  RESTART 0.15 300 170 "$OT_WFN"

cat <<'MSG'
[PLAN C] Hybrid OT bootstrap branch prepared.

 - hybrid_broyden.inp        (Broyden RESTART candidate, alpha=0.13, 500K)
 - production_from_hybrid.inp (final production candidate, alpha=0.15, 300K, RESTART)

Suggested execution (echo only):
echo "docker run --rm -v \"/mnt/d/PSID_BAMOF/try04/02_calculations:/work:Z\" -w /work/BAMOF_2IP_cluster keti/cp2k:2025.2-gpu mpirun -n 4 cp2k.psmp -i hybrid_broyden.inp -o simulation.input.out"
echo "docker run --rm -v \"/mnt/d/PSID_BAMOF/try04/02_calculations:/work:Z\" -w /work/BAMOF_2IP_cluster keti/cp2k:2025.2-gpu mpirun -n 4 cp2k.psmp -i production_from_hybrid.inp -o simulation.input.out"
MSG
