#!/usr/bin/env bash
# check_P3.05 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-3
require_file tests/test_worker.py
harness_pytest Phase_3/harness/tests/test_contracts_P3.py -k C25
harness_pytest Phase_3/harness/tests/test_P3_05.py
repo_pytest tests/test_worker.py
ruff_files src/lunar_reg/distributed/worker.py tests/test_worker.py
ok P3.05
