#!/usr/bin/env bash
set -euo pipefail

OUT_FILE="${1:?Usage: monitor_scf.sh <simulation.output>}"
if [[ ! -f "$OUT_FILE" ]]; then
  echo "File not found: $OUT_FILE"
  exit 1
fi

echo "[monitor] file=$OUT_FILE"
echo "[monitor] sampled_at=$(date -Iseconds)"

SCF_CONV_COUNT=$(grep -c "SCF run converged" "$OUT_FILE" 2>/dev/null || true)
SCF_FAIL_COUNT=$(grep -c "SCF run NOT converged" "$OUT_FILE" 2>/dev/null || true)
echo "SCF converged count: $SCF_CONV_COUNT"
echo "SCF NOT converged count: $SCF_FAIL_COUNT"

echo ""
echo "Last 10 ENERGY| Total FORCE_EVAL lines:"
grep "ENERGY| Total FORCE_EVAL" "$OUT_FILE" | tail -n 10 || true
echo ""

python3 - "$OUT_FILE" <<'PY'
import re, sys, statistics, os, time
out = sys.argv[1]
lines = open(out, errors="ignore").read().splitlines()

energy = []
conv = []
step_info = {}
for i,l in enumerate(lines):
    if "SCF run converged" in l or "SCF run NOT converged" in l:
        step = step_info.get("step")
        if step is not None:
            step_info.setdefault("scf", []).append((step, "converged" in l))
    if "Step" in l and "Time" in l:
        # very permissive parser e.g. Step  10  ...
        m = re.search(r"Step\\s+(\\d+)", l)
        if m:
            step_info["step"] = int(m.group(1))
    if "ENERGY| Total FORCE_EVAL" in l:
        m = re.findall(r"(-?\\d+\\.\\d+(?:[Ee][+-]?\\d+)?)", l)
        if m:
            try:
                energy.append((i, float(m[-1])))
            except ValueError:
                pass
    if "Max Force" in l or "Maximal force" in l:
        m = re.findall(r"(-?\\d+\\.\\d+(?:[Ee][+-]?\\d+)?)", l)
        if m:
            conv.append((i, float(m[-1])))

if energy:
    last_step, last_e = energy[-1]
    print(f"Last total energy: {last_e:.12f}")
else:
    print("No ENERGY| Total FORCE_EVAL found.")

if conv:
    _, c = conv[-1]
    print(f"Last max-force estimate: {c:.10f}")

conv_vals = [v for _,v in conv]
if len(conv_vals) >= 2:
    deltas = [abs(conv_vals[i] - conv_vals[i-1]) for i in range(1, len(conv_vals))]
    avg_delta = statistics.mean(deltas)
else:
    avg_delta = 0.0

step_re = re.search(r"\\b(\\d+)\\b", str(os.path.basename(out)))
sim_step = 0
if step_re:
    sim_step = int(step_re.group(1))

if energy and sim_step:
    # fallback ETA from file timestamp + per-step trend
    elapsed = os.path.getmtime(out) - os.path.getctime(out)
    # if output has 600-step GEO_OPT target:
    remaining = max(0, 600 - sim_step)
    if sim_step > 1 and elapsed > 0:
        avg_t = elapsed / sim_step
        eta_s = remaining * avg_t
        print(f"Estimated remaining time (coarse): {eta_s/60:.1f} min")
    else:
        print("ETA estimate unavailable.")
else:
    print("ETA estimate unavailable.")

if conv_vals:
    print(f"Last 5 max-force values:")
    tail = conv_vals[-5:]
    for i,v in enumerate(tail, start=max(0, len(conv_vals)-5)):
        print(f"  {i:5d}: {v:.10f}")
PY

echo ""
echo "Tail SCF lines:"
grep -E "SCF run|ENERGY\\| Total FORCE_EVAL|GEO_OPT|Total Force Eval" "$OUT_FILE" | tail -n 30 || true
