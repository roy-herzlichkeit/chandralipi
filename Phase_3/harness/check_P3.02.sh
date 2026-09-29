#!/usr/bin/env bash
# check_P3.02 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-3
require_file tests/test_job_outcome.py
harness_pytest Phase_3/harness/tests/test_contracts_P3.py -k C23
harness_pytest Phase_3/harness/tests/test_P3_02.py
repo_pytest tests/test_job_outcome.py
ruff_files src/lunar_reg/distributed/outcome.py tests/test_job_outcome.py
ok P3.02
