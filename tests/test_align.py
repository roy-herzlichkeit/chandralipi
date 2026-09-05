"""Transform estimation and the sub-pixel path."""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.align.estimate import Transform, estimate_transform
from lunar_reg.eval.metrics import rmse
from lunar_reg.match.base import MatchResult

RNG = np.random.default_rng(7)
TRUE_H = np.array([[1.02, 0.01, 12.0], [-0.015, 0.99, -7.0], [0.0, 0.0, 1.0]])


def _apply(matrix, pts):
    h = np.hstack([pts, np.ones((len(pts), 1))]) @ matrix.T
    return h[:, :2] / h[:, 2:3]


def test_recovers_a_known_homography():
    src = RNG.uniform(0, 1000, (200, 2))
    result = MatchResult(src, _apply(TRUE_H, src), matcher="synthetic")
    transform, result = estimate_transform(result, "homography")
    assert transform.inlier_ratio > 0.95
    assert rmse(result, transform) < 0.01


def test_rejects_injected_outliers():
    src = RNG.uniform(0, 1000, (200, 2))
    dst = _apply(TRUE_H, src)
    dst[:40] = RNG.uniform(0, 1000, (40, 2))  # 20% gross outliers
    result = MatchResult(src, dst, matcher="synthetic")
    transform, result = estimate_transform(result, "homography", threshold_px=2.0)
    assert 0.7 < transform.inlier_ratio < 0.9
    assert rmse(result, transform) < 1.0


def test_too_few_points_raises_rather_than_reporting_success():
    """A fit at exactly the minimum point count is meaningless."""
    with pytest.raises(ValueError, match="at least"):
        estimate_transform(MatchResult(np.zeros((2, 2)), np.zeros((2, 2))), "homography")


def test_unknown_model_rejected():
    r = MatchResult(RNG.uniform(0, 100, (20, 2)), RNG.uniform(0, 100, (20, 2)))
    with pytest.raises(ValueError, match="model must be"):
        estimate_transform(r, "thin_plate_spline")


def test_estimate_populates_the_inlier_mask():
    src = RNG.uniform(0, 1000, (100, 2))
    result = MatchResult(src, _apply(TRUE_H, src))
    _, result = estimate_transform(result, "homography")
    assert result.inlier_mask is not None
    assert result.inlier_mask.dtype == bool
    assert len(result.inlier_mask) == 100


@pytest.mark.parametrize("model", ["homography", "affine", "partial_affine"])
def test_all_models_fit_a_pure_translation(model):
    src = RNG.uniform(0, 1000, (100, 2))
    result = MatchResult(src, src + np.array([5.0, -3.0]))
    transform, result = estimate_transform(result, model)
    assert rmse(result, transform) < 0.01


def test_transform_apply_matches_the_generating_homography():
    t = Transform(TRUE_H, "homography", 0, 0)
    pts = RNG.uniform(0, 500, (10, 2))
    np.testing.assert_allclose(t.apply(pts), _apply(TRUE_H, pts), rtol=1e-9)


def test_affine_transform_apply_handles_2x3_matrix():
    matrix = np.array([[1.0, 0.0, 5.0], [0.0, 1.0, -3.0]])
    t = Transform(matrix, "affine", 0, 0)
    np.testing.assert_allclose(t.apply(np.array([[0.0, 0.0]])), [[5.0, -3.0]])
