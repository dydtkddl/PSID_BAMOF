#!/usr/bin/env bash
set -euo pipefail

CLUSTER_DIR="/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster"
TEST_OUT="$CLUSTER_DIR/test_output_ot.out"
TRY03_TRAJ="/mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/simulation.input-pos-1.xyz"
TRY03_TRAJ_ALT="/mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/BAMOF_EMIM_TFSI_Cluster-1-pos-1.xyz"

if [[ ! -f "$TEST_OUT" ]]; then
  echo "ERROR: $TEST_OUT missing"
  exit 1
fi
if ! grep -q "SCF run NOT converged" "$TEST_OUT"; then
  echo "WARN: test_output_ot.out does not show NOT converged."
fi

if [[ -f "$TRY03_TRAJ" ]]; then
  TRY03_SOURCE="$TRY03_TRAJ"
elif [[ -f "$TRY03_TRAJ_ALT" ]]; then
  TRY03_SOURCE="$TRY03_TRAJ_ALT"
else
  echo "ERROR: try03 trajectory not found."
  echo "checked: $TRY03_TRAJ"
  echo "checked: $TRY03_TRAJ_ALT"
  exit 2
fi

MOF_ONLY_XYZ="$CLUSTER_DIR/mof_only_init.xyz"
M1IP_XYZ="$CLUSTER_DIR/1ip_try03_base.xyz"
FULL_XYZ="$CLUSTER_DIR/BAMOF_2IP_cluster_init.xyz"
WFN_FROM_1IP="$CLUSTER_DIR/mof_1ip_energy-RESTART.wfn"

python3 - <<'PY'
from pathlib import Path

def copy_first_atoms(src, n, dst):
    lines = Path(src).read_text().splitlines()
    if not lines:
        raise RuntimeError(f"{src} is empty")
    nat = int(lines[0].strip())
    if n > nat:
        raise RuntimeError(f"requested {n} > nat={nat}")
    body = lines[2:2+n]
    out = [str(n), lines[1] if len(lines) > 1 else "subset"] + body
    Path(dst).write_text("\n".join(out) + "\n")


