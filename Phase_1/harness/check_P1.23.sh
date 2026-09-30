#!/usr/bin/env bash
# check_P1.23 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
harness_pytest Phase_1/harness/tests/test_P1_23.py
repo_pytest tests/test_ingest_labels.py tests/test_preprocess_pipeline.py
ruff_files src/lunar_reg/ingest/__init__.py src/lunar_reg/ingest/fieldmap.py src/lunar_reg/ingest/manifest.py src/lunar_reg/preprocess/config.py
ok P1.23
