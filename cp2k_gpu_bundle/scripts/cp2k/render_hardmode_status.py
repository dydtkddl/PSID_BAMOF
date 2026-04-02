#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYSTEMS = ["T1-01_EC-DMC", "T1-02_EC-DVS", "T1-03_EC-DMS"]
SEEDS = [1, 2, 3]


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def latest(path_glob: str) -> Path | None:
    candidates = sorted(ROOT.glob(path_glob), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def collect_unit(system: str, seed: int) -> dict:
    base = ROOT / "runs" / system / f"seed-{seed}" / "cp2k" / "pilot_smoke"
    report = load_json(ROOT / "results" / "reports" / f"cp2k_pilot_smoke_{system}_seed-{seed}.json")
    pilot_meta = load_json(base / "pilot" / "run_meta.json")
    nve_meta = load_json(base / "nve" / "run_meta.json")
    drift = load_json(base / "nve" / "nve_drift_postrun.json") or load_json(base / "nve" / "nve_drift.json")
    export_dir = ROOT / "results" / "visualization" / "cp2k" / system / f"seed-{seed}" / "pilot_smoke_nve"
    export_ok = any(export_dir.glob("*.load.pml"))
    return {
        "system": system,
        "seed": seed,
        "report_exists": report is not None,
        "pilot_state": (pilot_meta or {}).get("state", "MISSING"),
        "nve_state": (nve_meta or {}).get("state", "MISSING"),
        "drift_status": (drift or {}).get("status", "MISSING"),
        "drift_mev_atom_ps": (drift or {}).get("slope_mev_atom_ps"),
        "export_exists": export_ok,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Render current CP2K hard-mode validation status")
    ap.add_argument("--output-md", default=str(ROOT / "results" / "reports" / "20260329_cp2k_hardmode_status.md"))
    ap.add_argument("--output-json", default=str(ROOT / "results" / "reports" / "20260329_cp2k_hardmode_status.json"))
    args = ap.parse_args()

    units = [collect_unit(system, seed) for system in SYSTEMS for seed in SEEDS]
    queue_log = latest("logs/cp2k/hardmode_queue_*.log")
    queue_jsonl = latest("logs/cp2k/hardmode_queue_*.jsonl")
    launcher = latest("logs/cp2k/hardmode_queue_launcher_*.json")

    done = sum(1 for u in units if u["report_exists"] and u["nve_state"] == "DONE" and u["drift_status"] == "PASS")
    running = [u for u in units if u["nve_state"] == "RUNNING" or u["pilot_state"] == "RUNNING"]

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "units": units,
        "counts": {
            "smoke_pass": done,
            "running_units": len(running),
            "report_exists": sum(1 for u in units if u["report_exists"]),
            "exports_present": sum(1 for u in units if u["export_exists"]),
        },
        "artifacts": {
            "queue_log": str(queue_log) if queue_log else "",
            "queue_jsonl": str(queue_jsonl) if queue_jsonl else "",
            "launcher": str(launcher) if launcher else "",
        },
    }

    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# CP2K Hard-Mode Status",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- smoke_pass: `{payload['counts']['smoke_pass']}`",
        f"- running_units: `{payload['counts']['running_units']}`",
        f"- report_exists: `{payload['counts']['report_exists']}`",
        f"- exports_present: `{payload['counts']['exports_present']}`",
        "",
        "## Units",
        "",
        "| system | seed | report | pilot | nve | drift | export |",
        "|---|---:|---|---|---|---|---|",
    ]
    for u in units:
        lines.append(
            f"| {u['system']} | {u['seed']} | {u['report_exists']} | {u['pilot_state']} | {u['nve_state']} | {u['drift_status']} | {u['export_exists']} |"
        )
    lines.extend([
        "",
        "## Queue Artifacts",
        "",
        f"- queue_log: `{payload['artifacts']['queue_log']}`",
        f"- queue_jsonl: `{payload['artifacts']['queue_jsonl']}`",
        f"- launcher: `{payload['artifacts']['launcher']}`",
    ])
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
