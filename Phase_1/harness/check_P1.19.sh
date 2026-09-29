#!/usr/bin/env bash
# check_P1.19 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
harness_pytest Phase_1/harness/tests/test_P1_19.py
ruff_files src/lunar_reg/pipeline.py
ok P1.19
