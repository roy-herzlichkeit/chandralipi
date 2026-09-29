#!/usr/bin/env bash
# check_P1B.03 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1B
require_file tests/test_consensus.py
harness_pytest Phase_1B/harness/tests/test_contracts_P1B.py -k consensus
harness_pytest Phase_1B/harness/tests/test_P1B_03.py
repo_pytest tests/test_consensus.py
ruff_files src/lunar_reg/consensus.py tests/test_consensus.py
ok P1B.03
