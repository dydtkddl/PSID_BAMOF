#!/usr/bin/env python3
import sys
import numpy as np
from scipy.ndimage import label
from scipy.spatial import cKDTree
from ase import Atoms
from ase.data import vdw_radii, atomic_numbers

def parse_restart(filename):
    cell = []
    coords = []
    in_cell = in_coord = False
    with open(filename) as f:
        for line in f:
            ls = line.strip()
            if ls.startswith("&CELL"):
                in_cell = True
                continue
            if in_cell:
                if ls.startswith("&END CELL"):
                    in_cell = False
                else:
                    parts = ls.split()
                    if parts[0] in ("A","B","C"):
                        cell.append([float(parts[1]), float(parts[2]), float(parts[3])])
                continue
            if ls.startswith("&COORD"):
                in_coord = True
                continue
            if in_coord:
                if ls.startswith("&END COORD") or ls.startswith("UNIT"):
                    in_coord = False
                else:
                    parts = ls.split()
                    if len(parts) >= 4:
                        symbol = parts[0]
                        x, y, z = map(float, parts[1:4])
                        coords.append((symbol, x, y, z))
    return np.array(cell), coords

def find_pore_atoms(cell, coords, res=0.5, wall_tol=None, chunk_size=5000):
    # unpack primitive cell
    symbols = [c[0] for c in coords]
    positions = np.array([c[1:] for c in coords])
    # get vdW radii via atomic_numbers mapping
    radii = np.array([vdw_radii[atomic_numbers[s]] for s in symbols])
    if wall_tol is None:
        wall_tol = res

    # build 2×2×2 supercell
    shifts = [i*cell[0] + j*cell[1] + k*cell[2]
              for i in (0,1) for j in (0,1) for k in (0,1)]
    super_positions = np.vstack([positions + shift for shift in shifts])
    super_symbols   = symbols * len(shifts)
    super_radii     = np.tile(radii, len(shifts))
    cell_super = cell * 2

    # create grid over supercell
    lengths = np.linalg.norm(cell_super, axis=1)
    nx, ny, nz = [int(np.ceil(L/res)) for L in lengths]
    u = np.linspace(0,1,nx,endpoint=False)
    v = np.linspace(0,1,ny,endpoint=False)
    w = np.linspace(0,1,nz,endpoint=False)
    U,V,W = np.meshgrid(u,v,w, indexing='ij')
    frac_grid = np.vstack([U.ravel(), V.ravel(), W.ravel()]).T
    cart_grid = frac_grid @ cell_super

    # detect void voxels in chunks
    M = len(cart_grid)
    mask_void = np.empty(M, dtype=bool)
    for start in range(0, M, chunk_size):
        end = min(start + chunk_size, M)
        blk = cart_grid[start:end]
        d2 = np.linalg.norm(blk[:,None,:] - super_positions[None,:,:], axis=2)
        mask_void[start:end] = np.all(d2 > super_radii, axis=1)

    # cluster and find main pore
    void_grid = mask_void.reshape(nx, ny, nz)
    labeled, _ = label(void_grid, structure=np.ones((3,3,3)))
    counts = np.bincount(labeled.ravel()); counts[0] = 0
    main_lbl = np.argmax(counts)
    pore_frac = frac_grid[labeled.ravel() == main_lbl]
    pore_cart = pore_frac @ cell_super

    # identify pore wall atoms in supercell
    tree = cKDTree(pore_cart)
    d_atom, _ = tree.query(super_positions, k=1)
    mask_wall = d_atom <= (super_radii + wall_tol)

    # filter symbols and positions
    wall_symbols = [super_symbols[i] for i in np.where(mask_wall)[0]]
    wall_positions = super_positions[mask_wall]
    return wall_symbols, wall_positions

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <restart-file>")
        sys.exit(1)

    cell, coords = parse_restart(sys.argv[1])
    symbols, positions = find_pore_atoms(cell, coords, res=0.5)

    # write pore-only XYZ
    with open('pore_atoms.xyz','w') as f:
        f.write(f"{len(symbols)}\nPore-only atoms from 2x2x2 supercell\n")
        for s, (x,y,z) in zip(symbols, positions):
            f.write(f"{s} {x:.6f} {y:.6f} {z:.6f}\n")
