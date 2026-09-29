#!/usr/bin/env bash
# check_P0.08 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_file tests/test_ecc_fidelity.py
harness_pytest Phase_0/harness/tests/test_contracts_P0.py -k "C07"
harness_pytest Phase_0/harness/tests/test_P0_08.py
repo_pytest tests/test_ecc_fidelity.py tests/test_align.py
ruff_files src/lunar_reg/align/refine.py tests/test_ecc_fidelity.py
ok P0.08
