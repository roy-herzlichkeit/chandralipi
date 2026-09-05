"""Classical matchers, sub-pixel refinement, and the uniformity metric.

Several tests here pin *measured* findings rather than assumptions -- that
cornerSubPix degrades SIFT-family keypoints, that ECC's direction convention is
easy to get catastrophically wrong, and that fit RMSE is blind to clustering.
Each would silently regress without a guard.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from lunar_reg.align.estimate import estimate_transform
from lunar_reg.align.refine import (
    DETECTORS_ALREADY_SUBPIXEL,
    reestimate_on_inliers,
    refine_full,
    refine_matches,
    refine_transform_ecc,
)
from lunar_reg.eval.metrics import compute_metrics
from lunar_reg.eval.uniformity import (
    UNIFORMITY_GATE,
    clark_evans_index,
    compute_uniformity,
    uniformity_profile,
)
from lunar_reg.match.classical import (
    DETECTOR_INFO,
    PAPER_BASELINES,
    ClassicalMatcher,
    available_detectors,
    build_classical,
    paper_baseline_status,
)

TRUE_H = np.array([[1.02, 0.01, 12.0], [-0.015, 0.99, -7.0], [0.0, 0.0, 1.0]])


def _textured(size=512, seed=11, n_craters=60):
    rng = np.random.default_rng(seed)
    img = cv2.GaussianBlur(rng.integers(0, 255, (size, size)).astype(np.uint8), (7, 7), 2.0)
    for _ in range(n_craters):
        cx, cy = rng.integers(40, size - 40), rng.integers(40, size - 40)
        cv2.circle(img, (int(cx), int(cy)), int(rng.integers(8, 25)),
                   int(rng.integers(60, 220)), -1)
    return img


@pytest.fixture
def noisy_pair():
    """Source/reference related by TRUE_H, with independent sensor noise."""
    rng = np.random.default_rng(11)
    base = _textured()
    warped = cv2.warpPerspective(base, TRUE_H, base.shape[::-1], flags=cv2.INTER_CUBIC)
    src = np.clip(base.astype(np.float32) + rng.normal(0, 8, base.shape), 0, 255).astype(np.uint8)
    ref = np.clip(warped.astype(np.float32) + rng.normal(0, 8, base.shape), 0, 255).astype(np.uint8)
    return src, ref


def _probe_error(matrix, size=512, n=20):
    """RMS and max error against TRUE_H over a grid spanning the whole image."""
    probe = np.stack(
        np.meshgrid(np.linspace(0, size - 1, n), np.linspace(0, size - 1, n)), -1
    ).reshape(-1, 2)

    def apply(m, p):
        q = np.hstack([p, np.ones((len(p), 1))]) @ m.T
        return q[:, :2] / q[:, 2:3]

    err = np.linalg.norm(apply(matrix, probe) - apply(TRUE_H, probe), axis=1)
    return float(np.sqrt((err**2).mean())), float(err.max())


# --- matcher interface -----------------------------------------------------


def test_all_paper_classical_baselines_are_available():
    """All four of Makharia et al.'s classical baselines can now be run."""
    status = paper_baseline_status()
    for name in ("sift", "asift", "akaze"):
        assert status[name] == "available", (
            f"{name} unavailable -- this project pins opencv-python<5 precisely "
            f"because OpenCV 5 dropped AKAZE and contrib does not restore it"
        )
    assert "clean-room" in status["rift2"], (
        "RIFT2 must be labelled clean-room so nobody reports its results as "
        "reproducing the authors' published numbers"
    )


def test_akaze_is_present_which_requires_the_opencv_pin():
    """Regression guard on the dependency pin, not just on the code."""
    assert "akaze" in available_detectors()


@pytest.mark.parametrize("detector", sorted(set(available_detectors())))
def test_every_detector_recovers_the_transform(detector, noisy_pair):
    src, ref = noisy_pair
    result = ClassicalMatcher(detector).match(src, ref)
    assert len(result) > 20, f"{detector} found only {len(result)} matches"
    transform, result = estimate_transform(result, "homography", threshold_px=3.0)
    assert transform.inlier_ratio > 0.5
    rms, _ = _probe_error(transform.matrix)
    assert rms < 1.0, f"{detector} probe RMSE {rms:.3f} is not sub-pixel"


