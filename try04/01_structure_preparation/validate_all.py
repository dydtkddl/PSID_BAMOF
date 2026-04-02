#!/usr/bin/env python3
"""validate_all.py
Validate 2-IP structures for try04.

Checks:
1. total atoms = 192
2. element counts
3. minimum interatomic distance > 0.8 A
4. MOF(1-102) to 2nd IP minimum distance > 1.5 A
5. 1st IP to 2nd IP minimum distance > 2.0 A
6. cluster: 2nd EMIM-TFSI minimum distance < 4.0 A
7. dissociate: 2nd EMIM-TFSI minimum distance > 5.0 A
8. periodic cell compatibility
9. COORD_FILE_NAME matches target xyz name
10. KIND list covers all symbols in XYZ
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import numpy as np

BASE = Path("/mnt/d/PSID_BAMOF/try04/02_calculations")
CELL = np.array(
    [
        [16.000, -0.557, 0.090],
        [-6.517, 14.613, -0.057],
        [-4.635, -7.066, 13.095],
    ],
    dtype=float,
)

FILES = {
    "cluster": BASE / "BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz",
    "dissociate": BASE / "BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz",
}
INPUTS = {
    "cluster": BASE / "BAMOF_2IP_cluster/input.inp",
    "dissociate": BASE / "BAMOF_2IP_dissociate/input.inp",
}

EXPECTED_COUNTS = Counter({"Ti": 8, "H": 56, "C": 62, "N": 10, "O": 40, "F": 12, "S": 4})

MOF_HOST_END = 102
IP1_START = 124
IP1_END = 158
IP2_START = 158
IP2_END = 192
EMIM2_START = 158
EMIM2_END = 177
TFSI2_START = 177
TFSI2_END = 192


def read_xyz(path: Path):
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = int(lines[0])
    atoms = []
    coords = []
    for row in lines[2 : 2 + n]:
        p = row.split()
        atoms.append(p[0])
        coords.append([float(v) for v in p[1:4]])
    return atoms, np.array(coords, dtype=float)


def parse_input(path: Path):
    kinds = set()
    coord_name = None
    in_kind = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s.startswith("&KIND"):
            in_kind = True
            parts = s.split()
            if len(parts) >= 2:
                kinds.add(parts[1])
            continue
        if in_kind and s.startswith("&END"):
            in_kind = False
            continue
        if s.startswith("COORD_FILE_NAME"):
            m = re.match(r"COORD_FILE_NAME\\s+(\\S+)", s)
            if m:
                coord_name = m.group(1)
    return kinds, coord_name


def pair_min(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    d = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    return float(d.min())


def check(name: str):
    atoms, xyz = read_xyz(FILES[name])
    kinds, coord_name = parse_input(INPUTS[name])

    checks = []

    # 1) atom count
    ok = len(atoms) == 192
    checks.append((1, ok, f"atoms={len(atoms)}"))

    # 2) element counts
    got = Counter(atoms)
    ok = got == EXPECTED_COUNTS
    checks.append((2, ok, f"counts={dict(got)}"))

    # 3) minimum distance
    dmat = np.linalg.norm(xyz[:, None, :] - xyz[None, :, :], axis=2)
    tri = np.triu(np.ones_like(dmat, dtype=bool), 1)
    min_all = float(dmat[tri].min())
    checks.append((3, min_all > 0.8, f"min_all={min_all:.4f}"))

    # 4) MOF(1-102) to IP2
    host = xyz[:MOF_HOST_END]
    ip1 = xyz[IP1_START:IP1_END]
    ip2 = xyz[IP2_START:IP2_END]
    m4 = pair_min(ip2, host)
    checks.append((4, m4 > 1.5, f"min_MOF1to102_IP2={m4:.4f}"))

    # 5) IP1 to IP2
    m5 = pair_min(ip1, ip2)
    checks.append((5, m5 > 2.0, f"min_IP1_IP2={m5:.4f}"))

    # 6/7) 2nd EMIM-TFSI
    emim2 = xyz[EMIM2_START:EMIM2_END]
    tfsi2 = xyz[TFSI2_START:TFSI2_END]
    m6 = pair_min(emim2, tfsi2)
    if name == "cluster":
        checks.append((6, m6 < 4.0, f"cluster_IP2_EMIM_TFSI_min={m6:.4f}"))
    else:
        checks.append((7, m6 > 5.0, f"dissociate_IP2_EMIM_TFSI_min={m6:.4f}"))

    # 8) cell compatibility
    frac = xyz @ np.linalg.inv(CELL.T)
    ok = np.all(np.isfinite(frac)) and np.all((frac >= -0.05) & (frac <= 1.05))
    checks.append((8, ok, f"frac_sample={frac[0].tolist()}"))

    # 9) COORD file match
    ok = coord_name is not None and coord_name == FILES[name].name
    checks.append((9, ok, f"coord_file={coord_name}"))

    # 10) KIND coverage
    missing = sorted(set(atoms).difference(kinds))
    checks.append((10, not missing, f"missing_KIND={missing}"))

    all_ok = all(v[1] for v in checks)
    print(f"[{name}] {'PASS' if all_ok else 'FAIL'}")
    for n, ok, msg in checks:
        print(("PASS" if ok else "FAIL") + f" {n:02d}) {msg}")
    if not all_ok:
        print("FAILED:")
        for n, ok, msg in checks:
            if not ok:
                print(f" - {n:02d} {msg}")


def main():
    for tag in ("cluster", "dissociate"):
        check(tag)


if __name__ == "__main__":
    main()
