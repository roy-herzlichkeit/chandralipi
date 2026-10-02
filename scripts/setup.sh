#!/usr/bin/env bash
# One-shot bootstrap for a fresh machine: virtualenv -> dependencies -> data ->
# verification. Safe to re-run; it only does the missing work unless --force.
#
#   ./scripts/setup.sh                         # venv + deps only
#   ./scripts/setup.sh --data ../ch2-data.tar.zst   # + unpack a data bundle
#   ./scripts/setup.sh --data /media/usb/sih/data   # + copy a data directory
#   ./scripts/setup.sh --cuda --data ... --run      # CUDA torch, then launch dashboard
#
# Produce the bundle on the machine that has the data with scripts/pack_data.sh.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

PYTHON=${PYTHON:-python3}
EXTRAS="dev,dashboard"
DATA_SRC=""
WANT_CUDA=0
FORCE=0
RUN_AFTER=0

die()  { printf '\n\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --data)    DATA_SRC=${2:-}; shift 2 ;;
    --extras)  EXTRAS=${2:-}; shift 2 ;;
    --python)  PYTHON=${2:-}; shift 2 ;;
    --cuda)    WANT_CUDA=1; shift ;;
    --force)   FORCE=1; shift ;;
    --run)     RUN_AFTER=1; shift ;;
    -h|--help)
      sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

# --- 1. Python -------------------------------------------------------------
command -v "$PYTHON" >/dev/null 2>&1 || die "'$PYTHON' not found; pass --python <path> or install Python >=3.10"
"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' \
  || die "$("$PYTHON" -V) is too old; this project needs Python >=3.10"
info "using $("$PYTHON" -V) at $(command -v "$PYTHON")"

# --- 2. virtualenv ------------------------------------------------------------
if [ "$FORCE" -eq 1 ] && [ -d .venv ]; then
  info "removing existing .venv (--force)"
  rm -rf .venv
fi
if [ ! -d .venv ]; then
  info "creating .venv"
  "$PYTHON" -m venv .venv \
    || die "venv creation failed; on Debian/Ubuntu: sudo apt install python3-venv"
else
  info ".venv already exists; reusing it (pass --force to rebuild)"
fi

VPY=.venv/bin/python
[ -x "$VPY" ] || VPY=.venv/Scripts/python.exe   # Git Bash on Windows
[ -x "$VPY" ] || die "no python inside .venv — delete .venv and re-run with --force"

info "upgrading pip / wheel"
"$VPY" -m pip install --quiet --upgrade pip wheel

# --- 3. dependencies -------------------------------------------------------
if [ "$WANT_CUDA" -eq 1 ]; then
  info "installing CUDA torch (cu124) before the rest"
  "$VPY" -m pip install torch --index-url https://download.pytorch.org/whl/cu124
fi

info "installing lunar-reg with extras: [$EXTRAS]"
"$VPY" -m pip install -e ".[$EXTRAS]"

# --- 4. data --------------------------------------------------------------
if [ -n "$DATA_SRC" ]; then
  [ -e "$DATA_SRC" ] || die "--data path does not exist: $DATA_SRC"
  if [ -d "$DATA_SRC" ]; then
    # A directory whose contents go inside data/ (point --data at a `data` dir,
    # or at a `processed`/`results` subtree — rsync merges it in either way).
    info "copying $DATA_SRC/ -> data/"
    mkdir -p data
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --ignore-existing --info=progress2 "$DATA_SRC"/ data/
    else
      cp -an "$DATA_SRC"/. data/
    fi
  else
    # An archive produced by pack_data.sh; it stores paths as data/...
    info "unpacking data bundle $DATA_SRC"
    "$VPY" scripts/untar_data.py "$DATA_SRC" --dest . || die "data bundle refused or failed: $DATA_SRC"
  fi

  # Rebuild the results index from the .npz files on disk rather than trusting
  # an unpacked index.parquet.
  if [ -d data/processed/results/pairs ]; then
    info "reindexing data/processed/results"
    "$VPY" scripts/reindex_results.py
  fi

  if [ -f data/processed/results/index.parquet ]; then
    n=$("$VPY" - <<'PY'
from pathlib import Path
try:
    import pyarrow.parquet as pq
    print(pq.read_table("data/processed/results/index.parquet").num_rows)
except Exception:
    print("?")
PY
)
    info "data in place: data/processed/results/index.parquet ($n rows)"
  else
    printf '\033[33mwarning:\033[0m data copied but data/processed/results/index.parquet is missing — the dashboard will start empty.\n'
  fi
else
  info "no --data given; skipping the data copy"
  [ -f data/processed/results/index.parquet ] \
    || printf '\033[33mnote:\033[0m data/processed/results is empty. Copy a bundle with --data <bundle>, or run:  .venv/bin/python scripts/run_vikram.py\n'
fi

# --- 5. verify ----------------------------------------------------------------
info "verifying the install"
"$VPY" - <<'PY'
import importlib.util
mods = ["numpy", "cv2", "torch", "kornia", "rasterio", "pandas", "pyarrow", "streamlit", "lunar_reg"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    raise SystemExit("missing modules: " + ", ".join(missing))
import torch
print(f"  torch {torch.__version__}  cuda={torch.cuda.is_available()}")
import cv2
print(f"  opencv {cv2.__version__}")
PY
.venv/bin/lunar-reg env || true

cat <<EOF

$(printf '\033[32m✓ setup complete\033[0m')

  run the dashboard:   ./scripts/run_dashboard.sh
  activate the venv:   source .venv/bin/activate
  re-run the pipeline: .venv/bin/python scripts/run_vikram.py

EOF

if [ "$RUN_AFTER" -eq 1 ]; then
  exec "$SCRIPT_DIR/run_dashboard.sh"
fi