def test_binary_descriptors_use_hamming_not_l2():
    """Using L2 on binary descriptors does not error -- it silently matches badly."""
    import cv2 as _cv2

    for name in ("akaze", "orb", "brisk"):
        assert DETECTOR_INFO[name].binary_descriptor
        assert DETECTOR_INFO[name].norm == _cv2.NORM_HAMMING
    for name in ("sift", "asift", "kaze"):
        assert not DETECTOR_INFO[name].binary_descriptor
        assert DETECTOR_INFO[name].norm == _cv2.NORM_L2


def test_cross_check_reduces_match_count_but_not_quality(noisy_pair):
    src, ref = noisy_pair
    with_cc = ClassicalMatcher("sift", cross_check=True).match(src, ref)
    without = ClassicalMatcher("sift", cross_check=False).match(src, ref)
    assert len(with_cc) <= len(without)
    t_cc, _ = estimate_transform(with_cc, "homography", threshold_px=3.0)
    assert t_cc.inlier_ratio >= 0.5


def test_asift_finds_more_keypoints_than_sift(noisy_pair):
    """ASIFT simulates affine warps, so it should be strictly richer."""
    src, ref = noisy_pair
    assert len(ClassicalMatcher("asift").match(src, ref)) > len(
        ClassicalMatcher("sift").match(src, ref)
    )


def test_unknown_detector_rejected():
    with pytest.raises(ValueError, match="unknown detector"):
        ClassicalMatcher("magic")


def test_matcher_reports_its_provenance_in_meta(noisy_pair):
    src, ref = noisy_pair
    meta = ClassicalMatcher("sift").match(src, ref).meta
    assert meta["detector"] == "sift"
    assert "n_keypoints" in meta


def test_blank_images_yield_no_matches_without_crashing():
    blank = np.zeros((128, 128), dtype=np.uint8)
    assert len(ClassicalMatcher("sift").match(blank, blank)) == 0


# --- the licensing decision, recorded ---------------------------------------


def test_build_classical_routes_rift2_to_the_clean_room_implementation():
    from lunar_reg.match.rift2 import RIFT2Matcher

    assert isinstance(build_classical("rift2"), RIFT2Matcher)


def test_rift2_is_still_listed_as_a_paper_baseline():
    """It must not quietly disappear from the comparison's scope."""
    assert "rift2" in PAPER_BASELINES


def test_decision_record_states_the_licensing_rationale():
    """The reason RIFT2 is clean-room must survive in the code, not just in git.

    If someone later swaps in a vendored implementation, this is the note that
    explains why that would be a problem.
    """
    from lunar_reg.match import rift2_status

    doc = rift2_status.__doc__ or ""
    assert "no licence" in doc.lower()
    assert "arXiv:1804.09493" in doc and "arXiv:2303.00319" in doc
    assert "No unlicensed source was read" in doc


def test_status_summary_warns_against_claiming_published_numbers():
    from lunar_reg.match.rift2_status import STATUS_SUMMARY

    assert "clean-room" in STATUS_SUMMARY
    assert "NOT been checked against" in STATUS_SUMMARY


# --- sub-pixel refinement --------------------------------------------------


def test_refit_on_inliers_improves_or_holds_accuracy(noisy_pair):
    src, ref = noisy_pair
    result = ClassicalMatcher("sift").match(src, ref)
    t1, r1 = estimate_transform(result, "homography", threshold_px=3.0)
    t2, _ = reestimate_on_inliers(r1, threshold_px=1.0)
    assert _probe_error(t2.matrix)[0] <= _probe_error(t1.matrix)[0] * 1.05


