#!/usr/bin/env bash
# check_P4.04 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-4
require_file tests/test_hosts_config.py
bash -n scripts/cluster_up.sh || fail cluster_up.sh
harness_pytest Phase_4/harness/tests/test_contracts_P4.py -k hosts
harness_pytest Phase_4/harness/tests/test_P4_04.py
repo_pytest tests/test_hosts_config.py
ruff_files src/lunar_reg/cli.py tests/test_hosts_config.py
ok P4.04
