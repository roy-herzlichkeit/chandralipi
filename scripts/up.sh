#!/usr/bin/env bash
# Everything in one command: (optional) venv + deps + data, then a fresh static
# export, then BOTH front ends running side by side until you Ctrl-C:
#   - the Streamlit dashboard  (dashboard/app.py, the live tool)
#   - the React showcase site  (web/, reads the static export)
#
#   ./scripts/up.sh                     # servers only (assumes ./scripts/setup.sh already ran)
#   ./scripts/up.sh --setup             # run setup.sh first (venv + deps)
#   ./scripts/up.sh --setup --data X    # ... and unpack/copy a data bundle (see pack_data.sh)
#   ./scripts/up.sh --build             # React: production build + preview instead of the dev server
#   ./scripts/up.sh --no-web            # Streamlit only
#   ./scripts/up.sh --host              # bind both to 0.0.0.0 for other devices on the LAN
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

die()  { printf '\n\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*"; }

RUN_SETUP=0
WANT_WEB=1
WEB_MODE="dev"            # dev | build
BIND_HOST=0
STREAMLIT_PORT=8501
WEB_PORT=5173
SETUP_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --setup)          RUN_SETUP=1; shift ;;
    --data)           SETUP_ARGS+=(--data "${2:?--data needs a path}"); RUN_SETUP=1; shift 2 ;;
    --cuda)           SETUP_ARGS+=(--cuda); RUN_SETUP=1; shift ;;
    --force)          SETUP_ARGS+=(--force); RUN_SETUP=1; shift ;;
    --build)          WEB_MODE="build"; shift ;;
    --no-web)         WANT_WEB=0; shift ;;
    --host)           BIND_HOST=1; shift ;;
    --streamlit-port) STREAMLIT_PORT=${2:?}; shift 2 ;;
    --web-port)       WEB_PORT=${2:?}; shift 2 ;;
    -h|--help)        sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

# --- 1. venv + deps (+ data) -------------------------------------------------
if [ "$RUN_SETUP" -eq 1 ]; then
  info "running scripts/setup.sh ${SETUP_ARGS[*]:-}"
  "$SCRIPT_DIR/setup.sh" ${SETUP_ARGS[@]+"${SETUP_ARGS[@]}"}
fi

VPY=.venv/bin/python
STREAMLIT=.venv/bin/streamlit
[ -x "$VPY" ] || VPY=.venv/Scripts/python.exe
[ -x "$STREAMLIT" ] || STREAMLIT=.venv/Scripts/streamlit.exe
[ -x "$VPY" ]       || die "no .venv — run: ./scripts/up.sh --setup"
[ -x "$STREAMLIT" ] || die "streamlit missing from .venv — run: ./scripts/setup.sh --force"

# --- 2. React deps + static export ----------------------------------------
if [ "$WANT_WEB" -eq 1 ]; then
  command -v npm >/dev/null 2>&1 || die "Node/npm not found — install Node >=18, or pass --no-web"
  if [ ! -d web/node_modules ]; then
    info "installing web/ dependencies (first run)"
    ( cd web && { npm ci || npm install; } )
  fi
  VITE="$REPO_ROOT/web/node_modules/.bin/vite"
  [ -x "$VITE" ] || die "vite not found under web/node_modules — 'cd web && npm install' failed?"
fi

# The React /dashboard reads a static snapshot, not the live store — refresh it
# every launch so the two front ends agree.
if [ -f data/processed/results/index.parquet ]; then
  info "exporting results -> web/public/data/"
  "$VPY" scripts/export_web_data.py
else
  warn "data/processed/results is empty — dashboards will start with no pairs."
  warn "populate it with:  ./scripts/setup.sh --data <bundle>   or   $VPY scripts/run_vikram.py"
fi

# --- 3. launch both, tear both down together -------------------------------
# Job control on, so each `&` server leads its own process group and can be
# torn down as a group -- streamlit and vite both spawn children that a plain
# kill on the parent PID leaves running.
set -m
PIDS=()
cleanup() {
  trap - INT TERM EXIT
  for p in ${PIDS[@]+"${PIDS[@]}"}; do kill -INT -"$p" 2>/dev/null || true; done
  for _ in 1 2 3 4 5 6 7 8; do
    still=0
    for p in ${PIDS[@]+"${PIDS[@]}"}; do kill -0 "$p" 2>/dev/null && still=1; done
    [ "$still" -eq 0 ] && break
    sleep 0.5
  done
  for p in ${PIDS[@]+"${PIDS[@]}"}; do kill -KILL -"$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
  printf '\n\033[36m==>\033[0m stopped.\n'
}
trap cleanup INT TERM EXIT

SL_ARGS=(run dashboard/app.py --server.port "$STREAMLIT_PORT")
[ "$BIND_HOST" -eq 1 ] && SL_ARGS+=(--server.address 0.0.0.0 --server.headless true)
"$STREAMLIT" "${SL_ARGS[@]}" &
PIDS+=($!)
info "Streamlit dashboard  ->  http://localhost:$STREAMLIT_PORT"

if [ "$WANT_WEB" -eq 1 ]; then
  HOST_ARGS=()
  [ "$BIND_HOST" -eq 1 ] && HOST_ARGS=(--host)
  if [ "$WEB_MODE" = "build" ]; then
    info "building the React bundle (web/dist/)"
    ( cd web && "$VITE" build )
    ( cd web && exec "$VITE" preview --port "$WEB_PORT" --strictPort ${HOST_ARGS[@]+"${HOST_ARGS[@]}"} ) &
    PIDS+=($!)
    info "React showcase (preview)  ->  http://localhost:$WEB_PORT"
  else
    ( cd web && exec "$VITE" --port "$WEB_PORT" --strictPort ${HOST_ARGS[@]+"${HOST_ARGS[@]}"} ) &
    PIDS+=($!)
    info "React showcase (dev)  ->  http://localhost:$WEB_PORT"
  fi
fi

printf '\033[36m==>\033[0m both running — Ctrl-C to stop everything.\n\n'
wait
