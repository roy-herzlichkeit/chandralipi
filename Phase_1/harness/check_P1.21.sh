#!/usr/bin/env bash
# check_P1.21 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_viewers.py
harness_pytest Phase_1/harness/tests/test_P1_21.py
repo_pytest tests/test_viewers.py
ruff_files scripts/export_web_data.py dashboard/app.py src/lunar_reg/viz/figures.py scripts/reindex_results.py scripts/demo.py tests/test_viewers.py
ok P1.21
