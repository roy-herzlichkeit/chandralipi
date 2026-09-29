#!/usr/bin/env bash
# check_P1.08 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_preprocess_nodata.py
harness_pytest Phase_1/harness/tests/test_P1_08.py
repo_pytest tests/test_preprocess.py tests/test_preprocess_nodata.py
ruff_files src/lunar_reg/preprocess/radiometric.py src/lunar_reg/preprocess/shadow.py tests/test_preprocess_nodata.py
ok P1.08
