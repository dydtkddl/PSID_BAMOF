#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs" / "cp2k"
DEFAULT_SYSTEMS = ["T1-01_EC-DMC", "T1-02_EC-DVS", "T1-03_EC-DMS"]
DEFAULT_SEEDS = [1, 2, 3]


def setup_logger(log_path: Path, verbose: bool) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("run_cp2k_hardmode_queue")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(formatter)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    sh.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def run(cmd: list[str], logger: logging.Logger, cwd: Path = ROOT, allow: set[int] | None = None) -> subprocess.CompletedProcess[str]:
    logger.info("RUN %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.stdout.strip():
        logger.info("STDOUT\n%s", proc.stdout.strip()[:12000])
    if proc.stderr.strip():
        logger.info("STDERR\n%s", proc.stderr.strip()[:12000])
    allow = allow or {0}
    if proc.returncode not in allow:
        raise RuntimeError(f"Command failed with exit code {proc.returncode}: {' '.join(cmd)}")
    return proc


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def cp2k_processes() -> list[str]:
    proc = subprocess.run(
        ["docker", "exec", "keti-cp2k", "bash", "-lc", "ps -eo pid,etimes,cmd | grep cp2k | grep -v grep || true"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return lines


def wait_for_cp2k_idle(logger: logging.Logger, *, poll_seconds: int = 30, max_wait_minutes: int = 720) -> None:
    deadline = time.time() + max_wait_minutes * 60
    while time.time() < deadline:
        lines = cp2k_processes()
        if not lines:
            logger.info("CP2K GPU lane is idle")
            return
        logger.info("Waiting for active CP2K job to finish (%d process lines)", len(lines))
        for line in lines[:3]:
            logger.info("ACTIVE %s", line)
        time.sleep(poll_seconds)
    raise TimeoutError("Timed out waiting for CP2K lane to become idle")


def report_base(run_label: str, system: str, seed: int) -> Path:
    return ROOT / "results" / "reports" / f"cp2k_{run_label}_{system}_seed-{seed}"


def smoke_report_exists(run_label: str, system: str, seed: int) -> bool:
    return report_base(run_label, system, seed).with_suffix(".json").exists()


def export_dir_for(run_label: str, system: str, seed: int) -> Path:
    return ROOT / "results" / "visualization" / "cp2k" / system / f"seed-{seed}" / run_label


def export_exists(run_label: str, system: str, seed: int) -> bool:
    export_dir = export_dir_for(run_label, system, seed)
    return any(export_dir.glob("*.load.pml"))


def run_smoke(system: str, seed: int, *, run_label: str, pilot_steps: int, nve_steps: int, timestep: float, cutoff: int, rel_cutoff: int, logger: logging.Logger) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "cp2k" / "run_cp2k_pilot_smoke.py"),
        "--system", system,
        "--seed", str(seed),
        "--source-stage", "npt",
        "--run-label", run_label,
        "--cutoff", str(cutoff),
        "--rel-cutoff", str(rel_cutoff),
        "--pilot-steps", str(pilot_steps),
        "--nve-steps", str(nve_steps),
        "--timestep", str(timestep),
        "--walltime", "04:00:00",
        "--mpi-ranks", "1",
        "--omp-threads", "4",
        "--extraction-mode", "cluster",
        "--cluster-radius-a", "2.5",
        "--cluster-padding-a", "12.0",
        "--verbose",
    ]
    run(cmd, logger)


def run_export(system: str, seed: int, *, run_label: str, logger: logging.Logger) -> None:
    nve_dir = ROOT / "runs" / system / f"seed-{seed}" / "cp2k" / run_label / "nve"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "cp2k" / "export_cp2k_traj_for_pymol.py"),
        "--nve-dir", str(nve_dir),
        "--overwrite",
    ]
    run(cmd, logger)


def parse_manifest_row(manifest_path: Path) -> dict:
    with manifest_path.open(encoding="utf-8") as handle:
        return next(csv.DictReader(handle))


def extract_snapshot_for_label(system: str, seed: int, *, run_label: str, mode: str, logger: logging.Logger) -> tuple[Path, Path, dict]:
    out_dir = ROOT / "runs" / system / f"seed-{seed}" / "cp2k" / run_label / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    top = f"/workspace/runs/{system}/seed-{seed}/gromacs/npt.tpr"
    traj = f"/workspace/runs/{system}/seed-{seed}/gromacs/npt.xtc"
    log_file = f"/workspace/logs/cp2k/{system}_seed-{seed}_{run_label}_extract.log"
    cmd = [
        "docker", "compose", "exec", "-T", "analysis", "bash", "-lc",
        "cd /workspace && python3 scripts/cp2k/extract_cp2k_snapshots_from_gmx.py "
        f"--top {top} "
        f"--traj {traj} "
        f"--system {system} "
        f"--seed-number {seed} "
        "--source-stage npt "
        f"--output-dir /workspace/runs/{system}/seed-{seed}/cp2k/{run_label}/snapshots "
        "--n-snapshots 1 "
        "--start-ps 1000.0 "
        "--min-separation-ps 0 "
        f"--mode {mode} "
        + ("--center-resname NA --neutralize-charge --cluster-radius-a 2.5 --cluster-padding-a 12.0 " if mode == "cluster" else "")
        + "--min-density-g-cm3 0.8 --max-edge-nm 5.0 "
        f"--log-file {log_file} --verbose"
    ]
    run(cmd, logger)
    snap_one = out_dir / "snap_0001"
    manifest_row = parse_manifest_row(out_dir / "manifest.csv")
    return snap_one / "coords.xyz", snap_one / "cell.inc", manifest_row


