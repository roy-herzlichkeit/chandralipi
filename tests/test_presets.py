"""Preprocessing presets and their stage inside register_pair (LLD preprocess_presets.md §4)."""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.eval.scenes import illumination_pair
from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair
from lunar_reg.preprocess import presets
from lunar_reg.preprocess.presets import (
    PRESET_NAMES,
    PresetOutcome,
    apply_preset,
    choose_default_preset,
)


def _image(seed: int = 0, shape=(96, 96)) -> np.ndarray:
    return np.random.default_rng(seed).integers(1, 255, shape).astype(np.uint8)


def test_none_is_identity_on_uint8():
    src, ref = _image(0), _image(1)
    out = apply_preset("none", src, ref)
    assert out.ok and out.detail == ""
    assert np.array_equal(out.source, src) and np.array_equal(out.reference, ref)
    assert out.source is not src  # a copy, not the caller's array
    assert out.uses_placeholders == []


def test_none_stretches_float_input_to_uint8():
    src = np.linspace(0.0, 1.0, 64 * 64, dtype=np.float32).reshape(64, 64)
    out = apply_preset("none", src, src.copy(), nodata=None)
    assert out.ok and out.source.dtype == np.uint8 and out.source.shape == src.shape


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_preset_keeps_shape_dtype_and_zero_border(name):
    src, ref = _image(2), _image(3)
    src[:, :8] = 0
    ref[:6, :] = 0
    out = apply_preset(name, src, ref, nodata=0)
    assert out.ok, out.detail
    for got, img in ((out.source, src), (out.reference, ref)):
        assert got.dtype == np.uint8 and got.shape == img.shape
        assert (got[img == 0] == 0).all()
        assert (got[img != 0] > 0).mean() > 0.99


def test_preset_uses_given_masks_over_nodata():
    src, ref = _image(4), _image(5)
    valid = np.ones(src.shape, bool)
    valid[:, -10:] = False
    out = apply_preset("clahe_shadow", src, ref, source_valid=valid, nodata=None)
    assert out.ok, out.detail
    assert (out.source[:, -10:] == 0).all()
    assert (out.reference > 0).all()  # no mask, no nodata -> every pixel valid


def test_history_and_placeholders_recorded():
    src, ref = _image(6), _image(7)
    out = apply_preset("ohrc_nac", src, ref)
    assert out.ok, out.detail
    steps = {(h["side"], h["step"]) for h in out.history}
    for side in ("source", "reference"):
        for step in ("normalize", "clahe", "invert", "dilate"):
            assert (side, step) in steps
    assert all(set(h) == {"side", "step", "status", "reason"} for h in out.history)
    assert not {"georeference", "resample"} & {h["step"] for h in out.history}
    assert "clahe_clip_limit" in out.uses_placeholders
    assert out.uses_placeholders == sorted(out.uses_placeholders)
    assert "source:" in out.report()


def test_all_zero_image_is_degenerate():
    z = np.zeros((64, 64), np.uint8)
    out = apply_preset("clahe_shadow", z, _image(8, (64, 64)))
    assert out.ok is False
    assert out.source is None and out.reference is None
    assert "degenerate_output" in out.detail and out.detail.startswith("source:")


@pytest.mark.parametrize("name", PRESET_NAMES)
@pytest.mark.parametrize("nodata", [None, float("nan"), 0])
def test_nan_pixels_of_float_input_are_nodata(name, nodata):
    rng = np.random.default_rng(12)
    src = rng.random((64, 64)).astype(np.float32) + 0.1
    ref = rng.random((64, 64)).astype(np.float32) + 0.1
    src[:, :10] = np.nan
    ref[:5, :] = np.inf
    out = apply_preset(name, src, ref, nodata=nodata)
    assert out.ok, out.detail
    assert (out.source[:, :10] == 0).all()
    assert (out.reference[:5, :] == 0).all()
    assert (out.source[:, 10:] > 0).mean() > 0.99


@pytest.mark.parametrize("name", ["ohrc_nac", "clahe_shadow"])
def test_nan_under_given_mask_is_nodata(name):
    src = np.random.default_rng(13).random((64, 64)).astype(np.float32) + 0.1
    src[:8, :8] = np.nan
    valid = np.ones(src.shape, bool)  # claims the NaN block is valid
    out = apply_preset(name, src, src.copy(), source_valid=valid, reference_valid=valid)
    assert out.ok, out.detail
    assert (out.source[:8, :8] == 0).all() and (out.reference[:8, :8] == 0).all()


