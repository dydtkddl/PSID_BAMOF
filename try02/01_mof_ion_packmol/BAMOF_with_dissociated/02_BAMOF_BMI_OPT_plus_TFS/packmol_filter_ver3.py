#!/usr/bin/env python3
"""
packmol_filter_nase.py  ──  ASE에 의존하지 않는 버전

USAGE
-----
python packmol_filter_nase.py  MOF.cif  combined.xyz  guest.xyz  outdir  [cutoff]

* MOF.cif       : 주기 셀·원자 좌표가 들어있는 CIF
* combined.xyz  : MOF + 여러 분자가 합쳐진 XYZ
* guest.xyz     : 단일 guest 분자 XYZ (원자수 Nₚ)
* outdir        : 결과 저장 폴더
* cutoff        : 겹침 판정 거리 Å (기본 2.0)

저장 파일
----------
<tag>_wrapped.xyz    : MOF + 래핑된 guest
<tag>_unwrapped.xyz  : MOF + 원본 guest
<tag>_reimg.xyz      : MOF + 재조립된 guest (셀 밖 허용)
<tag>.cif            : MOF + 래핑 guest (P1)
"""

import argparse, itertools, math, os, sys
from pathlib import Path

import numpy as np

# ============================================================
# 0. 간단한 CIF / XYZ 파서 & 라이터
# ============================================================
def read_xyz(path):
    """XYZ → (labels:list[str], coords: (N,3) ndarray)"""
    with open(path) as f:
        n = int(f.readline())
        f.readline()  # comment
        labels, coords = [], []
        for _ in range(n):
            parts = f.readline().split()
            labels.append(parts[0])
            coords.append([float(p) for p in parts[1:4]])
    return labels, np.array(coords, float)


def write_xyz(path, labels, coords, comment=""):
    """coords shape = (N,3)"""
    with open(path, "w") as f:
        f.write(f"{len(labels)}\n{comment}\n")
        for lab, (x, y, z) in zip(labels, coords):
            f.write(f"{lab:2s} {x: .6f} {y: .6f} {z: .6f}\n")


def parse_cif(path):
    """
    매우 제한적인 CIF 파서
    반환: (cell_a,b,c, alpha,beta,gamma), (labels list, frac (N,3) ndarray)
    """
    a = b = c = alpha = beta = gamma = None
    headers = []
    collecting = False
    atom_rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("_cell_length_a"):
                a = float(line.split()[1])
            elif line.startswith("_cell_length_b"):
                b = float(line.split()[1])
            elif line.startswith("_cell_length_c"):
                c = float(line.split()[1])
            elif line.startswith("_cell_angle_alpha"):
                alpha = float(line.split()[1])
            elif line.startswith("_cell_angle_beta"):
                beta = float(line.split()[1])
            elif line.startswith("_cell_angle_gamma"):
                gamma = float(line.split()[1])

            # atom loop
            if line.lower().startswith("loop_"):
                headers.clear()
                collecting = True
                continue
            if collecting and line.startswith("_"):
                headers.append(line.split()[0].lower())
                continue
            if collecting and line and not line.startswith("_"):
                atom_rows.append(line.split())
            elif collecting and (not line):
                collecting = False  # blank → loop 끝

    # 헤더 인덱스
    try:
        ix_x = headers.index("_atom_site_fract_x")
        ix_y = headers.index("_atom_site_fract_y")
        ix_z = headers.index("_atom_site_fract_z")
    except ValueError:
        raise RuntimeError("CIF에 _atom_site_fract_* 항목이 필요합니다.")

    ix_label = None
    if "_atom_site_label" in headers:
        ix_label = headers.index("_atom_site_label")
    elif "_atom_site_type_symbol" in headers:
        ix_label = headers.index("_atom_site_type_symbol")

    labels, fracs = [], []
    for row in atom_rows:
        labels.append(row[ix_label] if ix_label is not None else "X")
        fracs.append([float(row[ix_x]), float(row[ix_y]), float(row[ix_z])])

    cell = (a, b, c, alpha, beta, gamma)
    return cell, labels, np.array(fracs, float)
