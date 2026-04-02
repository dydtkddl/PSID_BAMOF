#!/usr/bin/env python3
"""export_visualization.py - create visualization-ready files"""
from pathlib import Path
import numpy as np

CELL = {
    'A': [16.000, -0.557, 0.090],
    'B': [-6.517, 14.613, -0.057],
    'C': [-4.635, -7.066, 13.095],
}

BASE = Path('/mnt/d/PSID_BAMOF/try04/02_calculations')
FILEMAP = {
    'cluster': BASE / 'BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz',
    'dissociate': BASE / 'BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz',
}

ROLE_MAP = {
    'mof': '0.65 0.65 0.65',
    'ip1': '0.10 0.30 1.00',
    'ip2': '1.00 0.15 0.15',
}


def read_xyz(path):
    lines = path.read_text().splitlines()
    n = int(lines[0])
    atoms = []
    for i in range(2, 2 + n):
        p = lines[i].split()
        atoms.append((p[0], float(p[1]), float(p[2]), float(p[3])))
    return atoms


def atom_role(i):
    if i < 124:
        return 'mof'
    if i < 158:
        return 'ip1'
    return 'ip2'


def save_color_xyz(path, atoms):
    out = path.with_name(path.stem + '_visual.xyz')
    with out.open('w') as f:
        f.write(f'{len(atoms)}\n')
        f.write('colored xyz for VESTA (mof=gray, ip1=blue, ip2=red)\n')
        for i, (e, x, y, z) in enumerate(atoms):
            role = atom_role(i)
            color = ROLE_MAP[role]
            f.write(f'{e} {x:.10f} {y:.10f} {z:.10f}  # color={color} role={role}\n')
    return out


def save_cell(path):
    out = path.with_name(path.stem + '_cell.cif')
    with out.open('w') as f:
        f.write('data_cell\n')
        f.write('_cell_length_a    16.000\n')
        f.write('_cell_length_b    16.000\n')
        f.write('_cell_length_c    16.000\n')
        f.write('_cell_angle_alpha 90.00\n')
        f.write('_cell_angle_beta  90.00\n')
        f.write('_cell_angle_gamma 90.00\n')
    return out


def save_poscar(path):
    out = path.with_name(path.stem + '_POSCAR.vasp')
    atoms = read_xyz(path)
    symbols = [a[0] for a in atoms]
    uniq = []
    counts = []
    for s in ['Ti', 'H', 'C', 'N', 'O', 'F', 'S']:
        c = symbols.count(s)
        if c:
            uniq.append(s)
            counts.append(c)

    with out.open('w') as f:
        f.write(f'{path.name}\n1.0\n')
        for k in ('A', 'B', 'C'):
            f.write(f"{CELL[k][0]:20.10f} {CELL[k][1]:20.10f} {CELL[k][2]:20.10f}\n")
        f.write(' '.join(uniq) + '\n')
        f.write(' '.join(str(c) for c in counts) + '\n')
        f.write('Direct\n')
        mat = np.array([CELL['A'], CELL['B'], CELL['C']], dtype=float).T
        inv = np.linalg.inv(mat)
        for e, x, y, z in atoms:
            fx, fy, fz = inv @ np.array([x, y, z], dtype=float)
            f.write(f'{fx: .10f} {fy: .10f} {fz: .10f} # {e}\n')
    return out


def main():
    for _, p in FILEMAP.items():
        atoms = read_xyz(p)
        o1 = save_color_xyz(p, atoms)
        o2 = save_cell(p)
        o3 = save_poscar(p)
        print(f'[{p.name}] -> {o1.name}, {o2.name}, {o3.name}')


if __name__ == '__main__':
    main()
