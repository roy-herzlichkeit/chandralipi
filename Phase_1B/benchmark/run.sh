#!/usr/bin/env bash
# benchmark/run.sh — Phase 1B score (≤ 45 min, G18). Writes Phase_1B/benchmark/score.json. Protected (G05).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(git -C "$HERE" rev-parse --show-toplevel)"
cd "$REPO"
(cd "$HERE/.." && sha256sum --quiet --strict -c harness/MANIFEST.sha256) \
  || { echo "benchmark: MANIFEST.sha256 mismatch (G05)"; exit 1; }
mkdir -p "$HERE/out"
exec "$REPO/.venv/bin/python" "$HERE/score.py" --out "$HERE/score.json" --work "$HERE/out"
