#!/usr/bin/env bash
# verify.sh — full Phase 0 suite (≤ 20 min, G18). Protected (G05).
# Writes junit XML under Phase_0/benchmark/out/ for benchmark/score.py.
source "$(dirname "$0")/lib.sh"
BASE="phase-base-approved"
OUT="$PHASE_DIR/benchmark/out"
mkdir -p "$OUT"

manifest_check
require_tag "$BASE"
if ! git diff --quiet "$BASE"..HEAD -- "$PHASE_REL/harness" "$PHASE_REL/benchmark/RUBRIC.md" \
     "$PHASE_REL/benchmark/run.sh" "$PHASE_REL/benchmark/score.py"; then
  fail "harness/benchmark changed since $BASE (G05)"
fi

echo "== CPU suite (scripts/ci.sh)"
PYTHON="$PY" bash scripts/ci.sh --junitxml="$OUT/ci_junit.xml" -p no:cacheprovider \
  || fail "scripts/ci.sh"

echo "== resource-marked repo tests (gpu / weights / data; skip with reason when absent)"
_pytest tests -m "gpu or weights or data" --junitxml="$OUT/marked_junit.xml" \
  || fail "marked repo tests"

echo "== Phase 0 harness"
_pytest Phase_0/harness/tests --junitxml="$OUT/harness_junit.xml" || fail "Phase 0 harness"

echo "== ruff on files changed since $BASE"
mapfile -t changed < <(changed_py_since "$BASE")
ruff_files "${changed[@]}"

ok "Phase 0 verify"
