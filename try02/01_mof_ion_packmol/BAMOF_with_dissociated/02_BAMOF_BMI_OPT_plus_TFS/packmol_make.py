#!/usr/bin/env python3
"""
packmol_make.py

Generate a Packmol input file by expanding a MOF primitive cell to define the bounding box
and padding by twice the molecule's longest dimension as buffer.
Optionally produce a Plotly 3D HTML visualization.

Usage:
    python packmol_make.py base_input.inp mof_structure.cif molecule_xyz \
        [--tolerance 2.0] [--figure fig.html]

Arguments:
    base_input.inp      Path to the Packmol base input template
    mof_structure.cif   Path to the MOF primitive cell CIF
    molecule_xyz        Path to the ion/molecule XYZ file

Options:
    --tolerance TOL     Packmol tolerance (default: 2.0)
    --figure FIG_HTML   Output HTML file for 3D visualization
"""
import sys
import os
import argparse
import math
import numpy as np
from ase.io import read, write

try:
    import plotly.graph_objects as go
    from plotly.offline import plot as plotly_plot
except ImportError:
    go = None


def parse_args():
    p = argparse.ArgumentParser(description="Generate Packmol input with cell-based box.")
    p.add_argument("template", help="Packmol base input template")
    p.add_argument("mof_cif", help="MOF primitive cell CIF")
    p.add_argument("molecule_xyz", help="Ion/molecule XYZ")
    p.add_argument("--tolerance", type=float, default=2.0,
                   help="Packmol tolerance")
    p.add_argument("--figure", metavar="FIG_HTML",
                   help="Output HTML file for 3D visualization")
    return p.parse_args()


def parse_cif_cell(cif):
    params = {}
    with open(cif) as f:
        for l in f:
            if l.startswith("_cell_length_a"):
                params['a'] = float(l.split()[1])
            elif l.startswith("_cell_length_b"):
                params['b'] = float(l.split()[1])
            elif l.startswith("_cell_length_c"):
                params['c'] = float(l.split()[1])
            elif l.startswith("_cell_angle_alpha"):
                params['alpha'] = math.radians(float(l.split()[1]))
            elif l.startswith("_cell_angle_beta"):
                params['beta'] = math.radians(float(l.split()[1]))
            elif l.startswith("_cell_angle_gamma"):
                params['gamma'] = math.radians(float(l.split()[1]))
    a,b,c = params['a'], params['b'], params['c']
    alpha,beta,gamma = params['alpha'], params['beta'], params['gamma']
    v_a = np.array([a, 0.0, 0.0])
    v_b = np.array([b * math.cos(gamma), b * math.sin(gamma), 0.0])
    cx = c * math.cos(beta)
    cy = c * (math.cos(alpha) - math.cos(beta) * math.cos(gamma)) / math.sin(gamma)
    cz = math.sqrt(c**2 - cx**2 - cy**2)
    v_c = np.array([cx, cy, cz])
    return np.vstack([v_a, v_b, v_c])


def get_cell_bounds(cif):
    mat = parse_cif_cell(cif)
    return {
        'x_min': float(mat[:,0].min()),
        'x_max': float(mat[:,0].max()),
        'y_min': float(mat[:,1].min()),
        'y_max': float(mat[:,1].max()),
        'z_min': float(mat[:,2].min()),
        'z_max': float(mat[:,2].max()),
        'cell_mat': mat
    }


def get_molecule_length(xyz):
    coords = []
    with open(xyz) as f:
        nat = int(f.readline().strip())
        _ = f.readline()
        for _ in range(nat):
            parts = f.readline().split()
            coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    arr = np.array(coords)
    mins, maxs = arr.min(axis=0), arr.max(axis=0)
    return {
        'x': float(maxs[0] - mins[0]),
        'y': float(maxs[1] - mins[1]),
        'z': float(maxs[2] - mins[2])
    }


def generate_packmol_input(template, out, mof_xyz, mol_xyz, bounds, mlen, tol):
    # pad each side by twice the molecule's longest dimension
    pad_x = 2 * mlen['x']
    pad_y = 2 * mlen['y']
    pad_z = 2 * mlen['z']
    xmin = bounds['x_min'] - pad_x
    xmax = bounds['x_max'] + pad_x
    ymin = bounds['y_min'] - pad_y
    ymax = bounds['y_max'] + pad_y
    zmin = bounds['z_min'] - pad_z
    zmax = bounds['z_max'] + pad_z
    tpl = open(template).read()
    inp = tpl.format(
        tolerance=tol,
        structure=mof_xyz,
        molecule=mol_xyz,
        x1=xmin, x2=xmax,
        y1=ymin, y2=ymax,
        z1=zmin, z2=zmax,
        number=1,
        index="{index}",
        seed="{seed}"
    )
    with open(out, 'w') as f:
        f.write(inp)


