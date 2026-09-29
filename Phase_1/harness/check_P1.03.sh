#!/usr/bin/env bash
# check_P1.03 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_catalog.py
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k C09
harness_pytest Phase_1/harness/tests/test_P1_03.py
repo_pytest tests/test_catalog.py tests/test_ingest_labels.py
ruff_files src/lunar_reg/ingest/catalog.py src/lunar_reg/ingest/manifest.py src/lunar_reg/ingest/lro.py src/lunar_reg/cli.py tests/test_catalog.py
ok P1.03
