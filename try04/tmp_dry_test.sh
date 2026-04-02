#!/bin/bash
set -u
set -o pipefail

run_case() {
  local case_dir="$1"
  cd "$case_dir" || return 1
  cp -f input.inp input_test.inp
  sed -i 's/MAX_ITER 600/MAX_ITER 2/' input_test.inp
  rm -f test_output.out test.log
  local log=run_dry.out

  timeout 240 docker run --rm --gpus=all \
    -v "${case_dir}":/work:Z \
    -w /work \
    keti/cp2k:2025.2-gpu \
    mpirun -n 4 -x OMP_NUM_THREADS=2 cp2k.psmp \
    -i input_test.inp -o test_output.out \
    > test.log 2>&1
  rc=$?

  echo "[${case_dir}] docker_exit=$rc"
  if [[ -f test_output.out ]]; then
    grep -n "SCF run" test_output.out | tail -n 10
    echo "--- ENERGY ---"
    grep -n "ENERGY| Total FORCE_EVAL" test_output.out | tail -n 5 || true
    echo "--- FLAGS ---"
    grep -n "ERROR\|FATAL\|NOT converged\|converged\|GEOMETRY OPTIMIZATION COMPLETED\|MAXIMUM NUMBER OF GEOMETRY OPTIMIZATION CYCLES REACHED" test_output.out | tail -n 30 || true
  else
    echo "NO test_output.out"
  fi
}

run_case /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster
run_case /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate
