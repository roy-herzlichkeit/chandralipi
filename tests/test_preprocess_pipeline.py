"""The Makharia et al. pipeline: step behaviour, toggling, and provenance.

Parameter provenance is tested as hard as the image maths. The paper states few
numeric values, and a placeholder quietly promoted to "paper-matched" would
misrepresent any result built on it.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from lunar_reg.preprocess.config import (
    STEP_ORDER,
    PreprocessConfig,
    ablation_configs,
    iirs_wac_config,
    minimal_config,
    ohrc_nac_config,
)
from lunar_reg.preprocess.georeference import georeference, lunar_crs
from lunar_reg.preprocess.hyperspectral import reduce_bands, select_reference_band
from lunar_reg.preprocess.params import (
    ALL_PARAMS,
    PLACEHOLDER_PARAM_NAMES,
    RESAMPLE_TARGETS,
    ParamSource,
    provenance_report,
)
from lunar_reg.preprocess.pipeline import (
    PreprocessContext,
    run_ablation,
    run_pipeline,
)
from lunar_reg.preprocess.radiometric import dilate, invert, log_transform, match_histogram
from lunar_reg.preprocess.resample import paper_target_gsd
from lunar_reg.preprocess.shadow import (
    estimate_shadow_severity,
    normalize_shadows,
    shadow_fraction,
    shadow_mask,
)


@pytest.fixture
def scene():
    """A textured frame with a deep-shadow quadrant."""
    rng = np.random.default_rng(3)
    img = cv2.GaussianBlur(rng.integers(20, 200, (256, 256)).astype(np.uint8), (5, 5), 1.5)
    img[:100, :100] //= 8
    return img


@pytest.fixture
def cube():
    rng = np.random.default_rng(5)
    c = rng.normal(100, 20, (16, 64, 64)).astype(np.float32)
    c[7] *= 3.0  # one deliberately high-contrast band
    return c


# --- parameter provenance --------------------------------------------------


def test_paper_stated_values_are_marked_paper():
    """8-bit normalisation and the inversion formula are quoted in the paper."""
    by_name = {p.name: p for p in ALL_PARAMS}
    for name in ("normalize_target_max", "inversion_max"):
        assert by_name[name].source is ParamSource.PAPER
        assert by_name[name].quote, "a PAPER param must carry the supporting quote"


def test_clahe_and_shadow_params_are_marked_placeholder():
    """Guard: the paper gives no CLAHE or shadow numbers, so these must stay placeholders."""
    for name in ("clahe_clip_limit", "clahe_tile_grid", "shadow_percentile",
                 "shadow_method", "shadow_gamma"):
        assert name in PLACEHOLDER_PARAM_NAMES, (
            f"{name} is not marked a placeholder; the paper does not state it, "
            f"so promoting it would misrepresent a run as paper-matched"
        )


def test_every_placeholder_explains_itself():
    for p in ALL_PARAMS:
        if p.source is ParamSource.PLACEHOLDER:
            assert "NOT IN PAPER" in p.note, f"{p.name} must say it is not from the paper"


def test_paper_range_params_explain_the_choice():
    for p in ALL_PARAMS:
        if p.source is ParamSource.PAPER_RANGE:
            assert p.note and p.quote, f"{p.name} must carry both the range quote and our pick"


def test_provenance_report_warns_against_claiming_paper_match():
    report = provenance_report()
    assert "NOT stated in the paper" in report
    assert "pipeline STRUCTURE only" in report


def test_resample_targets_match_the_paper_text():
    """Values quoted from the paper's section 4.1.2."""
    assert RESAMPLE_TARGETS[("IIRS", "LRO_WAC")].value == 100.0
    assert RESAMPLE_TARGETS[("DFSAR", "SELENE_TC")].value == 9.0
    assert 0.5 <= RESAMPLE_TARGETS[("OHRC", "LRO_NAC")].value <= 2.0


def test_paper_target_gsd_lookup_and_unknown_pair():
    assert paper_target_gsd("IIRS", "LRO_WAC") == 100.0
    assert paper_target_gsd("OHRC", "SELENE_TC") is None, "must not invent a target"
    assert paper_target_gsd(None, None) is None


# --- individual steps ------------------------------------------------------


def test_inversion_uses_the_exact_paper_formula():
    a = np.array([[0, 1, 128, 255]], dtype=np.uint8)
    np.testing.assert_array_equal(invert(a), [[255, 254, 127, 0]])


def test_inversion_is_its_own_inverse():
    a = np.arange(256, dtype=np.uint8).reshape(16, 16)
    np.testing.assert_array_equal(invert(invert(a)), a)


def test_dilation_brightens_or_preserves_never_darkens():
    """Dilation is a max filter; no pixel may decrease."""
    rng = np.random.default_rng(0)
    a = rng.integers(0, 255, (64, 64)).astype(np.uint8)
    assert (dilate(a) >= a).all()


