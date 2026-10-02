"""Cross-instrument pairs at any site (CONTRACTS C10/C11/C28, Phase_1/LLD/cross_pairs.md §7).

All offline and synthetic. The end-to-end ``run_cross.py run`` test drives the
real pair preparation, ``register_pair`` and results store on a source that is a
resampled crop of a georeferenced reference (helpers from ``tests/test_pairs.py``);
only the product catalog is stubbed.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from tests.test_pairs import (
    C0,
    LINES,
    NAC_PROJ,
    PSX,
    R0,
    REF_N,
    SAMPLES,
    STEM,
    X0,
    Y0,
    _reference_pixels,
    _write_source,
)

REPO = Path(__file__).resolve().parents[1]
R_M = 1737400.0
EQC = "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"


def _eqc(tmp_path, *, lon=(31.5, 33.0), lat=(-70.0, -68.7), px=100.0, fill=False,
         lbl_offset_px=None, name="ref", crs=EQC, transform=None):  # fmt: skip
    """North-up eqc GeoTIFF on the lunar sphere, optionally with a PDS3 bounds label."""
    import rasterio
    from rasterio.transform import from_origin

    k = R_M * np.pi / 180.0
    w = int(round((lon[1] - lon[0]) * k / px))
    h = int(round((lat[1] - lat[0]) * k / px))
    data = (
        np.zeros((h, w), np.uint8)
        if fill
        else np.random.default_rng(0).integers(20, 250, (h, w)).astype(np.uint8)
    )
    path = tmp_path / f"{name}.tif"
    profile = dict(driver="GTiff", width=w, height=h, count=1, dtype="uint8")
    if crs is not None:
        profile["crs"] = crs
        profile["transform"] = transform or from_origin(lon[0] * k, lat[1] * k, px, px)
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(data, 1)
    if lbl_offset_px is not None:
        d = lbl_offset_px * px / k
        (tmp_path / f"{name}.lbl").write_text(
            f"MAXIMUM_LATITUDE = {lat[1] + d:.6f} <deg>\n"
            f"MINIMUM_LATITUDE = {lat[0] + d:.6f} <deg>\n"
            f"WESTERNMOST_LONGITUDE = {lon[0]:.6f} <deg>\n"
            f"EASTERNMOST_LONGITUDE = {lon[1]:.6f} <deg>\n"
        )
    return path


def _grid(lat, lon):
    from lunar_reg.ingest.geometry_grid import GeometryGrid

    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    return GeometryGrid(
        scan_lines=np.arange(lat.shape[0]) * 100,
        pixels=np.arange(lat.shape[1]) * 100,
        lat=lat,
        lon=lon,
    )


def _overlap(grid, path, *, independent=True):
    from lunar_reg.cross import ReferenceSpec, overlap_for_grid, reference_validity
    from lunar_reg.ingest.lro import georeference_from_raster

    geo = georeference_from_raster(path)
    spec = ReferenceSpec("ref", str(path), "raster", "TEST_ORTHO", independent)
    return overlap_for_grid(
        "p", "TMC2", "calibrated", grid, spec, geo, reference_validity(spec, geo),
        nominal_gsd_m=5.0,
    )  # fmt: skip


def _strip_over_reference():
    lat = np.linspace(-69.8, -68.9, 30)[:, None] + np.zeros((1, 9))
    lon = np.zeros((30, 1)) + np.linspace(32.0, 32.6, 9)[None]
    return _grid(lat, lon)


# ------------------------------------------------------------------ C10 raster georeference


def test_raster_georef_matching_label_bounds_is_documented(tmp_path):
    from lunar_reg.ingest.lro import georeference_from_raster
    from lunar_reg.provenance import ValueSource

    geo = georeference_from_raster(_eqc(tmp_path, lbl_offset_px=0.0))
    k = R_M * np.pi / 180.0
    assert geo.source is ValueSource.DOCUMENTED
    assert (geo.x0_m, geo.y0_m) == pytest.approx((31.5 * k, -68.7 * k))
    assert (geo.pixel_size_x_m, geo.pixel_size_y_m) == pytest.approx((100.0, 100.0))
    assert "+proj=eqc" in geo.crs_proj4 and "+R=1737400" in geo.crs_proj4
    assert "agree" in geo.note


def test_raster_georef_label_off_by_ten_pixels_is_inferred(tmp_path):
    from lunar_reg.ingest.lro import georeference_from_raster
    from lunar_reg.provenance import ValueSource

    geo = georeference_from_raster(_eqc(tmp_path, lbl_offset_px=10.0))
    assert geo.source is ValueSource.INFERRED
    assert "disagree" in geo.note and " m (" in geo.note


@pytest.mark.parametrize("case", ["no_crs", "rotated", "merc"])
def test_raster_georef_rejects_unsupported_rasters(tmp_path, case):
    from rasterio.transform import Affine

    from lunar_reg.ingest.lro import LabelGeoreferenceError, georeference_from_raster

    if case == "no_crs":
        path, reason = _eqc(tmp_path, crs=None), "no CRS"
    elif case == "rotated":
        path, reason = _eqc(tmp_path, transform=Affine(10, 2, 0, 2, -10, 0)), "north-up"
    else:
        merc = "+proj=merc +lon_0=0 +R=1737400 +units=m +no_defs"
        path, reason = _eqc(tmp_path, crs=merc), "unsupported CRS"
    with pytest.raises(LabelGeoreferenceError, match=reason):
        georeference_from_raster(path)


# ------------------------------------------------------------------ C11 centre_sample


def test_centre_sample_moves_and_clamps_the_source_window(tmp_path):
    from tests.test_pairs import _write_reference

    from lunar_reg.ingest.lro import GeoReference
    from lunar_reg.pairs import PrepStatus, prepare_window_pair
    from lunar_reg.provenance import ValueSource

    ref_path = tmp_path / "ref.tif"
    _write_reference(ref_path, _reference_pixels())
    geo = GeoReference(NAC_PROJ, X0, Y0, PSX, PSX, REF_N, REF_N, ValueSource.DOCUMENTED)
    src = np.random.default_rng(1).integers(1, 255, (LINES, SAMPLES)).astype(np.uint8)
    label = _write_source(tmp_path / "src", src)
    args = dict(gsd_m=1.0, window_m=40.0, margin_m=10.0)  # 160 x 160 native px window

    def col_off(**kw):
        out = prepare_window_pair(label, ref_path, geo, **args, **kw)
        assert out.status is PrepStatus.OK, out.detail
        return out.pair.source_window[1]

    assert col_off() == SAMPLES // 2 - 80  # default: centred on the middle sample
    assert col_off(centre_sample=100) == 20
    assert col_off(centre_sample=0) == 0  # clamped at the left edge
    assert col_off(centre_sample=SAMPLES - 1) == SAMPLES - 160  # and at the right edge
    with pytest.raises(ValueError, match="centre_sample"):
        prepare_window_pair(label, ref_path, geo, **args, centre_sample=SAMPLES)


# ------------------------------------------------------------------ C28 overlaps


def test_pole_crossing_strip_is_disjoint_from_a_site_reference(tmp_path):
    """The P1.DL trap: corner longitudes span > 180 deg, yet the strip is far from Vikram."""
    from lunar_reg.cross import OverlapStatus

    down = np.linspace(-61.0, -89.6, 40)
    lat = np.r_[down, down[::-1]][:, None] + np.zeros((1, 5))
    lon = np.r_[np.full(40, 77.0), np.full(40, 257.0)][:, None] + np.linspace(-0.4, 0.4, 5)[None]
    assert np.ptp(lon) > 180
    c = _overlap(_grid(lat, lon), _eqc(tmp_path))
    assert c.status is OverlapStatus.DISJOINT and c.n_inside == 0
    assert c.min_distance_km is not None and c.min_distance_km > 400
    assert c.centre_line is None and c.overlap_km2 is None


def test_strip_over_reference_overlaps_at_a_grid_node(tmp_path):
    from lunar_reg.cross import OverlapStatus
    from lunar_reg.ingest.lro import georeference_from_raster

    path = _eqc(tmp_path)
    grid = _strip_over_reference()
    c = _overlap(grid, path, independent=False)
    assert c.status is OverlapStatus.OVERLAP and c.n_inside >= 4
    assert c.centre_line in set(grid.scan_lines) and c.centre_sample in set(grid.pixels)
    i = list(grid.scan_lines).index(c.centre_line)
    j = list(grid.pixels).index(c.centre_sample)
    assert (c.centre_lat, c.centre_lon) == pytest.approx((grid.lat[i, j], grid.lon[i, j]))
    geo = georeference_from_raster(path)
    col, row = geo.lonlat_to_pixel(lon=c.centre_lon, lat=c.centre_lat)
    assert 0 <= col < geo.width and 0 <= row < geo.height
    assert c.overlap_km2 > 0 and c.overlap_source == "computed"
    assert c.reference_independent is False and c.reference_georef_source == "inferred"


def test_all_fill_reference_is_never_an_overlap(tmp_path):
    from lunar_reg.cross import OverlapStatus

    c = _overlap(_strip_over_reference(), _eqc(tmp_path, fill=True))
    assert c.status is OverlapStatus.DISJOINT and c.n_inside == 0
    assert "no valid pixels" in c.detail


def test_missing_reference_is_counted_not_raised(tmp_path, monkeypatch):
    from lunar_reg.cross import OverlapStatus, ReferenceSpec, find_overlaps
    from lunar_reg.ingest import catalog as catalog_mod
    from lunar_reg.ingest.catalog import (
        CatalogEntry,
        InstrumentStatus,
        ProductCatalog,
        ScanDiagnostics,
    )

    entry = CatalogEntry(
        instrument="TMC2", product_id="ch2_tmc_ncn_x", label_path=tmp_path / "x.xml",
        image_path=None, level="calibrated", product_type="data", geometry_grid_path=None,
    )  # fmt: skip
    cat = ProductCatalog(
        entries=[entry],
        status={"TMC2": InstrumentStatus.PRESENT},
        diagnostics=ScanDiagnostics(),
    )
    monkeypatch.setattr(catalog_mod, "build_catalog", lambda *a, **k: cat)
    spec = ReferenceSpec("gone", str(tmp_path / "nope.tif"), "raster", "X", True)
    rep = find_overlaps(tmp_path, [spec], instruments=("TMC2",))
    assert [c.status for c in rep.candidates] == [OverlapStatus.REFERENCE_MISSING]
    assert not rep.candidates[0].status.is_failure
    assert rep.counts == {"reference_missing": 1}
    assert "reference_missing: 1" in rep.report() and "data gap" in rep.report()


def test_load_references_lists_every_problem(tmp_path):
    from lunar_reg.cross import load_references

    path = tmp_path / "refs.json"
    path.write_text(json.dumps({
        "schema": 1,
        "references": [
            {"name": "a", "path": "x", "georef": "gdal", "sensor": "S", "independent": True},
            {"name": "a", "path": "y", "georef": "label", "sensor": "S", "independent": "yes"},
        ],
    }))  # fmt: skip
    with pytest.raises(ValueError) as err:
        load_references(path)
    text = str(err.value)
    assert "georef" in text and "independent" in text and "duplicated" in text


# ------------------------------------------------------------------ run_cross.py run, end to end


def _load_run_cross():
    spec = importlib.util.spec_from_file_location("run_cross", REPO / "scripts" / "run_cross.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_cross_registers_a_synthetic_overlap(tmp_path, monkeypatch, capsys):
    import cv2
    import rasterio
    from rasterio.transform import from_origin

    import lunar_reg.sites.runner as runner
    from lunar_reg.ingest import catalog as catalog_mod
    from lunar_reg.ingest.catalog import (
        CatalogEntry,
        InstrumentStatus,
        ProductCatalog,
        ScanDiagnostics,
    )
    from lunar_reg.results import load_index, load_pair

    # reference: correctly georeferenced polar-stereographic GeoTIFF
    pixels = _reference_pixels()
    ref_path = tmp_path / "ref.tif"
    with rasterio.open(ref_path, "w", driver="GTiff", width=REF_N, height=REF_N, count=1,
                       dtype="uint8", crs=NAC_PROJ,
                       transform=from_origin(X0, Y0, PSX, PSX)) as ds:  # fmt: skip
        ds.write(pixels, 1)
    # source: a 2x upsampled crop of the reference, at OHRC 0.25 m, with label corners
    crop = pixels[R0 : R0 + LINES // 2, C0 : C0 + SAMPLES // 2]
    src = cv2.resize(crop, (SAMPLES, LINES), interpolation=cv2.INTER_LINEAR)
    label = _write_source(tmp_path / "src", src)

    pid = f"urn:isro:isda:ch2_cho.ohr:data_calibrated:{STEM.lower()}"
    entry = CatalogEntry(
        instrument="OHRC", product_id=pid, label_path=label, image_path=None,
        level="calibrated", product_type="data", geometry_grid_path=None,
    )  # fmt: skip
    status = {k: InstrumentStatus.ABSENT for k in ("OHRC", "TMC2", "IIRS")}
    status["OHRC"] = InstrumentStatus.PRESENT
    cat = ProductCatalog(entries=[entry], status=status, diagnostics=ScanDiagnostics())
    monkeypatch.setattr(runner, "build_catalog", lambda *a, **k: cat)
    monkeypatch.setattr(catalog_mod, "build_catalog", lambda *a, **k: cat)

    refs = tmp_path / "references.json"
    refs.write_text(json.dumps({"schema": 1, "references": [
        {"name": "synthetic", "path": str(ref_path), "georef": "raster",
         "sensor": "TEST_ORTHO", "independent": False},
    ]}))  # fmt: skip
    overlaps = tmp_path / "cross" / "overlaps.json"
    overlaps.parent.mkdir()
    overlaps.write_text(json.dumps({"schema": 1, "candidates": [{
        "source_product_id": pid, "instrument": "OHRC", "level": "calibrated",
        "reference": "synthetic", "status": "overlap", "n_nodes": 25, "n_inside": 25,
        "centre_line": LINES // 2, "centre_sample": SAMPLES // 2, "centre_lat": None,
        "centre_lon": None, "min_distance_km": None, "overlap_km2": 0.01,
        "overlap_source": "computed", "reference_independent": False,
        "reference_georef_source": "inferred", "detail": "",
    }]}))  # fmt: skip

    root = tmp_path / "results"
    rc = _load_run_cross().main([
        "run", "--overlaps", str(overlaps), "--references", str(refs), "--matchers", "sift",
        "--results-root", str(root), "--out-dir", str(tmp_path / "runs"),
        "--raw-root", str(tmp_path),
    ])  # fmt: skip
    out = capsys.readouterr().out
    assert rc == 0, out

    index = load_index(root)
    assert len(index) == 1, out
    stored = load_pair(index["pair_id"][0], root)
    assert stored.extra["reference_independent"] is False
    assert stored.extra["reference_name"] == "synthetic"
    assert stored.extra["reference_georef_source"] == "inferred"

    record = json.loads((overlaps.parent / "run_record.json").read_text())
    counts = record["outcome_counts"]
    assert counts["registrations_ok"] == 1 and counts["pairs_run"] == 1
    assert counts["instrument_OHRC_present"] == 1
    assert "relative only: reference synthetic is not independent" in record["notes"]
