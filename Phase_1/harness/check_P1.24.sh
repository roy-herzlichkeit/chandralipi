#!/usr/bin/env bash
# check_P1.24 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file configs/references.json
require_file src/lunar_reg/cross.py
require_file scripts/run_cross.py
require_file tests/test_cross_pairs.py
harness_pytest Phase_1/harness/tests/test_P1_24.py
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k "C10 or C11 or C28"
repo_pytest tests/test_cross_pairs.py tests/test_pairs.py tests/test_lro_georeference.py
ruff_files src/lunar_reg/cross.py src/lunar_reg/ingest/lro.py src/lunar_reg/pairs.py src/lunar_reg/sites/runner.py scripts/run_cross.py tests/test_cross_pairs.py
ok P1.24