def copy_last_frame(src, dst):
    lines = Path(src).read_text().splitlines()
    if not lines:
        raise RuntimeError(f"{src} is empty")
    nat = int(lines[0].strip())
    frame = nat + 2
    if len(lines) % frame != 0:
        print(f"WARNING: {src} has non-uniform frame count; best-effort last full frame read.")
    start = ((len(lines) // frame) - 1) * frame
    if start < 0:
        raise RuntimeError(f"Could not parse frame in {src}")
    body = lines[start + 2:start + 2 + nat]
    out = [str(nat), lines[start+1]] + body
    Path(dst).write_text("\n".join(out) + "\n")


copy_first_atoms(
    "/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz",
    102,
    "/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster/mof_only_init.xyz",
)
copy_last_frame(
    "/mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/simulation.input-pos-1.xyz",
    "/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster/1ip_try03_base.xyz",
)
print("Generated:\n - mof_only_init.xyz (102 atoms)\n - 1ip_try03_base.xyz (158 atoms)")
PY

build_input() {
  local src="$1" dst="$2" coord="$3" project="$4"
  local run_type="$5" scf_guess="$6" max_scf="$7" alpha="$8" temp="$9" added_mos="$10" wfn="${11:-}"

  python3 - "$src" "$dst" "$coord" "$project" "$run_type" "$scf_guess" "$max_scf" "$alpha" "$temp" "$added_mos" "$wfn" <<'PY2'
import re
import sys
from pathlib import Path

src, dst, coord, project, run_type, guess, max_scf, alpha, temp, added_mos, wfn = sys.argv[1:]
text = Path(src).read_text()

text = re.sub(r"^\s*PROJECT_NAME\s+\S+", f"    PROJECT_NAME {project}", text, flags=re.M)
text = re.sub(r"^\s*COORD_FILE_NAME\s+\S+", f"    COORD_FILE_NAME {coord}", text, flags=re.M)
text = re.sub(r"^\s*RUN_TYPE\s+\w+", f"  RUN_TYPE {run_type}", text, flags=re.M)
if run_type == "ENERGY":
    text = re.sub(r"^\s*MAX_ITER\s+\d+\n?", "", text, flags=re.M)
else:
    text = re.sub(r"^\s*MAX_ITER\s+\d+", "      MAX_ITER 600", text, flags=re.M)
text = re.sub(r"\n\s*&SCF\b[\s\S]*?\n\s*&END SCF\n", "\n", text, count=1)

wfn_line = ""
if guess == "RESTART":
    wfn_line = f"      WFN_RESTART_FILE_NAME {Path(wfn).name}\n" if wfn else "      ! Fill in WFN_RESTART_FILE_NAME from preceding step\n"

scf = (
    "    &SCF\n"
    f"      MAX_SCF {max_scf}\n"
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
    text = text[:idx] + scf + "\n" + text[idx:]
else:
    text += "\n" + scf

Path(dst).write_text(text)
PY2
}

BASE_INP="$CLUSTER_DIR/input.inp"

# B-1 MOF only ENERGY
build_input "$BASE_INP" "$CLUSTER_DIR/mof_only_energy.inp" "mof_only_init.xyz" \
  "BAMOF_2IP_mof_only" ENERGY ATOMIC 300 0.15 300 50

# B-2 MOF + 1IP ENERGY (try03 converged frame)
build_input "$BASE_INP" "$CLUSTER_DIR/mof_1ip_energy.inp" "1ip_try03_base.xyz" \
  "BAMOF_2IP_mof_1ip" ENERGY ATOMIC 300 0.13 500 100

# B-3 MOF + 2IP ENERGY (restart from B-2)
build_input "$BASE_INP" "$CLUSTER_DIR/mof_2ip_scf.inp" "BAMOF_2IP_cluster_init.xyz" \
  "BAMOF_2IP_mof_2ip_scf" ENERGY RESTART 300 0.13 500 170 "$WFN_FROM_1IP"

# B-4 production GEO_OPT from bootstrap
build_input "$BASE_INP" "$CLUSTER_DIR/production_from_bootstrap.inp" "BAMOF_2IP_cluster_init.xyz" \
  "BAMOF_2IP_bootstrap_prod" GEO_OPT RESTART 200 0.15 300 170 "$WFN_FROM_1IP"

cat <<'MSG'
[PLAN B] Bootstrapped workflow generated.

Files:
 - mof_only_energy.inp           (RUN_TYPE ENERGY, MOF only)
 - mof_1ip_energy.inp            (RUN_TYPE ENERGY, MOF+try03 1IP)
 - mof_2ip_scf.inp               (RUN_TYPE ENERGY, 192 atoms, RESTART from 1IP wfn)
 - production_from_bootstrap.inp   (RUN_TYPE GEO_OPT)

Suggested run commands (echo only):
echo "docker run --rm -v \"/mnt/d/PSID_BAMOF/try04/02_calculations:/work:Z\" -w /work/BAMOF_2IP_cluster keti/cp2k:2025.2-gpu mpirun -n 4 cp2k.psmp -i mof_only_energy.inp -o simulation.input.out"
echo "docker run --rm -v \"/mnt/d/PSID_BAMOF/try04/02_calculations:/work:Z\" -w /work/BAMOF_2IP_cluster keti/cp2k:2025.2-gpu mpirun -n 4 cp2k.psmp -i mof_1ip_energy.inp -o simulation.input.out"
echo "docker run --rm -v \"/mnt/d/PSID_BAMOF/try04/02_calculations:/work:Z\" -w /work/BAMOF_2IP_cluster keti/cp2k:2025.2-gpu mpirun -n 4 cp2k.psmp -i mof_2ip_scf.inp -o simulation.input.out"
echo "docker run --rm -v \"/mnt/d/PSID_BAMOF/try04/02_calculations:/work:Z\" -w /work/BAMOF_2IP_cluster keti/cp2k:2025.2-gpu mpirun -n 4 cp2k.psmp -i production_from_bootstrap.inp -o simulation.input.out"

Example completion checks:
grep -q \"SCF run converged\" simulation.input.out
grep -n \" ENERGY| Total\" simulation.input.out | tail -n 5
echo \"Done\"
MSG
