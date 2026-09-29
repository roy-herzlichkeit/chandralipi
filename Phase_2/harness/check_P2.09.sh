#!/usr/bin/env bash
# check_P2.09 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
require_file tests/test_warp_georef.py
harness_pytest Phase_2/harness/tests/test_P2_09.py
repo_pytest tests/test_warp_georef.py tests/test_registered_export.py
ruff_files src/lunar_reg/align/warp.py tests/test_warp_georef.py
ok P2.09
