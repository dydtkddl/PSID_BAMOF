#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_POLICY_PATH = Path("inputs/policy/classical_gate.yml")
DEFAULT_POLICY: dict[str, Any] = {
    "source_stage_allowlist": ["npt", "handoff_nvt"],
    "density_plateau": {
        "slope_limit_g_cm3_per_ps": 2.0e-4,
        "cv_limit": 0.03,
    },
    "temperature": {"tolerance_k": 15.0},
    "pressure": {
        "abs_mean_bar_limit": 1500.0,
        "stdev_bar_limit": 3000.0,
    },
    "physical": {
        "min_density_g_cm3": 0.8,
        "max_density_g_cm3": 1.8,
        "max_edge_nm": 5.0,
        "target_density_tolerance_g_cm3": 0.15,
    },
    "log_patterns": {
        "hard_fail": {
            "pressure_scaling_instability": "Pressure scaling more than 1%",
            "fatal_error": "Fatal error",
            "segfault": "Segmentation fault",
            "lincs_warning": "LINCS WARNING",
            "nan_detected": r"\bnan\b",
        }
    },
}


@dataclass
class GateResult:
    eligible: bool
    hard_fail: list[str]
    soft_warn: list[str]
    metrics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "hard_fail": self.hard_fail,
            "soft_warn": self.soft_warn,
            "metrics": self.metrics,
        }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_gate_policy(path: str | Path | None = None) -> dict[str, Any]:
    policy_path = Path(path) if path else DEFAULT_POLICY_PATH
    if not policy_path.exists():
        return DEFAULT_POLICY
    loaded = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        return DEFAULT_POLICY
    return _deep_merge(DEFAULT_POLICY, loaded)


def convert_density_kg_m3_to_g_cm3(value_kg_m3: float) -> float:
    return value_kg_m3 / 1000.0


def convert_density_slope_kgm3_to_gcm3(value_kg_m3_per_ps: float) -> float:
    return value_kg_m3_per_ps / 1000.0


def linear_slope(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return float("nan")
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0.0:
        return float("nan")
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return sxy / sxx


def summarize_series(data: list[tuple[float, float]]) -> dict[str, float]:
    if not data:
        return {"n": 0}
    values = [v for _, v in data]
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def evaluate_density_plateau(
    density_tail: list[tuple[float, float]],
    slope_limit_g_cm3_per_ps: float,
    cv_limit: float,
) -> dict[str, Any]:
    if len(density_tail) < 2:
        return {"ok": False, "reason": "insufficient_density_points"}

    xs = [t for t, _ in density_tail]
    ys = [v for _, v in density_tail]
    mean_raw = statistics.fmean(ys)
    stdev_raw = statistics.pstdev(ys) if len(ys) > 1 else 0.0
    cv = stdev_raw / mean_raw if mean_raw else float("inf")
    slope_raw = linear_slope(xs, ys)
    slope_g_cm3 = convert_density_slope_kgm3_to_gcm3(slope_raw)
    ok = (
        math.isfinite(slope_g_cm3)
        and abs(slope_g_cm3) <= slope_limit_g_cm3_per_ps
        and math.isfinite(cv)
        and cv <= cv_limit
    )
    return {
        "ok": ok,
        "slope_raw_kg_m3_per_ps": slope_raw,
        "slope_g_cm3_per_ps": slope_g_cm3,
        "mean_raw_kg_m3": mean_raw,
        "mean_g_cm3": convert_density_kg_m3_to_g_cm3(mean_raw),
        "cv": cv,
    }


def scan_log_hits(log_paths: list[Path], policy: dict[str, Any]) -> list[str]:
    patterns = policy.get("log_patterns", {}).get("hard_fail", {})
    compiled = [(tag, re.compile(expr, re.IGNORECASE)) for tag, expr in patterns.items()]
    hits: list[str] = []
    for path in log_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for tag, rx in compiled:
            if rx.search(text):
                hits.append(f"{path.name}:{tag}")
    return sorted(set(hits))


def read_last_gro_box_edge_nm(gro_path: str | Path) -> float:
    path = Path(gro_path)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(lines) < 3:
        raise ValueError(f"GRO file too short: {path}")
    parts = lines[-1].split()
    if len(parts) < 3:
        raise ValueError(f"Could not parse box line in {path}")
    return max(float(parts[0]), float(parts[1]), float(parts[2]))


def infer_target_density(system_id: str, lock_path: str | Path = "study_lock.yml") -> float | None:
    path = Path(lock_path)
    if not path.exists():
        return None
    lock = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for system in lock.get("systems", []):
        if system.get("id") == system_id:
            try:
                return float(system["density_g_cm3"])
            except Exception:
                return None
    return None


def classical_state_is_cp2k_eligible(
    *,
    system_id: str,
    seed: int,
    source_stage: str,
    qc_payload: dict[str, Any],
    observed_density_g_cm3: float,
    observed_edge_nm: float,
    target_density_g_cm3: float | None,
    policy: dict[str, Any] | None = None,
) -> GateResult:
    config = policy or DEFAULT_POLICY
    hard_fail: list[str] = []
    soft_warn: list[str] = []
    allowlist = set(config.get("source_stage_allowlist", []))
    physical = config.get("physical", {})
    gates = qc_payload.get("gates", {})
    log_hits = qc_payload.get("log_hits", [])

    if source_stage not in allowlist:
        hard_fail.append(f"source_stage_not_allowed:{source_stage}")

    min_density = float(physical.get("min_density_g_cm3", 0.8))
    max_density = float(physical.get("max_density_g_cm3", 1.8))
    max_edge = float(physical.get("max_edge_nm", 5.0))
    target_tol = float(physical.get("target_density_tolerance_g_cm3", 0.15))

    if observed_edge_nm > max_edge:
        hard_fail.append(f"box_edge_too_large:{observed_edge_nm:.3f}nm")
    if observed_density_g_cm3 < min_density or observed_density_g_cm3 > max_density:
        hard_fail.append(f"density_nonphysical:{observed_density_g_cm3:.4f}")
    if target_density_g_cm3 is not None and abs(observed_density_g_cm3 - target_density_g_cm3) > target_tol:
        soft_warn.append(
            f"density_off_target:{observed_density_g_cm3:.4f}:target={target_density_g_cm3:.4f}"
        )

    if not bool(gates.get("density_plateau_ok")):
        hard_fail.append("density_not_plateaued")
    if not bool(gates.get("temperature_ok")):
        hard_fail.append("temperature_not_ok")
    if not bool(gates.get("pressure_ok")):
        hard_fail.append("pressure_not_ok")
    if not bool(gates.get("potential_ok")):
        hard_fail.append("potential_not_ok")
    if not bool(gates.get("logs_ok", True)):
        hard_fail.append("logs_not_ok")

    if any("pressure_scaling_instability" in hit for hit in log_hits):
        hard_fail.append("pressure_scaling_instability")
    if any(
        key in hit
        for hit in log_hits
        for key in ("fatal_error", "segfault", "lincs_warning", "nan_detected")
    ):
        hard_fail.append("runtime_instability")

    metrics = {
        "system": system_id,
        "seed": seed,
        "source_stage": source_stage,
        "observed_density_g_cm3": observed_density_g_cm3,
        "observed_edge_nm": observed_edge_nm,
        "target_density_g_cm3": target_density_g_cm3,
    }
    return GateResult(
        eligible=not hard_fail,
        hard_fail=sorted(set(hard_fail)),
        soft_warn=sorted(set(soft_warn)),
        metrics=metrics,
    )


def load_qc_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