def render_sp_input(system: str, seed: int, *, run_label: str, coord_file: Path, cell_file: Path, charge: str, cutoff: int, rel_cutoff: int, logger: logging.Logger) -> tuple[Path, Path]:
    run_dir = ROOT / "runs" / system / f"seed-{seed}" / "cp2k" / run_label / f"sp_cutoff_{cutoff}"
    run_dir.mkdir(parents=True, exist_ok=True)
    sp_input = run_dir / "sp.inp"
    sp_output = run_dir / "sp.out"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "cp2k" / "render_cp2k_template.py"),
        "--template", str(ROOT / "inputs" / "cp2k" / "sp_cutoff.inp.tmpl"),
        "--output", str(sp_input),
        "--project", f"{system}_seed{seed}_{run_label}_sp{cutoff}",
        "--coord-file", "/workspace/" + str(coord_file.relative_to(ROOT)).replace("\\", "/"),
        "--cell-file", "/workspace/" + str(cell_file.relative_to(ROOT)).replace("\\", "/"),
        "--charge", charge,
        "--cutoff", str(cutoff),
        "--rel-cutoff", str(rel_cutoff),
        "--log-file", str(LOGS / f"{system}_seed-{seed}_{run_label}_render_sp_{cutoff}.log"),
        "--verbose",
    ]
    run(cmd, logger)
    return sp_input, sp_output


def run_sp_job(system: str, *, run_label: str, stage_tag: str, sp_input: Path, sp_output: Path, logger: logging.Logger) -> None:
    log_rel = (LOGS / f"{system}_{stage_tag}.log").relative_to(ROOT).as_posix()
    cmd = [
        "bash", "scripts/cp2k/run_cp2k_job.sh",
        "--input", sp_input.relative_to(ROOT).as_posix(),
        "--output", sp_output.relative_to(ROOT).as_posix(),
        "--stage", stage_tag,
        "--system", system,
        "--log-file", log_rel,
    ]
    run(cmd, logger)


TOTAL_ENERGY_RX = re.compile(r"Total energy:\s+(-?\d+\.\d+)")


def extract_total_energy(sp_output: Path) -> float | None:
    text = sp_output.read_text(encoding="utf-8", errors="ignore")
    matches = TOTAL_ENERGY_RX.findall(text)
    return float(matches[-1]) if matches else None


