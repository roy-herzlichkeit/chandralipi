#!/usr/bin/env bash
# check_P1.20 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
harness_pytest Phase_1/harness/tests/test_P1_20.py
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k C20
ok P1.20
