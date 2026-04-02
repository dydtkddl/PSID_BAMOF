#!/usr/bin/env python3
import argparse
import csv
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

console = Console()
ROOT = Path(__file__).resolve().parents[2]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def setup_logger(log_file: Path, verbose: bool) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("run_cp2k_pilot_smoke")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def sanitize_text(text: str, max_lines: int = 120) -> str:
    clipped = "\n".join(text.splitlines()[:max_lines])
    return clipped.encode("ascii", "replace").decode("ascii")


def run(
    cmd: list[str],
    logger: logging.Logger,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    allowed_returncodes: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    logger.info("RUN %s", " ".join(cmd))
    merged_env = None
    if env is not None:
        merged_env = dict(**__import__("os").environ)
        merged_env.update(env)
    if allowed_returncodes is None:
        allowed_returncodes = {0}
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=merged_env,
    )
    if proc.stdout and proc.stdout.strip():
        logger.info("STDOUT\n%s", sanitize_text(proc.stdout.strip()))
    if proc.stderr and proc.stderr.strip():
        logger.info("STDERR\n%s", sanitize_text(proc.stderr.strip()))
    if proc.returncode not in allowed_returncodes:
        logger.error("Command failed with exit code %s", proc.returncode)
        raise RuntimeError("Command failed: " + " ".join(cmd))
    return proc


def latest_match(path: Path, pattern: str) -> Path:
    matches = [
        p for p in path.glob(pattern)
        if ".bak" not in p.name
    ]
    matches = sorted(matches, key=lambda p: p.stat().st_mtime)
    if not matches:
        raise FileNotFoundError(f"No file matching {pattern} under {path}")
    return matches[-1]


def latest_match_any(paths: list[Path], pattern: str) -> Path:
    matches: list[Path] = []
    for path in paths:
        matches.extend(p for p in path.glob(pattern) if ".bak" not in p.name)
    matches = sorted(matches, key=lambda p: p.stat().st_mtime)
    if not matches:
        searched = ", ".join(str(path) for path in paths)
        raise FileNotFoundError(f"No file matching {pattern} under [{searched}]")
    return matches[-1]


def read_stage_meta(stage_dir: Path) -> dict | None:
    meta_path = stage_dir / "run_meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def stage_output_complete(output_path: Path) -> bool:
    if not output_path.exists() or output_path.stat().st_size <= 0:
        return False
    try:
        tail = output_path.read_text(encoding="utf-8", errors="ignore")[-10000:]
    except Exception:
        return False
    return "PROGRAM ENDED AT" in tail


def iso_from_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def repair_stage_meta_from_artifacts(
    stage_dir: Path,
    *,
    system: str,
    stage_name: str,
    input_rel: str,
    output_rel: str,
    log_rel: str,
    output_path: Path,
) -> None:
    existing = read_stage_meta(stage_dir) or {}
    payload = {
        "system": system,
        "stage": stage_name,
        "state": "DONE",
        "input": input_rel.replace("\\", "/"),
        "output": output_rel.replace("\\", "/"),
        "log_file": log_rel.replace("\\", "/"),
        "started_at": existing.get("started_at", iso_from_mtime(output_path)),
        "ended_at": iso_from_mtime(output_path),
        "exit_code": 0,
        "container_id": existing.get("container_id", ""),
        "image_id": existing.get("image_id", ""),
        "repaired_from_artifact": True,
    }
    (stage_dir / "run_meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_stage(
    *,
    stage_dir: Path,
    stage_name: str,
    system: str,
    input_rel: str,
    output_rel: str,
    log_rel: str,
    output_path: Path,
    required_artifacts: list[Path],
    run_cmd: list[str],
    logger: logging.Logger,
    env: dict[str, str] | None = None,
) -> tuple[bool, bool]:
    meta = read_stage_meta(stage_dir)
    if meta and meta.get("state") == "DONE" and meta.get("exit_code") == 0 and output_path.exists():
        if all(path.exists() for path in required_artifacts):
            logger.info("Reusing completed stage %s from existing artifacts", stage_name)
            return True, False

    if stage_output_complete(output_path) and all(path.exists() for path in required_artifacts):
        logger.warning("Repairing stale stage metadata for %s using completed artifacts", stage_name)
        repair_stage_meta_from_artifacts(
            stage_dir,
            system=system,
            stage_name=stage_name,
            input_rel=input_rel,
            output_rel=output_rel,
            log_rel=log_rel,
            output_path=output_path,
        )
        return True, True

    run(run_cmd, logger, env=env)
    return False, False


