#!/usr/bin/env bash
# check_P4.03 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-4
require_file tests/test_scheduler.py
harness_pytest Phase_4/harness/tests/test_P4_03.py
repo_pytest tests/test_scheduler.py tests/test_planner.py
ruff_files src/lunar_reg/distributed/scheduler.py src/lunar_reg/distributed/planner.py tests/test_scheduler.py
ok P4.03
