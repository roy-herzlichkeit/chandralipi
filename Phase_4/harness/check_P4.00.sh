#!/usr/bin/env bash
# check_P4.00 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-4
require_tag phase-3-approved
git merge-base --is-ancestor phase-3-approved HEAD || fail "phase-3-approved is not an ancestor of HEAD"
harness_pytest Phase_0/harness/tests/test_contracts_P0.py Phase_1/harness/tests/test_contracts_P1.py Phase_2/harness/tests/test_contracts_P2.py Phase_3/harness/tests/test_contracts_P3.py
ok P4.00
