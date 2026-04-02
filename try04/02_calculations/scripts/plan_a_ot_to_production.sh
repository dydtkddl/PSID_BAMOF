#!/usr/bin/env bash
set -euo pipefail

CLUSTER_DIR="/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster"
DISSOC_DIR="/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate"
TEST_OUT="$CLUSTER_DIR/test_output_ot.out"

if [[ ! -f "$TEST_OUT" ]]; then
  echo "ERROR: $TEST_OUT not found"
  exit 1
fi
if ! grep -q "SCF run converged" "$TEST_OUT"; then
  echo "ERROR: OT run is not converged. Choose Plan B or Plan C."
  exit 2
fi

LATEST_WFN=$(ls -1t "$CLUSTER_DIR"/*.wfn 2>/dev/null | head -n 1 || true)
if [[ -z "$LATEST_WFN" ]]; then
  LATEST_WFN=$(grep -Eo "[A-Za-z0-9_./-]+RESTART\\.wfn" "$TEST_OUT" | tail -n 1 || true)
  if [[ -n "$LATEST_WFN" ]]; then
    echo "Detected restart WFN token: $LATEST_WFN"
  fi
fi
if [[ -z "$LATEST_WFN" ]]; then
  echo "WARN: Could not auto-detect WFN. Edit generated cluster input manually."
  LATEST_WFN="<path_to_ot_restart.wfn>"
fi

make_prod_input() {
  local src="$1"
  local dst="$2"
  local coord="$3"
  local project="$4"
  local scf_guess="$5"
  local added_mos="$6"
  local alpha="$7"
  local temp="$8"
  local wfn="$9"

  python3 - "$src" "$dst" "$coord" "$project" "$scf_guess" "$added_mos" "$alpha" "$temp" "$wfn" <<'PY'
import re
import sys
from pathlib import Path

src, dst, coord, project, guess, added_mos, alpha, temp, wfn = sys.argv[1:]
text = Path(src).read_text()

text = re.sub(r"^\s*PROJECT_NAME\s+\S+", f"    PROJECT_NAME {project}", text, flags=re.M)
text = re.sub(r"^\s*COORD_FILE_NAME\s+\S+", f"    COORD_FILE_NAME {coord}", text, flags=re.M)
text = re.sub(r"^\s*MAX_ITER\s+\d+", "      MAX_ITER 600", text, flags=re.M)
text = re.sub(r"\n\s*&SCF\b[\s\S]*?\n\s*&END SCF\n", "\n", text, count=1)

wfn_line = ""
if guess == "RESTART" and wfn != "<path_to_ot_restart.wfn>":
    wfn_line = f"      WFN_RESTART_FILE_NAME {Path(wfn).name}\n"

scf_block = (
    "    &SCF\n"
    "      MAX_SCF 200\n"
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
    "      &SMEAR\n"
    "        METHOD FERMI_DIRAC\n"
    f"        ELECTRONIC_TEMPERATURE {temp}\n"
    "      &END SMEAR\n"
    "    &END SCF\n"
)

idx = text.find("&MOTION")
if idx >= 0:
    text = text[:idx] + scf_block + "\n" + text[idx:]
else:
    text += "\n" + scf_block

Path(dst).write_text(text)
PY
}

make_prod_input \
  "$CLUSTER_DIR/input.inp" \
  "$CLUSTER_DIR/production_cluster.inp" \
  "BAMOF_2IP_cluster_init.xyz" \
  "BAMOF_2IP_cluster" \
  "RESTART" 170 0.15 300 "$LATEST_WFN"

make_prod_input \
  "$DISSOC_DIR/input.inp" \
  "$DISSOC_DIR/production_dissociate.inp" \
  "BAMOF_2IP_dissociate_init.xyz" \
  "BAMOF_2IP_dissociate" \
  "ATOMIC" 170 0.13 500 "$LATEST_WFN"

cat <<'MSG'
[PLAN A] OT success branch executed.
- Generated: production_cluster.inp, production_dissociate.inp

Suggested execution commands (print only; DO NOT execute here):

echo "docker run --rm -v \"/mnt/d/PSID_BAMOF/try04/02_calculations:/work:Z\" -w /work/BAMOF_2IP_cluster keti/cp2k:2025.2-gpu mpirun -n 4 cp2k.psmp -i production_cluster.inp -o simulation.input.out"
echo "docker run --rm -v \"/mnt/d/PSID_BAMOF/try04/02_calculations:/work:Z\" -w /work/BAMOF_2IP_dissociate keti/cp2k:2025.2-gpu mpirun -n 4 cp2k.psmp -i production_dissociate.inp -o simulation.input.out"

echo "Estimated GEO_OPT time (cluster): ~600 steps x 5.4 s/step ≈ 54 min + overhead"
echo "Monitor with: /mnt/d/PSID_BAMOF/try04/02_calculations/scripts/monitor_scf.sh <simulation.input.out>"
MSG