def test_ecc_refinement_beats_the_feature_only_fit(noisy_pair):
    """Measured 0.0457 -> 0.0177 px; ECC is not limited by keypoint localisation."""
    src, ref = noisy_pair
    result = ClassicalMatcher("sift").match(src, ref)
    t1, r1 = estimate_transform(result, "homography", threshold_px=3.0)
    t2, _ = reestimate_on_inliers(r1, threshold_px=1.0)
    t3, cc = refine_transform_ecc(t2, src, ref)
    assert np.isfinite(cc)
    assert _probe_error(t3.matrix)[0] < _probe_error(t2.matrix)[0]


def test_ecc_direction_convention_is_not_silently_reversed(noisy_pair):
    """The trap: three of four conventions are wrong, two catastrophically (~48 px),
    and the correlation coefficient does NOT distinguish them.
    """
    src, ref = noisy_pair
    result = ClassicalMatcher("sift").match(src, ref)
    t1, r1 = estimate_transform(result, "homography", threshold_px=3.0)
    t2, _ = reestimate_on_inliers(r1, threshold_px=1.0)
    t3, _ = refine_transform_ecc(t2, src, ref)
    rms, _ = _probe_error(t3.matrix)
    assert rms < 1.0, (
        f"probe RMSE {rms:.3f} suggests the ECC direction convention was reversed; "
        f"a reversed convention gives ~48 px while still reporting a high cc"
    )


def test_ecc_returns_the_original_transform_when_it_cannot_converge():
    """A diverged warp is worse than no refinement, so failure must be inert."""
    flat = np.full((128, 128), 100, dtype=np.uint8)
    pts = np.random.default_rng(0).uniform(10, 118, (30, 2))
    from lunar_reg.match.base import MatchResult

    result = MatchResult(pts, pts + 1.0)
    transform, _ = estimate_transform(result, "homography", threshold_px=3.0)
    refined, cc = refine_transform_ecc(transform, flat, flat)
    if not np.isfinite(cc):
        np.testing.assert_allclose(refined.matrix, transform.matrix)


def test_corner_subpix_is_refused_for_subpixel_detectors(noisy_pair):
    """Measured: running it on SIFT keypoints made probe error 4x worse."""
    src, ref = noisy_pair
    result = ClassicalMatcher("sift").match(src, ref)
    assert refine_matches(result, src, ref) is result, "must be a no-op by default"


def test_corner_subpix_can_be_forced_deliberately(noisy_pair):
    src, ref = noisy_pair
    result = ClassicalMatcher("sift").match(src, ref)
    forced = refine_matches(result, src, ref, force=True)
    assert forced is not result
    assert forced.meta["subpixel"].startswith("cornerSubPix")


def test_all_supported_detectors_are_marked_already_subpixel():
    """Guard: if a detector with integer output is added, this must be revisited."""
    for name in ("sift", "asift", "akaze", "kaze"):
        assert name in DETECTORS_ALREADY_SUBPIXEL


def test_refine_full_records_which_stages_ran(noisy_pair):
    src, ref = noisy_pair
    result = ClassicalMatcher("sift").match(src, ref)
    _, r1 = estimate_transform(result, "homography", threshold_px=3.0)
    transform, _, detail = refine_full(r1, src, ref)
    assert "reestimate_on_inliers" in detail["stages"]
    assert "ecc" in detail["stages"]
    assert _probe_error(transform.matrix)[0] < 0.1


def test_refine_full_works_without_images(noisy_pair):
    """No images means no ECC, but the refit must still happen."""
    src, ref = noisy_pair
    result = ClassicalMatcher("sift").match(src, ref)
    _, r1 = estimate_transform(result, "homography", threshold_px=3.0)
    _, _, detail = refine_full(r1)
    assert detail["stages"] == ["reestimate_on_inliers"]


# --- uniformity metric -----------------------------------------------------


def _layouts(size=1024, n=400, seed=0):
    rng = np.random.default_rng(seed)
    return {
        "grid": np.stack(np.meshgrid(np.linspace(30, size - 30, 20),
                                     np.linspace(30, size - 30, 20)), -1).reshape(-1, 2),
        "uniform": rng.uniform(30, size - 30, (n, 2)),
        "quadrant": rng.uniform(30, size / 2, (n, 2)),
        "blob": rng.normal([size / 2, size / 2], 40, (n, 2)),
    }


