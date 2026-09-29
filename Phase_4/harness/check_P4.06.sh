#!/usr/bin/env bash
# check_P4.06 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-4
harness_pytest Phase_4/harness/tests/test_P4_06.py
ok P4.06
