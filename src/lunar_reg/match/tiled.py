"""Tile-wise matching orchestration.

VRAM CONSTRAINT: this is the component that makes OHRC tractable.

Whole-image matching is impossible on 8 GB for a full strip, so the pipeline
matches tile against tile and merges the results in parent coordinates. Three
consequences worth being explicit about:

* Tiles must be *paired* before matching. Two rasters over the same ground do
  not share pixel origins, scale or orientation, so each reference patch is
  located *and rectified* through an approximate 3x3 prior (footprint geometry,
  or a coarse whole-image alignment) that maps source px to reference px. The
  rectified patch is at the source tile's scale and orientation, so the inner
  matcher sees a near-identity pair whatever the true scale and rotation are
  (AUDIT A079).
* Every tile gets a classified :class:`TileStatus` -- matched, empty, outside
  the reference, skipped for nodata, matcher error, or out of memory -- counted
  in :class:`TileDiagnostics` (AUDIT A078). A tile that fails is never dropped
  silently; the caller prints :meth:`TileDiagnostics.report`.
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
import math
import sys
from dataclasses import dataclass, field
from enum import Enum

import cv2
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

#: Tile side used when neither ``tile_px`` nor the matcher's ``max_tile_px`` is given.
DEFAULT_TILE_PX = 640

#: Smallest tile side derived from a matcher's ``max_tile_px`` minus the margins.
MIN_DERIVED_TILE_PX = 64

#: Longest sample text in :meth:`TileDiagnostics.report` (classified-outcomes skill).
_SAMPLE_CHARS = 200


class TileStatus(str, Enum):
    """What happened to one source tile (C18)."""

    OK = "ok"
    #: The matcher ran and found nothing -- a non-result, not a failure.
    EMPTY = "empty"
    #: The prior maps the tile entirely outside the reference -- a data gap.
    OUT_OF_REFERENCE = "out_of_reference"
    #: Too little valid data in the source tile or the rectified reference patch.
    SKIPPED_NODATA = "skipped_nodata"
    #: The matcher raised something other than an out-of-memory error.
    MATCHER_ERROR = "matcher_error"
    #: ``torch.OutOfMemoryError`` while matching the tile.
    OOM = "oom"

    @property
    def is_failure(self) -> bool:
        """True for outcomes where the matcher itself broke (not data gaps or empty tiles)."""
        return self in (TileStatus.MATCHER_ERROR, TileStatus.OOM)


#: How :meth:`TileDiagnostics.report` describes each status in words, so a data
#: gap is never mistaken for a matcher that found nothing (skill: data gap vs bug).
_STATUS_WORDS = {
    TileStatus.OK: "matched",
    TileStatus.EMPTY: "matcher ran, found nothing",
    TileStatus.OUT_OF_REFERENCE: "data gap: prior maps the tile outside the reference",
    TileStatus.SKIPPED_NODATA: "data gap: valid fraction below min_valid_fraction",
    TileStatus.MATCHER_ERROR: "FAILURE: matcher raised",
    TileStatus.OOM: "FAILURE: out of memory",
}


@dataclass
class TileOutcome:
    """One tile's classified outcome (C18).

    ``source_window`` and ``reference_window`` are ``(row_off, col_off, height,
    width)`` in source and reference px; ``reference_window`` is ``None`` when
    the prior maps the tile outside the reference.
    """

    index: int
    status: TileStatus
    n_matches: int
    detail: str
    source_window: tuple[int, int, int, int]
    reference_window: tuple[int, int, int, int] | None


@dataclass
class TileDiagnostics:
    """Every tile's outcome, with per-status counts and the first sample of each (C18)."""

    outcomes: list[TileOutcome] = field(default_factory=list)

    def record(self, outcome: TileOutcome) -> None:
        self.outcomes.append(outcome)

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for o in self.outcomes:
            out[o.status.value] = out.get(o.status.value, 0) + 1
        return out

    @property
    def samples(self) -> dict[str, TileOutcome]:
        out: dict[str, TileOutcome] = {}
        for o in self.outcomes:
            out.setdefault(o.status.value, o)
        return out

    @property
    def n_failed(self) -> int:
        return sum(1 for o in self.outcomes if o.status.is_failure)

    def report(self) -> str:
        """One header line, then one line per status (sorted) with its first sample."""
        counts = self.counts
        samples = self.samples
        lines = [
            f"tiles: {len(self.outcomes)} total, {counts.get(TileStatus.OK.value, 0)} ok, "
            f"{self.n_failed} failed"
        ]
        for value in sorted(counts):
            status = TileStatus(value)
            first = samples[value]
            sample = f"tile {first.index}: {first.detail or status.value}"[:_SAMPLE_CHARS]
            lines.append(f"  {value}: {counts[value]}  ({_STATUS_WORDS[status]})  e.g. {sample}")
        return "\n".join(lines)


