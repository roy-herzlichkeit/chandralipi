#!/usr/bin/env bash
# check_P0.02 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_absent src/lunar_reg/match/loftr.py
require_file tests/test_learned_matchers.py
harness_pytest Phase_0/harness/tests/test_P0_02.py
repo_pytest tests/test_learned_matchers.py -m "not gpu"
ruff_files src/lunar_reg/match/learned.py src/lunar_reg/match/superglue.py src/lunar_reg/match/__init__.py src/lunar_reg/match/classical.py src/lunar_reg/match/stitch.py tests/test_learned_matchers.py
ok P0.02
