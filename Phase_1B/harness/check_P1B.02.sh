#!/usr/bin/env bash
# check_P1B.02 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1B
require_file tests/test_rendered_reference.py
harness_pytest Phase_1B/harness/tests/test_P1B_02.py
repo_pytest tests/test_rendered_reference.py tests/test_pairs.py
ruff_files src/lunar_reg/pairs.py tests/test_rendered_reference.py
ok P1B.02
