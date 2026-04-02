#!/usr/bin/env python3
"""
build_structures.py — try04 2-IP 초기구조 자동 생성
====================================================
이 스크립트 하나로 BAMOF_2IP_cluster_init.xyz와 BAMOF_2IP_dissociate_init.xyz를
생성합니다. 모든 좌표가 하드코딩되어 있어 외부 파일 의존성이 없습니다.

Usage:
    python3 build_structures.py

Output:
    ../02_calculations/BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz
    ../02_calculations/BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz

Source: try03 restart files (Phase 1-3에서 추출/검증 완료)
"""
import numpy as np
import os
import sys
from pathlib import Path

# ════════════════════════════════════════════════════════════
# SECTION 1: CONSTANTS
# ════════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR_CLUSTER = SCRIPT_DIR / ".." / "02_calculations" / "BAMOF_2IP_cluster"
OUTPUT_DIR_DISSOCIATE = SCRIPT_DIR / ".." / "02_calculations" / "BAMOF_2IP_dissociate"

N_MOF_FIXED = 102      # atoms 1-102: MOF framework (FIXED_ATOMS)
N_MOF_UNFIXED = 22      # atoms 103-124: BA modulator phenyl rings (unfixed)
N_EMIM = 19             # atoms per EMIM+ (C6H11N2+)
N_TFSI = 15             # atoms per TFSI- (C2F6NO4S2-)
N_ION_PAIR = N_EMIM + N_TFSI  # 34
N_1IP_TOTAL = N_MOF_FIXED + N_MOF_UNFIXED + N_ION_PAIR  # 158
N_2IP_TOTAL = N_1IP_TOTAL + N_ION_PAIR  # 192

# Cell vectors (Å)
CELL_A = np.array([16.000, -0.557,  0.090])
CELL_B = np.array([-6.517, 14.613, -0.057])
CELL_C = np.array([-4.635, -7.066, 13.095])

# ════════════════════════════════════════════════════════════
# SECTION 2: BA-MOF + 1IP OPTIMIZED STRUCTURE (158 atoms)
# Source: try03/BAMOF_EMIM_TFSI_Cluster-1/restart (step 144)
# ════════════════════════════════════════════════════════════
BAMOF_1IP_ELEMENTS = (
    ['Ti']*8 + ['H']*24 + ['C']*34 + ['N']*4 + ['O']*32 +   # MOF fixed (102)
    ['H']*10 + ['C']*12 +                                     # MOF unfixed (22)
    ['N','N'] + ['C']*6 + ['H']*11 +                          # EMIM+ (19)
    ['N'] + ['C']*2 + ['O']*4 + ['F']*6 + ['S']*2             # TFSI- (15)
)

