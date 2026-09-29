#!/usr/bin/env bash
# check_P0.10 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_file tests/test_results_v2.py
harness_pytest Phase_0/harness/tests/test_contracts_P0.py -k "C04 or C05"
harness_pytest Phase_0/harness/tests/test_P0_10.py
repo_pytest tests/test_results_v2.py tests/test_results_and_pipeline.py
ruff_files src/lunar_reg/results.py src/lunar_reg/pipeline.py scripts/reindex_results.py scripts/run_vikram.py scripts/build_demo_results.py tests/test_results_v2.py
ok P0.10
