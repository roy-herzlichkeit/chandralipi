"""P1.06 — overlap grid wiring + fixes (Phase_1/LLD/overlap.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from _h1 import write_grid_csv

LINES, SAMPLES = 1001, 301


def _lonlat(line, sample):
    return 32.30 + 2e-5 * sample + 1e-6 * line, -69.30 - 3e-5 * line + 1e-6 * sample


def _fp(**kw):
    from lunar_reg.ingest.overlap import FootprintPolygon

    corners = ((-69.30, 32.30), (-69.30, 32.306), (-69.33, 32.307), (-69.33, 32.301))
    base = dict(corners=corners, product_id="p", sensor="OHRC", lines=LINES, samples=SAMPLES)
    base.update(kw)
    return FootprintPolygon(**base)


def test_members():
    from lunar_reg.ingest.overlap import PriorSource, WindowStatus

    assert {m.value for m in PriorSource} == {"geometry_grid", "label_corners", "bbox"}
    assert {m.value for m in WindowStatus} == {
        "ok", "no_pixel_size", "outside_product", "bbox_has_no_pixel_orientation",
        "grid_unreadable"}


def test_grid_first(tmp_path):
    from lunar_reg.ingest.overlap import PriorSource, WindowStatus, footprint_prior_source, pixel_window

    csv = write_grid_csv(tmp_path / "x_g_grd_d18.csv", LINES, SAMPLES, _lonlat)
    fp = _fp(geometry_grid_path=str(csv))
    assert footprint_prior_source(fp) is PriorSource.GEOMETRY_GRID
    poly = [(-69.305, 32.301), (-69.305, 32.305), (-69.32, 32.305), (-69.32, 32.301)]
    out = pixel_window(fp, poly)
    assert out.status is WindowStatus.OK and out.source is PriorSource.GEOMETRY_GRID
    assert out.window is not None
    bad = tmp_path / "bad_g_grd_d18.csv"
    bad.write_text("garbage\n")
    out = pixel_window(_fp(geometry_grid_path=str(bad)), poly)
    assert out.status is WindowStatus.GRID_UNREADABLE and out.window is None


def test_bbox_has_no_orientation():
    from lunar_reg.ingest.overlap import WindowStatus, pixel_window, polygon_to_pixel_window

    fp = _fp(bbox_derived=True)
    out = pixel_window(fp, fp.corners)
    assert out.status is WindowStatus.BBOX_HAS_NO_PIXEL_ORIENTATION
    assert polygon_to_pixel_window(fp, fp.corners) is None


def test_row_carries_grid_path(tmp_path):
    from lunar_reg.ingest.overlap import footprint_from_row

    row = {"product_id": "p", "sensor": "OHRC", "lines": LINES, "samples": SAMPLES,
           "geometry_grid_path": "/x/y_g_grd_d18.csv"}
    ring = _fp().corners  # UL, UR, LR, LL -> corner1..4 = UL, UR, LL, LR
    for i, (lat, lon) in enumerate((ring[0], ring[1], ring[3], ring[2]), 1):
        row[f"corner{i}_lat"], row[f"corner{i}_lon"] = lat, lon
    assert footprint_from_row(row).geometry_grid_path == "/x/y_g_grd_d18.csv"


def _box(a0, a1, b0, b1):
    return ((a0, b0), (a0, b1), (a1, b1), (a1, b0))


def test_touching_both_axes():
    from lunar_reg.ingest import overlap

    a = _box(0.0, 1.0, 0.0, 1.0)
    assert overlap._touching(a, _box(1.0, 2.0, 5.0, 6.0)) is False   # shared lat edge, far in lon
    assert overlap._touching(a, _box(1.0, 2.0, 0.5, 1.5)) is True


def test_same_sensor_no_self_pairs():
    from lunar_reg.ingest.overlap import find_overlapping_pairs

    rows = []
    for k in range(3):
        c = [(-69.30, 32.30 + 1e-4 * k), (-69.30, 32.31), (-69.33, 32.31), (-69.33, 32.30 + 1e-4 * k)]
        row = {"product_id": f"p{k}", "sensor": "OHRC", "lines": 10, "samples": 10}
        for i, (lat, lon) in enumerate([c[0], c[1], c[3], c[2]], 1):
            row[f"corner{i}_lat"], row[f"corner{i}_lon"] = lat, lon
        rows.append(row)
    frame, diag = find_overlapping_pairs(pd.DataFrame(rows), "OHRC", "OHRC")
    assert diag.n_pairs_considered == 3
    if len(frame):
        assert not (frame["source_id"] == frame["reference_id"]).any()


def test_missing_footprint_counted_per_product():
    from lunar_reg.ingest.overlap import find_overlapping_pairs

    rows = [{"product_id": "a", "sensor": "OHRC"}, {"product_id": "b", "sensor": "OHRC"},
            {"product_id": "c", "sensor": "TMC2"}]
    _, diag = find_overlapping_pairs(pd.DataFrame(rows), "OHRC", "TMC2")
    assert diag.counts.get("missing_footprint") == 3


def test_crop_georef_and_bands(tmp_path):
    import rasterio
    from rasterio.transform import from_origin

    from lunar_reg.ingest.overlap import FootprintPolygon, OverlapResult, OverlapStatus, crop_to_overlap

    path = tmp_path / "parent.tif"
    data = np.arange(3 * 200 * 100, dtype=np.uint16).reshape(3, 200, 100)
    transform = from_origin(1000.0, 5000.0, 2.0, 2.0)
    with rasterio.open(path, "w", driver="GTiff", width=100, height=200, count=3, dtype="uint16",
                       crs="+proj=eqc +R=1737400 +units=m +no_defs", transform=transform) as ds:
        ds.write(data)
    corners = ((-1.0, 1.0), (-1.0, 2.0), (-2.0, 2.0), (-2.0, 1.0))
    fp = FootprintPolygon(corners=corners, product_id="p", image_path=str(path),
                          label_path=str(path), lines=200, samples=100)
    poly = ((-1.2, 1.2), (-1.2, 1.5), (-1.6, 1.5), (-1.6, 1.2))
    result = OverlapResult(fp, fp, OverlapStatus.OK, poly, 1.0, "")
    summary = crop_to_overlap(result, tmp_path / "out")
    side = summary["sides"]["source"]
    assert "output" in side, side
    with rasterio.open(side["output"]) as crop:
        assert crop.count == 3
        x, y = crop.transform * (0, 0)
        px, py = transform * (side["col_off"], side["row_off"])
        assert (x, y) == pytest.approx((px, py))
    assert side["window_status"] == "ok" and side["prior_source"] == "label_corners"


def test_pseudo_gt_polar_plane():
    from lunar_reg.ingest.overlap import FootprintPolygon, to_fit_plane

    polar = FootprintPolygon(corners=((-85.0, 10.0), (-85.0, 12.0), (-86.0, 12.0), (-86.0, 10.0)),
                             lines=100, samples=100)
    ring = tuple(tuple(p) for p in to_fit_plane(polar, polar.corners))
    assert ring != tuple(polar.corners)
    equatorial = _fp()
    same = tuple(tuple(p) for p in to_fit_plane(equatorial, equatorial.corners))
    assert same == tuple(equatorial.corners)
