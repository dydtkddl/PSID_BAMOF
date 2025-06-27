
#!/usr/bin/env python3
"""
packmol_filter.py
-----------------
MOF(프리미티브)와 guest 분자들을 함께 포함한 XYZ 파일을 받아,
분자를 셀 안으로 wrap → (wrap된 분자 + MOF primitive) 를 ±1 셀로 복제해
겹침(overlap)이 없는 분자만 남긴 뒤
 • 래핑 XYZ,   • 원래 XYZ,   • CIF(PBC)  세 가지 파일로 저장한다.

Run:
    python packmol_filter.py mof.cif combined.xyz molecule.xyz outdir [cutoff]
"""

import argparse, itertools, os
from pathlib import Path

import numpy as np
from ase.io import read, write
from ase.geometry import distance
from ase import Atoms

# ------------------------------------------------------------
# 0. 유틸리티
# ------------------------------------------------------------
def build_translations(cell):
    """(-1,0,1)³ 27 개 셀 벡터를 반환"""
    a, b, c = cell
    for i, j, k in itertools.product([-1, 0, 1], repeat=3):
        yield i * a + j * b + k * c


def atoms_with_shift(atoms: Atoms, shift):
    """atoms 객체를 주어진 실수 벡터만큼 평행이동한 복제본 반환(새 Atoms)"""
    dup = atoms.copy()
    dup.translate(shift)
    return dup


def min_distance(A: np.ndarray, B: np.ndarray) -> float:
    """두 좌표 집합의 최소 거리(Å)"""
    # (N,3)-(M,3) → (N,M,3)
    diff = A[:, None, :] - B[None, :, :]
    return np.sqrt((diff ** 2).sum(axis=-1)).min()


# ------------------------------------------------------------
# 1. 메인 로직
# ------------------------------------------------------------
def main():
    # ---------- 1-A. 인자 파싱 ----------
    p = argparse.ArgumentParser()
    p.add_argument("mof_cif")
    p.add_argument("combined_xyz")
    p.add_argument("molecule_xyz")
    p.add_argument("outdir")
    p.add_argument("cutoff", nargs="?", type=float, default=2.0,
                   help="overlap cutoff in Å (default 2.0)")
    args = p.parse_args()

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    # ---------- 1-B. 파일 읽기 ----------
    mof = read(args.mof_cif)
    cell = mof.get_cell()
    mof.set_pbc(True)          # PBC 켜기

    mol_template = read(args.molecule_xyz)
    combined = read(args.combined_xyz)

    n_mof = len(mof)
    n_per_mol = len(mol_template)
    n_total = len(combined)

    if (n_total - n_mof) % n_per_mol != 0:
        raise ValueError("Total atoms is not a multiple of guest molecule atom count")
    n_mols = (n_total - n_mof) // n_per_mol

    # ---------- 1-C. guest 분자 분리 ----------
    mols_original = []
    for i in range(n_mols):
        start = n_mof + i * n_per_mol
        end = start + n_per_mol
        mol_i = combined[start:end].copy()
        mol_i.set_cell(cell)
        mol_i.set_pbc(True)
        mols_original.append(mol_i)

    # ---------- 1-D. 분자 래핑 ----------
    mols_wrapped = []
    for mol in mols_original:
        mol_wrap = mol.copy()
        # scaled positions → wrap → back to Cartesian
        mol_wrap.set_scaled_positions(mol_wrap.get_scaled_positions() % 1.0)
        mols_wrapped.append(mol_wrap)

    # --------------------------------------------------------
    # 2. 겹침 검사용 이미지(±1 복제) 생성
    #    * MOF primitive + 현재까지 accept된 분자들을 모두 복제
    # --------------------------------------------------------
    translations = list(build_translations(cell))
    # MOF 27개 이미지 (겹침 체크용)
    mof_images = [atoms_with_shift(mof, t) for t in translations]

    accepted_wrapped = []
    accepted_original = []

    cutoff = args.cutoff

    # ---------- 2-A. 분자별 최소-이미지 겹침 검사 ----------
    for mol_w, mol_ori in zip(mols_wrapped, mols_original):
        overlap = False

        # (i) MOF ↔ 분자
        for img in mof_images:
            if min_distance(mol_w.get_positions(), img.get_positions()) < cutoff:
                overlap = True
                break
        if overlap:
            continue

        # (ii) 이미 accept된 분자 ↔ 새 분자  (±1 셀 복제 포함)
        for acc in accepted_wrapped:
            # acc 이미지 27개
            for t in translations:
                acc_img = atoms_with_shift(acc, t)
                if min_distance(mol_w.get_positions(), acc_img.get_positions()) < cutoff:
                    overlap = True
                    break
            if overlap:
                break

        if not overlap:
            accepted_wrapped.append(mol_w)
            accepted_original.append(mol_ori)

    # --------------------------------------------------------
    # 3. 결과 저장
    # --------------------------------------------------------
    # 3-A. XYZ (래핑)
    wrapped_all = mof.copy()
    for mol in accepted_wrapped:
        wrapped_all += mol
    write(outdir / "nonoverlap_wrapped.xyz", wrapped_all)

    # 3-B. XYZ (원본 좌표)
    original_all = mof.copy()
    for mol in accepted_original:
        original_all += mol
    write(outdir / "nonoverlap_unwrapped.xyz", original_all)

    # 3-C. CIF (PBC)
    cif_atoms = mof.copy()
    for mol in accepted_wrapped:
        cif_atoms += mol
    cif_atoms.set_pbc(True)
    cif_atoms.set_cell(cell)
    write(outdir / "nonoverlap.cif", cif_atoms, format="cif")

    # 요약 메시지
    print(f"[OK] {n_mols} → {len(accepted_wrapped)} molecules kept "
          f"(cutoff={cutoff:.2f} Å). Files written to: {outdir}")


if __name__ == "__main__":
    main()

