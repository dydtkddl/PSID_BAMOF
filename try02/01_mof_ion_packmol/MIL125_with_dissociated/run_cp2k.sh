#!/usr/bin/env bash
# run_cp2k.sh
# 사용법: ./run_cp2k.sh <RESTART_FILE>
# 예시:  ./run_cp2k.sh MIL125_DISSOCIATED_GEOOPT-1.restart

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <restart_file>"
  exit 1
fi

RESTART_FILE="$1"
PASSWORD="9582"

while true; do
  echo "$PASSWORD" | sudo -S timeout 30m podman run --rm \
    -v "$HOME/cp2k/data":/opt/cp2k/data:Z \
    -v "$PWD":/work:Z \
    -w /work docker.io/cp2k/cp2k:latest \
    mpirun -n 7 -genv OMP_NUM_THREADS=4 \
    cp2k -i "${RESTART_FILE}" \
         -o simulation.input.out \
    > simulation.input.log 2>&1

  # 마지막 30줄 확인해서 종료 조건 검사
  if tail -n 30 simulation.input.out \
     | grep -q "The number of warnings for this run is"; then
    echo "▶ 경고 메시지 발견: 루프를 종료합니다."
    break
  fi

  sleep 3
done

