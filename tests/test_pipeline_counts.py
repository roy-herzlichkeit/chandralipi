"""register_pair keeps raw counts, refits at the refit threshold and classifies every stage."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from lunar_reg.match.base import MatchResult
from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

H = np.array([[1.01, 0.02, 12.0], [-0.015, 0.99, -7.0], [1e-5, -2e-5, 1.0]])


def _texture(seed: int) -> np.ndarray:
    noise = np.random.default_rng(seed).normal(0, 1, (400, 400)).astype(np.float32)
    blurred = cv2.GaussianBlur(noise, (0, 0), 2.0)
    scaled = (blurred - blurred.min()) / (blurred.max() - blurred.min())
    return (scaled * 255).astype(np.uint8)


@pytest.fixture
def images():
    return _texture(3), _texture(4)


def _exact_plus_outliers(n_in: int = 60, n_out: int = 40, seed: int = 11) -> MatchResult:
    """``n_in`` correspondences exact under ``H`` followed by ``n_out`` random outliers."""
    rng = np.random.default_rng(seed)
    src_in = rng.uniform(10, 390, (n_in, 2))
    hom = np.c_[src_in, np.ones(n_in)] @ H.T
    dst_in = hom[:, :2] / hom[:, 2:3]
    src_out = rng.uniform(10, 390, (n_out, 2))
    dst_out = rng.uniform(10, 390, (n_out, 2))
    return MatchResult(
        np.vstack([src_in, src_out]),
        np.vstack([dst_in, dst_out]),
        matcher="stub",
        meta={"detector": "stub", "n_keypoints": (100, 100)},
    )


class _Stub:
    name = "stub"

    def __init__(self, result: MatchResult) -> None:
        self._result = result

    def match(self, source, reference) -> MatchResult:
        return self._result


def _use_stub(monkeypatch, result: MatchResult) -> None:
    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: _Stub(result))


def test_counts_are_over_the_raw_set(monkeypatch, images):
    raw = _exact_plus_outliers()
    _use_stub(monkeypatch, raw)
    out = register_pair(*images, "p", PipelineConfig(matcher="stub", use_ecc=False, n_bootstrap=0))
    assert out.status is RunStatus.OK, out.detail
    m = out.result.metrics
    assert m["n_matches"] == 100
    assert m["n_ransac_inliers"] >= 60
    assert m["n_inliers"] <= m["n_ransac_inliers"]
    assert m["inlier_ratio"] == pytest.approx(m["n_inliers"] / 100)
    assert out.result.src_pts.shape == (100, 2)
    assert out.result.inlier_mask[:60].all()
    assert raw.inlier_mask is None, "the matcher's result must not be written"
    assert out.extra["stage"] == "done"
    assert out.extra["n_raw_matches"] == 100
    assert out.result.extra["matcher_detector"] == "stub"
    assert "matcher_n_keypoints" not in out.result.extra  # tuples are not scalars


def test_refit_uses_the_refit_threshold(monkeypatch, images):
    import lunar_reg.align.refine as refine

    _use_stub(monkeypatch, _exact_plus_outliers())
    seen: dict = {}
    real = refine.refine_full

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(refine, "refine_full", spy)
    config = PipelineConfig(
        matcher="stub", use_ecc=False, n_bootstrap=0, refit_threshold_px=0.6, seed=4, nodata=0.0
    )
    out = register_pair(*images, "p", config)
    assert out.ok, out.detail
    assert seen["threshold_px"] == 0.6
    assert seen["seed"] == 4
    assert seen["ecc_kwargs"]["nodata"] == 0.0
    assert seen["ecc_kwargs"]["max_shift_px"] == config.ecc_max_shift_px
    assert out.result.extra["refit_threshold_px"] == 0.6


def test_refine_raising_is_refinement_failed(monkeypatch, images):
    import lunar_reg.align.refine as refine

    _use_stub(monkeypatch, _exact_plus_outliers())

    def boom(*args, **kwargs):
        raise ValueError("degenerate refit")

    monkeypatch.setattr(refine, "refine_full", boom)
    out = register_pair(*images, "p", PipelineConfig(matcher="stub"))
    assert out.status is RunStatus.REFINEMENT_FAILED
    assert out.extra["stage"] == "refine"
    assert out.detail == "ValueError: degenerate refit"
    assert out.extra["n_raw_matches"] == 100 and out.extra["n_ransac_inliers"] >= 60


def test_after_refit_gate(monkeypatch, images):
    import lunar_reg.align.refine as refine

    _use_stub(monkeypatch, _exact_plus_outliers())
    real = refine.refine_full

    def keep_three(result, *args, **kwargs):
        transform, refit, detail = real(result, *args, **kwargs)
        mask = np.zeros(len(refit), dtype=bool)
        mask[:3] = True
        refit.inlier_mask = mask
        return transform, refit, detail

    monkeypatch.setattr(refine, "refine_full", keep_three)
    out = register_pair(*images, "p", PipelineConfig(matcher="stub", use_ecc=False, min_inliers=8))
    assert out.status is RunStatus.TOO_FEW_INLIERS
    assert out.detail.startswith("after refit: 3 of ")
    assert out.extra["stage"] == "refine" and out.extra["n_refit_inliers"] == 3


def test_eval_raising_is_eval_failed(monkeypatch, images):
    import lunar_reg.eval.uniformity as uniformity

    _use_stub(monkeypatch, _exact_plus_outliers())

    def boom(*args, **kwargs):
        raise RuntimeError("uniformity broke")

    monkeypatch.setattr(uniformity, "compute_uniformity", boom)
    out = register_pair(*images, "p", PipelineConfig(matcher="stub", use_ecc=False, n_bootstrap=0))
    assert out.status is RunStatus.EVAL_FAILED
    assert out.extra["stage"] == "eval" and "uniformity broke" in out.detail


def test_empty_reason_reaches_the_detail():
    blank = np.zeros((128, 128), np.uint8)
    out = register_pair(blank, blank, "blank", PipelineConfig(matcher="sift", preprocess="none"))
    assert out.status is RunStatus.TOO_FEW_MATCHES
    assert "reason: too_few_keypoints" in out.detail
    assert out.extra["n_raw_matches"] == 0 and out.extra["stage"] == "match"
