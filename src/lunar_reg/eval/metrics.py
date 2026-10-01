"""Registration accuracy metrics.

Covers the metrics the problem statement names explicitly -- RMSE, inlier match
count, inlier ratio -- plus the residual percentiles needed to substantiate a
sub-pixel claim. A mean RMSE below 1 px with a 95th percentile of 6 px is not
sub-pixel registration, and only the percentile shows that.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from lunar_reg.align.estimate import Transform
from lunar_reg.match.base import MatchResult


def residuals(result: MatchResult, transform: Transform, inliers_only: bool = True) -> np.ndarray:
    """Per-correspondence reprojection error in pixels."""
    subset = result.inliers() if (inliers_only and result.inlier_mask is not None) else result
    if len(subset) == 0:
        return np.empty(0)
    predicted = transform.apply(subset.src_pts)
    return np.linalg.norm(predicted - subset.dst_pts, axis=1)


def rmse(result: MatchResult, transform: Transform, inliers_only: bool = True) -> float:
    """Root-mean-square reprojection error in pixels.

    Computed over inliers by default. Reporting RMSE over *all* matches instead
    conflates registration accuracy with outlier rejection and makes numbers
    incomparable across matchers -- state which convention a table uses.
    """
    r = residuals(result, transform, inliers_only)
    return float(np.sqrt(np.mean(r**2))) if r.size else float("nan")


@dataclass
class RegistrationMetrics:
    """The full metric set for one registered pair.

    Counts follow DECISIONS G34: ``n_matches`` is the raw matcher output,
    ``n_ransac_inliers`` the first robust fit's inliers, ``n_inliers`` the final
    (refit) inliers, and both ratios are over the raw count. Residuals are over
    the final inliers. ``residual_basis`` says what the residuals measure:
    ``"self_residual"`` is the fit's own reprojection error on the points it
    was fitted to (no ground truth), ``"truth"`` is error against a known
    transform.
    """

    n_matches: int
    n_ransac_inliers: int | None
    n_inliers: int
    inlier_ratio: float
    ransac_inlier_ratio: float | None
    rmse_px: float
    mae_px: float
    median_px: float
    p95_px: float
    max_px: float
    model: str
    matcher: str
    #: RMSE converted to ground distance, when the GSD is known.
    rmse_m: float | None = None
    residual_basis: str = "self_residual"

    @property
    def self_residual_subpixel(self) -> bool:
        """Whether the self-residual clears one pixel at both the RMS and the 95th percentile.

        Deliberately strict, and deliberately named: on a real pair with no
        ground truth this is the fit agreeing with its own inliers, not
        registration accuracy.
        """
        return self.rmse_px < 1.0 and self.p95_px < 1.0

    def as_dict(self) -> dict:
        return {**asdict(self), "self_residual_subpixel": self.self_residual_subpixel}


def compute_metrics(
    result: MatchResult,
    transform: Transform,
    gsd_m: float | None = None,
    ransac_mask: np.ndarray | None = None,
    residual_basis: str = "self_residual",
) -> RegistrationMetrics:
    """Assemble every accuracy metric for one registered pair.

    ``result`` holds the raw correspondences with the final inlier mask;
    ``ransac_mask`` (same length) marks the first-pass inliers when known.
    """
    r = residuals(result, transform, inliers_only=True)
    value = rmse(result, transform)
    n_matches = len(result)
    if result.inlier_mask is not None:
        n_inliers = int(np.asarray(result.inlier_mask, dtype=bool).sum())
    else:
        n_inliers = transform.n_inliers
    n_ransac = None if ransac_mask is None else int(np.asarray(ransac_mask, dtype=bool).sum())
    return RegistrationMetrics(
        n_matches=n_matches,
        n_ransac_inliers=n_ransac,
        n_inliers=n_inliers,
        inlier_ratio=n_inliers / n_matches if n_matches else 0.0,
        ransac_inlier_ratio=(
            None if n_ransac is None else (n_ransac / n_matches if n_matches else 0.0)
        ),
        rmse_px=value,
        mae_px=float(np.mean(r)) if r.size else float("nan"),
        median_px=float(np.median(r)) if r.size else float("nan"),
        p95_px=float(np.percentile(r, 95)) if r.size else float("nan"),
        max_px=float(np.max(r)) if r.size else float("nan"),
        model=transform.model,
        matcher=result.matcher,
        rmse_m=None if gsd_m is None or np.isnan(value) else value * gsd_m,
        residual_basis=residual_basis,
    )
