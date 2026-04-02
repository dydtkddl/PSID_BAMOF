#!/usr/bin/env python3
"""extract_try03_energies.py
Extract final energies from try03 references and compare dissociation numbers.
"""

from __future__ import annotations

from pathlib import Path
import json
import re

HA_TO_KJ = 2625.499638
TOLERANCE = 5.0

TARGETS = {
    "BAMOF_1IP_cluster": Path("/mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/simulation.input.out"),
    "BAMOF_1IP_dissociate": Path("/mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_dissociate-1/simulation.input.out"),
    "MIL125_1IP_cluster": Path("/mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/MIL125_EMIM_TFSI_Cluster-1/simulation.input.out"),
    "MIL125_1IP_dissociate": Path("/mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/MIL125_EMIM_TFSI_dissociate-1/simulation.input.out"),
}


def parse_energy(path: Path):
    if not path.exists():
        return {"status": "missing_file", "energy_ha": None, "energy_kj": None, "converged": False, "scf_fail": 0, "steps": 0}
    text = path.read_text(errors="ignore")
    m = re.findall(r"ENERGY\\| Total FORCE_EVAL \\( QS \\) energy \\[hartree\\]\\s+([+-]?[0-9]+\\.[0-9]+(?:[eEdD][+-]?[0-9]+)?)", text)
    if not m:
        return {"status": "no_energy", "energy_ha": None, "energy_kj": None, "converged": False, "scf_fail": text.count("SCF run NOT converged"), "steps": text.count("OPTIMIZATION STEP:")}
    e = float(m[-1])
    return {
        "status": "ok",
        "energy_ha": e,
        "energy_kj": e * HA_TO_KJ,
        "converged": "GEOMETRY OPTIMIZATION COMPLETED" in text,
        "scf_fail": text.count("SCF run NOT converged"),
        "steps": text.count("OPTIMIZATION STEP:"),
    }


def dissociation_value(cluster: dict, diss: dict):
    if cluster["energy_ha"] is None or diss["energy_ha"] is None:
        return {"status": "pending", "value_kj": None}
    return {"status": "ok", "value_kj": (diss["energy_ha"] - cluster["energy_ha"]) * HA_TO_KJ}


def warning(name, expected, value):
    if value is None:
        return None
    if abs(value - expected) > TOLERANCE:
        return f"{name} mismatch: {value:.2f} vs expected {expected:.2f} (kJ/mol)"
    return None


def main():
    out = Path("/mnt/d/PSID_BAMOF/try04/00_reference_structures/try03_energies.json")
    parsed = {k: parse_energy(v) for k, v in TARGETS.items()}

    ed_bamof = dissociation_value(parsed["BAMOF_1IP_cluster"], parsed["BAMOF_1IP_dissociate"])
    ed_mil = dissociation_value(parsed["MIL125_1IP_cluster"], parsed["MIL125_1IP_dissociate"])

    data = {
        "results": parsed,
        "ediss_kj": {
            "BAMOF_1IP": ed_bamof,
            "MIL125_1IP": ed_mil,
        },
        "reference_kj": {"gas_phase": 225.06, "bamof_1ip_ref": 17.77, "mil125_1ip_ref": 23.05},
        "warnings": [],
    }

    for msg in (
        warning("BAMOF 1IP", 17.77, ed_bamof.get("value_kj")),
        warning("MIL125 1IP", 23.05, ed_mil.get("value_kj")),
    ):
        if msg:
            data["warnings"].append(msg)

    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"WROTE: {out}")
    if ed_bamof["status"] == "ok":
        print(f"BAMOF 1IP E_diss = {ed_bamof['value_kj']:.4f} kJ/mol")
    if ed_mil["status"] == "ok":
        print(f"MIL125 1IP E_diss = {ed_mil['value_kj']:.4f} kJ/mol")


if __name__ == "__main__":
    main()
