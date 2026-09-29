"""P0.09 — counts, refit threshold, classification (Phase_0/LLD/pipeline_counts.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h0 import exact_matches, textured


class _Stub:
    def __init__(self, result):
        self.name = "stub"
        self._result = result

    def match(self, source, reference):
        return self._result


@pytest.fixture
def images():
    return textured((400, 400), seed=3), textured((400, 400), seed=4)


def _use(monkeypatch, result):
    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: _Stub(result))


def test_counts_over_raw_set(monkeypatch, images):
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    raw, _ = exact_matches(n_in=60, n_out=40)
    _use(monkeypatch, raw)
    out = register_pair(*images, "p", PipelineConfig(matcher="stub", use_ecc=False, n_bootstrap=0))
    assert out.status is RunStatus.OK, out.detail
    r, m = out.result, out.result.metrics
    assert r.n_matches == 100 and m["n_matches"] == 100
    assert 60 <= m["n_ransac_inliers"] <= 100
    assert m["n_inliers"] <= m["n_ransac_inliers"]
    assert m["inlier_ratio"] == pytest.approx(m["n_inliers"] / 100)
    assert m["ransac_inlier_ratio"] == pytest.approx(m["n_ransac_inliers"] / 100)
    assert m["residual_basis"] == "self_residual"
    assert "self_residual_subpixel" in m and "is_subpixel" not in m
    assert len(r.inlier_mask) == 100 and r.inlier_mask.sum() == m["n_inliers"]
    for key in ("refit_threshold_px", "ransac_threshold_px", "min_inliers", "model", "seed",
                "refine_stages", "ecc_status", "cv2_version", "numpy_version"):
        assert key in r.extra, key
    assert out.extra["stage"] == "done"


def test_refit_threshold_used(monkeypatch, images):
    import lunar_reg.align.refine as refine
    from lunar_reg.pipeline import PipelineConfig, register_pair

    raw, _ = exact_matches()
    _use(monkeypatch, raw)
    seen = {}
    real = refine.refine_full

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(refine, "refine_full", spy)
    register_pair(*images, "p", PipelineConfig(matcher="stub", use_ecc=False, n_bootstrap=0,
                                               refit_threshold_px=0.75, seed=9))
    assert seen["threshold_px"] == 0.75 and seen["seed"] == 9


def test_refine_raises(monkeypatch, images):
    import lunar_reg.align.refine as refine
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    raw, _ = exact_matches()
    _use(monkeypatch, raw)

    def boom(*a, **k):
        raise ValueError("degenerate refit")

    monkeypatch.setattr(refine, "refine_full", boom)
    out = register_pair(*images, "p", PipelineConfig(matcher="stub"))
    assert out.status is RunStatus.REFINEMENT_FAILED
    assert out.extra["stage"] == "refine" and "degenerate refit" in out.detail
    assert out.extra["n_raw_matches"] == 100 and "n_ransac_inliers" in out.extra


def test_after_refit_gate(monkeypatch, images):
    import lunar_reg.align.refine as refine
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    raw, _ = exact_matches()
    _use(monkeypatch, raw)
    real = refine.refine_full

    def starve(result, *a, **k):
        transform, res, detail = real(result, *a, **k)
        mask = np.zeros(len(res), bool)
        mask[:3] = True
        res.inlier_mask = mask
        transform.n_inliers = 3
        return transform, res, detail

    monkeypatch.setattr(refine, "refine_full", starve)
    out = register_pair(*images, "p", PipelineConfig(matcher="stub", use_ecc=False, min_inliers=8))
    assert out.status is RunStatus.TOO_FEW_INLIERS
    assert out.detail.startswith("after refit") and out.extra["stage"] == "refine"


def test_eval_raises(monkeypatch, images):
    import lunar_reg.eval.uniformity as uniformity
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    raw, _ = exact_matches()
    _use(monkeypatch, raw)

    def boom(*a, **k):
        raise RuntimeError("uniformity broke")

    monkeypatch.setattr(uniformity, "compute_uniformity", boom)
    out = register_pair(*images, "p", PipelineConfig(matcher="stub", use_ecc=False, n_bootstrap=0))
    assert out.status is RunStatus.EVAL_FAILED and out.extra["stage"] == "eval"


def test_matcher_error_classified(monkeypatch, images):
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    class Bad:
        name = "bad"

        def match(self, s, r):
            raise RuntimeError("kaput")

    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: Bad())
    out = register_pair(*images, "p", PipelineConfig(matcher="bad"))
    assert out.status is RunStatus.MATCHER_ERROR and "RuntimeError: kaput" in out.detail


def test_empty_reason_in_detail():
    from lunar_reg.match.classical import ClassicalMatcher
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    blank = np.zeros((128, 128), np.uint8)
    empty = ClassicalMatcher("sift").match(blank, blank)
    assert empty.meta["empty_reason"] == "too_few_keypoints"
    assert empty.meta["n_keypoints_src"] == 0
    out = register_pair(blank, blank, "b", PipelineConfig(matcher="sift"))
    assert out.status is RunStatus.TOO_FEW_MATCHES and "too_few_keypoints" in out.detail


def test_metrics_dataclass():
    import dataclasses

    from lunar_reg.eval.metrics import RegistrationMetrics

    names = [f.name for f in dataclasses.fields(RegistrationMetrics)]
    assert names == ["n_matches", "n_ransac_inliers", "n_inliers", "inlier_ratio",
                     "ransac_inlier_ratio", "rmse_px", "mae_px", "median_px", "p95_px",
                     "max_px", "model", "matcher", "rmse_m", "residual_basis"]
    assert not hasattr(RegistrationMetrics, "is_subpixel")