BAMOF_1IP_COORDS = np.array([
    # ── Ti ×8 (atoms 1-8) ──
    [-2.85544, 2.22976,11.24640],[ 7.97504, 5.11098, 1.88159],
    [ 1.24125,-1.70644, 9.42642],[ 2.75244, 7.45570, 3.65339],
    [ 1.75386, 9.13401, 1.74900],[ 3.12945,-1.96078,11.37979],
    [-1.90624, 0.49387, 9.35492],[ 5.98722, 5.41353, 3.72905],
    # ── H ×24 (atoms 9-32) ──
    [-2.35356, 6.12685,11.02695],[ 8.78382, 1.20492, 2.20227],
    [-6.81534, 1.47314,10.86395],[11.35719, 7.11527, 2.08224],
    [ 4.10506,-5.99532,10.99386],[-2.30466, 8.54411, 2.07105],
    [ 2.24832, 7.49720,-0.12409],[ 6.09951, 4.86828, 0.18165],
    [ 3.63936,-2.62789, 5.86869],[ 1.02900, 9.29272, 7.27235],
    [-5.97886, 3.88250, 8.99901],[10.72979, 3.02665, 4.18759],
    [-3.67775, 2.43506, 5.66517],[-1.34621,10.96187, 4.10224],
    [ 2.14611,12.23684, 2.60447],[ 8.62599,-0.81392, 3.40476],
    [ 4.84506, 7.13583, 2.31476],[ 0.16055, 0.14196,10.72004],
    [ 7.36419,-0.02593, 9.76945],[ 5.88307,-0.49499,10.51678],
    [ 7.93831, 4.40771, 8.67055],[ 7.36860, 4.76629, 7.05200],
    [ 6.87538,-4.98076, 9.57942],[ 5.59623,-3.88018,10.03681],
    # ── C ×34 (atoms 33-66) ──
    [ 8.55307, 4.36974, 4.74512],[-3.81599, 2.49115, 8.39937],
    [ 3.82175,-2.71714, 8.50170],[ 0.81632, 9.42621, 4.61275],
    [ 9.44909, 3.76542, 5.74031],[-4.74789, 3.11616, 7.42232],
    [ 4.76195,-3.33149, 7.55451],[-0.07350,10.07301, 5.61254],
    [ 9.20033, 3.84034, 7.14673],[-4.53150, 2.99618, 6.03430],
    [ 5.89140,-4.09179, 8.00757],[-1.16822,10.84596, 5.16761],
    [ 0.18100, 9.90225, 6.96742],[ 4.51424,-3.19935, 6.17058],
    [10.58277, 3.06644, 5.26460],[-5.84805, 3.80858, 7.92100],
    [ 8.76485, 1.28399, 0.05818],[ 2.29511,13.07558, 0.08319],
    [11.24928, 7.04711,-0.06783],[-2.10905, 8.58954,-0.08721],
    [ 3.49916, 5.11252, 5.61798],[-1.25693,-1.98185, 7.53612],
    [ 8.62899, 2.73885, 0.03498],[ 2.20236,11.64206, 0.04570],
    [ 9.95145, 6.43028,-0.02096],[-0.70674, 9.00389,-0.06275],
    [ 8.80420, 0.61488, 1.28786],[-2.34264, 6.71525,11.94084],
    [11.90458, 7.32191, 1.16613],[-7.37683, 1.29376,11.77930],
    [ 7.30894, 0.24940,11.79380],[-2.80624, 8.35912, 1.12526],
    [ 4.14670,-6.52248,11.94291],[ 2.30889,13.82677, 1.31247],
    # ── N ×4 (atoms 67-70) ──
    [ 2.36395,13.22794, 2.55063],[ 6.72990, 0.06655,10.55483],
    [ 8.11945, 4.48658, 7.67802],[ 6.22241,-4.25004, 9.32497],
    # ── O ×32 (atoms 71-102) ──
    [ 7.37675, 4.77483, 5.11091],[-3.04700, 1.54028, 8.00108],
    [ 4.20321,-2.59266, 9.72280],[ 0.75045, 9.85588, 3.41315],
    [ 1.58678, 8.46899, 4.99920],[ 2.65133,-2.34870, 8.09618],
    [ 8.96495, 4.45049, 3.53337],[-3.85800, 2.92740, 9.59908],
    [ 6.29244, 4.19562, 2.53436],[-1.35378, 2.05423,10.09944],
    [ 7.23123, 6.48291, 2.98434],[-3.10596, 0.32955,10.59211],
    [ 1.50055,-2.87840,10.68683],[ 3.26899, 9.01701, 2.91491],
    [ 2.45450,-0.61691,10.22266],[ 1.56276, 7.25990, 2.39748],
    [ 4.72028, 4.93265, 5.26373],[-1.91460,-0.94691, 7.91434],
    [ 3.87177,-3.73264,11.98889],[ 2.11925,10.94063, 1.14089],
    [ 4.67392,-0.94446,11.98376],[-0.11668, 9.10490, 1.08082],
    [-0.09511,-2.27640, 7.99393],[ 2.75732, 6.03341, 5.12464],
    [ 9.41211, 6.13010, 1.12702],[-4.74222, 2.16971,11.91484],
    [ 8.61655, 3.37578, 1.15643],[-2.47403, 3.95205,11.99611],
    [ 4.48423, 6.58707, 3.03543],[-0.21771,-0.41674,10.01645],
    [ 6.93834, 5.36195, 0.10263],[ 2.37069, 8.46400,-0.06411],
    # ── Unfixed MOF: H ×10 (atoms 103-112) ──
    [ 3.70045, 1.46246, 8.51890],[-0.08730,-3.99750, 6.16570],
    [ 4.45390,10.21562, 5.58082],[ 4.69737, 3.00361, 6.80336],
    [ 0.04314, 3.72896, 8.43013],[-3.86976,-2.09344, 6.92316],
    [ 1.37481, 1.83243, 9.29325],[ 1.03928, 5.26701, 6.70849],
    [ 5.78970, 8.44543, 4.46470],[-7.75390, 8.90874, 4.66004],
    # ── Unfixed MOF: C ×12 (atoms 113-124) ──
    [ 2.92235, 4.21875, 6.65193],[ 1.81427, 2.50791, 8.56108],
    [ 6.28772, 9.18645, 5.08891],[-1.91351,-2.94621, 6.61972],
    [ 1.60918, 4.43247, 7.11081],[ 3.12644, 2.29658, 8.11873],
    [ 5.53495,10.19134, 5.70813],[-1.16326,-3.96563, 6.00738],
    [ 7.67786, 9.13798, 5.24449],[-3.30800,-2.88966, 6.44023],
    [ 3.68262, 3.15126, 7.16645],[ 1.05823, 3.57749, 8.06638],
    # ── EMIM+: N ×2 (atoms 125-126) ──
    [-5.47047,18.52922,14.32175],[-4.38148,17.38792,12.81716],
    # ── EMIM+: C ×6 (atoms 127-132) ──
    [-5.75322,19.09658,13.09538],[-5.07536,18.37932,12.14893],
    [-2.11867,17.33497,11.81857],[-5.88868,19.05077,15.62519],
    [-4.62676,17.49942,14.13584],[-3.34838,16.52381,12.21983],
    # ── EMIM+: H ×11 (atoms 133-143) ──
    [-6.35576,19.98780,12.99573],[-4.99590,18.52610,11.08072],
    [-2.38347,18.13127,11.11096],[-6.33826,20.03423,15.47263],
    [-1.66193,17.81470,12.69286],[-6.61729,18.36425,16.06690],
    [-1.38726,16.67004,11.34147],[-3.79115,16.00514,11.36093],
    [-5.00719,19.16615,16.26162],[-4.17829,16.89475,14.91367],
    [-3.11452,15.76107,12.97020],
    # ── TFSI-: N ×1 (atom 144) ──
    [-3.92469,21.93811,13.24958],
    # ── TFSI-: C ×2 (atoms 145-146) ──
    [-1.50253,21.98356,14.68411],[-3.33273,23.32503,11.06839],
    # ── TFSI-: O ×4 (atoms 147-150) ──
    [-3.88388,21.48995,15.67513],[-2.80878,19.78711,14.16648],
    [-5.12085,21.41854,11.09201],[-2.70458,20.74830,11.25736],
    # ── TFSI-: F ×6 (atoms 151-156) ──
    [-1.57198,23.32532,14.86950],[-2.27231,23.82577,11.74335],
    [-0.69197,21.74083,13.62369],[-0.94091,21.43466,15.80057],
    [-4.37657,24.19763,11.19492],[-3.01760,23.25287, 9.73941],
    # ── TFSI-: S ×2 (atoms 157-158) ──
    [-3.17421,21.17602,14.44156],[-3.79586,21.61952,11.67971],
])

