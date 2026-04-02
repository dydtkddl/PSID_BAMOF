# VESTA guide for try04 structures

1. Open structure
   - File > Open...
   - Load one of:
     - `01_structure_preparation` output `*_visual.xyz`, or
     - raw `try04/02_calculations/*/*_init.xyz`

2. Set unit cell
   - Edit > Unit Cell... (or `Ctrl+U`)
   - Set lattice vectors directly from `*_cell.cif` or `*_POSCAR.vasp`:
     - `a [16.000 -0.557 0.090]`
     - `b [-6.517 14.613 -0.057]`
     - `c [-4.635 -7.066 13.095]`
   - Confirm and press Apply/OK.

3. Color by region (comment-based helper)
   - MOF atoms: gray
   - IP1 atoms (125-158): blue
   - IP2 atoms (159-192): red
   - In VESTA you can also manually recolor by atom index ranges above.

4. Bond setup
   - Properties > Bond > Set distance cutoff
   - Default auto-detect is usually enough, then tune slightly if needed.

5. Camera
   - Set to Perspective
   - Save a fixed angle and a close-up of the second ion pair region.

6. Export
   - File > Export Bitmap...
   - Example resolution: 3000 x 2400
   - Keep white background and anti-aliasing ON for manuscript figures.
