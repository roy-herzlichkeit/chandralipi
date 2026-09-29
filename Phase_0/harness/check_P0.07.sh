#!/usr/bin/env bash
# check_P0.07 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_file src/lunar_reg/provenance.py
require_file src/lunar_reg/runrecord.py
require_file tests/test_estimate_seeded.py
harness_pytest Phase_0/harness/tests/test_contracts_P0.py -k "C01 or C06 or C15"
harness_pytest Phase_0/harness/tests/test_P0_07.py
repo_pytest tests/test_estimate_seeded.py tests/test_align.py
ruff_files src/lunar_reg/provenance.py src/lunar_reg/runrecord.py src/lunar_reg/align/estimate.py tests/test_estimate_seeded.py
ok P0.07
