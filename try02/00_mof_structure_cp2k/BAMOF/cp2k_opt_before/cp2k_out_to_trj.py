import re
from pathlib import Path

def parse_restart_file(file_path):
    """
    Parse the &COORD section from a CP2K .restart file
    and return a list of (element, x, y, z) tuples.
    """
    coords = []
    in_coord = False
    coord_pattern = re.compile(r"^\s*(\w+)\s+([\dE+\-.]+)\s+([\dE+\-.]+)\s+([\dE+\-.]+)")
    with open(file_path) as f:
        for line in f:
            if line.strip().startswith('&COORD'):
                in_coord = True
                continue
            if in_coord:
                if line.strip().startswith('&END'):
                    break
                m = coord_pattern.match(line)
                if m:
                    elem, x, y, z = m.groups()
                    coords.append((elem, float(x), float(y), float(z)))
    return coords

def write_xyz(filename, frames):
    """
    Write a series of coordinate frames to an XYZ file.
    Each frame is a list of (element, x, y, z) tuples.
    """
    with open(filename, 'w') as out:
        for coords in frames:
            out.write(f"{len(coords)}\nFrame\n")
            for elem, x, y, z in coords:
                out.write(f"{elem} {x:.6f} {y:.6f} {z:.6f}\n")

def main(prefix):
    """
    Parse all CP2K restart files in current directory matching 'prefix<index>.restart',
    sorted by integer index, and write:
      - <cwd_basename>_trj.xyz (all frames)
      - <cwd_basename>_final.xyz (last frame)
    """
    path = Path('.')

    # Collect and sort restart files by integer index
    files = []
    for p in path.glob(f"{prefix}*.restart"):
        match = re.search(rf"{re.escape(prefix)}(\d+)", p.name)
        if match:
            idx = int(match.group(1))
            files.append((idx, p))
    files.sort(key=lambda x: x[0])

    # Parse coordinates
    frames = []
    for idx, filepath in files:
        coords = parse_restart_file(filepath)
        if coords:
            frames.append(coords)

    if not frames:
        print(f"No frames found with prefix '{prefix}' in current directory")
        return

    base = path.resolve().name
    # Write trajectory file
    trj_file = path / f"{base}_trj.xyz"
    write_xyz(trj_file, frames)

    # Write final structure file
    final_file = path / f"{base}_final.xyz"
    write_xyz(final_file, [frames[-1]])

    print(f"Wrote trajectory to {trj_file}")
    print(f"Wrote final structure to {final_file}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description="Parse CP2K restart files in current directory into XYZ trajectory and final structure."
    )
    parser.add_argument(
        '-p', '--prefix',
        required=True,
        help="Restart filename prefix (e.g. 'BAMOF_cp2k_opt-1_')"
    )
    args = parser.parse_args()
    main(args.prefix)
