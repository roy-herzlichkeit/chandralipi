#!/usr/bin/env bash
# check_P1.12 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_agreement.py
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k C14
harness_pytest Phase_1/harness/tests/test_P1_12.py
repo_pytest tests/test_agreement.py
ruff_files src/lunar_reg/eval/agreement.py tests/test_agreement.py
ok P1.12
