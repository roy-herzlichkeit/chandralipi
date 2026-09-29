#!/usr/bin/env bash
# check_P4.02 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-4
require_file tests/test_node_cache.py
harness_pytest Phase_4/harness/tests/test_P4_02.py
repo_pytest tests/test_node_cache.py tests/test_worker.py
ruff_files src/lunar_reg/distributed/cache.py src/lunar_reg/distributed/worker.py tests/test_node_cache.py
ok P4.02
