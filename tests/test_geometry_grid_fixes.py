"""P1.05 geometry-grid fixes (Phase_1/LLD/geometry_grid.md §1-§4, tests per §6).

Synthetic grids are built directly as :class:`GeometryGrid` objects with a
smooth analytic lat/lon field, sampled the way the real products are (every 100
lines/samples plus a short final step onto the last index). The antimeridian
grid goes through :func:`read_geometry_grid` instead, because the longitude
rewrap under test happens at load time; its CSV uses the
``Longitude,Latitude,Pixel,Scan`` layout of ``tests/test_geometry_grid.py``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest

from lunar_reg.ingest import geometry_grid as gg
from lunar_reg.ingest.geometry_grid import (
    GeometryGrid,
    find_geometry_files,
    lonlat_to_pixel,
    pixel_to_lonlat,
    polygon_to_pixel_window,
    read_geometry_grid,
    snap_to_integer,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OHRC_ROOT = DATA_DIR / "raw" / "ch2" / "ohrc"


def sampled_axis(n_elements: int, step: int = 100) -> np.ndarray:
    values = list(range(0, n_elements, step))
    if values[-1] != n_elements - 1:
        values.append(n_elements - 1)
    return np.asarray(values, dtype=np.int64)


def make_grid(lonlat, lines: int, samples: int, step: int = 100) -> GeometryGrid:
    """A ``GeometryGrid`` from ``lonlat(line, sample) -> (lon, lat)``."""
    scans = sampled_axis(lines, step)
    pixels = sampled_axis(samples, step)
    line, sample = np.meshgrid(scans.astype(float), pixels.astype(float), indexing="ij")
    lon, lat = lonlat(line, sample)
    return GeometryGrid(
        scan_lines=scans,
        pixels=pixels,
        lat=np.asarray(lat, dtype=np.float64),
        lon=np.asarray(lon, dtype=np.float64),
        lines=lines,
        samples=samples,
    )


def write_grid_csv(path: Path, lonlat, lines: int, samples: int, step: int = 100) -> Path:
    rows = ["Longitude,Latitude,Pixel,Scan"]
    for scan in sampled_axis(lines, step):
        for pixel in sampled_axis(samples, step):
            lon, lat = lonlat(float(scan), float(pixel))
            rows.append(f"{lon:.9f},{lat:.9f},{pixel},{scan}")
    path.write_text("\n".join(rows) + "\n")
    return path


# A coarse, slightly sheared field: lon 10..11, lat 0..1 over 1001 x 1001 pixels.
LINES, SAMPLES = 1001, 1001


def coarse(line, sample):
    lon = 10.0 + 1e-3 * sample + 1e-5 * line
    lat = 1.0 - 1e-3 * line + 1e-5 * sample
    return lon, lat


# ---------------------------------------------------------------------------
# §1 public snap helper
# ---------------------------------------------------------------------------


def test_snap_to_integer_is_public_and_aliased():
    assert snap_to_integer(11999.9999999) == 12000.0
    assert snap_to_integer(3.4) == 3.4
    assert snap_to_integer(3.4, tolerance=0.5) == 3.0
    assert gg._snap is snap_to_integer
    assert "snap_to_integer" in gg.__all__


# ---------------------------------------------------------------------------
# §4 polygon windows
# ---------------------------------------------------------------------------


def test_polygon_with_no_boundary_sample_inside_still_gets_its_interior_nodes():
    """A band crossing the grid whose vertices (densify=1) all lie off the grid."""
    grid = make_grid(coarse, LINES, SAMPLES)
    ring = [(0.62, 5.0), (0.62, 16.0), (0.33, 16.0), (0.33, 5.0)]

    # Precondition: the boundary path alone finds nothing.
    lats = np.array([lat for lat, _ in ring])
    lons = np.array([lon for _, lon in ring])
    assert not lonlat_to_pixel(grid, lats, lons).inside.any()

    win = polygon_to_pixel_window(grid, ring, densify=1)
    assert win is not None
    row0, col0, height, width = win

    inside_nodes = (grid.lat > 0.33) & (grid.lat < 0.62)
    assert inside_nodes.any()
    ii, jj = np.nonzero(inside_nodes)
    for i, j in zip(ii, jj, strict=True):
        assert row0 <= grid.scan_lines[i] < row0 + height
        assert col0 <= grid.pixels[j] < col0 + width
    # It is a band, not the whole product.
    assert height < LINES


def test_small_polygon_strictly_inside_one_grid_cell():
    grid = make_grid(coarse, LINES, SAMPLES)
    # Pixel square 420..460 x 520..560 lies inside the cell (400..500, 500..600).
    corners = [(420.0, 520.0), (420.0, 560.0), (460.0, 560.0), (460.0, 520.0)]
    ring = []
    for line, sample in corners:
        lon, lat = pixel_to_lonlat(grid, line, sample)
        ring.append((float(lat), float(lon)))
    win = polygon_to_pixel_window(grid, ring)
    assert win is not None
    row0, col0, height, width = win
    assert row0 <= 420 and row0 + height >= 460
    assert col0 <= 520 and col0 + width >= 560
    # And it is tight: no grid node is inside, so only the boundary contributes.
    assert height < 100 and width < 100


def test_polygon_larger_than_the_product_gives_the_full_product():
    grid = make_grid(coarse, LINES, SAMPLES)
    big = [(3.0, 8.0), (3.0, 13.0), (-2.0, 13.0), (-2.0, 8.0)]
    assert polygon_to_pixel_window(grid, big) == (0, 0, LINES, SAMPLES)


def test_polar_polygon_around_the_pole_covers_a_near_pole_product():
    """In lat/lon a ring at -80 deg cannot contain a point at -88; on the plane it does."""

    def near_pole(line, sample):
        return 20.0 + 0.01 * sample, -88.0 - 0.001 * line

    grid = make_grid(near_pole, 501, 401)
    ring = [(-80.0, 0.0), (-80.0, 90.0), (-80.0, 180.0), (-80.0, -90.0)]
    assert polygon_to_pixel_window(grid, ring) == (0, 0, 501, 401)


def test_disjoint_polygon_still_returns_none():
    grid = make_grid(coarse, LINES, SAMPLES)
    assert polygon_to_pixel_window(grid, [(40, 40), (40, 41), (41, 41), (41, 40)]) is None


# ---------------------------------------------------------------------------
# §3 longitude rewrap
# ---------------------------------------------------------------------------

SEAM_LINES, SEAM_SAMPLES = 501, 1001


def seam(line, sample):
    """lon 179.5 .. 180.5, written in the -180..180 convention (so 179.5 .. -179.5)."""
    lon = 179.5 + 1e-3 * sample
    return (lon - 360.0 if lon > 180.0 else lon), 10.0 - 1e-3 * line


def test_antimeridian_grid_is_rewrapped_and_queries_follow(tmp_path):
    path = write_grid_csv(tmp_path / "seam_g_grd_d18.csv", seam, SEAM_LINES, SEAM_SAMPLES)
    grid = read_geometry_grid(path, lines=SEAM_LINES, samples=SEAM_SAMPLES)

    assert grid.longitude_reference_deg is not None
    assert grid.longitude_unwrapped
    assert any("unwrapped" in note for note in grid.diagnostics.notes)
    # Continuous after the rewrap.
    assert np.nanmax(grid.lon) - np.nanmin(grid.lon) < 2.0

    look = lonlat_to_pixel(grid, np.array([9.9, 9.9]), np.array([-179.9, 179.9]))
    assert look.inside.all()
    assert look.sample[0] == pytest.approx(600.0, abs=1e-3)
    assert look.sample[1] == pytest.approx(400.0, abs=1e-3)
    assert look.line[0] == pytest.approx(100.0, abs=1e-3)

    # A window across the seam spans both sides of it.
    ring = [(9.95, 179.8), (9.95, -179.8), (9.85, -179.8), (9.85, 179.8)]
    row0, col0, height, width = polygon_to_pixel_window(grid, ring)
    assert col0 <= 300 and col0 + width >= 700
    assert row0 <= 50 and row0 + height >= 150


def test_non_wrapping_grid_is_left_untouched(tmp_path):
    path = write_grid_csv(tmp_path / "plain_g_grd_d18.csv", coarse, LINES, SAMPLES)
    grid = read_geometry_grid(path, lines=LINES, samples=SAMPLES)
    assert grid.longitude_reference_deg is None
    assert not grid.longitude_unwrapped
    assert not any("unwrapped" in note for note in grid.diagnostics.notes)


def test_rewrap_helper_returns_false_without_a_change():
    lon = np.array([[350.0, 351.0], [352.0, np.nan]])
    before = lon.copy()
    diag = gg.GeometryGridDiagnostics()
    assert gg._maybe_unwrap_longitude(lon, diag) is False
    np.testing.assert_array_equal(lon, before)
    assert diag.notes == []

    wrapped = np.array([[359.5, 0.5], [359.6, 0.6]])
    assert gg._maybe_unwrap_longitude(wrapped, diag) is True
    np.testing.assert_allclose(wrapped, [[359.5, 360.5], [359.6, 360.6]])
    assert len(diag.notes) == 1


# ---------------------------------------------------------------------------
# §2 find_geometry_files
# ---------------------------------------------------------------------------


def test_find_geometry_files_matches_n18_and_d18_and_filters_by_timestamp(tmp_path, caplog):
    n18 = tmp_path / "a" / "ch2_ohr_ncp_20230823T1450475804_g_grd_n18.csv"
    d18 = tmp_path / "b" / "ch2_ohr_ncp_20240425T1406019344_g_grd_d18.csv"
    for path in (n18, d18):
        path.parent.mkdir(parents=True)
        path.write_text("x")
    (d18.with_suffix(".xml")).write_text("<x/>")

    found = find_geometry_files(tmp_path)
    assert found == [(n18, None), (d18, d18.with_suffix(".xml"))]

    # The image id's level/version tokens differ from the grid's; only the
    # timestamp token is shared.
    hits = find_geometry_files(tmp_path, "ch2_ohr_nrp_20230823T1450475804_d_img_n18")
    assert hits == [(n18, None)]
    assert find_geometry_files(tmp_path, "ch2_ohr_ncp_20240425T1406019344_d_img_d18") == [
        (d18, d18.with_suffix(".xml"))
    ]

    with caplog.at_level(logging.WARNING, logger="lunar_reg.ingest.geometry_grid"):
        assert find_geometry_files(tmp_path, "no_token_here") == []
    assert sum("timestamp token" in r.getMessage() for r in caplog.records) == 1


# ---------------------------------------------------------------------------
# Real calibrated OHRC grids (P1.DL)
# ---------------------------------------------------------------------------


def real_ncp_grids():
    if not OHRC_ROOT.exists():
        return []
    return [csv for csv, _ in find_geometry_files(OHRC_ROOT) if "_ncp_" in csv.name]


@pytest.mark.data
@pytest.mark.parametrize("csv_path", real_ncp_grids() or [None])
def test_real_ncp_grid_covers_the_image_and_round_trips(csv_path):
    if csv_path is None:
        pytest.skip(f"no *_ncp_*_g_grd_*.csv geometry grid under {OHRC_ROOT}")
    from lunar_reg.ingest.pds4 import read_label

    product_dir = csv_path.parents[3]
    image_labels = sorted((product_dir / "data").glob("**/*_d_img_*.xml"))
    assert image_labels, f"no image label under {product_dir / 'data'}"
    image = read_label(image_labels[0])
    assert image.lines and image.samples

    grid = read_geometry_grid(csv_path, lines=image.lines, samples=image.samples)
    assert grid.covers_full_image is True, grid.diagnostics.report()

    ls = np.linspace(float(grid.scan_lines[0]), float(grid.scan_lines[-1]), 5)
    ss = np.linspace(float(grid.pixels[0]), float(grid.pixels[-1]), 5)
    line, sample = (a.ravel() for a in np.meshgrid(ls, ss))
    lon, lat = pixel_to_lonlat(grid, line, sample)
    back = lonlat_to_pixel(grid, lat, lon)
    assert back.inside.all()
    assert np.max(np.abs(back.line - line)) < 0.01
    assert np.max(np.abs(back.sample - sample)) < 0.01
