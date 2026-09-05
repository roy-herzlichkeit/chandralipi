"""MatchResult is the common currency between every matcher and the metrics."""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.ingest.tiling import Tile
from lunar_reg.match.base import MatchResult


def test_mismatched_point_counts_rejected():
    with pytest.raises(ValueError, match="differ"):
        MatchResult(np.zeros((5, 2)), np.zeros((3, 2)))


def test_points_are_stored_as_float():
    """Integer storage would silently discard the sub-pixel result."""
    r = MatchResult(np.array([[1, 2]], dtype=np.int32), np.array([[3, 4]], dtype=np.int32))
    assert r.src_pts.dtype == np.float64


def test_inliers_filters_both_sides_consistently():
    pts = np.arange(20, dtype=float).reshape(10, 2)
    r = MatchResult(pts, pts + 1, scores=np.arange(10.0))
    r.inlier_mask = np.array([True, False] * 5)
    inl = r.inliers()
    assert len(inl) == 5
    np.testing.assert_allclose(inl.dst_pts - inl.src_pts, 1.0)
    assert len(inl.scores) == 5


def test_inlier_ratio_before_ransac_is_zero():
    assert MatchResult(np.zeros((10, 2)), np.zeros((10, 2))).inlier_ratio == 0.0


def test_concatenate_merges_tile_results():
    a = MatchResult(np.zeros((3, 2)), np.ones((3, 2)), scores=np.ones(3))
    b = MatchResult(np.ones((4, 2)), np.zeros((4, 2)), scores=np.ones(4))
    merged = MatchResult.concatenate([a, b], matcher="tiled")
    assert len(merged) == 7
    assert merged.meta["n_tiles"] == 2


def test_concatenate_of_nothing_is_empty_not_an_error():
    assert len(MatchResult.concatenate([])) == 0


def test_tile_results_merge_into_a_common_frame():
    """Two tiles' local coordinates must not collide once lifted."""
    t0 = Tile(0, 0, 256, 256, index=(0, 0))
    t1 = Tile(0, 256, 256, 256, index=(0, 1))
    local = np.array([[10.0, 10.0]])
    merged = MatchResult.concatenate([
        MatchResult(t0.to_parent(local), t0.to_parent(local)),
        MatchResult(t1.to_parent(local), t1.to_parent(local)),
    ])
    assert merged.src_pts[0, 0] == 10.0
    assert merged.src_pts[1, 0] == 266.0
