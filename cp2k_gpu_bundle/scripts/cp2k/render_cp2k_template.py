#!/usr/bin/env python3
import argparse
import logging
import sys
import time
from pathlib import Path

import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

console = Console()

TOKENS = [
    "__PROJECT__",
    "__COORD_FILE__",
    "__CELL_FILE__",
    "__CHARGE__",
    "__CUTOFF__",
    "__REL_CUTOFF__",
    "__TEMP__",
    "__TIMESTEP__",
    "__STEPS__",
    "__WALLTIME__",
    "__WFN_RESTART__",
    "__EXT_RESTART__",
]


def setup_logger(log_file: Path, verbose: bool) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("render_cp2k_template")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    console_handler = RichHandler(console=console, rich_tracebacks=True)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def locked_temperature(lock_file: Path, system_id: str) -> str | None:
    data = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
    for row in data.get("systems", []):
        if row.get("id") == system_id:
            value = row.get("temperature_K")
            return None if value is None else str(value)
    return None


def main() -> int:
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--coord-file", required=True)
    ap.add_argument("--cell-file", required=True)
    ap.add_argument("--charge", default="0")
    ap.add_argument("--cutoff", required=True)
    ap.add_argument("--rel-cutoff", required=True)
    ap.add_argument("--temp")
    ap.add_argument("--timestep", default="0.5")
    ap.add_argument("--steps", default="1000")
    ap.add_argument("--walltime", default="23:50:00")
    ap.add_argument("--wfn-restart", default="")
    ap.add_argument("--ext-restart", default="")
    ap.add_argument("--system", default="")
    ap.add_argument("--lock-file", default="study_lock.yml")
    ap.add_argument("--log-file", default="logs/cp2k/render_cp2k_template.log")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logger = setup_logger(Path(args.log_file), args.verbose)
    template = Path(args.template)
    output = Path(args.output)
    if not template.exists():
        logger.error("Missing template: %s", template)
        return 2

    text = template.read_text(encoding="utf-8")
    template_has_temp = "__TEMP__" in text
    template_has_wfn = "__WFN_RESTART__" in text or "WFN_RESTART_FILE_NAME" in text
    template_has_ext = "__EXT_RESTART__" in text or "RESTART_FILE_NAME ${EXT_RESTART}" in text

    temp_value = args.temp
    if template_has_temp and temp_value is None:
        if not args.system:
            logger.error("Template requires temperature; provide --temp or --system.")
            return 3
        lock_path = Path(args.lock_file)
        if not lock_path.exists():
            logger.error("Missing lock file: %s", lock_path)
            return 4
        temp_value = locked_temperature(lock_path, args.system)
        if temp_value is None:
            logger.error("System %s not found in %s", args.system, lock_path)
            return 5
        logger.info("Resolved temperature from lock: system=%s temp=%s", args.system, temp_value)

    values = {
        "__PROJECT__": args.project,
        "__COORD_FILE__": args.coord_file,
        "__CELL_FILE__": args.cell_file,
        "__CHARGE__": str(args.charge),
        "__CUTOFF__": str(args.cutoff),
        "__REL_CUTOFF__": str(args.rel_cutoff),
        "__TEMP__": "" if temp_value is None else str(temp_value),
        "__TIMESTEP__": str(args.timestep),
        "__STEPS__": str(args.steps),
        "__WALLTIME__": str(args.walltime),
        "__WFN_RESTART__": str(args.wfn_restart),
        "__EXT_RESTART__": str(args.ext_restart),
    }

    for token, value in values.items():
        text = text.replace(token, value)

    unresolved = [token for token in TOKENS if token in text]
    if unresolved:
        logger.error("Unresolved token(s): %s", unresolved)
        return 6

    if template_has_wfn and not args.wfn_restart.strip():
        logger.error("Template requires --wfn-restart")
        return 7
    if template_has_ext and not args.ext_restart.strip():
        logger.error("Template requires --ext-restart")
        return 8

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")

    table = Table(title="CP2K Template Rendered")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Template", str(template))
    table.add_row("Output", str(output))
    table.add_row("Project", args.project)
    if temp_value is not None:
        table.add_row("Temperature K", str(temp_value))
    table.add_row("Elapsed s", f"{time.time() - t0:.2f}")
    console.print(table)
    logger.info("Rendered %s -> %s", template, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
