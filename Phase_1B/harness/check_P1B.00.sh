#!/usr/bin/env bash
# check_P1B.00 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-1B
require_tag phase-2-approved
git merge-base --is-ancestor phase-2-approved HEAD || fail "phase-2-approved is not an ancestor of HEAD"
harness_pytest Phase_1/harness/tests/test_contracts_P1.py -k C20
if [ -f Phase_1B/SKIPPED.md ]; then
  "$PY" -c "import json,sys; d=json.load(open(\"data/processed/vikram/exp1_gate.json\")); sys.exit(0 if d[\"decision\"]==\"SKIP_1B\" else 1)" || fail "SKIPPED.md present but the gate says BUILD_1B"
  require_grep "DECISIONS G02" Phase_1B/SKIPPED.md
else
  "$PY" -c "import json,sys; d=json.load(open(\"data/processed/vikram/exp1_gate.json\")); sys.exit(0 if d[\"decision\"]==\"BUILD_1B\" else 1)" || fail "gate says SKIP_1B but Phase_1B/SKIPPED.md is missing"
fi
ok P1B.00
