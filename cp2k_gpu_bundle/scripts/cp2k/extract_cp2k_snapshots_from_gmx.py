#!/usr/bin/env python3
import argparse
import csv
import json
import logging
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import MDAnalysis as mda
import numpy as np
from MDAnalysis.lib.distances import distance_array
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from scripts.ops.classical_state_gate import (
    classical_state_is_cp2k_eligible,
    infer_target_density,
    load_gate_policy,
    load_qc_json,
)

console = Console()
AVOGADRO = 6.02214076e23
FORMAL_CHARGE_BY_RESNAME = {
    "NA": 1,
    "NAP": 1,
    "PF6": -1,
}


def setup_logger(log_file: Path, verbose: bool) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("extract_cp2k_snapshots_from_gmx")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    console_handler = RichHandler(console=console, rich_tracebacks=True)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def infer_element(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z]", "", name or "")
    if not cleaned:
        return "X"
    upper = cleaned.upper()
    if upper.startswith("NA"):
        return "Na"
    if upper.startswith("CL"):
        return "Cl"
    if upper.startswith("SI"):
        return "Si"
    if len(cleaned) >= 2 and cleaned[1].islower():
        return cleaned[:2]
    return cleaned[0].upper()


def write_xyz(path: Path, atoms, coords: np.ndarray | None = None) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write(f"{len(atoms)}\n")
        handle.write("Generated for CP2K snapshot extraction\n")
        xyz = atoms.positions if coords is None else coords
        for atom, pos in zip(atoms, xyz, strict=True):
            try:
                element = atom.element
            except Exception:
                element = ""
            element = element if element else infer_element(atom.name)
            x, y, z = pos
            handle.write(f"{element:2s} {x:16.8f} {y:16.8f} {z:16.8f}\n")


def write_cell(path: Path, dimensions, periodic: str = "XYZ") -> None:
    a, b, c = dimensions[:3]
    path.write_text(
        "&CELL\n"
        f"  ABC {a:.8f} {b:.8f} {c:.8f}\n"
        f"  PERIODIC {periodic}\n"
        "&END CELL\n",
        encoding="utf-8",
    )


def formal_residue_charge(residue) -> int:
    return FORMAL_CHARGE_BY_RESNAME.get(str(residue.resname).upper(), 0)


def validate_structure_for_cp2k(universe: mda.Universe, min_density_g_cm3: float, max_edge_nm: float) -> tuple[float, float]:
    ts = universe.trajectory.ts
    box_lengths_a = np.asarray(ts.dimensions[:3], dtype=float)
    box_lengths_nm = box_lengths_a / 10.0
    max_edge_nm_value = float(box_lengths_nm.max())
    volume_cm3 = float(ts.volume) * 1.0e-24
    total_mass_g = float(universe.atoms.masses.sum()) / AVOGADRO
    density_g_cm3 = total_mass_g / volume_cm3
    if max_edge_nm_value > max_edge_nm:
        raise ValueError(
            f"Source box edge {max_edge_nm_value:.3f} nm exceeds allowed maximum {max_edge_nm:.3f} nm"
        )
    if density_g_cm3 < min_density_g_cm3:
        raise ValueError(
            f"Source density {density_g_cm3:.4f} g/cm3 is below allowed minimum {min_density_g_cm3:.4f} g/cm3"
        )
    return density_g_cm3, max_edge_nm_value


def choose_center_atom(atoms, center_resname: str):
    target_resname = center_resname.upper()
    candidates = [atom for atom in atoms if str(atom.resname).upper() == target_resname]
    if not candidates:
        candidates = [atom for atom in atoms if infer_element(atom.name).upper() == target_resname]
    if not candidates:
        raise ValueError(f"No center atom found for center_resname={center_resname}")
    box_center = np.asarray(atoms.dimensions[:3], dtype=float) / 2.0
    return min(candidates, key=lambda atom: float(np.linalg.norm(atom.position - box_center)))


