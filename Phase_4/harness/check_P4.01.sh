#!/usr/bin/env bash
# check_P4.01 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-4
require_file tests/test_redis_queue.py
harness_pytest Phase_4/harness/tests/test_contracts_P4.py -k "conformance or max_bytes"
harness_pytest Phase_4/harness/tests/test_P4_01.py
repo_pytest tests/test_redis_queue.py
ruff_files src/lunar_reg/distributed/redis_queue.py tests/test_redis_queue.py
ok P4.01
