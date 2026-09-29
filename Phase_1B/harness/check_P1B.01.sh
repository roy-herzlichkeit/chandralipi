#!/usr/bin/env bash
# check_P1B.01 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1B
require_file tests/test_render.py
harness_pytest Phase_1B/harness/tests/test_contracts_P1B.py -k render
harness_pytest Phase_1B/harness/tests/test_P1B_01.py
repo_pytest tests/test_render.py tests/test_scenes_and_budget.py
ruff_files src/lunar_reg/eval/render.py src/lunar_reg/eval/scenes.py tests/test_render.py
ok P1B.01
