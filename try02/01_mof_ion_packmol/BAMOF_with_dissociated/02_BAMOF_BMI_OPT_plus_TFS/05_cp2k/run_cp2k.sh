#!/usr/bin/env bash
# run_cp2k.sh
# 사용법: ./run_cp2k.sh [-s seconds] [-m minutes] <RESTART_FILE>
# 예시:  ./run_cp2k.sh -m 30 MIL125_DISSOCIATED_GEOOPT-1.restart

set -uo pipefail
set +e  # 워치독 때문에 -e 끔

usage() {
  echo "Usage: $0 [-s seconds] [-m minutes] <restart_file>"
  exit 1
}

# 기본값: 30분
RUN_SECS=$((20*60))

# 옵션 파싱
while getopts ":s:m:" opt; do
  case $opt in
    s) RUN_SECS="$OPTARG" ;;
    m) RUN_SECS="$((OPTARG*60))" ;;
    *) usage ;;
  esac
done
shift $((OPTIND-1))

# 리스타트 파일
if [ $# -lt 1 ]; then
  usage
fi
RESTART_FILE="$1"

PASSWORD="9582"
ITER=0

# 워치독 백그라운드: 지정 초마다 cp2k 프로세스 전부 강제 종료
(
  while true; do
    sleep "$RUN_SECS"
    echo "▶ [watchdog] $(date '+%H:%M:%S') → pkill -9 cp2k"
    echo "$PASSWORD" | sudo -S pkill -f -9 cp2k
  done
)&
WATCHDOG_PID=$!

# 메인 루프
while true; do
  ITER=$((ITER+1))
  echo "============================================================"
  echo "▶ [#${ITER}] START  at $(date '+%Y-%m-%d %H:%M:%S')"
  echo "▶ Restart file: ${RESTART_FILE}"
  echo "▶ Kill interval: ${RUN_SECS}s"
  echo "============================================================"

  # 컨테이너 실행 (blocking)
  echo "$PASSWORD" | sudo -S podman run --rm \
    -v "$HOME/cp2k/data":/opt/cp2k/data:Z \
    -v "$PWD":/work:Z \
    -w /work docker.io/cp2k/cp2k:latest \
    mpirun -n 7 -genv OMP_NUM_THREADS=4 \
      cp2k -i "${RESTART_FILE}" \
           -o simulation.input.out \
    > simulation.input.log 2>&1

  EXIT_CODE=$?
  echo "▶ [#${ITER}] FINISHED (exit code: ${EXIT_CODE})"
  echo "----- Last 5 lines of simulation.input.log -----"
  tail -n 5 simulation.input.log
  echo "-----------------------------------------------"

  # 워닝 메시지 검사
  if tail -n 30 simulation.input.out \
     | grep -q "The number of warnings for this run is"; then
    echo "▶ [#${ITER}] Warning 메시지 발견 – 루프 종료"
    break
  fi

  echo "▶ [#${ITER}] Warning 없음 → 3초 후 재시작"
  sleep 3
done

# 워치독 정리
kill $WATCHDOG_PID &>/dev/null
echo "✅ 전체 완료. 총 반복 횟수: ${ITER}"
