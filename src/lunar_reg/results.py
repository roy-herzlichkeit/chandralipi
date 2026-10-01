"""Per-pair result persistence.

Until now the pipeline computed correspondences, a transform and metrics, and
then dropped them: only the ingest manifest and the overlap pair table reached
disk. Nothing could browse what had been registered, compare two matchers on the
same pair, or redraw a match figure without rerunning the match.

This module is the minimal addition that fixes that, and it is deliberately an
*addition* -- no matching, alignment or evaluation code changes shape to
accommodate it.

Layout
------
::

    results/
      index.parquet              one row per registered pair
      failures.parquet           one row per pair that did not register (appended)
      pairs/<pair_id>.npz        points, masks, transforms, images

``index.parquet`` is the browsable table: identifiers, sensors, matcher, and
every metric, flat, one row per pair. The ``.npz`` holds the arrays that would
bloat a table.

Two decisions worth stating
---------------------------
**Point coordinates are stored float64 and never rounded.** The whole project
is about sub-pixel accuracy; storing pixel indices would throw away the answer.

**Thumbnails are stored alongside the arrays.** A dashboard that has to reopen a
90,000-line OHRC strip to draw one figure is unusable, and the source rasters
may not even be present on the machine doing the browsing.

Schema v2 (CONTRACTS C04/C05): ``pair_id`` is validated (it becomes a file
name), every file is written to a temp file and renamed into place, a stored
pair is never overwritten unless asked, the points are the raw matcher output
with first-pass (``ransac_mask``) and final (``inlier_mask``) masks over them
(DECISIONS G34), failed pairs are persisted to ``failures.parquet``, and a
reindex that would silently shrink a good index because files failed to load
keeps the old index instead. v1 records still load.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas

logger = logging.getLogger(__name__)

#: Longest edge of the stored preview images, in pixels.
THUMBNAIL_MAX_PX = 1024

SCHEMA_VERSION = 2
PAIR_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"

#: Fields stored as npz arrays rather than in the JSON ``meta``.
_ARRAY_FIELDS = frozenset(
    {
        "src_pts",
        "dst_pts",
        "inlier_mask",
        "transform",
        "ransac_mask",
        "pre_ecc_transform",
        "source_image",
        "reference_image",
    }
)


def _check_pair_id(pair_id: str) -> None:
    if not isinstance(pair_id, str) or not re.fullmatch(PAIR_ID_PATTERN, pair_id):
        raise ValueError(f"invalid pair_id {pair_id!r}: must match {PAIR_ID_PATTERN}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class PairResult:
    """Everything one registered pair produced.

    ``extra`` carries anything a caller wants in the index that this schema does
    not name -- sun angles, tile counts, an ablation label. It is flattened into
    the index with an ``x_`` prefix, so adding a field never requires changing
    this class.
    """

    pair_id: str
    source_id: str
    reference_id: str
    source_sensor: str
    reference_sensor: str
    matcher: str

    src_pts: np.ndarray
    dst_pts: np.ndarray
    inlier_mask: np.ndarray | None
    transform: np.ndarray

    metrics: dict = field(default_factory=dict)
    uniformity: dict = field(default_factory=dict)
    conditioning: dict = field(default_factory=dict)

    source_image: np.ndarray | None = None
    reference_image: np.ndarray | None = None

    #: Free-form provenance. ``synthetic`` is load-bearing: a result computed on
    #: generated scenes must never be presented as a lunar measurement, and the
    #: dashboard reads this field to say so on screen.
    synthetic: bool = False
    notes: str = ""
    extra: dict = field(default_factory=dict)
    created_utc: str = ""
    #: v2: first-pass RANSAC inliers over the raw set (G34); None for v1 records.
    ransac_mask: np.ndarray | None = None
    #: v2: transform after the refit, before ECC; None for v1 records.
    pre_ecc_transform: np.ndarray | None = None
    #: v2: the schema version the record was written with.
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_pair_id(self.pair_id)
        self.src_pts = np.asarray(self.src_pts, dtype=np.float64).reshape(-1, 2)
        self.dst_pts = np.asarray(self.dst_pts, dtype=np.float64).reshape(-1, 2)
        if self.src_pts.shape != self.dst_pts.shape:
            raise ValueError(
                f"{self.pair_id}: src/dst counts differ "
                f"({len(self.src_pts)} vs {len(self.dst_pts)})"
            )
        for name in ("inlier_mask", "ransac_mask"):
            mask = getattr(self, name)
            if mask is None:
                continue
            mask = np.asarray(mask, dtype=bool).reshape(-1)
            if len(mask) != len(self.src_pts):
                label = "inlier mask" if name == "inlier_mask" else "ransac mask"
                raise ValueError(
                    f"{self.pair_id}: {label} has {len(mask)} entries "
                    f"for {len(self.src_pts)} points"
                )
            setattr(self, name, mask)
        if self.pre_ecc_transform is not None:
            self.pre_ecc_transform = np.asarray(self.pre_ecc_transform, dtype=np.float64)
        if not self.created_utc:
            self.created_utc = _utc_now()

    @property
    def n_matches(self) -> int:
        return len(self.src_pts)

    @property
    def n_inliers(self) -> int:
        return int(self.inlier_mask.sum()) if self.inlier_mask is not None else self.n_matches

    @property
    def n_ransac_inliers(self) -> int | None:
        return None if self.ransac_mask is None else int(self.ransac_mask.sum())

    @property
    def inlier_ratio(self) -> float:
        return self.n_inliers / self.n_matches if self.n_matches else 0.0

    def index_row(self) -> dict:
        """Flat row for ``index.parquet``.

        Metric groups are prefixed rather than merged, because ``rmse_px`` from
        the accuracy metrics and ``p95_px`` from conditioning mean different
        things and a collision would silently overwrite one with the other.
        Values are Python scalars; lists, tuples, dicts and arrays become JSON
        strings; anything else raises ``TypeError`` naming the column.
        """
        row = {
            "pair_id": self.pair_id,
            "source_id": self.source_id,
            "reference_id": self.reference_id,
            "source_sensor": self.source_sensor,
            "reference_sensor": self.reference_sensor,
            "matcher": self.matcher,
            "n_matches": self.n_matches,
            "n_ransac_inliers": self.n_ransac_inliers,
            "n_inliers": self.n_inliers,
            "inlier_ratio": self.inlier_ratio,
            "synthetic": self.synthetic,
            "notes": self.notes,
            "created_utc": self.created_utc,
            "schema_version": self.schema_version,
        }
        for prefix, group in (
            ("m", self.metrics),
            ("u", self.uniformity),
            ("c", self.conditioning),
            ("x", self.extra),
        ):
            for key, value in group.items():
                row[f"{prefix}_{key}"] = _plain_for_index(f"{prefix}_{key}", value)
        return row


def _plain(value):
    """Numpy scalars to their Python equivalents, everything else untouched.

    Metric dataclasses carry ``np.bool_`` and ``np.float64`` throughout. Neither
    survives ``json.dumps``, and ``np.bool_`` is not a subclass of ``bool``, so an
    ``isinstance`` filter silently drops every boolean flag from the index rather
    than raising. Both failures are fixed in one place here.
    """
    if isinstance(value, np.generic):
        return value.item()
    return value


def _is_scalar(value) -> bool:
    return value is None or isinstance(value, (int, float, bool, str))


def _json_default(value):
    """``json.dumps`` hook: numpy scalars and arrays; anything else is a TypeError."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"cannot JSON-encode {type(value).__name__}")


