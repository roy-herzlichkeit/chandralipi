#!/usr/bin/env bash
# check_P3.09 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-3
harness_pytest Phase_3/harness/tests/test_P3_09.py
ok P3.09
