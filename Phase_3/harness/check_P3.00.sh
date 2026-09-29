#!/usr/bin/env bash
# check_P3.00 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-3
require_tag phase-1B-approved
git merge-base --is-ancestor phase-1B-approved HEAD || fail "phase-1B-approved is not an ancestor of HEAD"
harness_pytest Phase_0/harness/tests/test_contracts_P0.py Phase_1/harness/tests/test_contracts_P1.py Phase_2/harness/tests/test_contracts_P2.py
ok P3.00
