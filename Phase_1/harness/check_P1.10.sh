#!/usr/bin/env bash
# check_P1.10 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_presets.py
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k "C03 or C12"
harness_pytest Phase_1/harness/tests/test_P1_10.py
repo_pytest tests/test_presets.py tests/test_pipeline.py
ruff_files src/lunar_reg/preprocess/presets.py src/lunar_reg/pipeline.py tests/test_presets.py
ok P1.10
