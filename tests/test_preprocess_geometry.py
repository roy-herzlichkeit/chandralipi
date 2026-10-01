"""P1.09: step outcomes, pixel transforms, measured GSD, valid-mask plumbing.

Phase_1/LLD/preprocess_geometry.md §7.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pytest

from lunar_reg.constants import SENSORS
from lunar_reg.preprocess import pipeline as pp
from lunar_reg.preprocess.config import PreprocessConfig, minimal_config
from lunar_reg.preprocess.georeference import georeference, lunar_crs
from lunar_reg.preprocess.pipeline import PreprocessContext, StepStatus, run_pipeline
from lunar_reg.preprocess.resample import resample_mask
from lunar_reg.provenance import ValueSource

M_PER_DEG = np.pi * 1_737_400.0 / 180.0


def _record(result, name):
    return next(r for r in result.history if r.name == name)


def _apply(matrix, x, y):
    p = np.asarray(matrix) @ np.array([x, y, 1.0])
    return p[0] / p[2], p[1] / p[2]


def _geo_only():
    return PreprocessConfig(
        label="geo",
        georeference=True,
        resample=False,
        normalize=False,
        clahe=False,
        shadow=False,
        band_reduction=False,
    )


def _make_pair(src_nodata=None):
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    files = [MemoryFile(), MemoryFile()]
    src = files[0].open(
        driver="GTiff",
        width=50,
        height=40,
        count=1,
        dtype="float32",
        crs=lunar_crs("geographic"),
        transform=from_origin(10.0, 5.0, 0.001, 0.001),
        nodata=src_nodata,
    )
    ref = files[1].open(
        driver="GTiff",
        width=60,
        height=50,
        count=1,
        dtype="float32",
        crs=lunar_crs("equirectangular"),
        transform=from_origin(10.0 * M_PER_DEG - 5.0, 5.0 * M_PER_DEG + 5.0, 25.0, 25.0),
    )
    return files, src, ref


def _close(files, *datasets):
    for ds in datasets:
        ds.close()
    for f in files:
        f.close()


@pytest.fixture
def rasterio_pair():
    """An in-memory geographic source and an equirectangular reference over it."""
    files, src, ref = _make_pair()
    yield src, ref
    _close(files, src, ref)


@pytest.fixture
def rasterio_pair_nodata_one():
    """The same pair, but the source declares nodata = 1."""
    files, src, ref = _make_pair(src_nodata=1.0)
    yield src, ref
    _close(files, src, ref)


# --- §2 pixel transforms ---------------------------------------------------


def test_resample_pixel_transform_maps_centres():
    cfg = minimal_config(resample=True, target_gsd_m=2.0)
    img = np.random.default_rng(0).uniform(1, 255, (80, 100)).astype(np.float32)
    res = run_pipeline(img, cfg, PreprocessContext(src_gsd_m=1.0))
    assert res.image.shape == (40, 50)
    assert _apply(res.pixel_transform, 49.5, 39.5) == pytest.approx((24.5, 19.5))
    assert _apply(res.pixel_transform, -0.5, -0.5) == pytest.approx((-0.5, -0.5))
    assert res.pixel_transform_source == ValueSource.COMPUTED.value


def test_no_geometric_step_gives_identity_transform():
    img = np.random.default_rng(1).uniform(1, 255, (30, 40)).astype(np.float32)
    res = run_pipeline(img, minimal_config(resample=False), PreprocessContext())
    np.testing.assert_array_equal(res.pixel_transform, np.eye(3))


def test_resample_noop_when_already_at_target():
    img = np.random.default_rng(1).uniform(1, 255, (30, 40)).astype(np.float32)
    res = run_pipeline(img, minimal_config(target_gsd_m=1.0), PreprocessContext(src_gsd_m=1.0))
    rec = _record(res, "resample")
    assert rec.status is StepStatus.NOOP and not rec.ran
    np.testing.assert_array_equal(res.pixel_transform, np.eye(3))


# --- §4 guards -------------------------------------------------------------


def test_cube_without_band_reduction_is_failed_not_raised():
    cfg = PreprocessConfig(
        band_reduction=False, resample=False, clahe=True, normalize=True, shadow=False
    )
    cube = np.random.default_rng(0).uniform(1, 255, (3, 20, 30)).astype(np.float32)
    res = run_pipeline(cube, cfg, PreprocessContext())
    assert res.failed
    rec = _record(res, "normalize")
    assert rec.status is StepStatus.FAILED
    assert rec.reason == "input is 3-D after band_reduction"
    assert res.status_counts == {"failed": 2}
    assert "PREPROCESSING FAILED" in res.report()


def test_georeference_rejects_a_mismatched_image(rasterio_pair):
    src, ref = rasterio_pair
    out = georeference(np.ones((10, 10), np.float32), src, ref)
    assert out.status is StepStatus.FAILED and not out.applied
    assert "does not match the source dataset grid" in out.reason


# --- §3 measured GSD ---------------------------------------------------------


def test_reference_side_uses_ref_gsd():
    img = np.ones((40, 40), np.float32) * 5
    img[5:10, 5:10] = 50
    cfg = PreprocessConfig(
        resample=True,
        normalize=False,
        clahe=False,
        shadow=False,
        band_reduction=False,
        target_gsd_m=2.0,
        side="reference",
    )
    res = run_pipeline(img, cfg, PreprocessContext(ref_gsd_m=1.0, src_gsd_m=4.0))
    assert res.image.shape == (20, 20)
    rec = _record(res, "resample")
    assert rec.detail["side"] == "reference" and rec.detail["src_gsd_m"] == 1.0
    assert rec.detail["gsd_source"] == "context"


def test_unknown_side_is_failed():
    cfg = minimal_config(target_gsd_m=2.0, side="left")
    res = run_pipeline(np.ones((8, 8), np.float32), cfg, PreprocessContext(src_gsd_m=1.0))
    rec = _record(res, "resample")
    assert rec.status is StepStatus.FAILED and "side" in rec.reason


def test_nominal_fallback_is_recorded_and_warned(caplog):
    img = np.ones((40, 40), np.float32) * 5
    img[5:10, 5:10] = 50
    cfg = PreprocessConfig(
        resample=True,
        normalize=False,
        clahe=False,
        shadow=False,
        band_reduction=False,
        target_gsd_m=1.0,
        source_sensor="OHRC",
    )
    with caplog.at_level(logging.WARNING, logger="lunar_reg.preprocess.pipeline"):
        res = run_pipeline(img, cfg, PreprocessContext())
    rec = _record(res, "resample")
    assert rec.ran
    assert rec.detail["gsd_source"] == "nominal"
    assert rec.detail["nominal_gsd_value_source"] == ValueSource.DOCUMENTED.value
    assert res.image.shape == (10, 10)  # nominal OHRC 0.25 m -> 1.0 m
    assert sum("nominal GSD" in r.getMessage() for r in caplog.records) == 1


def test_reference_side_nominal_fallback():
    cfg = PreprocessConfig(
        resample=True,
        normalize=False,
        clahe=False,
        shadow=False,
        band_reduction=False,
        target_gsd_m=1.0,
        side="reference",
        reference_sensor="LRO_NAC",
    )
    res = run_pipeline(np.full((20, 20), 7.0, np.float32), cfg, PreprocessContext(src_gsd_m=9.0))
    rec = _record(res, "resample")
    assert rec.detail["gsd_source"] == "nominal" and rec.detail["src_gsd_m"] == 0.5
    assert res.image.shape == (10, 10)


def test_missing_gsd_is_skipped_missing_input():
    cfg = minimal_config(target_gsd_m=1.0)
    res = run_pipeline(np.ones((8, 8), np.float32), cfg, PreprocessContext())
    rec = _record(res, "resample")
    assert rec.status is StepStatus.SKIPPED_MISSING_INPUT
    assert "src_gsd_m" in rec.reason


def test_sensor_specs_carry_gsd_provenance():
    assert all(s.gsd_source is ValueSource.DOCUMENTED for s in SENSORS.values())
    assert "1.0" in SENSORS["LRO_NAC"].gsd_note


# --- §6 valid-mask plumbing -------------------------------------------------


def test_valid_mask_honoured_by_normalize():
    img = np.random.default_rng(2).uniform(10, 900, (40, 50)).astype(np.float32)
    img[:, :5] = 0
    res = run_pipeline(img, minimal_config(), PreprocessContext(valid=img > 0))
    assert (res.image[:, :5] == 0).all()
    assert (res.image[:, 5:] >= 1).all()


def test_valid_mask_excludes_a_bright_invalid_band_from_normalize():
    # The invalid band is the image MAXIMUM, so only a mask that reaches to_uint8
    # can make it 0 and keep it out of the percentile stretch.
    img = np.random.default_rng(2).uniform(10, 900, (40, 50)).astype(np.float32)
    img[:, :5] = 5000.0
    valid = np.ones(img.shape, bool)
    valid[:, :5] = False
    masked = run_pipeline(img, minimal_config(), PreprocessContext(valid=valid)).image
    unmasked = run_pipeline(img, minimal_config(), PreprocessContext()).image
    assert (masked[:, :5] == 0).all()
    assert (unmasked[:, :5] > 0).all()
    assert (masked[:, 5:] >= 1).all()
    assert not np.array_equal(masked[:, 5:], unmasked[:, 5:])


def test_resample_resamples_valid_and_leaves_caller_context_alone():
    img = np.random.default_rng(3).uniform(10, 900, (80, 100)).astype(np.float32)
    img[:, :20] = 5000.0  # bright, invalid: only the resampled mask can zero it
    valid = np.ones(img.shape, bool)
    valid[:, :20] = False
    ctx = PreprocessContext(src_gsd_m=1.0, valid=valid)
    res = run_pipeline(img, minimal_config(target_gsd_m=2.0), ctx)
    unmasked = run_pipeline(img, minimal_config(target_gsd_m=2.0), PreprocessContext(src_gsd_m=1.0))
    assert res.image.shape == (40, 50)
    assert (res.image[:, :10] == 0).all()
    assert (res.image[:, 10:] >= 1).all()
    assert (unmasked.image[:, :10] > 0).all()
    assert not np.array_equal(res.image, unmasked.image)
    assert ctx.valid is valid  # run_pipeline works on a copy of the context


def test_resample_mask_uses_pixel_centre_geometry():
    # Factor-4 downsample, valid source columns 0..41. Output column j samples
    # source floor((j + 0.5) * 4), so j = 10 lands on column 42 (invalid);
    # plain INTER_NEAREST would sample column 40 and call it valid.
    valid = np.zeros((40, 100), bool)
    valid[:, :42] = True
    out = resample_mask(valid, (10, 25))
    assert out[:, :10].all()
    assert not out[:, 10:].any()


def test_resampled_mask_hides_half_nodata_blend():
    img = np.zeros((40, 100), np.float32)
    img[:, :42] = 200.0
    cfg = minimal_config(target_gsd_m=1.0)
    res = run_pipeline(img, cfg, PreprocessContext(src_gsd_m=0.25, valid=img > 0))
    assert res.image.shape == (10, 25)
    assert (res.image[:, 10:] == 0).all()  # col 10 averages 2 valid + 2 nodata pixels


def test_histogram_match_receives_reference_valid():
    rng = np.random.default_rng(4)
    img = rng.integers(1, 255, (30, 30)).astype(np.uint8)
    ref = rng.integers(100, 200, (30, 30)).astype(np.uint8)
    ref_valid = np.ones_like(ref, bool)
    ref_valid[:, :10] = False
    cfg = PreprocessConfig(
        resample=False,
        normalize=False,
        clahe=False,
        shadow=False,
        band_reduction=False,
        histogram_match=True,
    )
    res = run_pipeline(
        img,
        cfg,
        PreprocessContext(
            reference_image=ref, reference_valid=ref_valid, valid=np.ones_like(img, bool)
        ),
    )
    assert _record(res, "histogram_match").ran


# --- georeference through the pipeline ------------------------------------


def test_georeference_onto_reference_grid(rasterio_pair):
    src, ref = rasterio_pair
    img = np.random.default_rng(0).uniform(1, 255, (40, 50)).astype(np.float32)
    res = run_pipeline(img, _geo_only(), PreprocessContext(src_dataset=src, ref_dataset=ref))
    rec = _record(res, "georeference")
    assert rec.ran, rec.reason
    assert res.image.shape == (ref.height, ref.width)
    assert res.image.dtype == np.float32 and np.isnan(res.image).any()
    assert not np.allclose(res.pixel_transform, np.eye(3))
    assert rec.detail["pixel_transform_fit_rms_px"] < 0.01

    # The matrix agrees with the CRS transform for an interior source pixel centre.
    from rasterio.warp import transform as warp_transform

    x, y = 25.0, 20.0
    wx, wy = src.transform @ (x + 0.5, y + 0.5)
    (rx,), (ry,) = warp_transform(src.crs, ref.crs, [wx], [wy])
    col, row = ~ref.transform @ (rx, ry)
    assert _apply(res.pixel_transform, x, y) == pytest.approx((col - 0.5, row - 0.5), abs=0.01)


def test_georeference_without_valid_keeps_uncovered_pixels_nodata(rasterio_pair):
    src, ref = rasterio_pair
    img = np.random.default_rng(0).uniform(1, 255, (40, 50)).astype(np.float32)
    ctx = PreprocessContext(src_dataset=src, ref_dataset=ref)
    uncovered = np.isnan(run_pipeline(img, _geo_only(), ctx).image)
    assert uncovered.any() and not uncovered.all()
    cfg = _geo_only()
    cfg.normalize = True
    cfg.clahe = True
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        res = run_pipeline(img, cfg, ctx)
    assert res.steps_run == ("georeference", "normalize", "clahe") and not res.failed
    assert (res.image[uncovered] == 0).all()
    assert (res.image[~uncovered] >= 1).all()
    assert ctx.valid is None  # the caller's context is untouched


def test_georeference_valid_mask_ignores_dataset_nodata(rasterio_pair_nodata_one):
    # nodata = 1 must not turn the True (1) pixels of the mask into nodata.
    src, ref = rasterio_pair_nodata_one
    img = np.random.default_rng(0).uniform(10, 255, (40, 50)).astype(np.float32)
    cfg = _geo_only()
    cfg.normalize = True
    ctx = PreprocessContext(src_dataset=src, ref_dataset=ref, valid=np.ones_like(img, bool))
    res = run_pipeline(img, cfg, ctx)
    assert not res.failed, res.report()
    covered = res.image >= 1
    assert covered.mean() > 0.9 and (res.image[~covered] == 0).all()


def test_georeference_provenance(rasterio_pair):
    skipped = georeference(np.ones((3, 3)), None, None)
    assert skipped.pixel_transform is None
    assert skipped.pixel_transform_source == ValueSource.UNKNOWN.value
    assert skipped.pixel_transform_fit_rms_px_source == ValueSource.UNKNOWN.value

    src, ref = rasterio_pair
    img = np.random.default_rng(0).uniform(1, 255, (40, 50)).astype(np.float32)
    ran = georeference(img, src, ref)
    assert ran.pixel_transform_source == ValueSource.INFERRED.value
    assert ran.pixel_transform_fit_rms_px_source == ValueSource.COMPUTED.value

    cfg = _geo_only()
    cfg.resample = True
    cfg.target_gsd_m = 50.0
    ctx = PreprocessContext(src_dataset=src, ref_dataset=ref, src_gsd_m=25.0)
    res = run_pipeline(img, cfg, ctx)
    assert res.steps_run == ("georeference", "resample")
    rec = _record(res, "georeference")
    assert rec.detail["pixel_transform_source"] == ValueSource.INFERRED.value
    assert rec.detail["pixel_transform_fit_rms_px_source"] == ValueSource.COMPUTED.value
    assert _record(res, "resample").detail["pixel_transform_source"] == "computed"
    assert res.pixel_transform_source == ValueSource.INFERRED.value  # weakest factor


def test_georeference_reprojects_valid(rasterio_pair):
    src, ref = rasterio_pair
    img = np.random.default_rng(0).uniform(1, 255, (40, 50)).astype(np.float32)
    valid = np.ones_like(img, bool)
    cfg = _geo_only()
    cfg.normalize = True
    res = run_pipeline(img, cfg, PreprocessContext(src_dataset=src, ref_dataset=ref, valid=valid))
    assert res.steps_run == ("georeference", "normalize")
    assert res.image.shape == (ref.height, ref.width)
    assert (res.image == 0).any() and (res.image >= 1).any()


def test_georeference_same_crs_is_noop(rasterio_pair):
    src, _ = rasterio_pair
    img = np.ones((40, 50), np.float32)
    res = run_pipeline(img, _geo_only(), PreprocessContext(src_dataset=src, ref_dataset=src))
    assert _record(res, "georeference").status is StepStatus.NOOP


def test_georeference_without_datasets_is_skipped_missing_input():
    res = run_pipeline(np.ones((8, 8), np.float32), _geo_only(), PreprocessContext())
    assert _record(res, "georeference").status is StepStatus.SKIPPED_MISSING_INPUT


# --- §1 classified outcomes ---------------------------------------------------


def test_step_exception_is_failed_with_text(monkeypatch):
    def boom(image, config, context):
        raise RuntimeError("step broke")

    monkeypatch.setitem(pp._HANDLERS, "normalize", boom)
    res = run_pipeline(np.ones((10, 10), np.float32), minimal_config(), PreprocessContext())
    rec = _record(res, "normalize")
    assert rec.status is StepStatus.FAILED
    assert rec.reason == "RuntimeError: step broke"
    assert res.failed


def test_all_zero_output_is_degenerate():
    res = run_pipeline(np.zeros((16, 16), np.float32), minimal_config(), PreprocessContext())
    rec = _record(res, "normalize")
    assert rec.status is StepStatus.DEGENERATE_OUTPUT and not rec.ran
    assert res.failed
    assert res.status_counts[StepStatus.DEGENERATE_OUTPUT.value] == 1


def test_band_reduction_on_2d_is_noop():
    img = np.random.default_rng(6).uniform(1, 255, (8, 8)).astype(np.float32)
    res = run_pipeline(img, minimal_config(), PreprocessContext())
    assert _record(res, "band_reduction").status is StepStatus.NOOP
    assert not res.failed


# --- §5 placeholders actually used -------------------------------------------


def test_uses_placeholders_only_when_value_equals_placeholder():
    img = np.random.default_rng(5).uniform(1, 255, (32, 32)).astype(np.float32)
    base = PreprocessConfig(resample=False, shadow=False, band_reduction=False, clahe=True)
    assert "clahe_clip_limit" in run_pipeline(img, base).uses_placeholders
    tuned = PreprocessConfig(
        resample=False, shadow=False, band_reduction=False, clahe=True, clahe_clip_limit=3.5
    )
    used = run_pipeline(img, tuned).uses_placeholders
    assert "clahe_clip_limit" not in used and "clahe_tile_grid" in used
