#!/usr/bin/env python3
"""
packmol_filter.py  (분자별 개별 출력 버전)
----------------------------------------
MOF CIF + combined XYZ + 단일 분자 XYZ를 받아
 1) guest 분자를 셀 안으로 wrap
 2) (wrap된 분자 + MOF) 를 ±1 셀 복제해 겹침 여부 검사
 3) 겹치지 않는 분자마다
      • <prefix>_<idx>_wrapped.xyz
      • <prefix>_<idx>_unwrapped.xyz
      • <prefix>_<idx>.cif      (PBC)
    세 가지 파일 저장.

Run:
    python packmol_filter.py BAMOF.cif combined.xyz TFS.xyz outdir [cutoff]
"""
import argparse, itertools, os
from pathlib import Path

import numpy as np
from ase.io import read, write
from ase import Atoms


# ------------------------------------------------------------
# 0. 유틸리티
# ------------------------------------------------------------
def build_translations(cell):
    a, b, c = cell
    for i, j, k in itertools.product([-1, 0, 1], repeat=3):
        yield i * a + j * b + k * c


def atoms_with_shift(atoms: Atoms, shift):
    dup = atoms.copy()
    dup.translate(shift)
    return dup


def min_distance(A: np.ndarray, B: np.ndarray) -> float:
    diff = A[:, None, :] - B[None, :, :]
    return np.sqrt((diff ** 2).sum(axis=-1)).min()


# ------------------------------------------------------------
# 1. 메인
# ------------------------------------------------------------
def main():
    # ---------- 인자 ----------
    p = argparse.ArgumentParser()
    p.add_argument("mof_cif")
    p.add_argument("combined_xyz")
    p.add_argument("molecule_xyz")
    p.add_argument("outdir")
    p.add_argument("cutoff", nargs="?", type=float, default=2.0)
    args = p.parse_args()

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    prefix = Path(args.combined_xyz).stem   # ex) 'case_002'

    # ---------- 입력 ----------
    mof = read(args.mof_cif)
    cell = mof.get_cell()
    mof.set_pbc(True)

    mol_template = read(args.molecule_xyz)
    combined = read(args.combined_xyz)

    n_mof = len(mof)
    n_per_mol = len(mol_template)
    n_total = len(combined)

    if (n_total - n_mof) % n_per_mol != 0:
        raise ValueError("Total atoms is not a multiple of guest molecule atom count")
    n_mols = (n_total - n_mof) // n_per_mol

    # ---------- 분자 분리 ----------
    mols_original = []
    for i in range(n_mols):
        start = n_mof + i * n_per_mol
        mol_i = combined[start: start + n_per_mol].copy()
        mol_i.set_cell(cell)
        mol_i.set_pbc(True)
        mols_original.append(mol_i)

    # ---------- 래핑 ----------
    mols_wrapped = []
    for mol in mols_original:
        mw = mol.copy()
        mw.set_scaled_positions(mw.get_scaled_positions() % 1.0)
        mols_wrapped.append(mw)

    # ---------- 겹침 검사 ----------
    translations = list(build_translations(cell))
    mof_images = [atoms_with_shift(mof, t) for t in translations]

    accepted_wrapped, accepted_original = [], []
    cutoff = args.cutoff

    for mol_w, mol_ori in zip(mols_wrapped, mols_original):
        overlap = False

        # MOF ↔ 분자
        for img in mof_images:
            if min_distance(mol_w.positions, img.positions) < cutoff:
                overlap = True
                break
        if overlap:
            continue

        # 분자 ↔ 분자
        for acc in accepted_wrapped:
            for t in translations:
                if min_distance(mol_w.positions,
                                atoms_with_shift(acc, t).positions) < cutoff:
                    overlap = True
                    break
            if overlap:
                break

        if not overlap:
            accepted_wrapped.append(mol_w)
            accepted_original.append(mol_ori)

    # ---------- 분자별 저장 ----------
    for idx, (mol_w, mol_ori) in enumerate(zip(accepted_wrapped,
                                               accepted_original)):
        tag = f"{prefix}_{idx:03d}"

        # wrapped XYZ
        xwrap = mof.copy() + mol_w
        write(outdir / f"{tag}_wrapped.xyz", xwrap)

        # unwrapped XYZ
        xraw = mof.copy() + mol_ori
        write(outdir / f"{tag}_unwrapped.xyz", xraw)

        # CIF (PBC, 래핑된 좌표)
        cif_atoms = mof.copy() + mol_w
        cif_atoms.set_pbc(True)
        cif_atoms.set_cell(cell)
        write(outdir / f"{tag}.cif", cif_atoms, format="cif")

    # ---------- 요약 ----------
    print(f"[OK] {n_mols} → {len(accepted_wrapped)} molecules kept "
          f"(cutoff={cutoff:.2f} Å).")
    print(f"Files saved in '{outdir}/' as {prefix}_###.*")


if __name__ == "__main__":
    main()


