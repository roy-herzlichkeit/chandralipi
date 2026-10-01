"""P1.06 regressions: geometry-grid wiring and the audited overlap defects.

One test (or a small group) per row of Phase_1/LLD/overlap.md §3, plus the
grid-first / classified-window behaviour of §1-§2 (A053).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from lunar_reg.constants import MOON_RADIUS_M
from lunar_reg.ingest import overlap
from lunar_reg.ingest.overlap import (
    FootprintPolygon,
    OverlapResult,
    OverlapStatus,
    PriorSource,
    WindowStatus,
    crop_to_overlap,
    find_overlapping_pairs,
    footprint_from_row,
    footprint_prior_source,
    geographic_to_pixel_transform,
    intersect,
    pixel_window,
    polygon_to_pixel_window,
    to_fit_plane,
)

LINES, SAMPLES = 1001, 301


def box(lat0, lat1, lon0, lon1, pid="p", sensor="OHRC", lines=1000, samples=800, **kw):
    """Footprint in UL, UR, LR, LL ring order."""
    return FootprintPolygon(
        corners=((lat1, lon0), (lat1, lon1), (lat0, lon1), (lat0, lon0)),
        product_id=pid,
        sensor=sensor,
        lines=lines,
        samples=samples,
        **kw,
    )


def analytic_area(lat0, lat1, lon0, lon1):
    return (
        MOON_RADIUS_M**2
        * math.radians(lon1 - lon0)
        * (math.sin(math.radians(lat1)) - math.sin(math.radians(lat0)))
    )


def _lonlat(line, sample):
    """Smooth synthetic ground map, (lon, lat) for an image (line, sample)."""
    return 32.30 + 2e-5 * sample + 1e-6 * line, -69.30 - 3e-5 * line + 1e-6 * sample


def write_grid_csv(path, lines=LINES, samples=SAMPLES, step=100):
    """Geometry grid in the layout of tests/test_geometry_grid.py::write_product:
    ``Longitude,Latitude,Pixel,Scan`` header, 0-based Scan x Pixel nodes every
    ``step`` with a final short step onto the last index. No label, so the
    CSV header supplies the field order."""
    scans = [*range(0, lines - 1, step), lines - 1]
    pixels = [*range(0, samples - 1, step), samples - 1]
    rows = ["Longitude,Latitude,Pixel,Scan"]
    for s in scans:
        for p in pixels:
            lon, lat = _lonlat(s, p)
            rows.append(f"{lon:.9f},{lat:.9f},{p},{s}")
    path.write_text("\n".join(rows) + "\n")
    return path


def _grid_fp(**kw):
    ul, ur = _lonlat(0, 0), _lonlat(0, SAMPLES - 1)
    lr, ll = _lonlat(LINES - 1, SAMPLES - 1), _lonlat(LINES - 1, 0)
    corners = tuple((lat, lon) for lon, lat in (ul, ur, lr, ll))
    base = dict(corners=corners, product_id="g", sensor="OHRC", lines=LINES, samples=SAMPLES)
    base.update(kw)
    return FootprintPolygon(**base)


INNER = ((-69.305, 32.301), (-69.305, 32.305), (-69.32, 32.305), (-69.32, 32.301))


# --- §1-§2: types and grid-first mapping ------------------------------------


def test_prior_source_members_are_the_contract():
    assert [m.value for m in PriorSource] == ["geometry_grid", "label_corners", "bbox"]
    assert not WindowStatus.OK.is_failure
    assert all(m.is_failure for m in WindowStatus if m is not WindowStatus.OK)


def test_grid_is_preferred_when_present(tmp_path):
    csv = write_grid_csv(tmp_path / "x_g_grd_d18.csv")
    fp = _grid_fp(geometry_grid_path=str(csv))
    assert footprint_prior_source(fp) is PriorSource.GEOMETRY_GRID
    out = pixel_window(fp, INNER)
    assert out.status is WindowStatus.OK and out.source is PriorSource.GEOMETRY_GRID
    row_off, col_off, height, width = out.window
    assert row_off >= 0 and row_off + height <= LINES
    assert col_off >= 0 and col_off + width <= SAMPLES
    assert polygon_to_pixel_window(fp, INNER) == out.window


def test_unreadable_grid_is_reported_not_replaced_by_corners(tmp_path):
    bad = tmp_path / "bad_g_grd_d18.csv"
    bad.write_text("garbage\n")
    fp = _grid_fp(geometry_grid_path=str(bad))
    out = pixel_window(fp, INNER)
    assert out.status is WindowStatus.GRID_UNREADABLE
    assert out.window is None and out.source is PriorSource.GEOMETRY_GRID
    assert "bad_g_grd_d18.csv" in out.detail
    # The same footprint without the grid has a perfectly good corner window,
    # so a silent fallback would have produced one.
    assert pixel_window(_grid_fp(), INNER).status is WindowStatus.OK


def test_missing_grid_file_falls_back_to_corners_and_says_so(tmp_path):
    fp = _grid_fp(geometry_grid_path=str(tmp_path / "absent_g_grd_d18.csv"))
    assert footprint_prior_source(fp) is PriorSource.LABEL_CORNERS
    out = pixel_window(fp, INNER)
    assert out.status is WindowStatus.OK and out.source is PriorSource.LABEL_CORNERS
    assert "does not exist" in out.detail


def test_footprint_from_row_copies_the_grid_path():
    row = {
        "product_id": "p",
        "sensor": "OHRC",
        "min_lat": 0,
        "max_lat": 1,
        "min_lon": 0,
        "max_lon": 1,
        "geometry_grid_path": "/a/b_g_grd_d18.csv",
    }
    assert footprint_from_row(row).geometry_grid_path == "/a/b_g_grd_d18.csv"
    row["geometry_grid_path"] = float("nan")  # pandas fill for an absent value
    assert footprint_from_row(row).geometry_grid_path is None
    del row["geometry_grid_path"]
    assert footprint_from_row(row).geometry_grid_path is None


def test_no_pixel_size_and_outside_are_distinct_statuses():
    fp = box(0, 10, 0, 10, lines=None, samples=None)
    assert pixel_window(fp, fp.corners).status is WindowStatus.NO_PIXEL_SIZE
    far = ((50.0, 50.0), (50.0, 60.0), (60.0, 60.0), (60.0, 50.0))
    out = pixel_window(box(0, 10, 0, 10, lines=100, samples=100), far)
    assert out.status is WindowStatus.OUTSIDE_PRODUCT and out.window is None


# --- A047: longitude conventions -------------------------------------------


def test_a047_mixed_longitude_conventions_still_overlap():
    east = box(0, 10, 350, 356, "east360")  # 0..360 convention
    west = box(0, 10, -8, -2, "west180")  # -180..180 convention, same ground
    r = intersect(east, west)
    assert r.status is OverlapStatus.OK, r.detail
    assert r.area_m2 == pytest.approx(analytic_area(0, 10, 352, 356), rel=0.02)
    assert intersect(west, east).area_m2 == pytest.approx(r.area_m2, rel=1e-6)


@pytest.mark.parametrize(
    ("source", "reference"),
    [
        # Both -180..180; the reference strip straddles the source's antipodal meridian.
        (box(10, 11, 177.9, 178.1, "ohrc"), box(0, 20, -3.0, -1.0, "tmc")),
        # 0..360 reference straddling lon 180, source near lon 0.
        (box(0, 1, 0, 5, "src"), box(0, 1, 170, 190, "ref")),
    ],
)
def test_a047_antipodal_pair_is_disjoint_in_both_orders(source, reference):
    assert intersect(source, reference).status is OverlapStatus.DISJOINT
    assert intersect(reference, source).status is OverlapStatus.DISJOINT


def test_a047_antipodal_pair_is_not_reported_as_overlap():
    rows = []
    for fp in (box(10, 11, 177.9, 178.1, "ohrc", "OHRC"), box(0, 20, -3.0, -1.0, "tmc", "TMC2")):
        r = {"product_id": fp.product_id, "sensor": fp.sensor, "lines": 100, "samples": 100}
        for i, (la, lo) in enumerate(fp.corners, 1):
            r[f"corner{i}_lat"], r[f"corner{i}_lon"] = la, lo
        rows.append(r)
    found, diag = find_overlapping_pairs(pd.DataFrame(rows), "OHRC", "TMC2")
    assert len(found) == 0
    assert diag.counts.get("ok", 0) == 0


def test_a047_mixed_conventions_next_to_lon_180_overlap():
    # Same ground written in both conventions just east of lon 180.
    source = box(0, 1, -179.5, -178.5, "src")
    reference = box(0, 1, 180.0, 181.0, "ref")
    r = intersect(source, reference)
    assert r.status is OverlapStatus.OK, r.detail
    assert r.area_m2 == pytest.approx(analytic_area(0, 1, 180.5, 181.0), rel=0.02)
    assert intersect(reference, source).area_m2 == pytest.approx(r.area_m2, rel=1e-6)


def test_a047_rewrap_moves_the_ring_as_a_whole():
    # A ring straddling ref + 180 stays one contiguous 20-degree quad.
    ring = overlap._rewrap_ring(((1, 170.0), (1, 190.0), (0, 190.0), (0, 170.0)), 0.0)
    lons = [lon for _, lon in ring]
    assert max(lons) - min(lons) == pytest.approx(20.0)
    assert -180.0 < sum(lons) / len(lons) <= 180.0


# --- A048: touching needs both axes ------------------------------------------


def _ring(a0, a1, b0, b1):
    return ((a0, b0), (a0, b1), (a1, b1), (a1, b0))


def test_a048_shared_edge_far_apart_is_not_touching():
    a = _ring(0.0, 1.0, 0.0, 1.0)
    assert overlap._touching(a, _ring(1.0, 2.0, 5.0, 6.0)) is False
    assert overlap._touching(a, _ring(1.0, 2.0, 0.5, 1.5)) is True
    assert overlap._touching(a, _ring(1.0, 2.0, 1.0, 2.0)) is True  # corner


def test_a048_intersect_reports_far_shared_parallel_as_disjoint():
    r = intersect(box(0, 1, 0, 1, "a"), box(1, 2, 5, 6, "b"))
    assert r.status is OverlapStatus.DISJOINT


# --- A049: a bounding box has no pixel orientation ---------------------------


def test_a049_bbox_footprint_gets_no_window():
    fp = footprint_from_row(
        {
            "product_id": "b",
            "sensor": "OHRC",
            "min_lat": 0,
            "max_lat": 1,
            "min_lon": 0,
            "max_lon": 1,
            "lines": 100,
            "samples": 100,
        }
    )
    assert fp.bbox_derived
    assert footprint_prior_source(fp) is PriorSource.BBOX
    out = pixel_window(fp, fp.corners)
    assert out.status is WindowStatus.BBOX_HAS_NO_PIXEL_ORIENTATION and out.window is None
    assert polygon_to_pixel_window(fp, fp.corners) is None


# --- A050: same-sensor scans -------------------------------------------------


def _row(pid, lat0, lat1, lon0, lon1, sensor="OHRC"):
    c = ((lat1, lon0), (lat1, lon1), (lat0, lon0), (lat0, lon1))  # corner1..4 = UL, UR, LL, LR
    row = {"product_id": pid, "sensor": sensor, "lines": 10, "samples": 10}
    for i, (lat, lon) in enumerate(c, 1):
        row[f"corner{i}_lat"], row[f"corner{i}_lon"] = lat, lon
    return row


def test_a050_same_sensor_scans_each_unordered_pair_once():
    rows = [_row(f"p{k}", 0, 1, 0.1 * k, 1 + 0.1 * k) for k in range(3)]
    frame, diag = find_overlapping_pairs(pd.DataFrame(rows), "OHRC", "OHRC")
    assert diag.n_pairs_considered == 3
    assert len(frame) == 3
    assert not (frame["source_id"] == frame["reference_id"]).any()
    pairs = {frozenset(p) for p in zip(frame["source_id"], frame["reference_id"], strict=True)}
    assert len(pairs) == 3


def test_a050_duplicate_product_rows_are_counted_not_paired():
    rows = [_row("p0", 0, 1, 0, 1), _row("p0", 0, 1, 0, 1), _row("p1", 0, 1, 0.5, 1.5)]
    frame, diag = find_overlapping_pairs(pd.DataFrame(rows), "OHRC", "OHRC")
    assert diag.n_self_pairs_skipped == 1
    assert diag.n_pairs_considered == 2
    assert "share a product_id" in diag.report()


# --- A105: one missing-footprint count per product ---------------------------


def test_a105_missing_footprint_counted_per_product_with_role_sample():
    rows = [
        {"product_id": "a", "sensor": "OHRC"},
        {"product_id": "b", "sensor": "OHRC"},
        {"product_id": "c", "sensor": "TMC2"},
    ]
    _, diag = find_overlapping_pairs(pd.DataFrame(rows), "OHRC", "TMC2")
    assert diag.counts["missing_footprint"] == 3
    assert diag.samples["missing_footprint"] == "source a"
    assert (diag.n_source_without_footprint, diag.n_reference_without_footprint) == (2, 1)


def test_a105_same_sensor_missing_is_not_double_counted():
    rows = [{"product_id": "a", "sensor": "OHRC"}, _row("p", 0, 1, 0, 1)]
    _, diag = find_overlapping_pairs(pd.DataFrame(rows), "OHRC", "OHRC")
    assert diag.counts["missing_footprint"] == 1


# --- A106: snap before floor on the corner path ------------------------------


def test_a106_corner_window_snaps_float32_round_off():
    # Corners found by search: the float32 homography maps the far corners to
    # 798.99992 / 998.99930, so a bare floor would lose a column and a row.
    corners = (
        (-28.114171031318076, 3.8334052653268884),
        (-28.09785465264755, 4.649224198853213),
        (-28.919989964844397, 4.657382388188476),
        (-28.9299899648444, 3.8364052653268885),
    )
    fp = FootprintPolygon(corners=corners, lines=1000, samples=800)
    matrix = geographic_to_pixel_transform(fp)
    pts = np.array([[lon, lat, 1.0] for lat, lon in corners]) @ matrix.T
    raw = pts[:, :2] / pts[:, 2:3]
    assert raw[:, 0].max() < 799 or raw[:, 1].max() < 999, "fixture lost its round-off"
    assert polygon_to_pixel_window(fp, corners) == (0, 0, 1000, 800)


# --- A046 / A052: crop georeference and bands ---------------------------------


def _geotiff(path, count=3, nodata=None):
    import rasterio
    from rasterio.transform import from_origin

    data = np.arange(count * 200 * 100, dtype=np.uint16).reshape(count, 200, 100)
    transform = from_origin(1000.0, 5000.0, 2.0, 2.0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=100,
        height=200,
        count=count,
        dtype="uint16",
        crs="+proj=eqc +R=1737400 +units=m +no_defs",
        transform=transform,
        nodata=nodata,
    ) as ds:
        ds.write(data)
    return transform, data


def _crop_pair(tmp_path, path):
    fp = FootprintPolygon(
        corners=((-1.0, 1.0), (-1.0, 2.0), (-2.0, 2.0), (-2.0, 1.0)),
        product_id="p",
        image_path=str(path),
        label_path=str(path),
        lines=200,
        samples=100,
    )
    poly = ((-1.2, 1.2), (-1.2, 1.5), (-1.6, 1.5), (-1.6, 1.2))
    return crop_to_overlap(OverlapResult(fp, fp, OverlapStatus.OK, poly, 1.0, ""), tmp_path / "out")


def test_a046_a052_crop_keeps_georeference_and_every_band(tmp_path):
    import rasterio

    path = tmp_path / "parent.tif"
    transform, data = _geotiff(path, nodata=0)
    side = _crop_pair(tmp_path, path)["sides"]["source"]
    assert "output" in side, side
    assert side["window_status"] == "ok" and side["prior_source"] == "label_corners"
    r, c, h, w = side["row_off"], side["col_off"], side["height"], side["width"]
    with rasterio.open(side["output"]) as crop:
        assert crop.count == 3
        assert crop.transform.c == pytest.approx(transform.c + c * transform.a)
        assert crop.transform.f == pytest.approx(transform.f + r * transform.e)
        assert crop.crs is not None
        assert crop.nodata == 0
        np.testing.assert_array_equal(crop.read(), data[:, r : r + h, c : c + w])


def test_a046_crop_without_parent_nodata_writes_none(tmp_path):
    import rasterio

    path = tmp_path / "parent.tif"
    _geotiff(path, count=1, nodata=None)
    side = _crop_pair(tmp_path, path)["sides"]["source"]
    with rasterio.open(side["output"]) as crop:
        assert crop.nodata is None and crop.count == 1


def test_crop_records_window_status_for_failed_side(tmp_path):
    bboxed = FootprintPolygon(
        corners=box(0, 10, 0, 10).corners, product_id="b", lines=10, samples=10, bbox_derived=True
    )
    other = box(5, 15, 5, 15, "o", lines=None, samples=None)
    summary = crop_to_overlap(intersect(bboxed, other), tmp_path)
    src, ref = summary["sides"]["source"], summary["sides"]["reference"]
    assert src["window_status"] == "bbox_has_no_pixel_orientation"
    assert src["prior_source"] == "bbox" and "error" in src
    assert ref["window_status"] == "no_pixel_size" and "error" in ref


# --- A051: pseudo-GT projection in the fit plane -----------------------------


def test_a051_polar_points_project_in_the_fit_plane():
    from lunar_reg.ingest.pseudo_gt import project_to_pixels

    polar = FootprintPolygon(
        corners=((-85.0, 10.0), (-85.0, 12.0), (-86.0, 12.0), (-86.0, 10.0)), lines=100, samples=80
    )
    pixels = project_to_pixels(polar, list(polar.corners))
    np.testing.assert_allclose(pixels, [[0, 0], [79, 0], [79, 99], [0, 99]], atol=1e-2)


def test_a051_to_fit_plane_is_identity_away_from_the_pole():
    fp = box(0, 10, 0, 10)
    assert to_fit_plane(fp, fp.corners) == tuple(fp.corners)
    polar = box(-86, -85, 10, 12)
    assert to_fit_plane(polar, polar.corners) != tuple(polar.corners)