def workspace_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def workspace_abs(path: Path) -> str:
    return "/workspace/" + workspace_rel(path)


def write_report(report_base: Path, payload: dict) -> None:
    report_base.parent.mkdir(parents=True, exist_ok=True)
    report_base.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# CP2K Pilot Smoke Report",
        "",
        f"- system: `{payload['system']}`",
        f"- seed: `{payload['seed']}`",
        f"- source_stage: `{payload['source_stage']}`",
        f"- extraction_mode: `{payload['extraction_mode']}`",
        f"- source_reason: `{payload['source_reason']}`",
        f"- cutoff: `{payload['cutoff']}` Ry",
        f"- rel_cutoff: `{payload['rel_cutoff']}` Ry",
        f"- pilot_steps: `{payload['pilot_steps']}`",
        f"- nve_steps: `{payload['nve_steps']}`",
        "",
        "## Outputs",
    ]
    for key, value in payload["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Notes"])
    for note in payload["notes"]:
        lines.append(f"- {note}")
    report_base.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    t0 = time.time()
    ap = argparse.ArgumentParser(description="Run a small CP2K pilot smoke path")
    ap.add_argument("--system", default="T1-01_EC-DMC")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--source-stage", default="npt")
    ap.add_argument("--start-ps", type=float, default=1000.0)
    ap.add_argument("--cutoff", default="600")
    ap.add_argument("--rel-cutoff", default="60")
    ap.add_argument("--pilot-steps", default="50")
    ap.add_argument("--nve-steps", default="250")
    ap.add_argument("--timestep", default="0.25")
    ap.add_argument("--walltime", default="04:00:00")
    ap.add_argument("--mpi-ranks", default="1")
    ap.add_argument("--omp-threads", default="4")
    ap.add_argument("--extraction-mode", choices=["full", "cluster"], default="cluster")
    ap.add_argument("--cluster-radius-a", default="2.5")
    ap.add_argument("--cluster-padding-a", default="12.0")
    ap.add_argument("--run-label", default="pilot_smoke")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    log_file = ROOT / "logs" / "cp2k" / f"{args.system}_seed-{args.seed}_pilot_smoke_driver.log"
    logger = setup_logger(log_file, args.verbose)

    run_label = args.run_label.strip()
    if not run_label:
        raise SystemExit("--run-label must not be empty")
    run_dir = ROOT / "runs" / args.system / f"seed-{args.seed}" / "cp2k" / run_label
    snap_dir = run_dir / "snapshots"
    sp_dir = run_dir / "sp_cutoff"
    pilot_dir = run_dir / "pilot"
    nve_dir = run_dir / "nve"
    for directory in [snap_dir, sp_dir, pilot_dir, nve_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    report_base = ROOT / "results" / "reports" / f"cp2k_{run_label}_{args.system}_seed-{args.seed}"

    notes = [
        "This is a smoke path for CP2K pipeline bring-up, not a production AIMD run.",
        "Source stage defaults to NPT because current prod_short classical outputs are not trusted as CP2K seeds.",
        "Smoke defaults are intentionally tiny-scale to prove runtime and pipeline viability before periodic full-cell AIMD.",
        "Cutoff choice here is a pilot-smoke setting only. It does not replace the formal cutoff scan policy.",
        "Na uses the runtime-available q9 basis/potential branch in this smoke path because the current CP2K data bundle does not expose a production-ready Na q1 MOLOPT path.",
    ]
    if run_label != "pilot_smoke":
        notes.append(f"Run label: {run_label}")

    top = f"/workspace/runs/{args.system}/seed-{args.seed}/gromacs/{args.source_stage}.tpr"
    traj = f"/workspace/runs/{args.system}/seed-{args.seed}/gromacs/{args.source_stage}.xtc"

    cp2k_env = {
        "CP2K_MPI_RANKS": str(args.mpi_ranks),
        "CP2K_OMP_THREADS": str(args.omp_threads),
    }

    run(["bash", "scripts/cp2k/validate_cp2k_runtime.sh"], logger)

    extract_cmd = [
        "docker", "compose", "exec", "-T", "analysis", "bash", "-lc",
        "cd /workspace && python3 scripts/cp2k/extract_cp2k_snapshots_from_gmx.py "
        f"--top {top} "
        f"--traj {traj} "
        f"--system {args.system} "
        f"--seed-number {args.seed} "
        f"--source-stage {args.source_stage} "
        f"--output-dir /workspace/runs/{args.system}/seed-{args.seed}/cp2k/{run_label}/snapshots "
        "--n-snapshots 1 "
        f"--start-ps {args.start_ps} "
        "--min-separation-ps 0 "
        f"--mode {args.extraction_mode} "
        "--center-resname NA "
        "--neutralize-charge "
        f"--cluster-radius-a {args.cluster_radius_a} "
        f"--cluster-padding-a {args.cluster_padding_a} "
        "--min-density-g-cm3 0.8 "
        "--max-edge-nm 5.0 "
        f"--log-file /workspace/logs/cp2k/{args.system}_seed-{args.seed}_{run_label}_extract.log "
        + ("--verbose" if args.verbose else "")
    ]
    run(extract_cmd, logger)

    snap_one = run_dir / "snapshots" / "snap_0001"
    coord_file = snap_one / "coords.xyz"
    cell_file = snap_one / "cell.inc"
    if not coord_file.exists() or not cell_file.exists():
        raise FileNotFoundError("Snapshot extraction did not produce coords.xyz and cell.inc")
    eligibility_json = run_dir / "snapshots" / "eligibility.json"
    eligibility_payload = json.loads(eligibility_json.read_text(encoding="utf-8")) if eligibility_json.exists() else {}
    with (run_dir / "snapshots" / "manifest.csv").open(encoding="utf-8") as handle:
        manifest_row = next(csv.DictReader(handle))
    cluster_charge = manifest_row.get("net_charge", "0")
    cluster_natoms = manifest_row.get("natoms", "")

    sp_input = sp_dir / "sp.inp"
    sp_output = sp_dir / "sp.out"
    pilot_input = pilot_dir / "pilot.inp"
    pilot_output = pilot_dir / "pilot.out"
    nve_input = nve_dir / "nve.inp"
    nve_output = nve_dir / "nve.out"

    run([
        sys.executable,
        str(ROOT / "scripts" / "cp2k" / "render_cp2k_template.py"),
        "--template", str(ROOT / "inputs" / "cp2k" / "sp_cutoff.inp.tmpl"),
        "--output", str(sp_input),
        "--project", f"{args.system}_seed{args.seed}_{run_label}_sp",
        "--coord-file", workspace_abs(coord_file),
        "--cell-file", workspace_abs(cell_file),
        "--charge", cluster_charge,
        "--cutoff", args.cutoff,
        "--rel-cutoff", args.rel_cutoff,
        "--log-file", str(ROOT / "logs" / "cp2k" / f"{args.system}_seed-{args.seed}_{run_label}_render_sp.log"),
        *([] if not args.verbose else ["--verbose"]),
    ], logger, env=cp2k_env)

    sp_log_rel = workspace_rel(ROOT / "logs" / "cp2k" / f"{args.system}_seed-{args.seed}_{run_label}_sp.log")
    sp_stage_name = f"{run_label}_sp_seed{args.seed}"
    ensure_stage(
        stage_dir=sp_dir,
        stage_name=sp_stage_name,
        system=args.system,
        input_rel=workspace_rel(sp_input),
        output_rel=workspace_rel(sp_output),
        log_rel=sp_log_rel,
        output_path=sp_output,
        required_artifacts=[sp_output],
        run_cmd=[
            "bash",
            "scripts/cp2k/run_cp2k_job.sh",
            "--input", workspace_rel(sp_input),
            "--output", workspace_rel(sp_output),
            "--stage", sp_stage_name,
            "--system", args.system,
            "--log-file", sp_log_rel,
        ],
        logger=logger,
        env=cp2k_env,
    )

    run([
        sys.executable,
        str(ROOT / "scripts" / "cp2k" / "render_cp2k_template.py"),
        "--template", str(ROOT / "inputs" / "cp2k" / "pilot_nvt.inp.tmpl"),
        "--output", str(pilot_input),
        "--project", f"{args.system}_seed{args.seed}_{run_label}_pilot",
        "--system", args.system,
        "--coord-file", workspace_abs(coord_file),
        "--cell-file", workspace_abs(cell_file),
        "--charge", cluster_charge,
        "--cutoff", args.cutoff,
        "--rel-cutoff", args.rel_cutoff,
        "--timestep", args.timestep,
        "--steps", args.pilot_steps,
        "--walltime", args.walltime,
        "--log-file", str(ROOT / "logs" / "cp2k" / f"{args.system}_seed-{args.seed}_{run_label}_render_pilot.log"),
        *([] if not args.verbose else ["--verbose"]),
    ], logger, env=cp2k_env)

    pilot_log_rel = workspace_rel(ROOT / "logs" / "cp2k" / f"{args.system}_seed-{args.seed}_{run_label}_pilot.log")
    pilot_stage_name = f"{run_label}_pilot_seed{args.seed}"
    ensure_stage(
        stage_dir=pilot_dir,
        stage_name=pilot_stage_name,
        system=args.system,
        input_rel=workspace_rel(pilot_input),
        output_rel=workspace_rel(pilot_output),
        log_rel=pilot_log_rel,
        output_path=pilot_output,
        required_artifacts=[pilot_output, pilot_dir / "pilot_restart", pilot_dir / "pilot_wfn"],
        run_cmd=[
            "bash",
            "scripts/cp2k/run_cp2k_job.sh",
            "--input", workspace_rel(pilot_input),
            "--output", workspace_rel(pilot_output),
            "--stage", pilot_stage_name,
            "--system", args.system,
            "--log-file", pilot_log_rel,
        ],
        logger=logger,
        env=cp2k_env,
    )

    pilot_restart = latest_match_any([pilot_dir, ROOT], "*pilot_restart*")
    pilot_wfn = latest_match_any([pilot_dir, ROOT], "*pilot_wfn*")

    run([
        sys.executable,
        str(ROOT / "scripts" / "cp2k" / "render_cp2k_template.py"),
        "--template", str(ROOT / "inputs" / "cp2k" / "nve_drift.inp.tmpl"),
        "--output", str(nve_input),
        "--project", f"{args.system}_seed{args.seed}_{run_label}_nve",
        "--system", args.system,
        "--coord-file", workspace_abs(coord_file),
        "--cell-file", workspace_abs(cell_file),
        "--charge", cluster_charge,
        "--cutoff", args.cutoff,
        "--rel-cutoff", args.rel_cutoff,
        "--timestep", args.timestep,
        "--steps", args.nve_steps,
        "--walltime", args.walltime,
        "--wfn-restart", workspace_abs(pilot_wfn),
        "--ext-restart", workspace_abs(pilot_restart),
        "--log-file", str(ROOT / "logs" / "cp2k" / f"{args.system}_seed-{args.seed}_{run_label}_render_nve.log"),
        *([] if not args.verbose else ["--verbose"]),
    ], logger)

    nve_log_rel = workspace_rel(ROOT / "logs" / "cp2k" / f"{args.system}_seed-{args.seed}_{run_label}_nve.log")
    nve_stage_name = f"{run_label}_nve_seed{args.seed}"
    ensure_stage(
        stage_dir=nve_dir,
        stage_name=nve_stage_name,
        system=args.system,
        input_rel=workspace_rel(nve_input),
        output_rel=workspace_rel(nve_output),
        log_rel=nve_log_rel,
        output_path=nve_output,
        required_artifacts=[nve_output, nve_dir / "nve_ener"],
        run_cmd=[
            "bash",
            "scripts/cp2k/run_cp2k_job.sh",
            "--input", workspace_rel(nve_input),
            "--output", workspace_rel(nve_output),
            "--stage", nve_stage_name,
            "--system", args.system,
            "--log-file", nve_log_rel,
        ],
        logger=logger,
        env=cp2k_env,
    )

    natoms = int(coord_file.read_text(encoding="utf-8").splitlines()[0].strip())
    nve_ener = latest_match(nve_dir, "*nve_ener*")
    drift_json = nve_dir / "nve_drift_postrun.json"
    legacy_drift_json = nve_dir / "nve_drift.json"
    drift_proc = run([
        sys.executable,
        str(ROOT / "scripts" / "cp2k" / "check_nve_drift.py"),
        "--ener", str(nve_ener),
        "--natoms", str(natoms),
        "--min-points", "50",
        "--min-duration-ps", "0.05",
        "--discard-frac", "0.10",
        "--json-out", str(drift_json),
        "--log-file", str(ROOT / "logs" / "cp2k" / f"{args.system}_seed-{args.seed}_{run_label}_check_nve.log"),
        *([] if not args.verbose else ["--verbose"]),
    ], logger, allowed_returncodes={0, 5})

    drift_payload = json.loads(drift_json.read_text(encoding="utf-8")) if drift_json.exists() else {}
    if drift_json.exists():
        legacy_drift_json.write_text(drift_json.read_text(encoding="utf-8"), encoding="utf-8")
    drift_status = drift_payload.get("status", "MISSING")
    if drift_status == "NOT_EVALUABLE":
        notes.append("NVE drift gate returned NOT_EVALUABLE. This smoke path opened the runtime, but the current trace is too short for a strict microcanonical verdict.")
    elif drift_status == "PASS":
        notes.append("NVE drift gate passed.")
    elif drift_status == "FAIL":
        notes.append("NVE drift gate failed.")
    else:
        notes.append(f"NVE drift gate status: {drift_status}")

    payload = {
        "system": args.system,
        "seed": args.seed,
        "run_label": run_label,
        "source_stage": args.source_stage,
        "extraction_mode": args.extraction_mode,
        "source_reason": "NPT was chosen for smoke because prod_short is currently non-physical for CP2K start use.",
        "cutoff": int(args.cutoff),
        "rel_cutoff": int(args.rel_cutoff),
        "pilot_steps": int(args.pilot_steps),
        "nve_steps": int(args.nve_steps),
        "mpi_ranks": int(args.mpi_ranks),
        "omp_threads": int(args.omp_threads),
        "duration_sec": round(time.time() - t0, 2),
        "outputs": {
            "snapshot_dir": str(snap_one),
            "snapshot_atoms": cluster_natoms,
            "snapshot_charge": cluster_charge,
            "sp_output": str(sp_output),
            "pilot_output": str(pilot_output),
            "pilot_restart": str(pilot_restart),
            "pilot_wfn": str(pilot_wfn),
            "nve_output": str(nve_output),
            "nve_ener": str(nve_ener),
            "nve_drift_json": str(drift_json),
            "driver_log": str(log_file),
        },
        "notes": notes,
        "source_stage_validated": eligibility_payload.get("eligibility", {}).get("eligible"),
        "source_stage_eligibility": eligibility_payload,
    }
    write_report(report_base, payload)

    table = Table(title="CP2K Pilot Smoke Complete")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("System", args.system)
    table.add_row("Seed", str(args.seed))
    table.add_row("Snapshot", str(snap_one))
    table.add_row("Pilot restart", str(pilot_restart.name))
    table.add_row("NVE energy", str(nve_ener.name))
    table.add_row("Report", str(report_base.with_suffix(".md")))
    table.add_row("Elapsed s", f"{payload['duration_sec']:.2f}")
    console.print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
