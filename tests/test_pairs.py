"""Window-pair preparation (CONTRACTS C11, Phase_1/LLD/pairs.md §2), synthetic end to end.

No real data: a small PDS4 source label (the documented layout from
``tests/test_ingest_labels.py``) over a raw uint8 image, and a reference GeoTIFF
whose own transform is deliberately wrong -- only its pixels are read, the
georeference is a :class:`GeoReference` built directly (C10). The source is a
resampled crop of the reference, so every source pixel has a known reference
position: source (s, l) -> reference (C0 + s / 2, R0 + l / 2) native px.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from tests.test_ingest_labels import _pds4_label

NAC_PROJ = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m +no_defs"
MOON_GEO = "+proj=longlat +R=1737400 +no_defs"
X0, Y0, PSX = -2000.0, 615000.0, 0.5  # reference: 600 x 600 px at 0.5 m
REF_N = 600
C0, R0 = 120, 90  # reference px of the source's upper-left outer corner
LINES, SAMPLES = 400, 300  # source at OHRC 0.25 m -> 200 x 150 reference px
STEM = "ch2_ohr_ncp_20240425T1406019344_d_img_d18"
GRID_STEM = "ch2_ohr_ncp_20240425T1406019344_g_grd_d18"
C04_GEOMETRY_KEYS = {
    "ref_crop_c0", "ref_crop_r0", "ref_factor", "shift_e_m", "shift_s_m", "src_win_l0",
    "src_win_s0", "src_win_lines", "src_win_samples", "gsd_m", "crop_geometry_source",
}  # fmt: skip


def _lonlat(cols, rows):
    """(lat, lon) arrays of reference native px (corner convention)."""
    from rasterio.warp import transform

    cols, rows = np.atleast_1d(cols), np.atleast_1d(rows)
    lon, lat = transform(NAC_PROJ, MOON_GEO, list(X0 + cols * PSX), list(Y0 - rows * PSX))
    return np.asarray(lat), np.asarray(lon)


def _reference_pixels(seed=5):
    import cv2

    rng = np.random.default_rng(seed)
    g = cv2.GaussianBlur(rng.normal(0, 1, (REF_N, REF_N)).astype(np.float32), (0, 0), 2.0)
    return (1 + (g - g.min()) / (g.max() - g.min()) * 250).astype(np.uint8)


def _write_reference(path, pixels):
    import rasterio
    from rasterio.transform import from_origin

    with rasterio.open(path, "w", driver="GTiff", width=REF_N, height=REF_N, count=1,
                       dtype="uint8", transform=from_origin(0, 0, 1, 1)) as ds:  # fmt: skip
        ds.write(pixels, 1)


def _corner_geometry():
    lat, lon = _lonlat(
        [C0, C0 + SAMPLES / 2, C0, C0 + SAMPLES / 2], [R0, R0, R0 + LINES / 2, R0 + LINES / 2]
    )
    names = ("upper_left", "upper_right", "lower_left", "lower_right")
    geometry = {}
    for name, a, o in zip(names, lat, lon, strict=True):
        geometry[f"{name}_latitude"], geometry[f"{name}_longitude"] = f"{a:.10f}", f"{o:.10f}"
    return geometry


def _real_lid(stem):
    """The logical_identifier form of real CH-2 calibrated labels: lower case, so
    the timestamp separator is ``t`` while the file stem has ``T``."""
    return f"urn:isro:isda:ch2_cho.ohr:data_calibrated:{stem.lower()}"


def _write_source(directory, image, *, geometry=True, bands=1, stem=STEM, lid=True):
    directory.mkdir(parents=True, exist_ok=True)
    if bands == 1:
        axes = (("Line", LINES), ("Sample", SAMPLES))
        kind = "Array_2D_Image"
    else:
        axes = (("Band", bands), ("Line", LINES), ("Sample", SAMPLES))
        kind = "Array_3D_Spectrum"
    label = directory / f"{stem}.xml"
    label.write_text(
        _pds4_label(
            lid=_real_lid(stem),
            file_name=f"{stem}.img",
            axes=axes,
            array_kind=kind,
            data_type="UnsignedByte",
            geometry=_corner_geometry() if geometry else None,
        )
    )
    if not lid:
        text = label.read_text()
        start = text.index("<logical_identifier>")
        end = text.index("</logical_identifier>") + len("</logical_identifier>")
        label.write_text(text[:start] + text[end:])
    (directory / f"{stem}.img").write_bytes(np.ascontiguousarray(image, np.uint8).tobytes())
    return label


@pytest.fixture
def scene(tmp_path):
    """``(label, reference_path, geo, ref_pixels)`` with label corners and no grid."""
    import cv2

    from lunar_reg.ingest.lro import GeoReference
    from lunar_reg.provenance import ValueSource

    ref = _reference_pixels()
    ref_path = tmp_path / "ref.tif"
    _write_reference(ref_path, ref)
    geo = GeoReference(NAC_PROJ, X0, Y0, PSX, PSX, REF_N, REF_N, ValueSource.DOCUMENTED)
    crop = ref[R0 : R0 + LINES // 2, C0 : C0 + SAMPLES // 2]
    src = cv2.resize(crop, (SAMPLES, LINES), interpolation=cv2.INTER_LINEAR)
    label = _write_source(tmp_path / "src", src)
    return label, ref_path, geo, ref


def _prepare(label, ref_path, geo, **kw):
    from lunar_reg.pairs import prepare_window_pair

    args = {"gsd_m": 1.0, "window_m": 40.0, "margin_m": 10.0} | kw
    return prepare_window_pair(label, ref_path, geo, **args)


def _apply(m, x, y):
    p = np.asarray(m, dtype=np.float64) @ np.array([x, y, 1.0])
    return p[:2] / p[2]


# --------------------------------------------------------------------- LLD §2


def test_ok_outcome_and_shapes(scene):
    from lunar_reg.pairs import PrepStatus, PriorSource

    label, ref_path, geo, _ = scene
    out = _prepare(label, ref_path, geo)
    assert out.status is PrepStatus.OK, out.detail
    pair = out.pair
    assert pair.prior_source is PriorSource.LABEL_CORNERS
    # window 40 m at 0.25 m = 160 native px, centred on line 200 and sample 150
    assert pair.source_window == (120, 70, 160, 160)
    assert pair.source.shape == (40, 40) and pair.source.dtype == np.uint8
    assert pair.source_valid.dtype == bool and pair.source_valid.all()
    assert pair.reference.dtype == np.uint8 and pair.reference_valid.shape == pair.reference.shape
    assert pair.prior.shape == (3, 3) and pair.prior.dtype == np.float64
    assert pair.source_native_gsd_m == 0.25 and pair.reference_native_gsd_m == PSX
    assert pair.source_id == STEM.lower() and pair.reference_id == "ref"
    assert pair.provenance == {
        "src_gsd": "documented",
        "reference_georef": "documented",
        "corners": "documented",
        "shift_m": "computed",
    }


def test_prior_maps_window_centre_to_known_position(scene):
    label, ref_path, geo, _ = scene
    pair = _prepare(label, ref_path, geo).pair
    l0, s0, h, w = pair.source_window
    # known reference native position of the source window centre
    col = C0 + (s0 + w / 2) / 2
    row = R0 + (l0 + h / 2) / 2
    r0, c0, _, _ = pair.reference_window
    factor = pair.gsd_m / PSX
    expected = ((col - c0) / factor, (row - r0) / factor)
    sh, sw = pair.source.shape
    assert tuple(_apply(pair.prior, sw / 2, sh / 2)) == pytest.approx(expected, abs=1.0)


def test_geometry_extra_is_the_c04_set_plus_prior_source(scene):
    label, ref_path, geo, _ = scene
    pair = _prepare(label, ref_path, geo).pair
    extra = pair.geometry_extra()
    assert set(extra) == C04_GEOMETRY_KEYS | {"prior_source"}
    assert extra["crop_geometry_source"] == "recorded"
    assert extra["prior_source"] == "label_corners"
    r0, c0, _, _ = pair.reference_window
    l0, s0, h, w = pair.source_window
    assert (extra["ref_crop_c0"], extra["ref_crop_r0"]) == (c0, r0)
    assert (extra["src_win_l0"], extra["src_win_s0"]) == (l0, s0)
    assert (extra["src_win_lines"], extra["src_win_samples"]) == (h, w)
    assert extra["ref_factor"] == pytest.approx(1.0 / PSX) and extra["gsd_m"] == 1.0
    types = {k: type(v) for k, v in extra.items()}
    assert types["ref_crop_c0"] is int and types["ref_factor"] is float
    assert types["shift_e_m"] is float and types["src_win_lines"] is int


def test_shift_east_moves_reference_crop(scene):
    label, ref_path, geo, _ = scene
    a = _prepare(label, ref_path, geo).pair
    b = _prepare(label, ref_path, geo, shift_m=(40.0, 0.0)).pair
    ea, eb = a.geometry_extra(), b.geometry_extra()
    assert eb["ref_crop_c0"] - ea["ref_crop_c0"] == pytest.approx(40.0 / PSX, abs=1)
    assert eb["ref_crop_r0"] == ea["ref_crop_r0"]
    assert eb["shift_e_m"] == 40.0 and eb["shift_s_m"] == 0.0
    assert b.provenance["shift_m"] == "inferred"
    # the prior stays the unshifted label prior: its target moves by -shift in working px
    sh, sw = a.source.shape
    da = _apply(a.prior, sw / 2, sh / 2)
    db = _apply(b.prior, sw / 2, sh / 2)
    assert db[0] - da[0] == pytest.approx(-40.0, abs=1.0)


def test_shift_south_moves_rows(scene):
    label, ref_path, geo, _ = scene
    a = _prepare(label, ref_path, geo).pair
    b = _prepare(label, ref_path, geo, shift_m=(0.0, 20.0)).pair
    assert b.reference_window[0] - a.reference_window[0] == pytest.approx(20.0 / PSX, abs=1)


def test_reference_far_away_is_outside_reference(scene):
    from lunar_reg.pairs import PrepStatus

    label, ref_path, geo, _ = scene
    out = _prepare(label, ref_path, geo, shift_m=(20000.0, 0.0))
    assert out.status is PrepStatus.OUTSIDE_REFERENCE and out.pair is None
    assert out.detail


def test_label_without_corners_and_no_grid_is_no_footprint(tmp_path, scene):
    from lunar_reg.pairs import PrepStatus

    _, ref_path, geo, _ = scene
    label = _write_source(
        tmp_path / "bare", np.ones((LINES, SAMPLES), np.uint8), geometry=False, stem="bare_x"
    )
    out = _prepare(label, ref_path, geo)
    assert out.status is PrepStatus.NO_FOOTPRINT and out.pair is None


# --------------------------------------------------------------------- more outcomes


def test_unreadable_label(tmp_path, scene):
    from lunar_reg.pairs import PrepStatus

    _, ref_path, geo, _ = scene
    bad = tmp_path / "bad.xml"
    bad.write_text("<not xml")
    assert _prepare(bad, ref_path, geo).status is PrepStatus.LABEL_UNREADABLE


def test_unknown_sensor_is_label_unreadable(tmp_path, scene):
    from lunar_reg.pairs import PrepStatus

    _, ref_path, geo, _ = scene
    label = tmp_path / "mystery.xml"
    label.write_text(_pds4_label(lid="urn:x:mystery", file_name="m.img",
                                 axes=(("Line", 10), ("Sample", 10))))  # fmt: skip
    out = _prepare(label, ref_path, geo)
    assert out.status is PrepStatus.LABEL_UNREADABLE
    assert out.detail == "no nominal GSD for sensor None"


def test_nodata_reference_is_empty_reference(tmp_path, scene):
    from lunar_reg.pairs import PrepStatus

    label, _, geo, _ = scene
    zeros = tmp_path / "zeros.tif"
    _write_reference(zeros, np.zeros((REF_N, REF_N), np.uint8))
    out = _prepare(label, zeros, geo)
    assert out.status is PrepStatus.EMPTY_REFERENCE and out.pair is None


def test_missing_reference_file_is_read_failed(tmp_path, scene):
    from lunar_reg.pairs import PrepStatus

    label, _, geo, _ = scene
    out = _prepare(label, tmp_path / "nope.tif", geo)
    assert out.status is PrepStatus.READ_FAILED


def test_programmer_errors_raise(scene):
    label, ref_path, geo, _ = scene
    with pytest.raises(ValueError):
        _prepare(label, ref_path, geo, band_reduction="median")
    with pytest.raises(ValueError):
        _prepare(label, ref_path, geo, gsd_m=0.0)
    with pytest.raises(ValueError):
        _prepare(label, ref_path, geo, centre_line=LINES)


# --------------------------------------------------------------------- geometry


def test_to_native_follows_pixel_centre_convention(scene):
    label, ref_path, geo, _ = scene
    pair = _prepare(label, ref_path, geo).pair
    l0, s0, h, w = pair.source_window
    sh, sw = pair.source.shape
    fx, fy = w / sw, h / sh
    assert tuple(_apply(pair.source_to_native, 0, 0)) == pytest.approx(
        (s0 + (fx - 1) / 2, l0 + (fy - 1) / 2)
    )
    r0, c0, rh, rw = pair.reference_window
    rsh, rsw = pair.reference.shape
    gx, gy = rw / rsw, rh / rsh
    assert tuple(_apply(pair.reference_to_native, 0, 0)) == pytest.approx(
        (c0 + (gx - 1) / 2, r0 + (gy - 1) / 2)
    )


def test_reference_crop_holds_the_source_content(scene):
    """The working reference at the prior's position looks like the working source."""
    import cv2

    label, ref_path, geo, _ = scene
    pair = _prepare(label, ref_path, geo, gsd_m=0.5, window_m=40.0, margin_m=10.0).pair
    sh, sw = pair.source.shape
    warped = cv2.warpPerspective(pair.reference, np.linalg.inv(pair.prior), (sw, sh))
    a = pair.source.astype(np.float64).ravel()
    b = warped.astype(np.float64).ravel()
    assert np.corrcoef(a, b)[0, 1] > 0.8


