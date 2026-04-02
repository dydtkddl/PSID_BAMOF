#!/usr/bin/env python3
"""distance_report.py
Create comparison and nearest-distance tables for initial try04 structures.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

BASE = Path("/mnt/d/PSID_BAMOF/try04/02_calculations")
OUT = Path("/mnt/d/PSID_BAMOF/try04/01_structure_preparation/distance_report.txt")

# index boundaries (0-based, Python slicing)
MOF_HOST_END = 102
MOF_ALL_END = 124
IP1_START = 124
IP1_END = 158
IP2_START = 158
IP2_END = 192
EMIM2_START = 158
EMIM2_END = 177
TFSI2_START = 177
TFSI2_END = 192

ATOMS_MASS = {"H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998, "S": 32.06, "Ti": 47.867}

PATHS = {
    "cluster": BASE / "BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz",
    "dissociate": BASE / "BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz",
}


def read_xyz(path: Path):
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = int(lines[0])
    atoms: list[str] = []
    xyz: list[list[float]] = []
    for row in lines[2 : 2 + n]:
        p = row.split()
        atoms.append(p[0])
        xyz.append([float(p[1]), float(p[2]), float(p[3])])
    return atoms, np.array(xyz, dtype=float)


def pair_min(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    return float(np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2).min())


def nearest_from_set(src: np.ndarray, target: np.ndarray):
    if len(src) == 0 or len(target) == 0:
        return np.array([]), np.array([], dtype=int)
    d = np.linalg.norm(src[:, None, :] - target[None, :, :], axis=2)
    mins = d.min(axis=1)
    idx = d.argmin(axis=1)
    return mins, idx


def nearest_atom_pairs(src: np.ndarray, tgt: np.ndarray):
    if len(src) == 0 or len(tgt) == 0:
        return float("nan"), -1, -1
    d = np.linalg.norm(src[:, None, :] - tgt[None, :, :], axis=2)
    i, j = divmod(int(np.argmin(d)), d.shape[1])
    return float(d.min()), i, j


def com(atoms: list[str], xyz: np.ndarray, indices: range) -> np.ndarray:
    sel = [i for i in indices if i < len(atoms)]
    if not sel:
        return np.array([np.nan, np.nan, np.nan], dtype=float)
    w = np.array([ATOMS_MASS.get(atoms[i], 12.0) for i in sel], dtype=float)
    r = xyz[sel]
    return (r * w[:, None]).sum(axis=0) / w.sum()


def section(name: str):
    atoms, xyz = read_xyz(PATHS[name])

    host = xyz[:MOF_HOST_END]
    host_or_mof_all = xyz[:MOF_ALL_END]
    ip1 = xyz[IP1_START:IP1_END]
    ip2 = xyz[IP2_START:IP2_END]
    emim2 = xyz[EMIM2_START:EMIM2_END]
    tfsi2 = xyz[TFSI2_START:TFSI2_END]

    d_ip2_host, host_idx = nearest_from_set(ip2, np.vstack((host, ip1)))
    emim2_min, emim_idx, tfsi_idx = nearest_atom_pairs(emim2, tfsi2)
    emim2_ti_min, _, _ = nearest_atom_pairs(np.array([com(atoms, xyz, range(EMIM2_START, EMIM2_END))]), xyz[[i for i, a in enumerate(atoms) if a == "Ti"]])
    ip2_host_com = pair_min(com(atoms, xyz, range(EMIM2_START, IP2_END))[None, :], host)

    lines = [f"[{name}]\\n", "Index  Element  Dist_to_host_or_IP1_min(A)\\n"]
    for i, d in enumerate(d_ip2_host, start=IP2_START + 1):
        atom = atoms[i - 1]
        nearest_host_idx = int(host_idx[i - IP2_START]) + 1
        lines.append(f"{i:5d} {atom:>2} {d:10.5f} nearest_host_or_ip1={nearest_host_idx:4d}\\n")
    lines.append(f"2nd EMIM COM - nearest Ti = {emim2_ti_min:.6f} A\\n")
    lines.append(f"min(2nd EMIM, 2nd TFSI) = {emim2_min:.6f} A (emim#{EMIM2_START + emim_idx + 1}, tfsi#{TFSI2_START + tfsi_idx + 1})\\n")
    lines.append(f"min(2nd IP COM, host 1-102) = {ip2_host_com:.6f} A\\n")

    # keep summary for comparison
    summary = {
        "ip2_to_host_min": float(d_ip2_host.min()) if len(d_ip2_host) else float("nan"),
        "emim_to_ti_min": float(emim2_ti_min) if np.isfinite(emim2_ti_min) else float("nan"),
        "emim_tfsi_min": float(emim2_min),
    }
    return lines, summary


def main():
    out_lines: list[str] = []
    stats: dict[str, dict[str, float]] = {}
    for name in ("cluster", "dissociate"):
        lines, st = section(name)
        out_lines.extend(lines)
        out_lines.append("\\n")
        stats[name] = st

    out_lines.append("Comparison\\n")
    out_lines.append(
        f"2nd IP->host+IP1 min: cluster={stats['cluster']['ip2_to_host_min']:.4f}, dissociate={stats['dissociate']['ip2_to_host_min']:.4f}\\n"
    )
    out_lines.append(
        f"2nd EMIM-TFSI min: cluster={stats['cluster']['emim_tfsi_min']:.4f}, dissociate={stats['dissociate']['emim_tfsi_min']:.4f}\\n"
    )
    out_lines.append(
        f"2nd EMIM nearest Ti: cluster={stats['cluster']['emim_to_ti_min']:.4f}, dissociate={stats['dissociate']['emim_to_ti_min']:.4f}\\n"
    )

    OUT.write_text("".join(out_lines), encoding="utf-8")
    print(f"WROTE: {OUT}")


if __name__ == "__main__":
    main()
