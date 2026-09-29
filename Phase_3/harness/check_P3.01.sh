#!/usr/bin/env bash
# check_P3.01 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-3
require_file tests/test_job.py
harness_pytest Phase_3/harness/tests/test_contracts_P3.py -k C22
harness_pytest Phase_3/harness/tests/test_P3_01.py
repo_pytest tests/test_job.py
ruff_files src/lunar_reg/distributed/__init__.py src/lunar_reg/distributed/job.py tests/test_job.py
ok P3.01
