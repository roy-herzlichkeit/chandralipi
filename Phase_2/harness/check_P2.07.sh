#!/usr/bin/env bash
# check_P2.07 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
require_file tests/test_caps_and_memory.py
harness_pytest Phase_2/harness/tests/test_P2_07.py
repo_pytest tests/test_caps_and_memory.py tests/test_rift2.py
ruff_files src/lunar_reg/match/classical.py src/lunar_reg/match/rift2/matcher.py src/lunar_reg/preprocess/radiometric.py tests/test_caps_and_memory.py
ok P2.07
