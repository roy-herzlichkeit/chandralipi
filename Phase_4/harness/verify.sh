#!/usr/bin/env bash
# verify.sh — full Phase 4 suite (≤ 20 min, G18). Protected (G05).
source "$(dirname "$0")/lib.sh"
BASE="phase-3-approved"
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

echo "== resource-marked repo tests"
_pytest tests -m "gpu or weights or data" --junitxml="$OUT/marked_junit.xml" || fail "marked repo tests"

echo "== consumed contracts"
_pytest Phase_0/harness/tests/test_contracts_P0.py Phase_1/harness/tests/test_contracts_P1.py \
  Phase_2/harness/tests/test_contracts_P2.py Phase_3/harness/tests/test_contracts_P3.py \
  || fail "consumed contracts regressed"

echo "== Phase 4 harness (fakeredis)"
_pytest Phase_4/harness/tests --junitxml="$OUT/harness_junit.xml" || fail "Phase 4 harness"

echo "== real redis-server on localhost (G25; skipped with reason when not installed)"
if command -v redis-server >/dev/null 2>&1; then
  PORT=6399
  redis-server --port "$PORT" --save "" --appendonly no --daemonize yes >/dev/null
  trap 'redis-cli -p '"$PORT"' shutdown nosave >/dev/null 2>&1 || true' EXIT
  sleep 1
  REDIS_URL="redis://127.0.0.1:$PORT/0" _pytest tests/test_redis_queue.py -k real_server \
    || fail "real redis-server tests"
else
  echo "SKIP: redis-server not installed (sudo apt install redis-server) — real-server tests not run"
fi

echo "== ruff on files changed since $BASE"
mapfile -t changed < <(changed_py_since "$BASE")
ruff_files "${changed[@]}"
ok "Phase 4 verify"