def _translation(col: float, row: float) -> np.ndarray:
    return np.array([[1.0, 0.0, col], [0.0, 1.0, row], [0.0, 0.0, 1.0]])


def _apply_h(h: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply a 3x3 transform projectively to ``(N, 2)`` ``(x, y)`` points in float64."""
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    hom = np.c_[pts, np.ones(len(pts))] @ np.asarray(h, dtype=np.float64).T
    return hom[:, :2] / hom[:, 2:3]


def _oom_types() -> tuple[type[BaseException], ...]:
    """``(torch.OutOfMemoryError,)`` when torch is loaded, else ``()``.

    Evaluated when an exception reaches the ``except`` clause, not before the
    matcher runs: a matcher that imports torch lazily inside ``match()`` can
    raise its OOM on the very first tile. CPU-only callers (classical
    matchers) never pay for importing torch here.
    """
    torch = sys.modules.get("torch")
    oom = getattr(torch, "OutOfMemoryError", None) if torch is not None else None
    return (oom,) if oom is not None else ()


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip().splitlines()
    return (text[0] if text else type(exc).__name__)[:_SAMPLE_CHARS]


def _valid_fraction(valid: np.ndarray) -> float:
    return float(np.count_nonzero(valid)) / valid.size if valid.size else 0.0


def _default_valid(patch: np.ndarray) -> np.ndarray:
    """The C18 default validity rule: ``patch > 0`` (any band for a multi-band patch)."""
    valid = np.asarray(patch) > 0
    return valid.any(axis=-1) if valid.ndim == 3 else valid


def _warpable(image: np.ndarray) -> np.ndarray:
    """``image`` in a dtype ``cv2.warpPerspective`` accepts (bool/int32/int64 -> float32)."""
    if image.dtype in (np.uint8, np.uint16, np.int16, np.float32, np.float64):
        return image
    return image.astype(np.float32)


class TiledMatcher:
    """Runs an inner matcher over prior-rectified tile pairs and merges into parent coordinates.

    ``matcher`` is any object satisfying :class:`~lunar_reg.match.base.Matcher`.
    ``tile_px`` defaults to the inner matcher's own VRAM-derived limit minus the
    two rectification margins (the rectified reference patch is
    ``tile_px + 2 * ref_margin_px`` on a side and must fit the same limit), or
    to :data:`DEFAULT_TILE_PX` when the matcher advertises no limit.
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
        min_valid_fraction: float = 0.5,
        ref_margin_px: int = 32,
    ) -> None:
        if ref_margin_px < 0:
            raise ValueError(f"ref_margin_px must be >= 0, got {ref_margin_px}")
        if not 0.0 <= min_valid_fraction <= 1.0:
            raise ValueError(f"min_valid_fraction must be in [0, 1], got {min_valid_fraction}")
        self.matcher = matcher
        if tile_px:
            self.tile_px = tile_px
        else:
            limit = getattr(matcher, "max_tile_px", None)
            self.tile_px = (
                max(MIN_DERIVED_TILE_PX, int(limit) - 2 * ref_margin_px)
                if limit
                else DEFAULT_TILE_PX
            )
        self.overlap = overlap
        self.max_matches_per_tile = max_matches_per_tile
        self.progress = progress
        self.deduplicate_overlaps = deduplicate_overlaps
        self.tolerance_px = tolerance_px
        self.min_valid_fraction = min_valid_fraction
        self.ref_margin_px = ref_margin_px
        self.name = f"tiled({getattr(matcher, 'name', 'unknown')})"
        #: Populated by the last call to :meth:`match_arrays` or
        #: :meth:`match_datasets`, so callers can report how much of the raw
        #: match count was overlap duplication.
        self.last_stats = None
        #: Per-tile outcomes of the last call; the caller prints its ``report()``.
        self.last_diagnostics: TileDiagnostics | None = None

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

    # ------------------------------------------------------------------ prior

    @staticmethod
    def _resolve_prior(
        prior: np.ndarray | None, offset_prior: tuple[int, int] | None
    ) -> np.ndarray:
        """The 3x3 source px -> reference px prior; identity when neither is given."""
        if prior is not None and offset_prior is not None:
            raise ValueError("pass either prior or offset_prior, not both")
        if offset_prior is not None:
            row, col = offset_prior
            return _translation(float(col), float(row))
        if prior is None:
            return np.eye(3)
        prior = np.asarray(prior, dtype=np.float64)
        if prior.shape != (3, 3) or not np.all(np.isfinite(prior)):
            raise ValueError(f"prior must be a finite 3x3 matrix, got shape {prior.shape}")
        return prior

    def _rectifier(self, tile: Tile, prior: np.ndarray) -> np.ndarray:
        """``T_t``: rectified-patch px -> reference px (LLD §P2.06 step 2)."""
        m = self.ref_margin_px
        return prior @ _translation(tile.col_off - m, tile.row_off - m)

    @staticmethod
    def _bbox(
        points: np.ndarray, pad: float, ref_h: int, ref_w: int
    ) -> tuple[int, int, int, int] | None:
        """Clipped ``(row_off, col_off, height, width)`` bounding box of ``points`` ± ``pad``."""
        if not np.all(np.isfinite(points)):
            return None
        c0 = max(0, math.floor(points[:, 0].min() - pad))
        r0 = max(0, math.floor(points[:, 1].min() - pad))
        c1 = min(ref_w, math.ceil(points[:, 0].max() + pad))
        r1 = min(ref_h, math.ceil(points[:, 1].max() + pad))
        if c1 <= c0 or r1 <= r0:
            return None
        return (r0, c0, r1 - r0, c1 - c0)

    def _reference_window(
        self, tile: Tile, prior: np.ndarray, ref_h: int, ref_w: int
    ) -> tuple[int, int, int, int] | None:
        """C18 reference window: bbox of the prior-mapped tile corners ± ``ref_margin_px``."""
        x0, y0 = tile.col_off, tile.row_off
        x1, y1 = x0 + tile.width, y0 + tile.height
        corners = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64)
        hom = np.c_[corners, np.ones(4)] @ prior.T
        if np.any(hom[:, 2] <= 0):
            # Part of the tile maps through the prior's horizon: not a window.
            return None
        return self._bbox(hom[:, :2] / hom[:, 2:3], self.ref_margin_px, ref_h, ref_w)

    def _read_window(
        self,
        tile: Tile,
        t_t: np.ndarray,
        ref_window: tuple[int, int, int, int],
        ref_h: int,
        ref_w: int,
    ) -> tuple[int, int, int, int]:
        """Reference window to read for rectification (windowed-read path).

        The C18 window covers the tile corners; the rectified patch also covers
        the source-px margin, which at a reference finer than the source maps
        wider. Reading the union of both (plus 2 px for interpolation) makes
        the windowed rectification sample the same pixels as a full-raster one.
        """
        m = self.ref_margin_px
        pw, ph = tile.width + 2 * m, tile.height + 2 * m
        corners = np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], dtype=np.float64)
        patch_box = self._bbox(_apply_h(t_t, corners), 2.0, ref_h, ref_w)
        if patch_box is None:
            return ref_window
        r0 = min(ref_window[0], patch_box[0])
        c0 = min(ref_window[1], patch_box[1])
        r1 = max(ref_window[0] + ref_window[2], patch_box[0] + patch_box[2])
        c1 = max(ref_window[1] + ref_window[3], patch_box[1] + patch_box[3])
        return (r0, c0, r1 - r0, c1 - c0)

    # -------------------------------------------------------------- per tile

    def _match_tile(
        self,
        number: int,
        tile: Tile,
        src_patch: np.ndarray,
        src_valid: np.ndarray,
        ref_image: np.ndarray,
        ref_valid_u8: np.ndarray,
        ref_origin: tuple[int, int],
        t_t: np.ndarray,
        ref_window: tuple[int, int, int, int],
    ) -> tuple[TileOutcome, MatchResult | None, np.ndarray | None]:
        """Rectify, validity-check, match, cap and lift one tile (LLD §P2.06 steps 2-5).

        ``ref_image``/``ref_valid_u8`` are a window of the reference (sliced or
        read) whose top-left reference px is ``ref_origin = (row, col)``.
        Returns the outcome, the lifted result (``None`` unless OK) and its
        deduplication priorities.
        """
        src_window = (tile.row_off, tile.col_off, tile.height, tile.width)
        m = self.ref_margin_px
        size = (tile.width + 2 * m, tile.height + 2 * m)

        def outcome(status: TileStatus, n: int = 0, detail: str = "") -> TileOutcome:
            return TileOutcome(number, status, n, detail, src_window, ref_window)

        src_fraction = _valid_fraction(src_valid)
        if src_fraction < self.min_valid_fraction:
            return (
                outcome(TileStatus.SKIPPED_NODATA, detail=f"source valid {src_fraction:.2f}"),
                None,
                None,
            )

        # Rectified-patch px -> px of the array actually held (window or full).
        local = _translation(-ref_origin[1], -ref_origin[0]) @ t_t
        flags = cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP
        rectified = cv2.warpPerspective(
            _warpable(ref_image), local, size, flags=flags, borderValue=0
        )
        rect_valid = cv2.warpPerspective(
            ref_valid_u8,
            local,
            size,
            flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP,
            borderValue=0,
        )
        ref_fraction = _valid_fraction(rect_valid)
        if ref_fraction < self.min_valid_fraction:
            return (
                outcome(TileStatus.SKIPPED_NODATA, detail=f"reference valid {ref_fraction:.2f}"),
                None,
                None,
            )

        oom_detail = None
        try:
            res = self.matcher.match(src_patch, rectified)
        except _oom_types() as exc:  # caught before RuntimeError, which it subclasses
            oom_detail = _first_line(exc)
        except Exception as exc:  # noqa: BLE001 - a matcher can raise anything; one bad tile must not kill the run
            detail = f"{type(exc).__name__}: {_first_line(exc)}"
            return outcome(TileStatus.MATCHER_ERROR, detail=detail), None, None
        if oom_detail is not None:
            # Outside the except clause: the traceback, and the tensors its
            # frames hold, are released by now, so the cache can be returned.
            sys.modules["torch"].cuda.empty_cache()
            return outcome(TileStatus.OOM, detail=oom_detail), None, None

        if not len(res):
            return outcome(TileStatus.EMPTY), None, None
        n_raw = len(res)
        res = self._cap(res)
        # Priority for overlap deduplication: how far inside its tile the
        # match sat. A copy from deeper inside a tile had fuller descriptor
        # support, so it is the better measurement of the same feature.
        priority = edge_distance(res.src_pts, tile.height, tile.width)
        lifted = MatchResult(
            src_pts=tile.to_parent(res.src_pts),
            dst_pts=_apply_h(t_t, res.dst_pts),
            scores=res.scores,
            matcher=res.matcher,
        )
        detail = f"capped from {n_raw}" if n_raw > len(res) else ""
        return outcome(TileStatus.OK, len(res), detail), lifted, priority

    def _finish(
        self,
        results: list[MatchResult],
        priorities: list[np.ndarray],
        diagnostics: TileDiagnostics,
    ) -> MatchResult:
        merged, stats = stitch_tiles(
            results, priorities, self.tolerance_px, self.name, self.deduplicate_overlaps
        )
        self.last_stats = stats
        self.last_diagnostics = diagnostics
        counts = ", ".join(f"{k}={v}" for k, v in sorted(diagnostics.counts.items()))
        log = logger.warning if diagnostics.n_failed else logger.info
        log(
            "%s: %d matches from %d/%d tiles (%s)",
            self.name,
            len(merged),
            len(results),
            len(diagnostics.outcomes),
            counts,
        )
        return merged

    # ------------------------------------------------------------- entry points

    def match_arrays(
        self,
        source: np.ndarray,
        reference: np.ndarray,
        prior: np.ndarray | None = None,
        source_valid: np.ndarray | None = None,
        reference_valid: np.ndarray | None = None,
        offset_prior: tuple[int, int] | None = None,
    ) -> MatchResult:
        """Tile two in-memory arrays and match them through a prior (C18).

        ``prior`` maps source px -> reference px (3x3, ``(x, y)`` order);
        ``offset_prior=(row, col)`` is shorthand for a translation prior; with
        neither the prior is the identity. The prior only has to be good to a
        fraction of ``ref_margin_px``: each reference patch is rectified into
        the source tile's frame, so scale and rotation are taken out before
        the inner matcher runs.

        ``source_valid``/``reference_valid`` are boolean masks the size of
        their images; the default is ``image > 0``. Tiles whose valid fraction
        (source tile or rectified reference patch) is below
        ``min_valid_fraction`` are ``SKIPPED_NODATA``.

        Suitable for arrays that already fit in host RAM. For full products use
        :meth:`match_datasets`, which never materialises either raster.
        """
        prior = self._resolve_prior(prior, offset_prior)
        tiles = plan_tiles(*source.shape[:2], tile_px=self.tile_px, overlap=self.overlap)
        ref_h, ref_w = reference.shape[:2]
        if source_valid is not None and source_valid.shape[:2] != source.shape[:2]:
            raise ValueError("source_valid must have the source's shape")
        if reference_valid is not None and reference_valid.shape[:2] != (ref_h, ref_w):
            raise ValueError("reference_valid must have the reference's shape")

        diagnostics = TileDiagnostics(outcomes=[])
        results: list[MatchResult] = []
        priorities: list[np.ndarray] = []

        for number, tile in enumerate(tqdm(tiles, desc=self.name, disable=not self.progress)):
            rows = slice(tile.row_off, tile.row_off + tile.height)
            cols = slice(tile.col_off, tile.col_off + tile.width)
            ref_window = self._reference_window(tile, prior, ref_h, ref_w)
            if ref_window is None:
                diagnostics.record(
                    TileOutcome(
                        number,
                        TileStatus.OUT_OF_REFERENCE,
                        0,
                        "prior maps the tile outside the reference",
                        (tile.row_off, tile.col_off, tile.height, tile.width),
                        None,
                    )
                )
                continue
            src_patch = source[rows, cols]
            src_valid = (
                _default_valid(src_patch) if source_valid is None else source_valid[rows, cols]
            )
            # Same reference window as match_datasets reads: every warp source
            # stays tile-sized, so a reference side >= 32767 px (cv2.remap's
            # SHRT_MAX limit) never reaches warpPerspective whole.
            t_t = self._rectifier(tile, prior)
            r0, c0, h, w = self._read_window(tile, t_t, ref_window, ref_h, ref_w)
            ref_patch = reference[r0 : r0 + h, c0 : c0 + w]
            ref_valid = (
                _default_valid(ref_patch)
                if reference_valid is None
                else reference_valid[r0 : r0 + h, c0 : c0 + w]
            )
            outcome, lifted, priority = self._match_tile(
                number,
                tile,
                src_patch,
                src_valid,
                ref_patch,
                ref_valid.astype(np.uint8),
                (r0, c0),
                t_t,
                ref_window,
            )
            diagnostics.record(outcome)
            if lifted is not None:
                results.append(lifted)
                priorities.append(priority)

        return self._finish(results, priorities, diagnostics)

    def match_datasets(
        self,
        src_dataset,
        ref_dataset,
        prior: np.ndarray | None = None,
        offset_prior: tuple[int, int] | None = None,
        preprocess=None,
    ) -> MatchResult:
        """Match two open rasterio datasets using windowed reads.

        Same per-tile routine as :meth:`match_arrays`. Each source tile is one
        windowed read; each reference read covers only the tile's reference
        window (and the rectified patch's footprint), never the whole raster,
        so peak memory is independent of product size -- this is the path to
        use for OHRC.

        Band 1 is read with ``masked=True``: valid pixels are unmasked and
        ``> 0`` (AUDIT A128). Masked pixels are set to 0 before ``preprocess``,
        which is applied per tile (source tile and reference window); pass
        :func:`lunar_reg.preprocess.standard_chain` for the validated default.
        """
        prior = self._resolve_prior(prior, offset_prior)
        tiles = plan_tiles(
            src_dataset.height, src_dataset.width, tile_px=self.tile_px, overlap=self.overlap
        )
        ref_h, ref_w = ref_dataset.height, ref_dataset.width

        diagnostics = TileDiagnostics(outcomes=[])
        results: list[MatchResult] = []
        priorities: list[np.ndarray] = []

        for number, tile in enumerate(tqdm(tiles, desc=self.name, disable=not self.progress)):
            ref_window = self._reference_window(tile, prior, ref_h, ref_w)
            if ref_window is None:
                diagnostics.record(
                    TileOutcome(
                        number,
                        TileStatus.OUT_OF_REFERENCE,
                        0,
                        "prior maps the tile outside the reference",
                        (tile.row_off, tile.col_off, tile.height, tile.width),
                        None,
                    )
                )
                continue
            t_t = self._rectifier(tile, prior)
            read = self._read_window(tile, t_t, ref_window, ref_h, ref_w)
            read_tile = Tile(row_off=read[0], col_off=read[1], height=read[2], width=read[3])

            src_patch, src_valid = _read_valid(src_dataset, tile)
            ref_patch, ref_valid = _read_valid(ref_dataset, read_tile)
            if preprocess is not None:
                src_patch = preprocess(src_patch)
                ref_patch = preprocess(ref_patch)

            outcome, lifted, priority = self._match_tile(
                number,
                tile,
                src_patch,
                src_valid,
                ref_patch,
                ref_valid.astype(np.uint8),
                (read[0], read[1]),
                t_t,
                ref_window,
            )
            diagnostics.record(outcome)
            if lifted is not None:
                results.append(lifted)
                priorities.append(priority)

        return self._finish(results, priorities, diagnostics)


def _read_valid(dataset, tile: Tile) -> tuple[np.ndarray, np.ndarray]:
    """Band 1 of ``dataset`` over ``tile`` with masked pixels zeroed, and its validity mask."""
    data = dataset.read(1, window=tile.window, masked=True)
    masked = np.ma.getmaskarray(data)
    filled = np.ma.filled(data, 0)
    with np.errstate(invalid="ignore"):
        valid = ~masked & (filled > 0)
    return filled, valid
