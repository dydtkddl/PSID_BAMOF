#!/usr/bin/env python3
"""plot_convergence.py
Parse CP2K GEO_OPT logs and build 2-panel convergence plots.
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

    step_re = re.compile(r"Step\s+(\d+)")
    num_re = re.compile(r"(-?\d+\.\d+(?:[EDed][+-]?\d+)?)")
    cur_step = None

    for line in path.read_text(errors="ignore").splitlines():
        m = step_re.search(line)
        if m:
            cur_step = int(m.group(1))
        if "ENERGY| Total FORCE_EVAL" in line and cur_step is not None:
            vals = num_re.findall(line)
            if vals:
                energies.append(float(vals[-1]))
                steps.append(cur_step)
        if "Max. force" in line or "Max Force" in line:
            vals = num_re.findall(line)
            if vals:
                max_forces.append(float(vals[-1]))

    return steps, energies, max_forces


def parse_final_energy(path: Path) -> float | None:
    num_re = re.compile(r"(-?\d+\.\d+(?:[EDed][+-]?\d+)?)")
    if not path.exists():
        return None
    last = None
    for line in path.read_text(errors="ignore").splitlines():
        if "ENERGY| Total FORCE_EVAL" in line:
            vals = num_re.findall(line)
            if vals:
                last = float(vals[-1])
    return last


def plot_cluster_diss(cluster_out: Path, diss_out: Path, out_png: Path, out_svg: Path) -> None:
    sc, ec, fc = parse_cp2k_output(cluster_out)
    sd, ed, fd = parse_cp2k_output(diss_out)

    fig, (ax_e, ax_f) = plt.subplots(2, 1, figsize=(11, 8), sharex=False)

    if ec:
        ax_e.plot(sc, ec, "-o", label="Cluster")
    if ed:
        ax_e.plot(sd, ed, "-o", label="Dissociate")
    ax_e.set_title("Total Energy")
    ax_e.set_xlabel("GEO_OPT step")
    ax_e.set_ylabel("Energy (Ha)")
    if ec or ed:
        ax_e.legend()
    ax_e.grid(alpha=0.3)

    if fc:
        ax_f.plot(list(range(len(fc))), fc, "-o", label="Cluster max force")
    if fd:
        ax_f.plot(list(range(len(fd))), fd, "-o", label="Dissociate max force")
    ax_f.axhline(4.5e-4, color="red", linestyle="--", label="4.5e-4 threshold")
    ax_f.set_title("SCF Convergence (max force proxy)")
    ax_f.set_xlabel("SCF iteration")
    ax_f.set_ylabel("max force")
    ax_f.set_yscale("log")
    if fc or fd:
        ax_f.legend()
    ax_f.grid(alpha=0.3)

    e_cluster = parse_final_energy(cluster_out)
    e_diss = parse_final_energy(diss_out)
    if e_cluster is not None:
        ax_e.axhline(e_cluster, linestyle=":", color="gray", alpha=0.5, label="cluster ref")
    if e_diss is not None:
        ax_e.axhline(e_diss, linestyle=":", color="gray", alpha=0.5, label="diss ref")

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300)
    fig.savefig(out_svg)
    print(f"Saved: {out_png}, {out_svg}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cluster",
        default="D:/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster/simulation.input.out",
    )
    parser.add_argument(
        "--dissociate",
        default="D:/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate/simulation.input.out",
    )
    parser.add_argument(
        "--out-prefix",
        default="D:/PSID_BAMOF/try04/03_postprocessing/plot_convergence",
    )
    args = parser.parse_args()

    plot_cluster_diss(Path(args.cluster), Path(args.dissociate), Path(f"{args.out_prefix}.png"), Path(f"{args.out_prefix}.svg"))


if __name__ == "__main__":
    main()
