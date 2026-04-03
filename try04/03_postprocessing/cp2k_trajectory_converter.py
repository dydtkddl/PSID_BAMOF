#!/usr/bin/env python3
"""
cp2k_trajectory_converter.py  v2.0
=============================================================
CP2K GEO_OPT trajectory → supercell + multi-format export
with cell-vector preservation & validation.

v2.0 changes:
  - fractional wrapping in make_supercell (fixes 0.499 error)
  - periodic image-aware bond detection
  - validate() with image-boundary tolerance
  - minimum-image convention for coordinate comparison

Usage:
  python cp2k_trajectory_converter.py \
    --cp2k-out  production_ot.out \
    --init-xyz  BAMOF_2IP_cluster_init.xyz \
    --cell "16.00 -0.557 0.090 | -6.517 14.613 -0.057 | -4.635 -7.066 13.095" \
    --repeat 2 2 2 \
    --out-dir   ./exported \
    --frames last
"""

from __future__ import annotations
import argparse, sys
from pathlib import Path
from typing import List, Tuple
from collections import defaultdict, OrderedDict
import numpy as np

# ───────────────────────────────────────────────
# 1.  Cell-vector utilities
# ───────────────────────────────────────────────
def parse_cell(cell_str: str) -> np.ndarray:
    """Parse 'Ax Ay Az | Bx By Bz | Cx Cy Cz' → (3,3) row-vector matrix."""
    rows = [list(map(float, r.split())) for r in cell_str.split("|")]
    M = np.array(rows, dtype=np.float64)
    assert M.shape == (3, 3), f"Cell must be 3x3, got {M.shape}"
    return M


def cell_to_params(M: np.ndarray):
    """Cell matrix → (a, b, c, alpha, beta, gamma) in Angstrom / degrees."""
    va, vb, vc = M[0], M[1], M[2]
    a = np.linalg.norm(va)
    b = np.linalg.norm(vb)
    c = np.linalg.norm(vc)
    alpha = np.degrees(np.arccos(np.clip(np.dot(vb, vc) / (b * c), -1, 1)))
    beta = np.degrees(np.arccos(np.clip(np.dot(va, vc) / (a * c), -1, 1)))
    gamma = np.degrees(np.arccos(np.clip(np.dot(va, vb) / (a * b), -1, 1)))
    return a, b, c, alpha, beta, gamma


