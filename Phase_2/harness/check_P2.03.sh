#!/usr/bin/env bash
# check_P2.03 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
require_file tests/test_benchmark_cli.py
harness_pytest Phase_2/harness/tests/test_P2_03.py
repo_pytest tests/test_benchmark_cli.py
ruff_files src/lunar_reg/cli.py src/lunar_reg/match/benchmark.py src/lunar_reg/match/memory.py tests/test_benchmark_cli.py
ok P2.03
