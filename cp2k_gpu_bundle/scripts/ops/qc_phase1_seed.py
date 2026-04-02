#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops.classical_state_gate import (
    classical_state_is_cp2k_eligible,
    evaluate_density_plateau,
    infer_target_density,
    load_gate_policy,
    read_last_gro_box_edge_nm,
    scan_log_hits,
    summarize_series,
)


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True)


def run_shell(cmd: str) -> subprocess.CompletedProcess:
    return run_cmd(["bash", "-lc", cmd])


def parse_xvg_series(xvg_path: Path) -> list[tuple[float, float]]:
    data: list[tuple[float, float]] = []
    for raw in xvg_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "@")):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            data.append((float(parts[0]), float(parts[1])))
        except ValueError:
            continue
    return data


def extract_energy_term(edr: Path, out_xvg: Path, term: str) -> subprocess.CompletedProcess:
    out_xvg.parent.mkdir(parents=True, exist_ok=True)
    quoted_term = term.replace("'", "'\"'\"'")
    cmd = (
        f"printf '{quoted_term}\\n0\\n' | "
        f"docker compose exec -T gmx bash -lc "
        f"\"cd /workspace && gmx energy -f {edr.as_posix()} -o {out_xvg.as_posix()} -xvg none\""
    )
    return run_shell(cmd)


