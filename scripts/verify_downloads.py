"""Verify ``data/raw/DOWNLOADS.json`` against the files on disk.

Every manifest entry is classified OK / MISSING / SIZE_MISMATCH /
HASH_MISMATCH, every recorded failed download becomes one HTTP_ERROR, and
(unless ``--no-scan``) every file under ``data/raw/`` that no entry names and
that is not a pre-plan file is reported UNRECORDED (suspicious, not a failure).
Reads only: nothing is ever deleted, moved or rewritten.

    python scripts/verify_downloads.py                 # full check (hashes every file)
    python scripts/verify_downloads.py --no-hash       # sizes only (fast)
    python scripts/verify_downloads.py --no-scan       # skip the unrecorded-file scan
    python scripts/verify_downloads.py --manifest PATH # another manifest

Prints the report on every run. Exit 1 when any failure status (missing,
size_mismatch, hash_mismatch, http_error) was recorded, else 0. A missing
manifest is an empty manifest (exit 0). Run from the repo root: entry paths are
repo-relative.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lunar_reg.ingest.downloads import DEFAULT_MANIFEST, verify_downloads  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"manifest path (default {DEFAULT_MANIFEST})",
    )
    ap.add_argument("--no-hash", action="store_true", help="compare sizes only, skip sha256")
    ap.add_argument(
        "--no-scan", action="store_true", help="do not scan data/raw for unrecorded files"
    )
    args = ap.parse_args(argv)
    diag = verify_downloads(
        manifest=args.manifest, check_hash=not args.no_hash, scan_unrecorded=not args.no_scan
    )
    print(diag.report())
    return 1 if diag.has_failure else 0


if __name__ == "__main__":
    sys.exit(main())
