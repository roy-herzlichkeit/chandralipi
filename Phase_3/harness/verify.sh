#!/usr/bin/env bash
# verify.sh — full Phase 3 suite (≤ 20 min, G18). Protected (G05).
source "$(dirname "$0")/lib.sh"
BASE="phase-1B-approved"
OUT="$PHASE_DIR/benchmark/out"
mkdir -p "$OUT"

manifest_check
require_tag "$BASE"
if ! git diff --quiet "$BASE"..HEAD -- "$PHASE_REL/harness" "$PHASE_REL/benchmark/RUBRIC.md" \
     "$PHASE_REL/benchmark/run.sh" "$PHASE_REL/benchmark/score.py"; then
  fail "harness/benchmark changed since $BASE (G05)"
fi

echo "== CPU suite (scripts/ci.sh)"
PYTHON="$PY" bash scripts/ci.sh --junitxml="$OUT/ci_junit.xml" -p no:cacheprovider || fail "scripts/ci.sh"

echo "== resource-marked repo tests (gpu / weights / data)"
_pytest tests -m "gpu or weights or data" --junitxml="$OUT/marked_junit.xml" || fail "marked repo tests"

echo "== Phase 0/1/2 contracts (consumed)"
_pytest Phase_0/harness/tests/test_contracts_P0.py Phase_1/harness/tests/test_contracts_P1.py Phase_2/harness/tests/test_contracts_P2.py || fail "consumed contracts regressed"

echo "== Phase 3 harness"
_pytest Phase_3/harness/tests --junitxml="$OUT/harness_junit.xml" || fail "Phase 3 harness"

echo "== downloads manifest"
if [ -f data/raw/DOWNLOADS.json ]; then
  "$PY" scripts/verify_downloads.py --no-hash || fail "verify_downloads"
fi

echo "== ruff on files changed since $BASE"
mapfile -t changed < <(changed_py_since "$BASE")
ruff_files "${changed[@]}"

ok "Phase 3 verify"
