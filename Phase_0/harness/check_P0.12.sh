#!/usr/bin/env bash
# check_P0.12 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_file tests/test_eval_fixes.py
harness_pytest Phase_0/harness/tests/test_P0_12.py
repo_pytest tests/test_eval_fixes.py tests/test_eval.py tests/test_conditioning.py
ruff_files src/lunar_reg/eval/error_budget.py src/lunar_reg/eval/conditioning.py src/lunar_reg/eval/uniformity.py tests/test_eval_fixes.py
ok P0.12