def cluster_from_center(universe: mda.Universe, atoms, center_resname: str, radius_a: float, padding_a: float, neutralize_charge: bool):
    center_atom = choose_center_atom(atoms, center_resname)
    selected_residues = []
    selected_ids = set()
    for residue in universe.residues:
        distances = distance_array(center_atom.position[None, :], residue.atoms.positions, box=universe.trajectory.ts.dimensions)
        if float(distances.min()) <= radius_a:
            selected_residues.append(residue)
            selected_ids.add(int(residue.resid))

    if center_atom.residue.resid not in selected_ids:
        selected_residues.append(center_atom.residue)
        selected_ids.add(int(center_atom.residue.resid))

    def current_charge() -> int:
        return sum(formal_residue_charge(residue) for residue in selected_residues)

    if neutralize_charge:
        charge = current_charge()
        while charge != 0:
            target_resname = "PF6" if charge > 0 else "NA"
            candidates = []
            for residue in universe.residues:
                if int(residue.resid) in selected_ids:
                    continue
                if str(residue.resname).upper() != target_resname:
                    continue
                distances = distance_array(center_atom.position[None, :], residue.atoms.positions, box=universe.trajectory.ts.dimensions)
                candidates.append((float(distances.min()), residue))
            if not candidates:
                break
            _, chosen = min(candidates, key=lambda row: row[0])
            selected_residues.append(chosen)
            selected_ids.add(int(chosen.resid))
            charge = current_charge()

    atom_indices: list[int] = []
    for residue in selected_residues:
        atom_indices.extend(int(atom.index) for atom in residue.atoms)
    atom_indices = sorted(atom_indices)
    cluster_atoms = universe.atoms[atom_indices]
    coords = cluster_atoms.positions.copy()
    mins = coords.min(axis=0)
    coords = coords - mins + padding_a / 2.0
    spans = coords.max(axis=0) - coords.min(axis=0)
    box_len = float(spans.max() + padding_a)
    shift = (box_len - spans) / 2.0 - coords.min(axis=0)
    coords = coords + shift
    return {
        "atoms": cluster_atoms,
        "coords": coords,
        "box": np.array([box_len, box_len, box_len], dtype=float),
        "periodic": "XYZ",
        "charge": sum(formal_residue_charge(residue) for residue in selected_residues),
        "center_resid": int(center_atom.resid),
        "center_resname": str(center_atom.resname),
        "natoms": int(len(cluster_atoms)),
        "nresidues": int(len(selected_residues)),
    }


def choose_frames(universe: mda.Universe, start_ps: float, min_separation_ps: float, n_snapshots: int) -> list[tuple[int, float]]:
    eligible: list[tuple[int, float]] = []
    for ts in universe.trajectory:
        if float(ts.time) >= start_ps:
            eligible.append((int(ts.frame), float(ts.time)))
    if not eligible:
        return []

    chosen: list[tuple[int, float]] = []
    last_time = None
    for frame, time_ps in eligible:
        if last_time is None or time_ps - last_time >= min_separation_ps:
            chosen.append((frame, time_ps))
            last_time = time_ps
        if len(chosen) >= n_snapshots:
            break

    if len(chosen) < n_snapshots and eligible:
        for frame, time_ps in reversed(eligible):
            if (frame, time_ps) not in chosen:
                chosen.append((frame, time_ps))
            if len(chosen) >= n_snapshots:
                break
        chosen = sorted(chosen, key=lambda x: x[1])[:n_snapshots]
    return chosen


