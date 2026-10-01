"""Stitching tile-wise matches into one whole-image correspondence set.

Tiles overlap on purpose: a feature near a tile edge has truncated descriptor
support, so without overlap the match field develops periodic gaps along the
seams -- exactly the clustering the uniform-distribution requirement penalises.

Overlap has a cost, though. A feature inside an overlap region is matched **once
per tile that contains it**, so the merged set contains duplicates. Left alone
they:

* inflate the reported match count, making a result look better than it is;
* bias RANSAC, because a duplicated correspondence votes more than once and the
  overlap regions are a regular grid, so the bias is systematic rather than
  random;
* skew the uniformity metric, since duplicates concentrate in a lattice of
  overlap strips.

So the merge deduplicates. Two matches are duplicates when their source points
agree to within a tolerance **and** their destination points do too -- requiring
both stops two genuinely different correspondences that happen to share a source
pixel from being collapsed.

Which duplicate survives
------------------------
The copy from the tile where the feature sat **furthest from the tile edge**.
That copy had the most complete descriptor support and the least truncated
receptive field, so it is the better measurement. Equal priorities keep the
copy with the highest original index; when no priority is passed, the match
score is the priority (zeros when there are no scores).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from lunar_reg.match.base import MatchResult

logger = logging.getLogger(__name__)

#: Coordinate tolerance for calling two matches the same, in parent pixels.
#: Duplicates from adjacent tiles land within a fraction of a pixel of each
#: other -- they are the same feature seen through a different crop -- so this
#: is generous. Raising it starts merging genuinely distinct nearby matches.
DEFAULT_TOLERANCE_PX = 1.5


@dataclass
class StitchStats:
    """What the merge did, for reporting and for spotting a bad overlap setting."""

    n_before: int
    n_after: int
    n_tiles: int
    tolerance_px: float

    @property
    def n_removed(self) -> int:
        return self.n_before - self.n_after

    @property
    def duplicate_fraction(self) -> float:
        return self.n_removed / self.n_before if self.n_before else 0.0

    def __str__(self) -> str:
        return (
            f"stitched {self.n_tiles} tiles: {self.n_before} -> {self.n_after} matches "
            f"({self.n_removed} duplicates removed, "
            f"{100 * self.duplicate_fraction:.1f}%, tol={self.tolerance_px}px)"
        )


def edge_distance(points: np.ndarray, tile_height: int, tile_width: int) -> np.ndarray:
    """Distance from each tile-local point to the nearest tile edge, in pixels.

    The preference signal for deduplication: a larger value means the feature
    was further inside the tile and had fuller descriptor support.
    """
    points = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    if len(points) == 0:
        return np.empty(0)
    return np.minimum.reduce(
        [
            points[:, 0],
            points[:, 1],
            tile_width - 1 - points[:, 0],
            tile_height - 1 - points[:, 1],
        ]
    )


def deduplicate(
    result: MatchResult,
    priority: np.ndarray | None = None,
    tolerance_px: float = DEFAULT_TOLERANCE_PX,
) -> tuple[MatchResult, int]:
    """Collapse duplicate correspondences, keeping the highest-priority copy.

    ``priority`` is one value per match, larger meaning "prefer this copy";
    :func:`edge_distance` supplies it in the tiled path. When omitted, the match
    score is used, falling back to arbitrary-but-deterministic order.

    Returns ``(deduplicated, n_removed)``. Grouping is by connected components
    over the "is a duplicate of" relation, so a feature appearing in three
    overlapping tiles collapses to one match rather than to two.
    """
    n = len(result)
    if n < 2:
        return result, 0

    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    src = result.src_pts
    dst = result.dst_pts

    pairs = cKDTree(src).query_pairs(r=tolerance_px, output_type="ndarray")
    if len(pairs):
        # Both ends must agree, or these are different correspondences that
        # merely share a source location.
        dst_close = np.linalg.norm(dst[pairs[:, 0]] - dst[pairs[:, 1]], axis=1) <= tolerance_px
        pairs = pairs[dst_close]

    if not len(pairs):
        return result, 0

    graph = coo_matrix(
        (np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(n, n)
    )
    n_groups, labels = connected_components(graph, directed=False)
    if n_groups == n:
        return result, 0

    if priority is None:
        priority = result.scores if result.scores is not None else np.zeros(n)
    priority = np.asarray(priority, dtype=np.float64).reshape(-1)

    # Keep the highest-priority member of each connected component. lexsort's
    # last key is primary, so this sorts by (label, priority) and takes the last
    # entry per label.
    order = np.lexsort((priority, labels))
    sorted_labels = labels[order]
    last_of_group = np.ones(len(order), dtype=bool)
    last_of_group[:-1] = sorted_labels[:-1] != sorted_labels[1:]
    keep = np.sort(order[last_of_group])

    deduplicated = MatchResult(
        src_pts=src[keep],
        dst_pts=dst[keep],
        scores=None if result.scores is None else result.scores[keep],
        matcher=result.matcher,
        meta={**result.meta, "deduplicated": True, "tolerance_px": tolerance_px},
    )
    return deduplicated, n - len(keep)


def stitch_tiles(
    results: list[MatchResult],
    priorities: list[np.ndarray] | None = None,
    tolerance_px: float = DEFAULT_TOLERANCE_PX,
    matcher: str | None = None,
    deduplicate_overlaps: bool = True,
) -> tuple[MatchResult, StitchStats]:
    """Merge per-tile results, already in parent coordinates, and deduplicate.

    ``results`` must already have been lifted out of tile-local coordinates --
    see :meth:`lunar_reg.ingest.tiling.Tile.to_parent`. Merging tile-local
    coordinates would silently collapse matches from different tiles that share
    a local position, which is most of them.
    """
    non_empty = [(i, r) for i, r in enumerate(results) if len(r)]
    if not non_empty:
        return MatchResult.empty(matcher or "tiled"), StitchStats(0, 0, len(results), tolerance_px)

    merged = MatchResult.concatenate([r for _, r in non_empty], matcher=matcher)
    n_before = len(merged)

    priority = None
    if priorities is not None:
        chosen = [priorities[i] for i, _ in non_empty]
        aligned = all(
            p is not None and len(p) == len(r) for p, (_, r) in zip(chosen, non_empty, strict=True)
        )
        if aligned:
            priority = np.concatenate(chosen)
        else:
            logger.warning("priority arrays did not line up with results; falling back to scores")

    if deduplicate_overlaps:
        merged, _ = deduplicate(merged, priority, tolerance_px)

    stats = StitchStats(n_before, len(merged), len(results), tolerance_px)
    logger.info("%s", stats)
    return merged, stats
