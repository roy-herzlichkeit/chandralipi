#!/usr/bin/env bash
# check_P2.10 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
require_file tests/test_runner_native.py
harness_pytest Phase_2/harness/tests/test_P2_10.py
repo_pytest tests/test_runner_native.py tests/test_site_runner.py
ruff_files src/lunar_reg/sites/runner.py scripts/run_vikram.py tests/test_runner_native.py
ok P2.10
