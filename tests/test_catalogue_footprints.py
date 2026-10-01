"""Catalogue rows carry their real footprint ring as WKT, preferred by footprint_from_row."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from lunar_reg.ingest.overlap import (
    footprint_from_row,
    polygon_area_m2,
    polygon_from_wkt,
    polygon_to_wkt,
)

REPO = Path(__file__).resolve().parents[1]

#: A rotated 5-vertex ring near Vikram's latitude, ``(lat, lon)`` in ring order.
RING = ((-69.2, 32.1), (-69.2, 32.3), (-69.4, 32.35), (-69.45, 32.2), (-69.4, 32.05))


def _load_fetch_catalogue():
    spec = importlib.util.spec_from_file_location(
        "fetch_catalogue", REPO / "scripts" / "fetch_catalogue.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(**extra) -> dict:
    return {
        "product_id": "p",
        "sensor": "OHRC",
        "min_lat": -69.45,
        "max_lat": -69.2,
        "min_lon": 32.05,
        "max_lon": 32.35,
        **{f"corner{i}_{c}": None for i in range(1, 5) for c in ("lat", "lon")},
        **extra,
    }


def test_wkt_round_trip():
    back = polygon_from_wkt(polygon_to_wkt(RING))
    assert back is not None and len(back) == len(RING)
    for (lat, lon), (want_lat, want_lon) in zip(back, RING, strict=True):
        assert lat == pytest.approx(want_lat, abs=1e-9)
        assert lon == pytest.approx(want_lon, abs=1e-9)


def test_ode_spacing_parses_to_four_latlon_vertices():
    ode = "POLYGON ((32.1 -69.2, 32.3 -69.2, 32.3 -69.4, 32.1 -69.4, 32.1 -69.2))"
    ring = polygon_from_wkt(ode)
    assert ring == ((-69.2, 32.1), (-69.2, 32.3), (-69.4, 32.3), (-69.4, 32.1))


@pytest.mark.parametrize(
    "bad",
    [
        "MULTIPOLYGON (((1 2, 3 4, 5 6, 1 2)))",
        "POLYGON((1 2, 3 4))",
        "POLYGON((1 2, 3 4, 1 2))",
        "POLYGON((a b, c d, e f))",
        "POLYGON((1 2 3, 4 5 6, 7 8 9))",
        "POLYGON((nan 1, 2 3, 4 5))",
        "POLYGON EMPTY",
        "",
        None,
    ],
)
def test_unparseable_wkt_is_none(bad):
    assert polygon_from_wkt(bad) is None


def test_row_with_wkt_only_uses_the_polygon():
    footprint = footprint_from_row(_row(footprint_wkt=polygon_to_wkt(RING)))
    assert footprint is not None
    assert footprint.bbox_derived is False
    assert len(footprint.corners) == len(RING)
    for got, want in zip(footprint.corners, RING, strict=True):
        assert got == pytest.approx(want, abs=1e-9)


def test_row_with_multipolygon_falls_back_to_bbox():
    footprint = footprint_from_row(_row(footprint_wkt="MULTIPOLYGON (((1 2, 3 4, 5 6, 1 2)))"))
    assert footprint is not None and footprint.bbox_derived is True


def test_explicit_corners_still_win_over_wkt():
    corners = {
        "corner1_lat": -69.2, "corner1_lon": 32.1,
        "corner2_lat": -69.2, "corner2_lon": 32.3,
        "corner3_lat": -69.4, "corner3_lon": 32.1,
        "corner4_lat": -69.4, "corner4_lon": 32.3,
    }  # fmt: skip
    row = {**_row(footprint_wkt=polygon_to_wkt(RING)), **corners}
    footprint = footprint_from_row(row)
    assert footprint.corners == ((-69.2, 32.1), (-69.2, 32.3), (-69.4, 32.3), (-69.4, 32.1))


def test_issdc_reader_writes_wkt_not_ring_vertices_as_corners(tmp_path):
    fc = _load_fetch_catalogue()
    closed = [[lon, lat] for lat, lon in RING] + [[RING[0][1], RING[0][0]]]
    document = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"PRODUCT_ID": "ch2_ohr_ncp_test"},
                "geometry": {"type": "Polygon", "coordinates": [closed]},
            }
        ],
    }
    path = tmp_path / "catalogue.geojson"
    path.write_text(json.dumps(document))

    rows = list(fc.read_issdc_catalogue(path, "OHRC", fc.Diagnostics()))
    assert len(rows) == 1
    row = rows[0]
    assert all(row[f"corner{i}_{c}"] is None for i in range(1, 5) for c in ("lat", "lon"))
    assert row["footprint_resolved"] is True
    footprint = footprint_from_row(row)
    assert footprint is not None and footprint.bbox_derived is False
    want = polygon_area_m2(RING)
    assert footprint.area_m2() == pytest.approx(want, rel=1e-6)
