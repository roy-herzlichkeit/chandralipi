"""Rebuild ``data/processed/results/index.parquet`` from the ``.npz`` files on disk.

Why this exists
---------------
``scripts/build_demo_results.py`` calls ``save_results()``. That now reindexes
from every pair on disk, but an index written by an *older* build (or hand-edited)
can still be missing pairs whose ``.npz`` are present. This script is the
recovery: it ignores the stale index, reads every ``pairs/*.npz`` back, and
writes a fresh index covering all of them. It never deletes a result
(``--exclude-synthetic`` *moves* the synthetic ones aside).

    python scripts/reindex_results.py                     # index every .npz found
    python scripts/reindex_results.py --exclude-synthetic # move synthetic aside, index the rest
    python scripts/reindex_results.py --dry-run           # report only, write nothing
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lunar_reg.results import load_all_pairs, write_index  # noqa: E402

DEFAULT_ROOT = Path("data/processed/results")
DEFAULT_STASH = Path("data/processed/results_ch2_synthetic_backup/pairs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--exclude-synthetic", action="store_true",
        help="move synthetic pairs to --stash-dir and index only the rest",
    )
    parser.add_argument("--stash-dir", type=Path, default=DEFAULT_STASH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pairs_dir = args.root / "pairs"
    if not any(pairs_dir.glob("*.npz")):
        print(f"no .npz files under {pairs_dir}", file=sys.stderr)
        return 1

    loaded, failed = load_all_pairs(args.root)
    real = [r.pair_id for r in loaded if not r.synthetic]
    synthetic = [r.pair_id for r in loaded if r.synthetic]

    # --- report every outcome, not just the happy path ----------------------
    print(f"scanned {len(loaded) + len(failed)} .npz file(s) under {pairs_dir}")
    print(f"  real (from a sensor product): {len(real)}")
    print(f"  synthetic (generated scene):  {len(synthetic)}")
    print(f"  failed to load:               {len(failed)}")
    for pair_id, why in failed:
        print(f"    ! {pair_id}: {why}")
    if not loaded:
        print("every file failed to load -- aborting, index not touched", file=sys.stderr)
        return 1

    keep = loaded
    if args.exclude_synthetic and synthetic:
        keep = [r for r in loaded if not r.synthetic]
        if not args.dry_run:
            args.stash_dir.mkdir(parents=True, exist_ok=True)
            for pair_id in synthetic:
                shutil.move(str(pairs_dir / f"{pair_id}.npz"),
                            str(args.stash_dir / f"{pair_id}.npz"))
        print(f"  {'would move' if args.dry_run else 'moved'} {len(synthetic)} synthetic "
              f"pair(s) -> {args.stash_dir}")

    if args.dry_run:
        print(f"\ndry run: would write {len(keep)} row(s) to {args.root / 'index.parquet'}")
        return 0

    frame = write_index(keep, args.root)
    print(f"\nwrote {len(frame)} row(s) to {args.root / 'index.parquet'}")
    if len(frame):
        cols = [c for c in ("pair_id", "source_sensor", "reference_sensor", "matcher", "synthetic")
                if c in frame.columns]
        print(frame[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
