"""P1.05 — geometry grid fixes (Phase_1/LLD/geometry_grid.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h1 import REPO, write_grid_csv

LINES, SAMPLES = 1001, 301


def _lonlat(line, sample):
    # smooth, slightly rotated field near Vikram (lon 32.30..32.32, lat -69.30..-69.33)
    return 32.30 + 2e-5 * sample + 1e-6 * line, -69.30 - 3e-5 * line + 1e-6 * sample


def _grid(tmp_path, fn=_lonlat, name="ch2_ohr_ncp_20240425T1406019344_g_grd_d18.csv"):
    from lunar_reg.ingest.geometry_grid import read_geometry_grid

    path = write_grid_csv(tmp_path / name, LINES, SAMPLES, fn)
    return read_geometry_grid(path, lines=LINES, samples=SAMPLES)


def test_snap_public():
    from lunar_reg.ingest import geometry_grid as gg

    assert gg.snap_to_integer(11999.9999999) == 12000.0
    assert gg.snap_to_integer(3.4) == 3.4
    assert "snap_to_integer" in gg.__all__


def test_find_files_patterns(tmp_path):
    from lunar_reg.ingest.geometry_grid import find_geometry_files

    for n in ("ch2_ohr_ncp_20230823T1450475804_g_grd_n18.csv",
              "ch2_ohr_ncp_20240425T1406019344_g_grd_d18.csv"):
        (tmp_path / n).write_text("x")
    assert len(find_geometry_files(tmp_path)) == 2
    hits = find_geometry_files(tmp_path, "ch2_ohr_nrp_20230823T1450475804_d_img_n18")
    assert [p.name for p, _ in hits] == ["ch2_ohr_ncp_20230823T1450475804_g_grd_n18.csv"]
    assert find_geometry_files(tmp_path, "no_token_here") == []


def test_small_interior_polygon_gets_window(tmp_path):
    from lunar_reg.ingest.geometry_grid import pixel_to_lonlat, polygon_to_pixel_window

    grid = _grid(tmp_path)
    # a polygon spanning lines 400..600 and samples 100..200: its vertices are inside the grid,
    # and a polygon covering the whole product must give the whole window
    corners = [(400, 100), (400, 200), (600, 200), (600, 100)]
    ring = []
    for line, sample in corners:
        lon, lat = pixel_to_lonlat(grid, line, sample)
        ring.append((float(lat), float(lon)))
    win = polygon_to_pixel_window(grid, ring)
    assert win is not None
    r0, c0, h, w = win
    assert r0 <= 400 and r0 + h >= 600 and c0 <= 100 and c0 + w >= 200
    big = [(-69.0, 32.0), (-69.0, 32.6), (-69.6, 32.6), (-69.6, 32.0)]
    assert polygon_to_pixel_window(grid, big) == (0, 0, LINES, SAMPLES)


def test_antimeridian_rewrap(tmp_path):
    from lunar_reg.ingest.geometry_grid import lonlat_to_pixel

    def seam(line, sample):
        lon = 179.7 + 2e-3 * sample
        return (lon - 360.0 if lon > 180 else lon), 10.0 - 1e-3 * line

    grid = _grid(tmp_path, seam, name="seam_g_grd_d18.csv")
    assert grid.longitude_reference_deg is not None
    look = lonlat_to_pixel(grid, np.array([9.9]), np.array([-179.9]))
    assert bool(look.inside[0])
    plain = _grid(tmp_path, name="plain_g_grd_d18.csv")
    assert plain.longitude_reference_deg is None


@pytest.mark.data
def test_real_ncp_grid_roundtrip():
    from lunar_reg.ingest.geometry_grid import lonlat_to_pixel, pixel_to_lonlat, read_geometry_grid

    csvs = sorted(REPO.glob("data/raw/ch2/ohrc/*/geometry/**/*_g_grd_*.csv"))
    if not csvs:
        pytest.skip("no calibrated OHRC geometry grid under data/raw/ch2/ohrc (P1.DL)")
    grid = read_geometry_grid(csvs[0])
    ls = np.linspace(float(grid.scan_lines[0]), float(grid.scan_lines[-1]), 5)
    ss = np.linspace(float(grid.pixels[0]), float(grid.pixels[-1]), 5)
    L, S = np.meshgrid(ls, ss)
    lon, lat = pixel_to_lonlat(grid, L.ravel(), S.ravel())
    back = lonlat_to_pixel(grid, lat, lon)
    assert np.nanmax(np.abs(back.line - L.ravel())) < 0.01
    assert np.nanmax(np.abs(back.sample - S.ravel())) < 0.01
