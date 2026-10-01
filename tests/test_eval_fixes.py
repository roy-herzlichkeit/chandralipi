"""Evaluation correctness: dominant stage, one bootstrap core, adaptive uniformity, oracle model."""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.eval.conditioning import (
    bootstrap_conditioning,
    conditioning_map,
    conditioning_map_with_failures,
)
from lunar_reg.eval.error_budget import ErrorBudget, attribute_error
from lunar_reg.eval.uniformity import (
    UNIFORMITY_GATE,
    cell_counts,
    compute_uniformity,
    uniformity_profile,
)

SHAPE = (500, 500)


def _budget(dist: float, fit: float) -> ErrorBudget:
    budget = ErrorBudget("sift", (100, 100))
    budget.add("transform: distribution only", dist)
    budget.add("transform: RANSAC fit", fit)
    return budget


@pytest.mark.parametrize(
    "dist,fit,corr,expected",
    [
        (0.35, 0.40, 0.194, "point distribution"),
        (0.10, 1.00, 0.995, "correspondence error"),
        (0.30, 0.40, 0.265, None),  # ratio 1.13: inside the not-resolved band
    ],
)
def test_dominant_compares_distribution_with_correspondence_share(dist, fit, corr, expected):
    budget = _budget(dist, fit)
    assert budget.shares["correspondence_px"] == pytest.approx(corr, abs=5e-4)
    assert budget.shares["distribution_px"] == dist
    assert budget.dominant == expected
    report = budget.report()
    assert "distribution" in report and "correspondence" in report


def test_dominant_is_none_without_both_stages():
    budget = ErrorBudget("sift", (100, 100))
    budget.add("transform: RANSAC fit", 1.0)
    assert budget.dominant is None
    assert budget.shares == {"distribution_px": None, "correspondence_px": None}


def _points(model: str, n: int = 40, seed: int = 0):
    rng = np.random.default_rng(seed)
    src = rng.uniform(0, 500, (n, 2))
    if model == "homography":
        H = np.array([[1.01, 0.02, 3.0], [-0.01, 0.99, 2.0], [1e-5, 0.0, 1.0]])
        hom = np.c_[src, np.ones(n)] @ H.T
        dst = hom[:, :2] / hom[:, 2:3]
    else:
        dst = src @ np.array([[1.0, 0.01], [-0.01, 1.0]]).T + (3.0, 2.0)
    return src, dst + rng.normal(0, 0.3, dst.shape)


@pytest.mark.parametrize("model", ["homography", "affine", "partial_affine"])
def test_conditioning_map_max_equals_headline_max(model):
    src, dst = _points(model)
    metrics = bootstrap_conditioning(
        src, dst, SHAPE, model=model, n_bootstrap=30, probe_n=12, seed=4
    )
    cmap = conditioning_map(src, dst, SHAPE, model=model, n_bootstrap=30, probe_n=12, seed=4)
    assert cmap.shape == (12, 12)
    assert np.isfinite(cmap).all()
    assert float(cmap.max()) == pytest.approx(metrics.max_px, abs=1e-9)
    assert metrics.estimator == "lsq" and metrics.n_failed_refits == 0
    assert metrics.as_dict()["gate_source"] == "inferred"


def test_degenerate_refits_are_counted():
    same = np.ones((6, 2))
    for model in ("homography", "affine", "partial_affine"):
        cmap, n_failed = conditioning_map_with_failures(
            same, same, (10, 10), model=model, n_bootstrap=10, probe_n=4, seed=0
        )
        assert n_failed == 10, model
        assert cmap.shape == (4, 4) and np.isinf(cmap).all()


def test_well_spread_twenty_points_can_pass_the_gate():
    centres = [(c * 64 + 32, r * 64 + 32) for r in range(8) for c in range(8)]
    pts = np.array(centres[::3][:20], dtype=float)
    metrics = compute_uniformity(pts, (512, 512))
    assert metrics.grid == 4 and metrics.total_cells == 16
    assert metrics.score >= 0.9 >= UNIFORMITY_GATE
    assert metrics.as_dict()["gate_source"] == "inferred"


def test_twenty_points_in_one_quadrant_fail():
    pts = np.random.default_rng(0).uniform(0, 256, (20, 2))
    assert compute_uniformity(pts, (512, 512)).score < 0.5


def test_large_sets_keep_the_requested_grid():
    pts = np.random.default_rng(1).uniform(0, 512, (400, 2))
    metrics = compute_uniformity(pts, (512, 512))
    assert metrics.grid == 8 and metrics.total_cells == 64
    assert {g: m.grid for g, m in uniformity_profile(pts[:20], (512, 512)).items()} == {
        4: 4,
        8: 8,
        16: 16,
    }


def test_out_of_frame_points_are_counted_not_binned():
    pts = np.array([[10.0, 10.0], [-5.0, 10.0], [600.0, 10.0], [100.0, 100.0], [10.0, 512.0]])
    metrics = compute_uniformity(pts, (512, 512))
    assert metrics.n_out_of_frame == 3 and metrics.n_points == 2
    assert cell_counts(pts, (512, 512)).sum() == 2


def test_oracle_fit_uses_the_pipeline_model():
    from lunar_reg.eval.scenes import illumination_pair

    src, ref, H, _ = illumination_pair(
        shape=(256, 256), seed=1, source_sun=(300, 30), reference_sun=(300, 30)
    )
    budget = attribute_error(src, ref, H, matcher_name="sift", model="affine", use_ecc=False)
    assert budget.failed is None
    stage = next(s for s in budget.stages if s.stage == "transform: distribution only")
    assert stage.note == "oracle fit: affine least squares"
    assert stage.rmse_px is not None and np.isfinite(stage.rmse_px)
    refined = next(s for s in budget.stages if s.stage == "transform: after refinement")
    assert "ecc skipped_disabled" in refined.note