# ════════════════════════════════════════════════════════════
# SECTION 3: GAS-PHASE ION PAIR (34 atoms, BAMOF element order)
# Source: try03/00_ionic_structure_cp2k/Cluster01/restart (step 298)
# Reordered from gas-phase order to BAMOF element order
# ════════════════════════════════════════════════════════════
# Gas→BAMOF reorder mapping (0-based): Phase 3에서 검증 완료
_REORDER = [3,11,2,7,8,10,12,15,0,1,4,5,6,9,13,14,16,17,18,
            21,25,28,20,23,31,33,19,22,26,29,30,32,24,27]

_GAS_COORDS_ORIGINAL = np.array([
    [ 0.08256,-4.93595,-3.89888],[-1.33091,-3.96795,-3.45385],
    [-0.24737,-4.06753,-3.31558],[ 0.37615,-2.88195,-3.93980],
    [-1.15977,-1.36849,-3.64032],[-0.26538,-5.14953,-1.45234],
    [ 2.32225,-3.67437,-4.44672],[-0.16895,-1.65420,-3.98344],
    [ 1.67667,-2.80803,-4.41362],[ 0.72881, 0.98831,-5.58897],
    [ 0.11846,-4.19475,-1.83712],[ 0.74180,-0.80545,-4.48783],
    [ 1.90444,-1.50573,-4.75904],[-0.44428, 0.89213,-4.22477],
    [ 1.20529,-4.16981,-1.69206],[ 0.56895, 0.64826,-4.56026],
    [ 2.78793,-1.01939,-5.14782],[-0.32662,-3.38295,-1.24635],
    [ 1.28336, 1.11989,-3.87566],[ 2.62712, 1.55778,-1.62727],
    [-2.32230,-0.07679,-2.36669],[-0.03714,-0.05209,-1.49541],
    [-2.00084, 2.19041,-0.50216],[ 2.13140,-1.29703,-1.63250],
    [-1.56519,-0.36952,-1.14372],[ 2.11086, 1.07803,-0.45481],
    [ 1.24641, 2.00571, 0.01102],[ 1.26414,-0.58139,-0.69735],
    [-2.12013, 0.95940, 0.05524],[ 3.12592, 0.93863, 0.43337],
    [-3.42586, 0.75240, 0.37560],[-1.81050,-1.62462,-0.44572],
    [-1.37776, 0.93473, 1.18707],[ 1.05671,-1.12074, 0.63475],
])

