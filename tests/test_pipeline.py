"""End-to-end pipeline runs on synthetic data.

These use the classical CPU matcher so the suite stays runnable anywhere. They
verify the stages actually compose -- preprocess to match to estimate to
metrics -- which unit tests of each stage individually do not.
"""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.align.estimate import estimate_transform
from lunar_reg.eval.metrics import compute_metrics
from lunar_reg.eval.uniformity import cell_counts, compute_uniformity, enforce_uniformity
from lunar_reg.match.classical import ClassicalMatcher, available_detectors
from lunar_reg.match.tiled import TiledMatcher
from lunar_reg.preprocess.radiometric import standard_chain


def test_end_to_end_recovers_a_known_warp(synthetic_pair):
    src, ref, true_h = synthetic_pair

    result = ClassicalMatcher("sift").match(standard_chain(src), standard_chain(ref))
    assert len(result) > 20, "SIFT found too few matches on synthetic texture"

    transform, result = estimate_transform(result, "homography", threshold_px=3.0)
    metrics = compute_metrics(result, transform)

    assert metrics.inlier_ratio > 0.5
    assert metrics.rmse_px < 3.0

    # The recovered homography should agree with the generating one on where it
    # sends points, which is the meaningful comparison -- the matrices differ by
    # an arbitrary scale factor.
    probe = np.array([[100.0, 100.0], [400.0, 150.0], [250.0, 400.0]])
    expected = np.hstack([probe, np.ones((3, 1))]) @ true_h.T
    expected = expected[:, :2] / expected[:, 2:3]
    np.testing.assert_allclose(transform.apply(probe), expected, atol=2.0)


def test_end_to_end_reports_every_required_metric(synthetic_pair):
    """The problem statement names RMSE, inlier count, and inlier ratio."""
    src, ref, _ = synthetic_pair
    result = ClassicalMatcher("sift").match(standard_chain(src), standard_chain(ref))
    transform, result = estimate_transform(result, "homography", threshold_px=3.0)

    report = compute_metrics(result, transform).as_dict()
    for key in ("rmse_px", "n_inliers", "inlier_ratio"):
        assert key in report and report[key] is not None


def test_illumination_change_does_not_destroy_matching(synthetic_pair):
    """A gamma shift stands in for a sun-elevation change.

    The point of the CLAHE default is that the match survives this; without
    preprocessing the same pair yields markedly fewer correspondences.
    """
    src, ref, _ = synthetic_pair
    darkened = (255.0 * (ref / 255.0) ** 2.2).astype(np.uint8)

    matcher = ClassicalMatcher("sift")
    with_prep = matcher.match(standard_chain(src), standard_chain(darkened))
    without_prep = matcher.match(src, darkened)

    assert len(with_prep) >= len(without_prep)
    transform, with_prep = estimate_transform(with_prep, "homography", threshold_px=3.0)
    assert transform.inlier_ratio > 0.5


def test_tiled_matching_agrees_with_whole_image_matching(synthetic_pair):
    """Tiling is a memory strategy; it must not change the answer."""
    src, ref, _ = synthetic_pair
    prep_src, prep_ref = standard_chain(src), standard_chain(ref)

    whole = ClassicalMatcher("sift").match(prep_src, prep_ref)
    tiled = TiledMatcher(
        ClassicalMatcher("sift"), tile_px=256, overlap=0.25, progress=False
    ).match_arrays(prep_src, prep_ref)

    assert len(tiled) > 10
    t_whole, _ = estimate_transform(whole, "homography", threshold_px=3.0)
    t_tiled, _ = estimate_transform(tiled, "homography", threshold_px=3.0)

    probe = np.array([[128.0, 128.0], [384.0, 256.0]])
    np.testing.assert_allclose(t_tiled.apply(probe), t_whole.apply(probe), atol=3.0)


def test_per_tile_cap_bounds_the_busiest_cell(synthetic_pair):
    """What capping actually guarantees: no tile dominates the match budget.

    It does *not* guarantee a better uniformity score -- on already-even
    imagery it can lower one, and it can never fill a featureless region.
    See test_capping_cannot_create_coverage.
    """
    src, ref, _ = synthetic_pair
    prep_src, prep_ref = standard_chain(src), standard_chain(ref)

    cap = 8
    tiled = TiledMatcher(
        ClassicalMatcher("sift"), tile_px=128, overlap=0.0,
        max_matches_per_tile=cap, progress=False,
    ).match_arrays(prep_src, prep_ref)

    # With non-overlapping 128px tiles on a 512px image, the 4x4 tile grid maps
    # exactly onto a 4x4 evaluation grid, so no cell may exceed the cap.
    assert cell_counts(tiled.src_pts, src.shape, grid=4).max() <= cap


def test_capping_cannot_create_coverage():
    """The documented limitation, stated as a test so it is not forgotten.

    A featureless region yields no keypoints; no amount of redistribution
    produces matches there. Closing those gaps needs a different mechanism.
    """
    pts = np.random.default_rng(0).uniform(0, 128, (400, 2))  # one corner only
    before = compute_uniformity(pts, (512, 512), grid=8)
    keep = enforce_uniformity(pts, (512, 512), grid=8, max_per_cell=4)
    after = compute_uniformity(pts[keep], (512, 512), grid=8)

    assert after.cv <= before.cv          # skew improves
    assert after.coverage <= before.coverage  # coverage never does


@pytest.mark.parametrize("detector", available_detectors())
def test_every_available_detector_produces_usable_matches(detector, synthetic_pair):
    """Parametrised over what this OpenCV build actually has.

    ORB and BRISK use binary descriptors and need Hamming distance rather than
    L2, so this also guards the norm selection in ClassicalMatcher.match.
    """
    src, ref, _ = synthetic_pair
    result = ClassicalMatcher(detector).match(standard_chain(src), standard_chain(ref))
    assert len(result) > 10, f"{detector} produced only {len(result)} matches"
    transform, _ = estimate_transform(result, "homography", threshold_px=3.0)
    assert transform.inlier_ratio > 0.3
