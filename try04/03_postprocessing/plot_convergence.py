#!/usr/bin/env python3
"""
plot_convergence.py
===================
Parse CP2K output and build 2-panel convergence plots.

This version is tolerant of the naming variation in current try04:
  production_ot.out -> production.out -> test_output_ot.out -> test_output.out -> simulation.input.out
and supports missing/empty dissociate outputs.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt


def parse_cp2k_output(path: Path) -> Tuple[List[int], List[float], List[float]]:
    steps: List[int] = []
    energies: List[float] = []
    max_forces: List[float] = []

    if not path.exists() or path.stat().st_size == 0:
        return steps, energies, max_forces

    step_re = re.compile(r"OPTIMIZATION STEP:\s*(\d+)|Step number\s+(\d+)")
    num_re = re.compile(r"(-?\d+\.\d+(?:[EDed][+-]?\d+)?)")
    cur_step = None

    for line in path.read_text(errors="ignore").splitlines():
        m_step = step_re.search(line)
        if m_step:
            cur_step = int(m_step.group(1) or m_step.group(2))

        if "ENERGY| Total FORCE_EVAL" in line and cur_step is not None:
            vals = num_re.findall(line)
            if vals:
                energies.append(float(vals[-1]))
                steps.append(cur_step)

        if (
            "Maximum gradient" in line
            or "RMS gradient" in line
            or "Max. force" in line
            or "Max Force" in line
        ):
            vals = num_re.findall(line)
            if vals:
                max_forces.append(float(vals[-1]))

    if energies and not steps:
        # Some outputs may contain energy lines without explicit "Step" labels in parse window.
        steps = list(range(1, len(energies) + 1))
    return steps, energies, max_forces


def parse_final_energy(path: Path) -> float | None:
    if not path.exists() or path.stat().st_size == 0:
        return None

    num_re = re.compile(r"(-?\d+\.\d+(?:[EDed][+-]?\d+)?)")
    last = None
    for line in path.read_text(errors="ignore").splitlines():
        if "ENERGY| Total FORCE_EVAL" in line:
            vals = num_re.findall(line)
            if vals:
                last = float(vals[-1])
    return last


def resolve_output_path(candidates: List[Path], label: str) -> Path:
    for p in candidates:
        if p.exists():
            return p
    print(f"[WARN] {label} output not found. Candidate used for compatibility: {candidates[0]}")
    return candidates[0]


def default_candidates(base: Path, label: str) -> List[Path]:
    return [
        base / "production_ot.out",
        base / "production.out",
        base / "test_output_ot.out",
        base / "test_output.out",
        base / "simulation.input.out",
        base / f"{label}.out",
    ]


def plot_cluster_diss(
    cluster_out: Path,
    diss_out: Path | None,
    out_png: Path,
    out_svg: Path,
    threshold: float,
) -> None:
    steps_c, energies_c, forces_c = parse_cp2k_output(cluster_out)
    steps_d, energies_d, forces_d = parse_cp2k_output(diss_out) if diss_out else ([], [], [])

    fig, (ax_e, ax_f) = plt.subplots(2, 1, figsize=(11, 8), sharex=False)

    if not steps_c:
        print(f"[WARN] No cluster energy data found in: {cluster_out}")
    if not steps_d and diss_out is not None:
        print(f"[WARN] No dissociate energy data found in: {diss_out}")

    if energies_c:
        ax_e.plot(steps_c, energies_c, "-o", label="Cluster")
    if energies_d:
        ax_e.plot(steps_d, energies_d, "-o", label="Dissociate")
    ax_e.set_title("Total Energy")
    ax_e.set_xlabel("GEO_OPT step")
    ax_e.set_ylabel("Energy (Ha)")
    if energies_c or energies_d:
        ax_e.legend()
    ax_e.grid(alpha=0.3)

    if forces_c:
        x_c = list(range(1, len(forces_c) + 1))
        ax_f.plot(x_c, forces_c, "-o", label="Cluster max gradient")
    if forces_d:
        x_d = list(range(1, len(forces_d) + 1))
        ax_f.plot(x_d, forces_d, "-o", label="Dissociate max gradient")
    ax_f.axhline(threshold, color="red", linestyle="--", label=f"{threshold} threshold")
    ax_f.set_title("SCF Convergence (max gradient proxy)")
    ax_f.set_xlabel("GEO_OPT step")
    ax_f.set_ylabel("max gradient")
    ax_f.set_yscale("log")
    if forces_c or forces_d:
        ax_f.legend()
    ax_f.grid(alpha=0.3)

    e_cluster = parse_final_energy(cluster_out)
    e_diss = parse_final_energy(diss_out) if diss_out else None
    if e_cluster is not None:
        ax_e.axhline(e_cluster, linestyle=":", color="gray", alpha=0.5, label="cluster final")
    if e_diss is not None:
        ax_e.axhline(e_diss, linestyle=":", color="black", alpha=0.5, label="dissociate final")

    if e_cluster is not None and e_diss is not None:
        delta_h = e_diss - e_cluster
        print(f"DeltaE = E(dissociate) - E(cluster) = {delta_h:.8f} Ha = {delta_h*2625.5:.3f} kJ/mol")
    elif e_cluster is not None:
        print(f"Final cluster energy: {e_cluster:.10f} Ha")

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300)
    fig.savefig(out_svg)
    print(f"Saved: {out_png}, {out_svg}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot CP2K convergence from output logs.")
    script_dir = Path(__file__).resolve().parent
    try04_root = script_dir.parent
    cluster_default_dir = try04_root / "02_calculations" / "BAMOF_2IP_cluster"
    diss_default_dir = try04_root / "02_calculations" / "BAMOF_2IP_dissociate"
    default_out = try04_root / "03_postprocessing" / "plot_convergence"

    parser.add_argument(
        "--cluster",
        default=None,
        help="Path to cluster output (default: auto-detect in 02_calculations/BAMOF_2IP_cluster)",
    )
    parser.add_argument(
        "--dissociate",
        default=None,
        help="Path to dissociate output (default: auto-detect in 02_calculations/BAMOF_2IP_dissociate)",
    )
    parser.add_argument(
        "--out-prefix",
        default=str(default_out),
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=4.5e-4,
        help="Convergence threshold for max gradient line.",
    )
    args = parser.parse_args()

    cluster_dir = cluster_default_dir
    diss_dir = diss_default_dir

    cluster_out = (
        Path(args.cluster)
        if args.cluster
        else resolve_output_path(default_candidates(cluster_dir, "cluster"), "Cluster")
    )
    if args.dissociate:
        diss_tmp = Path(args.dissociate)
        diss_out = diss_tmp if diss_tmp.exists() else None
        if diss_out is None:
            print(f"[WARN] Provided dissociate output missing: {diss_tmp}. Ignored.")
    else:
        diss_candidate = resolve_output_path(default_candidates(diss_dir, "dissociate"), "Dissociate")
        # If all missing, keep explicit skip by setting None. This is useful before diss run starts.
        diss_out = diss_candidate if diss_candidate.exists() else None

    if not cluster_out.exists():
        print(f"[WARN] Cluster output path not found: {cluster_out}")
    plot_cluster_diss(
        cluster_out,
        diss_out,
        Path(f"{args.out_prefix}.png"),
        Path(f"{args.out_prefix}.svg"),
        args.threshold,
    )


if __name__ == "__main__":
    main()
