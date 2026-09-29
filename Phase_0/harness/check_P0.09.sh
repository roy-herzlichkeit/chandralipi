#!/usr/bin/env bash
# check_P0.09 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_file tests/test_pipeline_counts.py
harness_pytest Phase_0/harness/tests/test_contracts_P0.py -k "C02 or C03"
harness_pytest Phase_0/harness/tests/test_P0_09.py
repo_pytest tests/test_pipeline_counts.py tests/test_pipeline.py tests/test_eval.py
ruff_files src/lunar_reg/pipeline.py src/lunar_reg/eval/metrics.py src/lunar_reg/match/classical.py src/lunar_reg/match/rift2/matcher.py tests/test_pipeline_counts.py
ok P0.09
