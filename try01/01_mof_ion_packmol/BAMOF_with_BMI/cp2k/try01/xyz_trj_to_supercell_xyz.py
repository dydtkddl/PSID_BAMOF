import sys
from ase.io import read, write

def expand_xyz(cif_file, input_xyz, output_xyz, nx, ny, nz):
    """
    Reads a CIF to get unit cell, reads an XYZ or trajectory XYZ file,
    replicates each frame nx x ny x nz times, and writes to output_xyz.
    """
    # Read CIF to obtain cell
    unit_cell = read(cif_file, format='cif')
    cell = unit_cell.get_cell()
    
    # Read all frames from input_xyz (handles single-frame as well)
    frames = read(input_xyz, index=':')
    
    expanded_frames = []
    for atoms in frames:
        # Assign cell and periodic boundary conditions
        atoms.set_cell(cell)
        atoms.set_pbc([True, True, True])
        # Replicate the cell
        supercell = atoms.repeat((nx, ny, nz))
        expanded_frames.append(supercell)
    
    # Write out the expanded frames
    write(output_xyz, expanded_frames)

def main():
    if len(sys.argv) != 7:
        print(f"Usage: {sys.argv[0]} <cif_file> <input_xyz> <output_xyz> <nx> <ny> <nz>")
        sys.exit(1)

    cif_file = sys.argv[1]
    input_xyz = sys.argv[2]
    output_xyz = sys.argv[3]
    nx, ny, nz = map(int, sys.argv[4:7])

    expand_xyz(cif_file, input_xyz, output_xyz, nx, ny, nz)
    print(f"Expanded {input_xyz} by {nx}x{ny}x{nz} using cell from {cif_file}, saved to {output_xyz}")

if __name__ == "__main__":
    main()

