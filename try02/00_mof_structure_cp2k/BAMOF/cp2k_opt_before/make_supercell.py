#!/usr/bin/env python3
"""
make_supercell.py

Read a CIF, tile it into an a×b×c supercell, and write out a new CIF.

Usage:
    python make_supercell.py input.cif a b c [output.cif]

Arguments:
    input.cif       Path to the input CIF file.
    a, b, c         Integer repeats along the a-, b-, and c-axes.
    output.cif      (Optional) Output filename. Defaults to
                    <input_basename>_<a>x<b>x<c>.cif
"""
import sys, os
from ase.io import read, write

def main():
    if len(sys.argv) not in (5,6):
        print("Usage: python make_supercell.py input.cif a b c [output.cif]", file=sys.stderr)
        sys.exit(1)

    infile = sys.argv[1]
    try:
        a, b, c = map(int, sys.argv[2:5])
    except ValueError:
        print("Error: a, b, c must be integers", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(infile):
        print(f"Error: file not found: {infile}", file=sys.stderr)
        sys.exit(1)

    # determine output filename
    if len(sys.argv) == 6:
        outfile = sys.argv[5]
    else:
        base = os.path.splitext(os.path.basename(infile))[0]
        outfile = f"{base}_{a}x{b}x{c}.cif"

    # read CIF (will create an Atoms object with cell, symbols, coords, etc.)
    atoms = read(infile)

    # build supercell by tiling
    supercell = atoms.repeat((a, b, c))

    # write out the new CIF
    write(outfile, supercell, format='cif')

    print(f"Wrote supercell CIF to {outfile}")

if __name__ == "__main__":
    main()

