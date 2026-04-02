#!/usr/bin/env python3
"""export_visualization.py
Export color-annotated XYZ and cell-based files for VESTA/VMD.
"""

from __future__ import annotations

from pathlib import Path
import math
import numpy as np

BASE = Path("/mnt/d/PSID_BAMOF/try04/02_calculations")
FILEMAP = {
    "cluster": BASE / "BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz",
    "dissociate": BASE / "BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz",
}
CELL = np.array(
    [
        [16.000, -0.557, 0.090],
        [-6.517, 14.613, -0.057],
        [-4.635, -7.066, 13.095],
    ],
    dtype=float,
)

MOF_END = 124
IP1_END = 158

COLORS = {
    "mof": "0.65 0.65 0.65",
    "ip1": "0.12 0.32 1.00",
    "ip2": "1.00 0.20 0.20",
}


def read_xyz(path: Path):
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = int(lines[0])
    atoms = []
    for row in lines[2 : 2 + n]:
        p = row.split()
        atoms.append((p[0], float(p[1]), float(p[2]), float(p[3])))
    return atoms


def role(i: int) -> str:
    if i < MOF_END:
        return "mof"
    if i < IP1_END:
        return "ip1"
    return "ip2"


def write_visual_xyz(path: Path, atoms):
    out = path.with_name(path.stem + "_visual.xyz")
    with out.open("w", encoding="utf-8") as f:
        f.write(f"{len(atoms)}\\n")
        f.write("MOF=gray, IP1=blue, IP2=red\\n")
        for i, (el, x, y, z) in enumerate(atoms):
            c = COLORS[role(i)]
            f.write(f"{el} {x:.10f} {y:.10f} {z:.10f}  # color={c} role={role(i)}\\n")
    return out


def cell_lengths_and_angles():
    a, b, c = CELL
    la = float(np.linalg.norm(a))
    lb = float(np.linalg.norm(b))
    lc = float(np.linalg.norm(c))
    alpha = math.degrees(math.acos(float(np.dot(b, c) / (lb * lc))))
    beta = math.degrees(math.acos(float(np.dot(a, c) / (la * lc))))
    gamma = math.degrees(math.acos(float(np.dot(a, b) / (la * lb))))
    return la, lb, lc, alpha, beta, gamma


def write_cell_cif(path: Path):
    out = path.with_name(path.stem + "_cell.cif")
    la, lb, lc, alpha, beta, gamma = cell_lengths_and_angles()
    with out.open("w", encoding="utf-8") as f:
        f.write("data_try04_structure\\n")
        f.write(f"_cell_length_a    {la:.6f}\\n")
        f.write(f"_cell_length_b    {lb:.6f}\\n")
        f.write(f"_cell_length_c    {lc:.6f}\\n")
        f.write(f"_cell_angle_alpha  {alpha:.6f}\\n")
        f.write(f"_cell_angle_beta   {beta:.6f}\\n")
        f.write(f"_cell_angle_gamma  {gamma:.6f}\\n")
    return out


def write_poscar(path: Path, atoms):
    out = path.with_name(path.stem + "_POSCAR.vasp")
    inv = np.linalg.inv(CELL)
    symbols = [a for a, *_ in atoms]
    uniq = []
    counts = []
    for s in symbols:
        if s not in uniq:
            uniq.append(s)
            counts.append(1)
        else:
            counts[uniq.index(s)] += 1
    xyz = np.array([[x, y, z] for _, x, y, z in atoms], dtype=float)
    frac = xyz @ inv.T

    with out.open("w", encoding="utf-8") as f:
        f.write("try04_2IP\\n1.0\\n")
        for v in CELL:
            f.write(f"{v[0]:18.10f} {v[1]:18.10f} {v[2]:18.10f}\\n")
        f.write(" ".join(uniq) + "\\n")
        f.write(" ".join(str(c) for c in counts) + "\\n")
        f.write("Direct\\n")
        for x, y, z in frac:
            f.write(f"{x:.10f} {y:.10f} {z:.10f}\\n")
    return out


def main():
    for _, p in FILEMAP.items():
        atoms = read_xyz(p)
        v = write_visual_xyz(p, atoms)
        c = write_cell_cif(p)
        pcar = write_poscar(p, atoms)
        print(f"[{p.name}] -> {v.name}, {c.name}, {pcar.name}")


if __name__ == "__main__":
    main()
