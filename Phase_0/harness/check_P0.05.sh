#!/usr/bin/env bash
# check_P0.05 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_file tests/test_pds4_resolver.py
harness_pytest Phase_0/harness/tests/test_P0_05.py
repo_pytest tests/test_ingest_labels.py tests/test_pds4_resolver.py
ruff_files src/lunar_reg/ingest/pds4.py src/lunar_reg/ingest/fieldmap.py src/lunar_reg/ingest/lro.py src/lunar_reg/ingest/manifest.py tests/test_pds4_resolver.py
ok P0.05