def cart_to_frac(coords: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Cartesian → fractional. coords (N,3), M (3,3) row-vectors."""
    return coords @ np.linalg.inv(M)


def frac_to_cart(frac: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Fractional → Cartesian."""
    return frac @ M


def wrap_frac(frac: np.ndarray) -> np.ndarray:
    """[FIX #1] Wrap fractional coordinates into [0, 1).
    This is the core fix for the 0.499 error.
    Atoms at fractional -0.01 become 0.99, etc."""
    return frac - np.floor(frac)


def min_image_frac_diff(f1: np.ndarray, f2: np.ndarray) -> np.ndarray:
    """[FIX #2] Minimum-image fractional difference."""
    diff = f1 - f2
    diff = diff - np.round(diff)  # shift into [-0.5, 0.5)
    return diff


# ───────────────────────────────────────────────
# 2.  XYZ / trajectory parsing
# ───────────────────────────────────────────────
def parse_xyz_frames(path: Path) -> List[Tuple[str, List[str], np.ndarray]]:
    """Return list of (comment, [symbols], coords(N,3))."""
    text = path.read_text(errors="ignore")
    lines = text.splitlines()
    frames = []
    i = 0
    while i < len(lines):
        l = lines[i].strip()
        if not l:
            i += 1
            continue
        try:
            n = int(l)
        except ValueError:
            i += 1
            continue
        comment = lines[i + 1].strip() if i + 1 < len(lines) else ""
        syms, coords = [], []
        for j in range(i + 2, min(i + 2 + n, len(lines))):
            parts = lines[j].split()
            if len(parts) >= 4:
                syms.append(parts[0])
                coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
        if len(syms) == n:
            frames.append((comment, syms, np.array(coords, dtype=np.float64)))
        i += 2 + n
    return frames


# ───────────────────────────────────────────────
# 3.  Supercell expansion  (cell vectors × n)
# ───────────────────────────────────────────────
def make_supercell(
    syms: List[str],
    coords: np.ndarray,
    M: np.ndarray,
    na: int, nb: int, nc: int,
) -> Tuple[List[str], np.ndarray, np.ndarray]:
    """Expand primitive cell → na×nb×nc supercell with wrapping fix."""
    frac = cart_to_frac(coords, M)
    frac = wrap_frac(frac)

    new_syms = []
    new_frac = []
    for ia in range(na):
        for ib in range(nb):
            for ic in range(nc):
                shift = np.array([ia, ib, ic], dtype=np.float64)
                for s, f in zip(syms, frac):
                    new_syms.append(s)
                    new_frac.append((f + shift) / np.array([na, nb, nc]))

    new_frac = np.array(new_frac, dtype=np.float64)
    M_super = M.copy()
    M_super[0] *= na
    M_super[1] *= nb
    M_super[2] *= nc
    new_cart = frac_to_cart(new_frac, M_super)
    return new_syms, new_cart, M_super


# ───────────────────────────────────────────────
# 4.  Bond detection (periodic-image aware)
# ───────────────────────────────────────────────
_COV_RADII = {
    "H": 0.31, "C": 0.76, "N": 0.71, "O": 0.66,
    "F": 0.57, "S": 1.05, "Ti": 1.60, "Cl": 1.02,
    "Br": 1.20, "P": 1.07, "B": 0.84,
}


def detect_bonds_periodic(
    syms: List[str],
    coords: np.ndarray,
    M: np.ndarray,
    tol: float = 0.45,
) -> List[Tuple[int, int]]:
    """Periodic-image-aware bond detection."""
    n = len(syms)
    frac = cart_to_frac(coords, M)
    frac = wrap_frac(frac)
    coords_w = frac_to_cart(frac, M)

    M_inv = np.linalg.inv(M)
    max_r = max(_COV_RADII.get(s, 1.5) for s in syms) * 2 + tol + 0.1

    cell_size = max_r
    cells = defaultdict(list)
    for i in range(n):
        cx = int(coords_w[i, 0] // cell_size)
        cy = int(coords_w[i, 1] // cell_size)
        cz = int(coords_w[i, 2] // cell_size)
        cells[(cx, cy, cz)].append(i)

    bonds = []
    for (cx, cy, cz), atoms_i in cells.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    atoms_j = cells.get((cx + dx, cy + dy, cz + dz), [])
                    for i in atoms_i:
                        ri = _COV_RADII.get(syms[i], 1.5)
                        for j in atoms_j:
                            if j <= i:
                                continue
                            rj = _COV_RADII.get(syms[j], 1.5)
                            delta_cart = coords_w[i] - coords_w[j]
                            delta_frac = delta_cart @ M_inv
                            delta_frac -= np.round(delta_frac)
                            delta_cart_mic = delta_frac @ M
                            d = np.linalg.norm(delta_cart_mic)
                            if 0.4 < d < (ri + rj + tol):
                                bonds.append((i, j))
    return bonds


# ───────────────────────────────────────────────
# 5.  Writers
# ───────────────────────────────────────────────
def write_xyz(path: Path, syms, coords, comment=""):
    with open(path, "w") as f:
        f.write(f"{len(syms)}\n{comment}\n")
        for s, c in zip(syms, coords):
            f.write(f"{s:4s} {c[0]:16.10f} {c[1]:16.10f} {c[2]:16.10f}\n")


def write_multiframe_xyz(path: Path, frames_data):
    with open(path, "w") as f:
        for comment, syms, coords in frames_data:
            f.write(f"{len(syms)}\n{comment}\n")
            for s, c in zip(syms, coords):
                f.write(f"{s:4s} {c[0]:16.10f} {c[1]:16.10f} {c[2]:16.10f}\n")


def write_cif(path: Path, syms, coords, M, title="structure"):
    a, b, c, alpha, beta, gamma = cell_to_params(M)
    frac = cart_to_frac(coords, M)
    frac = wrap_frac(frac)
    with open(path, "w") as f:
        f.write(f"data_{title}\n")
        f.write(f"_cell_length_a    {a:.6f}\n")
        f.write(f"_cell_length_b    {b:.6f}\n")
        f.write(f"_cell_length_c    {c:.6f}\n")
        f.write(f"_cell_angle_alpha {alpha:.4f}\n")
        f.write(f"_cell_angle_beta  {beta:.4f}\n")
        f.write(f"_cell_angle_gamma {gamma:.4f}\n")
        f.write("_symmetry_space_group_name_H-M 'P 1'\n")
        f.write("_symmetry_Int_Tables_number 1\n")
        f.write("loop_\n_atom_site_label\n_atom_site_type_symbol\n")
        f.write("_atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\n")
        counts = {}
        for s, fc in zip(syms, frac):
            counts[s] = counts.get(s, 0) + 1
            label = f"{s}{counts[s]}"
            f.write(f"{label:8s} {s:4s} {fc[0]:12.8f} {fc[1]:12.8f} {fc[2]:12.8f}\n")


def write_poscar(path: Path, syms, coords, M, title="structure"):
    species = list(OrderedDict.fromkeys(syms))
    counts = [syms.count(s) for s in species]
    idx_sorted = []
    for s in species:
        idx_sorted += [i for i, sym in enumerate(syms) if sym == s]
    with open(path, "w") as f:
        f.write(f"{title}\n1.0\n")
        for row in M:
            f.write(f"  {row[0]:16.10f} {row[1]:16.10f} {row[2]:16.10f}\n")
        f.write("  " + "  ".join(species) + "\n")
        f.write("  " + "  ".join(map(str, counts)) + "\n")
        f.write("Cartesian\n")
        for i in idx_sorted:
            c = coords[i]
            f.write(f"  {c[0]:16.10f} {c[1]:16.10f} {c[2]:16.10f}\n")


def write_pdb(path: Path, syms, coords, M, bonds=None):
    a, b, c, alpha, beta, gamma = cell_to_params(M)
    with open(path, "w") as f:
        f.write(f"CRYST1{a:9.3f}{b:9.3f}{c:9.3f}{alpha:7.2f}{beta:7.2f}{gamma:7.2f} P 1\n")
        counts = {}
        for i, (s, co) in enumerate(zip(syms, coords)):
            counts[s] = counts.get(s, 0) + 1
            name = f"{s}{counts[s] % 10000}"
            f.write(
                f"HETATM{i+1:5d} {name:4s} MOL A   1    "
                f"{co[0]:8.3f}{co[1]:8.3f}{co[2]:8.3f}"
                f"  1.00  0.00          {s:>2s}\n"
            )
        if bonds:
            conn = defaultdict(list)
            for a_idx, b_idx in bonds:
                conn[a_idx + 1].append(b_idx + 1)
                conn[b_idx + 1].append(a_idx + 1)
            for atom_id in sorted(conn):
                nbrs = conn[atom_id]
                for cs in range(0, len(nbrs), 4):
                    chunk = nbrs[cs : cs + 4]
                    f.write(f"CONECT{atom_id:5d}" + "".join(f"{n:5d}" for n in chunk) + "\n")
        f.write("END\n")


def write_mol2(path: Path, syms, coords, bonds, title="structure"):
    n_atoms = len(syms)
    n_bonds = len(bonds)
    with open(path, "w") as f:
        f.write("@<TRIPOS>MOLECULE\n")
        f.write(f"{title}\n {n_atoms} {n_bonds} 0 0 0\nSMALL\nNO_CHARGES\n\n")
        f.write("@<TRIPOS>ATOM\n")
        counts = {}
        for i, (s, c) in enumerate(zip(syms, coords)):
            counts[s] = counts.get(s, 0) + 1
            label = f"{s}{counts[s]}"
            f.write(
                f"{i+1:7d} {label:8s} {c[0]:10.4f} {c[1]:10.4f} {c[2]:10.4f}"
                f" {s:8s}  1 MOL       0.0000\n"
            )
        f.write("@<TRIPOS>BOND\n")
        for bi, (a_idx, b_idx) in enumerate(bonds, 1):
            f.write(f"{bi:6d} {a_idx+1:5d} {b_idx+1:5d} 1\n")


# ───────────────────────────────────────────────
# 6.  Validation  v2.0
# ───────────────────────────────────────────────
def validate(
    M_prim: np.ndarray,
    M_super: np.ndarray,
    na: int, nb: int, nc: int,
    syms_prim: List[str],
    coords_prim: np.ndarray,
    syms_super: List[str],
    coords_super: np.ndarray,
) -> bool:
    p_a, p_b, p_c, p_al, p_be, p_ga = cell_to_params(M_prim)
    s_a, s_b, s_c, s_al, s_be, s_ga = cell_to_params(M_super)

    print("\n" + "=" * 65)
    print("  VALIDATION REPORT  v2.0")
    print("=" * 65)
    all_pass = True

    print("\n  [1] Cell Angles (must be identical)")
    for name, pv, sv in [("alpha", p_al, s_al), ("beta", p_be, s_be), ("gamma", p_ga, s_ga)]:
        diff = abs(pv - sv)
        ok = diff < 1e-6
        if not ok:
            all_pass = False
        print(f"      {name:5s}: prim={pv:.6f}°  super={sv:.6f}°  Δ={diff:.2e}  [{'PASS' if ok else 'FAIL'}]")

    print("\n  [2] Cell Lengths (super = prim × repeat)")
    for name, plen, mult, slen in [("a", p_a, na, s_a), ("b", p_b, nb, s_b), ("c", p_c, nc, s_c)]:
        expected = plen * mult
        diff = abs(expected - slen)
        ok = diff < 1e-6
        if not ok:
            all_pass = False
        print(f"      {name}: {plen:.6f} × {mult} = {expected:.6f}  actual={slen:.6f}  Δ={diff:.2e}  [{'PASS' if ok else 'FAIL'}]")

    print("\n  [3] Atom Count")
    expected_n = len(syms_prim) * na * nb * nc
    actual_n = len(syms_super)
    cnt_ok = expected_n == actual_n
    if not cnt_ok:
        all_pass = False
    print(f"      prim={len(syms_prim)} × {na}×{nb}×{nc} = {expected_n}  actual={actual_n}  [{'PASS' if cnt_ok else 'FAIL'}]")

    print("\n  [4] Coordinate Roundtrip (minimum-image convention)")
    frac_prim = cart_to_frac(coords_prim, M_prim)
    frac_prim_wrapped = wrap_frac(frac_prim)

    n_prim = len(syms_prim)
    frac_super_first = cart_to_frac(coords_super[:n_prim], M_super)
    expected_frac = frac_prim_wrapped / np.array([na, nb, nc])

    mic_diff = min_image_frac_diff(frac_super_first, expected_frac)
    max_mic_err = np.max(np.abs(mic_diff))

    coord_ok = max_mic_err < 1e-6
    if not coord_ok:
        all_pass = False
    print(f"      max min-image frac error = {max_mic_err:.2e}  [{'PASS' if coord_ok else 'FAIL'}]")

    raw_diff = np.abs(frac_super_first - expected_frac)
    n_boundary = np.sum(np.any(raw_diff > 0.4, axis=1))
    if n_boundary > 0:
        print(f"      ℹ️  {n_boundary} atoms near periodic boundary (raw Δfrac > 0.4, resolved by min-image)")

    print("\n  [5] Interatomic Distance Preservation (first-image cartesian)")
    rng = np.random.default_rng(42)
    n_check = min(20, n_prim * (n_prim - 1) // 2)
    pairs = set()
    while len(pairs) < n_check and len(pairs) < n_prim * (n_prim - 1) // 2:
        i, j = sorted(rng.choice(n_prim, 2, replace=False))
        pairs.add((i, j))

    # compare direct cartesian distances in first image (PBC removed by construction)
    frac_prim_wrapped = wrap_frac(frac_prim)
    coords_prim_wrapped = frac_to_cart(frac_prim_wrapped, M_prim)
    max_dist_err = 0.0
    for i, j in pairs:
        d_prim = np.linalg.norm(coords_prim_wrapped[i] - coords_prim_wrapped[j])
        d_super = np.linalg.norm(coords_super[i] - coords_super[j])
        max_dist_err = max(max_dist_err, abs(d_prim - d_super))

    dist_ok = max_dist_err < 1e-4
    if not dist_ok:
        all_pass = False
    print(f"      checked {len(pairs)} random pairs")
    print(f"      max |d_prim - d_super| = {max_dist_err:.2e} Å  [{'PASS' if dist_ok else 'FAIL'}]")

    print("\n  [6] Element Composition")
    from collections import Counter
    c_prim = Counter(syms_prim)
    c_super = Counter(syms_super)
    comp_ok = True
    for elem, count in c_prim.items():
        expected_count = count * na * nb * nc
        actual_count = c_super.get(elem, 0)
        ok = expected_count == actual_count
        if not ok:
            comp_ok = False
            all_pass = False
        print(f"      {elem:3s}: {count} × {na*nb*nc} = {expected_count}  actual={actual_count}  [{'PASS' if ok else 'FAIL'}]")

    print("\n" + "-" * 65)
    if all_pass:
        print("  ✅ ALL 6 CHECKS PASSED — structure integrity confirmed")
    else:
        print("  ❌ SOME CHECKS FAILED — review above")
    print("=" * 65 + "\n")
    return all_pass


# ───────────────────────────────────────────────
# 7.  Main
# ───────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="CP2K trajectory → supercell converter v2.0")
    parser.add_argument("--cp2k-out", type=str, default=None)
    parser.add_argument("--init-xyz", type=str, required=True)
    parser.add_argument("--cell", type=str, required=True,
                        help='"Ax Ay Az | Bx By Bz | Cx Cy Cz"')
    parser.add_argument("--repeat", type=int, nargs=3, default=[2, 2, 2])
    parser.add_argument("--out-dir", type=str, default="./exported")
    parser.add_argument("--bond-cutoff-tol", type=float, default=0.45)
    parser.add_argument("--frames", type=str, default="last", help='"all", "first", "last", or "0,5,10"')
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    M = parse_cell(args.cell)
    na, nb, nc = args.repeat

    a, b, c, al, be, ga = cell_to_params(M)
    print(f"Cell vectors:\n{M}")
    print(f"Primitive: a={a:.4f} b={b:.4f} c={c:.4f}  α={al:.4f}° β={be:.4f}° γ={ga:.4f}°")
    print(f"Supercell: {na}×{nb}×{nc}\n")

    frames = []
    if args.cp2k_out:
        traj_files = sorted(Path(args.cp2k_out).parent.glob("*-pos-1.xyz"))
        if traj_files:
            print(f"Trajectory: {traj_files[0]}")
            frames = parse_xyz_frames(traj_files[0])
            print(f"  → {len(frames)} frames")

    if not frames:
        print(f"Using init XYZ: {args.init_xyz}")
        frames = parse_xyz_frames(Path(args.init_xyz))

    if not frames:
        print("ERROR: No frames found!")
        sys.exit(1)

    frame_spec = args.frames.strip()
    if frame_spec == "all":
        selected = list(range(len(frames)))
    elif frame_spec == "first":
        selected = [0]
    elif frame_spec == "last":
        selected = [len(frames) - 1]
    else:
        selected = [int(x) for x in frame_spec.split(",")]
    print(f"Selected frames: {selected}\n")

    multi_super = []

    for fi in selected:
        comment, syms, coords = frames[fi]
        tag = f"frame{fi:04d}"
        print(f"━━━ {tag} ({len(syms)} atoms) ━━━")

        s_syms, s_coords, M_super = make_supercell(syms, coords, M, na, nb, nc)
        print(f"  Supercell: {len(s_syms)} atoms")

        validate(M, M_super, na, nb, nc, syms, coords, s_syms, s_coords)

        print("  Bonds...", end=" ", flush=True)
        bonds = detect_bonds_periodic(s_syms, s_coords, M_super, args.bond_cutoff_tol)
        print(f"{len(bonds)} found")

        prefix = out_dir / f"{tag}_{na}x{nb}x{nc}"
        sc_comment = f"{tag} {na}x{nb}x{nc} | {len(s_syms)} atoms"

        write_xyz(Path(f"{prefix}.xyz"), s_syms, s_coords, sc_comment)
        write_cif(Path(f"{prefix}.cif"), s_syms, s_coords, M_super, tag)
        write_poscar(Path(f"{prefix}.vasp"), s_syms, s_coords, M_super, tag)
        write_pdb(Path(f"{prefix}.pdb"), s_syms, s_coords, M_super, bonds)
        write_mol2(Path(f"{prefix}.mol2"), s_syms, s_coords, bonds, tag)

        prim_pre = out_dir / f"{tag}_prim"
        write_cif(Path(f"{prim_pre}.cif"), syms, coords, M, f"{tag}_prim")
        write_xyz(Path(f"{prim_pre}.xyz"), syms, coords, f"{tag} prim | {len(syms)} atoms")

        multi_super.append((sc_comment, s_syms, s_coords))
        print(f"  Exported: .xyz .cif .vasp .pdb .mol2\n")

    if len(multi_super) > 1:
        mf = out_dir / f"trajectory_{na}x{nb}x{nc}.xyz"
        write_multiframe_xyz(mf, multi_super)
        print(f"Multi-frame: {mf}")

    print("✅ Done.")


if __name__ == "__main__":
    main()


