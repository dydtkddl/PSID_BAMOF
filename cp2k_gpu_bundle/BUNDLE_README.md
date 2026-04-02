# CP2K GPU Bundle
## Required for rebuild / redeploy
- compose.yaml
- .env (cp2k image/env params)
- containers/cp2k/Dockerfile
- inputs/cp2k/*.inp.tmpl
- scripts/cp2k/*
- scripts/ops/classical_state_gate.py
- scripts/ops/run_phase1_seed_matrix.py
- scripts/ops/qc_phase1_seed.py
- scripts/ops/render_phase1_report_from_outputs.py

Note: This bundle excludes run artifacts/logs and archive folders.