def test_dilation_rejects_bad_parameters():
    a = np.zeros((8, 8), dtype=np.uint8)
    with pytest.raises(ValueError, match="shape must be"):
        dilate(a, shape="hexagon")
    with pytest.raises(ValueError, match="kernel_size"):
        dilate(a, kernel_size=0)


def test_log_transform_lifts_shadows_more_than_highlights():
    a = np.array([[10, 20, 200, 210]], dtype=np.uint8)
    out = log_transform(a).astype(int)
    assert (out[0, 1] - out[0, 0]) > (out[0, 3] - out[0, 2])


def test_log_transform_is_monotonic():
    a = np.arange(256, dtype=np.uint8).reshape(1, 256)
    assert (np.diff(log_transform(a)[0].astype(int)) >= 0).all()


def test_histogram_matching_moves_source_stats_toward_reference():
    rng = np.random.default_rng(1)
    src = rng.normal(60, 10, (128, 128)).clip(0, 255).astype(np.uint8)
    ref = rng.normal(190, 10, (128, 128)).clip(0, 255).astype(np.uint8)
    out = match_histogram(src, ref)
    assert abs(float(out.mean()) - float(ref.mean())) < abs(float(src.mean()) - float(ref.mean()))


def test_histogram_matching_needs_no_parameters():
    """Unlike most steps here, this one has nothing to tune."""
    rng = np.random.default_rng(2)
    a = rng.integers(0, 255, (32, 32)).astype(np.uint8)
    np.testing.assert_array_equal(match_histogram(a, a.copy()), match_histogram(a, a.copy()))


# --- shadow ----------------------------------------------------------------


@pytest.mark.parametrize("method", ["gamma", "mask", "retinex", "none"])
def test_every_shadow_method_returns_a_same_shaped_image(method, scene):
    out = normalize_shadows(scene, method=method)
    assert out.shape == scene.shape
    assert np.isfinite(out).all()


def test_gamma_shadow_brightens_shadow_and_leaves_lit_terrain_alone(scene):
    """Regression: an earlier version darkened shadow instead of lifting it.

    It normalised against the full image range rather than the shadow range, so
    the gamma output was a tiny fraction of the scale and the step inverted its
    own intent (shadow mean fell 12.20 -> 10.01).
    """
    out = normalize_shadows(scene, method="gamma", percentile=10.0)
    dark = shadow_mask(scene, 10.0)
    assert out[dark].mean() > scene[dark].mean(), "shadow must be lifted, not darkened"
    np.testing.assert_allclose(out[~dark], scene[~dark], rtol=0, atol=0), (
        "lit terrain must be untouched -- the paper requires overall contrast kept"
    )


def test_gamma_shadow_is_continuous_at_the_shadow_boundary(scene):
    """No seam: the brightest shadowed pixel must not exceed the threshold.

    A discontinuity there would create a synthetic edge that detectors latch
    onto, manufacturing keypoints along an artefact of preprocessing.
    """
    out = normalize_shadows(scene, method="gamma", percentile=10.0)
    dark = shadow_mask(scene, 10.0)
    assert out[dark].max() <= np.percentile(scene, 10.0) + 1e-4


def test_gamma_shadow_preserves_ordering_within_shadow(scene):
    """'Revealed', not 'removed' -- structure inside shadow must survive."""
    out = normalize_shadows(scene, method="gamma", percentile=20.0)
    dark = shadow_mask(scene, 20.0)
    order_in = np.argsort(scene[dark], kind="stable")
    assert (np.diff(out[dark][order_in]) >= -1e-3).all(), "monotonic map required"


def test_gamma_shadow_leaves_a_single_level_shadow_alone():
    """Nothing to reveal in a flat shadow; the step must not invent detail."""
    img = np.full((64, 64), 100, dtype=np.uint8)
    img[:16, :16] = 5  # one quantised shadow level
    out = normalize_shadows(img, method="gamma", percentile=5.0)
    assert len(np.unique(out[:16, :16])) == 1


def test_mask_method_flattens_shadow(scene):
    out = normalize_shadows(scene, method="mask", percentile=10.0)
    dark = scene < np.percentile(scene, 10)
    assert out[dark].std() == pytest.approx(0.0, abs=1e-6)


def test_unknown_shadow_method_rejected():
    with pytest.raises(ValueError, match="method must be"):
        normalize_shadows(np.zeros((4, 4)), method="magic")


