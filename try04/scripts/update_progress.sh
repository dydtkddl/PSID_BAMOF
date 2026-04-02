#!/usr/bin/env bash
set -euo pipefail

PROGRESS_FILE="/mnt/d/PSID_BAMOF/try04/PROGRESS.md"
WORKDIR="/mnt/d/PSID_BAMOF/try04"
TIMESTAMP="$(date -Iseconds)"

cluster_out="$WORKDIR/02_calculations/BAMOF_2IP_cluster/simulation.input.out"
diss_out="$WORKDIR/02_calculations/BAMOF_2IP_dissociate/simulation.input.out"

extract_last_energy() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "N/A"
    return
  fi
  local e
  e=$(grep "ENERGY| Total FORCE_EVAL" "$file" | tail -n 1 | awk '{print $NF}')
  if [[ -z "$e" ]]; then echo "N/A"; else echo "$e"; fi
}

scf_state() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "missing"
    return
  fi
  local c n
  c=$(grep -c "SCF run converged" "$file" || true)
  n=$(grep -c "SCF run NOT converged" "$file" || true)
  echo "converged:${c} failed:${n}"
}

geo_step() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "N/A"
    return
  fi
  grep -E "STEP|Geometry step|GEO_OPT|Step" "$file" | tail -n 1 | awk '{print $NF}'
}

cat <<EOF >> "$PROGRESS_FILE"

## Auto-update: ${TIMESTAMP}
- cluster.out.exists: $([[ -f "$cluster_out" ]] && echo true || echo false)
- dissociate.out.exists: $([[ -f "$diss_out" ]] && echo true || echo false)
- cluster.scf: $(scf_state "$cluster_out")
- dissociate.scf: $(scf_state "$diss_out")
- cluster.last_energy: $(extract_last_energy "$cluster_out")
- dissociate.last_energy: $(extract_last_energy "$diss_out")
- cluster.last_geo_step: $(geo_step "$cluster_out")
- dissociate.last_geo_step: $(geo_step "$diss_out")
EOF
