#!/usr/bin/env bash
# check_P3.07 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-3
require_file tests/test_distributed_runner.py
harness_pytest Phase_3/harness/tests/test_P3_07.py
repo_pytest tests/test_distributed_runner.py
ruff_files src/lunar_reg/distributed/runner.py src/lunar_reg/cli.py tests/test_distributed_runner.py
ok P3.07