# Reordered to BAMOF element sequence
GAS_IP_COORDS_BAMOF = _GAS_COORDS_ORIGINAL[_REORDER]
GAS_IP_ELEMENTS_BAMOF = (
    ['N','N'] + ['C']*6 + ['H']*11 +   # EMIM+ (19)
    ['N'] + ['C']*2 + ['O']*4 + ['F']*6 + ['S']*2  # TFSI- (15)
)

# ════════════════════════════════════════════════════════════
# SECTION 4: DISSOCIATE REFERENCE (try03에서 사용한 TFSI 재배치 좌표)
# Source: try03/BAMOF_EMIM_TFSI_dissociate-1/init xyz (atoms 144-158)
# ════════════════════════════════════════════════════════════
DISSOCIATE_TFSI_REFERENCE = np.array([
    [-0.5309,25.3952,13.8659],  # N
    [-2.8551,25.4280,12.3379],  # C
    [ 0.9207,23.3828,13.1812],  # C
    [-2.6315,26.3492,14.7698],  # O
    [-1.4639,27.5844,12.9003],  # O
    [ 1.9624,25.8010,13.5894],  # O
    [ 0.6205,25.4364,11.5063],  # O
    [-3.3597,24.2949,12.8971],  # F
    [-0.1623,22.7514,12.6466],  # F
    [-2.1802,25.0832,11.2125],  # F
    [-3.9110,26.2073,11.9653],  # F
    [ 1.0010,23.0488,14.4963],  # F
    [ 2.0309,22.9146,12.5497],  # F
    [-1.7884,26.3376,13.5887],  # S
    [ 0.7721,25.2362,12.9420],  # S
])

# ════════════════════════════════════════════════════════════
# SECTION 5: UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════
def write_xyz(filepath, elements, coords, comment=""):
    """Write XYZ file."""
    n = len(elements)
    assert coords.shape == (n, 3), f"Shape mismatch: {n} elements vs {coords.shape}"
    with open(filepath, 'w') as f:
        f.write(f"{n}\n{comment}\n")
        for elem, (x, y, z) in zip(elements, coords):
            f.write(f"{elem:2s} {x:20.12f} {y:20.12f} {z:20.12f}\n")
    print(f"  Written: {filepath} ({n} atoms)")

def min_dist(c1, c2):
    """Minimum distance between two coordinate arrays."""
    return np.min(np.linalg.norm(c1[:, None, :] - c2[None, :, :], axis=2))

def min_dist_per_atom(c1, c2):
    """Min distance from each atom in c1 to any atom in c2."""
    return np.min(np.linalg.norm(c1[:, None, :] - c2[None, :, :], axis=2), axis=1)

def find_best_placement(base_coords, new_ip_coords, cell_vectors,
                        n_translate_samples=500, n_rotation_samples=50,
                        min_allowed_dist=1.8):
    """
    Find optimal placement for 2nd ion pair inside the MOF pore.
    
    Strategy: 
    1. Sample random fractional coordinates for translation
    2. For each, try random rotations  
    3. Pick placement that maximizes min distance to existing atoms
    """
    rng = np.random.default_rng(42)  # reproducible
    ip_com = new_ip_coords.mean(axis=0)
    ip_centered = new_ip_coords - ip_com
    
    best_score = 0
    best_coords = None
    best_info = {}
    
    for _ in range(n_translate_samples):
        # Random fractional coordinates (avoid edges)
        frac = rng.uniform(0.1, 0.9, size=3)
        target = frac[0]*cell_vectors[0] + frac[1]*cell_vectors[1] + frac[2]*cell_vectors[2]
        
        for _ in range(n_rotation_samples):
            # Random rotation
            axis = rng.normal(size=3)
            axis /= np.linalg.norm(axis)
            angle = rng.uniform(0, 2*np.pi)
            
            # Rodrigues rotation
            K = np.array([
                [0, -axis[2], axis[1]],
                [axis[2], 0, -axis[0]],
                [-axis[1], axis[0], 0]
            ])
            R = np.eye(3) + np.sin(angle)*K + (1-np.cos(angle))*(K@K)
            
            rotated = (R @ ip_centered.T).T + target
            
            # Score: minimum distance to all existing atoms
            d_min = min_dist(rotated, base_coords)
            
            if d_min > best_score:
                best_score = d_min
                best_coords = rotated.copy()
                best_info = {'frac': frac, 'target': target, 'd_min': d_min}
    
    if best_score < min_allowed_dist:
        print(f"  ⚠ WARNING: Best min distance = {best_score:.2f} Å < {min_allowed_dist} Å")
        print(f"    Manual adjustment may be needed!")
    
    return best_coords, best_info

