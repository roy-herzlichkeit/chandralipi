#!/usr/bin/env bash
# check_P1.00 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_tag phase-0-approved
git merge-base --is-ancestor phase-0-approved HEAD || fail "phase-0-approved is not an ancestor of HEAD"
harness_pytest Phase_0/harness/tests/test_contracts_P0.py
ok P1.00