def test_shadow_fraction_is_a_lower_bound_not_the_percentile(scene):
    """Ties make the selected fraction exceed the requested percentile.

    The mask is inclusive and real lunar shadow saturates at few DN values, so
    a nominal 5% threshold can select far more. Measured 9.1% on this scene.
    This is why shadow_fraction() exists rather than assuming percentile/100.
    """
    frac = shadow_fraction(scene, 5.0)
    assert frac >= 0.05
    assert frac > 0.06, "this scene has heavy ties; the overshoot is the point"
    assert shadow_fraction(scene, 20.0) >= shadow_fraction(scene, 5.0)


def test_shadow_fraction_matches_the_percentile_without_ties():
    """With continuous values and no ties, the fraction does track the percentile."""
    smooth = np.linspace(0, 255, 10000, dtype=np.float32).reshape(100, 100)
    assert shadow_fraction(smooth, 5.0) == pytest.approx(0.05, abs=0.005)


def test_severity_distinguishes_a_shadowed_scene_from_a_lit_one(scene):
    """shadow_fraction always returns ~percentile; severity is the real measure."""
    lit = np.full((256, 256), 180, dtype=np.uint8)
    lit[0, 0] = 0  # a single dark pixel, so the range is non-degenerate
    assert estimate_shadow_severity(scene) > estimate_shadow_severity(lit)


def test_shadow_on_a_flat_image_does_not_crash():
    flat = np.full((16, 16), 42, dtype=np.uint8)
    assert normalize_shadows(flat, method="gamma").shape == flat.shape


# --- band reduction --------------------------------------------------------


def test_band_selection_picks_the_high_contrast_band(cube):
    plane, index = select_reference_band(cube)
    assert index == 7
    assert plane.shape == (64, 64)


def test_band_selection_can_be_pinned(cube):
    _, index = select_reference_band(cube, band=3)
    assert index == 3


def test_band_selection_rejects_out_of_range(cube):
    with pytest.raises(ValueError, match="out of range"):
        select_reference_band(cube, band=999)


@pytest.mark.parametrize("method", ["pca", "select", "mean"])
def test_every_reduction_method_yields_one_plane(method, cube):
    plane, detail = reduce_bands(cube, method=method)
    assert plane.shape == (64, 64)
    assert detail["method"] == method
    assert detail["n_bands"] == 16


def test_pca_reports_explained_variance(cube):
    _, detail = reduce_bands(cube, method="pca", n_components=1)
    assert 0.0 <= detail["explained_variance"] <= 1.0


def test_reduce_bands_rejects_a_2d_input():
    with pytest.raises(ValueError, match="cube"):
        reduce_bands(np.zeros((8, 8)))


# --- config and toggling ---------------------------------------------------


def test_paper_presets_use_only_their_own_track():
    assert ohrc_nac_config().tracks_used() == {"ohrc_nac"}
    assert iirs_wac_config().tracks_used() == {"iirs_wac"}


def test_mixed_track_config_says_so():
    mixed = PreprocessConfig(label="mixed", clahe=True, shadow=True)
    assert len(mixed.tracks_used()) == 2
    assert "not the paper's configuration" in mixed.describe()


def test_minimal_config_runs_core_steps_only():
    assert minimal_config().tracks_used() == set()


def test_toggle_returns_a_copy_and_does_not_mutate():
    base = ohrc_nac_config()
    off = base.toggle("clahe", False)
    assert base.clahe is True and off.clahe is False
    assert "clahe=off" in off.label


def test_toggle_rejects_an_unknown_step():
    with pytest.raises(ValueError, match="unknown step"):
        PreprocessConfig().toggle("denoise", False)


@pytest.mark.parametrize("step", STEP_ORDER)
def test_every_step_can_be_toggled_independently(step, scene):
    """The whole point of the config layer: any step off, pipeline still runs."""
    config = PreprocessConfig(**{step: False}, label=f"no_{step}")
    result = run_pipeline(scene, config, PreprocessContext(src_gsd_m=0.25))
    assert step not in result.steps_run
    assert result.image.ndim == 2


def test_ablation_set_is_leave_one_out():
    base = ohrc_nac_config()
    configs = ablation_configs(base)
    assert configs[0] is base
    assert len(configs) == 1 + len(base.enabled_steps())
    for config, step in zip(configs[1:], base.enabled_steps(), strict=True):
        assert getattr(config, step) is False


# --- pipeline --------------------------------------------------------------


def test_ohrc_nac_track_runs_every_configured_step(scene):
    result = run_pipeline(scene, ohrc_nac_config(), PreprocessContext(src_gsd_m=0.25))
    assert result.steps_run == ("resample", "normalize", "clahe", "invert", "dilate")
    assert not result.steps_skipped
    assert result.image.dtype == np.uint8


def test_iirs_wac_track_runs_on_a_cube(cube):
    ref = np.random.default_rng(0).integers(80, 180, (64, 64)).astype(np.uint8)
    result = run_pipeline(cube, iirs_wac_config(), PreprocessContext(reference_image=ref))
    assert "band_reduction" in result.steps_run
    assert "shadow" in result.steps_run
    assert result.image.ndim == 2


