"""Common matcher interface.

Every matcher -- classical or learned, tiled or whole-image -- returns a
:class:`MatchResult` in the *parent product's* pixel coordinates. Keeping one
result type is what lets the benchmark table in ``eval/`` compare SIFT against
LoFTR without special-casing either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass
class MatchResult:
    """Correspondences between a source and a reference image.

    ``src_pts`` and ``dst_pts`` are ``(N, 2)`` float arrays of ``(x, y)`` pixel
    coordinates. They are float, not int, because sub-pixel accuracy is the
    stated requirement -- never round them for storage.
    """

    src_pts: np.ndarray
    dst_pts: np.ndarray
    scores: np.ndarray | None = None
    matcher: str = "unknown"
    #: Set by the alignment stage once RANSAC has run.
    inlier_mask: np.ndarray | None = None
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.src_pts = np.asarray(self.src_pts, dtype=np.float64).reshape(-1, 2)
        self.dst_pts = np.asarray(self.dst_pts, dtype=np.float64).reshape(-1, 2)
        if self.src_pts.shape != self.dst_pts.shape:
            raise ValueError(
                f"src/dst point counts differ: {self.src_pts.shape} vs {self.dst_pts.shape}"
            )
        if self.scores is not None:
            self.scores = np.asarray(self.scores, dtype=np.float64).reshape(-1)

    def __len__(self) -> int:
        return len(self.src_pts)

    @property
    def n_inliers(self) -> int:
        return int(self.inlier_mask.sum()) if self.inlier_mask is not None else 0

    @property
    def inlier_ratio(self) -> float:
        return self.n_inliers / len(self) if len(self) else 0.0

    def inliers(self) -> MatchResult:
        """A new result containing only the RANSAC inliers."""
        if self.inlier_mask is None:
            return self
        m = self.inlier_mask.astype(bool)
        return MatchResult(
            src_pts=self.src_pts[m],
            dst_pts=self.dst_pts[m],
            scores=None if self.scores is None else self.scores[m],
            matcher=self.matcher,
            meta={**self.meta, "filtered": "inliers"},
        )

    @classmethod
    def empty(cls, matcher: str = "unknown") -> MatchResult:
        return cls(np.empty((0, 2)), np.empty((0, 2)), matcher=matcher)

    @classmethod
    def concatenate(cls, results, matcher: str | None = None) -> MatchResult:
        """Merge per-tile results into one whole-image result.

        Coordinates must already be lifted into parent space via
        :meth:`lunar_reg.ingest.Tile.to_parent`.
        """
        results = [r for r in results if len(r)]
        if not results:
            return cls.empty(matcher or "unknown")
        has_scores = all(r.scores is not None for r in results)
        return cls(
            src_pts=np.vstack([r.src_pts for r in results]),
            dst_pts=np.vstack([r.dst_pts for r in results]),
            scores=np.concatenate([r.scores for r in results]) if has_scores else None,
            matcher=matcher or results[0].matcher,
            meta={"n_tiles": len(results)},
        )


@runtime_checkable
class Matcher(Protocol):
    """Structural interface every matcher satisfies."""

    name: str

    def match(self, source: np.ndarray, reference: np.ndarray) -> MatchResult:
        """Find correspondences between two single-band, preprocessed images."""
        ...
