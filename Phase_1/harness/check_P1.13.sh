#!/usr/bin/env bash
# check_P1.13 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_pairs.py
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k C11
harness_pytest Phase_1/harness/tests/test_P1_13.py
repo_pytest tests/test_pairs.py
ruff_files src/lunar_reg/pairs.py tests/test_pairs.py
ok P1.13
