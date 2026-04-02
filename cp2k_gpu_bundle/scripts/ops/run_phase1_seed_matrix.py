#!/usr/bin/env python3
import argparse
import json
import logging
import math
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops.classical_state_gate import load_gate_policy


ROOT = Path(".")
STATE_PATH = Path("logs/step0/phase1_seed_matrix_state.json")
REPORT_MD = Path("results/reports/phase1_seed_matrix_report.md")
REPORT_JSON = Path("results/reports/phase1_seed_matrix_report.json")

MOLAR_MASS = {
    "EC": 88.06,
    "DMC": 90.08,
    "DVS": 118.15,
    "DMS": 94.13,
    "NaPF6": 167.95,
}

SYSTEM_INDEX = {
    "T1-01_EC-DMC": 1,
    "T1-02_EC-DVS": 2,
    "T1-03_EC-DMS": 3,
}

CHARGE_MAP = {"EC": 0, "DMC": 0, "DVS": 0, "DMS": 0, "PF6": -1}

PATCHED_FILES = [
    "inputs/policy/classical_gate.yml",
    "scripts/packing/write_packmol_input.py",
    "scripts/packing/check_xyz_counts.py",
    "scripts/gromacs/assemble_gmx_system.py",
    "scripts/gromacs/xyz_to_gro.py",
    "scripts/gromacs/xyz_to_gro.sh",
    "scripts/gromacs/run_gromacs_stage.sh",
    "scripts/ops/qc_phase1_seed.py",
    "scripts/ops/run_phase1_seed_matrix.py",
    "scripts/ops/classical_state_gate.py",
]


def run_cmd(cmd: List[str], timeout: int = 0) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=None if timeout <= 0 else timeout,
    )


def run_shell(cmd: str, timeout: int = 0) -> subprocess.CompletedProcess:
    return run_cmd(["bash", "-lc", cmd], timeout=timeout)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def setup_logger() -> logging.Logger:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(f"logs/step0/phase1_seed_matrix_{ts}.log")
    ensure_parent(log_path)
    logger = logging.getLogger("phase1_seed_matrix")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.info("Main log: %s", log_path)
    return logger


def load_state() -> Dict:
    def default_state() -> Dict:
        return {"run_units": {}, "rca": [], "warnings": [], "started_at": datetime.now().isoformat()}

    def rebuild_from_outputs() -> Dict:
        state = default_state()
        for gmx_dir in Path("runs").glob("*/*/gromacs"):
            try:
                system = gmx_dir.parent.parent.name
                seed_name = gmx_dir.parent.name
                if not seed_name.startswith("seed-"):
                    continue
                unit_key = f"{system}/{seed_name}"
                run_state = state["run_units"].setdefault(unit_key, {"stages": {}, "warnings": []})
                pack_dir = gmx_dir.parent / "packmol"

                if (pack_dir / "box_meta.json").exists():
                    run_state["stages"]["calc_box"] = "PASS"
                if (pack_dir / "packmol.inp").exists():
                    run_state["stages"]["packmol_input"] = "PASS"
                if output_exists([pack_dir / "packed.xyz"]):
                    run_state["stages"]["packmol"] = "PASS"
                    run_state["stages"]["xyz_count"] = "PASS"
                if output_exists([gmx_dir / "topol.top"]):
                    run_state["stages"]["assemble"] = "PASS"
                if output_exists([gmx_dir / "conf.gro"]):
                    run_state["stages"]["xyz_to_gro"] = "PASS"
                for stage in ("em", "nvt", "npt", "prod_short", "handoff_nvt"):
                    if output_exists(
                        [
                            gmx_dir / f"{stage}.tpr",
                            gmx_dir / f"{stage}.gro",
                            gmx_dir / f"{stage}.edr",
                            gmx_dir / f"{stage}.log",
                        ]
                    ):
                        run_state["stages"][stage] = "PASS"
            except Exception:
                continue
        return state

    if STATE_PATH.exists():
        try:
            raw = STATE_PATH.read_text(encoding="utf-8")
            if raw.strip():
                return json.loads(raw)
        except Exception:
            pass
    return rebuild_from_outputs()


def save_state(state: Dict) -> None:
    ensure_parent(STATE_PATH)
    tmp_path = STATE_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp_path.replace(STATE_PATH)


