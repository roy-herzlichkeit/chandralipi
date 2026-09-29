#!/usr/bin/env bash
# check_P0.11 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_file tests/test_run_vikram_geometry.py
harness_pytest Phase_0/harness/tests/test_P0_11.py
repo_pytest tests/test_run_vikram_geometry.py tests/test_registered_export.py
ruff_files scripts/run_vikram.py tests/test_run_vikram_geometry.py
ok P0.11
