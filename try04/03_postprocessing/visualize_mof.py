#!/usr/bin/env python3
"""
visualize_mof.py
================
??? MOF/IL(2IP) ?? ??? ????
- ?? ???: cif/xyz/mol2/pdb ? PyMOL ???? ?? ??
- Trajectory: multi-frame xyz ? multi-model PDB ??
- PyMOL .pml ?? ??(?/?? ??? ??)

Usage:
  # ?? ???
  python visualize_mof.py BAMOF_2IP_cluster.xyz

  # Trajectory
  python visualize_mof.py trajectory.xyz --trj --ncpus 8

  # ??? ????
  python visualize_mof.py input.cif --no-gui --output mof.png

  # pml ? ??
  python visualize_mof.py input.cif --pml-only
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


SUPPORTED_STRUCT = {".cif", ".xyz", ".mol2", ".pdb", ".pdbqt"}


def run_cmd(cmd: List[str], timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess:
    """Run subprocess with clear error message."""
    try:
        return subprocess.run(
            cmd,
            check=check,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Command timeout ({timeout}s): {' '.join(cmd)}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {cmd[0]}") from exc


def check_dependencies(require_obabel: bool = False, require_pymol: bool = False) -> None:
    need_cmds = []
    if require_obabel and shutil.which("obabel") is None:
        need_cmds.append("obabel")
    if require_pymol and shutil.which("pymol") is None:
        need_cmds.append("pymol")

    if need_cmds:
        msg = []
        if "obabel" in need_cmds:
            msg.append("obabel")
        if "pymol" in need_cmds:
            msg.append("pymol-open-source")
        install = ", ".join([c for c in msg])
        raise RuntimeError(
            f"Required command(s) missing: {', '.join(need_cmds)}.\n"
            f"Install suggestion: conda install -c conda-forge {install}"
        )


def parse_xyz_frame_lines(lines: List[str]) -> List[tuple[int, int]]:
    """Parse all xyz frame [start, end) indices from a line list."""
    frames = []
    i = 0
    total = len(lines)
    while i < total:
        if i >= total:
            break
        head = lines[i].strip()
        if not head:
            i += 1
            continue
        try:
            n = int(head)
        except ValueError:
            i += 1
            continue
        start = i
        end = i + 2 + n
        if end <= total:
            frames.append((start, end))
            i = end
        else:
            # malformed trailing fragment
            break
    return frames


def split_xyz_to_frames(xyz_path: Path, tmpdir: Path) -> List[Path]:
    """Split multi-frame xyz into single-frame xyz files for parallel conversion."""
    txt = xyz_path.read_text(errors="ignore").splitlines()
    frame_ranges = parse_xyz_frame_lines(txt)
    if not frame_ranges:
        raise RuntimeError(f"No valid xyz frame found: {xyz_path}")

    out = []
    for idx, (s, e) in enumerate(frame_ranges):
        fp = tmpdir / f"frame_{idx+1:04d}.xyz"
        fp.write_text("\n".join(txt[s:e]) + "\n", encoding="utf-8")
        out.append(fp)
    return out


def obabel_to_mol2(src: Path, dst: Path, timeout: int = 300, add_h: bool = False) -> None:
    cmd = ["obabel", str(src), "-O", str(dst)]
    if add_h:
        cmd.append("--addh")
    else:
        cmd.append("-d")
    run_cmd(cmd, timeout=timeout)


def obabel_to_pdb(src: Path, dst: Path, timeout: int = 300, add_h: bool = False) -> None:
    cmd = ["obabel", str(src), "-O", str(dst)]
    if add_h:
        cmd.append("--addh")
    else:
        cmd.append("-d")
    run_cmd(cmd, timeout=timeout)


def convert_single_frame_to_pdb(xyz_path: Path, timeout: int = 300, add_h: bool = False) -> Path:
    """Convert a single xyz frame to pdb for trajectory concatenation."""
    pdb = xyz_path.with_suffix(".pdb")
    # direct xyz->pdb conversion
    obabel_to_pdb(xyz_path, pdb, timeout=timeout, add_h=add_h)
    return pdb


def frame_to_mol2(xyz_frame: Path, timeout: int = 300) -> Path:
    mol2 = xyz_frame.with_suffix(".mol2")
    obabel_to_mol2(xyz_frame, mol2, timeout=timeout)
    return mol2


def trajectory_to_multimodel_pdb(xyz_path: Path, ncpus: Optional[int] = None, timeout: int = 300, add_h: bool = False) -> Path:
    """Convert multi-frame xyz to multi-model PDB."""
    ncpus = ncpus or max(1, os.cpu_count() or 1)
    if ncpus <= 0:
        ncpus = 1

    with tempfile.TemporaryDirectory(prefix="traj_frames_") as td:
        td_path = Path(td)
        frame_xyzs = split_xyz_to_frames(xyz_path, td_path)

        pdb_paths: List[Path] = []
        with ProcessPoolExecutor(max_workers=ncpus) as ex:
            futures = [
                ex.submit(convert_single_frame_to_pdb, fp, timeout, add_h) for fp in frame_xyzs
            ]
            for fut in as_completed(futures):
                p = fut.result()
                pdb_paths.append(p)

        # ?? ??? ?? ??
        pdb_paths = sorted(pdb_paths)

        out_pdb = xyz_path.with_suffix(".pdb")
        with out_pdb.open("w", encoding="utf-8") as out:
            for i, p in enumerate(pdb_paths, start=1):
                out.write(f"MODEL     {i}\n")
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.upper().startswith("MODEL") or line.upper().startswith("ENDMDL"):
                        continue
                    out.write(line)
                    if line and not line.endswith("\n"):
                        out.write("\n")
                out.write("ENDMDL\n")

        return out_pdb


def make_guest_selection(guest_selection: Optional[str], guest_atoms: Optional[str], guest_range: Optional[str], mol_name: str) -> str:
    """Build guest PyMOL selection command block."""
    if not any([guest_selection, guest_atoms, guest_range]):
        return ""
    lines = ["\n# --- guest highlight ---"]
    if guest_selection:
        lines.append(f"select guest, ({guest_selection}) and {mol_name}")
    elif guest_atoms:
        lines.append(f"select guest, id {guest_atoms} and {mol_name}")
    elif guest_range:
        lines.append(f"select guest, byres ({guest_range}) and {mol_name}")
    lines += [
        "show sticks, guest",
        "color tv_red, guest",
        "set stick_radius, 0.15, guest",
        "",
    ]
    return "\n".join(lines)


def to_pml_color_block(framework_elements: List[str], output_image: Optional[Path], style: str, mol_name: str) -> str:
    elems_sel = " or ".join([f"elem {e}" for e in framework_elements]) if framework_elements else ""
    img = output_image.resolve().as_posix() if output_image else ""

    lines = [
        f"bg_color white",
        f"load {mol_name}",
        "hide everything, all",
        "show lines, all",
        "set line_width, 1.2",
        "set antialias, 2",
        "set ray_shadows, 0",
        "set depth_cue, 0",
        "set specular, 0.2",
        "set stick_h_scale, 1.0",
        "set stick_radius, 0.12",
        "set stick_ball, on",
        "set line_as_cylinders, on",
        "color gray60, elem C",
        f"color atomic, elem N",
        "color red, elem O",
        "color blue, elem N",
        "color yellow, elem S",
        "color green, elem F",
        "hide everything, elem H",
        "orient",
        "zoom all, 2",
        "set_view (\n    0.7071,    0.0000,    0.7071,    0.0000,\n    1.0000,    0.0000,   -0.7071,    0.0000,\n   -0.7071,    0.7071,    0.0000,    0.0000,\n    0.0000,    0.0000,   -100.0000,    1.0000\n)",
    ]

    if elems_sel:
        lines += [
            f"select framework, ({elems_sel})",
            "show spheres, framework",
            "set sphere_scale, 0.40, framework",
            "color marine, framework",
        ]

    if style:
        if style == "sticks":
            lines.append("show sticks, all")
        elif style == "surface":
            lines.append("show surface, all")

    if output_image:
        lines += ["ray 2400, 2400", f"png {img}, dpi=300"]

    return "\n".join(lines)


def build_pml_file(structure_file: Path, output_image: Optional[Path], no_gui: bool,
                  framework_elements: List[str], guest_selection: Optional[str],
                  guest_atoms: Optional[str], guest_range: Optional[str], style: str) -> Path:
    mol_name = structure_file.stem
    lines = [
        "# auto-generated by visualize_mof.py",
        "set bg_rgb, [1.0,1.0,1.0]",
        f"load {structure_file.as_posix()}, {mol_name}",
        "",
        to_pml_color_block(framework_elements, output_image, style, mol_name),
        "",
    ]

    guest_block = make_guest_selection(guest_selection, guest_atoms, guest_range, mol_name)
    if guest_block:
        lines.append(guest_block)

    if no_gui:
        lines.append("quit")

    pml_path = structure_file.with_suffix(".pml")
    pml_path.write_text("\n".join([ln for ln in lines if ln is not None]).strip() + "\n", encoding="utf-8")
    return pml_path


def prepare_single_structure(input_file: Path, timeout: int = 300) -> Path:
    """Return a PyMOL-ready structure file path."""
    ext = input_file.suffix.lower()
    if ext in {".pdb", ".mol2", ".pdbqt"}:
        return input_file

    if ext == ".cif":
        out = input_file.with_suffix(".mol2")
        obabel_to_mol2(input_file, out, timeout=timeout)
        return out

    if ext == ".xyz":
        out = input_file.with_suffix(".mol2")
        obabel_to_mol2(input_file, out, timeout=timeout)
        return out

    raise ValueError(f"Unsupported input extension: {ext}")


def run_pymol(pml_path: Path, no_gui: bool) -> None:
    cmd = ["pymol", str(pml_path)]
    if no_gui:
        cmd.insert(1, "-c")
    run_cmd(cmd, check=True)


@dataclass
class Args:
    input: Path
    trj: bool = False
    ncpus: Optional[int] = None
    timeout: int = 300
    framework: Optional[str] = None
    output: Optional[str] = None
    no_gui: bool = False
    pml_only: bool = False
    style: str = "line"
    guest_selection: Optional[str] = None
    guest_atoms: Optional[str] = None
    guest_range: Optional[str] = None
    add_h: bool = False


def parse_args() -> Args:
    p = argparse.ArgumentParser(description="MOF/IL one-click visualization helper")
    p.add_argument("input", help="Input structure: cif / xyz / mol2 / pdb")
    p.add_argument("--trj", action="store_true", help="Treat XYZ as trajectory (multi-frame)")
    p.add_argument("--ncpus", type=int, default=None, help="CPU count for trajectory conversion")
    p.add_argument("--timeout", type=int, default=300, help="Timeout for each obabel call (seconds)")
    p.add_argument("--framework", type=str, default="Zr,Ti,Cu,Fe,Co,Ni,Al,Ti,Zn,Mg,Ca,Ba,Sr,Cd,In,Ga", help="Framework elements (comma-separated)")
    p.add_argument("--output", type=str, default=None, help="Output image path (render only)")
    p.add_argument("--no-gui", action="store_true", help="Run pymol in command mode")
    p.add_argument("--pml-only", action="store_true", help="Only generate .pml file")
    p.add_argument("--style", type=str, default="line", choices=["line", "sticks", "surface"], help="PyMOL style")
    p.add_argument("--guest-selection", type=str, default=None, help="PyMOL atom selection for guest (?: 'resi 1')")
    p.add_argument("--guest-atoms", type=str, default=None, help="Guest atom ids, comma separated")
    p.add_argument("--guest-range", type=str, default=None, help="Guest residue range, e.g. 'resi 10-12'")
    p.add_argument("--add-h", action="store_true", help="Preserve/add hydrogens in conversion")
    args = p.parse_args()

    return Args(
        input=Path(args.input).resolve(),
        trj=args.trj,
        ncpus=args.ncpus,
        timeout=args.timeout,
        framework=args.framework,
        output=args.output,
        no_gui=args.no_gui,
        pml_only=args.pml_only,
        style=args.style,
        guest_selection=args.guest_selection,
        guest_atoms=args.guest_atoms,
        guest_range=args.guest_range,
        add_h=args.add_h,
    )


def main() -> int:
    args = parse_args()

    need_obabel = args.trj or args.input.suffix.lower() in {".xyz", ".cif"}
    need_pymol = not args.pml_only

    try:
        check_dependencies(require_obabel=need_obabel, require_pymol=need_pymol)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 1

    inp = args.input
    if not inp.exists():
        print(f"[ERROR] file not found: {inp}")
        return 1

    if inp.suffix.lower() not in SUPPORTED_STRUCT:
        print(f"[ERROR] unsupported file extension: {inp.suffix}")
        return 1

    framework_elements = [x.strip() for x in args.framework.split(",") if x.strip()]

    if args.trj:
        if inp.suffix.lower() != ".xyz":
            print("[ERROR] --trj option requires trajectory.xyz")
            return 1
        structure = trajectory_to_multimodel_pdb(inp, ncpus=args.ncpus, timeout=args.timeout, add_h=args.add_h)
    else:
        structure = prepare_single_structure(inp, timeout=args.timeout)

    output_image = Path(args.output).resolve() if args.output else None
    pml = build_pml_file(
        structure,
        output_image=output_image,
        no_gui=args.no_gui,
        framework_elements=framework_elements,
        guest_selection=args.guest_selection,
        guest_atoms=args.guest_atoms,
        guest_range=args.guest_range,
        style=args.style,
    )

    print(f"[OK] pml: {pml}")

    if args.pml_only:
        print("Done: pml-only mode")
        return 0

    print(f"[RUN] pymol {'-c (no-gui)' if args.no_gui else ''}: {pml}")
    try:
        run_pymol(pml, no_gui=args.no_gui)
    except RuntimeError as exc:
        print(f"[ERROR] PyMOL execution failed: {exc}")
        return 1

    print("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
