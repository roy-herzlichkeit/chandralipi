#!/usr/bin/env bash
# check_P1.02 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_fetch_public.py
harness_pytest Phase_1/harness/tests/test_P1_02.py
repo_pytest tests/test_fetch_public.py
ruff_files scripts/fetch_public.py tests/test_fetch_public.py
ok P1.02