def write_cif(path, cell, labels, fracs):
    """매우 단순한 P1 CIF 라이터 (원소기호 자동 추출 개선)"""
    a, b, c, alpha, beta, gamma = cell
    with open(path, "w") as f:
        f.write("data_generated\n")
        f.write("_symmetry_space_group_name_H-M   'P1'\n")
        f.write("_symmetry_Int_Tables_number      1\n")
        f.write("_symmetry_cell_setting           triclinic\n\n")

        f.write(f"_cell_length_a    {a:.6f}\n")
        f.write(f"_cell_length_b    {b:.6f}\n")
        f.write(f"_cell_length_c    {c:.6f}\n")
        f.write(f"_cell_angle_alpha {alpha:.4f}\n")
        f.write(f"_cell_angle_beta  {beta:.4f}\n")
        f.write(f"_cell_angle_gamma {gamma:.4f}\n\n")

        f.write("loop_\n")
        f.write("_atom_site_label\n")
        f.write("_atom_site_type_symbol\n")
        f.write("_atom_site_fract_x\n")
        f.write("_atom_site_fract_y\n")
        f.write("_atom_site_fract_z\n")

        for lab, (x, y, z) in zip(labels, fracs):
            # ── 여기가 핵심 수정 ────────────────────────────────
            if '_' in lab:
                sym = lab.split('_')[-1]              # 'G0_C' → 'C'
            else:
                sym = ''.join(filter(str.isalpha, lab))  # 'C12' → 'C'
            sym = sym.capitalize()                    # cl → Cl
            # ────────────────────────────────────────────────
            f.write(f"{lab:6s} {sym:4s} {x:.6f} {y:.6f} {z:.6f}\n")


            f.write(f"{lab:6s} {sym:4s} {x:.6f} {y:.6f} {z:.6f}\n")


# ============================================================
# 1. 셀 변환 유틸리티
# ============================================================
def cell_matrix(a, b, c, alpha, beta, gamma):
    """길이 Å, 각도 deg → (3,3) 행렬 (row = a⃗,b⃗,c⃗)"""
    ar, br, gr = map(math.radians, (alpha, beta, gamma))
    va = np.array([a, 0.0, 0.0])
    vb = np.array([b * math.cos(gr), b * math.sin(gr), 0.0])
    cx = c * math.cos(br)
    cy = c * (math.cos(ar) - math.cos(br) * math.cos(gr)) / math.sin(gr)
    cz = math.sqrt(c**2 - cx**2 - cy**2)
    vc = np.array([cx, cy, cz])
    return np.vstack([va, vb, vc])  # shape (3,3)


def cart2frac(cart, cell_mat):
    return np.dot(cart, np.linalg.inv(cell_mat))


def frac2cart(frac, cell_mat):
    return np.dot(frac, cell_mat)


# ============================================================
# 2. 겹침 검사
# ============================================================
def build_translations(cell_mat):
    """(-1,0,1)^3 모든 셀 이동벡터 (27,3)"""
    a, b, c = cell_mat
    vecs = []
    for i, j, k in itertools.product([-1, 0, 1], repeat=3):
        vecs.append(i * a + j * b + k * c)
    return np.array(vecs)


def min_dist(A, B):
    """A(N,3)·B(M,3) → 최소 거리"""
    diff = A[:, None, :] - B[None, :, :]
    return np.sqrt((diff**2).sum(axis=-1)).min()


