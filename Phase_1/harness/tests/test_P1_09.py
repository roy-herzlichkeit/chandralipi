"""P1.09 — preprocess outcomes, pixel transforms, measured GSD (Phase_1/LLD/preprocess_geometry.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest


def test_step_status_members():
    from lunar_reg.preprocess.pipeline import StepStatus

    assert {m.value for m in StepStatus} == {"ran", "skipped_missing_input", "noop", "failed",
                                             "degenerate_output"}


def test_resample_pixel_transform():
    from lunar_reg.preprocess.config import minimal_config
    from lunar_reg.preprocess.pipeline import PreprocessContext, run_pipeline

    cfg = minimal_config()
    cfg.resample = True
    cfg.target_gsd_m = 2.0
    img = np.random.default_rng(0).uniform(1, 255, (80, 100)).astype(np.float32)
    res = run_pipeline(img, cfg, PreprocessContext(src_gsd_m=1.0))
    assert res.image.shape == (40, 50)
    p = res.pixel_transform @ np.array([49.5, 39.5, 1.0])
    assert p[:2] / p[2] == pytest.approx((24.5, 19.5))


def test_cube_without_reduction_fails_not_raises():
    from lunar_reg.preprocess.config import PreprocessConfig
    from lunar_reg.preprocess.pipeline import PreprocessContext, StepStatus, run_pipeline

    cfg = PreprocessConfig(band_reduction=False, resample=False, clahe=True, normalize=True,
                           shadow=False)
    cube = np.random.default_rng(0).uniform(1, 255, (3, 20, 30)).astype(np.float32)
    res = run_pipeline(cube, cfg, PreprocessContext())
    assert res.failed
    assert any(r.status is StepStatus.FAILED for r in res.history)


def test_reference_side_and_nominal_fallback():
    from lunar_reg.preprocess.config import PreprocessConfig
    from lunar_reg.preprocess.pipeline import PreprocessContext, run_pipeline

    img = np.ones((40, 40), np.float32) * 5
    img[5:10, 5:10] = 50
    cfg = PreprocessConfig(resample=True, normalize=False, clahe=False, shadow=False,
                           band_reduction=False, target_gsd_m=2.0, side="reference")
    res = run_pipeline(img, cfg, PreprocessContext(ref_gsd_m=1.0, src_gsd_m=4.0))
    assert res.image.shape == (20, 20)
    cfg2 = PreprocessConfig(resample=True, normalize=False, clahe=False, shadow=False,
                            band_reduction=False, target_gsd_m=1.0, source_sensor="OHRC")
    res2 = run_pipeline(img, cfg2, PreprocessContext())
    rec = next(r for r in res2.history if r.name == "resample")
    assert rec.detail.get("gsd_source") == "nominal"


def test_valid_mask_honoured_by_normalize():
    from lunar_reg.preprocess.config import minimal_config
    from lunar_reg.preprocess.pipeline import PreprocessContext, run_pipeline

    img = np.random.default_rng(2).uniform(10, 900, (40, 50)).astype(np.float32)
    img[:, :5] = 0
    res = run_pipeline(img, minimal_config(), PreprocessContext(valid=img > 0))
    assert (res.image[:, :5] == 0).all()


def test_step_exception_classified(monkeypatch):
    from lunar_reg.preprocess import pipeline as pp
    from lunar_reg.preprocess.config import minimal_config

    def boom(image, config, context):
        raise RuntimeError("step broke")

    monkeypatch.setitem(pp._HANDLERS, "normalize", boom)
    res = pp.run_pipeline(np.ones((10, 10), np.float32), minimal_config(), pp.PreprocessContext())
    rec = next(r for r in res.history if r.name == "normalize")
    assert rec.status is pp.StepStatus.FAILED and "step broke" in rec.reason


def test_sensor_gsd_provenance():
    from lunar_reg.constants import SENSORS
    from lunar_reg.provenance import ValueSource

    assert all(s.gsd_source is ValueSource.DOCUMENTED for s in SENSORS.values())
    assert "1.0" in SENSORS["LRO_NAC"].gsd_note
