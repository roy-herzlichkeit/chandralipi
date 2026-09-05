"""The VRAM budget model is what stops the pipeline OOMing; check it holds."""

from __future__ import annotations

import pytest

from lunar_reg import device


def test_dense_cost_is_between_quadratic_and_quartic():
    """The model has two terms, and the exponent must sit between them.

    Replaces an earlier test asserting a clean 16x over a doubled side. That
    assertion held only because the model was pure S^4, which measurement
    disproved: below ~900 px the S^2 backbone term dominates, so a doubled side
    costs well under 16x. See the table in :mod:`lunar_reg.device`.
    """
    ratio = device.dense_matcher_peak_bytes(1024, "fp32") / device.dense_matcher_peak_bytes(
        512, "fp32"
    )
    assert 4.0 < ratio < 16.0


def test_measured_activation_scaling_is_reproduced():
    """Predictions must track the benchmark's measured activations.

    Measured by lunar_reg.match.benchmark on 2026-09-05 (host RSS, fp32). The
    20% tolerance is the two-term fit's own residual, not slack: the model is a
    planning aid, which is why VRAM_SAFETY_FRACTION exists on top.
    """
    measured_gb = {256: 0.219, 512: 0.778, 768: 1.756, 896: 2.750, 1024: 4.500}
    for side, expected in measured_gb.items():
        predicted = device.dense_matcher_peak_bytes(side, "fp32") / 1024**3
        assert predicted == pytest.approx(expected, rel=0.20), f"at {side}px"


def test_fp16_saves_less_than_half():
    """Autocast does not halve the cost, and the model must not pretend it does.

    Normalisations and softmax stay in fp32 under autocast, so the backbone term
    only partly shrinks. NOT MEASURED -- see FP16_BACKBONE_FACTOR. This test
    pins the intent (a saving, but short of 2x) rather than a verified number.
    """
    fp32 = device.dense_matcher_peak_bytes(1024, "fp32")
    fp16 = device.dense_matcher_peak_bytes(1024, "fp16")
    assert fp32 / 2 < fp16 < fp32


def test_planned_tile_fits_the_budget():
    plan = device.plan_dense_tile("cpu", "fp16")
    assert plan.est_peak_bytes <= plan.free_bytes * device.VRAM_SAFETY_FRACTION


def test_planned_tile_is_pyramid_compatible():
    """LoFTR's 1/8-then-1/2 pyramid needs a side divisible by 64."""
    assert device.plan_dense_tile("cpu", "fp16").tile_px % 64 == 0


def test_fp32_plans_a_smaller_tile_than_fp16():
    assert (
        device.plan_dense_tile("cpu", "fp32").tile_px
        <= device.plan_dense_tile("cpu", "fp16").tile_px
    )


def test_1600px_tile_would_exceed_8gb():
    """The documented OOM boundary -- if this changes, update the module docs."""
    assert device.dense_matcher_peak_bytes(1600, "fp32") > 8 * 1024**3


def test_keypoint_budget_is_conservative_on_8gb():
    assert device.plan_keypoint_budget("cpu") <= device.SAFE_MAX_KEYPOINTS


def test_get_device_returns_a_valid_string():
    assert device.get_device() in {"cuda", "cpu"}
    assert device.get_device(prefer_cuda=False) == "cpu"
