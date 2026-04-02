#!/usr/bin/env bash
set -euo pipefail
trap 'echo "[ERROR] validate_cp2k_runtime.sh failed at line $LINENO"; exit 1' ERR

LOG_DIR="logs/cp2k"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/validate_cp2k_runtime_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "============================================================"
echo "[STAGE] Validate CP2K runtime"
echo "[START] $(date --iso-8601=seconds)"
echo "[LOG  ] ${LOG_FILE}"
echo "============================================================"

docker compose exec -T cp2k bash -lc '
set -euo pipefail
CP2K_BIN="${CP2K_BIN:-$(command -v cp2k.psmp || command -v cp2k || true)}"
MPI_BIN="${MPI_BIN:-$(command -v mpirun || command -v mpiexec || true)}"
if [[ -z "${CP2K_BIN}" ]]; then
  CP2K_BIN="$(find /opt /usr/local -type f \( -name cp2k.psmp -o -name cp2k \) 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "${MPI_BIN}" ]]; then
  MPI_BIN="$(find /opt /usr/local -type f \( -name mpirun -o -name mpiexec \) 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "${CP2K_DATA_DIR:-}" ]]; then
  for p in /opt/cp2k/data /opt/cp2k/share/cp2k/data /usr/local/share/cp2k/data $(find /opt /usr/local -type d \( -path "*/cp2k/data" -o -path "*/cp2k/share/cp2k/data" \) 2>/dev/null); do
    if [[ -f "$p/BASIS_MOLOPT" ]]; then
      export CP2K_DATA_DIR="$p"
      break
    fi
  done
fi
echo "[INFO ] Container hostname: $(hostname)"
echo "[INFO ] CP2K binary check"
test -x "${CP2K_BIN}"
echo "${CP2K_BIN}"
echo "[INFO ] CP2K version"
"${CP2K_BIN}" -v
echo "[INFO ] CUDA-linked libraries"
ldd "${CP2K_BIN}" | egrep -i "cuda|cublas|cusolver|cufft|curand|nvidia" || true
echo "[INFO ] GPU visibility"
nvidia-smi || true
echo "[INFO ] MPI check"
echo "${MPI_BIN}"
echo "[INFO ] Data files"
test -f "${CP2K_DATA_DIR}/BASIS_MOLOPT"
test -f "${CP2K_DATA_DIR}/BASIS_MOLOPT_UCL"
test -f "${CP2K_DATA_DIR}/POTENTIAL"
test -f "${CP2K_DATA_DIR}/dftd3.dat"
echo "[INFO ] Na basis inventory"
grep "^Na " "${CP2K_DATA_DIR}/BASIS_MOLOPT" | head -20 || true
grep "^Na " "${CP2K_DATA_DIR}/BASIS_MOLOPT_UCL" | head -20 || true
'

echo "[DONE ] CP2K runtime validation complete"
