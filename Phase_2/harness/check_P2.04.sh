#!/usr/bin/env bash
# check_P2.04 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
harness_pytest Phase_2/harness/tests/test_P2_04.py
ok P2.04
