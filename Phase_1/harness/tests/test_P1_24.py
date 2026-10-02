"""P1.24 — cross-instrument pairs at any site (Phase_1/LLD/cross_pairs.md). Protected (G05)."""

from __future__ import annotations

import inspect
import json

import numpy as np
import pytest
from _h1 import REPO

R_M = 1737400.0
EQC = "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
VIKRAM = (-69.37, 32.32)


def _eqc_raster(tmp_path, *, lon=(31.5, 33.0), lat=(-70.0, -68.7), px=100.0, fill=False,
                lbl_offset_px=None, name="ref"):
    """North-up eqc GeoTIFF on the lunar sphere; optional PDS3-style .lbl with bounds."""
    import rasterio
    from rasterio.transform import from_origin

    k = R_M * np.pi / 180.0
    x0, y0 = lon[0] * k, lat[1] * k
    w = int(round((lon[1] - lon[0]) * k / px))
    h = int(round((lat[1] - lat[0]) * k / px))
    data = np.zeros((h, w), np.uint8) if fill else \
        np.random.default_rng(0).integers(20, 250, (h, w)).astype(np.uint8)
    path = tmp_path / f"{name}.tif"
    with rasterio.open(path, "w", driver="GTiff", width=w, height=h, count=1, dtype="uint8",
                       crs=EQC, transform=from_origin(x0, y0, px, px)) as ds:
        ds.write(data, 1)
    if lbl_offset_px is not None:
        d = lbl_offset_px * px / k
        (tmp_path / f"{name}.lbl").write_text(
            f"MAXIMUM_LATITUDE = {lat[1] + d:.6f} <deg>\n"
            f"MINIMUM_LATITUDE = {lat[0] + d:.6f} <deg>\n"
            f"WESTERNMOST_LONGITUDE = {lon[0]:.6f} <deg>\n"
            f"EASTERNMOST_LONGITUDE = {lon[1]:.6f} <deg>\n")
    return path


def _grid(lat, lon):
    from lunar_reg.ingest.geometry_grid import GeometryGrid

    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    return GeometryGrid(scan_lines=np.arange(lat.shape[0]) * 100,
                        pixels=np.arange(lat.shape[1]) * 100, lat=lat, lon=lon)


def _spec(path, independent=True):
    from lunar_reg.cross import ReferenceSpec

    return ReferenceSpec(name="ref", path=str(path), georef="raster", sensor="TEST_ORTHO",
                         independent=independent)


def _overlap(grid, path, **kw):
    from lunar_reg.ingest.lro import georeference_from_raster

    geo = georeference_from_raster(path)
    from lunar_reg.cross import overlap_for_grid, reference_validity  # noqa: E402

    spec = _spec(path)
    return overlap_for_grid("p", "TMC2", "calibrated", grid, spec, geo,
                            reference_validity(spec, geo), nominal_gsd_m=5.0, **kw)


# ------------------------------------------------------------------ C10 raster georef


def test_raster_georef_cross_checked(tmp_path):
    from lunar_reg.ingest.lro import georeference_from_raster
    from lunar_reg.provenance import ValueSource

    good = georeference_from_raster(_eqc_raster(tmp_path, lbl_offset_px=0.0, name="good"))
    assert good.source is ValueSource.DOCUMENTED
    assert good.pixel_size_x_m == pytest.approx(100.0)
    assert good.pixel_size_y_m == pytest.approx(100.0)
    assert good.x0_m == pytest.approx(31.5 * R_M * np.pi / 180)
    bad = georeference_from_raster(_eqc_raster(tmp_path, lbl_offset_px=10.0, name="bad"))
    assert bad.source is ValueSource.INFERRED and bad.note
    bare = georeference_from_raster(_eqc_raster(tmp_path, name="bare"))
    assert bare.source is ValueSource.INFERRED and "not cross-checked" in bare.note


def test_raster_georef_rejects(tmp_path):
    import rasterio
    from rasterio.transform import Affine

    from lunar_reg.ingest.lro import LabelGeoreferenceError, georeference_from_raster

    nocrs = tmp_path / "nocrs.tif"
    with rasterio.open(nocrs, "w", driver="GTiff", width=8, height=8, count=1, dtype="uint8") as ds:
        ds.write(np.ones((8, 8), np.uint8), 1)
    with pytest.raises(LabelGeoreferenceError):
        georeference_from_raster(nocrs)
    rot = tmp_path / "rot.tif"
    with rasterio.open(rot, "w", driver="GTiff", width=8, height=8, count=1, dtype="uint8",
                       crs=EQC, transform=Affine(10, 2, 0, 2, -10, 0)) as ds:
        ds.write(np.ones((8, 8), np.uint8), 1)
    with pytest.raises(LabelGeoreferenceError):
        georeference_from_raster(rot)


# ------------------------------------------------------------------ C11 centre_sample