def plot_structure(bounds, mlen, figfile):
    if go is None:
        print("Plotly not installed; skipping figure.", file=sys.stderr)
        return
    mat = bounds['cell_mat']
    vecs = {'a': mat[0], 'b': mat[1], 'c': mat[2]}
    ix1, ix2 = bounds['x_min'], bounds['x_max']
    iy1, iy2 = bounds['y_min'], bounds['y_max']
    iz1, iz2 = bounds['z_min'], bounds['z_max']
    # apply twice-longest padding for visualization
    ox1 = ix1 - 2 * mlen['x']
    ox2 = ix2 + 2 * mlen['x']
    oy1 = iy1 - 2 * mlen['y']
    oy2 = iy2 + 2 * mlen['y']
    oz1 = iz1 - 2 * mlen['z']
    oz2 = iz2 + 2 * mlen['z']
    fig = go.Figure()
    # draw cell vectors
    for name, v in vecs.items():
        fig.add_trace(go.Scatter3d(
            x=[0, v[0]], y=[0, v[1]], z=[0, v[2]],
            mode='lines+text', text=[name], textposition='top center',
            line=dict(width=5)
        ))
    # helper to draw boxes
    def add_box(xmin, xmax, ymin, ymax, zmin, zmax, color):
        edges = [
            ([xmin, xmax], [ymin, ymin], [zmin, zmin]),
            ([xmin, xmax], [ymax, ymax], [zmin, zmin]),
            ([xmin, xmin], [ymin, ymin], [zmin, zmax]),
            ([xmax, xmax], [ymin, ymin], [zmin, zmax]),
            ([xmin, xmin], [ymin, ymax], [zmin, zmin]),
            ([xmin, xmin], [ymin, ymax], [zmax, zmax]),
            ([xmax, xmax], [ymin, ymax], [zmin, zmin]),
            ([xmax, xmax], [ymin, ymax], [zmax, zmax]),
            ([xmin, xmax], [ymin, ymin], [zmin, zmax]),
            ([xmin, xmax], [ymax, ymax], [zmin, zmax]),
            ([xmin, xmax], [ymin, ymin], [zmax, zmax]),
            ([xmin, xmax], [ymax, ymax], [zmax, zmax]),
        ]
        for xs, ys, zs in edges:
            fig.add_trace(go.Scatter3d(
                x=xs, y=ys, z=zs, mode='lines',
                line=dict(color=color)
            ))
    # inner cell box (blue) and outer padded box (red)
    add_box(ix1, ix2, iy1, iy2, iz1, iz2, 'blue')
    add_box(ox1, ox2, oy1, oy2, oz1, oz2, 'red')
    # enforce equal scaling for axes
    fig.update_layout(
        scene=dict(
            aspectmode='cube'
        ),
        title="Cell vectors and Buffers"
    )
    plotly_plot(fig, filename=figfile, auto_open=False)


def main():
    args = parse_args()
    for p in (args.template, args.mof_cif, args.molecule_xyz):
        if not os.path.isfile(p):
            print(f"Error: not found: {p}", file=sys.stderr)
            sys.exit(1)
    # convert CIF to XYZ automatically
    mof_xyz = os.path.splitext(os.path.basename(args.mof_cif))[0] + ".xyz"
    atoms = read(args.mof_cif)
    write(mof_xyz, atoms)

    bounds = get_cell_bounds(args.mof_cif)
    mlen = get_molecule_length(args.molecule_xyz)
    # print the longest molecular dimension
    max_dim = max(mlen.values())
    print(f"Molecule longest dimension: {max_dim:.3f} Å")

    outinp = os.path.splitext(os.path.basename(args.template))[0] + "_gen.inp"

    generate_packmol_input(
        args.template, outinp,
        mof_xyz, args.molecule_xyz,
        bounds, mlen, args.tolerance
    )
    print(f"Generated Packmol input: {outinp}")

    if args.figure:
        plot_structure(bounds, mlen, args.figure)
        print(f"Saved figure HTML: {args.figure}")

if __name__ == "__main__":
    main()