def test_decimated_read_path(scene):
    """gsd 2 m from 0.25 m is a factor 8 shrink: read decimated, same geometry."""
    label, ref_path, geo, _ = scene
    pair = _prepare(label, ref_path, geo, gsd_m=2.0, window_m=40.0).pair
    assert pair.source.shape == (20, 20)
    assert pair.source_to_native[0, 0] == pytest.approx(8.0)
    assert pair.source_valid.all()


def test_centre_line_moves_the_source_window(scene):
    label, ref_path, geo, _ = scene
    pair = _prepare(label, ref_path, geo, centre_line=100).pair
    assert pair.source_window[:2] == (20, 70)
    # near the end the window is clamped inside the product
    pair = _prepare(label, ref_path, geo, centre_line=LINES - 1).pair
    assert pair.source_window[0] + pair.source_window[2] == LINES


# --------------------------------------------------------------------- geometry grid


def _write_grid(csv_path, lines=LINES, samples=SAMPLES, step=50, last_scan=None):
    """A ``Longitude,Latitude,Pixel,Scan`` grid of pixel-centre ground positions."""
    last_scan = lines - 1 if last_scan is None else last_scan
    scans = sorted(set(range(0, last_scan + 1, step)) | {last_scan})
    pixels = sorted(set(range(0, samples, step)) | {samples - 1})
    ss, pp = np.meshgrid(scans, pixels, indexing="ij")
    lat, lon = _lonlat(C0 + (pp.ravel() + 0.5) / 2, R0 + (ss.ravel() + 0.5) / 2)
    rows = [f"{o:.10f},{a:.10f},{p},{s}" for o, a, p, s in
            zip(lon, lat, pp.ravel(), ss.ravel(), strict=True)]  # fmt: skip
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text("Longitude,Latitude,Pixel,Scan\n" + "".join(r + "\r\n" for r in rows))
    return csv_path


