#!/usr/bin/env python3
"""track_ion_distance.py
Track 2nd IP EMIM-TFSI distance descriptors from GEO_OPT trajectory.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, List, Tuple


MASS = {
    "H": 1.008,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "F": 18.998,
    "S": 32.06,
    "Ti": 47.867,
    "Al": 26.982,
    "Zn": 65.38,
}


def read_frames(path: Path) -> List[Tuple[List[str], List[Tuple[float, float, float]]]]:
    lines = path.read_text().splitlines()
    if not lines:
        return []
    nat = int(lines[0].strip())
    step = nat + 2
    frames = []
    for i in range(0, len(lines), step):
        block = lines[i : i + step]
        if len(block) < step:
            break
        atoms = block[2:]
        symbols = []
        coords = []
        for row in atoms:
            parts = row.split()
            if len(parts) < 4:
                continue
            symbols.append(parts[0])
            coords.append((float(parts[1]), float(parts[2]), float(parts[3])))
        frames.append((symbols, coords))
    return frames


def distance(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def com(atoms: List[Tuple[float, float, float]], symbols: List[str], idx: List[int]) -> Tuple[float, float, float]:
    s = 0.0
    wx = wy = wz = 0.0
    for i in idx:
        e = symbols[i]
        m = MASS.get(e, 1.0)
        x, y, z = atoms[i]
        s += m
        wx += x * m
        wy += y * m
        wz += z * m
    return (wx / s, wy / s, wz / s)


def min_pair_distance(coords_a: List[Tuple[float, float, float]], coords_b: List[Tuple[float, float, float]]) -> float:
    best = 1.0e9
    for a in coords_a:
        for b in coords_b:
            d = distance(a, b)
            if d < best:
                best = d
    return best


def classify_emim_tfsi(symbols: List[str], idx: List[int]) -> Tuple[List[int], List[int]]:
    emim = []
    tfsi = []
    for i in idx:
        s = symbols[i]
        if s in {"F", "S", "O"}:
            tfsi.append(i)
        elif s == "N":
            emim.append(i)
        elif s == "C":
            # in ambiguous cases, send C to EMIM until C count reaches typical 8
            emim.append(i)
        else:
            emim.append(i)
    if not emim or not tfsi:
        n = len(idx)
        emim = idx[: n // 2]
        tfsi = idx[n // 2 :]
    return emim, tfsi


def analyze_file(path: Path) -> List[Tuple[int, float, float, float]]:
    frames = read_frames(path)
    if not frames:
        return []
    out: List[Tuple[int, float, float, float]] = []
    for fidx, (symbols, coords) in enumerate(frames):
        # atoms are 1-based in our convention
        mof = list(range(0, 102))
        ip1 = list(range(102, 158))
        ip2 = list(range(158, 192))
        emim, tfsi = classify_emim_tfsi(symbols, ip2)
        emim_coords = [coords[i] for i in emim]
        tfsi_coords = [coords[i] for i in tfsi]
        cross2_to_rest = min_pair_distance([coords[i] for i in ip2], [coords[i] for i in mof + ip1])
        emim_com = com(coords, symbols, emim)
        tfsi_com = com(coords, symbols, tfsi)
        emim_tfsi_min = min_pair_distance(emim_coords, tfsi_coords)
        # warning logic
        out.append((fidx, cross2_to_rest, distance(emim_com, tfsi_com), emim_tfsi_min))
    return out


def write_table(path: Path, rows: List[Tuple[int, float, float, float]]) -> None:
    with path.open("w") as f:
        f.write("step,cross_mof_ip1_min,emim_tfsi_com_dist,emim_tfsi_min_dist\n")
        for r in rows:
            f.write(f"{r[0]},{r[1]:.6f},{r[2]:.6f},{r[3]:.6f}\n")


def run(args: argparse.Namespace) -> None:
    rows_cluster = analyze_file(Path(args.cluster))
    rows_diss = analyze_file(Path(args.diss))
    if rows_cluster:
        write_table(Path("D:/PSID_BAMOF/try04/03_postprocessing/track_cluster.csv"), rows_cluster)
        last = rows_cluster[-1][3]
        print(f"cluster final emim-tfsi min distance = {last:.4f} Å")
        if last > 5.0:
            print("WARNING: cluster shows IP2 separation >5.0 Å.")
    if rows_diss:
        write_table(Path("D:/PSID_BAMOF/try04/03_postprocessing/track_dissociate.csv"), rows_diss)
        last = rows_diss[-1][3]
        print(f"dissociate final emim-tfsi min distance = {last:.4f} Å")
        if last < 4.0:
            print("WARNING: dissociate trajectory shows recombination (distance < 4.0 Å).")

    if rows_cluster and rows_diss and len(rows_cluster) == len(rows_diss):
        import matplotlib.pyplot as plt

        steps = [x[0] for x in rows_cluster]
        cl = [x[1] for x in rows_cluster]
        ds = [x[1] for x in rows_diss]
        plt.figure()
        plt.plot(steps, cl, label="cluster: IP2 to MOF+IP1")
        plt.plot(steps, ds, label="dissociate: IP2 to MOF+IP1")
        plt.xlabel("step")
        plt.ylabel("distance (Å)")
        plt.legend()
        plt.tight_layout()
        plt.savefig("D:/PSID_BAMOF/try04/03_postprocessing/track_ip2_distance.png")

        steps2 = [x[0] for x in rows_cluster]
        plt.figure()
        plt.plot(steps2, [x[3] for x in rows_cluster], label="cluster emim-tfsi")
        plt.plot(steps2, [x[3] for x in rows_diss], label="dissociate emim-tfsi")
        plt.legend()
        plt.xlabel("step")
        plt.ylabel("min distance (Å)")
        plt.tight_layout()
        plt.savefig("D:/PSID_BAMOF/try04/03_postprocessing/track_emim_tfsi_distance.png")

    print("Saved: track_cluster.csv / track_dissociate.csv and PNG summaries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", default="D:/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster/BAMOF_2IP_cluster-pos-1.xyz")
    parser.add_argument("--diss", default="D:/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate/BAMOF_2IP_dissociate-pos-1.xyz")
    args = parser.parse_args()
    run(args)
