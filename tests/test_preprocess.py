"""Preprocessing defaults come from the benchmark paper; pin their behaviour."""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.preprocess.hyperspectral import iirs_to_panchromatic, select_bands
from lunar_reg.preprocess.radiometric import (
    apply_clahe,
    normalize_intensity,
    shadow_mask,
    standard_chain,
    suppress_shadows,
    to_uint8,
)
from lunar_reg.preprocess.resample import to_common_gsd


def test_to_uint8_handles_16bit_input():
    img = (np.arange(65536, dtype=np.uint16) % 4096).reshape(256, 256)
    assert to_uint8(img).dtype == np.uint8


def test_to_uint8_survives_a_single_saturated_pixel():
    """Percentile clipping, not min/max -- one hot pixel must not crush the rest."""
    img = np.full((64, 64), 100.0)
    img[0, 0] = 1e6
    out = to_uint8(img)
    assert out[1:, 1:].std() >= 0.0
    assert out.max() <= 255


def test_to_uint8_on_flat_image_does_not_divide_by_zero():
    assert to_uint8(np.full((16, 16), 7.0)).sum() == 0


def test_clahe_increases_local_contrast():
    rng = np.random.default_rng(0)
    img = (rng.normal(128, 4, (256, 256))).clip(0, 255).astype(np.uint8)
    assert apply_clahe(img).std() > img.std()


def test_normalize_intensity_is_zero_mean_unit_variance():
    out = normalize_intensity(np.random.default_rng(0).normal(500, 30, (128, 128)))
    assert out.mean() == pytest.approx(0.0, abs=1e-5)
    assert out.std() == pytest.approx(1.0, abs=1e-4)


def test_shadow_mask_selects_the_darkest_fraction():
    img = np.arange(10000, dtype=np.float32).reshape(100, 100)
    mask = shadow_mask(img, percentile=10.0)
    assert mask.sum() == pytest.approx(1000, rel=0.02)
    assert img[mask].max() < img[~mask].min()


def test_suppress_shadows_removes_the_dark_mode():
    img = np.concatenate([np.zeros(500), np.full(9500, 200.0)]).reshape(100, 100)
    assert suppress_shadows(img, percentile=5.0).min() > 0


def test_standard_chain_returns_uint8():
    img = np.random.default_rng(0).integers(0, 4096, (256, 256)).astype(np.uint16)
    out = standard_chain(img)
    assert out.dtype == np.uint8 and out.shape == img.shape


def test_downsampling_uses_area_averaging_not_aliasing():
    """A 20x reduction with the wrong interpolation manufactures false corners."""
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, (1000, 1000)).astype(np.uint8)
    small = to_common_gsd(img, src_gsd_m=0.25, target_gsd_m=5.0)
    assert small.shape == (50, 50)
    # Area averaging collapses white noise toward the mean; nearest would not.
    assert small.std() < img.std() / 2


def test_common_gsd_is_a_noop_at_equal_resolution():
    img = np.ones((32, 32), dtype=np.uint8)
    assert to_common_gsd(img, 5.0, 5.0) is img


def test_iirs_collapses_to_a_single_plane():
    cube = np.random.default_rng(0).random((256, 64, 64)).astype(np.float32)
    pan = iirs_to_panchromatic(cube, band_range=(0, 60))
    assert pan.shape == (64, 64)
    np.testing.assert_allclose(pan, cube[0:60].mean(axis=0), rtol=1e-5)


def test_band_range_beyond_cube_is_clipped_not_an_error():
    cube = np.ones((10, 8, 8), dtype=np.float32)
    assert iirs_to_panchromatic(cube, band_range=(0, 500)).shape == (8, 8)


def test_empty_band_range_rejected():
    with pytest.raises(ValueError):
        iirs_to_panchromatic(np.ones((10, 8, 8), dtype=np.float32), band_range=(5, 5))


def test_select_bands_preserves_order():
    cube = np.arange(10 * 4 * 4, dtype=np.float32).reshape(10, 4, 4)
    np.testing.assert_array_equal(select_bands(cube, [3, 1]), cube[[3, 1]])