def run_cutoff_scan(system: str, seed: int, *, run_label: str, cutoffs: list[int], rel_cutoff: int, logger: logging.Logger, jsonl_path: Path) -> None:
    wait_for_cp2k_idle(logger)
    coord_file, cell_file, manifest_row = extract_snapshot_for_label(system, seed, run_label=run_label, mode="cluster", logger=logger)
    charge = manifest_row.get("net_charge", "0")
    results: list[dict] = []
    for cutoff in cutoffs:
        wait_for_cp2k_idle(logger)
        sp_input, sp_output = render_sp_input(system, seed, run_label=run_label, coord_file=coord_file, cell_file=cell_file, charge=charge, cutoff=cutoff, rel_cutoff=rel_cutoff, logger=logger)
        run_sp_job(system, run_label=run_label, stage_tag=f"{run_label}_sp_{cutoff}", sp_input=sp_input, sp_output=sp_output, logger=logger)
        energy = extract_total_energy(sp_output)
        payload = {
            "event": "cutoff_scan_point_done",
            "system": system,
            "seed": seed,
            "run_label": run_label,
            "cutoff": cutoff,
            "rel_cutoff": rel_cutoff,
            "total_energy_ha": energy,
            "output": str(sp_output),
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        append_jsonl(jsonl_path, payload)
        results.append(payload)
    (ROOT / "results" / "reports" / f"{run_label}_{system}_seed-{seed}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def periodic_bridge_prep(system: str, seed: int, *, run_label: str, logger: logging.Logger, jsonl_path: Path) -> None:
    coord_file, cell_file, manifest_row = extract_snapshot_for_label(system, seed, run_label=run_label, mode="full", logger=logger)
    natoms = int(coord_file.read_text(encoding="utf-8").splitlines()[0].strip())
    payload = {
        "event": "periodic_bridge_prepared",
        "system": system,
        "seed": seed,
        "run_label": run_label,
        "coord_file": str(coord_file),
        "cell_file": str(cell_file),
        "natoms": natoms,
        "net_charge": manifest_row.get("net_charge", ""),
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if natoms > 256:
        payload["status"] = "BLOCKED_SIZE"
        payload["reason"] = f"full periodic snapshot too large for immediate workstation pilot ({natoms} atoms)"
    else:
        payload["status"] = "READY"
    append_jsonl(jsonl_path, payload)


def main() -> int:
    ap = argparse.ArgumentParser(description="Sequential hard-mode CP2K validation runner")
    ap.add_argument("--systems", default=",".join(DEFAULT_SYSTEMS))
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--skip-breadth", action="store_true")
    ap.add_argument("--skip-longer", action="store_true")
    ap.add_argument("--skip-convergence", action="store_true")
    ap.add_argument("--skip-periodic-prep", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    ts = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS / f"hardmode_queue_{ts}.log"
    jsonl_path = LOGS / f"hardmode_queue_{ts}.jsonl"
    logger = setup_logger(log_path, args.verbose)

    append_jsonl(jsonl_path, {"event": "queue_start", "systems": systems, "seeds": seeds, "ts": datetime.now().astimezone().isoformat(timespec="seconds")})

    if not args.skip_breadth:
        for system in systems:
            for seed in seeds:
                wait_for_cp2k_idle(logger)
                append_jsonl(jsonl_path, {"event": "breadth_start", "system": system, "seed": seed, "ts": datetime.now().astimezone().isoformat(timespec="seconds")})
                try:
                    run_smoke(system, seed, run_label="pilot_smoke", pilot_steps=50, nve_steps=250, timestep=0.25, cutoff=600, rel_cutoff=60, logger=logger)
                    run_export(system, seed, run_label="pilot_smoke", logger=logger)
                    append_jsonl(jsonl_path, {"event": "breadth_done", "system": system, "seed": seed, "report": str(report_base("pilot_smoke", system, seed).with_suffix(".json")), "ts": datetime.now().astimezone().isoformat(timespec="seconds")})
                except Exception as exc:
                    append_jsonl(jsonl_path, {"event": "breadth_fail", "system": system, "seed": seed, "error": str(exc), "ts": datetime.now().astimezone().isoformat(timespec="seconds")})
                    logger.exception("Breadth smoke failed for %s seed-%s", system, seed)

    rep_system = systems[0] if systems else DEFAULT_SYSTEMS[0]
    rep_seed = seeds[0] if seeds else 1

    if not args.skip_longer:
        wait_for_cp2k_idle(logger)
        append_jsonl(jsonl_path, {"event": "longer_start", "system": rep_system, "seed": rep_seed, "ts": datetime.now().astimezone().isoformat(timespec="seconds")})
        try:
            run_smoke(rep_system, rep_seed, run_label="pilot_longer_t025", pilot_steps=100, nve_steps=500, timestep=0.25, cutoff=600, rel_cutoff=60, logger=logger)
            run_export(rep_system, rep_seed, run_label="pilot_longer_t025", logger=logger)
            append_jsonl(jsonl_path, {"event": "longer_done", "system": rep_system, "seed": rep_seed, "report": str(report_base("pilot_longer_t025", rep_system, rep_seed).with_suffix(".json")), "ts": datetime.now().astimezone().isoformat(timespec="seconds")})
        except Exception as exc:
            append_jsonl(jsonl_path, {"event": "longer_fail", "system": rep_system, "seed": rep_seed, "error": str(exc), "ts": datetime.now().astimezone().isoformat(timespec="seconds")})
            logger.exception("Longer validation failed for %s seed-%s", rep_system, rep_seed)

    if not args.skip_convergence:
        try:
            run_cutoff_scan(rep_system, rep_seed, run_label="cutoff_scan", cutoffs=[400, 500, 600], rel_cutoff=60, logger=logger, jsonl_path=jsonl_path)
        except Exception as exc:
            append_jsonl(jsonl_path, {"event": "convergence_fail", "system": rep_system, "seed": rep_seed, "error": str(exc), "ts": datetime.now().astimezone().isoformat(timespec="seconds")})
            logger.exception("Cutoff scan failed for %s seed-%s", rep_system, rep_seed)

    if not args.skip_periodic_prep:
        try:
            periodic_bridge_prep(rep_system, rep_seed, run_label="periodic_bridge", logger=logger, jsonl_path=jsonl_path)
        except Exception as exc:
            append_jsonl(jsonl_path, {"event": "periodic_prep_fail", "system": rep_system, "seed": rep_seed, "error": str(exc), "ts": datetime.now().astimezone().isoformat(timespec="seconds")})
            logger.exception("Periodic bridge prep failed for %s seed-%s", rep_system, rep_seed)

    append_jsonl(jsonl_path, {"event": "queue_end", "ts": datetime.now().astimezone().isoformat(timespec="seconds")})
    logger.info("Hard-mode queue finished")
    logger.info("Log: %s", log_path)
    logger.info("JSONL: %s", jsonl_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
