#!/usr/bin/env python3
"""
analyze.py (try04)
===================
Compute E_diss, check GEO_OPT convergence, and optionally inspect
2nd ion-pair separation in the dissociation trajectory.

Usage:
    python3 analyze.py
    python3 analyze.py --energy-only
    python3 analyze.py --check CASE_DIR
"""

import csv
import os
import re
from pathlib import Path

import numpy as np

HA_TO_KJMOL = 2625.5
CALC_DIR = Path(__file__).parent / ".." / "02_calculations"

# try03 reference values
REF_EDISS = {
    'gas_phase': 225.06,
    'BAMOF_1IP': 17.77,
    'MOF_1IP': 23.05,
}


def extract_final_energy(outfile):
    """Extract final energy and convergence status from CP2K output."""
    if not Path(outfile).exists():
        return None

    with open(outfile, encoding="utf-8", errors="ignore") as f:
        content = f.read()

    energies = re.findall(r"ENERGY\| Total FORCE_EVAL.*?:\s+([-.\d]+)", content)
    if not energies:
        return None

    return {
        'energy_ha': float(energies[-1]),
        'n_steps': len(re.findall(r"OPTIMIZATION STEP:", content)),
        'converged': "GEOMETRY OPTIMIZATION COMPLETED" in content,
        'scf_failures': len(re.findall(r"SCF run NOT converged", content)),
    }


def calc_ediss(cluster_dir, dissociate_dir, label="BA-MOF 2IP"):
    """Compute and print dissociation energy from cluster and dissociated jobs."""
    e_c = extract_final_energy(f"{cluster_dir}/simulation.input.out")
    e_d = extract_final_energy(f"{dissociate_dir}/simulation.input.out")

    if not e_c or not e_d:
        missing = []
        if not e_c:
            missing.append("cluster")
        if not e_d:
            missing.append("dissociate")
        print(f"Missing output files: {', '.join(missing)}")
        return None

    ediss_ha = e_d['energy_ha'] - e_c['energy_ha']
    ediss_kj = ediss_ha * HA_TO_KJMOL

    print(f"\n{'='*60}")
    print(f"  E_diss: {label}")
    print(f"{'='*60}")
    print(f"  E_cluster:     {e_c['energy_ha']:.10f} Ha ({e_c['n_steps']} steps, conv={e_c['converged']})")
    print(f"  E_dissociated: {e_d['energy_ha']:.10f} Ha ({e_d['n_steps']} steps, conv={e_d['converged']})")
    print(f"  E_diss = {ediss_ha:.10f} Ha = {ediss_kj:.2f} kJ/mol")

    print(f"\n  Reference values (kJ/mol)")
    print(f"  {'System':<24} {'E_diss':>10}")
    print(f"  {'-'*12} {'-'*10}")
    print(f"  {'Gas-phase':<24} {REF_EDISS['gas_phase']:>10.2f}")
    print(f"  {'MOF + 1 IP':<24} {REF_EDISS['MOF_1IP']:>10.2f}")
    print(f"  {'BA-MOF + 1 IP':<24} {REF_EDISS['BAMOF_1IP']:>10.2f}")
    print(f"  {'BA-MOF + 2 IP (new)':<24} {ediss_kj:>10.2f}")

    diff = ediss_kj - REF_EDISS['BAMOF_1IP']
    print(f"\n  (2IP - 1IP) = {diff:+.2f} kJ/mol ({diff / REF_EDISS['BAMOF_1IP'] * 100:+.1f}%)")

    if ediss_kj <= REF_EDISS['BAMOF_1IP']:
        print("  Trend: screening lowers or keeps similar dissociation energy.")
    elif ediss_kj < REF_EDISS['BAMOF_1IP'] * 1.5:
        print(f"  Trend: slightly higher, still far below gas-phase ({REF_EDISS['gas_phase']:.2f}).")

    return {
        'label': label,
        'ediss_kj': ediss_kj,
        'cluster_conv': e_c['converged'],
        'diss_conv': e_d['converged'],
    }


def check_distances(xyz_file, n_mof=102, n_unfixed=22, n_emim=19, n_tfsi=15):
    """Check minimum EMIM-TFSI distance for the 2nd ion pair in the last frame."""
    if not Path(xyz_file).exists():
        print(f"  File not found: {xyz_file}")
        return None

    with open(xyz_file, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    natoms = int(lines[0].strip())
    frame_size = natoms + 2
    n_frames = len(lines) // frame_size
    last_start = (n_frames - 1) * frame_size

    coords = []
    for line in lines[last_start + 2:last_start + 2 + natoms]:
        parts = line.split()
        coords.append([float(x) for x in parts[1:4]])
    coords = np.array(coords)

    ip2_start = n_mof + n_unfixed + n_emim + n_tfsi
    emim2 = coords[ip2_start:ip2_start + n_emim]
    tfsi2 = coords[ip2_start + n_emim:ip2_start + n_emim + n_tfsi]

    d = np.min(np.linalg.norm(emim2[:, None, :] - tfsi2[None, :, :], axis=2))
    print(f"  Frame {n_frames}: 2nd IP EMIM-TFSI min dist = {d:.2f} A", end="")
    if d < 3.5:
        print(" -> RECOMBINED")
    elif d < 5.0:
        print(" (borderline)")
    else:
        print(" -> separated")

    return d


def main():
    print("try04 postprocessing summary")
    print("=" * 60)

    cluster_dir = CALC_DIR / "BAMOF_2IP_cluster"
    diss_dir = CALC_DIR / "BAMOF_2IP_dissociate"

    result = calc_ediss(cluster_dir, diss_dir)

    traj = diss_dir / "BAMOF_2IP_dissociate-pos-1.xyz"
    if traj.exists():
        print(f"\n[Distance Check] {traj}")
        check_distances(str(traj))

    if result:
        outcsv = Path(__file__).parent / "energy_comparison.csv"
        with open(outcsv, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['System', 'N_IP', 'E_diss_kJmol', 'Converged'])
            w.writerow(['Gas-phase', 1, 225.06, True])
            w.writerow(['MOF', 1, 23.05, True])
            w.writerow(['BA-MOF', 1, 17.77, True])
            w.writerow(['BA-MOF', 2, f"{result['ediss_kj']:.2f}", result['cluster_conv'] and result['diss_conv']])
        print(f"\nSaved: {outcsv}")


if __name__ == "__main__":
    main()