def _plain_for_index(column: str, value):
    """One index cell: a Python scalar, or a JSON string for containers."""
    plain = _plain(value)
    if _is_scalar(plain):
        return plain
    if isinstance(plain, np.ndarray):
        return json.dumps(plain.tolist())
    if isinstance(plain, (list, tuple, dict)):
        return json.dumps(plain, sort_keys=True, default=_json_default)
    raise TypeError(f"{column}: cannot store {type(value).__name__} in the index")


def _atomic_replace(tmp: Path, path: Path, write) -> None:
    """Run ``write(tmp)``, then ``os.replace(tmp, path)``; never leave ``tmp`` behind."""
    replaced = False
    try:
        write(tmp)
        os.replace(tmp, path)
        replaced = True
    finally:
        if not replaced:
            tmp.unlink(missing_ok=True)


def _thumbnail(image: np.ndarray | None, max_px: int = THUMBNAIL_MAX_PX):
    """Downscale for storage, returning the array and the scale applied.

    The scale is returned and stored because match coordinates are in *full*
    resolution. A viewer that forgot to apply it would draw every point in the
    wrong place, and the error would look like a registration failure rather
    than a display bug.
    """
    import cv2

    if image is None:
        return None, 1.0
    array = np.asarray(image)
    longest = max(array.shape[:2])
    if longest <= max_px:
        return array, 1.0
    scale = max_px / longest
    resized = cv2.resize(
        array,
        (int(array.shape[1] * scale), int(array.shape[0] * scale)),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def _pair_path(pair_id: str, root: Path) -> Path:
    _check_pair_id(pair_id)
    return root / "pairs" / f"{pair_id}.npz"


def save_pair(result: PairResult, root: str | Path, overwrite: bool = False) -> Path:
    """Write one pair's arrays to ``<root>/pairs/<pair_id>.npz``, atomically.

    Raises ``FileExistsError`` when the file exists and ``overwrite`` is False
    (checked before anything is written).
    """
    root = Path(root)
    path = _pair_path(result.pair_id, root)
    if path.exists() and not overwrite:
        raise FileExistsError(f"stored result exists for pair {result.pair_id!r}: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)

    source_thumb, source_scale = _thumbnail(result.source_image)
    reference_thumb, reference_scale = _thumbnail(result.reference_image)

    meta = {
        f.name: getattr(result, f.name)
        for f in dataclasses.fields(result)
        if f.name not in _ARRAY_FIELDS
    }
    meta.update(
        source_scale=source_scale,
        reference_scale=reference_scale,
        schema_version=result.schema_version,
    )
    payload = {
        "src_pts": result.src_pts,
        "dst_pts": result.dst_pts,
        "transform": np.asarray(result.transform, dtype=np.float64),
        "meta": np.array(json.dumps(meta, default=_json_default)),
    }
    for name in ("inlier_mask", "ransac_mask", "pre_ecc_transform"):
        value = getattr(result, name)
        if value is not None:
            payload[name] = value
    if source_thumb is not None:
        payload["source_image"] = source_thumb
    if reference_thumb is not None:
        payload["reference_image"] = reference_thumb

    def write(tmp: Path) -> None:
        # Through a file handle: given a *path* without ``.npz`` numpy appends
        # the suffix, and the rename would then miss the file it wrote.
        with open(tmp, "wb") as fh:
            np.savez_compressed(fh, **payload)
            fh.flush()
            os.fsync(fh.fileno())

    _atomic_replace(path.with_name(f".{path.name}.tmp"), path, write)
    return path


def load_pair(pair_id: str, root: str | Path) -> PairResult:
    """Read one pair back (schema v1 or v2). Raises ``FileNotFoundError`` if never written."""
    path = _pair_path(pair_id, Path(root))
    if not path.exists():
        raise FileNotFoundError(f"no stored result for pair {pair_id!r} at {path}")

    with np.load(path, allow_pickle=False) as data:
        meta = json.loads(str(data["meta"]))
        version = int(meta.get("schema_version", 1))
        if version > SCHEMA_VERSION:
            logger.warning(
                "pair %s was written by schema version %s, newer than this reader (%s); "
                "fields may be missing",
                pair_id,
                version,
                SCHEMA_VERSION,
            )
        result = PairResult(
            pair_id=meta["pair_id"],
            source_id=meta["source_id"],
            reference_id=meta["reference_id"],
            source_sensor=meta["source_sensor"],
            reference_sensor=meta["reference_sensor"],
            matcher=meta["matcher"],
            src_pts=data["src_pts"],
            dst_pts=data["dst_pts"],
            inlier_mask=data.get("inlier_mask"),
            transform=data["transform"],
            metrics=meta.get("metrics", {}),
            uniformity=meta.get("uniformity", {}),
            conditioning=meta.get("conditioning", {}),
            source_image=data.get("source_image"),
            reference_image=data.get("reference_image"),
            synthetic=meta.get("synthetic", False),
            notes=meta.get("notes", ""),
            extra=meta.get("extra", {}),
            created_utc=meta.get("created_utc", ""),
            ransac_mask=data.get("ransac_mask"),
            pre_ecc_transform=data.get("pre_ecc_transform"),
            schema_version=version,
        )
    result.extra.setdefault("source_scale", meta.get("source_scale", 1.0))
    result.extra.setdefault("reference_scale", meta.get("reference_scale", 1.0))
    return result


def write_index(results, root: str | Path):
    """Rebuild ``index.parquet`` from a list of results, atomically. Returns the DataFrame."""
    import pandas as pd

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([r.index_row() for r in results])
    if len(frame):
        frame = frame.sort_values("pair_id").reset_index(drop=True)
    _atomic_replace(
        root / ".index.parquet.tmp",
        root / "index.parquet",
        lambda tmp: frame.to_parquet(tmp, index=False),
    )
    return frame


def load_index(root: str | Path):
    """Read the pair index, or an empty frame when nothing has been written."""
    import pandas as pd

    path = Path(root) / "index.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_all_pairs(root: str | Path):
    """Load every ``pairs/*.npz`` under ``root``.

    Returns ``(results, failures)`` where ``failures`` is a list of
    ``(pair_id, reason)`` -- a single unreadable file is reported, never allowed
    to abort the scan.
    """
    root = Path(root)
    results, failures = [], []
    for path in sorted((root / "pairs").glob("*.npz")):
        try:
            results.append(load_pair(path.stem, root))
        except Exception as exc:  # noqa: BLE001 -- one bad file must not stop the rest
            failures.append((path.stem, f"{type(exc).__name__}: {exc}"))
    if failures:
        logger.warning(
            "%d stored pair(s) under %s could not be loaded, e.g. %s: %s",
            len(failures),
            root,
            *failures[0],
        )
    return results, failures


# ---------------------------------------------------------------------------
# Failures (C05)
# ---------------------------------------------------------------------------

FAILURE_COLUMNS = (
    "pair_id",
    "status",
    "detail",
    "stage",
    "matcher",
    "model",
    "source_id",
    "reference_id",
    "source_sensor",
    "reference_sensor",
    "n_raw_matches",
    "n_ransac_inliers",
    "created_utc",
    "schema_version",
)


def _failure_row(outcome) -> dict:
    extra = dict(outcome.extra)
    row = {
        "pair_id": outcome.pair_id,
        "status": outcome.status.value,
        "detail": outcome.detail,
        "stage": extra.get("stage"),
        "matcher": extra.get("matcher"),
        "model": extra.get("model"),
        "source_id": extra.get("source_id"),
        "reference_id": extra.get("reference_id"),
        "source_sensor": extra.get("source_sensor"),
        "reference_sensor": extra.get("reference_sensor"),
        "n_raw_matches": extra.get("n_raw_matches"),
        "n_ransac_inliers": extra.get("n_ransac_inliers"),
        "created_utc": _utc_now(),
        "schema_version": SCHEMA_VERSION,
    }
    for key, value in extra.items():
        if key in row:
            continue
        row[f"x_{key}"] = _plain_for_index(f"x_{key}", value)
    return row


def save_failures(outcomes, root: str | Path) -> Path:
    """Append one row per failed outcome to ``<root>/failures.parquet`` (atomic rewrite).

    OK outcomes are ignored. Existing rows are kept as they are; with no failed
    outcome nothing is written.
    """
    import pandas as pd

    root = Path(root)
    path = root / "failures.parquet"
    rows = [_failure_row(o) for o in outcomes if not o.ok]
    if not rows:
        return path
    root.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(rows)
    ordered = list(FAILURE_COLUMNS) + sorted(c for c in new.columns if c not in FAILURE_COLUMNS)
    new = new[ordered]
    old = load_failures(root)
    frame = pd.concat([old, new], ignore_index=True) if len(old) else new
    _atomic_replace(
        root / ".failures.parquet.tmp", path, lambda tmp: frame.to_parquet(tmp, index=False)
    )
    logger.info("recorded %d failed pair(s) in %s (%d total)", len(rows), path, len(frame))
    return path


def load_failures(root: str | Path):
    """Read ``failures.parquet``, or an empty frame when absent."""
    import pandas as pd

    path = Path(root) / "failures.parquet"
    if not path.exists():
        return pd.DataFrame(columns=list(FAILURE_COLUMNS))
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# Store report, reindex, save (C05)
# ---------------------------------------------------------------------------


@dataclass
class StoreReport:
    """What a save or reindex did to the store; ``report()`` is printed on every run."""

    frame: pandas.DataFrame  # the index as written (or as kept)
    n_saved: int
    load_failures: list[tuple[str, str]]
    index_written: bool
    index_rows_before: int

    def report(self) -> str:
        root = getattr(self, "_root", "")
        state = "written" if self.index_written else "KEPT"
        lines = [
            f"store {root}: saved {self.n_saved}, index rows {self.index_rows_before} -> "
            f"{len(self.frame)} ({state})"
        ]
        if self.load_failures:
            pid, reason = self.load_failures[0]
            lines.append(f"  load failures: {len(self.load_failures)}  e.g. {pid}: {reason}"[:300])
            lines.extend(f"    ! {p}: {r}"[:300] for p, r in self.load_failures)
            if not self.index_written:
                lines.append(
                    "  index KEPT: rebuilding would drop rows only because files failed "
                    "to load; fix them or reindex with force=True"
                )
        else:
            lines.append("  no load failures")
        return "\n".join(lines)


def _store_report(root: Path, **kwargs) -> StoreReport:
    report = StoreReport(**kwargs)
    report._root = str(root)  # for report(); not a contract field
    return report


def reindex(root: str | Path, force: bool = False) -> StoreReport:
    """Rebuild ``index.parquet`` from every ``.npz`` on disk.

    Refuses (keeps the old index, ``index_written=False``) when at least one
    file failed to load and the new index would have fewer rows than the old
    one, unless ``force=True``.
    """
    root = Path(root)
    rows_before = len(load_index(root))
    results, failures = load_all_pairs(root)
    if failures and len(results) < rows_before and not force:
        logger.warning(
            "reindex %s: %d file(s) failed to load and the index would shrink %d -> %d; "
            "keeping the existing index",
            root,
            len(failures),
            rows_before,
            len(results),
        )
        return _store_report(
            root,
            frame=load_index(root),
            n_saved=0,
            load_failures=failures,
            index_written=False,
            index_rows_before=rows_before,
        )
    frame = write_index(results, root)
    logger.info("reindexed %s: %d pair(s)", root, len(frame))
    return _store_report(
        root,
        frame=frame,
        n_saved=0,
        load_failures=failures,
        index_written=True,
        index_rows_before=rows_before,
    )


def save_results(
    results, root: str | Path, reindex_all: bool = True, overwrite: bool = False
) -> StoreReport:
    """Persist a batch of results and rebuild the index.

    The index is rebuilt from **every** pair on disk, not just this batch, so
    running one build after another never drops the earlier pairs from
    ``index.parquet`` while their ``.npz`` files sit unindexed. Pass
    ``reindex_all=False`` for the old batch-only behaviour.

    Without ``overwrite`` an existing pair is never replaced: every target is
    checked first and ``FileExistsError`` names the clashes before anything is
    written. A batch that repeats a ``pair_id`` raises ``ValueError``, also
    before anything is written (whatever ``overwrite`` says): one id names one
    file, so the second copy would either clash mid-batch or silently replace
    the first.
    """
    root = Path(root)
    results = list(results)
    counts = Counter(r.pair_id for r in results)
    repeated = sorted(pid for pid, n in counts.items() if n > 1)
    if repeated:
        raise ValueError(
            f"{len(repeated)} pair_id(s) repeated within one batch; nothing was written: "
            f"{', '.join(repeated[:5])}"
        )
    if not overwrite:
        clashes = [r.pair_id for r in results if _pair_path(r.pair_id, root).exists()]
        if clashes:
            raise FileExistsError(
                f"{len(clashes)} pair(s) already stored under {root} (pass overwrite=True "
                f"to replace): {', '.join(clashes[:5])}"
            )
    for result in results:
        save_pair(result, root, overwrite=overwrite)
    if reindex_all:
        store = reindex(root)
        store.n_saved = len(results)
    else:
        rows_before = len(load_index(root))
        store = _store_report(
            root,
            frame=write_index(results, root),
            n_saved=len(results),
            load_failures=[],
            index_written=True,
            index_rows_before=rows_before,
        )
    logger.info(
        "wrote %d pair result(s) to %s; index covers %d", len(results), root, len(store.frame)
    )
    return store


__all__ = [
    "FAILURE_COLUMNS",
    "PAIR_ID_PATTERN",
    "SCHEMA_VERSION",
    "THUMBNAIL_MAX_PX",
    "PairResult",
    "StoreReport",
    "load_all_pairs",
    "load_failures",
    "load_index",
    "load_pair",
    "reindex",
    "save_failures",
    "save_pair",
    "save_results",
    "write_index",
]
