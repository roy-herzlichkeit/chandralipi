"""P0.06 — catalogue footprints as polygons (Phase_0/LLD/catalogue_footprints.md). Protected (G05)."""

from __future__ import annotations

import json

import pytest
from _h0 import load_script

RING = ((-69.2, 32.1), (-69.2, 32.3), (-69.4, 32.35), (-69.45, 32.2), (-69.4, 32.05))


def test_wkt_roundtrip():
    from lunar_reg.ingest.overlap import polygon_from_wkt, polygon_to_wkt

    back = polygon_from_wkt(polygon_to_wkt(RING))
    assert len(back) == len(RING)
    for (a, b), (c, d) in zip(back, RING, strict=True):
        assert abs(a - c) < 1e-9 and abs(b - d) < 1e-9


def test_ode_spacing():
    from lunar_reg.ingest.overlap import polygon_from_wkt

    ring = polygon_from_wkt(
        "POLYGON ((32.1 -69.2, 32.3 -69.2, 32.3 -69.4, 32.1 -69.4, 32.1 -69.2))")
    assert ring == ((-69.2, 32.1), (-69.2, 32.3), (-69.4, 32.3), (-69.4, 32.1))


@pytest.mark.parametrize("bad", ["MULTIPOLYGON (((1 2, 3 4, 5 6, 1 2)))", "POLYGON((1 2, 3 4))",
                                 "POLYGON((a b, c d, e f))", ""])
def test_bad_wkt(bad):
    from lunar_reg.ingest.overlap import polygon_from_wkt

    assert polygon_from_wkt(bad) is None


def test_row_with_wkt_only():
    from lunar_reg.ingest.overlap import footprint_from_row, polygon_to_wkt

    row = {"product_id": "x", "sensor": "OHRC", "footprint_wkt": polygon_to_wkt(RING),
           "min_lat": -69.45, "max_lat": -69.2, "min_lon": 32.05, "max_lon": 32.35,
           **{f"corner{i}_{c}": None for i in range(1, 5) for c in ("lat", "lon")}}
    fp = footprint_from_row(row)
    assert fp is not None and fp.bbox_derived is False
    assert len(fp.corners) == 5
    row["footprint_wkt"] = "MULTIPOLYGON (((1 2, 3 4, 5 6, 1 2)))"
    assert footprint_from_row(row).bbox_derived is True


def test_issdc_reader_writes_wkt(tmp_path):
    from lunar_reg.ingest.overlap import footprint_from_row, polygon_area_m2

    fc = load_script("fetch_catalogue")
    ring = [[lon, lat] for lat, lon in RING] + [[RING[0][1], RING[0][0]]]
    doc = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {"PRODUCT_ID": "ch2_ohr_ncp_x"},
        "geometry": {"type": "Polygon", "coordinates": [ring]}}]}
    path = tmp_path / "cat.geojson"
    path.write_text(json.dumps(doc))
    rows = list(fc.read_issdc_catalogue(path, "OHRC", fc.Diagnostics()))
    assert len(rows) == 1
    row = rows[0]
    assert all(row[f"corner{i}_{c}"] is None for i in range(1, 5) for c in ("lat", "lon"))
    fp = footprint_from_row(row)
    assert fp is not None and not fp.bbox_derived
    assert abs(fp.area_m2() - polygon_area_m2(RING)) <= 1e-6 * polygon_area_m2(RING)
    assert not hasattr(fc, "_corner_columns")
