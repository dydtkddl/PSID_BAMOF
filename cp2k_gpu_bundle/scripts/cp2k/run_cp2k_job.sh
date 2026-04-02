#!/usr/bin/env bash
set -euo pipefail
trap 'echo "[ERROR] run_cp2k_job.sh failed at line $LINENO"; exit 1' ERR

INPUT=""
OUTPUT=""
STAGE=""
SYSTEM=""
LOG_FILE=""
QUIET=0

to_fs_path() {
  local value="$1"
  if [[ "${value}" =~ ^[A-Za-z]:[\\/].* ]]; then
    local drive="${value:0:1}"
    local rest="${value:2}"
    rest="${rest//\\//}"
    drive="$(printf '%s' "${drive}" | tr 'A-Z' 'a-z')"
    printf '/mnt/%s%s' "${drive}" "${rest}"
    return 0
  fi
  printf '%s' "${value}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input) INPUT="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --stage) STAGE="$2"; shift 2 ;;
    --system) SYSTEM="$2"; shift 2 ;;
    --log-file) LOG_FILE="$2"; shift 2 ;;
    --quiet) QUIET=1; shift ;;
    --verbose|--no-progress) shift ;;
    *) echo "[ERROR] Unknown arg: $1"; exit 2 ;;
  esac
done

if [[ -z "${INPUT}" || -z "${OUTPUT}" || -z "${STAGE}" || -z "${SYSTEM}" || -z "${LOG_FILE}" ]]; then
  echo "[ERROR] Missing required args"
  exit 2
fi

INPUT_FS="$(to_fs_path "${INPUT}")"
OUTPUT_FS="$(to_fs_path "${OUTPUT}")"
LOG_FILE_FS="$(to_fs_path "${LOG_FILE}")"

mkdir -p "$(dirname "${OUTPUT_FS}")" "$(dirname "${LOG_FILE_FS}")"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="$(dirname "${OUTPUT}")"
OUTPUT_DIR_FS="$(dirname "${OUTPUT_FS}")"
RUNNING_MARKER="${OUTPUT_DIR}/.running"
STATUS_FILE="${OUTPUT_DIR}/run_meta.json"
CONTAINER_ID="$(docker compose ps -q cp2k 2>/dev/null || true)"
IMAGE_ID="$(docker inspect -f '{{.Image}}' keti-cp2k 2>/dev/null || true)"
START_TS="$(date --iso-8601=seconds)"
EXIT_CODE=99

normalize_json_path() {
  local value="$1"
  value="${value//\\/\/}"
  printf '%s' "${value}"
}

rotate_if_exists() {
  local target="$1"
  if [[ -f "${target}" ]]; then
    mv "${target}" "${target}.${STAMP}.bak"
  fi
}

write_status() {
  local state="$1"
  local end_ts="${2:-}"
  cat > "${STATUS_FILE}" <<EOF
{
  "system": "${SYSTEM}",
  "stage": "${STAGE}",
  "state": "${state}",
  "input": "$(normalize_json_path "${INPUT}")",
  "output": "$(normalize_json_path "${OUTPUT}")",
  "log_file": "$(normalize_json_path "${LOG_FILE}")",
  "started_at": "${START_TS}",
  "ended_at": "${end_ts}",
  "exit_code": ${EXIT_CODE},
  "container_id": "${CONTAINER_ID}",
  "image_id": "${IMAGE_ID}"
}
EOF
}

rotate_if_exists "${OUTPUT_FS}"
rotate_if_exists "${LOG_FILE_FS}"
exec > >(tee "${LOG_FILE_FS}") 2>&1

INPUT_DIR="$(dirname "${INPUT}")"
INPUT_NAME="$(basename "${INPUT}")"
OUTPUT_NAME="$(basename "${OUTPUT}")"

echo "============================================================"
echo "[STAGE] CP2K ${SYSTEM} / ${STAGE}"
echo "[START] $(date --iso-8601=seconds)"
echo "[INPUT] ${INPUT}"
echo "[OUT  ] ${OUTPUT}"
echo "[LOG  ] ${LOG_FILE}"
echo "============================================================"

if [[ ! -f "${INPUT_FS}" ]]; then
  echo "[ERROR] Missing input: ${INPUT}"
  exit 3
fi

echo "${START_TS}" > "${RUNNING_MARKER}"
write_status "RUNNING" ""

(
  LAST_SIZE=-1
  STALE_COUNT=0
  while true; do
    sleep "${HEARTBEAT_SECONDS:-30}"
    if [[ -f "${OUTPUT}" ]]; then
      CUR_SIZE=$(wc -c < "${OUTPUT}" 2>/dev/null || echo 0)
      LAST_LINE=$(tail -n 3 "${OUTPUT}" 2>/dev/null | tr '\n' ' ' | sed 's/  */ /g' | cut -c1-220 || true)
      if [[ "${CUR_SIZE}" -eq "${LAST_SIZE}" ]]; then
        STALE_COUNT=$((STALE_COUNT+1))
      else
        STALE_COUNT=0
      fi
      LAST_SIZE="${CUR_SIZE}"
      [[ "${QUIET}" -eq 1 ]] || echo "[HEARTBEAT] $(date --iso-8601=seconds) stage=${STAGE} bytes=${CUR_SIZE} stale=${STALE_COUNT} tail='${LAST_LINE}'"
    else
      [[ "${QUIET}" -eq 1 ]] || echo "[HEARTBEAT] $(date --iso-8601=seconds) waiting_for_output=${OUTPUT}"
    fi
  done
) &
HB_PID=$!

cleanup() {
  kill "${HB_PID}" >/dev/null 2>&1 || true
  rm -f "${RUNNING_MARKER}" >/dev/null 2>&1 || true
  local final_state="FAIL"
  if [[ "${EXIT_CODE}" -eq 0 ]]; then
    final_state="DONE"
  fi
  write_status "${final_state}" "$(date --iso-8601=seconds)"
}
trap cleanup EXIT

docker compose exec -T \
  -e CP2K_MPI_RANKS=${CP2K_MPI_RANKS:-1} \
  -e CP2K_OMP_THREADS=${CP2K_OMP_THREADS:-4} \
  -e INPUT_DIR="${INPUT_DIR}" \
  -e INPUT_NAME="${INPUT_NAME}" \
  -e OUTPUT_NAME="${OUTPUT_NAME}" \
  cp2k bash /workspace/scripts/cp2k/run_cp2k_in_container.sh

EXIT_CODE=0
echo "[DONE ] $(date --iso-8601=seconds)"