def classify_failure(text: str) -> str:
    t = text.lower()
    if "packmol" in t and ("failed" in t or "error" in t):
        return "packmol_failure"
    if "grompp" in t and ("fatal error" in t or "error" in t):
        return "grompp_failure"
    if "mdrun" in t and ("fatal" in t or "error" in t):
        return "mdrun_failure"
    if "no such file" in t or "missing" in t:
        return "input_or_path_missing"
    if "atom count mismatch" in t:
        return "topology_or_count_mismatch"
    return "unknown_failure"


def parse_composition(comp: str) -> Tuple[float, float, str]:
    m = re.search(r"(\d+)\s*:\s*(\d+)", comp)
    if not m:
        raise ValueError(f"Unsupported composition format: {comp}")
    a = float(m.group(1))
    b = float(m.group(2))
    unit = "wt" if "wt" in comp.lower() else ("v/v" if "v/v" in comp.lower() else "ratio")
    return a, b, unit


def derive_counts(system: Dict, total_solvent: int, target_molarity: float) -> Tuple[int, int, int, float]:
    solv_a = system["solvent_A"]
    solv_b = system["solvent_B"]
    density = float(system["density_g_cm3"])
    comp_a, comp_b, unit = parse_composition(str(system["composition"]))

    if unit == "v/v":
        frac_b = comp_b / (comp_a + comp_b)
        n_b = round(total_solvent * frac_b)
        n_a = total_solvent - n_b
    elif unit == "wt":
        frac_b = comp_b / (comp_a + comp_b)
        mwa = MOLAR_MASS[solv_a]
        mwb = MOLAR_MASS[solv_b]
        numerator = frac_b * total_solvent * mwa
        denominator = mwb * (1.0 - frac_b) + frac_b * mwa
        n_b = round(numerator / denominator)
        n_a = total_solvent - n_b
    else:
        raise ValueError(f"Unsupported composition unit for {system['id']}: {system['composition']}")

    salt_cont = (
        target_molarity * (n_a * MOLAR_MASS[solv_a] + n_b * MOLAR_MASS[solv_b])
        / (1000.0 * density - target_molarity * MOLAR_MASS["NaPF6"])
    )
    n_salt = max(1, round(salt_cont))
    est_c = 1000.0 * n_salt * density / (
        n_a * MOLAR_MASS[solv_a] + n_b * MOLAR_MASS[solv_b] + n_salt * MOLAR_MASS["NaPF6"]
    )
    return n_a, n_b, n_salt, est_c


def read_smiles_map(path: Path) -> Dict[str, str]:
    mp: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split()
        if len(parts) < 2:
            continue
        mp[parts[0]] = parts[1]
    return mp


def xyz_coord_count(path: Path) -> Tuple[int, int]:
    lines = path.read_text().splitlines()
    nat = int(lines[0].strip())
    coords = [ln for ln in lines[2:] if ln.strip() and len(ln.split()) >= 4]
    return nat, len(coords)


def prepare_xyz(logger: logging.Logger) -> None:
    smiles_path = Path("data/raw/molecules/solvents.smi")
    if not smiles_path.exists():
        raise RuntimeError(f"Missing smiles file: {smiles_path}")
    smiles = read_smiles_map(smiles_path)
    needed = ["EC", "DMC", "DVS", "DMS"]
    xyz_dir = Path("data/prepared/xyz")
    xyz_dir.mkdir(parents=True, exist_ok=True)

    for mol in needed:
        if mol not in smiles:
            raise RuntimeError(f"SMILES for {mol} missing in {smiles_path}")
        out = xyz_dir / f"{mol}.xyz"
        cmd = (
            f"docker compose exec -T gmx bash -lc "
            f"\"obabel -:'{smiles[mol]}' --gen3d -h -O /workspace/{out.as_posix()}\""
        )
        logger.info("Generating XYZ via obabel: %s", mol)
        res = run_shell(cmd)
        if res.returncode != 0:
            raise RuntimeError(f"XYZ generation failed for {mol}: {(res.stderr or res.stdout)[-600:]}")
        if not out.exists():
            raise RuntimeError(f"XYZ output missing after generation: {out}")

    (xyz_dir / "NaP.xyz").write_text(
        "1\nNaP charge=+1 method=single_atom\nNa      0.000000      0.000000      0.000000\n",
        encoding="utf-8",
    )
    (xyz_dir / "PF6.xyz").write_text(
        "7\nPF6 charge=-1 method=ideal_octahedron P-F=1.606A\n"
        "P       0.000000      0.000000      0.000000\n"
        "F       1.606000      0.000000      0.000000\n"
        "F      -1.606000      0.000000      0.000000\n"
        "F       0.000000      1.606000      0.000000\n"
        "F       0.000000     -1.606000      0.000000\n"
        "F       0.000000      0.000000      1.606000\n"
        "F       0.000000      0.000000     -1.606000\n",
        encoding="utf-8",
    )

    for mol in ["EC", "DMC", "DVS", "DMS", "NaP", "PF6"]:
        p = xyz_dir / f"{mol}.xyz"
        if not p.exists():
            raise RuntimeError(f"Missing XYZ after preparation: {p}")
        nat, ncoord = xyz_coord_count(p)
        if nat != ncoord:
            raise RuntimeError(f"XYZ count mismatch in {p}: header={nat} coords={ncoord}")
    logger.info("XYZ preparation complete")


