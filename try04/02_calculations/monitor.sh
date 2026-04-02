#!/usr/bin/env bash
set -u
set -o pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGETS=(
  "${BASE_DIR}/BAMOF_2IP_cluster"
  "${BASE_DIR}/BAMOF_2IP_dissociate"
)
LOG_FILE="${BASE_DIR}/monitor.log"
STATE_FILE="${BASE_DIR}/.monitor_state"
INTERVAL_SEC=300
MAX_ITER=600

echo "[START] $(date '+%F %T') monitoring ${BASE_DIR}" | tee -a "${LOG_FILE}"

parse_energy() {
  local f="$1"
  grep -E "ENERGY\\| Total FORCE_EVAL" "$f" 2>/dev/null | tail -n 1 | awk '{print $NF}'
}

parse_scf_fail() {
  local f="$1"
  grep -c "SCF run NOT converged" "$f" 2>/dev/null || true
}

parse_step() {
  local f="$1"
  grep -c "OPTIMIZATION STEP:" "$f" 2>/dev/null || true
}

parse_max_force() {
  local f="$1"
  grep -Ei "max force|maximum force|rms force" "$f" 2>/dev/null | tail -n 1 \
    | sed -E 's/.*([0-9]+(\\.[0-9]+)?([eE][+-]?[0-9]+)?).*/\\1/'
}

while true; do
  ts="$(date '+%F %T')"
  for d in "${TARGETS[@]}"; do
    name="$(basename "$d")"
    out="${d}/simulation.input.out"
    if [[ ! -f "${out}" ]]; then
      echo "${ts} ${name} no_output" | tee -a "${LOG_FILE}"
      continue
    fi

    step="$(parse_step "${out}")"
    energy="$(parse_energy "${out}")"
    force="$(parse_max_force "${out}")"
    scf_fail="$(parse_scf_fail "${out}")"
    [ -z "${step}" ] && step=0
    [ -z "${energy}" ] && energy="NA"
    [ -z "${force}" ] && force="NA"

    if tail -n 5 "${out}" | grep -q "GEOMETRY OPTIMIZATION COMPLETED"; then
      status="COMPLETED"
    elif (( scf_fail > 0 )); then
      status="SCF_FAIL"
    else
      status="RUNNING"
    fi

    prev=0
    prev_ts=$(date +%s)
    if [[ -f "${STATE_FILE}" ]]; then
      line="$(grep "^${name} " "${STATE_FILE}" || true)"
      if [[ -n "${line}" ]]; then
        prev="$(echo "${line}" | awk '{print $2}')"
        prev_ts="$(echo "${line}" | awk '{print $3}')"
      fi
    fi

    eta="N/A"
    if (( step > prev && prev > 0 )); then
      now=$(date +%s)
      dt=$(( now - prev_ts ))
      ds=$(( step - prev ))
      avg=$(( dt / ds ))
      remain=$(( MAX_ITER - step ))
      (( remain < 0 )) && remain=0
      eta=$(( avg * remain ))
      eta="${eta}s"
    fi

    echo "${ts} ${name} step=${step}/${MAX_ITER} energy=${energy} max_force=${force} scf_fail=${scf_fail} status=${status} eta=${eta}" | tee -a "${LOG_FILE}"

    tmp="${STATE_FILE}.tmp"
    grep -v "^${name} " "${STATE_FILE}" 2>/dev/null > "${tmp}" || true
    echo "${name} ${step} $(date +%s)" >> "${tmp}"
    mv "${tmp}" "${STATE_FILE}"
  done

  disk="$(du -sh "${BASE_DIR}" | awk '{print $1}')"
  echo "${ts} DISK=${disk}" | tee -a "${LOG_FILE}"
  echo "[sleep ${INTERVAL_SEC}s] Ctrl+C to stop"
  sleep "${INTERVAL_SEC}"
done
