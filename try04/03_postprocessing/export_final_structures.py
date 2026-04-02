#!/usr/bin/env python3
"""export_final_structures.py
Export final frame from CP2K trajectory to XYZ/CIF/POSCAR/MOL2.
"""

from __future__ import annotations

from pathlib import Path


def parse_last_frame(xyz_path: Path):
    lines = xyz_path.read_text().splitlines()
    nat = int(lines[0].strip())
    step = nat + 2
    if len(lines) < step:
        raise ValueError(f"{xyz_path} has no full frame")
    last = (len(lines) // step - 1) * step
    atoms = []
    for row in lines[last + 2:last + 2 + nat]:
        s = row.split()
        if len(s) < 4:
            continue
        atoms.append((s[0], float(s[1]), float(s[2]), float(s[3])))
    return atoms


def write_xyz(atoms, path: Path) -> None:
    with path.open("w") as f:
        f.write(f"{len(atoms)}\\nFinal frame\\n")
        for a in atoms:
            f.write(f"{a[0]} {a[1]:.8f} {a[2]:.8f} {a[3]:.8f}\\n")


def write_poscar(atoms, path: Path) -> None:
    unique = sorted(set(s for s, *_ in atoms))
    counts = {k: sum(1 for a in atoms if a[0] == k) for k in unique}
    with path.open("w") as f:
        f.write("try04 final frame\\n1.0\\n")
        for i in range(3):
            f.write("  1.0 0.0 0.0\\n" if i == 0 else ("  0.0 1.0 0.0\\n" if i == 1 else "  0.0 0.0 1.0\\n"))
        f.write(" ".join(unique) + "\\n")
        f.write(" ".join(str(counts[k]) for k in unique) + "\\n")
        f.write("Cartesian\\n")
        for _, x, y, z in atoms:
            f.write(f"{x:.8f} {y:.8f} {z:.8f}\\n")


def write_cif(atoms, path: Path) -> None:
    with path.open("w") as f:
        f.write("data_try04_final\\n")
        f.write("_symmetry_space_group_name_H-M   'P 1'\\n")
        f.write("_cell_length_a 1.0\\n_cell_length_b 1.0\\n_cell_length_c 1.0\\n")
        f.write("_cell_angle_alpha 90\\n_cell_angle_beta 90\\n_cell_angle_gamma 90\\n")
        f.write("loop_\\n")
        f.write("_atom_site_label _atom_site_type_symbol _atom_site_fract_x _atom_site_fract_y _atom_site_fract_z\\n")
        for i, (s, x, y, z) in enumerate(atoms, start=1):
            f.write(f"{s}{i} {s} {x:.8f} {y:.8f} {z:.8f}\\n")


def write_mol2(atoms, path: Path) -> None:
    with path.open("w") as f:
        f.write("@<TRIPOS>MOLECULE\\ntry04\\n")
        f.write(f"{len(atoms)} {max(len(atoms)-1,0)} 0 0 0\\n")
        f.write("SMALL\\nNO_CHARGES\\n")
        f.write("@<TRIPOS>ATOM\\n")
        for i, (s, x, y, z) in enumerate(atoms, start=1):
            f.write(f"{i:>7d} {s:<4s} {x:10.4f} {y:10.4f} {z:10.4f} {s} 1 <0> {0:10.4f}\\n")
        f.write("@<TRIPOS>BOND\\n")


def export_one(src_xyz: Path, out_root: Path) -> None:
    atoms = parse_last_frame(src_xyz)
    out_root.mkdir(parents=True, exist_ok=True)
    write_xyz(atoms, out_root / (src_xyz.stem + "_final.xyz"))
    write_cif(atoms, out_root / (src_xyz.stem + "_final.cif"))
    write_poscar(atoms, out_root / (src_xyz.stem + "_final.POSCAR"))
    write_mol2(atoms, out_root / (src_xyz.stem + "_final.mol2"))
    print(f"Exported from {src_xyz}")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("trajectories", nargs="+", help="trajectory xyz path(s)")
    p.add_argument("--outdir", default="D:/PSID_BAMOF/try04/03_postprocessing/final_structures")
    args = p.parse_args()
    out = Path(args.outdir)
    for t in args.trajectories:
        export_one(Path(t), out)


if __name__ == "__main__":
    main()
