"""Native-GSD refinement of a coarse registration (CONTRACTS C19, DECISIONS G10).

The coarse pass registers both images at a working GSD (4 m by default). This
module refines that solution at the *reference's* native GSD -- 1 m for the LRO
NAC ortho -- and re-expresses the result in *source*-native pixels (0.25 m for
OHRC). The source window is resampled down to the reference GSD; the reference
is never upsampled, because it holds no detail finer than its own pixels and
matching against an upsampled copy adds compute, not information (G10).

Steps (``Phase_2/LLD/native.md`` §P2.08):

1. ``f = reference_native_gsd_m / source_native_gsd_m``; resample the source by
   ``1/f`` with ``INTER_AREA``. ``S`` maps source-native px -> resampled px
   (the inverse of the CONTRACTS C11 pixel-centre ``to_native`` matrix). A
   resampled cell is valid only when every native pixel under it is valid, so
   averaging with nodata never produces a valid half-intensity collar.
2. Prior at matching scale: ``P = prior_native @ inv(S)``.
3. Tile-by-tile matching through ``P`` (:class:`~lunar_reg.match.tiled.TiledMatcher`).
4. Robust fit at 3 px, then a refit on inliers at 1 px.
5. ``T_native = T_fit @ S``: source-native px -> reference-native px.
6. Drift against the coarse prior on a 5x5 probe grid, in coarse px.
7. Tile-failure rule. When the fit cannot run (too few matches) or fails,
   and more than half the tiles failed in the matcher, the outcome is
   ``TILE_FAILURES`` (transform ``None``): the matcher, not the data, is the
   cause.

Every outcome is a :class:`NativeStatus`; nothing raises for a bad input pair
(only for programmer error such as a wrong array rank). Callers print
:meth:`NativeRefinement.report` -- or :meth:`NativeDiagnostics.report` for a
batch -- on every run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from lunar_reg.align.estimate import TRANSFORM_MODELS, estimate_transform
from lunar_reg.align.refine import reestimate_on_inliers
from lunar_reg.match import build_matcher
from lunar_reg.match.tiled import TileDiagnostics, TiledMatcher
from lunar_reg.provenance import Sourced, ValueSource

logger = logging.getLogger(__name__)

#: Fewest merged matches worth fitting at native GSD.
MIN_MATCHES = Sourced(8, ValueSource.INFERRED, "Phase_2/LLD/native.md §P2.08 step 4")
#: First robust fit threshold, in reference-native px.
FIT_THRESHOLD_PX = Sourced(3.0, ValueSource.INFERRED, "Phase_2/LLD/native.md §P2.08 step 4")
#: Inlier refit threshold, in reference-native px.
REFIT_THRESHOLD_PX = Sourced(1.0, ValueSource.INFERRED, "Phase_2/LLD/native.md §P2.08 step 4")
#: Tile side used when the caller passes ``tile_px=None``.
DEFAULT_NATIVE_TILE_PX = Sourced(512, ValueSource.INFERRED, "Phase_2/LLD/native.md §P2.08 step 3")
#: Fraction of failed tiles above which the result is ``TILE_FAILURES``.
MAX_FAILED_TILE_FRACTION = Sourced(0.5, ValueSource.INFERRED, "Phase_2/LLD/native.md §P2.08 step 7")
#: Probe grid side (probes = PROBE_GRID x PROBE_GRID over the source window).
PROBE_GRID = 5

#: Provenance of each numeric output of :class:`NativeRefinement`.
_OUTPUT_PROVENANCE = {
    "transform": ValueSource.COMPUTED.value,
    "n_matches": ValueSource.MEASURED.value,
    "n_inliers": ValueSource.MEASURED.value,
    "drift_coarse_px": ValueSource.COMPUTED.value,
}

_SAMPLE_CHARS = 200


class NativeStatus(str, Enum):
    """What happened to one native-GSD refinement (C19)."""

    OK = "ok"
    #: Fewer than :data:`MIN_MATCHES` merged matches -- nothing to fit.
    TOO_FEW_MATCHES = "too_few_matches"
    #: The robust fit or the inlier refit raised ``ValueError`` or gave a non-finite matrix.
    ESTIMATION_FAILED = "estimation_failed"
    #: The refined transform moved further than ``max_drift_coarse_px`` from the prior.
    DRIFT_EXCEEDED = "drift_exceeded"
    #: More than half the tiles failed (matcher error or out of memory). The
    #: transform is ``None`` when the failures left too little to fit.
    TILE_FAILURES = "tile_failures"

    @property
    def is_failure(self) -> bool:
        return self is not NativeStatus.OK


#: How :meth:`NativeDiagnostics.report` describes each status in words.
_STATUS_WORDS = {
    NativeStatus.OK: "refined",
    NativeStatus.TOO_FEW_MATCHES: "too few correspondences (detail says: data gap or none found)",
    NativeStatus.ESTIMATION_FAILED: "FAILURE: transform fit failed",
    NativeStatus.DRIFT_EXCEEDED: "FAILURE: refined transform drifted from the coarse prior",
    NativeStatus.TILE_FAILURES: "FAILURE: most tiles failed in the matcher (error or OOM)",
}


@dataclass
class NativeRefinement:
    """The outcome of :func:`refine_native_arrays` (C19).

    ``transform`` maps source-native px -> reference-native px; it is ``None``
    for ``TOO_FEW_MATCHES`` and ``ESTIMATION_FAILED`` (and for ``TILE_FAILURES``
    when the failed tiles left nothing to fit) and is kept for
    ``DRIFT_EXCEEDED`` and ``TILE_FAILURES`` after a fit so it can be inspected.
    """

    status: NativeStatus
    transform: np.ndarray | None
    n_matches: int
    n_inliers: int
    drift_coarse_px: float | None
    tiles: TileDiagnostics | None
    detail: str

    @property
    def provenance(self) -> dict[str, str]:
        """Quantity -> :class:`~lunar_reg.provenance.ValueSource` value for each numeric output."""
        return dict(_OUTPUT_PROVENANCE)

    def report(self) -> str:
        """One summary line, then the tile report when tiles were matched."""
        drift = "n/a" if self.drift_coarse_px is None else f"{self.drift_coarse_px:.3f}"
        line = (
            f"native refinement: {self.status.value} ({_STATUS_WORDS[self.status]}); "
            f"matches {self.n_matches}, inliers {self.n_inliers}, drift {drift} coarse px"
        )
        if self.detail:
            line += f"; {self.detail}"
        if self.tiles is None:
            return line
        return line + "\n" + self.tiles.report()


@dataclass
class NativeDiagnostics:
    """Per-status counts and the first sample across many refinements (classified outcomes)."""

    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)

    def record(self, item_id: str, outcome: NativeRefinement) -> None:
        value = outcome.status.value
        self.counts[value] = self.counts.get(value, 0) + 1
        self.samples.setdefault(value, f"{item_id}: {outcome.detail or value}"[:_SAMPLE_CHARS])

    def report(self) -> str:
        total = sum(self.counts.values())
        n_ok = self.counts.get(NativeStatus.OK.value, 0)
        lines = [f"native refinements: {total} total, {n_ok} ok, {total - n_ok} failed"]
        for value in sorted(self.counts):
            words = _STATUS_WORDS[NativeStatus(value)]
            lines.append(f"  {value}: {self.counts[value]}  ({words})  e.g. {self.samples[value]}")
        return "\n".join(lines)


# --------------------------------------------------------------------- helpers


def _as_3x3(matrix: np.ndarray, name: str) -> np.ndarray:
    """A float64 3x3 copy; a 2x3 affine is promoted with ``[0, 0, 1]``."""
    m = np.asarray(matrix, dtype=np.float64)
    if m.shape == (2, 3):
        m = np.vstack([m, [0.0, 0.0, 1.0]])
    if m.shape != (3, 3):
        raise ValueError(f"{name} must be 3x3 or 2x3, got shape {m.shape}")
    return m


def _apply(h: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply a 3x3 transform projectively to ``(N, 2)`` ``(x, y)`` points."""
    hom = np.c_[pts, np.ones(len(pts))] @ h.T
    return hom[:, :2] / hom[:, 2:3]


