"""Geometric transform estimation.

MAGSAC++ is the default robust estimator rather than plain RANSAC: it
marginalises over the inlier threshold instead of requiring one to be guessed,
which matters here because a sensible threshold differs between an OHRC/TMC-2
pair and an OHRC/IIRS pair by more than an order of magnitude.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from lunar_reg.match.base import MatchResult

logger = logging.getLogger(__name__)

#: Reprojection threshold in pixels. Sub-pixel accuracy is the requirement, so
#: this is deliberately tight; loosen it only for a first coarse pass.
DEFAULT_THRESHOLD_PX = 2.0

TRANSFORM_MODELS = ("homography", "affine", "partial_affine")

#: Minimum correspondences each model needs before a fit means anything.
_MIN_POINTS = {"homography": 4, "affine": 3, "partial_affine": 2}


@dataclass
class Transform:
    """An estimated source-to-reference transform."""

    matrix: np.ndarray
    model: str
    n_inliers: int
    n_total: int

    @property
    def inlier_ratio(self) -> float:
        return self.n_inliers / self.n_total if self.n_total else 0.0

    def apply(self, pts: np.ndarray) -> np.ndarray:
        """Map ``(N, 2)`` source points into reference coordinates."""
        pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
        homogeneous = np.hstack([pts, np.ones((len(pts), 1))])
        if self.matrix.shape == (3, 3):
            out = homogeneous @ self.matrix.T
            return out[:, :2] / out[:, 2:3]
        return homogeneous @ self.matrix.T


def estimate_transform(
    result: MatchResult,
    model: str = "homography",
    threshold_px: float = DEFAULT_THRESHOLD_PX,
    max_iters: int = 10_000,
    confidence: float = 0.9999,
) -> tuple[Transform, MatchResult]:
    """Fit a robust transform and annotate the result with its inlier mask.

    Returns ``(transform, result)`` where ``result`` is the same object with
    :attr:`~lunar_reg.match.base.MatchResult.inlier_mask` populated -- the
    inlier count and ratio the problem statement asks for come from there.

    Raises :class:`ValueError` when there are too few correspondences for the
    requested model; a fit at exactly the minimum point count is meaningless
    and should not be reported as a success.
    """
    import cv2

    if model not in TRANSFORM_MODELS:
        raise ValueError(f"model must be one of {TRANSFORM_MODELS}, got {model!r}")

    n_needed = _MIN_POINTS[model]
    if len(result) < n_needed:
        raise ValueError(
            f"{model} needs at least {n_needed} correspondences, got {len(result)}"
        )

    src = result.src_pts.astype(np.float32)
    dst = result.dst_pts.astype(np.float32)

    if model == "homography":
        matrix, mask = cv2.findHomography(
            src, dst, method=cv2.USAC_MAGSAC,
            ransacReprojThreshold=threshold_px, maxIters=max_iters, confidence=confidence,
        )
    elif model == "affine":
        matrix, mask = cv2.estimateAffine2D(
            src, dst, method=cv2.RANSAC,
            ransacReprojThreshold=threshold_px, maxIters=max_iters, confidence=confidence,
        )
    else:
        matrix, mask = cv2.estimateAffinePartial2D(
            src, dst, method=cv2.RANSAC,
            ransacReprojThreshold=threshold_px, maxIters=max_iters, confidence=confidence,
        )

    if matrix is None:
        raise ValueError(f"{model} estimation failed to converge on {len(result)} points")

    mask = np.asarray(mask, dtype=bool).reshape(-1)
    result.inlier_mask = mask
    transform = Transform(
        matrix=np.asarray(matrix, dtype=np.float64),
        model=model,
        n_inliers=int(mask.sum()),
        n_total=len(result),
    )
    logger.info(
        "%s: %d/%d inliers (%.1f%%) at %.1f px threshold",
        model, transform.n_inliers, transform.n_total, 100 * transform.inlier_ratio, threshold_px,
    )
    return transform, result
