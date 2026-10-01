"""Datum convention (Phase_1/LLD/datum.md §1, §3; DECISIONS G13).

The unit tests pin ``lon_to_360`` / ``lon_to_180``. The data test checks the
east-positive longitude assumption on real products: the calibrated OHRC
geometry grid of ``ch2_ohr_ncp_20240425T1406019344_d_img_d18`` must land inside
the Vikram NAC orthoimage, and its east/west mirror must not.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from lunar_reg.constants import (
    DATUM_SOURCE,
    LONGITUDE_DIRECTION,
    LONGITUDE_RANGE,
    MOON_FLATTENING,
    MOON_RADIUS_M,
    lon_to_180,
    lon_to_360,
)
from lunar_reg.provenance import ValueSource

REPO = Path(__file__).resolve().parents[1]
OHRC_ID = "ch2_ohr_ncp_20240425T1406019344_d_img_d18"
OHRC_DIR = REPO / "data/raw/ch2/ohrc" / OHRC_ID
OHRC_LABEL = OHRC_DIR / "data/calibrated/20240425" / f"{OHRC_ID}.xml"
OHRC_GRID = OHRC_DIR / "geometry/calibrated/20240425/ch2_ohr_ncp_20240425T1406019344_g_grd_d18.csv"
NAC_LABEL = REPO / "data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml"
RUN_VIKRAM = REPO / "scripts/run_vikram.py"

#: Sanity bound only (LLD §3.5): the label corners are known to be ~2.9 km off.
MAX_GRID_VS_CORNER_OFFSET_M = 5000.0
MAX_GRID_VS_CORNER_OFFSET_M_SOURCE = ValueSource.INFERRED


# ---------------------------------------------------------------------------
# Unit tests (unmarked)
# ---------------------------------------------------------------------------


def test_datum_constants_carry_inferred_provenance():
    assert MOON_RADIUS_M == 1_737_400.0
    assert MOON_FLATTENING == 0.0
    assert LONGITUDE_DIRECTION == "east"
    assert LONGITUDE_RANGE == "0_360"
    assert DATUM_SOURCE is ValueSource.INFERRED


def test_datum_doc_assumption_table_uses_only_value_source_members():
    """docs/DATUM.md §2: every assumption row names a ValueSource member (LLD datum §2)."""
    text = (REPO / "docs/DATUM.md").read_text()
    section = text.split("## 2.", 1)[1].split("\n## ", 1)[0]
    rows = [
        line
        for line in section.splitlines()
        if line.startswith("|") and not line.startswith("|---") and not line.startswith("| item ")
    ]
    assert len(rows) == 5, rows
    members = {m.name for m in ValueSource}
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        clauses = [c.strip() for c in cells[2].split(";")]
        for clause in clauses:
            head = clause.split()[0]
            assert head in members, (
                f"clause {clause!r} does not start with a ValueSource member: {row}"
            )


def test_lon_to_360_wraps_vectorised_and_keeps_nan():
    out = lon_to_360(np.array([-32.0, 32.0, 360.0, 721.0, -360.0, 359.5, np.nan]))
    np.testing.assert_allclose(out[:-1], [328.0, 32.0, 0.0, 1.0, 0.0, 359.5])
    assert np.isnan(out[-1])
    assert np.all((out[:-1] >= 0.0) & (out[:-1] < 360.0))


def test_lon_to_360_scalar_returns_float():
    out = lon_to_360(-1.0)
    assert isinstance(out, float) and out == 359.0
    assert 0.0 <= lon_to_360(-1e-15) < 360.0  # tiny negatives never come back as 360


def test_lon_to_180_wraps_vectorised_and_keeps_nan():
    out = lon_to_180(np.array([328.0, 32.0, 180.0, -181.0, 540.0, np.nan]))
    np.testing.assert_allclose(out[:-1], [-32.0, 32.0, -180.0, 179.0, -180.0])
    assert np.isnan(out[-1])
    assert isinstance(lon_to_180(190.0), float) and lon_to_180(190.0) == -170.0


def test_round_trip_between_ranges():
    lon = np.linspace(-720.0, 720.0, 97)
    np.testing.assert_allclose(lon_to_360(lon_to_180(lon)), lon_to_360(lon), atol=1e-9)
    np.testing.assert_allclose(lon_to_180(lon_to_360(lon)), lon_to_180(lon), atol=1e-9)


# ---------------------------------------------------------------------------
# Data test (LLD §3)
# ---------------------------------------------------------------------------


def _run_vikram():
    """``scripts/run_vikram.py`` as a module, for its label-corner helpers."""
    spec = importlib.util.spec_from_file_location("_run_vikram_for_datum", RUN_VIKRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.data
def test_east_positive_longitudes_on_real_ohrc_grid_and_nac(capsys):
    for path in (OHRC_LABEL, OHRC_GRID, NAC_LABEL):
        if not path.exists():
            pytest.skip(f"datum data test needs {path.relative_to(REPO)} (absent)")

    from lunar_reg.ingest.geometry_grid import pixel_to_lonlat, read_geometry_grid
    from lunar_reg.ingest.lro import georeference_from_label
    from lunar_reg.ingest.pds4 import read_label

    image = read_label(OHRC_LABEL)
    assert image.lines and image.samples
    grid = read_geometry_grid(OHRC_GRID, lines=image.lines, samples=image.samples)
    nac = georeference_from_label(NAC_LABEL)

    def inside(col, row) -> np.ndarray:
        return (
            np.isfinite(col)
            & np.isfinite(row)
            & (col >= 0)
            & (col < nac.width)
            & (row >= 0)
            & (row < nac.height)
        )

    # 1. The 25 nodes of a 5x5 sub-grid of the geometry grid.
    n_scan, n_pixel = grid.shape
    ii = np.linspace(0, n_scan - 1, 5).round().astype(int)
    jj = np.linspace(0, n_pixel - 1, 5).round().astype(int)
    gi, gj = np.meshgrid(ii, jj, indexing="ij")
    lon = grid.lon[gi, gj].ravel()
    lat = grid.lat[gi, gj].ravel()
    assert np.all(np.isfinite(lon)) and np.all(np.isfinite(lat))

    # 2-3. East-positive reading: every node lands inside the NAC raster.
    col, row = nac.lonlat_to_pixel(lon=lon, lat=lat)
    assert inside(col, row).all(), np.c_[lon, lat, col, row][~inside(col, row)]

    # 4. Mirrored (west-positive) readings land outside.
    for name, mirrored in (("-lon", -lon), ("360-lon", 360.0 - lon)):
        mcol, mrow = nac.lonlat_to_pixel(lon=mirrored, lat=lat)
        assert not inside(mcol, mrow).any(), f"{name} mirror lands inside the NAC raster"

    # 5. Grid prediction vs the label-corner bilinear prior of scripts/run_vikram.py,
    #    at the same 25 image positions and at the strip centre.
    rv = _run_vikram()
    corners = rv.label_corners(image)
    lines_img = grid.scan_lines[gi].ravel().astype(np.float64)
    samples_img = grid.pixels[gj].ravel().astype(np.float64)
    lines_img = np.r_[lines_img, image.lines / 2.0]
    samples_img = np.r_[samples_img, image.samples / 2.0]

    g_lon, g_lat = pixel_to_lonlat(grid, lines_img, samples_img)
    c_latlon = np.array(
        [
            rv.interp_latlon(corners, s / image.samples, ln / image.lines)
            for ln, s in zip(lines_img, samples_img, strict=True)
        ]
    )
    g_col, g_row = nac.lonlat_to_pixel(lon=g_lon, lat=g_lat)
    c_col, c_row = nac.lonlat_to_pixel(lon=c_latlon[:, 1], lat=c_latlon[:, 0])
    dist_m = np.hypot((g_col - c_col) * nac.pixel_size_x_m, (g_row - c_row) * nac.pixel_size_y_m)
    assert np.all(np.isfinite(dist_m))
    median_m = float(np.median(dist_m[:-1]))
    centre_m = float(dist_m[-1])

    with capsys.disabled():
        print(
            f"\nMEASURED grid-vs-corner offset (m): median {median_m:.1f} over the 25 "
            f"sub-grid nodes, strip centre {centre_m:.1f} "
            f"(ValueSource.{ValueSource.MEASURED.name}; {OHRC_ID} vs NAC "
            f"{NAC_LABEL.stem}, NAC georeference source {nac.source.value})"
        )
    assert median_m < MAX_GRID_VS_CORNER_OFFSET_M
    assert centre_m < MAX_GRID_VS_CORNER_OFFSET_M
