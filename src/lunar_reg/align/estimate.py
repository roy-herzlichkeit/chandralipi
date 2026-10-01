"""Geometric transform estimation.

Homographies are fitted with MAGSAC++ (``cv2.USAC_MAGSAC``) rather than plain
RANSAC: it marginalises over the inlier threshold instead of requiring one to
be guessed, which matters because a sensible threshold differs between an
OHRC/TMC-2 pair and an OHRC/IIRS pair by more than an order of magnitude. The
affine and partial-affine models use plain RANSAC
(``cv2.estimateAffine2D``/``estimateAffinePartial2D``); MAGSAC++ does not apply
to them here. :attr:`Transform.estimator` records which one ran.

Fits are deterministic: OpenCV's RNG is seeded right before each estimator
call, and points are centred on their float64 centroids before OpenCV's float32
cast, so large map coordinates keep sub-pixel precision.
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
    estimator: str = "unknown"  # "USAC_MAGSAC" | "RANSAC" | "LSQ"
    seed: int | None = None

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
    seed: int = 0,
) -> tuple[Transform, MatchResult]:
    """Fit a robust transform and annotate the result with its inlier mask.

    Returns ``(transform, result)`` where ``result`` is the same object with
    :attr:`~lunar_reg.match.base.MatchResult.inlier_mask` populated -- the
    inlier count and ratio the problem statement asks for come from there.

    Raises :class:`ValueError` when there are too few correspondences for the
    requested model; a fit at exactly the minimum point count is meaningless
    and should not be reported as a success.

    ``seed`` resets OpenCV's RNG immediately before the estimator call, so the
    same input gives bit-identical matrices and masks across calls and
    processes. The input points are not modified.
    """
    import cv2

    if model not in TRANSFORM_MODELS:
        raise ValueError(f"model must be one of {TRANSFORM_MODELS}, got {model!r}")

    n_needed = _MIN_POINTS[model]
    if len(result) < n_needed:
        raise ValueError(f"{model} needs at least {n_needed} correspondences, got {len(result)}")

    # Centre on float64 centroids before the float32 cast: at map coordinates
    # around 5e5 px, float32 keeps only ~0.03 px, which is not sub-pixel safe.
    cs = result.src_pts.mean(axis=0)
    cd = result.dst_pts.mean(axis=0)
    src = (result.src_pts - cs).astype(np.float32)
    dst = (result.dst_pts - cd).astype(np.float32)

    # estimateAffine2D/estimateAffinePartial2D take no seed: their RANSAC draws
    # from OpenCV's per-thread RNG, so reset it here, in this thread, right
    # before the call.
    cv2.setRNGSeed(int(seed))
    if model == "homography":
        estimator = "USAC_MAGSAC"
        matrix, mask = cv2.findHomography(
            src,
            dst,
            method=cv2.USAC_MAGSAC,
            ransacReprojThreshold=threshold_px,
            maxIters=max_iters,
            confidence=confidence,
        )
    elif model == "affine":
        estimator = "RANSAC"
        matrix, mask = cv2.estimateAffine2D(
            src,
            dst,
            method=cv2.RANSAC,
            ransacReprojThreshold=threshold_px,
            maxIters=max_iters,
            confidence=confidence,
        )
    else:
        estimator = "RANSAC"
        matrix, mask = cv2.estimateAffinePartial2D(
            src,
            dst,
            method=cv2.RANSAC,
            ransacReprojThreshold=threshold_px,
            maxIters=max_iters,
            confidence=confidence,
        )

    if matrix is None:
        raise ValueError(f"{model} estimation failed to converge on {len(result)} points")

    # Un-centre in float64: M = Td_inv @ M3 @ Ts.
    m3 = np.asarray(matrix, dtype=np.float64)
    if m3.shape == (2, 3):
        m3 = np.vstack([m3, [0.0, 0.0, 1.0]])
    ts = np.array([[1.0, 0.0, -cs[0]], [0.0, 1.0, -cs[1]], [0.0, 0.0, 1.0]])
    td_inv = np.array([[1.0, 0.0, cd[0]], [0.0, 1.0, cd[1]], [0.0, 0.0, 1.0]])
    full = td_inv @ m3 @ ts
    full = full / full[2, 2] if model == "homography" else full[:2]

    mask = np.asarray(mask, dtype=bool).reshape(-1)
    result.inlier_mask = mask
    transform = Transform(
        matrix=full,
        model=model,
        n_inliers=int(mask.sum()),
        n_total=len(result),
        estimator=estimator,
        seed=seed,
    )
    logger.info(
        "%s: %d/%d inliers (%.1f%%) at %.1f px threshold",
        model,
        transform.n_inliers,
        transform.n_total,
        100 * transform.inlier_ratio,
        threshold_px,
    )
    return transform, result
