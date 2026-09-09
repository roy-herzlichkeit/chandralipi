#!/usr/bin/env bash
# Bundle the data/ tree into a single archive to carry to another machine.
# Everything under data/ is git-ignored (large, ISSDC redistribution terms), so
# this is how it travels. Unpack it on the far side with:
#     ./scripts/setup.sh --data <archive>
#
#   ./scripts/pack_data.sh                 # data/processed, real pairs only (~30 MB) — dashboard + real figures
#   ./scripts/pack_data.sh --full          # + data/raw reference imagery (~300 MB) — lets you re-run the pipeline
#   ./scripts/pack_data.sh --results-only  # just data/processed/results (~20 MB) — smallest set the dashboard needs
#   ./scripts/pack_data.sh --with-synthetic  # also include the generated-scene store (normally excluded)
#   ./scripts/pack_data.sh --out /tmp/x.tar.zst
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

die()  { printf '\n\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*"; }

MODE="processed"
OUT=""
WITH_SYNTHETIC=0
while [ $# -gt 0 ]; do
  case "$1" in
    --full)           MODE="full"; shift ;;
    --results-only)   MODE="results"; shift ;;
    --with-synthetic) WITH_SYNTHETIC=1; shift ;;
    --out)            OUT=${2:-}; shift 2 ;;
    -h|--help)        sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

case "$MODE" in
  full)     PATHS=(data) ;;
  processed) PATHS=(data/processed) ;;
  results)  PATHS=(data/processed/results) ;;
esac
for p in "${PATHS[@]}"; do
  [ -e "$p" ] || die "$p does not exist — nothing to pack"
done

# The synthetic scene store and its figures never travel: the showcase is the
# real JAXA/NASA pairs only. --with-synthetic overrides for a full archive.
SYNTH_EXCLUDES=()
if [ "$WITH_SYNTHETIC" -eq 0 ]; then
  SYNTH_EXCLUDES=(--exclude='data/processed/results_ch2_synthetic*'
                  --exclude='data/processed/demo')
fi

# zstd if we have it (smaller, faster), gzip otherwise.
if command -v zstd >/dev/null 2>&1; then
  EXT="tar.zst"; TAR_COMP=(--zstd)
else
  EXT="tar.gz";  TAR_COMP=(-z)
fi
[ -n "$OUT" ] || OUT="dist/chandralipi-data-${MODE}-$(date +%Y%m%d).${EXT}"
mkdir -p "$(dirname "$OUT")"

info "packing: ${PATHS[*]}  (mode: $MODE)"
du -sh "${PATHS[@]}" 2>/dev/null || true

# --exclude keeps Python caches and OS cruft out of the bundle.
tar "${TAR_COMP[@]}" \
    --exclude='__pycache__' --exclude='.DS_Store' \
    ${SYNTH_EXCLUDES[@]+"${SYNTH_EXCLUDES[@]}"} \
    -cf "$OUT" "${PATHS[@]}"

info "wrote $OUT ($(du -h "$OUT" | cut -f1))"
cat <<EOF

  copy it to the other machine, then there:
      git clone <this repo> && cd <repo>
      ./scripts/setup.sh --data /path/to/$(basename "$OUT")

EOF
