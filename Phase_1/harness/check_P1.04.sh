#!/usr/bin/env bash
# check_P1.04 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_lro_georeference.py
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k C10
harness_pytest Phase_1/harness/tests/test_P1_04.py
repo_pytest tests/test_lro_georeference.py
ruff_files src/lunar_reg/ingest/lro.py tests/test_lro_georeference.py
ok P1.04
