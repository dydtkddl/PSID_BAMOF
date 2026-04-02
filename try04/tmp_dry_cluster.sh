#!/usr/bin/env bash
set -euo pipefail

cd /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster
cp -f input.inp input_test.inp
sed -i 's/MAX_ITER 600/MAX_ITER 2/' input_test.inp

TIMEOUT_SEC=600
log=/tmp/try04_cluster_dry.log
(
  timeout ${TIMEOUT_SEC}s \
    docker run --rm --gpus=all \
      -v "$(pwd)":/work:Z \
      -w /work \
      keti/cp2k:2025.2-gpu \
      mpirun -n 4 -x OMP_NUM_THREADS=2 cp2k.psmp \
      -i input_test.inp -o test_output.out \
      > test.log 2>&1
  echo $?
) > "$log" 2>&1

rc=$(cat "$log" | tail -n 1)
echo "CP2K_EXIT=$rc"
if [[ -f test_output.out ]]; then
  echo "--- energy lines ---"
  grep "ENERGY| Total FORCE_EVAL" test_output.out | tail -n 3 || true
  echo "--- convergence flags ---"
  grep -n "SCF run" test_output.out | tail -n 20 || true
  grep -n "GEOMETRY OPTIMIZATION COMPLETED\|MAXIMUM NUMBER OF GEOMETRY OPTIMIZATION CYCLES REACHED\|FATAL\|ERROR" test_output.out | tail -n 20 || true
else
  echo "test_output.out missing"
fi
