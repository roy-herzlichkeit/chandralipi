"""Nodata-aware radiometric and shadow steps (Phase_1/LLD/preprocess_nodata.md §3).

Every function gains ``valid=None``. With a mask: statistics from valid pixels
only, nodata output 0 (uint8) or NaN (float). Without a mask: byte-identical to
the pre-P1.08 behaviour, pinned by hashes captured before the edit.
"""

from __future__ import annotations

import hashlib
import logging

import numpy as np
import pytest

from lunar_reg.preprocess import radiometric as r
from lunar_reg.preprocess import shadow as s

BORDER = 9


@pytest.fixture
def img() -> np.ndarray:
    """Float image with a zero (nodata) border on all four sides."""
    a = np.random.default_rng(7).uniform(20, 3000, (70, 84)).astype(np.float32)
    a[:BORDER, :] = 0
    a[-BORDER:, :] = 0
    a[:, :BORDER] = 0
    a[:, -BORDER:] = 0
    return a


@pytest.fixture
def valid(img) -> np.ndarray:
    return img > 0


# --- to_uint8 ---------------------------------------------------------------


def test_to_uint8_valid_stats_and_reserved_zero(img, valid):
    out = r.to_uint8(img, valid=valid)
    assert out.dtype == np.uint8
    assert (out[~valid] == 0).all()
    assert out[valid].min() >= 1 and out[valid].max() == 255
    lo, hi = np.percentile(img[valid], (1, 99))
    expect = np.clip((img[valid] - lo) / max(hi - lo, 1e-6) * 254 + 1, 1, 255).astype(np.uint8)
    np.testing.assert_array_equal(out[valid], expect)


def test_to_uint8_percentiles_ignore_nodata(img, valid):
    """The 0 border must not drag lo down: the 1st-percentile valid pixel maps near 1."""
    out = r.to_uint8(img, valid=valid)
    lo = np.percentile(img[valid], 1)
    assert out[valid & (img <= lo)].max() == 1


# --- pointwise float steps: valid region == function on valid pixels alone ---


def test_normalize_intensity_valid(img, valid):
    out = r.normalize_intensity(img, valid=valid)
    assert np.isnan(out[~valid]).all()
    np.testing.assert_array_equal(out[valid], r.normalize_intensity(img[valid]))


def test_suppress_shadows_valid(img, valid):
    out = r.suppress_shadows(img, 10.0, valid=valid)
    assert np.isnan(out[~valid]).all()
    np.testing.assert_array_equal(out[valid], r.suppress_shadows(img[valid], 10.0))


def test_log_transform_valid(img, valid):
    out = r.log_transform(img, valid=valid)
    assert out.dtype == np.uint8
    assert (out[~valid] == 0).all()
    np.testing.assert_array_equal(out[valid], r.log_transform(img[valid]))


def test_invert_valid_maps_1_255_to_255_1(img, valid):
    u8 = r.to_uint8(img, valid=valid)
    out = r.invert(u8, valid=valid)
    assert (out[~valid] == 0).all()
    np.testing.assert_array_equal(out[valid].astype(int), 256 - u8[valid].astype(int))
    assert out[valid].min() >= 1


def test_match_histogram_valid_cdfs(img, valid):
    src = r.to_uint8(img, valid=valid)
    ref_img = np.random.default_rng(8).gamma(2.0, 300.0, img.shape).astype(np.float32)
    ref_valid = np.ones(img.shape, bool)
    ref_valid[:20] = False
    ref_img[~ref_valid] = 0
    ref = r.to_uint8(ref_img, valid=ref_valid)
    out = r.match_histogram(src, ref, valid=valid, reference_valid=ref_valid)
    assert (out[~valid] == 0).all()
    np.testing.assert_array_equal(out[valid], r.match_histogram(src[valid], ref[ref_valid]))


# --- spatial uint8 steps: border 0, valid >= 1 --------------------------------


