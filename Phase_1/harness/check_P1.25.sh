#!/usr/bin/env bash
# check_P1.25 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_classical_cap.py
harness_pytest Phase_1/harness/tests/test_P1_25.py
repo_pytest tests/test_classical_cap.py tests/test_matcher_registry.py tests/test_matchers_and_refinement.py
ruff_files src/lunar_reg/match/classical.py tests/test_classical_cap.py
ok P1.25
