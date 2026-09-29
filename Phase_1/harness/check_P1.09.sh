#!/usr/bin/env bash
# check_P1.09 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_preprocess_geometry.py
harness_pytest Phase_1/harness/tests/test_P1_09.py
repo_pytest tests/test_preprocess_pipeline.py tests/test_preprocess_geometry.py
ruff_files src/lunar_reg/preprocess/pipeline.py src/lunar_reg/preprocess/resample.py src/lunar_reg/preprocess/georeference.py src/lunar_reg/constants.py tests/test_preprocess_geometry.py
ok P1.09
