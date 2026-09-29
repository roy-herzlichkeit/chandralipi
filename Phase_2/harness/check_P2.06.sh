#!/usr/bin/env bash
# check_P2.06 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
require_file tests/test_tiled_prior.py
harness_pytest Phase_2/harness/tests/test_contracts_P2.py -k C18
harness_pytest Phase_2/harness/tests/test_P2_06.py
repo_pytest tests/test_tiled_prior.py tests/test_tiling.py
ruff_files src/lunar_reg/match/tiled.py src/lunar_reg/match/stitch.py src/lunar_reg/match/learned.py tests/test_tiled_prior.py
ok P2.06
