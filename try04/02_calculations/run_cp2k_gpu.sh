#!/usr/bin/env bash
# ============================================================
# run_cp2k_gpu.sh - CP2K GEO_OPT launcher for try04
# BA-MOF + 2 IP Pairs
# ============================================================

set -u
set -o pipefail
set +e

INPUT_FILE="input.inp"
MPI_PROCS=8
OMP_THREADS=4
KILL_INTERVAL=3600
CPU_ONLY=false
DATA_DIR="${HOME}/cp2k/data"
DOCKER_IMAGE=""
ITER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)     DOCKER_IMAGE="$2"; shift 2;;
    --mpi)       MPI_PROCS="$2"; shift 2;;
    --omp)       OMP_THREADS="$2"; shift 2;;
    --kill)      KILL_INTERVAL="$2"; shift 2;;
    --cpu-only)  CPU_ONLY=true; shift;;
    --data-dir)  DATA_DIR="$2"; shift 2;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [[ -z "$DOCKER_IMAGE" ]]; then
  if [[ "$CPU_ONLY" == "true" ]]; then
    DOCKER_IMAGE="cp2k/cp2k:latest"
  else
    if docker image inspect cp2k-try04:2024.3-gpu &>/dev/null; then
      DOCKER_IMAGE="cp2k-try04:2024.3-gpu"
    elif docker image inspect cp2k/cp2k:2024.3_openmpi_generic_cuda_P100_psmp &>/dev/null; then
      DOCKER_IMAGE="cp2k/cp2k:2024.3_openmpi_generic_cuda_P100_psmp"
    else
      echo "GPU image not found. Falling back to CPU-only."
      DOCKER_IMAGE="cp2k/cp2k:latest"
      CPU_ONLY=true
    fi
  fi
fi

if [[ "$DOCKER_IMAGE" == *"openmpi"* ]] || [[ "$DOCKER_IMAGE" == "cp2k-try04"* ]]; then
  MPI_FLAVOR="openmpi"
  CP2K_BIN="cp2k.psmp"
else
  MPI_FLAVOR="intelmpi"
  CP2K_BIN="cp2k"
fi

if [[ "$CPU_ONLY" == "true" ]]; then
  GPU_FLAGS=""
else
  if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    GPU_FLAGS="--gpus all"
  else
    echo "nvidia-smi not available. Running CPU-only."
    GPU_FLAGS=""
    CPU_ONLY=true
  fi
fi

if [[ "$MPI_FLAVOR" == "openmpi" ]]; then
  MPI_CMD="mpirun -n ${MPI_PROCS} -x OMP_NUM_THREADS=${OMP_THREADS} -x OMP_STACKSIZE=512m --bind-to none"
else
  MPI_CMD="mpirun -n ${MPI_PROCS} -genv OMP_NUM_THREADS=${OMP_THREADS}"
fi

DATA_MOUNT=""
if [[ -d "$DATA_DIR" ]]; then
  DATA_MOUNT="-v ${DATA_DIR}:/opt/cp2k/data:Z"
  echo "CP2K data directory: ${DATA_DIR}"
else
  echo "CP2K data directory not found at ${DATA_DIR}. Using image built-in data."
fi

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
echo "============================================================"
echo "  try04 CP2K Runner"
echo "============================================================"
echo "  Image:       ${DOCKER_IMAGE}"
echo "  MPI flavor:  ${MPI_FLAVOR} (${MPI_PROCS} procs)"
echo "  OMP threads: ${OMP_THREADS}"
echo "  GPU:         $([ \"$CPU_ONLY\" == \"true\" ] && echo OFF || echo ON)"
echo "  Kill interval: ${KILL_INTERVAL}s"
echo "  Input file:  ${INPUT_FILE}"
echo "  Work dir:    ${WORKDIR}"
echo "============================================================"

if [[ ! -f "${WORKDIR}/${INPUT_FILE}" ]]; then
  echo "ERROR: ${INPUT_FILE} not found in ${WORKDIR}"
  exit 1
fi