def test_centre_sample_keyword():
    from lunar_reg.pairs import prepare_window_pair

    p = inspect.signature(prepare_window_pair).parameters["centre_sample"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is None


# ------------------------------------------------------------------ C28 overlaps


def test_overlap_status_members():
    from lunar_reg.cross import OverlapStatus

    assert [s.value for s in OverlapStatus] == ["overlap", "disjoint", "no_grid", "grid_unreadable",
                                                "reference_missing", "reference_unreadable"]
    assert {s.value for s in OverlapStatus if s.is_failure} == {"grid_unreadable",
                                                                 "reference_unreadable"}


def test_pole_crossing_strip_is_disjoint(tmp_path):
    """P1.DL error: a strip over the pole spans > 180 deg of longitude, yet is far from Vikram."""
    from lunar_reg.cross import OverlapStatus

    down = np.linspace(-61.0, -89.6, 40)
    lat = np.r_[down, down[::-1]][:, None] + np.zeros((1, 5))
    lon = np.r_[np.full(40, 77.0), np.full(40, 257.0)][:, None] + np.linspace(-0.4, 0.4, 5)[None]
    assert np.ptp(lon) > 180
    c = _overlap(_grid(lat, lon), _eqc_raster(tmp_path))
    assert c.status is OverlapStatus.DISJOINT and c.n_inside == 0
    assert c.min_distance_km is not None and c.min_distance_km > 300


def test_strip_over_reference_overlaps(tmp_path):
    from lunar_reg.cross import OverlapStatus

    lat = np.linspace(-69.8, -68.9, 30)[:, None] + np.zeros((1, 9))
    lon = np.zeros((30, 1)) + np.linspace(32.0, 32.6, 9)[None]
    c = _overlap(_grid(lat, lon), _eqc_raster(tmp_path))
    assert c.status is OverlapStatus.OVERLAP and c.n_inside >= 4
    assert c.centre_line % 100 == 0 and c.centre_sample % 100 == 0
    assert -70.0 < c.centre_lat < -68.7 and 31.5 < c.centre_lon < 33.0
    assert c.overlap_km2 > 0 and c.overlap_source == "computed" and c.reference_independent is True


def test_all_fill_reference_never_overlaps(tmp_path):
    from lunar_reg.cross import OverlapStatus

    lat = np.linspace(-69.8, -68.9, 30)[:, None] + np.zeros((1, 9))
    lon = np.zeros((30, 1)) + np.linspace(32.0, 32.6, 9)[None]
    assert _overlap(_grid(lat, lon), _eqc_raster(tmp_path, fill=True)).status is \
        OverlapStatus.DISJOINT


def test_references_config():
    from lunar_reg.cross import load_references

    refs = load_references(REPO / "configs/references.json")
    names = [r.name for r in refs]
    assert len(names) == len(set(names)) >= 5
    for r in refs:
        assert r.georef in ("label", "raster")
        if r.sensor == "LRO_NAC_ORTHO":
            assert r.georef == "label", "NAC orthos must never use GDAL's transform (S12)"
    assert any(not r.independent for r in refs), "the TMC-2 ortho is not an independent reference"


def test_overlaps_json_format(tmp_path):
    from lunar_reg.cross import OverlapReport

    lat = np.linspace(-69.8, -68.9, 30)[:, None] + np.zeros((1, 9))
    lon = np.zeros((30, 1)) + np.linspace(32.0, 32.6, 9)[None]
    c = _overlap(_grid(lat, lon), _eqc_raster(tmp_path))
    doc = json.loads(OverlapReport(candidates=[c], counts={"overlap": 1}, samples={}).to_json())
    assert doc["schema"] == 1 and len(doc["candidates"]) == 1
    row = doc["candidates"][0]
    for key in ("source_product_id", "instrument", "level", "reference", "status", "n_nodes",
                "n_inside", "centre_line", "centre_sample", "centre_lat", "centre_lon",
                "min_distance_km", "overlap_km2", "overlap_source", "reference_independent",
                "reference_georef_source", "detail"):
        assert key in row, key


@pytest.mark.data
def test_real_strips_disjoint_from_vikram_nac():
    """Control from Q-P1.18-1: the on-disk TMC-2/IIRS strips are 529-652 km from Vikram."""
    from lunar_reg.cross import OverlapStatus, find_overlaps, load_references

    refs = [r for r in load_references(REPO / "configs/references.json")
            if r.sensor == "LRO_NAC_ORTHO" and (REPO / r.path).exists()]
    if not refs:
        pytest.skip("NAC orthos not on disk")
    rep = find_overlaps(REPO / "data/raw", refs, instruments=("TMC2", "IIRS"))
    real = [c for c in rep.candidates if c.status is not OverlapStatus.NO_GRID]
    if not real:
        pytest.skip("no TMC-2/IIRS product with a geometry grid on disk")
    for c in real:
        assert c.status is OverlapStatus.DISJOINT, (c.source_product_id, c.status)
        assert c.min_distance_km > 400, (c.source_product_id, c.min_distance_km)
