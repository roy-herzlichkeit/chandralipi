#!/usr/bin/env bash
# Launch the Streamlit results browser. Assumes ./scripts/setup.sh has been run.
# Extra args pass straight through to streamlit, e.g.:
#     ./scripts/run_dashboard.sh --server.port 8600 --server.headless true
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

STREAMLIT=.venv/bin/streamlit
[ -x "$STREAMLIT" ] || STREAMLIT=.venv/Scripts/streamlit.exe   # Git Bash on Windows
if [ ! -x "$STREAMLIT" ]; then
  printf '\033[31merror:\033[0m no streamlit in .venv — run ./scripts/setup.sh first.\n' >&2
  exit 1
fi

if [ ! -f data/processed/results/index.parquet ]; then
  printf '\033[33mwarning:\033[0m data/processed/results/index.parquet is missing.\n'
  printf '          The dashboard will open but show no pairs. Populate it with:\n'
  printf '            ./scripts/setup.sh --data <bundle>        (copy from another machine)\n'
  printf '            .venv/bin/python scripts/run_vikram.py           (regenerate locally)\n\n'
fi

exec "$STREAMLIT" run dashboard/app.py "$@"
