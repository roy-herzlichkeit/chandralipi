"""Q-P1.19-3, human decision (b): an input with no information skips the preset.

The preset is skipped for both images, matching classifies the pair, and
``extra["preprocess_skipped"]`` says why. A preset that turns an informative
input into a degenerate output is still ``PREPROCESS_FAILED``.
"""

from __future__ import annotations

import cv2
import numpy as np

from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair


def _textured(seed: int = 7, shape=(256, 256)) -> np.ndarray:
    g = np.random.default_rng(seed).normal(0, 1, shape).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 2.0)
    return (1 + (g - g.min()) / (g.max() - g.min()) * 250).astype(np.uint8)


def test_blank_pair_skips_the_preset_and_fails_at_matching():
    blank = np.zeros((128, 128), np.uint8)
    out = register_pair(blank, blank, "blank", PipelineConfig(matcher="sift"))
    assert PipelineConfig().preprocess != "none", "the default preset is what this guards"
    assert out.status is RunStatus.TOO_FEW_MATCHES
    assert out.extra["stage"] == "match"
    assert out.extra["preprocess"] == PipelineConfig().preprocess
    assert out.extra["preprocess_skipped"].startswith("degenerate_input: source:")


def test_one_blank_side_skips_the_preset_for_both():
    blank = np.zeros((256, 256), np.uint8)
    out = register_pair(_textured(), blank, "half", PipelineConfig(matcher="sift"))
    assert out.status is RunStatus.TOO_FEW_MATCHES
    assert "reference:" in out.extra["preprocess_skipped"]


def test_all_nan_or_masked_input_is_degenerate():
    img = _textured().astype(np.float32)
    nan = np.full(img.shape, np.nan, np.float32)
    out = register_pair(img, nan, "nan", PipelineConfig(matcher="sift"))
    assert "reference: no valid pixel" in out.extra["preprocess_skipped"]
    masked = register_pair(
        img, img, "masked", PipelineConfig(matcher="sift"),
        source_valid=np.zeros(img.shape, bool),
    )  # fmt: skip
    assert "source: no valid pixel" in masked.extra["preprocess_skipped"]


def test_preset_failure_on_informative_input_is_still_preprocess_failed(monkeypatch):
    from lunar_reg.preprocess import presets

    def degenerate(name, source, reference, **kw):
        return presets.PresetOutcome(False, None, None, "source: output_check: degenerate", [], [])

    monkeypatch.setattr(presets, "apply_preset", degenerate)
    img = _textured()
    out = register_pair(img, img, "bad_preset", PipelineConfig(matcher="sift"))
    assert out.status is RunStatus.PREPROCESS_FAILED
    assert out.extra["stage"] == "preprocess"
    assert "preprocess_skipped" not in out.extra


def test_informative_pair_runs_the_preset(monkeypatch):
    from lunar_reg.preprocess import presets

    calls = []
    real = presets.apply_preset

    def spy(*args, **kwargs):
        calls.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(presets, "apply_preset", spy)
    img = _textured()
    ref = np.roll(img, (3, 5), axis=(0, 1))
    out = register_pair(
        img, ref, "ok", PipelineConfig(matcher="sift", use_ecc=False, n_bootstrap=0)
    )
    assert calls == [PipelineConfig().preprocess]
    assert out.ok, out.detail
    assert "preprocess_skipped" not in out.result.extra
    assert out.result.extra["preprocess"] == PipelineConfig().preprocess
