"""P0.12 — evaluation correctness (Phase_0/LLD/eval_fixes.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest


def _budget(dist, fit):
    from lunar_reg.eval.error_budget import ErrorBudget

    b = ErrorBudget("sift", (100, 100))
    b.add("transform: distribution only", dist)
    b.add("transform: RANSAC fit", fit)
    return b


@pytest.mark.parametrize("dist,fit,expected", [
    (0.35, 0.40, "point distribution"),
    (0.10, 1.00, "correspondence error"),
    (0.30, 0.40, None),
])
def test_dominant_regimes(dist, fit, expected):
    b = _budget(dist, fit)
    assert b.dominant == expected
    shares = b.shares
    assert shares["distribution_px"] == pytest.approx(dist)
    assert shares["correspondence_px"] == pytest.approx(np.sqrt(max(fit**2 - dist**2, 0)))
    assert "correspondence" in b.report()


def _points(n=40, seed=0, model="homography"):
    rng = np.random.default_rng(seed)
    src = rng.uniform(0, 500, (n, 2))
    if model == "homography":
        H = np.array([[1.01, 0.02, 3.0], [-0.01, 0.99, 2.0], [1e-5, 0, 1.0]])
        h = np.c_[src, np.ones(n)] @ H.T
        dst = h[:, :2] / h[:, 2:3]
    else:
        dst = src @ np.array([[1.0, 0.01], [-0.01, 1.0]]).T + (3.0, 2.0)
    return src, dst + rng.normal(0, 0.3, dst.shape)


@pytest.mark.parametrize("model", ["homography", "affine", "partial_affine"])
def test_conditioning_map_matches_headline(model):
    from lunar_reg.eval.conditioning import bootstrap_conditioning, conditioning_map

    src, dst = _points(model=model)
    metrics = bootstrap_conditioning(src, dst, (500, 500), model=model, n_bootstrap=30,
                                     probe_n=12, seed=4)
    cmap = conditioning_map(src, dst, (500, 500), model=model, n_bootstrap=30, probe_n=12,
                            seed=4)
    assert cmap.shape == (12, 12)
    assert float(cmap.max()) == pytest.approx(metrics.max_px, abs=1e-9)
    assert metrics.estimator == "lsq"
    assert metrics.as_dict()["gate_source"] == "inferred"


def test_conditioning_failures_counted():
    from lunar_reg.eval.conditioning import conditioning_map_with_failures

    src = np.ones((5, 2))  # identical points: every refit is degenerate
    cmap, n_failed = conditioning_map_with_failures(src, src, (10, 10), model="homography",
                                                    n_bootstrap=10, probe_n=4, seed=0)
    assert n_failed > 0
    assert cmap.shape == (4, 4)


def test_uniformity_small_sets_can_pass():
    from lunar_reg.eval.uniformity import UNIFORMITY_GATE, compute_uniformity

    cells = [(c * 64 + 32, r * 64 + 32) for r in range(8) for c in range(8)]
    pts = np.array(cells[::3][:20], dtype=float)  # 20 points, each in its own cell
    m = compute_uniformity(pts, (512, 512))
    assert m.coverage == pytest.approx(1.0)
    assert m.score >= 0.99 >= UNIFORMITY_GATE
    assert m.max_occupiable_cells == 20
    assert m.as_dict()["gate_source"] == "inferred"


def test_uniformity_out_of_frame_counted():
    from lunar_reg.eval.uniformity import cell_counts, compute_uniformity

    pts = np.array([[10.0, 10.0], [-5.0, 10.0], [600.0, 10.0], [100.0, 100.0]])
    m = compute_uniformity(pts, (512, 512))
    assert m.n_out_of_frame == 2 and m.n_points == 2
    assert cell_counts(pts, (512, 512)).sum() == 2


def test_oracle_uses_pipeline_model():
    from lunar_reg.eval.error_budget import attribute_error
    from lunar_reg.eval.scenes import illumination_pair

    src, ref, H, _ = illumination_pair(shape=(256, 256), seed=1, source_sun=(300, 30),
                                       reference_sun=(300, 30))
    budget = attribute_error(src, ref, H, matcher_name="sift", model="affine", use_ecc=False)
    assert budget.failed is None
    stage = next(s for s in budget.stages if s.stage == "transform: distribution only")
    assert stage.rmse_px is not None
    assert "affine" in stage.note and "least squares" in stage.note


def test_preprocessing_sweep_chains_are_uint8():
    from lunar_reg.eval import error_budget

    src = (np.random.default_rng(0).uniform(0, 1, (64, 64)) * 1000).astype(np.float32)
    text = open(error_budget.__file__).read()
    assert "to_uint8(normalize_intensity(" in text and "to_uint8(normalize_shadows(" in text
    assert src.dtype == np.float32
