"""Metrics are the submission's deliverable, so they need to be right."""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.align.estimate import Transform
from lunar_reg.eval.metrics import compute_metrics, rmse
from lunar_reg.eval.uniformity import cell_counts, compute_uniformity, enforce_uniformity
from lunar_reg.match.base import MatchResult

IDENTITY = np.eye(3)


def _perfect(n=50):
    pts = np.random.default_rng(0).uniform(0, 500, (n, 2))
    r = MatchResult(pts, pts.copy(), matcher="test")
    r.inlier_mask = np.ones(n, dtype=bool)
    return r


def test_exact_correspondence_gives_zero_rmse():
    t = Transform(IDENTITY, "homography", 50, 50)
    assert rmse(_perfect(), t) == pytest.approx(0.0, abs=1e-9)


def test_known_shift_gives_known_rmse():
    pts = np.array([[10.0, 10.0], [20.0, 20.0], [30.0, 30.0], [40.0, 40.0]])
    r = MatchResult(pts, pts + np.array([3.0, 4.0]), matcher="test")
    r.inlier_mask = np.ones(4, dtype=bool)
    t = Transform(IDENTITY, "homography", 4, 4)
    assert rmse(r, t) == pytest.approx(5.0)  # 3-4-5 triangle


def test_metrics_report_inlier_count_and_ratio():
    r = _perfect(100)
    r.inlier_mask = np.array([True] * 80 + [False] * 20)
    t = Transform(IDENTITY, "homography", 80, 100)
    m = compute_metrics(r, t)
    assert m.n_matches == 100
    assert m.n_inliers == 80
    assert m.inlier_ratio == pytest.approx(0.8)


def test_subpixel_flag_requires_both_rmse_and_p95():
    """A good mean with a bad tail is not sub-pixel registration."""
    pts = np.random.default_rng(1).uniform(0, 500, (100, 2))
    offsets = np.zeros((100, 2))
    offsets[:5] = 10.0  # a few large errors, rest exact
    r = MatchResult(pts, pts + offsets, matcher="test")
    r.inlier_mask = np.ones(100, dtype=bool)
    m = compute_metrics(r, Transform(IDENTITY, "homography", 100, 100))
    assert not m.self_residual_subpixel


def test_rmse_converts_to_ground_metres():
    r = _perfect()
    m = compute_metrics(r, Transform(IDENTITY, "homography", 50, 50), gsd_m=0.25)
    assert m.rmse_m == pytest.approx(m.rmse_px * 0.25)


def test_empty_result_does_not_crash():
    m = compute_metrics(MatchResult.empty(), Transform(IDENTITY, "homography", 0, 0))
    assert np.isnan(m.rmse_px)
    assert m.n_matches == 0


# --- uniformity ------------------------------------------------------------


def test_even_spread_scores_near_one():
    grid = 8
    xs, ys = np.meshgrid(np.linspace(10, 990, 24), np.linspace(10, 990, 24))
    pts = np.column_stack([xs.ravel(), ys.ravel()])
    u = compute_uniformity(pts, (1000, 1000), grid)
    assert u.coverage == 1.0
    assert u.entropy > 0.98
    assert u.score > 0.98


def test_clustered_points_score_poorly():
    """The exact failure the problem statement asks us to avoid."""
    pts = np.random.default_rng(0).uniform(0, 100, (500, 2))  # all in one corner
    u = compute_uniformity(pts, (1000, 1000), grid=8)
    assert u.coverage < 0.05
    assert u.score < 0.3


def test_full_coverage_with_skewed_counts_is_caught_by_entropy():
    """Coverage alone would report 1.0 here; entropy is what flags the skew."""
    pts = [[c * 125 + 60, r * 125 + 60] for r in range(8) for c in range(8)]
    pts += [[60.0, 60.0]] * 5000  # one cell dominates
    u = compute_uniformity(np.array(pts), (1000, 1000), grid=8)
    assert u.coverage == 1.0
    assert u.entropy < 0.3


def test_no_points_scores_zero():
    u = compute_uniformity(np.empty((0, 2)), (1000, 1000))
    assert u.score == 0.0 and u.n_points == 0


def test_enforce_uniformity_caps_dense_cells():
    pts = np.vstack([
        np.random.default_rng(0).uniform(0, 120, (400, 2)),
        np.array([[500.0, 500.0], [900.0, 900.0]]),
    ])
    keep = enforce_uniformity(pts, (1000, 1000), grid=8, max_per_cell=10)
    u = compute_uniformity(pts[keep], (1000, 1000), grid=8)
    assert len(keep) < len(pts)
    assert u.cv < compute_uniformity(pts, (1000, 1000), grid=8).cv


def test_enforce_uniformity_cannot_create_coverage():
    """A documented limitation -- thinning never fills an empty cell.

    Counted as occupied cells on the fixed 8x8 grid: ``coverage`` itself is a
    fraction of the adaptive grid (G33), which shrinks as thinning removes points.
    """
    pts = np.random.default_rng(0).uniform(0, 100, (300, 2))
    before = int((cell_counts(pts, (1000, 1000), 8) > 0).sum())
    keep = enforce_uniformity(pts, (1000, 1000), grid=8, max_per_cell=5)
    assert int((cell_counts(pts[keep], (1000, 1000), 8) > 0).sum()) <= before
