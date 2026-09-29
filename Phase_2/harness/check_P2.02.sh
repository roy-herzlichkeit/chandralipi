#!/usr/bin/env bash
# check_P2.02 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-2
require_file tests/test_device_profiles.py
harness_pytest Phase_2/harness/tests/test_contracts_P2.py -k C16
harness_pytest Phase_2/harness/tests/test_P2_02.py
repo_pytest tests/test_device_profiles.py tests/test_device.py
ruff_files src/lunar_reg/device.py tests/test_device_profiles.py
ok P2.02
