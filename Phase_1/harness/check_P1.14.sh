#!/usr/bin/env bash
# check_P1.14 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_matcher_registry.py
harness_pytest Phase_1/harness/tests/test_P1_14.py
repo_pytest tests/test_matcher_registry.py tests/test_pipeline.py
ruff_files src/lunar_reg/match/__init__.py src/lunar_reg/match/superglue.py src/lunar_reg/match/learned.py src/lunar_reg/pipeline.py tests/test_matcher_registry.py
ok P1.14
