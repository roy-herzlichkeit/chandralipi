#!/usr/bin/env bash
# check_P1.16 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_site_runner.py
harness_pytest Phase_1/harness/tests/test_P1_16.py
repo_pytest tests/test_site_runner.py tests/test_run_vikram_geometry.py
ruff_files src/lunar_reg/sites/__init__.py src/lunar_reg/sites/runner.py scripts/run_vikram.py tests/test_site_runner.py
ok P1.16