def _bundle(tmp_path, scene, lid=True, **grid_kw):
    """The CH-2 bundle layout: data/calibrated/<date>/ and geometry/calibrated/<date>/."""
    _, _, _, ref = scene
    import cv2

    crop = ref[R0 : R0 + LINES // 2, C0 : C0 + SAMPLES // 2]
    src = cv2.resize(crop, (SAMPLES, LINES), interpolation=cv2.INTER_LINEAR)
    root = tmp_path / "bundle" / STEM
    label = _write_source(root / "data" / "calibrated" / "20240425", src, geometry=False, lid=lid)
    grid_dir = root / "geometry" / "calibrated" / "20240425"
    grid = _write_grid(grid_dir / f"{GRID_STEM}.csv", **grid_kw)
    return label, grid


def test_geometry_grid_found_in_bundle(tmp_path, scene):
    from lunar_reg.pairs import PrepStatus, PriorSource

    _, ref_path, geo, _ = scene
    label, _ = _bundle(tmp_path, scene)
    out = _prepare(label, ref_path, geo)
    assert out.status is PrepStatus.OK, out.detail
    pair = out.pair
    assert pair.prior_source is PriorSource.GEOMETRY_GRID
    assert pair.geometry_extra()["prior_source"] == "geometry_grid"
    l0, s0, h, w = pair.source_window
    r0, c0, _, _ = pair.reference_window
    factor = pair.gsd_m / PSX
    col, row = C0 + (s0 + w / 2) / 2, R0 + (l0 + h / 2) / 2
    sh, sw = pair.source.shape
    assert tuple(_apply(pair.prior, sw / 2, sh / 2)) == pytest.approx(
        ((col - c0) / factor, (row - r0) / factor), abs=1.0
    )


def test_bundle_grid_found_from_real_lower_case_lid_without_token_warning(tmp_path, scene, caplog):
    """Real LIDs carry ``...20240425t1406019344...`` (lower-case ``t``); the grid
    file name carries ``T``. Discovery must still find it, with no warning."""
    import logging

    from lunar_reg.ingest.pds4 import read_label
    from lunar_reg.pairs import PrepStatus, PriorSource

    _, ref_path, geo, _ = scene
    label, grid = _bundle(tmp_path, scene)
    product_id = read_label(label).product_id
    assert "20240425t1406019344" in product_id and "20240425T" in grid.name
    with caplog.at_level(logging.WARNING):
        out = _prepare(label, ref_path, geo)
    assert out.status is PrepStatus.OK, out.detail
    assert out.pair.prior_source is PriorSource.GEOMETRY_GRID
    assert not [r for r in caplog.records if "timestamp token" in r.getMessage()]


def test_label_without_lid_uses_the_stem_token_for_the_grid(tmp_path, scene):
    from lunar_reg.ingest.pds4 import read_label
    from lunar_reg.pairs import PrepStatus, PriorSource

    _, ref_path, geo, _ = scene
    label, _ = _bundle(tmp_path, scene, lid=False)
    assert read_label(label).product_id is None
    out = _prepare(label, ref_path, geo)
    assert out.status is PrepStatus.OK, out.detail
    assert out.pair.prior_source is PriorSource.GEOMETRY_GRID


def test_foreign_grid_next_to_a_label_without_lid_is_not_used(tmp_path, scene):
    """No LID and no timestamp in the stem: discovery is skipped, never run
    unfiltered, so another product's grid is not taken as this one's."""
    from lunar_reg.ingest.pds4 import read_label
    from lunar_reg.pairs import PrepStatus, PriorSource

    label0, ref_path, geo, _ = scene
    src = np.fromfile(label0.with_suffix(".img"), np.uint8).reshape(LINES, SAMPLES)
    flat = tmp_path / "flat"
    label = _write_source(flat / "lbl", src, stem="ch2_ohr_ncp_notoken_d_img_d18", lid=False)
    assert read_label(label).product_id is None
    # a valid grid of a different product, under the label dir's parent
    _write_grid(flat / "other" / "ch2_ohr_ncp_20990101T0000000000_g_grd_d18.csv")
    out = _prepare(label, ref_path, geo)
    assert out.status is PrepStatus.OK, out.detail
    assert out.pair.prior_source is PriorSource.LABEL_CORNERS
    bare = _write_source(
        flat / "bare", src, geometry=False, stem="ch2_ohr_ncp_notoken2_d_img_d18", lid=False
    )
    out = _prepare(bare, ref_path, geo)
    assert out.status is PrepStatus.NO_FOOTPRINT and out.pair is None


def test_foreign_grid_in_bundle_is_not_used(tmp_path, scene):
    """A grid whose timestamp differs from the product's is never matched."""
    from lunar_reg.pairs import PrepStatus

    _, ref_path, geo, _ = scene
    label, grid = _bundle(tmp_path, scene)
    grid.rename(grid.with_name("ch2_ohr_ncp_20990101T0000000000_g_grd_d18.csv"))
    out = _prepare(label, ref_path, geo)
    assert out.status is PrepStatus.NO_FOOTPRINT and out.pair is None


def test_explicit_grid_path_wins_over_label_corners(tmp_path, scene):
    from lunar_reg.pairs import PriorSource

    label, ref_path, geo, _ = scene
    grid = _write_grid(tmp_path / "elsewhere" / f"{GRID_STEM}.csv")
    pair = _prepare(label, ref_path, geo, geometry_grid_path=grid).pair
    assert pair.prior_source is PriorSource.GEOMETRY_GRID


def test_grid_short_of_the_window_is_no_footprint(tmp_path, scene):
    from lunar_reg.pairs import PrepStatus

    _, ref_path, geo, _ = scene
    label, _ = _bundle(tmp_path, scene, last_scan=100)
    out = _prepare(label, ref_path, geo)
    assert out.status is PrepStatus.NO_FOOTPRINT
    assert "does not cover" in out.detail


def test_unreadable_grid_is_read_failed_not_a_fallback(tmp_path, scene):
    from lunar_reg.pairs import PrepStatus

    label, ref_path, geo, _ = scene
    grid = tmp_path / f"{GRID_STEM}.csv"
    grid.write_text("")
    out = _prepare(label, ref_path, geo, geometry_grid_path=grid)
    assert out.status is PrepStatus.READ_FAILED
    assert GRID_STEM in out.detail


# --------------------------------------------------------------------- multi-band


@pytest.mark.parametrize("method", ["first", "mean", "pca"])
def test_multiband_source_is_reduced(tmp_path, scene, method):
    import cv2

    _, ref_path, geo, ref = scene
    crop = ref[R0 : R0 + LINES // 2, C0 : C0 + SAMPLES // 2]
    band = cv2.resize(crop, (SAMPLES, LINES), interpolation=cv2.INTER_LINEAR)
    cube = np.stack([band, np.clip(band.astype(int) // 2 + 3, 1, 255).astype(np.uint8)])
    label = _write_source(tmp_path / "cube", cube, bands=2, stem=f"{STEM}_cube")
    out = _prepare(label, ref_path, geo, band_reduction=method)
    assert out.pair is not None, out.detail
    pair = out.pair
    assert pair.source.ndim == 2 and pair.source.dtype == np.uint8
    assert pair.provenance["band_reduction"] == method
    first = _prepare(label, ref_path, geo).pair.source.astype(float).ravel()
    # every reduction of two linearly related bands keeps the spatial pattern
    assert abs(np.corrcoef(first, pair.source.astype(float).ravel())[0, 1]) > 0.95


@pytest.mark.parametrize("method", ["first", "mean", "pca"])
def test_all_nodata_multiband_source_does_not_raise(tmp_path, scene, method):
    """An all-nodata cube window is a bad item: classified outcome, never an exception."""
    _, ref_path, geo, _ = scene
    cube = np.zeros((2, LINES, SAMPLES), np.uint8)
    label = _write_source(tmp_path / "empty", cube, bands=2, stem=f"{STEM}_empty")
    out = _prepare(label, ref_path, geo, band_reduction=method)
    assert out.pair is not None, out.detail
    assert not out.pair.source_valid.any() and not out.pair.source.any()


def test_single_band_records_no_band_reduction(scene):
    label, ref_path, geo, _ = scene
    assert "band_reduction" not in _prepare(label, ref_path, geo).pair.provenance


# --------------------------------------------------------------------- contract shape


def test_contract_shapes():
    from lunar_reg.ingest.overlap import PriorSource as OverlapPriorSource
    from lunar_reg.pairs import PrepOutcome, PrepStatus, PriorSource, WindowPair

    assert PriorSource is OverlapPriorSource
    assert {m.value for m in PrepStatus} == {
        "ok", "label_unreadable", "no_footprint", "outside_reference", "empty_reference",
        "read_failed",
    }  # fmt: skip
    assert not PrepStatus.OK.is_failure and PrepStatus.READ_FAILED.is_failure
    assert [f.name for f in dataclasses.fields(PrepOutcome)] == ["status", "pair", "detail"]
    assert "provenance" in {f.name for f in dataclasses.fields(WindowPair)}


def test_diagnostics_counts_and_samples(scene):
    from lunar_reg.pairs import PrepDiagnostics, PrepStatus

    label, ref_path, geo, _ = scene
    diag = PrepDiagnostics()
    diag.record(_prepare(label, ref_path, geo), "a")
    diag.record(_prepare(label, ref_path, geo, shift_m=(20000.0, 0.0)), "b")
    diag.record(_prepare(label, ref_path, geo, shift_m=(30000.0, 0.0)), "c")
    assert diag.counts == {"ok": 1, "outside_reference": 2}
    assert diag.n_failed == 2
    assert diag.samples[PrepStatus.OUTSIDE_REFERENCE.value].startswith("b: ")
    text = diag.report()
    assert "3 attempted, 1 ok, 2 failed" in text
    assert "outside_reference: 2" in text
