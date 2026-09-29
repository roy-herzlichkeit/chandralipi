#!/usr/bin/env bash
# check_P2.05 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
require_file tests/test_pipeline_gpu.py
harness_pytest Phase_2/harness/tests/test_contracts_P2.py -k C03
harness_pytest Phase_2/harness/tests/test_P2_05.py
repo_pytest tests/test_pipeline_gpu.py tests/test_pipeline_counts.py
ruff_files src/lunar_reg/pipeline.py src/lunar_reg/match/learned.py tests/test_pipeline_gpu.py
ok P2.05
