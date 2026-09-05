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
    """The full metric set for one registered pair."""

    n_matches: int
    n_inliers: int
    inlier_ratio: float
    rmse_px: float
    mae_px: float
    median_px: float
    p95_px: float
    max_px: float
    model: str
    matcher: str
    #: RMSE converted to ground distance, when the GSD is known.
    rmse_m: float | None = None

    @property
    def is_subpixel(self) -> bool:
        """Whether the pair meets the stated sub-pixel requirement.

        Deliberately strict: both the central tendency and the 95th percentile
        must clear one pixel.
        """
        return self.rmse_px < 1.0 and self.p95_px < 1.0

    def as_dict(self) -> dict:
        return {**asdict(self), "is_subpixel": self.is_subpixel}


def compute_metrics(
    result: MatchResult,
    transform: Transform,
    gsd_m: float | None = None,
) -> RegistrationMetrics:
    """Assemble every accuracy metric for one registered pair."""
    r = residuals(result, transform, inliers_only=True)
    value = rmse(result, transform)
    return RegistrationMetrics(
        n_matches=len(result),
        n_inliers=transform.n_inliers,
        inlier_ratio=transform.inlier_ratio,
        rmse_px=value,
        mae_px=float(np.mean(r)) if r.size else float("nan"),
        median_px=float(np.median(r)) if r.size else float("nan"),
        p95_px=float(np.percentile(r, 95)) if r.size else float("nan"),
        max_px=float(np.max(r)) if r.size else float("nan"),
        model=transform.model,
        matcher=result.matcher,
        rmse_m=None if gsd_m is None or np.isnan(value) else value * gsd_m,
    )
