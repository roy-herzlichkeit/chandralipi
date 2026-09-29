#!/usr/bin/env bash
# check_P0.06 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_file tests/test_catalogue_footprints.py
harness_pytest Phase_0/harness/tests/test_P0_06.py
repo_pytest tests/test_catalogue_footprints.py tests/test_overlap.py
ruff_files scripts/fetch_catalogue.py src/lunar_reg/ingest/overlap.py tests/test_catalogue_footprints.py
ok P0.06
