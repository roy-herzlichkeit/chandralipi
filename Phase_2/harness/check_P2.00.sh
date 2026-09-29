#!/usr/bin/env bash
# check_P2.00 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
require_tag phase-1-approved
git merge-base --is-ancestor phase-1-approved HEAD || fail "phase-1-approved is not an ancestor of HEAD"
gpu_available || fail "CUDA not available"
harness_pytest Phase_0/harness/tests/test_contracts_P0.py Phase_1/harness/tests/test_contracts_P1.py
ok P2.00