def fail_payload(
    *,
    system: str,
    seed: int,
    source_stage: str,
    output_json: Path,
    reason: str,
    detail: dict[str, Any],
    return_code: int,
) -> int:
    payload = {
        "system": system,
        "seed": seed,
        "source_stage": source_stage,
        "pass": False,
        "source_stage_valid": False,
        "cp2k_handoff_ready": False,
        "reason": reason,
        "details": detail,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return return_code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--source-stage", default="npt")
    ap.add_argument("--temperature-k", type=float, default=330.0)
    ap.add_argument("--target-density-g-cm3", type=float, default=None)
    ap.add_argument("--policy", default="inputs/policy/classical_gate.yml")
    ap.add_argument("--lock", default="study_lock.yml")
    ap.add_argument("--output-json", required=True)
    args = ap.parse_args()

    run_dir = Path(f"runs/{args.system}/seed-{args.seed}/gromacs")
    qc_dir = run_dir / "qc" / args.source_stage
    qc_dir.mkdir(parents=True, exist_ok=True)
    output_json = Path(args.output_json)
    policy = load_gate_policy(args.policy)
    stage = args.source_stage

    required = {
        "edr": run_dir / f"{stage}.edr",
        "log": run_dir / f"{stage}.log",
        "gro": run_dir / f"{stage}.gro",
        "tpr": run_dir / f"{stage}.tpr",
    }
    missing = [k for k, path in required.items() if not path.exists()]
    if missing:
        return fail_payload(
            system=args.system,
            seed=args.seed,
            source_stage=stage,
            output_json=output_json,
            reason="missing_required_files",
            detail={"missing": missing, "required": {k: str(v) for k, v in required.items()}},
            return_code=2,
        )

    term_map = {
        "density": ("Density", qc_dir / f"{stage}_density.xvg"),
        "temperature": ("Temperature", qc_dir / f"{stage}_temperature.xvg"),
        "pressure": ("Pressure", qc_dir / f"{stage}_pressure.xvg"),
        "potential": ("Potential", qc_dir / f"{stage}_potential.xvg"),
    }
    extract_failures: dict[str, str] = {}
    for key, (term, out_xvg) in term_map.items():
        result = extract_energy_term(required["edr"], out_xvg, term)
        if result.returncode != 0 or not out_xvg.exists():
            extract_failures[key] = (result.stderr or result.stdout or "").strip()[-500:]
    if extract_failures:
        return fail_payload(
            system=args.system,
            seed=args.seed,
            source_stage=stage,
            output_json=output_json,
            reason="gmx_energy_extract_failed",
            detail=extract_failures,
            return_code=3,
        )

    density_data = parse_xvg_series(term_map["density"][1])
    temp_data = parse_xvg_series(term_map["temperature"][1])
    pressure_data = parse_xvg_series(term_map["pressure"][1])
    potential_data = parse_xvg_series(term_map["potential"][1])

    density_tail = density_data[max(0, int(len(density_data) * 0.6)) :]
    temp_tail = temp_data[max(0, int(len(temp_data) * 0.7)) :]
    pressure_tail = pressure_data[max(0, int(len(pressure_data) * 0.7)) :]
    potential_tail = potential_data[max(0, int(len(potential_data) * 0.7)) :]

    plateau_cfg = policy.get("density_plateau", {})
    density_plateau = evaluate_density_plateau(
        density_tail=density_tail,
        slope_limit_g_cm3_per_ps=float(plateau_cfg.get("slope_limit_g_cm3_per_ps", 2.0e-4)),
        cv_limit=float(plateau_cfg.get("cv_limit", 0.03)),
    )

    temp_vals = [v for _, v in temp_tail]
    pressure_vals = [v for _, v in pressure_tail]
    potential_vals = [v for _, v in potential_tail]

    temp_mean = float("nan") if not temp_vals else sum(temp_vals) / len(temp_vals)
    pressure_mean = float("nan") if not pressure_vals else sum(pressure_vals) / len(pressure_vals)
    pressure_stdev = (
        float("nan")
        if not pressure_vals
        else (sum((x - pressure_mean) ** 2 for x in pressure_vals) / len(pressure_vals)) ** 0.5
    )
    potential_finite = bool(potential_vals) and all(math.isfinite(v) for v in potential_vals)

    temp_ok = math.isfinite(temp_mean) and abs(temp_mean - args.temperature_k) <= float(
        policy.get("temperature", {}).get("tolerance_k", 15.0)
    )
    pressure_ok = (
        math.isfinite(pressure_mean)
        and abs(pressure_mean) <= float(policy.get("pressure", {}).get("abs_mean_bar_limit", 1500.0))
        and math.isfinite(pressure_stdev)
        and pressure_stdev <= float(policy.get("pressure", {}).get("stdev_bar_limit", 3000.0))
    )
    potential_ok = potential_finite

    log_hits = scan_log_hits([required["log"], run_dir / "em.log", run_dir / "nvt.log"], policy)
    logs_ok = len(log_hits) == 0

    observed_density_g_cm3 = density_plateau.get("mean_g_cm3", float("nan"))
    source_box_edge_nm = read_last_gro_box_edge_nm(required["gro"])
    physical_cfg = policy.get("physical", {})
    min_density = float(physical_cfg.get("min_density_g_cm3", 0.8))
    max_density = float(physical_cfg.get("max_density_g_cm3", 1.8))
    max_edge_nm = float(physical_cfg.get("max_edge_nm", 5.0))

    density_physical_ok = (
        math.isfinite(observed_density_g_cm3) and min_density <= observed_density_g_cm3 <= max_density
    )
    box_edge_ok = math.isfinite(source_box_edge_nm) and source_box_edge_nm <= max_edge_nm

    target_density = args.target_density_g_cm3
    if target_density is None:
        target_density = infer_target_density(args.system, args.lock)

    payload: dict[str, Any] = {
        "system": args.system,
        "seed": args.seed,
        "source_stage": stage,
        "pass": False,
        "source_stage_valid": False,
        "cp2k_handoff_ready": False,
        "gates": {
            "density_plateau_ok": bool(density_plateau.get("ok")),
            "temperature_ok": temp_ok,
            "pressure_ok": pressure_ok,
            "potential_ok": potential_ok,
            "logs_ok": logs_ok,
            "density_physical_ok": density_physical_ok,
            "box_edge_ok": box_edge_ok,
        },
        "metrics": {
            "density_tail_summary_raw_kg_m3": summarize_series(density_tail),
            "density_tail_summary_g_cm3": (
                {
                    k: (v / 1000.0 if k in {"mean", "stdev", "min", "max"} else v)
                    for k, v in summarize_series(density_tail).items()
                }
            ),
            "density_tail_slope_raw_kg_m3_per_ps": density_plateau.get("slope_raw_kg_m3_per_ps"),
            "density_tail_slope_g_cm3_per_ps": density_plateau.get("slope_g_cm3_per_ps"),
            "density_tail_cv": density_plateau.get("cv"),
            "source_density_g_cm3": observed_density_g_cm3,
            "source_box_edge_nm": source_box_edge_nm,
            "target_density_g_cm3": target_density,
            "temperature_tail_summary": summarize_series(temp_tail),
            "pressure_tail_summary": summarize_series(pressure_tail),
            "potential_tail_summary": summarize_series(potential_tail),
        },
        "log_hits": log_hits,
        "artifacts": {k: str(v) for k, v in required.items()},
    }

    gate_result = classical_state_is_cp2k_eligible(
        system_id=args.system,
        seed=args.seed,
        source_stage=stage,
        qc_payload=payload,
        observed_density_g_cm3=observed_density_g_cm3,
        observed_edge_nm=source_box_edge_nm,
        target_density_g_cm3=target_density,
        policy=policy,
    )

    payload["source_stage_valid"] = bool(
        payload["gates"]["density_plateau_ok"]
        and payload["gates"]["temperature_ok"]
        and payload["gates"]["pressure_ok"]
        and payload["gates"]["potential_ok"]
        and payload["gates"]["logs_ok"]
        and payload["gates"]["density_physical_ok"]
        and payload["gates"]["box_edge_ok"]
    )
    payload["cp2k_handoff_ready"] = gate_result.eligible
    payload["pass"] = gate_result.eligible
    payload["reason_codes"] = gate_result.hard_fail
    payload["soft_warnings"] = gate_result.soft_warn
    payload["eligibility"] = gate_result.as_dict()

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if gate_result.eligible else 4


if __name__ == "__main__":
    sys.exit(main())