# ============================================================
# 3. 메인
# ============================================================
def reimage(frac):
    """첫 원자를 anchor 로 한 덩어리로 재조립 (N,3)"""
    anchor = frac[0].copy()
    diff = frac - anchor
    diff -= np.round(diff)          # (-0.5,0.5]
    return anchor + diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mof_cif")
    ap.add_argument("combined_xyz")
    ap.add_argument("guest_xyz")
    ap.add_argument("outdir")
    ap.add_argument("cutoff", nargs="?", type=float, default=2.0)
    args = ap.parse_args()

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    # --- 3.1 CIF 로부터 셀·MOF 정보 읽기
    cell_params, mof_labels, mof_frac = parse_cif(args.mof_cif)
    a, b, c, alpha, beta, gamma = cell_params
    cell_mat = cell_matrix(a, b, c, alpha, beta, gamma)
    mof_cart = frac2cart(mof_frac, cell_mat)
    n_mof = len(mof_labels)

    # --- 3.2 guest 템플릿
    guest_labels_tpl, _ = read_xyz(args.guest_xyz)
    n_guest = len(guest_labels_tpl)

    # --- 3.3 combined XYZ
    labels_all, coords_all = read_xyz(args.combined_xyz)
    print(len(labels_all))
    print(n_mof)
    print(n_guest)
    if len(labels_all) - n_mof <= 0 or (len(labels_all) - n_mof) % n_guest:
        sys.exit("※ guest 원자 수가 맞지 않습니다.")
    n_mols = (len(labels_all) - n_mof) // n_guest
    n_mof = len(mof_labels)                     # already parsed from CIF
    original_mof_labels = labels_all[:n_mof]    # should match mof_labels
    original_mof_cart   = coords_all[:n_mof]
    guest_coords_raw = []
    start = n_mof
    for i in range(n_mols):
        guest_coords_raw.append(coords_all[start + i * n_guest : start + (i + 1) * n_guest])
    guest_coords_raw = [g.copy() for g in guest_coords_raw]

    # --- 3.4 래핑
    guest_frac = [cart2frac(g, cell_mat) for g in guest_coords_raw]
    guest_frac_wrapped = [g % 1.0 for g in guest_frac]
    guest_cart_wrapped = [frac2cart(g, cell_mat) for g in guest_frac_wrapped]

    # --- 3.5 겹침 검사
    translations = build_translations(cell_mat)
    mof_imgs = [mof_cart + t for t in translations]

    accepted = []
    accepted_raw = []
    accepted_frac_wrapped = []
    for g_frac_w, g_cart_w, g_raw in zip(guest_frac_wrapped, guest_cart_wrapped, guest_coords_raw):
        # MOF ↔ guest
        overlap = any(min_dist(g_cart_w, img) < args.cutoff for img in mof_imgs)
        if overlap:
            continue
        # guest ↔ accepted
        for acc_cart in [frac2cart(fw, cell_mat) for fw in accepted_frac_wrapped]:
            if any(min_dist(g_cart_w, acc_cart + t) < args.cutoff for t in translations):
                overlap = True
                break
        if overlap:
            continue

        accepted.append(g_cart_w)
        accepted_raw.append(g_raw)
        accepted_frac_wrapped.append(g_frac_w)

    # --- 3.6 저장
    print(f"▶ {n_mols} → {len(accepted)} molecules kept (cutoff={args.cutoff} Å)")
    guest_tpl_labels = guest_labels_tpl

    for idx, (gw_cart, g_raw, g_frac_w) in enumerate(zip(accepted,
                                                         accepted_raw,
                                                         accepted_frac_wrapped)):
        tag = f"{Path(args.combined_xyz).stem}_{idx:03d}"

        # ① wrapped.xyz
        write_xyz(outdir / f"{tag}_wrapped.xyz",
              original_mof_labels + guest_tpl_labels,
	                   np.vstack([original_mof_cart, gw_cart]),
              "MOF + wrapped guest")

        # ② unwrapped.xyz
        write_xyz(outdir / f"{tag}_unwrapped.xyz",
              original_mof_labels + guest_tpl_labels,
              np.vstack([original_mof_cart, g_raw]),
              "MOF + original guest")        
	
        # ③ reimg.xyz
        g_frac_re = reimage(g_frac_w)
        g_cart_re = frac2cart(g_frac_re, cell_mat)
        write_xyz(outdir / f"{tag}_reimg.xyz",
              original_mof_labels + guest_tpl_labels,
              np.vstack([original_mof_cart, g_cart_re]),
              "MOF + re-imaged guest")    

        # ④ cif
        combined_labels = mof_labels + [f"G{idx}_{lab}" for lab in guest_tpl_labels]
        combined_frac = np.vstack([mof_frac, g_frac_w])
        write_cif(outdir / f"{tag}.cif", cell_params, combined_labels, combined_frac)

    print(f"✔ Files saved in '{outdir}' (wrapped/unwrapped/reimg + cif).")


if __name__ == "__main__":
    main()

