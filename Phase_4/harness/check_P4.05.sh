#!/usr/bin/env bash
# check_P4.05 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-4
require_file tests/test_multihost_semantics.py
harness_pytest Phase_4/harness/tests/test_P4_05.py
repo_pytest tests/test_multihost_semantics.py
ruff_files src/lunar_reg/distributed/outcome.py src/lunar_reg/distributed/reducer.py src/lunar_reg/distributed/worker.py tests/test_multihost_semantics.py
ok P4.05
