"""Tile-wise matching orchestration.

VRAM CONSTRAINT: this is the component that makes OHRC tractable.

Whole-image matching is impossible on 8 GB for a full strip, so the pipeline
matches tile against tile and merges the results in parent coordinates. Two
consequences worth being explicit about:

* Tiles must be *paired* before matching. Two rasters at the same GSD over the
  same ground do not share pixel origins, so the reference window is located
  from an approximate prior (footprint geometry, or a coarse whole-image
  alignment) rather than by reusing the source tile's offsets.
* Per-tile caps bound count skew, but they are not a uniformity fix. Capping
  stops one high-texture tile over a crater field from contributing thousands
  of matches while its neighbours contribute dozens. It cannot conjure matches
  where the terrain has no texture, so a smooth mare region stays empty either
  way -- measured on synthetic scenes, capping improves the uniformity score
  only when the tile grid is at least as fine as the evaluation grid, and it
  always costs total match count. Treat tiling as a memory strategy whose
  uniformity benefit is real but conditional; see
  :mod:`lunar_reg.eval.uniformity` for the measurement.
"""

from __future__ import annotations

import logging

import numpy as np
from tqdm import tqdm

from lunar_reg.ingest.tiling import Tile, plan_tiles
from lunar_reg.match.base import MatchResult
from lunar_reg.match.stitch import DEFAULT_TOLERANCE_PX, edge_distance, stitch_tiles

logger = logging.getLogger(__name__)

#: Matches kept per tile. Chosen so a 6x6 tile grid yields a few thousand
#: correspondences, ample for a homography or a low-order polynomial fit.
#: Lowering it evens out the per-cell distribution at the cost of total count.
DEFAULT_MAX_MATCHES_PER_TILE = 256