def test_apply_clahe_valid(img, valid):
    out = r.apply_clahe(img, 2.0, (8, 8), valid=valid)
    assert out.dtype == np.uint8
    assert (out[~valid] == 0).all() and (out[valid] >= 1).all()
    # Float input is stretched with the mask first: same as an explicit to_uint8.
    via_u8 = r.apply_clahe(r.to_uint8(img, valid=valid), 2.0, (8, 8), valid=valid)
    np.testing.assert_array_equal(out, via_u8)


def test_dilate_valid(img, valid):
    u8 = r.to_uint8(img, valid=valid)
    out = r.dilate(u8, 5, "ellipse", valid=valid)
    assert (out[~valid] == 0).all()
    assert (out[valid] >= u8[valid]).all()
    # Unmasked dilation spreads data into the border; the mask must undo exactly that.
    plain = r.dilate(u8, 5, "ellipse")
    assert (plain[~valid] > 0).any()
    np.testing.assert_array_equal(out[valid], plain[valid])


def test_standard_chain_valid(img, valid):
    out = r.standard_chain(img, valid=valid)
    assert (out[~valid] == 0).all() and (out[valid] >= 1).all()
    expect = r.apply_clahe(
        r.to_uint8(r.suppress_shadows(img, 5.0, valid=valid), valid=valid), valid=valid
    )
    np.testing.assert_array_equal(out, expect)


@pytest.mark.parametrize("suppress", [True, False])
def test_standard_chain_nan_inside_valid_stays_nodata(img, valid, suppress):
    """A NaN pixel marked valid is nodata (Q-P1.08-1 (b)) through the whole chain.

    to_uint8 writes it as 0; apply_clahe on the uint8 image must not lift it to >= 1.
    """
    a = img.copy()
    a[20, 20] = np.nan
    assert valid[20, 20]
    out = r.standard_chain(a, suppress_shadow=suppress, valid=valid)
    eff = valid & np.isfinite(a)
    assert out[20, 20] == 0
    assert (out[~eff] == 0).all() and (out[eff] >= 1).all()


# --- shadow module ------------------------------------------------------------


def test_shadow_mask_valid(img, valid):
    m = s.shadow_mask(img, 10.0, valid=valid)
    assert not m[~valid].any()
    thr = np.percentile(img[valid], 10.0)
    np.testing.assert_array_equal(m, (img <= thr) & valid)


def test_shadow_fraction_valid(img, valid):
    frac = s.shadow_fraction(img, 10.0, valid=valid)
    assert frac == pytest.approx(s.shadow_mask(img, 10.0, valid=valid)[valid].mean())
    assert frac == pytest.approx(s.shadow_fraction(img[valid], 10.0))
    # Without the mask the zero border counts as "shadow".
    assert s.shadow_fraction(img, 10.0) > frac


def test_estimate_shadow_severity_valid(img, valid):
    got = s.estimate_shadow_severity(img, valid=valid)
    assert got == pytest.approx(s.estimate_shadow_severity(img[valid]))


@pytest.mark.parametrize("method", ["gamma", "mask"])
def test_normalize_shadows_pointwise_methods(img, valid, method):
    out = s.normalize_shadows(img, method=method, percentile=10.0, gamma=0.5, valid=valid)
    assert out.dtype == np.float32
    assert np.isnan(out[~valid]).all()
    alone = s.normalize_shadows(img[valid], method=method, percentile=10.0, gamma=0.5)
    np.testing.assert_array_equal(out[valid], alone)


@pytest.mark.parametrize("method", ["gamma", "mask", "retinex", "none"])
def test_normalize_shadows_every_method_nan_border(img, valid, method):
    before = img.copy()
    out = s.normalize_shadows(img, method=method, percentile=5.0, gamma=0.5, valid=valid)
    assert np.isnan(out[~valid]).all(), method
    assert np.isfinite(out[valid]).all(), method
    np.testing.assert_array_equal(img, before)  # input not mutated