@pytest.mark.parametrize("name", ["ohrc_nac", "clahe_shadow"])
@pytest.mark.parametrize("value", [0, 100])
def test_flat_image_without_nodata_is_degenerate(name, value):
    flat = np.full((64, 64), value, np.uint8)
    out = apply_preset(name, flat, _image(14, (64, 64)), nodata=None)
    assert out.ok is False and out.source is None
    assert out.detail.startswith("source:") and "degenerate_output" in out.detail
    assert any(
        h["step"] == "output_check" and h["status"] == "degenerate_output" for h in out.history
    )


def test_register_pair_all_zero_source_default_nodata_skips_the_preset():
    """Q-P1.19-3 (b): an all-zero source has no information, so the preset is
    skipped and matching classifies the pair (no longer PREPROCESS_FAILED)."""
    src = np.zeros((128, 128), np.uint8)
    for name in ("ohrc_nac", "clahe_shadow"):
        cfg = PipelineConfig(matcher="sift", preprocess=name, n_bootstrap=0)
        assert cfg.nodata is None
        out = register_pair(src, _image(15, (128, 128)), "zz", cfg)
        assert out.status is RunStatus.TOO_FEW_MATCHES, (name, out.status, out.detail)
        assert out.extra["stage"] == "match"
        assert out.extra["preprocess_skipped"].startswith("degenerate_input: source:")


@pytest.mark.parametrize("nan", [True, False])
def test_register_pair_nan_input_gives_ecc_nodata_zero(monkeypatch, nan):
    from lunar_reg.align import refine

    seen: dict = {}
    pts = np.random.default_rng(17).uniform(10, 80, (40, 2))

    class _Matcher:
        def match(self, source, reference):
            from lunar_reg.match.base import MatchResult

            seen["matched"] = source
            return MatchResult(pts, pts.copy(), matcher="stub")

    def spy(first, **kw):
        seen["ecc_nodata"] = kw["ecc_kwargs"]["nodata"]
        raise RuntimeError("stop after capture")

    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name: _Matcher())
    monkeypatch.setattr(refine, "refine_full", spy)
    src = np.random.default_rng(16).random((96, 96)).astype(np.float32) + 0.1
    if nan:
        src[:, :12] = np.nan
    cfg = PipelineConfig(matcher="stub", preprocess="ohrc_nac", n_bootstrap=0)
    out = register_pair(src, src.copy(), "nan", cfg)
    assert out.status is RunStatus.REFINEMENT_FAILED, out.detail
    if nan:
        assert (seen["matched"][:, :12] == 0).all()
        assert seen["ecc_nodata"] == 0
    else:
        assert seen["ecc_nodata"] is None


def test_unknown_preset_raises():
    img = _image(9)
    with pytest.raises(ValueError, match="unknown preset"):
        apply_preset("nope", img, img)
    with pytest.raises(ValueError, match="unknown preset"):
        PipelineConfig(preprocess="nope")


def test_pipeline_config_default_is_none():
    # P1.19 sets the default from data/processed/ablation/ablation.json (G09).
    assert PipelineConfig().preprocess == "ohrc_nac"


def test_register_pair_preprocess_failure_is_classified(monkeypatch):
    def failing(name, source, reference, **kw):
        return PresetOutcome(False, None, None, "source: clahe: degenerate_output: x", [], [])

    monkeypatch.setattr(presets, "apply_preset", failing)
    src, ref, _, _ = illumination_pair(shape=(128, 128), seed=2)
    out = register_pair(src, ref, "pf", PipelineConfig(matcher="sift", preprocess="ohrc_nac"))
    assert out.status is RunStatus.PREPROCESS_FAILED
    assert out.extra["stage"] == "preprocess"
    assert out.extra["preprocess"] == "ohrc_nac"
    assert out.detail == "source: clahe: degenerate_output: x"


