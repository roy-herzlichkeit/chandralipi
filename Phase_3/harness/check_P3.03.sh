#!/usr/bin/env bash
# check_P3.03 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-3
require_file tests/test_planner.py
harness_pytest Phase_3/harness/tests/test_P3_03.py
repo_pytest tests/test_planner.py
ruff_files src/lunar_reg/distributed/planner.py tests/test_planner.py
ok P3.03
