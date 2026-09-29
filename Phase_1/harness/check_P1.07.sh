#!/usr/bin/env bash
# check_P1.07 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file docs/DATUM.md
require_file tests/test_datum.py
harness_pytest Phase_1/harness/tests/test_P1_07.py
repo_pytest tests/test_datum.py
ruff_files src/lunar_reg/constants.py tests/test_datum.py
ok P1.07
