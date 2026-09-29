#!/usr/bin/env bash
# check_P0.01 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
bash -n scripts/ci.sh || fail "scripts/ci.sh syntax"
bash -n scripts/setup.sh || fail "scripts/setup.sh syntax"
require_file tests/test_untar_data.py
harness_pytest Phase_0/harness/tests/test_P0_01.py
repo_pytest tests/test_untar_data.py
ruff_files scripts/untar_data.py tests/test_untar_data.py
ok P0.01
