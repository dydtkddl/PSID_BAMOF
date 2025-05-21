import os
import sys

def load_xyz_coords(xyz_path):
    with open(xyz_path, 'r') as f:
        lines = f.readlines()[2:]  # skip atom count and comment
    coords = [list(map(float, line.split()[1:4])) for line in lines]
    return coords

def load_pdb_lines(pdb_path):
    with open(pdb_path, 'r') as f:
        lines = f.readlines()
    return lines

def round_coord(x, width=8, prec=3):
    return f"{x:>{width}.{prec}f}"

def update_pdb_coords(pdb_lines, xyz_coords):
    new_lines = []
    coord_idx = 0
    for line in pdb_lines:
        if line.startswith("ATOM") or line.startswith("HETATM"):
            x, y, z = xyz_coords[coord_idx]
            x_str = round_coord(x)
            y_str = round_coord(y)
            z_str = round_coord(z)
            newline = f"{line[:30]}{x_str}{y_str}{z_str}{line[54:].rstrip()}"
            new_lines.append(newline)
            coord_idx += 1
        else:
            new_lines.append(line.strip())
    return '\n'.join(new_lines) + '\n'

def main():
    if len(sys.argv) != 4:
        print("Usage: python script.py reference.pdb xyz_dir output_dir")
        return

    pdb_path = sys.argv[1]
    xyz_dir = sys.argv[2]
    output_dir = sys.argv[3]

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pdb_lines = load_pdb_lines(pdb_path)
    atom_count = sum(1 for line in pdb_lines if line.startswith("ATOM"))

    
    xyz_files = sorted([f for f in os.listdir(xyz_dir) if f.endswith('.xyz')])


    for idx, xyz_file in enumerate(xyz_files, start=1):
        xyz_path = os.path.join(xyz_dir, xyz_file)
        xyz_coords = load_xyz_coords(xyz_path)

        if len(xyz_coords) != atom_count:
            print(f"❌ Mismatch in {xyz_file}: expected {atom_count} atoms, got {len(xyz_coords)}")
            continue

        updated_pdb = update_pdb_coords(pdb_lines, xyz_coords)
        out_path = os.path.join(output_dir, f"IONIC_LIQUID{idx:04d}.pdb")  # <- 여기!
        with open(out_path, 'w') as f:
            f.write(updated_pdb)
        print(f"✅ Saved: {out_path}")


if __name__ == "__main__":
    main()
