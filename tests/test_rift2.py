"""RIFT2: clean-room implementation checks.

Two kinds of test here. Some pin the implementation against statements in the
papers -- notably the worked histogram example, which the papers print in full
and which is the strongest independent check available without running the
authors' unlicensed MATLAB. The rest verify the *properties* RIFT2 exists for:
invariance to nonlinear radiation distortion, and to contrast inversion in
particular, where intensity- and gradient-based matchers fail outright.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from lunar_reg.align.estimate import estimate_transform
from lunar_reg.match.classical import ClassicalMatcher, build_classical, paper_baseline_status
from lunar_reg.match.rift2 import (
    N_ORIENTATIONS,
    N_SCALES,
    RIFT2Matcher,
    build_log_gabor_bank,
    build_mim,
    compute_moments,
    compute_phase_congruency,
    describe_patch,
    detect_corners,
    detect_edges,
    dominant_indices,
    recode_mim,
)
from lunar_reg.match.rift2.descriptor import N_GRIDS, PATCH_SIZE, describe_keypoints
from lunar_reg.match.rift2.mim import mim_histogram

TRUE_H = np.array([[1.02, 0.01, 12.0], [-0.015, 0.99, -7.0], [0.0, 0.0, 1.0]])


def _scene(size=512, seed=7, n_craters=60):
    rng = np.random.default_rng(seed)
    img = cv2.GaussianBlur(rng.integers(40, 215, (size, size)).astype(np.uint8), (7, 7), 2.0)
    for _ in range(n_craters):
        cx, cy = rng.integers(40, size - 40), rng.integers(40, size - 40)
        cv2.circle(img, (int(cx), int(cy)), int(rng.integers(8, 25)),
                   int(rng.integers(50, 230)), -1)
    return img


@pytest.fixture(scope="module")
def scene():
    return _scene()


@pytest.fixture(scope="module")
def warped(scene):
    return cv2.warpPerspective(scene, TRUE_H, scene.shape[::-1], flags=cv2.INTER_CUBIC)


def _probe_rmse(matrix, size=512, n=15):
    probe = np.stack(np.meshgrid(np.linspace(0, size - 1, n),
                                 np.linspace(0, size - 1, n)), -1).reshape(-1, 2)

    def apply(m, p):
        q = np.hstack([p, np.ones((len(p), 1))]) @ m.T
        return q[:, :2] / q[:, 2:3]

    return float(np.sqrt(
        (np.linalg.norm(apply(matrix, probe) - apply(TRUE_H, probe), axis=1) ** 2).mean()
    ))


# --- paper-stated parameters ------------------------------------------------


def test_parameters_match_the_papers():
    """All four are stated outright, unlike the Makharia preprocessing values."""
    assert N_ORIENTATIONS == 6
    assert N_SCALES == 4
    assert PATCH_SIZE == 96
    assert N_GRIDS == 6


def test_descriptor_dimension_is_the_papers_216():
    assert RIFT2Matcher().descriptor_size == 6 * 6 * 6 == 216


# --- the papers' own worked example -----------------------------------------


def test_recoding_reproduces_the_papers_worked_histogram_example():
    """RIFT2 section III prints this exact shift; strongest available check.

    Histogram {(1,170),(2,236),(3,450),(4,40),(5,300),(6,100)} becomes
    {(1,236),(2,450),(3,40),(4,300),(5,100),(6,170)} when the initial layer
    moves to the second.
    """
    counts = [170, 236, 450, 40, 300, 100]
    patch = np.concatenate(
        [np.full(c, i + 1) for i, c in enumerate(counts)]
    ).astype(np.int16).reshape(-1, 1)

    assert mim_histogram(patch, 6).tolist() == counts
    recoded = recode_mim(patch, 2, 6)
    assert mim_histogram(recoded, 6).tolist() == [236, 450, 40, 300, 100, 170]


def test_recoding_puts_the_dominant_index_first():
    counts = [10, 20, 90, 5, 30, 15]
    patch = np.concatenate(
        [np.full(c, i + 1) for i, c in enumerate(counts)]
    ).astype(np.int16).reshape(-1, 1)
    s = dominant_indices(patch, 6)[0]
    assert s == 3, "value 3 has the largest count"
    assert mim_histogram(recode_mim(patch, s, 6), 6)[0] == 90


def test_recoding_is_a_cyclic_permutation():
    patch = np.arange(1, 7, dtype=np.int16).reshape(2, 3)
    for s in range(1, 7):
        recoded = recode_mim(patch, s, 6)
        assert sorted(recoded.ravel().tolist()) == list(range(1, 7))


def test_ambiguous_peak_yields_two_dominant_indices():
    """RIFT2 emits a second descriptor when the runner-up is within 80%."""
    counts = [100, 85, 10, 10, 10, 10]  # 85/100 = 0.85 >= 0.8
    patch = np.concatenate(
        [np.full(c, i + 1) for i, c in enumerate(counts)]
    ).astype(np.int16).reshape(-1, 1)
    assert len(dominant_indices(patch, 6, dominant_ratio=0.8)) == 2
    assert len(dominant_indices(patch, 6, dominant_ratio=0.9)) == 1


# --- phase congruency and moments -------------------------------------------


def test_log_gabor_bank_has_the_expected_shape():
    bank = build_log_gabor_bank((64, 64))
    assert bank.shape == (N_SCALES, N_ORIENTATIONS, 64, 64)
    assert np.isfinite(bank).all()


def test_log_gabor_filters_are_bandpass_with_no_dc():
    """A DC component would make the response track absolute brightness."""
    bank = build_log_gabor_bank((64, 64))
    for s in range(N_SCALES):
        for o in range(N_ORIENTATIONS):
            assert bank[s, o][0, 0] == 0.0


def test_phase_congruency_outputs_are_well_formed(scene):
    result = compute_phase_congruency(scene.astype(np.float64))
    assert result.amplitude_by_orientation.shape[0] == N_ORIENTATIONS
    assert result.pc_by_orientation.min() >= 0.0
    assert np.isfinite(result.min_moment).all()


def test_max_moment_dominates_min_moment_everywhere(scene):
    """Equations (15) and (16) differ only by the sign of the discriminant."""
    result = compute_phase_congruency(scene.astype(np.float64))
    assert (result.max_moment >= result.min_moment - 1e-9).all()


def test_moments_are_zero_for_a_featureless_image():
    flat = np.full((128, 128), 128.0)
    result = compute_phase_congruency(flat)
    assert result.max_moment.max() < 1e-6


def test_phase_congruency_is_invariant_to_affine_intensity_change(scene):
    """The core claim: PC responds to structure, not to brightness or contrast."""
    a = compute_phase_congruency(scene.astype(np.float64))
    b = compute_phase_congruency(scene.astype(np.float64) * 0.4 + 30.0)
    correlation = np.corrcoef(a.max_moment.ravel(), b.max_moment.ravel())[0, 1]
    assert correlation > 0.99


def test_compute_moments_matches_a_hand_computation():
    pc = np.zeros((2, 1, 1))
    pc[0, 0, 0] = 1.0  # all energy at orientation 0
    pc[1, 0, 0] = 0.0
    minimum, maximum = compute_moments(pc)
    assert maximum[0, 0] == pytest.approx(1.0)
    assert minimum[0, 0] == pytest.approx(0.0, abs=1e-12)


# --- MIM --------------------------------------------------------------------


def test_mim_values_are_one_based_orientation_indices(scene):
    result = compute_phase_congruency(scene.astype(np.float64))
    mim = build_mim(result.amplitude_by_orientation)
    assert mim.min() >= 1
    assert mim.max() <= N_ORIENTATIONS
    assert mim.shape == scene.shape


def test_mim_rejects_a_2d_input():
    with pytest.raises(ValueError, match="n_orientations"):
        build_mim(np.zeros((8, 8)))


def test_mim_picks_the_strongest_orientation():
    amplitude = np.zeros((3, 2, 2))
    amplitude[1] = 5.0
    amplitude[2, 0, 0] = 9.0
    mim = build_mim(amplitude)
    assert mim[0, 0] == 3
    assert mim[1, 1] == 2


# --- descriptor -------------------------------------------------------------


def test_descriptor_is_unit_norm_and_correct_length():
    patch = np.random.default_rng(0).integers(1, 7, (PATCH_SIZE, PATCH_SIZE)).astype(np.int16)
    vector = describe_patch(patch, N_ORIENTATIONS)
    assert vector.shape == (216,)
    assert np.linalg.norm(vector) == pytest.approx(1.0, abs=1e-5)


def test_descriptor_of_a_constant_patch_is_well_defined():
    patch = np.full((PATCH_SIZE, PATCH_SIZE), 3, dtype=np.int16)
    vector = describe_patch(patch, N_ORIENTATIONS)
    assert np.isfinite(vector).all()


def test_keypoints_near_the_border_are_dropped_not_padded():
    """Padding would fabricate MIM values and the descriptor would encode them."""
    mim = np.random.default_rng(0).integers(1, 7, (200, 200)).astype(np.int16)
    points, descriptors = describe_keypoints(
        mim, np.array([[5.0, 5.0], [100.0, 100.0], [195.0, 195.0]]), N_ORIENTATIONS
    )
    assert len(points) >= 1
    assert all(48 <= p[0] <= 152 and 48 <= p[1] <= 152 for p in points)


def test_points_and_descriptors_stay_aligned_when_a_keypoint_doubles():
    """An ambiguous dominant index emits two descriptors for one keypoint."""
    mim = np.random.default_rng(1).integers(1, 7, (300, 300)).astype(np.int16)
    keypoints = np.array([[150.0, 150.0], [120.0, 160.0]])
    points, descriptors = describe_keypoints(mim, keypoints, N_ORIENTATIONS)
    assert len(points) == len(descriptors)
    assert len(points) >= len(keypoints)


# --- detection --------------------------------------------------------------


def test_corner_and_edge_detectors_both_return_points(scene):
    result = compute_phase_congruency(scene.astype(np.float64))
    assert len(detect_corners(result.min_moment, 500)) > 10
    assert len(detect_edges(result.max_moment, 500)) > 10


def test_detectors_respect_their_budget(scene):
    result = compute_phase_congruency(scene.astype(np.float64))
    assert len(detect_corners(result.min_moment, 50)) <= 50
    assert len(detect_edges(result.max_moment, 50)) <= 50


def test_detection_on_a_flat_image_returns_nothing():
    result = compute_phase_congruency(np.full((128, 128), 100.0))
    assert len(detect_corners(result.min_moment, 100)) == 0


def test_matcher_requires_at_least_one_detector_family():
    with pytest.raises(ValueError, match="use_edges"):
        RIFT2Matcher(use_edges=False, use_corners=False)


# --- end to end, and the property RIFT2 exists for --------------------------


def test_recovers_a_known_homography(scene, warped):
    result = RIFT2Matcher().match(scene, warped)
    assert len(result) > 100
    transform, result = estimate_transform(result, "homography", threshold_px=3.0)
    assert transform.inlier_ratio > 0.5
    assert _probe_rmse(transform.matrix) < 1.0


def test_survives_contrast_inversion_where_sift_fails(scene, warped):
    """The headline claim, and the reason RIFT2 is worth implementing.

    Measured: under full contrast inversion RIFT2 recovers the transform to
    ~0.31 px, while SIFT cannot fit at all and ASIFT/AKAZE return transforms
    wrong by 797 px and 329 px respectively.
    """
    inverted = 255 - warped
    rift = RIFT2Matcher().match(scene, inverted)
    assert len(rift) > 100, f"RIFT2 found only {len(rift)} matches under inversion"
    transform, _ = estimate_transform(rift, "homography", threshold_px=3.0)
    assert _probe_rmse(transform.matrix) < 2.0

    # SIFT on the same pair fails in one of three ways: too few matches to fit,
    # a fit that will not converge, or a converged but badly wrong transform.
    sift = ClassicalMatcher("sift").match(scene, inverted)
    sift_failed = len(sift) < 4
    if not sift_failed:
        try:
            sift_transform, _ = estimate_transform(sift, "homography", threshold_px=3.0)
            sift_failed = _probe_rmse(sift_transform.matrix) > 10.0
        except ValueError:
            sift_failed = True  # would not converge at all
    assert sift_failed, (
        "SIFT unexpectedly handled contrast inversion; the comparison in the "
        "README and the case for RIFT2 both need revisiting"
    )


def test_survives_a_non_monotonic_intensity_map(scene, warped):
    """True NRD: a non-monotonic map, which no gradient method can follow."""
    x = warped.astype(np.float32) / 255.0
    distorted = (np.abs(np.sin(2.6 * np.pi * x)) * 255).astype(np.uint8)
    result = RIFT2Matcher().match(scene, distorted)
    assert len(result) > 50
    transform, _ = estimate_transform(result, "homography", threshold_px=3.0)
    assert _probe_rmse(transform.matrix) < 3.0


def test_descriptor_is_invariant_to_inversion_for_the_same_patch(scene):
    """Descriptors of an image and its complement should be near-identical."""
    matcher = RIFT2Matcher(max_keypoints=200)
    _, direct = matcher.detect_and_describe(scene)
    _, inverted = matcher.detect_and_describe(255 - scene)
    assert len(direct) > 0 and len(inverted) > 0
    # Compare the mean descriptor: inversion must not reshape the distribution.
    similarity = float(np.dot(direct.mean(0), inverted.mean(0)) /
                       (np.linalg.norm(direct.mean(0)) * np.linalg.norm(inverted.mean(0))))
    assert similarity > 0.9


def test_empty_and_degenerate_inputs_do_not_crash():
    matcher = RIFT2Matcher(max_keypoints=100)
    flat = np.full((128, 128), 100, dtype=np.uint8)
    assert len(matcher.match(flat, flat)) == 0


def test_matcher_reports_provenance_in_meta(scene, warped):
    meta = RIFT2Matcher().match(scene, warped).meta
    assert meta["detector"] == "rift2"
    assert meta["n_orientations"] == N_ORIENTATIONS


def test_rift2_is_reachable_through_the_common_factory():
    assert isinstance(build_classical("rift2"), RIFT2Matcher)


def test_all_four_paper_baselines_are_now_available():
    status = paper_baseline_status()
    assert all("available" in v for v in status.values())
    assert "clean-room" in status["rift2"]
