#!/usr/bin/env bash
set -euo pipefail
cd /mnt/d/PSID_BAMOF/try04

cat <<MD >> PROGRESS.md
## Phase A-3: numpy 준비
MD

if python3 -c import
