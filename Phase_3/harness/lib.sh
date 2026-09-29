#!/usr/bin/env bash
# Shared helpers for Phase_<i>/harness/check_*.sh and verify.sh. Sourced, never executed.
# Protected file (DECISIONS G05): implementers must not edit anything under harness/ or benchmark/.
set -euo pipefail
_HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_DIR="$(cd "$_HARNESS_DIR/.." && pwd)"
REPO="$(git -C "$PHASE_DIR" rev-parse --show-toplevel)"
cd "$REPO"
PHASE_REL="${PHASE_DIR#"$REPO"/}"
PY="$REPO/.venv/bin/python"
RUFF="$REPO/.venv/bin/ruff"
export PYTHONDONTWRITEBYTECODE=1

fail() { echo "CHECK FAIL: $*" >&2; exit 1; }
ok() { echo "CHECK OK: $*"; }

# G05: every harness/benchmark file must match the manifest written by the architect.
manifest_check() {
  (cd "$PHASE_DIR" && sha256sum --quiet --strict -c harness/MANIFEST.sha256) \
    || fail "harness/benchmark files differ from $PHASE_REL/harness/MANIFEST.sha256 (G05). Restore with: git checkout -- $PHASE_REL/harness $PHASE_REL/benchmark"
}

# pytest with the project's markers but without repo addopts noise; -p no:cacheprovider keeps the tree clean.
_pytest() {
  timeout 600 "$PY" -m pytest -o addopts="" --strict-markers -ra -q -p no:cacheprovider "$@"
}
harness_pytest() { _pytest "$@" || fail "pytest $*"; }
repo_pytest() { _pytest "$@" || fail "pytest $*"; }

ruff_files() {
  local existing=()
  for f in "$@"; do [ -e "$f" ] && existing+=("$f"); done
  [ ${#existing[@]} -eq 0 ] && return 0
  "$RUFF" check "${existing[@]}" || fail "ruff check ${existing[*]}"
}
require_file() { [ -e "$1" ] || fail "missing $1"; }
require_absent() { [ ! -e "$1" ] || fail "must not exist: $1"; }
require_branch() {
  local b; b="$(git rev-parse --abbrev-ref HEAD)"
  [ "$b" = "$1" ] || fail "on branch '$b', expected '$1'"
}
require_tag() { [ -n "$(git tag -l "$1")" ] || fail "tag $1 does not exist"; }
require_grep() { grep -qE -- "$1" "$2" || fail "$2 does not contain /$1/"; }
forbid_grep() { if grep -qE -- "$1" "$2"; then fail "$2 still contains /$1/"; fi; }
gpu_available() { "$PY" -c "import sys, torch; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; }
# Files changed on this branch since the phase base (for ruff on touched files).
changed_py_since() { git diff --name-only --diff-filter=AM "$1"..HEAD -- '*.py' 2>/dev/null || true; }
