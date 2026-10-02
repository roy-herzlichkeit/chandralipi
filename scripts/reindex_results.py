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
    python scripts/reindex_results.py --force             # write even if unreadable files
                                                          # would shrink the index

When some ``.npz`` fail to load and the rebuilt index would have fewer rows
than the current one, the current index is KEPT and the script exits 1;
``--force`` writes it anyway.

``--exclude-synthetic`` never overwrites a file already in the stash: a name
that is taken gets the suffix ``_<created_utc>``; if that is taken too, nothing
is moved and the script exits 1. It moves the very file the scan loaded (the
path ``load_all_pairs`` read), not a name rebuilt from the stored ``pair_id``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lunar_reg.results import load_all_pairs, reindex  # noqa: E402

DEFAULT_ROOT = Path("data/processed/results")
DEFAULT_STASH = Path("data/processed/results_ch2_synthetic_backup/pairs")


def scanned_paths(pairs_dir: Path, loaded, failed) -> list[Path]:
    """The ``.npz`` path each loaded result was read from, in ``loaded`` order.

    ``load_all_pairs`` scans ``sorted(pairs/*.npz)``, loads each by its file
    stem and returns the results in scan order, with the unreadable stems in
    ``failed``. Replaying that scan and dropping the failed stems gives the file
    behind every result, which can differ from ``<pair_id>.npz`` when a file was
    renamed. Raises ``RuntimeError`` when the directory changed under the scan.
    """
    failed_stems = {stem for stem, _ in failed}
    paths = [p for p in sorted(pairs_dir.glob("*.npz")) if p.stem not in failed_stems]
    if len(paths) != len(loaded):
        raise RuntimeError(
            f"{pairs_dir} changed during the scan ({len(paths)} readable file(s) now, "
            f"{len(loaded)} loaded); re-run"
        )
    return paths


def _stamp(created_utc: str) -> str:
    """``created_utc`` as a file-name-safe suffix (``:`` and ``+`` are replaced)."""
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in (created_utc or "unknown"))


def plan_stash_moves(paths: list[Path], results, stash_dir: Path):
    """``(moves, refused)``: one ``(src, dst)`` per path, never onto an existing file.

    A taken name gets ``_<created_utc>``; when that is taken as well the file is
    refused as ``(src, reason)``. Checked before anything moves.
    """
    moves, refused, claimed = [], [], set()
    for path, result in zip(paths, results, strict=True):
        target = stash_dir / path.name
        if target.exists() or target in claimed:
            target = stash_dir / f"{path.stem}_{_stamp(result.created_utc)}{path.suffix}"
        if target.exists() or target in claimed:
            refused.append((path, f"stash file exists: {target}"))
            continue
        claimed.add(target)
        moves.append((path, target))
    return moves, refused


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--exclude-synthetic",
        action="store_true",
        help="move synthetic pairs to --stash-dir and index only the rest",
    )
    parser.add_argument("--stash-dir", type=Path, default=DEFAULT_STASH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="write the index even when unreadable files would make it shrink",
    )
    args = parser.parse_args(argv)

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
        paths = scanned_paths(pairs_dir, loaded, failed)
        chosen = [(p, r) for p, r in zip(paths, loaded, strict=True) if r.synthetic]
        moves, refused = plan_stash_moves(
            [p for p, _ in chosen], [r for _, r in chosen], args.stash_dir
        )
        if refused:
            print(
                f"refusing to overwrite {len(refused)} stash file(s); nothing moved, "
                "index not touched",
                file=sys.stderr,
            )
            for path, why in refused:
                print(f"    ! {path.name}: {why}", file=sys.stderr)
            return 1
        renamed = sum(1 for src, dst in moves if dst.name != src.name)
        if not args.dry_run:
            args.stash_dir.mkdir(parents=True, exist_ok=True)
            for src, dst in moves:
                shutil.move(str(src), str(dst))
        print(
            f"  {'would move' if args.dry_run else 'moved'} {len(moves)} synthetic "
            f"pair(s) -> {args.stash_dir} ({renamed} with a _<created_utc> suffix "
            "because the name was taken)"
        )

    if args.dry_run:
        print(f"\ndry run: would write {len(keep)} row(s) to {args.root / 'index.parquet'}")
        return 0

    # After any synthetic move, the .npz left on disk are exactly ``keep``.
    store = reindex(args.root, force=args.force)
    print()
    print(store.report())
    if not store.index_written:
        return 1
    frame = store.frame
    if len(frame):
        cols = [
            c
            for c in ("pair_id", "source_sensor", "reference_sensor", "matcher", "synthetic")
            if c in frame.columns
        ]
        print(frame[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