def main() -> int:
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", required=True)
    ap.add_argument("--traj", required=True)
    ap.add_argument("--system", required=True)
    ap.add_argument("--seed-number", type=int, required=True)
    ap.add_argument("--source-stage", default="npt")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--n-snapshots", type=int, default=1)
    ap.add_argument("--start-ps", type=float, default=0.0)
    ap.add_argument("--min-separation-ps", type=float, default=250.0)
    ap.add_argument("--selection", default="all")
    ap.add_argument("--mode", choices=["full", "cluster"], default="full")
    ap.add_argument("--center-resname", default="NA")
    ap.add_argument("--cluster-radius-a", type=float, default=6.0)
    ap.add_argument("--cluster-padding-a", type=float, default=12.0)
    ap.add_argument("--neutralize-charge", action="store_true")
    ap.add_argument("--min-density-g-cm3", type=float, default=0.8)
    ap.add_argument("--max-edge-nm", type=float, default=5.0)
    ap.add_argument("--qc-json", default="")
    ap.add_argument("--policy", default="inputs/policy/classical_gate.yml")
    ap.add_argument("--skip-eligibility-check", action="store_true")
    ap.add_argument("--log-file", default="logs/cp2k/extract_cp2k_snapshots_from_gmx.log")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logger = setup_logger(Path(args.log_file), args.verbose)
    top = Path(args.top)
    traj = Path(args.traj)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not top.exists() or not traj.exists():
        logger.error("Missing input(s): top=%s traj=%s", top, traj)
        return 2

    logger.info("Loading topology=%s trajectory=%s", top, traj)
    universe = mda.Universe(str(top), str(traj))
    atoms = universe.select_atoms(args.selection)
    policy = load_gate_policy(args.policy)
    density_g_cm3, max_edge_nm = validate_structure_for_cp2k(universe, args.min_density_g_cm3, args.max_edge_nm)

    eligibility_payload = {
        "checked": False,
        "eligible": True,
        "hard_fail": [],
        "soft_warn": [],
    }
    if not args.skip_eligibility_check:
        qc_json_path = Path(args.qc_json) if args.qc_json else Path(
            f"runs/{args.system}/seed-{args.seed_number}/gromacs/qc_summary_{args.source_stage}.json"
        )
        if not qc_json_path.exists():
            logger.error("Missing QC JSON for source-stage eligibility: %s", qc_json_path)
            return 4
        qc_payload = load_qc_json(qc_json_path)
        gate = classical_state_is_cp2k_eligible(
            system_id=args.system,
            seed=args.seed_number,
            source_stage=args.source_stage,
            qc_payload=qc_payload,
            observed_density_g_cm3=density_g_cm3,
            observed_edge_nm=max_edge_nm,
            target_density_g_cm3=infer_target_density(args.system),
            policy=policy,
        )
        eligibility_payload = {"checked": True, **gate.as_dict(), "qc_json": str(qc_json_path)}
        if not gate.eligible:
            logger.error("Source-stage is not CP2K-eligible: %s", gate.hard_fail)
            return 5

    chosen = choose_frames(universe, args.start_ps, args.min_separation_ps, args.n_snapshots)
    if not chosen:
        logger.error("No frames matched start-ps=%s", args.start_ps)
        return 3

    manifest_path = out_dir / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "snapshot_id", "frame", "time_ps", "mode", "natoms", "net_charge", "periodic",
            "coord_file", "cell_file", "source_top", "source_traj", "source_stage", "eligible"
        ])
        for idx, (frame, time_ps) in enumerate(chosen, start=1):
            universe.trajectory[frame]
            snap_dir = out_dir / f"snap_{idx:04d}"
            snap_dir.mkdir(parents=True, exist_ok=True)
            coord_path = snap_dir / "coords.xyz"
            cell_path = snap_dir / "cell.inc"
            if args.mode == "cluster":
                cluster = cluster_from_center(
                    universe=universe,
                    atoms=atoms,
                    center_resname=args.center_resname,
                    radius_a=args.cluster_radius_a,
                    padding_a=args.cluster_padding_a,
                    neutralize_charge=args.neutralize_charge,
                )
                write_xyz(coord_path, cluster["atoms"], cluster["coords"])
                write_cell(cell_path, cluster["box"], periodic=cluster["periodic"])
                writer.writerow([
                    snap_dir.name, frame, time_ps, args.mode, cluster["natoms"], cluster["charge"], cluster["periodic"],
                    coord_path, cell_path, top, traj, args.source_stage, eligibility_payload["eligible"],
                ])
                logger.info(
                    "Wrote cluster snapshot %s frame=%s time_ps=%.3f natoms=%s charge=%s center=%s/%s",
                    snap_dir.name, frame, time_ps, cluster["natoms"], cluster["charge"],
                    cluster["center_resname"], cluster["center_resid"]
                )
            else:
                write_xyz(coord_path, atoms)
                write_cell(cell_path, universe.trajectory.ts.dimensions)
                writer.writerow([
                    snap_dir.name, frame, time_ps, args.mode, len(atoms), 0, "XYZ",
                    coord_path, cell_path, top, traj, args.source_stage, eligibility_payload["eligible"],
                ])
                logger.info("Wrote full snapshot %s frame=%s time_ps=%.3f", snap_dir.name, frame, time_ps)

    (out_dir / "eligibility.json").write_text(
        json.dumps(
            {
                "system": args.system,
                "seed": args.seed_number,
                "source_stage": args.source_stage,
                "density_g_cm3": density_g_cm3,
                "max_edge_nm": max_edge_nm,
                "eligibility": eligibility_payload,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    table = Table(title="CP2K Snapshots Extracted")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("System", args.system)
    table.add_row("Seed", str(args.seed_number))
    table.add_row("Mode", args.mode)
    table.add_row("Snapshots", str(len(chosen)))
    table.add_row("Source density g/cm3", f"{density_g_cm3:.4f}")
    table.add_row("Source max edge nm", f"{max_edge_nm:.3f}")
    table.add_row("Output", str(out_dir))
    table.add_row("Elapsed s", f"{time.time() - t0:.2f}")
    console.print(table)
    console.print(Panel.fit(f"Snapshot manifest written to {manifest_path}", title="DONE"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
