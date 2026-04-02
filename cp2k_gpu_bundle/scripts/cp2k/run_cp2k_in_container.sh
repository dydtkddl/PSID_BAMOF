#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="${INPUT_DIR:-}"
INPUT_NAME="${INPUT_NAME:-}"
OUTPUT_NAME="${OUTPUT_NAME:-}"

if [[ -z "${INPUT_DIR}" || -z "${INPUT_NAME}" || -z "${OUTPUT_NAME}" ]]; then
  echo "[ERROR] INPUT_DIR, INPUT_NAME, OUTPUT_NAME must be set"
  exit 2
fi

cd /workspace
JOB_DIR="/workspace/${INPUT_DIR}"
cd "${JOB_DIR}"

export OMP_NUM_THREADS="${CP2K_OMP_THREADS:-8}"
CP2K_BIN="${CP2K_BIN:-$(command -v cp2k.psmp || command -v cp2k || true)}"
MPI_BIN="${MPI_BIN:-$(command -v mpirun || command -v mpiexec || true)}"

if [[ -z "${CP2K_BIN}" ]]; then
  CP2K_BIN="$(find /opt /usr/local -type f \( -name cp2k.psmp -o -name cp2k \) 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "${MPI_BIN}" ]]; then
  MPI_BIN="$(find /opt /usr/local -type f \( -name mpirun -o -name mpiexec \) 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "${CP2K_DATA_DIR:-}" ]]; then
  for p in /opt/cp2k/data /opt/cp2k/share/cp2k/data /usr/local/share/cp2k/data $(find /opt /usr/local -type d \( -path '*/cp2k/data' -o -path '*/cp2k/share/cp2k/data' \) 2>/dev/null); do
    if [[ -f "$p/BASIS_MOLOPT" ]]; then
      export CP2K_DATA_DIR="$p"
      break
    fi
  done
fi

if [[ ! -x "${CP2K_BIN}" ]]; then
  echo "[ERROR] CP2K binary not executable: ${CP2K_BIN}"
  exit 4
fi
if [[ -z "${MPI_BIN}" ]]; then
  echo "[ERROR] MPI launcher not found"
  exit 5
fi
if [[ ! -d "${CP2K_DATA_DIR:-}" ]]; then
  echo "[ERROR] CP2K data directory not found"
  exit 6
fi

MPI_ARGS=("-np" "${CP2K_MPI_RANKS:-1}")
if "${MPI_BIN}" --help 2>/dev/null | grep -qi -- '-bind-to'; then
  MPI_ARGS+=("-bind-to" "none")
fi

"${MPI_BIN}" "${MPI_ARGS[@]}" "${CP2K_BIN}" -i "${INPUT_NAME}" -o "${OUTPUT_NAME}"