def test_register_pair_feeds_preprocessed_images_and_keeps_inputs(monkeypatch):
    seen: dict = {}
    real = presets.apply_preset

    def spy(name, source, reference, **kw):
        seen["kw"] = kw
        out = real(name, source, reference, **kw)
        seen["out"] = out
        return out

    class _Matcher:
        def match(self, source, reference):
            from lunar_reg.match.base import MatchResult

            seen["matched"] = source
            return MatchResult(np.zeros((0, 2)), np.zeros((0, 2)), matcher="stub")

    monkeypatch.setattr(presets, "apply_preset", spy)
    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name: _Matcher())
    src, ref = _image(10), _image(11)
    out = register_pair(src, ref, "pp", PipelineConfig(matcher="stub", preprocess="clahe_shadow"))
    assert out.status is RunStatus.TOO_FEW_MATCHES  # the stub returns nothing
    assert np.array_equal(seen["matched"], seen["out"].source)
    assert not np.array_equal(seen["matched"], src)
    assert seen["kw"]["nodata"] is None


def _abl(anchor, synthetic):
    return {
        "anchor": [
            {"preset": p, "matcher": m, "status": s, "n_inliers": n, "u_score": u}
            for p, m, s, n, u in anchor
        ],
        "synthetic": [
            {
                "preset": p,
                "matcher": "sift",
                "azimuth_delta_deg": 0,
                "seed": 0,
                "status": s,
                "truth_rms_px": t,
            }
            for p, s, t in synthetic
        ],
    }


def test_choose_default_clear_anchor_winner():
    abl = _abl(
        [
            ("none", "sift", "ok", 25, 0.8),
            ("ohrc_nac", "sift", "ok", 40, 0.9),
            ("ohrc_nac", "akaze", "ok", 30, 0.75),
            ("clahe_shadow", "sift", "ok", 10, 0.9),  # below the inlier target
            ("clahe_shadow", "akaze", "too_few_inliers", 50, 0.9),  # not ok
        ],
        [("none", "ok", 0.1), ("ohrc_nac", "ok", 0.5), ("clahe_shadow", "ok", 0.05)],
    )
    winner, reason = choose_default_preset(abl)
    assert winner == "ohrc_nac"
    assert reason == "anchor passes none=1 ohrc_nac=2 clahe_shadow=0; ohrc_nac wins on anchor"


def test_choose_default_anchor_tie_broken_by_synthetic():
    abl = _abl(
        [
            ("none", "sift", "ok", 25, 0.8),
            ("clahe_shadow", "sift", "ok", 30, 0.7),
            ("ohrc_nac", "sift", "ok", 30, 0.69),  # below the u_score target
        ],
        [
            ("none", "ok", 0.3),
            ("none", "ok", 0.5),
            ("clahe_shadow", "ok", 0.2),
            ("clahe_shadow", "estimation_failed", 0.0),  # not ok: ignored
            ("ohrc_nac", "ok", 0.01),  # not a candidate
        ],
    )
    winner, reason = choose_default_preset(abl)
    assert winner == "clahe_shadow"
    assert "none=0.4" in reason and "clahe_shadow=0.2" in reason


def test_choose_default_no_synthetic_row_ranks_last():
    abl = _abl(
        [("none", "sift", "ok", 25, 0.8), ("ohrc_nac", "sift", "ok", 25, 0.8)],
        [("ohrc_nac", "ok", 0.9)],
    )
    assert choose_default_preset(abl)[0] == "ohrc_nac"


def test_choose_default_full_tie_is_none():
    abl = _abl(
        [
            ("none", "sift", "ok", 5, 0.1),
            ("ohrc_nac", "sift", "ok", 5, 0.1),
            ("clahe_shadow", "sift", "ok", 5, 0.1),
        ],
        [],
    )
    winner, reason = choose_default_preset(abl)
    assert winner == "none"
    assert "-> none" in reason


def test_choose_default_tie_without_none_takes_first_in_order():
    abl = _abl(
        [("ohrc_nac", "sift", "ok", 25, 0.8), ("clahe_shadow", "sift", "ok", 25, 0.8)],
        [("ohrc_nac", "ok", 0.3), ("clahe_shadow", "ok", 0.3)],
    )
    assert choose_default_preset(abl)[0] == "ohrc_nac"


def test_choose_default_rejects_unknown_preset():
    abl = _abl([("mystery", "sift", "ok", 25, 0.8)], [])
    with pytest.raises(ValueError, match="unknown preset"):
        choose_default_preset(abl)