def test_retinex_valid_range_from_valid_pixels(img, valid):
    out = s.normalize_shadows(img, method="retinex", valid=valid)
    vals = img[valid]
    assert out[valid].min() == pytest.approx(vals.min(), rel=1e-5)
    assert out[valid].max() == pytest.approx(vals.max(), rel=1e-5)


def test_retinex_valid_output_independent_of_nodata_values(img, valid):
    """A107: invalid (not only NaN) pixels are filled before blurring.

    Changing the nodata border value must not change the valid-region output.
    """
    other = img.copy()
    other[~valid] = 5000.0
    out0 = s.normalize_shadows(img, method="retinex", valid=valid)
    out1 = s.normalize_shadows(other, method="retinex", valid=valid)
    np.testing.assert_array_equal(out0[valid], out1[valid])
    assert np.isnan(out0[~valid]).all() and np.isnan(out1[~valid]).all()


def test_retinex_nan_input_finite_elsewhere():
    """A107: NaN pixels are filled before blurring and restored afterwards."""
    a = np.random.default_rng(1).uniform(1, 100, (64, 64)).astype(np.float32)
    a[10:20, 10:20] = np.nan
    out = s.normalize_shadows(a, method="retinex")
    nan = np.isnan(a)
    assert np.isfinite(out[~nan]).all()
    assert np.isnan(out[nan]).all()


# --- degenerate masks -----------------------------------------------------------


@pytest.mark.parametrize(
    "call, kind",
    [
        (lambda a, v: r.to_uint8(a, valid=v), "zero"),
        (lambda a, v: r.apply_clahe(a, valid=v), "zero"),
        (lambda a, v: r.normalize_intensity(a, valid=v), "nan"),
        (lambda a, v: r.suppress_shadows(a, valid=v), "nan"),
        (lambda a, v: r.invert(a, valid=v), "zero"),
        (lambda a, v: r.dilate(a, valid=v), "zero"),
        (lambda a, v: r.log_transform(a, valid=v), "zero"),
        (lambda a, v: r.match_histogram(a, a, valid=v), "zero"),
        (lambda a, v: r.standard_chain(a, valid=v), "zero"),
        (lambda a, v: s.shadow_mask(a, valid=v), "false"),
        (lambda a, v: s.normalize_shadows(a, valid=v), "nan"),
    ],
)
def test_empty_mask_returns_empty_output_and_warns(call, kind, caplog):
    a = np.random.default_rng(2).uniform(1, 100, (32, 32)).astype(np.float32)
    v = np.zeros(a.shape, bool)
    with caplog.at_level(logging.WARNING, logger="lunar_reg.preprocess.shadow"):
        out = call(a, v)
    assert out.shape == a.shape
    if kind == "zero":
        assert out.dtype == np.uint8 and not out.any()
    elif kind == "nan":
        assert np.isnan(out).all()
    else:
        assert out.dtype == bool and not out.any()
    assert any("no valid finite pixel" in rec.getMessage() for rec in caplog.records)


def test_empty_mask_scalar_functions():
    a = np.ones((8, 8), np.float32)
    v = np.zeros(a.shape, bool)
    assert s.shadow_fraction(a, valid=v) == 0.0
    assert s.estimate_shadow_severity(a, valid=v) == 0.0


def test_mask_shape_mismatch_raises():
    a = np.ones((8, 8), np.float32)
    with pytest.raises(ValueError, match="valid mask shape"):
        r.to_uint8(a, valid=np.ones((8, 9), bool))


# --- valid=None regression: byte-identical to the pre-P1.08 code ---------------
#
# Hashes computed by running each call on the pre-change code (HEAD 1d978f0)
# with the inputs below, before radiometric.py / shadow.py were edited.

