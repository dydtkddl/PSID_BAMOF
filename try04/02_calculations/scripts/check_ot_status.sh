#!/usr/bin/env bash
set -euo pipefail

OUT_FILE="${1:-/mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster/test_output_ot.out}"
if [[ ! -f "$OUT_FILE" ]]; then
  echo "File not found: $OUT_FILE"
  exit 1
fi

if ! grep -q "OT" "$OUT_FILE"; then
  echo "INFO: no explicit OT marker found in output"
fi

OUTER_COUNT=$(grep -c "OUTER_SCF" "$OUT_FILE" 2>/dev/null || true)
echo "Output: $OUT_FILE"
echo "OUTER_SCF count: $OUTER_COUNT"

python3 - "$OUT_FILE" <<'PY'
import re, sys, math
out = sys.argv[1]
lines = open(out, errors="ignore").read().splitlines()

target = 5.0e-7
conv_vals = []
outers = 0
steps = []

for l in lines:
    if "OUTER_SCF" in l:
        outers += 1
    m = re.search(r"Convergence\\s+([0-9.eE+-]+)", l)
    if m:
        try:
            conv_vals.append(float(m.group(1)))
            continue
        except ValueError:
            pass
    m2 = re.search(r"CONVERGENCE\\s+([0-9.eE+-]+)", l, re.I)
    if m2:
        try:
            conv_vals.append(float(m2.group(1)))
        except ValueError:
            pass
    m3 = re.search(r"Step\\s+(\\d+)", l)
    if m3:
        s = int(m3.group(1))
        if "Geometry" in l or "Convergence" in l or "OT iteration" in l:
            steps.append(s)

if not conv_vals:
    print("No convergence values found.")
    sys.exit(0)

last = conv_vals[-1]
ratio = last / target if target != 0 else float("inf")
logratio = math.log10(ratio) if ratio > 0 else float("-inf")
print(f"Last convergence: {last:.5e}")
print(f"Target: {target:.1e}")
print(f"ratio(last/target): {ratio:.3e}")
print(f"log10(ratio): {logratio:.3f}")

if len(conv_vals) >= 20:
    window = conv_vals[-20:]
    decays = []
    for i in range(1, len(window)):
        a = window[i-1]
        b = window[i]
        if a > 0 and b > 0:
            decays.append((a - b) / a)
    if decays:
        avg_decay = sum(d for d in decays if d > 0) / max(1, len([d for d in decays if d > 0]))
        if avg_decay <= 0:
            print("No positive average decay in last 20 steps.")
        else:
            step_rem = max(0.0, (last - target) / ((avg_decay) if avg_decay > 0 else 1.0))
            print(f"Remaining step estimate (coarse): {step_rem:.0f}")

if steps:
    print(f"Last parsed SCF step/token: {steps[-1]}")

if "SCF run converged" in open(out, errors='ignore').read():
    print("Status: converged (string found)")
elif "SCF run NOT converged" in open(out, errors='ignore').read():
    print("Status: not converged (string found)")
else:
    print("Status: unknown / running")
PY