def test_resample_uses_the_paper_target_for_a_known_pair(scene):
    result = run_pipeline(scene, ohrc_nac_config(), PreprocessContext(src_gsd_m=0.25))
    detail = next(r.detail for r in result.history if r.name == "resample")
    assert detail["target_gsd_m"] == 1.0
    assert result.image.shape == (64, 64), "0.25 -> 1.0 m/px is a 4x reduction"


def test_skipped_step_is_recorded_with_a_reason_not_dropped(scene):
    """A step that cannot run must be visible; a silent no-op would mislead."""
    config = PreprocessConfig(label="needs_ref", histogram_match=True, resample=False)
    result = run_pipeline(scene, config)
    assert "histogram_match" in result.steps_skipped
    record = next(r for r in result.history if r.name == "histogram_match")
    assert "no reference image" in record.reason


def test_georeference_without_crs_is_skipped_loudly(scene):
    config = PreprocessConfig(label="geo", georeference=True, resample=False)
    result = run_pipeline(scene, config)
    record = next(r for r in result.history if r.name == "georeference")
    assert not record.ran
    assert "georeferencing needs both" in record.reason


def test_resample_without_a_target_is_skipped_not_guessed(scene):
    config = PreprocessConfig(label="no_target", resample=True, source_sensor=None)
    result = run_pipeline(scene, config)
    record = next(r for r in result.history if r.name == "resample")
    assert not record.ran
    assert "target" in record.reason


def test_a_failing_step_does_not_abort_the_run(scene):
    config = PreprocessConfig(label="bad_dilate", dilate=True, dilation_kernel_shape="hexagon",
                              resample=False)
    result = run_pipeline(scene, config)
    record = next(r for r in result.history if r.name == "dilate")
    assert not record.ran and "ValueError" in record.reason
    assert "normalize" in result.steps_run, "later steps must still run"


def test_result_reports_which_placeholders_it_depended_on(scene):
    result = run_pipeline(scene, ohrc_nac_config(), PreprocessContext(src_gsd_m=0.25))
    assert "clahe_clip_limit" in result.uses_placeholders
    assert "not stated in the paper" in result.report()
    assert "STRUCTURE, not its parameter values" in result.report()


def test_a_run_of_only_paper_valued_steps_reports_no_placeholders(scene):
    config = PreprocessConfig(
        label="paper_only", resample=False, normalize=True, invert=True,
        clahe=False, shadow=False, dilate=False, band_reduction=False,
    )
    result = run_pipeline(scene, config)
    assert result.steps_run == ("normalize", "invert")
    assert result.uses_placeholders == ()


def test_history_covers_every_enabled_step(scene):
    config = ohrc_nac_config()
    result = run_pipeline(scene, config, PreprocessContext(src_gsd_m=0.25))
    assert [r.name for r in result.history] == list(config.enabled_steps())


def test_ablation_produces_one_result_per_config(scene):
    configs = ablation_configs(ohrc_nac_config())
    results = run_ablation(scene, configs, PreprocessContext(src_gsd_m=0.25))
    assert len(results) == len(configs)
    assert len(results[0].steps_run) > len(results[-1].steps_run)


def test_disabling_clahe_changes_the_output(scene):
    ctx = PreprocessContext(src_gsd_m=0.25)
    with_clahe = run_pipeline(scene, ohrc_nac_config(), ctx).image
    without = run_pipeline(scene, ohrc_nac_config().toggle("clahe", False), ctx).image
    assert not np.array_equal(with_clahe, without), "the ablation must actually change something"


def test_empty_config_is_a_passthrough(scene):
    config = PreprocessConfig(
        label="none", resample=False, normalize=False, clahe=False,
        shadow=False, band_reduction=False,
    )
    result = run_pipeline(scene, config)
    assert result.steps_run == ()
    np.testing.assert_array_equal(result.image, scene)


# --- georeferencing --------------------------------------------------------


def test_lunar_crs_uses_the_moon_radius_not_earths():
    from lunar_reg.constants import MOON_RADIUS_M

    crs = lunar_crs("equirectangular")
    assert str(int(MOON_RADIUS_M)) in crs.to_string() or "1737400" in crs.to_wkt()


def test_paper_projection_names_are_accepted():
    assert lunar_crs("Selenographic") is not None
    assert lunar_crs("Equirectangular Moon") is not None


def test_unknown_projection_rejected():
    with pytest.raises(ValueError, match="unknown projection"):
        lunar_crs("mercator-on-mars")


def test_georeference_without_datasets_reports_why(scene):
    result = georeference(scene)
    assert not result.applied
    assert "needs both" in result.reason
    np.testing.assert_array_equal(result.image, scene)
