#!/usr/bin/env python3
"""export_final.py
Export final frame from trajectory and generate XYZ/CIF/POSCAR/MOL2 and SI table.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import math
import re

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CALC = ROOT / "02_calculations"
OUT = Path(__file__).resolve().parent / "final_structures"
OUT.mkdir(exist_ok=True)

MOF_FIXED = set(range(0, 102))
MOF_UNFIXED = set(range(102, 124))
IP1_EMIM = set(range(124, 143))
IP1_TFSI = set(range(143, 158))
IP2_EMIM = set(range(158, 177))
IP2_TFSI = set(range(177, 192))

COV_RAD = {"H": 0.31, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57, "S": 1.05, "Ti": 1.47}


def parse_xyz(path: Path):
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    n = int(lines[0])
    atoms = []
    coords = []
    for row in lines[2:2 + n]:
        p = row.split()
        atoms.append(p[0])
        coords.append([float(p[1]), float(p[2]), float(p[3])])
    return atoms, np.array(coords, dtype=float)


def parse_frames(path: Path):
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        return []
    n = int(lines[0])
    block = n + 2
    frames = []
    for i in range(0, len(lines), block):
        chunk = lines[i : i + block]
        if len(chunk) < block:
            break
        atoms = []
        coords = []
        for row in chunk[2:]:
            p = row.split()
            atoms.append(p[0])
            coords.append([float(p[1]), float(p[2]), float(p[3])])
        frames.append((atoms, np.array(coords, dtype=float)))
    return frames


def write_xyz(path: Path, atoms, xyz):
    with path.open("w", encoding="utf-8") as f:
        f.write(f"{len(atoms)}\\n")
        f.write("try04 final frame\\n")
        for a, (x, y, z) in zip(atoms, xyz):
            f.write(f"{a} {x:.8f} {y:.8f} {z:.8f}\\n")


def parse_cell_from_input(inp: Path):
    a = b = c = None
    if not inp.exists():
        return None
    in_cell = False
    for line in inp.read_text(errors="ignore").splitlines():
        s = line.strip()
        if s.startswith("&CELL"):
            in_cell = True
            continue
        if in_cell:
            if s.startswith("&END"):
                break
            if s.startswith("A "):
                a = [float(v) for v in s.split()[1:4]]
            elif s.startswith("B "):
                b = [float(v) for v in s.split()[1:4]]
            elif s.startswith("C "):
                c = [float(v) for v in s.split()[1:4]]
    if a is None or b is None or c is None:
        return None
    return np.array([a, b, c], dtype=float)


def write_poscar(path: Path, atoms, xyz, cell):
    with path.open("w", encoding="utf-8") as f:
        f.write("try04 final structure\\n1.0\\n")
        for v in cell:
            f.write(f"{v[0]:.10f} {v[1]:.10f} {v[2]:.10f}\\n")
        uniq = []
        counts = []
        for a in atoms:
            if a not in uniq:
                uniq.append(a)
                counts.append(1)
            else:
                counts[uniq.index(a)] += 1
        f.write(" ".join(uniq) + "\\n")
        f.write(" ".join(str(c) for c in counts) + "\\n")
        f.write("Cartesian\\n")
        for x, y, z in xyz:
            f.write(f"{x:.8f} {y:.8f} {z:.8f}\\n")


def write_cif(path: Path, atoms, xyz, cell):
    import math

    a, b, c = cell
    inv = np.linalg.inv(cell)
    frac = xyz @ inv.T
    la = float(np.linalg.norm(a))
    lb = float(np.linalg.norm(b))
    lc = float(np.linalg.norm(c))
    alpha = math.degrees(math.acos(float(np.dot(b, c) / (lb * lc))))
    beta = math.degrees(math.acos(float(np.dot(a, c) / (la * lc))))
    gamma = math.degrees(math.acos(float(np.dot(a, b) / (la * lb))))
    with path.open("w", encoding="utf-8") as f:
        f.write("data_try04_final\\n")
        f.write("_symmetry_space_group_name_H-M   'P1'\\n")
        f.write(f"_cell_length_a   {la:.6f}\\n")
        f.write(f"_cell_length_b   {lb:.6f}\\n")
        f.write(f"_cell_length_c   {lc:.6f}\\n")
        f.write(f"_cell_angle_alpha {alpha:.6f}\\n")
        f.write(f"_cell_angle_beta  {beta:.6f}\\n")
        f.write(f"_cell_angle_gamma {gamma:.6f}\\n")
        f.write("loop_\\n")
        f.write("_atom_site_label\\n_atom_site_type_symbol\\n_atom_site_fract_x\\n_atom_site_fract_y\\n_atom_site_fract_z\\n")
        for i, (el, r) in enumerate(zip(atoms, frac), start=1):
            f.write(f"{el}{i} {el} {r[0]:.8f} {r[1]:.8f} {r[2]:.8f}\\n")


def bond_pairs(xyz, atoms, scale=1.25):
    pairs = []
    for i in range(len(xyz)):
        x1 = xyz[i]
        r1 = COV_RAD.get(atoms[i], 0.77)
        for j in range(i + 1, len(xyz)):
            d = float(np.linalg.norm(xyz[i] - xyz[j]))
            r2 = COV_RAD.get(atoms[j], 0.77)
            if d <= scale * (r1 + r2):
                pairs.append((i + 1, j + 1, d))
    return pairs


def write_mol2(path: Path, atoms, xyz):
    pairs = bond_pairs(xyz, atoms)
    with path.open("w", encoding="utf-8") as f:
        f.write("@<TRIPOS>MOLECULE\\n")
        f.write("try04_final\\n")
        f.write(f"{len(atoms)} {len(pairs)} 0 0 0\\nSMALL\\nNO_CHARGES\\n")
        f.write("@<TRIPOS>ATOM\\n")
        for i, (el, (x, y, z)) in enumerate(zip(atoms, xyz), start=1):
            f.write(f"{i:7d} {el}{i:<4} {el:>2} {x:10.4f} {y:10.4f} {z:10.4f} 0 {el} 0.0000\\n")
        f.write("@<TRIPOS>BOND\\n")
        for k, (i, j, _) in enumerate(pairs, start=1):
            f.write(f"{k:6d} {i:5d} {j:5d} 1\\n")


def role_of(idx: int) -> str:
    if idx in MOF_FIXED:
        return "MOF-fixed"
    if idx in MOF_UNFIXED:
        return "MOF-unfixed"
    if idx in IP1_EMIM:
        return "IP1-EMIM"
    if idx in IP1_TFSI:
        return "IP1-TFSI"
    if idx in IP2_EMIM:
        return "IP2-EMIM"
    if idx in IP2_TFSI:
        return "IP2-TFSI"
    return "UNKNOWN"


def write_si_table(path: Path, atoms, xyz):
    with path.open("w", encoding="utf-8") as f:
        f.write("| Atom | Element | x | y | z | Role |\\n")
        f.write("|---|---|---|---|---|---|\\n")
        for i, (el, (x, y, z)) in enumerate(zip(atoms, xyz), start=1):
            f.write(f"| {i} | {el} | {x:.6f} | {y:.6f} | {z:.6f} | {role_of(i-1)} |\\n")


def process(case: str):
    case_dir = CALC / case
    traj = case_dir / f"{case}-pos-1.xyz"
    if not traj.exists():
        print(f"missing trajectory: {traj}")
        return

    frames = parse_frames(traj)
    if not frames:
        print(f"empty trajectory: {traj}")
        return

    atoms, xyz = frames[-1]
    cell = parse_cell_from_input(case_dir / "input.inp")
    if cell is None:
        cell = np.array(
            [
                [16.000, -0.557, 0.090],
                [-6.517, 14.613, -0.057],
                [-4.635, -7.066, 13.095],
            ],
            dtype=float,
        )

    base = OUT / case
    write_xyz(base.with_suffix(".xyz"), atoms, xyz)
    write_poscar(base.with_suffix(".POSCAR.vasp"), atoms, xyz, cell)
    write_cif(base.with_suffix(".cif"), atoms, xyz, cell)
    write_mol2(base.with_suffix(".mol2"), atoms, xyz)
    write_si_table(base.with_suffix("_si_table.md"), atoms, xyz)
    print(f"WROTE: {base}.* and table")


def main():
    for case in ("BAMOF_2IP_cluster", "BAMOF_2IP_dissociate"):
        process(case)


if __name__ == "__main__":
    main()
