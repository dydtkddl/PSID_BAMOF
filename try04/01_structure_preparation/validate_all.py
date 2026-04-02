#!/usr/bin/env python3
"""validate_all.py ? ??? 2-IP ??? ??? ??? ??"""

from collections import Counter
from pathlib import Path
import numpy as np

BASE = Path('/mnt/d/PSID_BAMOF/try04/02_calculations')
FILES = {
    'cluster': BASE / 'BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz',
    'dissociate': BASE / 'BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz',
}
INPUTS = {
    'cluster': BASE / 'BAMOF_2IP_cluster/input.inp',
    'dissociate': BASE / 'BAMOF_2IP_dissociate/input.inp',
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
IP1_START = 125
IP1_END = 158
IP2_START = 159
IP2_END = 192
IP2_EMIM_START = 159
IP2_EMIM_END = 177
IP2_TFSI_START = 178
IP2_TFSI_END = 192


def read_xyz(path: Path):
    lines = path.read_text().splitlines()
    n = int(lines[0].strip())
    atoms = []
    coords = []
    for i in range(2, 2 + n):
        vals = lines[i].split()
        atoms.append(vals[0])
        coords.append([float(v) for v in vals[1:4]])
    return atoms, np.array(coords, dtype=float)


def parse_input(path: Path):
    kinds = []
    coord = None
    for line in path.read_text().splitlines():
        s = line.strip()
        if s.startswith('&KIND'):
            parts = s.split()
            if len(parts) >= 2:
                kinds.append(parts[1])
        elif s.startswith('COORD_FILE_NAME'):
            parts = s.split()
            if len(parts) >= 2:
                coord = parts[1]
    return sorted(set(kinds)), coord


def nearest(a, b):
    if len(a) == 0 or len(b) == 0:
        return np.array([]), np.array([])
    d = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    return d.min(axis=1), d


def check_group(name):
    atoms, coords = read_xyz(FILES[name])
    kinds, coord_name = parse_input(INPUTS[name])

    labels = []

    # 1
    ok1 = len(atoms) == 192
    labels.append((1, ok1, f'atoms={len(atoms)}'))

    # 2
    expected = Counter({'Ti': 8, 'H': 56, 'C': 62, 'N': 10, 'O': 40, 'F': 12, 'S': 4})
    got = Counter(atoms)
    ok2 = got == expected
    labels.append((2, ok2, f'counts={dict(got)}'))

    # 3
    _, d_all = nearest(coords, coords)
    if d_all.size:
        d_nodiag = d_all[np.triu_indices(len(coords), k=1)]
        min_all = float(d_nodiag.min())
    else:
        min_all = float('inf')
    labels.append((3, min_all > 0.8, f'min_all={min_all:.4f}'))

    mof = coords[:MOF_END]
    ip1 = coords[IP1_START - 1: IP1_END]
    ip2 = coords[IP2_START - 1: IP2_END]
    ip2_emim = coords[IP2_EMIM_START - 1: IP2_EMIM_END]
    ip2_tfsi = coords[IP2_TFSI_START - 1: IP2_TFSI_END]

    # 4
    _, d4 = nearest(ip2, np.vstack((mof, ip1)))
    m4 = float(d4.min())
    labels.append((4, m4 > 1.5, f'min_MOF+IP1_to_IP2={m4:.4f}'))

    # 5
    _, d5 = nearest(ip1, ip2)
    m5 = float(d5.min())
    labels.append((5, m5 > 2.0, f'min_IP1_to_IP2={m5:.4f}'))

    # 6/7
    _, d6 = nearest(ip2_emim, ip2_tfsi)
    m6 = float(d6.min())
    if name == 'cluster':
        labels.append((6, m6 < 4.0, f'cluster_IP2_EMIM_TFSI_min={m6:.4f}'))
    else:
        labels.append((7, m6 > 5.0, f'dissociate_IP2_EMIM_TFSI_min={m6:.4f}'))

    # 8 - fractional wrapping compatibility
    frac = coords @ np.linalg.inv(CELL.T)
    frac_wrapped = np.mod(frac, 1.0)
    ok8 = np.all((frac_wrapped >= -1e-8) & (frac_wrapped < 1.0 + 1e-8))
    labels.append((8, ok8, f'wrapped_frac_sample={frac_wrapped[0].tolist() if len(frac_wrapped) else []}'))

    # 9
    ok9 = coord_name is not None and coord_name == FILES[name].name
    labels.append((9, ok9, f'coord_file={coord_name}'))

    # 10
    uniq = set(atoms)
    miss = sorted(uniq.difference(kinds))
    labels.append((10, len(miss) == 0, f'missing_KIND={miss}'))

    # additional 11/12
    emim_counts = Counter(atoms[IP2_EMIM_START - 1:IP2_EMIM_END])
    tfsi_counts = Counter(atoms[IP2_TFSI_START - 1:IP2_TFSI_END])
    ok11 = emim_counts == Counter({'N': 2, 'C': 6, 'H': 11})
    ok12 = tfsi_counts == Counter({'N': 1, 'C': 2, 'O': 4, 'F': 6, 'S': 2})
    labels.append((11, ok11, f'2nd_EMIM_counts={dict(emim_counts)}'))
    labels.append((12, ok12, f'2nd_TFSI_counts={dict(tfsi_counts)}'))

    all_ok = all(v[1] for v in labels)
    print(f'[{name}] {"PASS" if all_ok else "FAIL"}')
    for n, ok, detail in labels:
        print(('PASS' if ok else 'FAIL').ljust(4), f'{n:02d}) {detail}')
    if not all_ok:
        print('FAILED items:')
        for n, ok, detail in labels:
            if not ok:
                print(f' - {n:02d} {detail}')


def main():
    for key in ('cluster', 'dissociate'):
        check_group(key)


if __name__ == '__main__':
    main()
