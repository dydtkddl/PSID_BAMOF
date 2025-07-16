#!/usr/bin/env bash
#
# run_cp2k.sh
# Usage: ./run_cp2k.sh <RESTART_FILE> [KILL_INTERVAL_SECONDS]
# Example: ./run_cp2k.sh MIL125_DISSOCIATED_GEOOPT-1.restart 1800

set -uo pipefail
set +e   # watchdog failures shouldn’t kill the script

if [ $# -lt 1 ]; then
  echo "Usage: $0 <restart_file> [kill_interval_seconds]"
  exit 1
fi

RESTART_FILE="$1"
KILL_INTERVAL="${2:-1800}"   # default 1800 seconds (30 min)
PASSWORD="psid1234!@"
ITER=0

# Ensure any naked Ctrl+C also kills leftover watchdogs
cleanup() {
  [[ -n "${WD_PID:-}" ]] && kill "${WD_PID}" &>/dev/null || true
}
trap cleanup EXIT

while true; do
  ITER=$((ITER+1))
  CONTAINER_NAME="cp2k_run_${ITER}"

  echo "============================================================"
  echo "▶ [#${ITER}] START  at $(date '+%Y-%m-%d %H:%M:%S')"
  echo "▶ Restart file: ${RESTART_FILE}"
  echo "▶ Kill interval: ${KILL_INTERVAL}s"
  echo "▶ Container name: ${CONTAINER_NAME}"
  echo "============================================================"

  # Remove any stale container with the same name
  echo "$PASSWORD" | sudo -S docker rm -f "${CONTAINER_NAME}" &>/dev/null || true

  # 1) Watchdog: every $KILL_INTERVAL seconds, kill only this container
  (
    while true; do
      sleep "${KILL_INTERVAL}"
      echo "▶ [watchdog] $(date '+%H:%M:%S') → docker kill ${CONTAINER_NAME}"
      echo "$PASSWORD" | sudo -S docker kill "${CONTAINER_NAME}" &>/dev/null
    done
  ) &> /dev/null &
  WD_PID=$!

  # 2) Run the container (blocking)
  echo "$PASSWORD" | sudo -S docker run --name "${CONTAINER_NAME}" --rm \
    -v "${HOME}/cp2k/data":/opt/cp2k/data:Z \
    -v "${PWD}":/work:Z \
    -w /work docker.io/cp2k/cp2k:latest \
    mpirun -n 10 -genv OMP_NUM_THREADS=4 \
      cp2k -i "${RESTART_FILE}" \
           -o simulation.input.out \
    > simulation.input.log 2>&1
  EXIT_CODE=$?

  # 3) Stop the watchdog for this iteration
  kill "${WD_PID}" &>/dev/null || true

  # 4) Report results
  echo "▶ [#${ITER}] END    at $(date '+%Y-%m-%d %H:%M:%S') (exit code: ${EXIT_CODE})"
  echo "----- Last 5 lines of simulation.input.log -----"
  tail -n 5 simulation.input.log
  echo "-----------------------------------------------"

  # 5) Check for warning message to break
  if tail -n 30 simulation.input.out \
     | grep -q "The number of warnings for this run is"; then
    echo "▶ [#${ITER}] Warning 메시지 발견 – 루프 종료"
    break
  fi

  echo "▶ [#${ITER}] Warning 없음 → 3초 후 재시작"
  sleep 3
done

echo "✅ 전체 완료. 총 반복 횟수: ${ITER}"