def ensure_ff(logger: logging.Logger, state: Dict) -> None:
    for mol, charge in CHARGE_MAP.items():
        target = Path(f"data/prepared/acpype/{mol}.acpype/{mol}_GMX.itp")
        if target.exists():
            logger.info("FF cache hit: %s", target)
            continue
        cmd = f"bash scripts/ff/run_antechamber_acpype.sh {mol} {charge}"
        logger.info("Generating FF: %s (charge=%s)", mol, charge)
        res = run_shell(cmd)
        if res.returncode != 0:
            summary = (res.stderr or res.stdout or "").strip()[-800:]
            if mol == "PF6":
                msg = (
                    "PF6 ACPYPE generation failed; continuing with locked PF6 ITP. "
                    f"Error tail: {summary}"
                )
                state["warnings"].append(msg)
                logger.warning(msg)
                continue
            raise RuntimeError(f"FF generation failed for {mol}: {summary}")
        if mol != "PF6" and not target.exists():
            raise RuntimeError(f"FF output missing for {mol}: {target}")
    logger.info("Force-field preparation complete")


def output_exists(paths: List[Path]) -> bool:
    return all(p.exists() and p.stat().st_size > 0 for p in paths)


def newest_mtime(paths: List[Path]) -> float:
    mtimes = [p.stat().st_mtime for p in paths if p.exists()]
    return max(mtimes) if mtimes else 0.0


def inputs_changed_since_outputs(input_paths: List[Path], output_paths: List[Path]) -> bool:
    if not input_paths:
        return False
    if not output_exists(output_paths):
        return True
    return newest_mtime(input_paths) > min(p.stat().st_mtime for p in output_paths if p.exists()) + 1e-6


def append_rca(state: Dict, unit: str, stage: str, attempt: int, category: str, detail: str, fix: str, final: str) -> None:
    state["rca"].append(
        {
            "unit": unit,
            "stage": stage,
            "attempt": attempt,
            "category": category,
            "detail": detail[-800:],
            "fix": fix,
            "final": final,
            "time": datetime.now().isoformat(),
        }
    )


def bump_box(system_id: str, seed: int, factor: float, logger: logging.Logger) -> None:
    meta = Path(f"runs/{system_id}/seed-{seed}/packmol/box_meta.json")
    if not meta.exists():
        raise RuntimeError(f"Cannot bump box; missing {meta}")
    data = json.loads(meta.read_text())
    data["box_side_angstrom"] = float(data["box_side_angstrom"]) * factor
    meta.write_text(json.dumps(data, indent=2))
    logger.warning("Bumped box side by factor %.3f for %s seed-%d", factor, system_id, seed)


def latest_log(glob_pat: str) -> str:
    files = sorted(Path(".").glob(glob_pat), key=lambda p: p.stat().st_mtime)
    if not files:
        return ""
    return files[-1].read_text(errors="ignore")[-1000:]


