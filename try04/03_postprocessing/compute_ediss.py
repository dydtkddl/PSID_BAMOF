#!/usr/bin/env python3
"""compute_ediss.py
Compute E_diss and unit conversions from final energies.
"""

from __future__ import annotations

from pathlib import Path
import re

HA_TO_KJ_PER_MOL = 2625.49962
HA_TO_KCAL_PER_MOL = 627.509474
HA_TO_EV = 27.211386245988


def parse_final_energy(out: Path) -> float | None:
    num_re = re.compile(r"(-?\d+\.\d+(?:[EDed][+-]?\d+)?)")
    if not out.exists():
        raise FileNotFoundError(out)
    last = None
    for line in out.read_text(errors="ignore").splitlines():
        if "ENERGY| Total FORCE_EVAL" in line:
            nums = num_re.findall(line)
            if nums:
                last = float(nums[-1])
    return last


def print_ediss(cluster: float, diss: float, refs: list[float] | None = None) -> None:
    ediss = diss - cluster
    print(f"Cluster final energy: {cluster:.8f} Ha")
    print(f"Dissociate final energy: {diss:.8f} Ha")
    print(f"E_diss = E(diss) - E(cluster) = {ediss:.8f} Ha")
    print(f"         = {ediss*HA_TO_KJ_PER_MOL:.6f} kJ/mol")
    print(f"         = {ediss*HA_TO_KCAL_PER_MOL:.6f} kcal/mol")
    print(f"         = {ediss*HA_TO_EV:.6f} eV")
    if refs is None:
        refs = [17.77, 23.05, 225.06]
    labels = ["Ref-1IP-MIL125 (kJ/mol): 17.77", "Ref-1IP-BAMOF (kJ/mol): 23.05", "Gas phase (kJ/mol): 225.06"]
    if refs:
        for label, val in zip(labels, refs):
            diff = ediss * HA_TO_KJ_PER_MOL - val
            print(f"  diff vs {label}: {diff:.4f} kJ/mol")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--cluster", required=True)
    p.add_argument("--dissociate", required=True)
    p.add_argument("--ref", nargs="*", type=float)
    args = p.parse_args()

    e_cluster = parse_final_energy(Path(args.cluster))
    e_diss = parse_final_energy(Path(args.dissociate))
    if e_cluster is None or e_diss is None:
        raise RuntimeError("Could not parse energy from one of the outputs.")
    print_ediss(e_cluster, e_diss, args.ref if args.ref else None)


if __name__ == "__main__":
    main()
