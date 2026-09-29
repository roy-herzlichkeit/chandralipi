#!/usr/bin/env bash
# check_P1.06 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_overlap_fixes.py
harness_pytest Phase_1/harness/tests/test_P1_06.py
repo_pytest tests/test_overlap.py tests/test_overlap_fixes.py tests/test_pseudo_gt.py
ruff_files src/lunar_reg/ingest/overlap.py src/lunar_reg/ingest/pseudo_gt.py tests/test_overlap_fixes.py
ok P1.06