def load_json_if_exists(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_stage_qc(
    *,
    logger: logging.Logger,
    sid: str,
    seed: int,
    stage: str,
    temperature_k: float,
    target_density_g_cm3: float,
    gmx_dir: Path,
) -> tuple[bool, Dict, Path]:
    summary_path = gmx_dir / f"qc_summary_{stage}.json"
    qc_cmd = (
        f"python3 scripts/ops/qc_phase1_seed.py --system {sid} --seed {seed} "
        f"--source-stage {stage} --temperature-k {temperature_k} "
        f"--target-density-g-cm3 {target_density_g_cm3} "
        f"--output-json {summary_path.as_posix()}"
    )
    result = run_shell(qc_cmd)
    summary = load_json_if_exists(summary_path)
    if result.returncode != 0:
        logger.warning("[QC FAIL] %s seed-%d stage=%s", sid, seed, stage)
    else:
        logger.info("[QC PASS] %s seed-%d stage=%s", sid, seed, stage)
    return result.returncode == 0, summary, summary_path


def qc_physical_valid(summary: Dict) -> bool:
    if not summary:
        return False
    gates = summary.get("gates", {})
    required = [
        "density_plateau_ok",
        "temperature_ok",
        "pressure_ok",
        "potential_ok",
        "logs_ok",
        "density_physical_ok",
        "box_edge_ok",
    ]
    return all(bool(gates.get(key, False)) for key in required)


def stage_runner(
    logger: logging.Logger,
    state: Dict,
    unit_key: str,
    stage: str,
    cmd: str,
    outputs: List[Path],
    retries: int,
    input_paths: List[Path] = None,
    retry_fix=None,
) -> bool:
    run_state = state["run_units"].setdefault(unit_key, {"stages": {}, "warnings": []})
    input_paths = input_paths or []
    if run_state["stages"].get(stage) == "PASS" and output_exists(outputs):
        if not inputs_changed_since_outputs(input_paths, outputs):
            logger.info("[SKIP] %s %s already PASS and outputs exist", unit_key, stage)
            return True
        logger.info("[RE-RUN] %s %s inputs changed since cached outputs", unit_key, stage)

    for attempt in range(1, retries + 1):
        logger.info("[RUN ] %s %s attempt %d/%d", unit_key, stage, attempt, retries)
        res = run_shell(cmd)
        combined = (res.stdout or "") + "\n" + (res.stderr or "")
        if res.returncode == 0 and output_exists(outputs):
            run_state["stages"][stage] = "PASS"
            save_state(state)
            logger.info("[PASS] %s %s", unit_key, stage)
            return True

        category = classify_failure(combined)
        fix_note = ""
        if retry_fix is not None:
            try:
                fix_note = retry_fix(attempt, combined) or ""
            except Exception as ex:
                fix_note = f"retry_fix_failed:{ex}"
        append_rca(
            state=state,
            unit=unit_key,
            stage=stage,
            attempt=attempt,
            category=category,
            detail=combined,
            fix=fix_note,
            final="RETRY" if attempt < retries else "FAIL",
        )
        save_state(state)
        logger.warning("[FAIL] %s %s attempt %d category=%s", unit_key, stage, attempt, category)

    run_state["stages"][stage] = "FAIL"
    save_state(state)
    return False


def write_reports(state: Dict, matrix: List[Dict]) -> None:
    ensure_parent(REPORT_MD)
    ensure_parent(REPORT_JSON)

    execution_complete = sum(1 for x in matrix if x.get("execution_complete"))
    source_valid = sum(1 for x in matrix if x.get("source_stage_valid"))
    handoff_ready = sum(1 for x in matrix if x.get("cp2k_handoff_ready"))
    downstream_prod_valid = sum(1 for x in matrix if x.get("downstream_prod_valid"))
    total = len(matrix)
    fail = total - handoff_ready

    payload = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_units": total,
            "execution_complete_units": execution_complete,
            "source_stage_valid_units": source_valid,
            "handoff_ready_units": handoff_ready,
            "downstream_prod_valid_units": downstream_prod_valid,
            "failed_units": fail,
            "success_units": handoff_ready,
        },
        "units": matrix,
        "matrix": matrix,
        "rca": state.get("rca", []),
        "warnings": state.get("warnings", []),
        "diff_summary": PATCHED_FILES,
        "handoff_ready_units": [x["unit"] for x in matrix if x.get("cp2k_handoff_ready")],
    }
    json_tmp = REPORT_JSON.with_suffix(".json.tmp")
    json_tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    json_tmp.replace(REPORT_JSON)

    lines: List[str] = []
    lines.append("# Phase 1 Seed Matrix Report")
    lines.append("")
    lines.append(f"- Generated: {payload['generated_at']}")
    lines.append(f"- Total run-units: {total}")
    lines.append(f"- Execution complete: {execution_complete}")
    lines.append(f"- Source-stage valid: {source_valid}")
    lines.append(f"- CP2K handoff ready: {handoff_ready}")
    lines.append(f"- Downstream prod valid: {downstream_prod_valid}")
    lines.append(f"- Failed: {fail}")
    lines.append("")
    lines.append("## System x Seed Status")
    lines.append("")
    lines.append("| Unit | Source | CalcBox | PackmolIn | Packmol | XYZCount | Assemble | XYZ2GRO | EM | NVT | NPT | PROD | Exec | Source QC | Handoff | Prod Valid |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for x in matrix:
        st = x["stages"]
        lines.append(
            f"| {x['unit']} | {x.get('source_stage','-')} | {st.get('calc_box','-')} | {st.get('packmol_input','-')} | {st.get('packmol','-')} | "
            f"{st.get('xyz_count','-')} | {st.get('assemble','-')} | {st.get('xyz_to_gro','-')} | "
            f"{st.get('em','-')} | {st.get('nvt','-')} | {st.get('npt','-')} | {st.get('prod_short','-')} | "
            f"{'PASS' if x.get('execution_complete') else 'FAIL'} | "
            f"{'PASS' if x.get('source_stage_valid') else 'FAIL'} | "
            f"{'PASS' if x.get('cp2k_handoff_ready') else 'FAIL'} | "
            f"{'PASS' if x.get('downstream_prod_valid') else 'FAIL'} |"
        )
    lines.append("")
    lines.append("## Failures RCA")
    lines.append("")
    if not state.get("rca"):
        lines.append("- No failures recorded.")
    else:
        for r in state["rca"]:
            lines.append(
                f"- `{r['unit']}` `{r['stage']}` attempt={r['attempt']} category={r['category']} "
                f"fix={r['fix']} final={r['final']}"
            )
    lines.append("")
    lines.append("## Diff Summary")
    lines.append("")
    for p in PATCHED_FILES:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("## Next Phase Handoff Seeds")
    lines.append("")
    for u in payload["handoff_ready_units"]:
        lines.append(f"- {u}")

    md_tmp = REPORT_MD.with_suffix(".md.tmp")
    md_tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    md_tmp.replace(REPORT_MD)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", default="study_lock.yml")
    ap.add_argument("--policy", default="inputs/policy/classical_gate.yml")
    ap.add_argument("--source-stage", default="npt")
    ap.add_argument("--total-solvent", type=int, default=120)
    ap.add_argument("--target-molarity", type=float, default=1.0)
    ap.add_argument("--systems", default="T1-01_EC-DMC,T1-02_EC-DVS,T1-03_EC-DMS")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    logger = setup_logger()
    state = load_state() if args.resume else {"run_units": {}, "rca": [], "warnings": [], "started_at": datetime.now().isoformat()}
    save_state(state)
    _policy = load_gate_policy(args.policy)

    lock_path = Path(args.lock)
    if not lock_path.exists():
        logger.error("Missing lock file: %s", lock_path)
        return 2
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    system_filter = {x.strip() for x in args.systems.split(",") if x.strip()}

    logger.info("Preflight: checking docker and tools")
    ps = run_shell("docker compose ps")
    if ps.returncode != 0 or "keti-gmx" not in ps.stdout:
        logger.error("docker compose ps failed or gmx missing")
        return 3
    tool_check = run_shell("docker compose exec -T gmx bash -lc \"command -v gmx && command -v packmol && command -v antechamber && command -v acpype && nvidia-smi >/dev/null\"")
    if tool_check.returncode != 0:
        logger.error("Tool preflight failed: %s", (tool_check.stderr or tool_check.stdout)[-800:])
        return 4

    prepare_xyz(logger)
    ensure_ff(logger, state)
    save_state(state)

    systems = [s for s in lock.get("systems", []) if s.get("active")]
    systems = [s for s in systems if s["id"] in SYSTEM_INDEX]
    systems = [s for s in systems if s["id"] in system_filter]
    systems.sort(key=lambda s: SYSTEM_INDEX[s["id"]])

    matrix: List[Dict] = []

    for s in systems:
        sid = s["id"]
        solv_a = s["solvent_A"]
        solv_b = s["solvent_B"]
        n_a, n_b, n_salt, est_c = derive_counts(s, args.total_solvent, args.target_molarity)
        logger.info(
            "System %s counts: %s=%d %s=%d salt=%d estC=%.3f M",
            sid,
            solv_a,
            n_a,
            solv_b,
            n_b,
            n_salt,
            est_c,
        )

        for seed in seeds:
            unit = f"{sid}/seed-{seed}"
            logger.info("===== UNIT START: %s =====", unit)

            pack_dir = Path(f"runs/{sid}/seed-{seed}/packmol")
            gmx_dir = Path(f"runs/{sid}/seed-{seed}/gromacs")
            pack_dir.mkdir(parents=True, exist_ok=True)
            gmx_dir.mkdir(parents=True, exist_ok=True)

            calc_cmd = (
                f"python3 scripts/packing/calc_initial_box.py --lock {args.lock} --system {sid} "
                f"--solvent-a {solv_a} --solvent-b {solv_b} --n-solvent-a {n_a} --n-solvent-b {n_b} --n-salt {n_salt} "
                f"--output {pack_dir.as_posix()}/box_meta.json "
                f"--log-file logs/packmol/{sid}_seed-{seed}_calc_initial_box.log --verbose"
            )
            packinp_cmd = (
                f"python3 scripts/packing/write_packmol_input.py --system {sid} --seed-number {seed} "
                f"--box-meta {pack_dir.as_posix()}/box_meta.json --output {pack_dir.as_posix()}/packmol.inp "
                f"--solvent-a {solv_a} --solvent-b {solv_b} --n-solvent-a {n_a} --n-solvent-b {n_b} --n-salt {n_salt} "
                f"--log-file logs/packmol/{sid}_seed-{seed}_write_packmol_input.log --verbose"
            )
            packrun_cmd = f"bash scripts/packing/run_packmol.sh {sid} {seed}"
            xyzcheck_cmd = (
                f"python3 scripts/packing/check_xyz_counts.py --xyz {pack_dir.as_posix()}/packed.xyz "
                f"--solvent-a {solv_a} --solvent-b {solv_b} --n-solvent-a {n_a} --n-solvent-b {n_b} --n-salt {n_salt} "
                f"--log-file logs/packmol/{sid}_seed-{seed}_check_xyz_counts.log --verbose"
            )
            assemble_cmd = (
                f"python3 scripts/gromacs/assemble_gmx_system.py --system {sid} --seed-number {seed} "
                f"--solvent-a {solv_a} --solvent-b {solv_b} --n-solvent-a {n_a} --n-solvent-b {n_b} --n-salt {n_salt} "
                f"--log-file logs/gromacs/{sid}_seed-{seed}_assemble_gmx_system.log --verbose"
            )
            xyz2gro_cmd = f"bash scripts/gromacs/xyz_to_gro.sh {sid} {seed}"

            ok = stage_runner(
                logger,
                state,
                unit,
                "calc_box",
                calc_cmd,
                [pack_dir / "box_meta.json"],
                retries=2,
                input_paths=[lock_path, Path("data/raw/molecules/solvents.smi")],
            )
            if ok:
                ok = stage_runner(
                    logger,
                    state,
                    unit,
                    "packmol_input",
                    packinp_cmd,
                    [pack_dir / "packmol.inp"],
                    retries=2,
                    input_paths=[pack_dir / "box_meta.json"],
                )

            def packmol_fix(attempt: int, _combined: str) -> str:
                if attempt == 1:
                    bump_box(sid, seed, 1.03, logger)
                elif attempt == 2:
                    bump_box(sid, seed, 1.05, logger)
                else:
                    return "no_additional_packmol_fix"
                run_shell(packinp_cmd)
                return f"box_scaled_and_packmol_input_regenerated_attempt_{attempt}"

            if ok:
                ok = stage_runner(
                    logger,
                    state,
                    unit,
                    "packmol",
                    packrun_cmd,
                    [pack_dir / "packed.xyz"],
                    retries=3,
                    input_paths=[
                        pack_dir / "packmol.inp",
                        Path(f"data/prepared/xyz/{solv_a}.xyz"),
                        Path(f"data/prepared/xyz/{solv_b}.xyz"),
                        Path("data/prepared/xyz/PF6.xyz"),
                    ],
                    retry_fix=packmol_fix,
                )
            if ok:
                ok = stage_runner(
                    logger,
                    state,
                    unit,
                    "xyz_count",
                    xyzcheck_cmd,
                    [pack_dir / "packed.xyz"],
                    retries=2,
                    input_paths=[pack_dir / "packed.xyz"],
                )
            if ok:
                ok = stage_runner(
                    logger,
                    state,
                    unit,
                    "assemble",
                    assemble_cmd,
                    [gmx_dir / "topol.top"],
                    retries=2,
                    input_paths=[
                        pack_dir / "packed.xyz",
                        Path("inputs/gromacs/NA_LOCKED.itp"),
                        Path("data/prepared/acpype/EC.acpype/EC_GMX.itp"),
                        Path("data/prepared/acpype/DMC.acpype/DMC_GMX.itp"),
                        Path("data/prepared/acpype/DVS.acpype/DVS_GMX.itp"),
                        Path("data/prepared/acpype/DMS.acpype/DMS_GMX.itp"),
                        Path("data/prepared/acpype/PF6.acpype/PF6_GMX.itp"),
                    ],
                )
            if ok:
                ok = stage_runner(
                    logger,
                    state,
                    unit,
                    "xyz_to_gro",
                    xyz2gro_cmd,
                    [gmx_dir / "conf.gro"],
                    retries=2,
                    input_paths=[pack_dir / "packed.xyz", gmx_dir / "topol.top"],
                )

            stage_sequence = ["em", "nvt", "npt", "prod_short"]
            for stage in (stage_sequence if ok else []):
                gmx_cmd = f"bash scripts/gromacs/run_gromacs_stage.sh {sid} {seed} {stage}"

                def gmx_fix(attempt: int, combined: str, sid=sid, seed=seed) -> str:
                    lower = combined.lower()
                    if "no such moleculetype" in lower or "atomtype" in lower:
                        run_shell(assemble_cmd)
                        return "reassembled_topology_for_grompp"
                    if "cut-off length is longer than half the shortest box vector" in lower:
                        factor = 1.03 if attempt == 1 else 1.05 if attempt == 2 else 1.08
                        bump_box(sid, seed, factor, logger)
                        run_shell(packinp_cmd)
                        run_shell(packrun_cmd)
                        run_shell(xyzcheck_cmd)
                        run_shell(assemble_cmd)
                        run_shell(xyz2gro_cmd)
                        return f"box_scaled_{factor:.3f}_and_coordinates_regenerated"
                    if "fatal error" in lower and "grompp" in lower:
                        run_shell(assemble_cmd)
                        return "reassembled_after_grompp_fatal"
                    if attempt < 3:
                        return "retry_same_stage_after_log_review"
                    return "no_further_fix"

                out_files = [gmx_dir / f"{stage}.tpr", gmx_dir / f"{stage}.gro", gmx_dir / f"{stage}.edr", gmx_dir / f"{stage}.log"]
                ok = stage_runner(
                    logger,
                    state,
                    unit,
                    stage,
                    gmx_cmd,
                    out_files,
                    retries=3,
                    input_paths=[
                        gmx_dir / (
                            "conf.gro"
                            if stage == "em"
                            else "em.gro"
                            if stage == "nvt"
                            else "nvt.gro"
                            if stage == "npt"
                            else "npt.gro"
                        ),
                        Path(f"inputs/gromacs/{stage}.mdp"),
                        gmx_dir / "topol.top",
                    ],
                    retry_fix=gmx_fix,
                )
                if not ok:
                    break

            execution_complete = all(
                state["run_units"].get(unit, {}).get("stages", {}).get(stage_name) == "PASS"
                for stage_name in ["calc_box", "packmol_input", "packmol", "xyz_count", "assemble", "xyz_to_gro", *stage_sequence]
            )
            source_stage = args.source_stage
            source_stage_key_files_ok = output_exists(
                [
                    pack_dir / "packed.xyz",
                    gmx_dir / "conf.gro",
                    gmx_dir / "topol.top",
                    gmx_dir / f"{source_stage}.tpr",
                    gmx_dir / f"{source_stage}.gro",
                    gmx_dir / f"{source_stage}.edr",
                    gmx_dir / f"{source_stage}.log",
                ]
            )
            source_qc_pass = False
            source_density_plateau = False
            source_qc_summary: Dict = {}
            source_qc_path = gmx_dir / f"qc_summary_{source_stage}.json"
            if source_stage_key_files_ok:
                source_qc_pass, source_qc_summary, source_qc_path = run_stage_qc(
                    logger=logger,
                    sid=sid,
                    seed=seed,
                    stage=source_stage,
                    temperature_k=float(s["temperature_K"]),
                    target_density_g_cm3=float(s["density_g_cm3"]),
                    gmx_dir=gmx_dir,
                )
                if source_stage == "npt":
                    (gmx_dir / "qc_summary.json").write_text(
                        json.dumps(source_qc_summary, indent=2),
                        encoding="utf-8",
                    )
                source_density_plateau = bool(source_qc_summary.get("gates", {}).get("density_plateau_ok"))
                if not source_qc_pass:
                    append_rca(
                        state=state,
                        unit=unit,
                        stage=f"qc:{source_stage}",
                        attempt=1,
                        category="source_stage_quality_gate_failed",
                        detail=json.dumps(source_qc_summary, indent=2),
                        fix="none",
                        final="FAIL",
                    )
                    save_state(state)

            prod_short_key_files_ok = output_exists(
                [
                    gmx_dir / "prod_short.tpr",
                    gmx_dir / "prod_short.gro",
                    gmx_dir / "prod_short.edr",
                    gmx_dir / "prod_short.log",
                ]
            )
            prod_qc_pass = False
            prod_qc_summary: Dict = {}
            if prod_short_key_files_ok:
                prod_qc_pass, prod_qc_summary, _ = run_stage_qc(
                    logger=logger,
                    sid=sid,
                    seed=seed,
                    stage="prod_short",
                    temperature_k=float(s["temperature_K"]),
                    target_density_g_cm3=float(s["density_g_cm3"]),
                    gmx_dir=gmx_dir,
                )

            source_stage_valid = bool(source_qc_summary.get("source_stage_valid", False))
            cp2k_handoff_ready = bool(source_qc_summary.get("cp2k_handoff_ready", False))
            downstream_prod_valid = qc_physical_valid(prod_qc_summary) if prod_short_key_files_ok else False
            unit_stages = state["run_units"].get(unit, {}).get("stages", {})
            matrix.append(
                {
                    "unit": unit,
                    "system": sid,
                    "seed": seed,
                    "n_solvent_a": n_a,
                    "n_solvent_b": n_b,
                    "n_salt": n_salt,
                    "est_molarity_M": est_c,
                    "stages": unit_stages,
                    "source_stage": source_stage,
                    "source_stage_key_files_ok": source_stage_key_files_ok,
                    "prod_short_key_files_ok": prod_short_key_files_ok,
                    "source_qc_pass": source_qc_pass,
                    "source_density_plateau": source_density_plateau,
                    "source_stage_valid": source_stage_valid,
                    "cp2k_handoff_ready": cp2k_handoff_ready,
                    "downstream_prod_valid": downstream_prod_valid,
                    "execution_complete": execution_complete,
                    "unit_pass": cp2k_handoff_ready,
                    "source_qc_summary": source_qc_summary,
                    "prod_short_qc_summary": prod_qc_summary,
                    "reason_codes": source_qc_summary.get("reason_codes", []),
                }
            )
            logger.info(
                "===== UNIT END: %s execution_complete=%s source_valid=%s handoff_ready=%s prod_valid=%s =====",
                unit,
                execution_complete,
                source_stage_valid,
                cp2k_handoff_ready,
                downstream_prod_valid,
            )

    write_reports(state, matrix)
    logger.info("Wrote reports: %s and %s", REPORT_MD, REPORT_JSON)

    total = len(matrix)
    success = sum(1 for x in matrix if x["unit_pass"])
    logger.info("FINAL: success=%d / total=%d", success, total)
    return 0 if total > 0 and success == total else 5


if __name__ == "__main__":
    sys.exit(main())