# ════════════════════════════════════════════════════════════
# SECTION 6: MAIN — GENERATE STRUCTURES
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  try04: 2-IP 초기구조 생성")
    print("=" * 60)
    
    # ── Validate base structure ──
    assert len(BAMOF_1IP_ELEMENTS) == N_1IP_TOTAL
    assert BAMOF_1IP_COORDS.shape == (N_1IP_TOTAL, 3)
    assert len(GAS_IP_ELEMENTS_BAMOF) == N_ION_PAIR
    print(f"\n✓ Base structure: {N_1IP_TOTAL} atoms")
    print(f"✓ Ion pair template: {N_ION_PAIR} atoms")
    
    # ── Find best placement for 2nd ion pair ──
    print(f"\n[Step 1] Finding optimal position for 2nd ion pair...")
    cell = np.array([CELL_A, CELL_B, CELL_C])
    
    placed_ip, info = find_best_placement(
        base_coords=BAMOF_1IP_COORDS,
        new_ip_coords=GAS_IP_COORDS_BAMOF,
        cell_vectors=cell,
        n_translate_samples=800,
        n_rotation_samples=80,
        min_allowed_dist=1.8,
    )
    
    print(f"  Best placement: min_dist = {info['d_min']:.2f} Å")
    print(f"  Fractional coords: ({info['frac'][0]:.3f}, {info['frac'][1]:.3f}, {info['frac'][2]:.3f})")
    
    # Sub-distances
    d_mof = min_dist(placed_ip, BAMOF_1IP_COORDS[:N_MOF_FIXED])
    d_unfixed = min_dist(placed_ip, BAMOF_1IP_COORDS[N_MOF_FIXED:N_MOF_FIXED+N_MOF_UNFIXED])
    d_ip1 = min_dist(placed_ip, BAMOF_1IP_COORDS[N_MOF_FIXED+N_MOF_UNFIXED:])
    print(f"  → MOF framework:  {d_mof:.2f} Å")
    print(f"  → Unfixed MOF:    {d_unfixed:.2f} Å")
    print(f"  → 1st ion pair:   {d_ip1:.2f} Å")
    
    # ── Build CLUSTER structure (2 IP, both associated) ──
    print(f"\n[Step 2] Building CLUSTER structure (192 atoms)...")
    cluster_elements = list(BAMOF_1IP_ELEMENTS) + list(GAS_IP_ELEMENTS_BAMOF)
    cluster_coords = np.vstack([BAMOF_1IP_COORDS, placed_ip])
    
    assert len(cluster_elements) == N_2IP_TOTAL
    assert cluster_coords.shape == (N_2IP_TOTAL, 3)
    
    os.makedirs(OUTPUT_DIR_CLUSTER, exist_ok=True)
    cluster_xyz = OUTPUT_DIR_CLUSTER / "BAMOF_2IP_cluster_init.xyz"
    write_xyz(
        cluster_xyz, cluster_elements, cluster_coords,
        comment=f"BA-MOF + 2 IP (cluster) | 192 atoms | min_dist={info['d_min']:.2f}A"
    )
    
    # ── Build DISSOCIATE structure ──
    # Strategy: same as cluster, but translate 2nd TFSI- away from 2nd EMIM+
    # Use the same COM shift as try03: (2.10, 2.93, 0.01) Å magnitude ~3.6 Å
    # Plus try multiple rotation angles to maximize EMIM-TFSI separation
    print(f"\n[Step 3] Building DISSOCIATE structure (192 atoms)...")
    
    ip2_start = N_1IP_TOTAL  # index of 2nd IP start in 2IP system
    emim2_slice = slice(ip2_start, ip2_start + N_EMIM)
    tfsi2_slice = slice(ip2_start + N_EMIM, ip2_start + N_ION_PAIR)
    
    emim2_coords = cluster_coords[emim2_slice]
    tfsi2_original = cluster_coords[tfsi2_slice]
    emim2_com = emim2_coords.mean(axis=0)
    tfsi2_com = tfsi2_original.mean(axis=0)
    
    # Try03 reference: COM shift direction roughly (2.10, 2.93, 0.01)
    # We'll try multiple shift vectors of similar magnitude (~5-8 Å) 
    # and pick the one that gives best separation
    rng = np.random.default_rng(123)
    best_diss_score = 0
    best_diss_coords = None
    
    # Also include the exact try03 direction as a candidate
    try03_direction = np.array([2.10, 2.93, 0.01])
    try03_direction /= np.linalg.norm(try03_direction)
    
    candidate_directions = [try03_direction]
    for _ in range(200):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        candidate_directions.append(d)
    
    all_non_tfsi2 = np.vstack([
        cluster_coords[:ip2_start + N_EMIM],  # everything except 2nd TFSI
    ])
    
    for direction in candidate_directions:
        for magnitude in [4.0, 5.0, 6.0, 7.0, 8.0]:
            shift = direction * magnitude
            shifted_tfsi = tfsi2_original + shift
            
            # Check: TFSI should be far from EMIM but not clash with MOF
            d_emim_tfsi = min_dist(emim2_coords, shifted_tfsi)
            d_to_others = min_dist(shifted_tfsi, all_non_tfsi2)
            
            # Score: maximize EMIM-TFSI distance, penalize MOF clashes
            if d_to_others < 1.5:
                continue  # too close to framework
            
            score = d_emim_tfsi + 0.5 * d_to_others
            
            if score > best_diss_score:
                best_diss_score = score
                best_diss_coords = shifted_tfsi.copy()
                best_diss_info = {
                    'd_emim_tfsi': d_emim_tfsi,
                    'd_to_others': d_to_others,
                    'shift': shift,
                    'magnitude': magnitude,
                }
    
    if best_diss_coords is None:
        print("  ⚠ ERROR: Could not find valid dissociate placement!")
        print("    Falling back to try03 direction with 6 Å shift")
        best_diss_coords = tfsi2_original + try03_direction * 6.0
        best_diss_info = {'d_emim_tfsi': 0, 'd_to_others': 0, 'shift': try03_direction*6, 'magnitude': 6}
    
    # Assemble dissociate structure
    diss_coords = cluster_coords.copy()
    diss_coords[tfsi2_slice] = best_diss_coords
    
    d_check = min_dist(diss_coords[emim2_slice], diss_coords[tfsi2_slice])
    print(f"  TFSI shift: ({best_diss_info['shift'][0]:.2f}, {best_diss_info['shift'][1]:.2f}, {best_diss_info['shift'][2]:.2f}) Å")
    print(f"  |shift| = {best_diss_info['magnitude']:.1f} Å")
    print(f"  EMIM-TFSI min distance (2nd IP): {d_check:.2f} Å")
    print(f"  TFSI-others min distance: {best_diss_info['d_to_others']:.2f} Å")
    
    if d_check < 4.0:
        print(f"  ⚠ WARNING: EMIM-TFSI distance < 4 Å. May recombine during optimization!")
    
    os.makedirs(OUTPUT_DIR_DISSOCIATE, exist_ok=True)
    diss_xyz = OUTPUT_DIR_DISSOCIATE / "BAMOF_2IP_dissociate_init.xyz"
    write_xyz(
        diss_xyz, cluster_elements, diss_coords,
        comment=f"BA-MOF + 2 IP (dissociated) | 192 atoms | EMIM-TFSI_d={d_check:.2f}A"
    )
    
    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"  구조 생성 완료!")
    print(f"{'='*60}")
    print(f"  Cluster:    {cluster_xyz}")
    print(f"  Dissociate: {diss_xyz}")
    print(f"\n  Next steps:")
    print(f"  1. VESTA/Chimera에서 두 구조를 시각적으로 확인")
    print(f"  2. 2nd IP가 포어 내부에 있는지 검증")
    print(f"  3. Dissociate에서 TFSI가 충분히 떨어져 있는지 확인")
    print(f"  4. 확인 후 cp2k 실행: cd ../02_calculations/BAMOF_2IP_cluster && bash ../../run_cp2k_gpu.sh")

if __name__ == "__main__":
    main()