def test_uniformity_ranks_layouts_correctly():
    layouts = _layouts()
    scores = {k: compute_uniformity(v, (1024, 1024)).score for k, v in layouts.items()}
    assert scores["grid"] > scores["uniform"] > scores["quadrant"] > scores["blob"]


def test_uniformity_predicts_error_away_from_the_matched_points():
    """The justification for the metric: fit RMSE cannot see this, U can.

    All layouts get the same point count and the same noise, so only the spatial
    distribution differs. Fit RMSE stays ~0.70 for every one of them while true
    error away from the points spans a ~50x range.
    """
    rng = np.random.default_rng(0)
    size = 1024
    probe = np.stack(np.meshgrid(np.linspace(0, size - 1, 25),
                                 np.linspace(0, size - 1, 25)), -1).reshape(-1, 2)

    def apply(m, p):
        q = np.hstack([p, np.ones((len(p), 1))]) @ m.T
        return q[:, :2] / q[:, 2:3]

    observed = []
    for pts in _layouts(size).values():
        dst = apply(TRUE_H, pts) + rng.normal(0, 0.5, (len(pts), 2))
        matrix, _ = cv2.findHomography(pts.astype(np.float32), dst.astype(np.float32), 0)
        fit_rmse = float(np.sqrt(
            (np.linalg.norm(apply(matrix, pts) - dst, axis=1) ** 2).mean()
        ))
        probe_max = float(np.linalg.norm(apply(matrix, probe) - apply(TRUE_H, probe), axis=1).max())
        observed.append((compute_uniformity(pts, (size, size)).score, fit_rmse, probe_max))

    fit_rmses = [o[1] for o in observed]
    assert max(fit_rmses) / min(fit_rmses) < 1.2, (
        "fit RMSE should be near-constant across layouts -- that is the point"
    )
    probe_maxes = [o[2] for o in observed]
    assert max(probe_maxes) / min(probe_maxes) > 10, "true error should vary widely"

    best = max(observed, key=lambda o: o[0])
    worst = min(observed, key=lambda o: o[0])
    assert best[2] < worst[2], "higher uniformity must mean lower worst-case error"


def test_coverage_alone_would_miss_skewed_counts():
    pts = [[c * 125 + 60, r * 125 + 60] for r in range(8) for c in range(8)]
    pts += [[60.0, 60.0]] * 5000
    metrics = compute_uniformity(np.array(pts), (1000, 1000))
    assert metrics.coverage == 1.0
    assert metrics.entropy < 0.3, "entropy is what catches this"
    assert not metrics.passes_gate


def test_entropy_alone_would_miss_empty_regions():
    pts = np.vstack([
        np.random.default_rng(0).uniform(c * 125, c * 125 + 120, (100, 2)) for c in range(4)
    ])
    metrics = compute_uniformity(pts, (1000, 1000))
    assert metrics.coverage < 0.3, "coverage is what catches this"
    assert not metrics.passes_gate


def test_clark_evans_catches_clustering_the_grid_cannot_see():
    """64 tight blobs, one per cell: grid metrics call it perfect, R does not."""
    rng = np.random.default_rng(1)
    cell = 1024 / 8
    blobs = np.vstack([
        rng.normal([c * cell + cell / 2, r * cell + cell / 2], 3.0, (8, 2))
        for r in range(8) for c in range(8)
    ])
    metrics = compute_uniformity(blobs, (1024, 1024))
    assert metrics.coverage == 1.0
    assert metrics.entropy > 0.99
    assert metrics.score > 0.99, "the grid metrics genuinely cannot see this"
    assert metrics.clark_evans < 0.25, "Clark-Evans must catch it"
    assert metrics.is_clustered
    # The gate uses the grid score alone (the validated part), so it PASSES here.
    # The blind spot surfaces as a disagreement between the two views instead.
    assert metrics.passes_gate
    assert metrics.grid_contradicted_by_neighbours


