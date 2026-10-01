#!/usr/bin/env bash
# check_P1.15 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_tmc2_iirs.py
harness_pytest Phase_1/harness/tests/test_P1_15.py
repo_pytest tests/test_tmc2_iirs.py tests/test_ingest_labels.py
ruff_files scripts/probe_raster.py src/lunar_reg/ingest/pds4.py src/lunar_reg/ingest/fieldmap.py src/lunar_reg/preprocess/hyperspectral.py src/lunar_reg/preprocess/pipeline.py tests/test_tmc2_iirs.py
ok P1.15
