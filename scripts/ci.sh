#!/usr/bin/env bash
# CI entry point (DECISIONS G21): lint + CPU test suite. Extra args go to pytest.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
"$PY" -m ruff check src tests scripts dashboard
"$PY" -m pytest -m "not gpu and not data and not weights" "$@"