XYZ_FILE=$(grep -oP 'COORD_FILE_NAME\s+\K\S+' "${WORKDIR}/${INPUT_FILE}" || true)
if [[ -n "$XYZ_FILE" && ! -f "${WORKDIR}/${XYZ_FILE}" ]]; then
  echo "ERROR: XYZ file '${XYZ_FILE}' referenced in input not found"
  exit 1
fi
echo "XYZ file: ${XYZ_FILE}"

if [[ "$CPU_ONLY" != "true" ]]; then
  echo ""
  echo "=== GPU Status ==="
  nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv 2>/dev/null || true
  echo "=================="
fi

cleanup() {
  [[ -n "${WD_PID:-}" ]] && kill "${WD_PID}" &>/dev/null || true
}
trap cleanup EXIT

while true; do
  ITER=$((ITER+1))
  CONTAINER_NAME="cp2k_2ip_$(basename "${WORKDIR}")_${ITER}"

  echo ""
  echo "[${ITER}] START at $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Input: ${INPUT_FILE}"

  docker rm -f "${CONTAINER_NAME}" &>/dev/null || true

  (
    while true; do
      sleep "${KILL_INTERVAL}"
      echo "[watchdog] $(date '+%H:%M:%S') killing ${CONTAINER_NAME}"
      docker kill "${CONTAINER_NAME}" &>/dev/null
    done
  ) &>/dev/null &
  WD_PID=$!

  docker run --name "${CONTAINER_NAME}" --rm \
    ${GPU_FLAGS} \
    ${DATA_MOUNT} \
    -v "${WORKDIR}":/work:Z \
    -w /work \
    "${DOCKER_IMAGE}" \
    ${MPI_CMD} \
      ${CP2K_BIN} -i "${INPUT_FILE}" \
                  -o simulation.input.out \
    > simulation.input.log 2>&1
  EXIT_CODE=$?

  kill "${WD_PID}" &>/dev/null || true

  echo "[#${ITER}] END at $(date '+%Y-%m-%d %H:%M:%S') (exit: ${EXIT_CODE})"

  if [[ -f "${WORKDIR}/simulation.input.out" ]]; then
    GEO_STEPS=$(grep -c "OPTIMIZATION STEP:" "${WORKDIR}/simulation.input.out" 2>/dev/null || echo "0")
    LAST_E=$(grep "ENERGY|" "${WORKDIR}/simulation.input.out" 2>/dev/null | tail -1 || echo "N/A")
    echo "  GEO_OPT steps: ${GEO_STEPS}"
    echo "  Last energy: ${LAST_E}"

    SCF_FAIL=$(grep -c "SCF run NOT converged" "${WORKDIR}/simulation.input.out" 2>/dev/null || echo "0")
    if [[ "${SCF_FAIL}" -gt 0 ]]; then
      echo "  SCF convergence failures detected: ${SCF_FAIL}"
    fi
  fi

  if tail -n 30 "${WORKDIR}/simulation.input.out" 2>/dev/null | \
     grep -q "The number of warnings for this run is"; then
    echo "CP2K finished (warnings summary found)."
    break
  fi

  if tail -n 50 "${WORKDIR}/simulation.input.out" 2>/dev/null | \
     grep -q "GEOMETRY OPTIMIZATION COMPLETED"; then
    echo "GEO_OPT completed."
    break
  fi

  RESTART_FILE=$(ls -t "${WORKDIR}"/*.restart 2>/dev/null | head -1)
  if [[ -n "${RESTART_FILE}" ]]; then
    INPUT_FILE="$(basename "${RESTART_FILE}")"
    echo "Restart file: ${INPUT_FILE}"
  fi

  echo "Retrying in 5 seconds..."
  sleep 5
done

echo ""
echo "============================================================"
echo "Done. Total iterations: ${ITER}"
echo "============================================================"
echo ""
echo "Final energy:"
grep "ENERGY|" "${WORKDIR}/simulation.input.out" 2>/dev/null | tail -3
echo ""

if grep -q "GEOMETRY OPTIMIZATION COMPLETED" "${WORKDIR}/simulation.input.out" 2>/dev/null; then
  echo "GEO_OPT CONVERGED"
else
  echo "GEO_OPT did NOT converge within MAX_ITER"
fi
