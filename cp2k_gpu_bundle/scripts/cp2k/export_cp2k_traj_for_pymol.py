#!/usr/bin/env python3
"""Export a CP2K DCD_ALIGNED_CELL trajectory to PyMOL-friendly files.

This script is designed to be easy to run from the host workspace:

    python scripts/cp2k/export_cp2k_traj_for_pymol.py --nve-dir runs/.../nve

If MDAnalysis is not installed locally, it automatically re-executes itself
inside the ``keti-analysis`` container where MDAnalysis is available.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import warnings
from pathlib import Path, PurePosixPath, PureWindowsPath


SCRIPT_PATH = Path(__file__).resolve()
WORKSPACE_ROOT = SCRIPT_PATH.parents[2]
DEFAULT_ANALYSIS_CONTAINER = "keti-analysis"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert CP2K DCD_ALIGNED_CELL trajectory into PyMOL files."
    )
    parser.add_argument(
        "--nve-dir",
        required=True,
        help="Directory containing nve.inp and nve_traj.",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory. Defaults to results/visualization/... based on the NVE path.",
    )
    parser.add_argument(
        "--object-name",
        help="PyMOL object name. Defaults to an identifier inferred from the path.",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Write every Nth frame. Default: 1.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Maximum number of frames to export after stride. 0 means all.",
    )
    parser.add_argument(
        "--analysis-container",
        default=DEFAULT_ANALYSIS_CONTAINER,
        help=f"Container to use when local MDAnalysis is unavailable. Default: {DEFAULT_ANALYSIS_CONTAINER}.",
    )
    parser.add_argument(
        "--container-mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--host-workspace-root",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    return parser.parse_args()


def sanitize_object_name(value: str) -> str:
    out = []
    for ch in value:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    name = "".join(out).strip("_")
    return name or "cp2k_traj"


def host_path_from_workspace_path(path_str: str) -> Path:
    path_str = path_str.strip()
    if path_str.startswith("/workspace/"):
        rel = PurePosixPath(path_str).relative_to("/workspace")
        return WORKSPACE_ROOT / Path(rel.as_posix())
    if path_str == "/workspace":
        return WORKSPACE_ROOT
    return Path(path_str)


def workspace_path_from_host(path: Path) -> str:
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise ValueError(f"Path is outside workspace and cannot be container-mapped: {resolved}") from exc
    return str(PurePosixPath("/workspace") / PurePosixPath(rel.as_posix()))


def externalize_path_string(path: Path, host_workspace_root: str | None) -> str:
    resolved = path.resolve()
    if not host_workspace_root:
        return str(resolved)

    try:
        rel = resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        return str(resolved)

    if ":" in host_workspace_root or "\\" in host_workspace_root:
        return str(PureWindowsPath(host_workspace_root) / PureWindowsPath(rel.as_posix()))
    return str(Path(host_workspace_root) / Path(rel.as_posix()))


def infer_output_dir(nve_dir: Path) -> Path:
    parts = list(nve_dir.parts)
    if "runs" in parts:
        runs_idx = parts.index("runs")
        run_parts = parts[runs_idx + 1 :]
        if len(run_parts) >= 5:
            system = run_parts[0]
            seed = run_parts[1]
            return (
                WORKSPACE_ROOT
                / "results"
                / "visualization"
                / "cp2k"
                / system
                / seed
                / "pilot_smoke_nve"
            )
    return nve_dir / "pymol_export"


def infer_object_name(nve_dir: Path) -> str:
    try:
        rel = nve_dir.resolve().relative_to(WORKSPACE_ROOT / "runs")
        return sanitize_object_name("_".join(rel.parts))
    except ValueError:
        return sanitize_object_name(nve_dir.name)


def parse_nve_input(nve_inp: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in nve_inp.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("@SET "):
            parts = line.split(maxsplit=2)
            if len(parts) == 3:
                values[parts[1]] = parts[2]
    return values


def resolve_nve_paths(nve_dir: Path) -> tuple[Path, Path, Path, str]:
    nve_inp = nve_dir / "nve.inp"
    nve_traj = nve_dir / "nve_traj"
    if not nve_inp.exists():
        raise FileNotFoundError(f"Missing nve.inp in {nve_dir}")
    if not nve_traj.exists():
        raise FileNotFoundError(f"Missing nve_traj in {nve_dir}")

    settings = parse_nve_input(nve_inp)
    coord_file = settings.get("COORD_FILE")
    if not coord_file:
        raise ValueError(f"Could not find @SET COORD_FILE in {nve_inp}")

    topology = host_path_from_workspace_path(coord_file)
    if not topology.exists():
        raise FileNotFoundError(f"Resolved topology file does not exist: {topology}")

    project = settings.get("PROJECT", "cp2k_nve")
    return nve_inp, nve_traj, topology, project


def maybe_reexec_in_container(args: argparse.Namespace) -> None:
    try:
        import MDAnalysis  # noqa: F401

        return
    except Exception:
        pass

    if args.container_mode:
        raise RuntimeError("MDAnalysis is unavailable inside container mode as well.")

    nve_dir = Path(args.nve_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else infer_output_dir(nve_dir).resolve()

    cmd = [
        "docker",
        "exec",
        "-w",
        "/workspace",
        args.analysis_container,
        "python3",
        "scripts/cp2k/export_cp2k_traj_for_pymol.py",
        "--container-mode",
        "--nve-dir",
        workspace_path_from_host(nve_dir),
        "--output-dir",
        workspace_path_from_host(output_dir),
        "--stride",
        str(args.stride),
        "--max-frames",
        str(args.max_frames),
    ]
    if args.object_name:
        cmd += ["--object-name", args.object_name]
    if args.overwrite:
        cmd.append("--overwrite")
    cmd += ["--host-workspace-root", str(WORKSPACE_ROOT)]

    print(
        "MDAnalysis is not available locally. Re-running inside "
        f"{args.analysis_container}: {' '.join(shlex.quote(part) for part in cmd)}"
    )
    result = subprocess.run(cmd, check=False)
    raise SystemExit(result.returncode)


def ensure_output_dir(path: Path, overwrite: bool) -> None:
    if path.exists():
        if not overwrite and any(path.iterdir()):
            raise FileExistsError(
                f"Output directory already exists and is not empty: {path}. "
                "Use --overwrite to reuse it."
            )
    path.mkdir(parents=True, exist_ok=True)


def selected_frame_indices(total_frames: int, stride: int, max_frames: int) -> list[int]:
    if stride <= 0:
        raise ValueError("--stride must be >= 1")
    indices = list(range(0, total_frames, stride))
    if max_frames > 0:
        indices = indices[:max_frames]
    if not indices:
        raise ValueError("No frames selected. Check --stride/--max-frames.")
    return indices


def write_multiframe_xyz(universe, frame_indices: list[int], out_path: Path) -> None:
    n_atoms = universe.atoms.n_atoms
    elements = universe.atoms.elements
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for state_idx, frame_idx in enumerate(frame_indices, start=1):
            ts = universe.trajectory[frame_idx]
            handle.write(f"{n_atoms}\n")
            handle.write(
                f"state={state_idx} frame={ts.frame} time_ps={float(ts.time):.6f} "
                f"cell_a={float(ts.dimensions[0]):.6f} cell_b={float(ts.dimensions[1]):.6f} "
                f"cell_c={float(ts.dimensions[2]):.6f}\n"
            )
            for element, position in zip(elements, universe.atoms.positions):
                x, y, z = position
                handle.write(f"{element:<2} {x:15.8f} {y:15.8f} {z:15.8f}\n")


def write_pymol_macro(
    out_path: Path,
    pdb_path: Path,
    first_frame_path: Path,
    helper_macro_path: Path,
    object_name: str,
    n_states: int,
    host_workspace_root: str | None,
) -> None:
    pdb_norm = externalize_path_string(pdb_path, host_workspace_root).replace("\\", "/")
    first_norm = externalize_path_string(first_frame_path, host_workspace_root).replace("\\", "/")
    helper_norm = externalize_path_string(helper_macro_path, host_workspace_root).replace("\\", "/")

    lines = [
        "# Auto-generated by scripts/cp2k/export_cp2k_traj_for_pymol.py",
        "reinitialize",
        f'load "{pdb_norm}", {object_name}',
        f'set_name {object_name}, {object_name}',
        "bg_color white",
        "set orthoscopic, on",
        "set valence, 0",
        "hide everything, all",
        f"show sticks, {object_name}",
        f"hide sticks, ({object_name} and hydro)",
        f"show spheres, ({object_name} and elem Na)",
        f"set sphere_scale, 0.45, ({object_name} and elem Na)",
        f"color marine, ({object_name} and elem Na)",
        f"util.cbaw {object_name}",
        f"orient {object_name}",
        f"zoom {object_name}, 4",
        f'mset 1 x{n_states}',
        "set movie_fps, 10",
        "",
        "# Optional publication helper already present in this repo.",
        f'@{helper_norm}',
        f'# Example after load: pub_solvation_shell obj={object_name}, center_sel=\"elem Na\", center_rank=1, shell_cutoff=4.0, frame=1',
        "",
        "# Helpful fallbacks.",
        f'# If multi-state PDB is heavy in your PyMOL build, load the first frame only: load "{first_norm}", {object_name}_first',
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def export_with_mdanalysis(args: argparse.Namespace) -> dict[str, object]:
    import MDAnalysis as mda

    nve_dir = host_path_from_workspace_path(args.nve_dir).resolve()
    nve_inp, nve_traj, topology, project = resolve_nve_paths(nve_dir)
    output_dir = (
        host_path_from_workspace_path(args.output_dir).resolve()
        if args.output_dir
        else infer_output_dir(nve_dir).resolve()
    )
    object_name = args.object_name or infer_object_name(nve_dir)
    object_name = sanitize_object_name(object_name)

    ensure_output_dir(output_dir, args.overwrite)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        universe = mda.Universe(str(topology), str(nve_traj), format="DCD")

    frame_indices = selected_frame_indices(len(universe.trajectory), args.stride, args.max_frames)

    multistate_pdb = output_dir / f"{object_name}.multistate.pdb"
    first_frame_pdb = output_dir / f"{object_name}.frame0.pdb"
    multiframe_xyz = output_dir / f"{object_name}.multiframe.xyz"
    pymol_macro = output_dir / f"{object_name}.load.pml"
    manifest_json = output_dir / f"{object_name}.manifest.json"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with mda.Writer(
            str(multistate_pdb),
            multiframe=True,
            bonds=None,
            reindex=False,
            n_atoms=universe.atoms.n_atoms,
        ) as writer:
            for frame_idx in frame_indices:
                universe.trajectory[frame_idx]
                writer.write(universe)

        universe.trajectory[frame_indices[0]]
        with mda.Writer(
            str(first_frame_pdb),
            multiframe=False,
            bonds=None,
            reindex=False,
            n_atoms=universe.atoms.n_atoms,
        ) as writer:
            writer.write(universe)

    write_multiframe_xyz(universe, frame_indices, multiframe_xyz)
    write_pymol_macro(
        out_path=pymol_macro,
        pdb_path=multistate_pdb,
        first_frame_path=first_frame_pdb,
        helper_macro_path=WORKSPACE_ROOT / "scripts" / "visualization" / "pymol_pub_na_sulfone.pml",
        object_name=object_name,
        n_states=len(frame_indices),
        host_workspace_root=args.host_workspace_root,
    )

    manifest = {
        "nve_dir": externalize_path_string(nve_dir, args.host_workspace_root),
        "nve_input": externalize_path_string(nve_inp, args.host_workspace_root),
        "trajectory": externalize_path_string(nve_traj, args.host_workspace_root),
        "topology": externalize_path_string(topology, args.host_workspace_root),
        "project": project,
        "object_name": object_name,
        "frames_total": len(universe.trajectory),
        "frames_exported": len(frame_indices),
        "frame_indices": frame_indices,
        "stride": args.stride,
        "max_frames": args.max_frames,
        "outputs": {
            "multistate_pdb": externalize_path_string(multistate_pdb, args.host_workspace_root),
            "first_frame_pdb": externalize_path_string(first_frame_pdb, args.host_workspace_root),
            "multiframe_xyz": externalize_path_string(multiframe_xyz, args.host_workspace_root),
            "pymol_macro": externalize_path_string(pymol_macro, args.host_workspace_root),
        },
    }
    manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    return manifest


def main() -> None:
    args = parse_args()
    maybe_reexec_in_container(args)
    manifest = export_with_mdanalysis(args)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
