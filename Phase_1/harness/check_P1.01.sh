#!/usr/bin/env bash
# check_P1.01 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_downloads.py
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k C08
harness_pytest Phase_1/harness/tests/test_P1_01.py
repo_pytest tests/test_downloads.py
ruff_files src/lunar_reg/ingest/downloads.py scripts/verify_downloads.py tests/test_downloads.py
ok P1.01