PRE_CHANGE = {
    "to_uint8": ("uint8", "4a0efa17d4155918f536653f925e98d5b5c55be384ef077df559e9eefa9469ee"),
    "apply_clahe": ("uint8", "caa853eb70daffba5d0842004c13ba975a65796a6f253c9664197b0bee6ceda8"),
    "apply_clahe_u8": ("uint8", "caa853eb70daffba5d0842004c13ba975a65796a6f253c9664197b0bee6ceda8"),
    "normalize_intensity": (
        "float32",
        "f62761ef57e650d1394b3bfd2313b7f1cd81b2ddd8dd84fa04271416bc5aedc6",
    ),
    "suppress_shadows": (
        "float32",
        "dd1a92b6fa7f66d35822deb58268185a73a1d0694cebff8ed2f1c42ff1488edb",
    ),
    "invert": ("uint8", "2c882b796736db8e5bac325bdec281f888b0ef12a7da240f5461926a120b8a31"),
    "invert_float": ("uint8", "2c882b796736db8e5bac325bdec281f888b0ef12a7da240f5461926a120b8a31"),
    "dilate": ("uint8", "e7ff3c577a038a2e0eb2261d7e0a46a3801833787ce92b9327eaeb8ae57482c3"),
    "log_transform": ("uint8", "23006ca6a28d2c4af5cb9f577f093347cb62c2bf237582d9a47b33f8a4ef02dd"),
    "match_histogram": (
        "uint8",
        "360339ef841280168cd5b85d5c1b722a58ddbab5b86fcd0503d3e1aec7a70931",
    ),
    "standard_chain": ("uint8", "1f0608245b79e78dc1ab1a3071213fe178ea8e02072b57ef533d54a7cfadc5b8"),
    "shadow_mask": ("bool", "41abf57f7f3f51e632dba0002aa55bf4acd5ec7b2aadeb59e306be9ceeb46596"),
    "shadow_fraction": "0.10004340277777778",
    "estimate_shadow_severity": "0.15625",
    "normalize_shadows_gamma": (
        "float32",
        "f1a912758cd738ff3fdfa2f6d4ee57e702d4379404a32de9a378d0b733542f72",
    ),
    "normalize_shadows_mask": (
        "float32",
        "dd1a92b6fa7f66d35822deb58268185a73a1d0694cebff8ed2f1c42ff1488edb",
    ),
    "normalize_shadows_retinex": (
        "float32",
        "b03b5ee31655669148c1c426eea74b1ff90a48f1e53fddd8626b6314c9af6734",
    ),
}


def _h(a) -> tuple[str, str]:
    """(dtype, sha256 of the raw bytes) of an array."""
    a = np.asarray(a)
    return str(a.dtype), hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def _current_outputs() -> dict[str, object]:
    rng = np.random.default_rng(0)
    img = rng.uniform(0, 1000, (64, 72)).astype(np.float32)
    ref = rng.uniform(0, 1000, (64, 72)).astype(np.float32)
    u8 = r.to_uint8(img)
    return {
        "to_uint8": _h(r.to_uint8(img)),
        "apply_clahe": _h(r.apply_clahe(img)),
        "apply_clahe_u8": _h(r.apply_clahe(u8)),
        "normalize_intensity": _h(r.normalize_intensity(img)),
        "suppress_shadows": _h(r.suppress_shadows(img)),
        "invert": _h(r.invert(u8)),
        "invert_float": _h(r.invert(img)),
        "dilate": _h(r.dilate(u8)),
        "log_transform": _h(r.log_transform(img)),
        "match_histogram": _h(r.match_histogram(img, ref)),
        "standard_chain": _h(r.standard_chain(img)),
        "shadow_mask": _h(s.shadow_mask(img)),
        "shadow_fraction": repr(s.shadow_fraction(img, 10.0)),
        "estimate_shadow_severity": repr(s.estimate_shadow_severity(img)),
        "normalize_shadows_gamma": _h(s.normalize_shadows(img, "gamma")),
        "normalize_shadows_mask": _h(s.normalize_shadows(img, "mask")),
        "normalize_shadows_retinex": _h(s.normalize_shadows(img, "retinex")),
    }


@pytest.mark.parametrize("name", sorted(PRE_CHANGE))
def test_valid_none_byte_identical_to_pre_change(name):
    assert _current_outputs()[name] == PRE_CHANGE[name]
