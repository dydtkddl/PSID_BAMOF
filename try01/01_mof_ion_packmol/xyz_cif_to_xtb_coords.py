#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xyz2xtbcoord.py
  usage: python xyz2xtbcoord.py <cell.cif> <coords.xyz> [out.coord]

  · CIF  : 유닛셀 파라미터(a, b, c, α, β, γ) 읽기
  · XYZ  : 원소·카르테시안 좌표(Å) 읽기
  → Turbomole '$coord / $periodic 3 / $cell' 형식으로 저장
"""

import sys
import numpy as np
from ase.io import read

# ------------------------------------------------------------
def read_xyz(path):
    with open(path) as f:
        n = int(f.readline())
        f.readline()            # comment
        labels, coords = [], []
        for _ in range(n):
            lab, x, y, z, *_ = f.readline().split()
            labels.append(lab)
            coords.append([float(x), float(y), float(z)])
    return labels, np.array(coords, float)

def write_xtb_coord(path, labels, coords, cell):
    a, b, c = cell.lengths()
    alpha, beta, gamma = cell.angles()

    with open(path, 'w') as f:
        f.write("$coord angs\n")
        for (x, y, z), lab in zip(coords, labels):
            f.write(f" {x:15.6f} {y:15.6f} {z:15.6f}  {lab}\n")
        f.write("$periodic 3\n")
        f.write("$cell angs\n")
        f.write(f" {a:.6f} {b:.6f} {c:.6f}  {alpha:.3f} {beta:.3f} {gamma:.3f}\n")
        f.write("$end\n")
    print(f"[✓] Turbomole coord 저장 → {path}")

# ------------------------------------------------------------
def main():
    if len(sys.argv) not in (3, 4):
        sys.exit("usage: python xyz2xtbcoord.py <cell.cif> <coords.xyz> [out.coord]")

    cif_path, xyz_path = sys.argv[1], sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) == 4 else "xtb.coord"

    # 1) CIF → Cell
    cell = read(cif_path).get_cell()

    # 2) XYZ → labels, coords
    labels, coords = read_xyz(xyz_path)

    # 3) Write Turbomole coord
    write_xtb_coord(out_path, labels, coords, cell)

if __name__ == "__main__":
    main()

