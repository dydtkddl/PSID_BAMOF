#!/usr/bin/env python3
"""distance_report.py - geometry distances for cluster/dissociate"""
from pathlib import Path
import numpy as np

BASE = Path('/mnt/d/PSID_BAMOF/try04/02_calculations')
PATHS = {
    'cluster': BASE / 'BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz',
    'dissociate': BASE / 'BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz',
}


def parse(path):
    lines = path.read_text().splitlines()
    n = int(lines[0])
    atoms = []
    xyz = []
    for i in range(2, 2 + n):
        p = lines[i].split()
        atoms.append(p[0])
        xyz.append([float(v) for v in p[1:4]])
    return atoms, np.array(xyz)


def nearest_from(src, target):
    d = np.linalg.norm(src[:, None, :] - target[None, :, :], axis=2)
    idx = np.argmin(d, axis=1)
    val = d[np.arange(len(src)), idx]
    return val, idx


def com(points):
    return points.mean(axis=0)


def make_section(name, atoms, xyz):
    mof = xyz[:124]
    ip1 = xyz[124:158]
    ip2 = xyz[158:192]
    emim2 = xyz[177:192]  # wrong? keep corrected below

    # correct
    emim2 = xyz[158:177]
    tfsi2 = xyz[177:192]
    ti = xyz[np.array(atoms) == 'Ti']

    target = np.vstack((mof, ip1))
    d_ip2_nei, idx1 = nearest_from(ip2, target)
    d_emim_ti, idx_ti = nearest_from(com(emim2)[None, :], ti)
    d_tfsi_nei, idx2 = nearest_from(tfsi2, emim2)

    lines = []
    lines.append(f'[{name}] 2nd IP to MOF/1stIP nearest distance\n')
    for i, d in enumerate(d_ip2_nei, start=159):
        lines.append(f'atom {i:4d}: {atoms[i-1]:2s} {d:10.5f} ?\n')
    lines.append(f'2nd EMIM-Ti min distance: {float(d_emim_ti.min()):.5f} ?\n')
    lines.append('2nd TFSI to nearest 2nd EMIM:\n')
    for k, d in enumerate(d_tfsi_nei, start=178):
        lines.append(f'atom {k:4d}: {atoms[k-1]:2s} {d:10.5f} ?\n')
    lines.append(f'2nd EMIM-TFSI min distance: {float(np.linalg.norm(ip2[0:0, :] if len(ip2)==0 else emim2[:,None,:] - tfsi2[None,:,:],axis=2).min()):.5f} ?\n')
    return lines, {
        'ip2_to_host_min': float(d_ip2_nei.min()),
        'emim_tfsi_min': float(np.linalg.norm(emim2[:, None, :] - tfsi2[None, :, :], axis=2).min()),
        'emim_ti_min': float(d_emim_ti.min()),
    }


def main():
    out = []
    stats = {}
    for name, p in PATHS.items():
        atoms, xyz = parse(p)
        # fix any potential bad indices if parsing changed
        section, s = make_section(name, atoms, xyz)
        out.extend(section)
        out.append('\n')
        stats[name] = s

    out.append('[Comparison]\n')
    out.append(f"ip2->host min: cluster={stats['cluster']['ip2_to_host_min']:.5f}, dissociate={stats['dissociate']['ip2_to_host_min']:.5f}\n")
    out.append(f"2nd emim-tfsi min: cluster={stats['cluster']['emim_tfsi_min']:.5f}, dissociate={stats['dissociate']['emim_tfsi_min']:.5f}\n")
    out.append(f"2nd emim-t i min: cluster={stats['cluster']['emim_ti_min']:.5f}, dissociate={stats['dissociate']['emim_ti_min']:.5f}\n")

    out_path = Path('/mnt/d/PSID_BAMOF/try04/01_structure_preparation/distance_report.txt')
    out_path.write_text(''.join(out))
    print('saved ->', out_path)


if __name__ == '__main__':
    main()
