#!/usr/bin/env bash
# check_P1.17 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1
require_file tests/test_cli_and_jaxa.py
harness_pytest Phase_1/harness/tests/test_P1_17.py
repo_pytest tests/test_cli_and_jaxa.py
ruff_files scripts/run_jaxa.py scripts/run_ablation.py src/lunar_reg/cli.py tests/test_cli_and_jaxa.py
ok P1.17
