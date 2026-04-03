#!/usr/bin/env bash
set -euo pipefail

WORKDIR="/mnt/d/PSID_BAMOF/try04"
CONVERTER="$WORKDIR/03_postprocessing/cp2k_trajectory_converter.py"
VISUALIZER="$WORKDIR/03_postprocessing/visualize_mof.py"

CELL="16.00 -0.557 0.090 | -6.517 14.613 -0.057 | -4.635 -7.066 13.095"
OUT_ROOT="$WORKDIR/03_postprocessing/manual_visual_supercells_2x2x2"

INPUTS=(
  "$WORKDIR/02_calculations/BAMOF_2IP_cluster/BAMOF_2IP_cluster_init_visual.xyz"
  "$WORKDIR/02_calculations/BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init_visual.xyz"
)

mkdir -p "$OUT_ROOT"

for src in "${INPUTS[@]}"; do
  if [[ ! -f "$src" ]]; then
    echo "[SKIP] missing: $src"
    continue
  fi

  stem="$(basename "$src")"
  tag="${stem%_init_visual.xyz}"
  out_dir="$OUT_ROOT/${tag}_2x2x2"
  mkdir -p "$out_dir"

  echo "[STEP] convert: $src"
  python3 "$CONVERTER" \
    --init-xyz "$src" \
    --cell "$CELL" \
    --repeat 2 2 2 \
    --out-dir "$out_dir" \
    --frames last

  mol2="$out_dir/frame0000_2x2x2.mol2"
  if [[ ! -f "$mol2" ]]; then
    echo "[ERROR] expected mol2 not found: $mol2"
    continue
  fi

  tmp_pml="$out_dir/frame0000_2x2x2.pml"
  final_pml="$out_dir/${tag}_2x2x2.pml"
  echo "[STEP] make pml: $mol2"
  python3 "$VISUALIZER" "$mol2" --pml-only --style line

  if [[ -f "$tmp_pml" ]]; then
    mv -f "$tmp_pml" "$final_pml"
  fi

  echo "[DONE] pml = $final_pml"
  echo

done

echo "[OK] all done."
