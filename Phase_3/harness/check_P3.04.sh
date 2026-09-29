#!/usr/bin/env bash
# check_P3.04 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-3
require_file tests/test_local_queue.py
harness_pytest Phase_3/harness/tests/test_contracts_P3.py -k C24
harness_pytest Phase_3/harness/tests/test_P3_04.py
repo_pytest tests/test_local_queue.py
ruff_files src/lunar_reg/distributed/queue.py tests/test_local_queue.py
ok P3.04
