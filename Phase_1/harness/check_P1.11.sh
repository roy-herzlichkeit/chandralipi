#!/usr/bin/env bash
# check_P1.11 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_sun.py
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k C13
harness_pytest Phase_1/harness/tests/test_P1_11.py
repo_pytest tests/test_sun.py
ruff_files src/lunar_reg/ingest/sun.py scripts/fit_reference_sun.py tests/test_sun.py
ok P1.11
