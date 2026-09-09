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
      pairs/<pair_id>.npz        points, inlier mask, transform, images

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
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

#: Longest edge of the stored preview images, in pixels.
THUMBNAIL_MAX_PX = 1024

SCHEMA_VERSION = 1


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

    def __post_init__(self) -> None:
        self.src_pts = np.asarray(self.src_pts, dtype=np.float64).reshape(-1, 2)
        self.dst_pts = np.asarray(self.dst_pts, dtype=np.float64).reshape(-1, 2)
        if self.src_pts.shape != self.dst_pts.shape:
            raise ValueError(
                f"{self.pair_id}: src/dst counts differ "
                f"({len(self.src_pts)} vs {len(self.dst_pts)})"
            )
        if self.inlier_mask is not None:
            self.inlier_mask = np.asarray(self.inlier_mask, dtype=bool).reshape(-1)
            if len(self.inlier_mask) != len(self.src_pts):
                raise ValueError(
                    f"{self.pair_id}: inlier mask has {len(self.inlier_mask)} entries "
                    f"for {len(self.src_pts)} points"
                )
        if not self.created_utc:
            self.created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    @property
    def n_matches(self) -> int:
        return len(self.src_pts)

    @property
    def n_inliers(self) -> int:
        return int(self.inlier_mask.sum()) if self.inlier_mask is not None else self.n_matches

    def index_row(self) -> dict:
        """Flat row for ``index.parquet``.

        Metric groups are prefixed rather than merged, because ``rmse_px`` from
        the accuracy metrics and ``p95_px`` from conditioning mean different
        things and a collision would silently overwrite one with the other.
        """
        row = {
            "pair_id": self.pair_id,
            "source_id": self.source_id,
            "reference_id": self.reference_id,
            "source_sensor": self.source_sensor,
            "reference_sensor": self.reference_sensor,
            "matcher": self.matcher,
            "n_matches": self.n_matches,
            "n_inliers": self.n_inliers,
            "synthetic": self.synthetic,
            "notes": self.notes,
            "created_utc": self.created_utc,
            "schema_version": SCHEMA_VERSION,
        }
        for prefix, group in (
            ("m", self.metrics), ("u", self.uniformity), ("c", self.conditioning)
        ):
            for key, value in group.items():
                plain = _plain(value)
                if _is_scalar(plain):
                    row[f"{prefix}_{key}"] = plain
        for key, value in self.extra.items():
            plain = _plain(value)
            if _is_scalar(plain):
                row[f"x_{key}"] = plain
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
        array, (int(array.shape[1] * scale), int(array.shape[0] * scale)),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def save_pair(result: PairResult, root: str | Path) -> Path:
    """Write one pair's arrays to ``<root>/pairs/<pair_id>.npz``."""
    root = Path(root)
    (root / "pairs").mkdir(parents=True, exist_ok=True)
    path = root / "pairs" / f"{result.pair_id}.npz"

    source_thumb, source_scale = _thumbnail(result.source_image)
    reference_thumb, reference_scale = _thumbnail(result.reference_image)

    payload = {
        "src_pts": result.src_pts,
        "dst_pts": result.dst_pts,
        "transform": np.asarray(result.transform, dtype=np.float64),
        "meta": np.array(json.dumps({
            **{k: v for k, v in asdict(result).items()
               if k not in {"src_pts", "dst_pts", "inlier_mask", "transform",
                            "source_image", "reference_image"}},
            "source_scale": source_scale,
            "reference_scale": reference_scale,
            "schema_version": SCHEMA_VERSION,
        }, default=_plain)),
    }
    if result.inlier_mask is not None:
        payload["inlier_mask"] = result.inlier_mask
    if source_thumb is not None:
        payload["source_image"] = source_thumb
    if reference_thumb is not None:
        payload["reference_image"] = reference_thumb

    np.savez_compressed(path, **payload)
    return path


def load_pair(pair_id: str, root: str | Path) -> PairResult:
    """Read one pair back. Raises ``FileNotFoundError`` if it was never written."""
    path = Path(root) / "pairs" / f"{pair_id}.npz"
    if not path.exists():
        raise FileNotFoundError(f"no stored result for pair {pair_id!r} at {path}")

    with np.load(path, allow_pickle=False) as data:
        meta = json.loads(str(data["meta"]))
        version = meta.get("schema_version")
        if version != SCHEMA_VERSION:
            logger.warning(
                "pair %s was written by schema version %s, this is version %s; "
                "fields may be missing", pair_id, version, SCHEMA_VERSION,
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
        )
    result.extra.setdefault("source_scale", meta.get("source_scale", 1.0))
    result.extra.setdefault("reference_scale", meta.get("reference_scale", 1.0))
    return result


def write_index(results, root: str | Path):
    """Rebuild ``index.parquet`` from a list of results. Returns the DataFrame."""
    import pandas as pd

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([r.index_row() for r in results])
    if len(frame):
        frame = frame.sort_values("pair_id").reset_index(drop=True)
    frame.to_parquet(root / "index.parquet", index=False)
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
    for pair_id, reason in failures:
        logger.warning("could not load stored pair %s: %s", pair_id, reason)
    return results, failures


def reindex(root: str | Path):
    """Rebuild ``index.parquet`` from every ``.npz`` on disk. Returns the frame."""
    results, _ = load_all_pairs(root)
    frame = write_index(results, root)
    logger.info("reindexed %s: %d pair(s)", root, len(frame))
    return frame


def save_results(results, root: str | Path, reindex_all: bool = True):
    """Persist a batch of results and rebuild the index.

    The index is rebuilt from **every** pair on disk, not just this batch, so
    running one build after another never drops the earlier pairs from
    ``index.parquet`` while their ``.npz`` files sit unindexed. Pass
    ``reindex_all=False`` for the old batch-only behaviour.
    """
    root = Path(root)
    for result in results:
        save_pair(result, root)
    frame = reindex(root) if reindex_all else write_index(results, root)
    logger.info("wrote %d pair result(s) to %s; index covers %d", len(results), root, len(frame))
    return frame


__all__ = [
    "SCHEMA_VERSION",
    "THUMBNAIL_MAX_PX",
    "PairResult",
    "load_all_pairs",
    "load_index",
    "load_pair",
    "reindex",
    "save_pair",
    "save_results",
    "write_index",
]
