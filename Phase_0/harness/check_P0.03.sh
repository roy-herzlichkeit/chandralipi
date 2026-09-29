#!/usr/bin/env bash
# check_P0.03 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
harness_pytest Phase_0/harness/tests/test_P0_03.py
repo_pytest tests/test_preprocess.py tests/test_pseudo_gt.py
ruff_files src/lunar_reg/preprocess/radiometric.py src/lunar_reg/preprocess/__init__.py src/lunar_reg/constants.py src/lunar_reg/ingest/pseudo_gt.py
ok P0.03