def _native_to_resampled(native_wh: tuple[int, int], resampled_wh: tuple[int, int]) -> np.ndarray:
    """``S``: native px -> resampled px, the inverse of the C11 pixel-centre ``to_native``."""
    fx = native_wh[0] / resampled_wh[0]
    fy = native_wh[1] / resampled_wh[1]
    to_native = np.array(
        [[fx, 0.0, (fx - 1) / 2], [0.0, fy, (fy - 1) / 2], [0.0, 0.0, 1.0]], dtype=np.float64
    )
    return np.linalg.inv(to_native)


def _resample_source(
    source_native: np.ndarray, size_wh: tuple[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    """``INTER_AREA`` image and full-support validity mask at ``size_wh``.

    Native validity is the C18 default rule (``> 0``, and finite for float
    input). A resampled cell is valid only when the area-weighted valid
    fraction under it is 1: an ``INTER_NEAREST`` mask is not enough, because
    OpenCV's nearest sample is the block's first pixel, so a block whose last
    columns are nodata would keep a blended half-intensity value marked valid.
    Invalid native pixels are zeroed before resizing (no NaN spreads) and
    invalid resampled cells are set to 0.
    """
    import cv2

    valid = source_native > 0
    if np.issubdtype(source_native.dtype, np.floating):
        valid &= np.isfinite(source_native)
    image = source_native if valid.all() else np.where(valid, source_native, 0)
    src_r = cv2.resize(image, size_wh, interpolation=cv2.INTER_AREA)
    support = cv2.resize(valid.astype(np.float32), size_wh, interpolation=cv2.INTER_AREA)
    valid_r = support >= 1.0 - 1e-6
    if not valid_r.all():
        src_r = np.where(valid_r, src_r, 0).astype(src_r.dtype, copy=False)
    return src_r, valid_r


def _tile_summary(tiles: TileDiagnostics | None) -> tuple[str, str]:
    """``("<status>=<n>, ... of <total>", cause in words)`` for a too-few-matches outcome."""
    if tiles is None or not tiles.outcomes:
        return "no tiles", "data gap: no tile was planned"
    counts = tiles.counts
    text = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    text += f" of {len(tiles.outcomes)}"
    gaps = counts.get("out_of_reference", 0) + counts.get("skipped_nodata", 0)
    if tiles.n_failed:
        cause = f"{tiles.n_failed} tile(s) failed in the matcher (error or OOM)"
    elif gaps == len(tiles.outcomes):
        cause = "data gap: no tile had enough valid overlapping data"
    else:
        cause = "matcher ran but found too few correspondences"
    return text, cause


def _probe_grid(height: int, width: int) -> np.ndarray:
    """``PROBE_GRID`` x ``PROBE_GRID`` ``(x, y)`` points spanning the source window, native px."""
    xs = np.linspace(0.0, width - 1.0, PROBE_GRID)
    ys = np.linspace(0.0, height - 1.0, PROBE_GRID)
    gx, gy = np.meshgrid(xs, ys)
    return np.c_[gx.ravel(), gy.ravel()]


# ------------------------------------------------------------------ public API


def lift_to_native(
    coarse: np.ndarray, source_to_native: np.ndarray, reference_to_native: np.ndarray
) -> np.ndarray:
    """Re-express a working-px transform in native px.

    ``coarse`` maps working-source px -> working-reference px; the result maps
    source-native px -> reference-native px:
    ``reference_to_native @ coarse @ inv(source_to_native)``. A 2x3 ``coarse``
    is promoted with ``[0, 0, 1]``.
    """
    c = _as_3x3(coarse, "coarse")
    s2n = _as_3x3(source_to_native, "source_to_native")
    r2n = _as_3x3(reference_to_native, "reference_to_native")
    return r2n @ c @ np.linalg.inv(s2n)


def refine_native_arrays(
    source_native: np.ndarray,
    reference_native: np.ndarray,
    prior_native: np.ndarray,
    *,
    source_native_gsd_m: float,
    reference_native_gsd_m: float,
    matcher: str = "sift",
    tile_px: int | None = None,
    model: str = "homography",
    coarse_gsd_m: float = 4.0,
    max_drift_coarse_px: float = 1.0,
    seed: int = 0,
) -> NativeRefinement:
    """Refine ``prior_native`` at the reference's native GSD (C19, G10).

    ``source_native`` and ``reference_native`` are single-band windows at their
    native GSDs (0 = nodata); ``prior_native`` maps source-native px ->
    reference-native px (typically :func:`lift_to_native` of the coarse
    transform). The source is resampled down to ``reference_native_gsd_m``;
    the reference is used as is. Raises ``ValueError`` only for programmer
    error: arrays that are not 2-D, non-positive GSDs, a source coarser than
    the reference, an unknown ``model``, or a malformed prior.
    """
    source_native = np.asarray(source_native)
    reference_native = np.asarray(reference_native)
    if source_native.ndim != 2 or reference_native.ndim != 2:
        raise ValueError(
            f"source and reference must be 2-D, got {source_native.shape} and "
            f"{reference_native.shape}"
        )
    if source_native_gsd_m <= 0 or reference_native_gsd_m <= 0 or coarse_gsd_m <= 0:
        raise ValueError("GSDs must be positive")
    if model not in TRANSFORM_MODELS:
        raise ValueError(f"model must be one of {TRANSFORM_MODELS}, got {model!r}")
    prior_native = _as_3x3(prior_native, "prior_native")
    if not np.all(np.isfinite(prior_native)):
        raise ValueError("prior_native must be finite")

    # 1. Resample the source to the reference GSD (never upsample the reference, G10).
    f = reference_native_gsd_m / source_native_gsd_m
    if f < 1.0:
        raise ValueError(
            f"source GSD {source_native_gsd_m} m is coarser than reference GSD "
            f"{reference_native_gsd_m} m; native refinement resamples the source down"
        )
    h, w = source_native.shape
    size = (max(1, round(w / f)), max(1, round(h / f)))
    src_r, valid_r = _resample_source(source_native, size)
    S = _native_to_resampled((w, h), (src_r.shape[1], src_r.shape[0]))

    # 2. Prior at matching scale: resampled source px -> reference-native px.
    P = prior_native @ np.linalg.inv(S)

    # 3. Tile-by-tile matching through the prior.
    tiled = TiledMatcher(
        build_matcher(matcher), tile_px=tile_px or int(DEFAULT_NATIVE_TILE_PX.value), progress=False
    )
    matches = tiled.match_arrays(src_r, reference_native, prior=P, source_valid=valid_r)
    tiles = tiled.last_diagnostics
    n_matches = len(matches)

    def finish(status, transform=None, n_inliers=0, drift=None, detail=""):
        out = NativeRefinement(status, transform, n_matches, n_inliers, drift, tiles, detail)
        log = logger.warning if status.is_failure else logger.info
        log(
            "native refinement (%s at %.3g m): %s, %d matches, %d inliers, drift %s coarse px",
            matcher,
            reference_native_gsd_m,
            status.value,
            n_matches,
            n_inliers,
            "n/a" if drift is None else f"{drift:.3f}",
        )
        return out

    total = len(tiles.outcomes) if tiles is not None else 0
    tiles_failed = bool(total) and tiles.n_failed / total > float(MAX_FAILED_TILE_FRACTION.value)

    # 4. Fit. Failed tiles that left nothing to fit are TILE_FAILURES, not a
    # data gap (classified outcomes: data gap vs bug).
    min_matches = int(MIN_MATCHES.value)
    if n_matches < min_matches:
        counts, cause = _tile_summary(tiles)
        detail = f"{n_matches} matches < {min_matches}; tiles {counts}; {cause}"
        if tiles_failed:
            return finish(NativeStatus.TILE_FAILURES, detail=detail[:_SAMPLE_CHARS])
        return finish(NativeStatus.TOO_FEW_MATCHES, detail=detail[:_SAMPLE_CHARS])
    try:
        _, annotated = estimate_transform(
            matches, model, threshold_px=float(FIT_THRESHOLD_PX.value), seed=seed
        )
        fit, refit = reestimate_on_inliers(
            annotated, model, threshold_px=float(REFIT_THRESHOLD_PX.value), seed=seed
        )
    except ValueError as exc:
        if tiles_failed:
            detail = f"{tiles.n_failed}/{total} tiles failed; fit then failed: {exc}"
            return finish(NativeStatus.TILE_FAILURES, detail=detail[:_SAMPLE_CHARS])
        return finish(NativeStatus.ESTIMATION_FAILED, detail=str(exc)[:_SAMPLE_CHARS])
    n_inliers = int(refit.n_inliers)
    t_fit = _as_3x3(fit.matrix, "fit")
    if not np.all(np.isfinite(t_fit)):
        return finish(
            NativeStatus.ESTIMATION_FAILED, n_inliers=n_inliers, detail="non-finite fit matrix"
        )

    # 5. Source-native px -> reference-native px.
    t_native = t_fit @ S

    # 6. Drift against the coarse prior, in coarse px.
    probes = _probe_grid(h, w)
    dist = np.linalg.norm(_apply(t_native, probes) - _apply(prior_native, probes), axis=1)
    drift = float(dist.max() * reference_native_gsd_m / coarse_gsd_m)
    if not np.isfinite(drift) or drift > max_drift_coarse_px:
        return finish(
            NativeStatus.DRIFT_EXCEEDED,
            t_native,
            n_inliers,
            drift,
            f"drift {drift:.3f} coarse px > {max_drift_coarse_px}",
        )

    # 7. Tile failures.
    if tiles_failed:
        return finish(
            NativeStatus.TILE_FAILURES,
            t_native,
            n_inliers,
            drift,
            f"{tiles.n_failed}/{total} tiles failed",
        )

    # 8. OK.
    return finish(NativeStatus.OK, t_native, n_inliers, drift)