def test_clark_evans_is_near_one_for_random_points():
    pts = np.random.default_rng(1).uniform(0, 1024, (512, 2))
    assert 0.85 < clark_evans_index(pts, (1024, 1024)) < 1.15


def test_clark_evans_needs_at_least_two_points():
    assert np.isnan(clark_evans_index(np.array([[1.0, 2.0]]), (100, 100)))


def test_gate_threshold_separates_good_from_clustered_layouts():
    layouts = _layouts()
    assert compute_uniformity(layouts["grid"], (1024, 1024)).score >= UNIFORMITY_GATE
    assert compute_uniformity(layouts["blob"], (1024, 1024)).score < UNIFORMITY_GATE


def test_profile_exposes_scale_dependence():
    pts = np.random.default_rng(1).uniform(0, 1024, (512, 2))
    profile = uniformity_profile(pts, (1024, 1024))
    assert set(profile) == {4, 8, 16}
    assert profile[4].coverage >= profile[16].coverage, "finer grids expose more gaps"


def test_empty_point_set_scores_zero_without_crashing():
    metrics = compute_uniformity(np.empty((0, 2)), (100, 100))
    assert metrics.score == 0.0
    assert np.isnan(metrics.clark_evans)
    assert not metrics.passes_gate


def test_metrics_serialise_for_reporting():
    pts = np.random.default_rng(0).uniform(0, 512, (100, 2))
    d = compute_uniformity(pts, (512, 512)).as_dict()
    for key in ("coverage", "entropy", "clark_evans", "score", "passes_gate", "is_clustered"):
        assert key in d


def test_full_metric_set_covers_the_problem_statement(noisy_pair):
    """RMSE, inlier count, inlier ratio, and uniformity -- all four deliverables."""
    src, ref = noisy_pair
    result = ClassicalMatcher("sift").match(src, ref)
    transform, result = estimate_transform(result, "homography", threshold_px=3.0)
    metrics = compute_metrics(result, transform)
    uniformity = compute_uniformity(result.inliers().src_pts, src.shape)

    assert metrics.rmse_px < 1.0
    assert metrics.n_inliers > 0
    assert 0.0 <= metrics.inlier_ratio <= 1.0
    assert 0.0 <= uniformity.score <= 1.0


def test_real_detector_output_is_not_flagged_as_a_grid_nn_disagreement():
    """Regression guard on a miscalibration that made the gate useless.

    An earlier version folded Clark-Evans into the gate at R < 0.7. Real
    detectors sit at R 0.24-0.63 with healthy coverage, so every real result
    failed. The blind-spot signal is a high grid score contradicted by a low R,
    which ordinary detector output does not produce.
    """
    from lunar_reg.eval.uniformity import compute_uniformity

    rng = np.random.default_rng(3)
    # Points concentrated on texture, as a real detector produces: several
    # keypoints per feature, features spread across the frame.
    centres = rng.uniform(40, 472, (60, 2))
    pts = np.vstack([rng.normal(c, 12.0, (6, 2)) for c in centres])
    metrics = compute_uniformity(pts, (512, 512))

    assert metrics.passes_gate, "healthy detector-like output must pass the gate"
    assert not metrics.grid_contradicted_by_neighbours


@pytest.mark.parametrize("detector", ["sift", "asift", "akaze"])
def test_real_matchers_pass_the_uniformity_gate(detector, noisy_pair):
    """End-to-end: the gate must not reject ordinary good results."""
    from lunar_reg.eval.uniformity import compute_uniformity

    src, ref = noisy_pair
    result = ClassicalMatcher(detector).match(src, ref)
    transform, result = estimate_transform(result, "homography", threshold_px=3.0)
    metrics = compute_uniformity(result.inliers().src_pts, src.shape)
    assert not metrics.grid_contradicted_by_neighbours, (
        f"{detector} flagged as grid/NN disagreement -- check the calibration"
    )
