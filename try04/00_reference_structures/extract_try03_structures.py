#!/usr/bin/env python3
"""extract_try03_structures.py
Extract final frames from try03 trajectories and compare with try04 base fragments.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np

ROOT = Path("/mnt/d/PSID_BAMOF")
TRY04 = ROOT / "try04"
OUT = TRY04 / "00_reference_structures"

SRC = {
    "BAMOF_1IP_cluster": ROOT / "try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/BAMOF_EMIM_TFSI_Cluster-pos-1.xyz",
    "BAMOF_1IP_dissociate": ROOT / "try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_dissociate-1/BAMOF_EMIM_TFSI_dissociate-pos-1.xyz",
    "EMIMTFSI_gasphase": ROOT / "try03/00_ionic_structure_cp2k/Cluster01/Cluster-pos-1.xyz",
}


def parse_trajectory_frames(path: Path):
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    n = int(lines[0])
    block = n + 2
    frames = []
    for i in range(0, len(lines), block):
        chunk = lines[i : i + block]
        if len(chunk) < block:
            break
        atoms = []
        xyz = []
        for row in chunk[2:]:
            p = row.split()
            atoms.append(p[0])
            xyz.append([float(p[1]), float(p[2]), float(p[3])])
        frames.append((atoms, np.array(xyz, dtype=float)))
    return frames


def write_xyz(path: Path, atoms, xyz):
    with path.open("w", encoding="utf-8") as f:
        f.write(f"{len(atoms)}\\n")
        f.write("auto extracted final frame\\n")
        for a, (x, y, z) in zip(atoms, xyz):
            f.write(f"{a} {x:.8f} {y:.8f} {z:.8f}\\n")


def rmsd(a: np.ndarray, b: np.ndarray):
    if a.shape != b.shape or len(a) == 0:
        return float("nan")
    return float(np.sqrt(((a - b) ** 2).sum(axis=1).mean()))


def main():
    OUT.mkdir(exist_ok=True)
    extracted = {}
    for name, p in SRC.items():
        if not p.exists():
            print(f"missing: {p}")
            continue
        frames = parse_trajectory_frames(p)
        if not frames:
            print(f"no frames: {p}")
            continue
        atoms, xyz = frames[-1]
        out = OUT / f"{name}_final.xyz"
        write_xyz(out, atoms, xyz)
        extracted[name] = (atoms, xyz)
        print(f"SAVED: {out}")

    # compare with try04 base fragments if available
    comp = []
    c_path = TRY04 / "02_calculations/BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz"
    d_path = TRY04 / "02_calculations/BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz"
    if "BAMOF_1IP_cluster" in extracted and c_path.exists():
        lines = [line.strip() for line in c_path.read_text().splitlines() if line.strip()]
        n = int(lines[0])
        c_atoms, c_xyz = [], []
        for row in lines[2 : 2 + 124]:
            p = row.split()
            c_atoms.append(p[0])
            c_xyz.append([float(v) for v in p[1:4]])
        r = rmsd(np.array(c_xyz), extracted["BAMOF_1IP_cluster"][1][:124])
        comp.append(f"Cluster fragment RMSD vs try04 base[1:124]: {r:.6f}\\n")
    if "BAMOF_1IP_dissociate" in extracted and d_path.exists():
        lines = [line.strip() for line in d_path.read_text().splitlines() if line.strip()]
        n = int(lines[0])
        d_atoms, d_xyz = [], []
        for row in lines[2 : 2 + 124]:
            p = row.split()
            d_atoms.append(p[0])
            d_xyz.append([float(v) for v in p[1:4]])
        r = rmsd(np.array(d_xyz), extracted["BAMOF_1IP_dissociate"][1][:124])
        comp.append(f"Dissociate fragment RMSD vs try04 base[1:124]: {r:.6f}\\n")

    rpt = OUT / "structure_comparison.txt"
    if comp:
        rpt.write_text("# Structure comparison\\n" + "".join(comp), encoding="utf-8")
        print(f"SAVED: {rpt}")
    else:
        print("No comparison generated")


if __name__ == "__main__":
    main()
