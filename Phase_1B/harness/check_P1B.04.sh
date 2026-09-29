#!/usr/bin/env bash
# check_P1B.04 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1B
require_file tests/test_rift2_fixes.py
harness_pytest Phase_1B/harness/tests/test_P1B_04.py
repo_pytest tests/test_rift2.py tests/test_rift2_fixes.py
ruff_files src/lunar_reg/match/rift2/mim.py src/lunar_reg/match/rift2/descriptor.py src/lunar_reg/match/rift2/matcher.py tests/test_rift2_fixes.py
ok P1B.04
