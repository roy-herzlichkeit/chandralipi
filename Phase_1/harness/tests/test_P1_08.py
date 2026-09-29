"""P1.08 — nodata-aware radiometric + shadow (Phase_1/LLD/preprocess_nodata.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def img():
    a = np.random.default_rng(3).uniform(10, 4000, (80, 90)).astype(np.float32)
    a[:, :12] = 0
    return a


def test_to_uint8_valid(img):
    from lunar_reg.preprocess.radiometric import to_uint8

    valid = img > 0
    out = to_uint8(img, valid=valid)
    assert out.dtype == np.uint8
    assert (out[~valid] == 0).all() and (out[valid] >= 1).all()
    lo, hi = np.percentile(img[valid], (1, 99))
    inside = valid & (img > lo) & (img < hi)
    expect = np.clip((img[inside] - lo) / (hi - lo) * 254 + 1, 1, 255)
    np.testing.assert_allclose(out[inside].astype(float), expect, atol=1.0)


def test_to_uint8_without_mask_unchanged():
    from lunar_reg.preprocess.radiometric import to_uint8

    a = np.random.default_rng(0).uniform(0, 1000, (50, 60)).astype(np.float32)
    lo, hi = np.percentile(a, (1, 99))
    out = to_uint8(a)
    assert out.min() == 0 and out.max() == 255
    assert out[a <= lo].max() == 0


@pytest.mark.parametrize("fn", ["apply_clahe", "invert", "dilate", "log_transform"])
def test_uint8_steps_keep_border_zero(img, fn):
    from lunar_reg.preprocess import radiometric as r

    valid = img > 0
    u8 = r.to_uint8(img, valid=valid)
    if fn == "apply_clahe":
        out = r.apply_clahe(u8, 2.0, (8, 8), valid=valid)
    elif fn == "dilate":
        out = r.dilate(u8, 3, "ellipse", valid=valid)
    else:
        out = getattr(r, fn)(u8, valid=valid)
    assert (out[~valid] == 0).all()
    assert (out[valid] > 0).mean() > 0.99


def test_invert_maps_1_255(img):
    from lunar_reg.preprocess.radiometric import invert, to_uint8

    valid = img > 0
    u8 = to_uint8(img, valid=valid)
    out = invert(u8, valid=valid)
    np.testing.assert_array_equal(out[valid].astype(int), 256 - u8[valid].astype(int))


def test_match_histogram_valid_only(img):
    from lunar_reg.preprocess.radiometric import match_histogram, to_uint8

    valid = img > 0
    src = to_uint8(img, valid=valid)
    ref = to_uint8(img[::-1], valid=valid[::-1])
    out = match_histogram(src, ref, valid=valid, reference_valid=valid[::-1])
    assert (out[~valid] == 0).all()


def test_shadow_functions(img):
    from lunar_reg.preprocess.shadow import normalize_shadows, shadow_fraction, shadow_mask

    valid = img > 0
    m = shadow_mask(img, 10.0, valid=valid)
    assert not m[~valid].any()
    assert shadow_fraction(img, 10.0, valid=valid) == pytest.approx(m[valid].mean())
    for method in ("gamma", "mask", "retinex"):
        out = normalize_shadows(img, method=method, percentile=5.0, gamma=0.5, valid=valid)
        assert np.isnan(out[~valid]).all(), method
        assert np.isfinite(out[valid]).all(), method


def test_retinex_nan_safe():
    from lunar_reg.preprocess.shadow import normalize_shadows

    a = np.random.default_rng(1).uniform(1, 100, (64, 64)).astype(np.float32)
    a[10:20, 10:20] = np.nan
    out = normalize_shadows(a, method="retinex", percentile=5.0, gamma=0.5)
    assert np.isfinite(out[~np.isnan(a)]).all()
