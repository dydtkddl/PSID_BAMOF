#!/usr/bin/env python3
"""fig_ediss_comparison.py
Build bar chart for E_diss references and current try04 result.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
HA_TO_KJ = 2625.499638

REF = {
    "gas": 225.06,
    "mof1ip": 23.05,
    "bamof1ip": 17.77,
}


def parse_energy(path: Path):
    if not path.exists():
        return None
    text = path.read_text(errors="ignore")
    m = re.findall(r"ENERGY\\| Total FORCE_EVAL \\( QS \\) energy \\[hartree\\]\\s+([+-]?[0-9]+\\.[0-9]+(?:[eEdD][+-]?[0-9]+)?)", text)
    if not m:
        return None
    return float(m[-1])


def try04_ediss():
    c = parse_energy(ROOT / "02_calculations/BAMOF_2IP_cluster/simulation.input.out")
    d = parse_energy(ROOT / "02_calculations/BAMOF_2IP_dissociate/simulation.input.out")
    if c is None or d is None:
        return None
    return (d - c) * HA_TO_KJ


def main():
    vals = {
        "Gas-phase": REF["gas"],
        "MOF + 1IP": REF["mof1ip"],
        "BA-MOF + 1IP": REF["bamof1ip"],
        "BA-MOF + 2IP": None,
    }
    v4 = try04_ediss()
    if v4 is not None:
        vals["BA-MOF + 2IP"] = v4

    colors = ["#808080", "#1f77b4", "#d62728", "#9467bd"]
    labels = list(vals.keys())
    data = [vals[k] for k in labels]
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (x, y, c) in enumerate(zip(labels, data, colors)):
        if y is None:
            ax.bar(i, 0, color=c, alpha=0.3)
            ax.text(i, 2, "TBD", ha="center", va="bottom", weight="bold")
        else:
            ax.bar(i, y, color=c)
            ax.text(i, y, f"{y:.2f}", ha="center", va="bottom", color="white", fontsize=9, weight="bold")

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=0)
    ax.set_ylabel("E_diss (kJ/mol)")
    ax.set_title("try04 E_diss comparison")
    fig.tight_layout()

    out_png = Path(__file__).with_name("ediss_comparison.png")
    out_svg = Path(__file__).with_name("ediss_comparison.svg")
    fig.savefig(out_png, dpi=300)
    fig.savefig(out_svg)
    print(f"Saved: {out_png}")
    print(f"Saved: {out_svg}")


if __name__ == "__main__":
    main()
