"""Synthetic illumination scenes and the error-attribution harness."""

from __future__ import annotations

import numpy as np
import pytest

from lunar_reg.align.estimate import estimate_transform
from lunar_reg.align.refine import (
    ECC_PREFILTERS,
    choose_ecc_prefilter,
    local_contrast_normalize,
    refine_transform_ecc,
)
from lunar_reg.eval.error_budget import attribute_error, transform_rms_px
from lunar_reg.eval.scenes import fractal_terrain, hillshade, illumination_pair
from lunar_reg.match.classical import build_classical


def test_relief_is_in_pixel_units():
    """A height field must be scaled against the pixel axes or it renders flat.

    Guards a real bug: relief was once 3.0 over a 512 px scene, which made every
    slope negligible, every sun angle produce the same near-uniform image, and
    the whole illumination experiment vacuous.
    """
    height = fractal_terrain((256, 256), seed=1)
    flat = hillshade(height, 285.0, 6.0, relief=1.0)
    steep = hillshade(height, 285.0, 6.0, relief=40.0)
    assert flat.std() < 5.0
    assert steep.std() > 15.0


def test_low_sun_casts_shadows_and_high_sun_does_not():
    height = fractal_terrain((256, 256), seed=2)
    grazing = hillshade(height, 285.0, 5.0, relief=40.0)
    overhead = hillshade(height, 285.0, 75.0, relief=40.0)
    assert (grazing < 15).mean() > 0.10
    assert (overhead < 15).mean() < 0.01


def test_opposed_illumination_inverts_contrast():
    """Same terrain, opposite sun: the images anti-correlate.

    This is the property the whole problem statement turns on, so if it stops
    holding the scenes are no longer testing what they claim to.
    """
    source, reference, _, _ = illumination_pair(
        source_sun=(285.0, 20.0), reference_sun=(105.0, 20.0),
        homography=np.eye(3), albedo_strength=0.0,
    )
    correlation = np.corrcoef(source.ravel(), reference.ravel())[0, 1]
    assert correlation < 0.0


def test_reference_is_lit_from_the_warped_terrain():
    """Shadows must belong to the reference's own sun, not the source's.

    Warping the rendered source image instead of the terrain would carry the
    source's shadows across and make the pair far easier than it should be.
    """
    source, reference, _, _ = illumination_pair(
        source_sun=(285.0, 5.0), reference_sun=(105.0, 70.0), albedo_strength=0.0
    )
    assert (source < 15).mean() > 0.15
    assert (reference < 15).mean() < 0.02


def test_transform_rms_of_a_transform_against_itself_is_zero():
    matrix = np.array([[1.03, 0.01, 9.0], [-0.02, 0.99, -6.0], [0.0, 0.0, 1.0]])
    assert transform_rms_px(matrix, matrix, (256, 256)) == pytest.approx(0.0, abs=1e-9)


def test_transform_rms_detects_a_pure_translation():
    identity = np.eye(3)
    shifted = np.array([[1.0, 0.0, 3.0], [0.0, 1.0, 4.0], [0.0, 0.0, 1.0]])
    assert transform_rms_px(shifted, identity, (256, 256)) == pytest.approx(5.0, rel=1e-6)


def test_attribution_is_subpixel_under_equal_illumination():
    source, reference, truth, _ = illumination_pair(
        source_sun=(285.0, 45.0), reference_sun=(285.0, 45.0), seed=3
    )
    budget = attribute_error(source, reference, truth, matcher_name="akaze")
    assert budget.failed is None
    assert budget.get("transform: after refinement") < 1.0
    # The oracle fit must be essentially exact, or the harness is not isolating
    # correspondence error from point distribution at all.
    assert budget.get("transform: distribution only") < 1e-3


def test_attribution_reports_failure_rather_than_a_number():
    """Opposed illumination defeats classical matchers; that must not look like success."""
    source, reference, truth, _ = illumination_pair(
        source_sun=(285.0, 6.0), reference_sun=(105.0, 62.0), seed=3
    )
    budget = attribute_error(source, reference, truth, matcher_name="sift")
    assert budget.failed is not None
    assert "correspondence" in budget.failed
    assert "FAILED" in budget.report()


def test_local_contrast_normalize_removes_a_brightness_ramp():
    base = fractal_terrain((128, 128), seed=5) * 120 + 60
    ramp = np.linspace(0, 100, 128)[None, :]
    plain = base.astype(np.uint8)
    ramped = np.clip(base + ramp, 0, 255).astype(np.uint8)
    before = np.corrcoef(plain.ravel(), ramped.ravel())[0, 1]
    after = np.corrcoef(
        local_contrast_normalize(plain).ravel(), local_contrast_normalize(ramped).ravel()
    )[0, 1]
    assert after > before


def test_prefilter_rejects_an_unknown_name():
    source, reference, _, _ = illumination_pair(
        source_sun=(285.0, 45.0), reference_sun=(285.0, 45.0), seed=4
    )
    result = build_classical("akaze").match(source, reference)
    transform, _ = estimate_transform(result, threshold_px=3.0)
    with pytest.raises(ValueError, match="prefilter"):
        refine_transform_ecc(transform, source, reference, prefilter="sharpen")


@pytest.mark.parametrize(
    ("source_sun", "reference_sun", "expected"),
    [
        ((285.0, 45.0), (285.0, 45.0), "none"),
        ((285.0, 45.0), (290.0, 50.0), "none"),
        ((285.0, 45.0), (315.0, 55.0), "local_contrast"),
        ((350.0, 20.0), (10.0, 20.0), "local_contrast"),  # wraps through 360
        (None, (10.0, 20.0), "none"),
    ],
)
def test_prefilter_choice_follows_azimuth_difference(source_sun, reference_sun, expected):
    assert choose_ecc_prefilter(source_sun, reference_sun) == expected
    assert expected in ECC_PREFILTERS
