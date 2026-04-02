#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/d/PSID_BAMOF/try04
cd "$ROOT"
{
  echo "# try04 Progress"
  echo ""
  echo "## Run started"
  echo "- date: $(date -Iseconds)"
  echo ""
  echo "## Phase A: Environment"
  echo "- uname: $(uname -a)"
  echo "- python3: $(python3 --version 2>&1)"
  if command -v pip3 >/dev/null 2>&1; then
    echo "- pip3: $(pip3 --version | awk '{print $1, $2}')"
  else
    echo "- pip3: NOT_FOUND"
  fi
  if command -v docker >/dev/null 2>&1; then
    echo "- docker: $(docker --version)"
  else
    echo "- docker: NOT_FOUND"
  fi
  echo "- docker images cp2k:"
  if docker images 2>/dev/null | grep -i cp2k; then :; else echo "  (none)"; fi
  echo "- cpu model: $(grep -m1 'model name' /proc/cpuinfo | sed 's/.*: //')"
  echo "- memory: $(free -h | awk 'NR==2{print $2, $3, $7}')"
  echo "- disk /mnt/d: $(df -h /mnt/d/ | tail -1 | awk '{print $2, $3, $4, $5}')"
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "- nvidia-smi:"
    nvidia-smi
  else
    echo "- nvidia-smi: NOT_FOUND"
  fi
  if command -v conda >/dev/null 2>&1; then
    echo "- conda: $(conda --version)"
  else
    echo "- conda: NOT_FOUND"
  fi
  npstat=$(python3 -c "import importlib.util; print('FOUND' if importlib.util.find_spec('numpy') else 'MISSING')")
  echo "- numpy: $npstat"
} > PROGRESS.md

{
  echo ""
  echo "## Phase A-2: try03 references"
  dirs=(
    /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/
    /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_dissociate-1/
    /mnt/d/PSID_BAMOF/try03/00_ionic_structure_cp2k/Cluster01/
  )
  for d in "${dirs[@]}"; do
    echo "- directory: $d"
    if [ -d "$d" ]; then
      ls -la "$d" | sed -n '1,3p'
    else
      echo "  - MISSING"
    fi
  done
  c1=$(grep "ENERGY| Total FORCE_EVAL" /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/simulation.input.out 2>/dev/null | tail -1)
  c2=$(grep "ENERGY| Total FORCE_EVAL" /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_dissociate-1/simulation.input.out 2>/dev/null | tail -1)
  echo "- try03 cluster final line: ${c1:-NOT_FOUND}"
  echo "- try03 dissociate final line: ${c2:-NOT_FOUND}"
} >> PROGRESS.md

{
  echo ""
  echo "## Phase A-3: numpy install check"
  npspec=$(python3 -c "import importlib.util; print('FOUND' if importlib.util.find_spec('numpy') else 'MISSING')")
  if [ "$npspec" = "FOUND" ]; then
    echo "- numpy status: already installed"
  else
    echo "- numpy status: missing, trying pip install"
    if pip3 install numpy >/tmp/try04_numpy_install.log 2>&1; then
      echo "- numpy install: success"
    else
      echo "- numpy install: failed (see /tmp/try04_numpy_install.log)"
    fi
  fi
} >> PROGRESS.md
