#!/usr/bin/env python3
import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console()
HARTREE_TO_MEV = 27.211386245988 * 1000.0
EXIT_PASS = 0
EXIT_MISSING = 2
EXIT_PARSE = 3
EXIT_NOT_EVALUABLE = 5
EXIT_FAIL = 4


def setup_logger(log_file: Path, verbose: bool) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("check_nve_drift")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    console_handler = RichHandler(console=console, rich_tracebacks=True)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def parse_header_indices(lines: list[str], logger: logging.Logger) -> tuple[int, int, int | None, list[str]]:
    header_line = None
    for line in lines:
        if line.startswith("#") and "Time" in line:
            header_line = line
            break
    if header_line is None:
        logger.error("Could not find .ener header line")
        raise SystemExit(EXIT_PARSE)

    raw = header_line.lstrip("#").strip().split()
    merged: list[str] = []
    idx = 0
    while idx < len(raw):
        if idx + 1 < len(raw) and raw[idx] == "Step" and raw[idx + 1].startswith("Nr"):
            merged.append("Step Nr.")
            idx += 2
            continue
        if idx + 1 < len(raw) and raw[idx] == "Cons" and raw[idx + 1].startswith("Qty"):
            merged.append("Cons Qty[a.u.]")
            idx += 2
            continue
        merged.append(raw[idx])
        idx += 1

    time_idx = None
    etot_idx = None
    ekin_idx = None
    kinetic_names = {
        "Kin.[a.u.]",
        "Ekin[a.u.]",
        "E_kin[a.u.]",
        "Kin[a.u.]",
    }
    total_names = {
        "Etot[a.u.]",
        "E_tot[a.u.]",
        "Cons Qty[a.u.]",
        "Cons.Qty[a.u.]",
        "TotalEnergy[a.u.]",
    }
    for pos, name in enumerate(merged):
        if name in {"Time[fs]", "Time"} and time_idx is None:
            time_idx = pos
        if name in total_names and etot_idx is None:
            etot_idx = pos
        if name in kinetic_names and ekin_idx is None:
            ekin_idx = pos
    if time_idx is None or etot_idx is None:
        logger.error("Failed to parse .ener header: %s", merged)
        raise SystemExit(EXIT_PARSE)
    return time_idx, etot_idx, ekin_idx, merged


def write_json(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--ener", required=True)
    ap.add_argument("--natoms", type=int, required=True)
    ap.add_argument("--threshold-mev-atom-ps", type=float, default=0.5)
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--min-duration-ps", type=float, default=0.05)
    ap.add_argument("--discard-frac", type=float, default=0.10)
    ap.add_argument("--json-out")
    ap.add_argument("--log-file", default="logs/cp2k/check_nve_drift.log")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logger = setup_logger(Path(args.log_file), args.verbose)
    ener = Path(args.ener)
    json_out = Path(args.json_out) if args.json_out else None
    if not ener.exists():
        logger.error("Missing energy file: %s", ener)
        return EXIT_MISSING

    lines = ener.read_text(encoding="utf-8", errors="ignore").splitlines()
    time_idx, etot_idx, ekin_idx, header = parse_header_indices(lines, logger)

    times_fs = []
    energies_ha = []
    kinetic_ha = []
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) <= max(time_idx, etot_idx, ekin_idx or 0):
            continue
        try:
            times_fs.append(float(parts[time_idx]))
            energies_ha.append(float(parts[etot_idx]))
            if ekin_idx is not None:
                kinetic_ha.append(float(parts[ekin_idx]))
        except ValueError:
            continue

    payload = {
        "ener": str(ener),
        "natoms": args.natoms,
        "threshold_mev_atom_ps": args.threshold_mev_atom_ps,
        "min_points": args.min_points,
        "min_duration_ps": args.min_duration_ps,
        "discard_frac": args.discard_frac,
        "header": header,
        "elapsed_s": round(time.time() - t0, 3),
    }

    if len(times_fs) < max(args.min_points, 2):
        payload["status"] = "NOT_EVALUABLE"
        payload["reason"] = f"Too few points ({len(times_fs)} < {args.min_points})"
        write_json(json_out, payload)
        logger.warning("%s", payload["reason"])
        return EXIT_NOT_EVALUABLE

    time_ps = np.asarray(times_fs, dtype=float) / 1000.0
    energy_ha = np.asarray(energies_ha, dtype=float)
    discard_idx = min(max(int(len(time_ps) * args.discard_frac), 0), max(len(time_ps) - 2, 0))
    time_fit = time_ps[discard_idx:]
    energy_fit = energy_ha[discard_idx:]

    duration_ps = float(time_fit[-1] - time_fit[0]) if len(time_fit) >= 2 else 0.0
    if duration_ps < args.min_duration_ps:
        payload["status"] = "NOT_EVALUABLE"
        payload["reason"] = f"Trajectory too short after discard ({duration_ps:.6f} ps < {args.min_duration_ps:.6f} ps)"
        payload["points"] = int(len(time_ps))
        payload["fit_points"] = int(len(time_fit))
        payload["duration_ps"] = duration_ps
        write_json(json_out, payload)
        logger.warning("%s", payload["reason"])
        return EXIT_NOT_EVALUABLE

    slope_ha_ps = float(np.polyfit(time_fit, energy_fit, 1)[0])
    slope_mev_atom_ps = slope_ha_ps * HARTREE_TO_MEV / args.natoms
    passed = abs(slope_mev_atom_ps) <= args.threshold_mev_atom_ps

    kinetic_mean_ha = None
    kinetic_percent_per_ps = None
    if kinetic_ha:
        kinetic_mean_ha = float(np.mean(np.asarray(kinetic_ha[discard_idx:], dtype=float)))
        if kinetic_mean_ha != 0.0:
            kinetic_percent_per_ps = abs(slope_ha_ps) / kinetic_mean_ha * 100.0

    payload.update(
        {
            "status": "PASS" if passed else "FAIL",
            "points": int(len(time_ps)),
            "fit_points": int(len(time_fit)),
            "discard_idx": int(discard_idx),
            "duration_ps": duration_ps,
            "slope_ha_ps": slope_ha_ps,
            "slope_mev_atom_ps": slope_mev_atom_ps,
            "mean_kinetic_ha": kinetic_mean_ha,
            "slope_percent_of_kinetic_per_ps": kinetic_percent_per_ps,
        }
    )
    write_json(json_out, payload)

    table = Table(title="NVE Drift Check")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Status", payload["status"])
    table.add_row("Points", str(payload["points"]))
    table.add_row("Fit points", str(payload["fit_points"]))
    table.add_row("Discard idx", str(payload["discard_idx"]))
    table.add_row("Duration ps", f"{payload['duration_ps']:.6f}")
    table.add_row("Slope (Ha/ps)", f"{payload['slope_ha_ps']:.8e}")
    table.add_row("Slope (meV/atom/ps)", f"{payload['slope_mev_atom_ps']:.6f}")
    table.add_row("Threshold", f"{args.threshold_mev_atom_ps:.6f}")
    if kinetic_percent_per_ps is not None:
        table.add_row("Slope / mean kinetic (%/ps)", f"{kinetic_percent_per_ps:.6f}")
    table.add_row("Header", " | ".join(header))
    table.add_row("Elapsed s", f"{time.time() - t0:.2f}")
    console.print(table)

    if not passed:
        logger.error("NVE drift failed: %.6f meV/atom/ps", slope_mev_atom_ps)
        return EXIT_FAIL
    logger.info("NVE drift passed")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
