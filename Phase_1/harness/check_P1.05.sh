#!/usr/bin/env bash
# check_P1.05 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_geometry_grid_fixes.py
harness_pytest Phase_1/harness/tests/test_P1_05.py
repo_pytest tests/test_geometry_grid.py tests/test_geometry_grid_fixes.py
ruff_files src/lunar_reg/ingest/geometry_grid.py tests/test_geometry_grid.py tests/test_geometry_grid_fixes.py
ok P1.05
