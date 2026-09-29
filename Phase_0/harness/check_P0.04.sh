#!/usr/bin/env bash
# check_P0.04 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_absent src/lunar_reg/ingest/footprint.py
require_absent configs/default.yaml
harness_pytest Phase_0/harness/tests/test_P0_04.py
repo_pytest tests/test_overlap.py
ruff_files src/lunar_reg/constants.py src/lunar_reg/ingest/__init__.py src/lunar_reg/ingest/overlap.py
ok P0.04
