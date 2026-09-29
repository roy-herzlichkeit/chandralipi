#!/usr/bin/env bash
# check_P1.22 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
harness_pytest Phase_1/harness/tests/test_P1_22.py
ok P1.22
