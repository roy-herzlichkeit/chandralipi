#!/usr/bin/env bash
# check_P1B.05 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1B
require_file tests/test_runner_bridge.py
harness_pytest Phase_1B/harness/tests/test_P1B_05.py
repo_pytest tests/test_runner_bridge.py tests/test_site_runner.py
ruff_files src/lunar_reg/sites/runner.py scripts/run_vikram.py tests/test_runner_bridge.py
ok P1B.05
