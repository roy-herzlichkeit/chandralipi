#!/usr/bin/env bash
# check_P1B.06 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1B
harness_pytest Phase_1B/harness/tests/test_P1B_06.py
ok P1B.06
