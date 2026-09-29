#!/usr/bin/env bash
# check_P3.08 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-3
require_file tests/test_distributed_faults.py
harness_pytest Phase_3/harness/tests/test_P3_08.py
repo_pytest tests/test_distributed_faults.py
ruff_files src/lunar_reg/distributed/faults.py tests/test_distributed_faults.py
ok P3.08
