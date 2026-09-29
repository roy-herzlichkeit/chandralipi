#!/usr/bin/env bash
# check_P2.08 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
require_file tests/test_native.py
harness_pytest Phase_2/harness/tests/test_contracts_P2.py -k C19
harness_pytest Phase_2/harness/tests/test_P2_08.py
repo_pytest tests/test_native.py
ruff_files src/lunar_reg/align/native.py tests/test_native.py
ok P2.08