class TiledMatcher:
    """Runs an inner matcher over paired tiles and merges into parent coordinates.

    ``matcher`` is any object satisfying :class:`~lunar_reg.match.base.Matcher`.
    ``tile_px`` defaults to the inner matcher's own VRAM-derived limit when it
    advertises one.
    """

    def __init__(
        self,
        matcher,
        tile_px: int | None = None,
        overlap: float = 0.25,
        max_matches_per_tile: int = DEFAULT_MAX_MATCHES_PER_TILE,
        progress: bool = True,
        deduplicate_overlaps: bool = True,
        tolerance_px: float = DEFAULT_TOLERANCE_PX,
    ) -> None:
        self.matcher = matcher
        self.tile_px = tile_px or getattr(matcher, "max_tile_px", 640)
        self.overlap = overlap
        self.max_matches_per_tile = max_matches_per_tile
        self.progress = progress
        self.deduplicate_overlaps = deduplicate_overlaps
        self.tolerance_px = tolerance_px
        self.name = f"tiled({getattr(matcher, 'name', 'unknown')})"
        #: Populated by the last call to :meth:`match_arrays` or
        #: :meth:`match_datasets`, so callers can report how much of the raw
        #: match count was overlap duplication.
        self.last_stats = None

    def _cap(self, result: MatchResult) -> MatchResult:
        """Keep at most ``max_matches_per_tile``, preferring higher scores."""
        if len(result) <= self.max_matches_per_tile:
            return result
        if result.scores is not None:
            keep = np.argsort(result.scores)[::-1][: self.max_matches_per_tile]
        else:
            keep = np.random.default_rng(0).choice(
                len(result), self.max_matches_per_tile, replace=False
            )
        return MatchResult(
            src_pts=result.src_pts[keep],
            dst_pts=result.dst_pts[keep],
            scores=None if result.scores is None else result.scores[keep],
            matcher=result.matcher,
        )

    def match_arrays(
        self,
        source: np.ndarray,
        reference: np.ndarray,
        offset_prior: tuple[int, int] = (0, 0),
    ) -> MatchResult:
        """Tile two in-memory arrays and match them.

        ``offset_prior`` is the approximate ``(row, col)`` shift of the
        reference relative to the source, used to place the paired reference
        window. A prior good to roughly half a tile is enough; beyond that the
        paired windows stop overlapping and tiles return nothing.

        Suitable for arrays that already fit in host RAM. For full products use
        :meth:`match_datasets`, which never materialises either raster.
        """
        tiles = plan_tiles(*source.shape[:2], tile_px=self.tile_px, overlap=self.overlap)
        ref_h, ref_w = reference.shape[:2]
        results: list[MatchResult] = []
        priorities: list = []

        for tile in tqdm(tiles, desc=self.name, disable=not self.progress):
            src_patch = source[
                tile.row_off : tile.row_off + tile.height,
                tile.col_off : tile.col_off + tile.width,
            ]
            ref_tile = self._paired_tile(tile, offset_prior, ref_h, ref_w)
            if ref_tile is None:
                continue
            ref_patch = reference[
                ref_tile.row_off : ref_tile.row_off + ref_tile.height,
                ref_tile.col_off : ref_tile.col_off + ref_tile.width,
            ]

            try:
                res = self.matcher.match(src_patch, ref_patch)
            except Exception as exc:  # noqa: BLE001 - one bad tile must not kill the run
                logger.warning("tile %s failed: %s", tile.index, exc)
                continue

            if not len(res):
                continue
            res = self._cap(res)
            # Priority for overlap deduplication: how far inside its tile the
            # match sat. A copy from deeper inside a tile had fuller descriptor
            # support, so it is the better measurement of the same feature.
            priorities.append(edge_distance(res.src_pts, tile.height, tile.width))
            results.append(
                MatchResult(
                    src_pts=tile.to_parent(res.src_pts),
                    dst_pts=ref_tile.to_parent(res.dst_pts),
                    scores=res.scores,
                    matcher=res.matcher,
                )
            )

        merged, stats = stitch_tiles(
            results, priorities, self.tolerance_px, self.name, self.deduplicate_overlaps
        )
        self.last_stats = stats
        logger.info(
            "%s: %d matches from %d/%d tiles", self.name, len(merged), len(results), len(tiles)
        )
        return merged

    def match_datasets(
        self,
        src_dataset,
        ref_dataset,
        offset_prior: tuple[int, int] = (0, 0),
        preprocess=None,
    ) -> MatchResult:
        """Match two open rasterio datasets using windowed reads.

        Peak memory is two tiles, independent of product size -- this is the
        path to use for OHRC. ``preprocess`` is applied per tile; pass
        :func:`lunar_reg.preprocess.standard_chain` for the validated default.
        """
        tiles = plan_tiles(
            src_dataset.height, src_dataset.width, tile_px=self.tile_px, overlap=self.overlap
        )
        results: list[MatchResult] = []
        priorities: list = []

        for tile in tqdm(tiles, desc=self.name, disable=not self.progress):
            ref_tile = self._paired_tile(tile, offset_prior, ref_dataset.height, ref_dataset.width)
            if ref_tile is None:
                continue

            src_patch = src_dataset.read(1, window=tile.window)
            ref_patch = ref_dataset.read(1, window=ref_tile.window)
            if preprocess is not None:
                src_patch = preprocess(src_patch)
                ref_patch = preprocess(ref_patch)

            try:
                res = self.matcher.match(src_patch, ref_patch)
            except Exception as exc:  # noqa: BLE001
                logger.warning("tile %s failed: %s", tile.index, exc)
                continue

            if not len(res):
                continue
            res = self._cap(res)
            # Priority for overlap deduplication: how far inside its tile the
            # match sat. A copy from deeper inside a tile had fuller descriptor
            # support, so it is the better measurement of the same feature.
            priorities.append(edge_distance(res.src_pts, tile.height, tile.width))
            results.append(
                MatchResult(
                    src_pts=tile.to_parent(res.src_pts),
                    dst_pts=ref_tile.to_parent(res.dst_pts),
                    scores=res.scores,
                    matcher=res.matcher,
                )
            )

        merged, stats = stitch_tiles(
            results, priorities, self.tolerance_px, self.name, self.deduplicate_overlaps
        )
        self.last_stats = stats
        logger.info(
            "%s: %d matches from %d/%d tiles", self.name, len(merged), len(results), len(tiles)
        )
        return merged

    @staticmethod
    def _paired_tile(
        tile: Tile, offset_prior: tuple[int, int], ref_h: int, ref_w: int
    ) -> Tile | None:
        """Locate the reference window corresponding to a source tile.

        Returns ``None`` when the prior places the window outside the reference,
        which is normal near the edges of a partial overlap.
        """
        row = tile.row_off + offset_prior[0]
        col = tile.col_off + offset_prior[1]
        if row + tile.height <= 0 or col + tile.width <= 0 or row >= ref_h or col >= ref_w:
            return None
        row = max(0, min(row, ref_h - tile.height)) if ref_h >= tile.height else 0
        col = max(0, min(col, ref_w - tile.width)) if ref_w >= tile.width else 0
        return Tile(
            row_off=row,
            col_off=col,
            height=min(tile.height, ref_h),
            width=min(tile.width, ref_w),
            index=tile.index,
        )
