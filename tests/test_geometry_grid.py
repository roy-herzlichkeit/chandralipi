"""The per-observation geometry grid: parsing, failure taxonomy, and inversion.

Two things are being pinned here. First, that no malformed row is ever dropped
without being classified and counted -- the fixtures deliberately include one of
each failure mode. Second, that the lat/lon -> pixel inverse is actually an
inverse: the round-trip through :func:`pixel_to_lonlat` and back must land on
the pixel it started from.

The synthetic fixtures reproduce the structure read out of two real products
(OHRC ``...0609041371`` and TMC-2 nadir ``...0627378557``): a 0-based ``Scan`` x
``Pixel`` grid sampled every 100 with a short final step onto the last real
index. Tests that need a real file are marked ``data`` and skip when it is
absent, so the suite stays runnable without a 1.2 GB archive.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from lunar_reg.ingest.fieldmap import Provenance
from lunar_reg.ingest.geometry_grid import (
    GEOMETRY_FIELD_NAMES,
    GeometryGrid,
    GridStatus,
    find_geometry_files,
    lonlat_to_pixel,
    pixel_to_lonlat,
    polygon_to_pixel_window,
    read_geometry_grid,
    read_geometry_label,
)

# ---------------------------------------------------------------------------
# Fixtures mirroring the real product structure
# ---------------------------------------------------------------------------

LABEL_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
  <Identification_Area>
    <logical_identifier>{pid}</logical_identifier>
  </Identification_Area>
  <File_Area_Observational>
    <File>
      <file_name>{csv_name}</file_name>
      <file_size unit="byte">{file_size}</file_size>
      <records>{records}</records>
      <md5_checksum>{md5}</md5_checksum>
    </File>
    <Table_Delimited>
      <records>{records}</records>
      <field_delimiter>Comma</field_delimiter>
      <Record_Delimited>
        <fields>4</fields>
        <Field_Delimited>
          <name>Longitude</name><field_number>1</field_number>
          <data_type>ASCII_Real</data_type>
        </Field_Delimited>
        <Field_Delimited>
          <name>Latitude</name><field_number>2</field_number>
          <data_type>ASCII_Real</data_type>
        </Field_Delimited>
        <Field_Delimited>
          <name>Pixel</name><field_number>3</field_number>
          <data_type>ASCII_Integer</data_type>
        </Field_Delimited>
        <Field_Delimited>
          <name>Scan</name><field_number>4</field_number>
          <data_type>ASCII_Integer</data_type>
        </Field_Delimited>
      </Record_Delimited>
    </Table_Delimited>
  </File_Area_Observational>
</Product_Observational>
"""


def sampled_axis(n_elements: int, step: int = 100) -> list[int]:
    """Index sampling the products use: every ``step``, then the last index.

    Verified against both real grids -- OHRC pixels end 11800, 11900, 11999 and
    scans end 100900, 101000, 101073.
    """
    values = list(range(0, n_elements, step))
    if values[-1] != n_elements - 1:
        values.append(n_elements - 1)
    return values


def ground(scan: int, pixel: int, lines: int, samples: int) -> tuple[float, float]:
    """A deliberately non-projective ground model.

    The along-track term is quadratic in scan and the cross-track term shears
    with scan, so a four-corner homography cannot reproduce it -- which is the
    property the real strips have and the reason this module exists.
    """
    v = scan / (lines - 1)
    u = pixel / (samples - 1)
    lat = -3.0 - 24.0 * v - 0.35 * v * (1.0 - v)
    lon = 142.7 - 0.72 * u - 1.0 * v + 0.08 * u * v + 0.05 * v * v
    return lat, lon


def write_product(
    tmp_path: Path,
    lines: int = 4037,
    samples: int = 413,
    step: int = 100,
    extra_rows: list[str] | None = None,
    stem: str = "ch2_tst_ncn_20260101T000000000_g_grd_d18",
    header: str | None = "Longitude,Latitude,Pixel,Scan",
    write_label: bool = True,
    bad_file_size: bool = False,
):
    """Write a synthetic ``_g_grd_d18`` CSV/label pair; return both paths."""
    scans = sampled_axis(lines, step)
    pixels = sampled_axis(samples, step)
    rows = []
    for scan in scans:
        for pixel in pixels:
            lat, lon = ground(scan, pixel, lines, samples)
            rows.append(f"{lon:.7f},{lat:.8f},{pixel},{scan}")
    rows.extend(extra_rows or [])

    csv_path = tmp_path / f"{stem}.csv"
    body = "".join(f"{row}\r\n" for row in rows)
    text = (header + "\n" + body) if header is not None else body
    csv_path.write_text(text, encoding="utf-8")

    label_path = tmp_path / f"{stem}.xml"
    if write_label:
        label_path.write_text(
            LABEL_TEMPLATE.format(
                pid=f"urn:isro:isda:test:{stem}",
                csv_name=csv_path.name,
                file_size=csv_path.stat().st_size + (89 if bad_file_size else 0),
                records=len(rows),
                md5="0" * 32,
            ),
            encoding="utf-8",
        )
        return csv_path, label_path
    return csv_path, None


@pytest.fixture
def product(tmp_path):
    csv_path, label_path = write_product(tmp_path)
    return read_geometry_grid(csv_path, label_path, lines=4037, samples=413)


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------


def test_label_field_order_comes_from_field_number(tmp_path):
    _, label_path = write_product(tmp_path)
    label = read_geometry_label(label_path)
    assert label.field_names == GEOMETRY_FIELD_NAMES
    assert label.field_types == (
        "ASCII_Real", "ASCII_Real", "ASCII_Integer", "ASCII_Integer",
    )
    assert label.records is not None


def test_label_order_wins_over_document_order(tmp_path):
    """field_number, not position in the XML, defines the column order."""
    _, label_path = write_product(tmp_path)
    text = label_path.read_text()
    # Swap the two numbers so document order and field_number disagree.
    text = text.replace(
        "<name>Longitude</name><field_number>1</field_number>",
        "<name>Longitude</name><field_number>2</field_number>",
    ).replace(
        "<name>Latitude</name><field_number>2</field_number>",
        "<name>Latitude</name><field_number>1</field_number>",
    )
    label_path.write_text(text)
    assert read_geometry_label(label_path).field_names[:2] == ("Latitude", "Longitude")


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def test_grid_shape_matches_the_sampling(product):
    assert product.shape == (len(sampled_axis(4037)), len(sampled_axis(413)))
    assert product.lat.shape == product.shape
    assert product.complete
    assert product.covers_full_image is True


def test_axes_are_zero_based_and_reach_the_last_index(product):
    assert product.scan_lines[0] == 0
    assert product.pixels[0] == 0
    assert product.scan_lines[-1] == 4036
    assert product.pixels[-1] == 412
    # The final step is short, so a uniform stride would be wrong.
    assert product.scan_lines[-1] - product.scan_lines[-2] != 100


def test_field_order_is_taken_from_the_label_and_marked_verified(product):
    assert product.field_names == GEOMETRY_FIELD_NAMES
    assert product.field_provenance is Provenance.VERIFIED


def test_record_count_is_checked_against_the_label(product):
    diag = product.diagnostics
    assert diag.declared_records == diag.observed_records
    assert not diag.record_count_mismatch
    assert "matches" in diag.report()


def test_corners_are_in_ul_ur_lr_ll_order(product):
    ul, ur, lr, ll = product.corners()
    assert ul == (product.lat[0, 0], product.lon[0, 0])
    assert ur == (product.lat[0, -1], product.lon[0, -1])
    assert lr == (product.lat[-1, -1], product.lon[-1, -1])
    assert ll == (product.lat[-1, 0], product.lon[-1, 0])


def test_headerless_file_falls_back_to_the_label(tmp_path):
    csv_path, label_path = write_product(tmp_path, header=None)
    grid = read_geometry_grid(csv_path, label_path, lines=4037, samples=413)
    assert grid.shape[0] > 1
    assert "no header line found" in grid.diagnostics.report()


def test_missing_label_uses_the_csv_header(tmp_path):
    csv_path, _ = write_product(tmp_path, write_label=False)
    grid = read_geometry_grid(csv_path, lines=4037, samples=413)
    assert grid.field_names == GEOMETRY_FIELD_NAMES
    assert grid.diagnostics.declared_records is None


def test_header_disagreeing_with_the_label_refuses_rather_than_picking_one(tmp_path):
    csv_path, label_path = write_product(tmp_path, header="Lon,Lat,Sample,Line")
    with pytest.raises(ValueError, match="disagrees with"):
        read_geometry_grid(csv_path, label_path, lines=4037, samples=413)


def test_label_without_a_required_field_raises(tmp_path):
    csv_path, label_path = write_product(tmp_path, header=None)
    text = label_path.read_text().replace("<name>Latitude</name>", "<name>Elevation</name>")
    label_path.write_text(text)
    with pytest.raises(ValueError, match="no 'latitude' field"):
        read_geometry_grid(csv_path, label_path)


def test_find_geometry_files_pairs_csv_with_label(tmp_path):
    nested = tmp_path / "geometry" / "calibrated" / "20260101"
    nested.mkdir(parents=True)
    csv_path, label_path = write_product(nested)
    found = find_geometry_files(tmp_path)
    assert found == [(csv_path, label_path)]


# ---------------------------------------------------------------------------
# Failure taxonomy -- nothing is dropped silently
# ---------------------------------------------------------------------------


def test_every_malformed_row_is_classified_counted_and_sampled(tmp_path):
    extra = [
        "1.0,2.0,3",                       # wrong field count
        "1.0,not-a-number,0,900",          # non numeric
        "1.0,120.0,0,1000",                # latitude out of range
        "1.0,2.0,99999,1100",              # pixel beyond the image
        "1.0,2.0,-5,1200",                 # negative index
        "",                                # blank line
    ]
    csv_path, label_path = write_product(tmp_path, extra_rows=extra)
    grid = read_geometry_grid(csv_path, label_path, lines=4037, samples=413)
    counts = grid.diagnostics.counts

    for status in (
        GridStatus.WRONG_FIELD_COUNT,
        GridStatus.NON_NUMERIC,
        GridStatus.COORDINATE_OUT_OF_RANGE,
        GridStatus.EMPTY_ROW,
    ):
        assert counts[status.value] == 1, status
        assert grid.diagnostics.samples[status.value]
    assert counts[GridStatus.INDEX_OUT_OF_RANGE.value] == 2

    report = grid.diagnostics.report()
    for status in (GridStatus.NON_NUMERIC, GridStatus.INDEX_OUT_OF_RANGE):
        assert status.value in report
        assert "sample:" in report
    assert grid.diagnostics.n_suspicious == 6


def test_a_clean_product_reports_no_suspicious_outcomes(product):
    assert product.diagnostics.n_suspicious == 0
    assert product.diagnostics.n_ok == product.diagnostics.observed_records


def test_duplicate_point_is_reported_and_the_first_value_kept(tmp_path):
    lat, lon = ground(0, 0, 4037, 413)
    csv_path, label_path = write_product(
        tmp_path, extra_rows=[f"{lon + 5:.7f},{lat + 5:.8f},0,0"]
    )
    grid = read_geometry_grid(csv_path, label_path, lines=4037, samples=413)
    assert grid.diagnostics.counts[GridStatus.DUPLICATE_POINT.value] == 1
    assert grid.lat[0, 0] == pytest.approx(lat, abs=1e-7)


def test_missing_grid_point_is_reported_not_silently_interpolated(tmp_path):
    csv_path, label_path = write_product(tmp_path)
    lines = csv_path.read_text().splitlines(keepends=True)
    # Drop one interior row; the rectangle is then incomplete.
    del lines[5]
    csv_path.write_text("".join(lines))
    grid = read_geometry_grid(csv_path, label_path, lines=4037, samples=413)

    assert grid.diagnostics.counts[GridStatus.MISSING_POINT.value] == 1
    assert not grid.complete
    assert "NOT a complete rectangle" in grid.diagnostics.report()
    assert np.isnan(grid.lat).sum() == 1
    # And the hole must propagate, not be papered over.
    hole = np.argwhere(np.isnan(grid.lat))[0]
    lon_q, lat_q = pixel_to_lonlat(
        grid, float(grid.scan_lines[hole[0]]), float(grid.pixels[hole[1]])
    )
    assert np.isnan(lat_q) and np.isnan(lon_q)


def test_record_count_mismatch_is_flagged(tmp_path):
    csv_path, label_path = write_product(tmp_path)
    label_path.write_text(label_path.read_text().replace("<records>", "<records>1"))
    grid = read_geometry_grid(csv_path, label_path, lines=4037, samples=413)
    assert grid.diagnostics.record_count_mismatch
    assert "MISMATCH" in grid.diagnostics.report()


def test_label_file_size_mismatch_is_reported_but_not_fatal(tmp_path):
    """Seen on the real TMC-2 product: file_size is wrong, the md5 is right."""
    csv_path, label_path = write_product(tmp_path, bad_file_size=True)
    grid = read_geometry_grid(csv_path, label_path, lines=4037, samples=413)
    assert grid.diagnostics.file_size_mismatch
    assert "label metadata bug" in grid.diagnostics.report()
    assert grid.complete


def test_a_file_with_no_usable_row_raises_with_the_report(tmp_path):
    csv_path = tmp_path / "empty_g_grd_d18.csv"
    csv_path.write_text("Longitude,Latitude,Pixel,Scan\r\nx,y,z,w\r\n")
    with pytest.raises(ValueError, match="no parseable geometry rows"):
        read_geometry_grid(csv_path)


def test_grid_short_of_the_image_edge_is_reported(tmp_path):
    csv_path, label_path = write_product(tmp_path, lines=4037, samples=413)
    grid = read_geometry_grid(csv_path, label_path, lines=5000, samples=413)
    assert grid.covers_full_image is False
    assert "extrapolation" in grid.diagnostics.report()


def test_covers_full_image_is_none_without_dimensions(tmp_path):
    csv_path, label_path = write_product(tmp_path)
    assert read_geometry_grid(csv_path, label_path).covers_full_image is None


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def test_grid_nodes_map_back_to_their_own_pixel(product):
    rng = np.random.default_rng(0)
    i = rng.integers(0, product.shape[0], 200)
    j = rng.integers(0, product.shape[1], 200)
    found = lonlat_to_pixel(product, product.lat[i, j], product.lon[i, j])
    assert found.inside.all()
    assert np.allclose(found.line, product.scan_lines[i], atol=1e-6)
    assert np.allclose(found.sample, product.pixels[j], atol=1e-6)


def test_interior_points_round_trip_through_pixel_to_lonlat(product):
    rng = np.random.default_rng(1)
    line = rng.uniform(0, 4036, 300)
    sample = rng.uniform(0, 412, 300)
    lon, lat = pixel_to_lonlat(product, line, sample)
    back = lonlat_to_pixel(product, lat, lon)
    assert back.inside.all()
    assert np.allclose(back.line, line, atol=1e-4)
    assert np.allclose(back.sample, sample, atol=1e-4)


def test_points_outside_the_grid_are_reported_not_extrapolated(product):
    found = lonlat_to_pixel(product, [45.0, 0.0], [10.0, 0.0])
    assert not found.inside.any()
    assert np.isnan(found.line).all()
    assert np.isnan(found.sample).all()
    assert found.n_inside == 0


def test_pixel_to_lonlat_outside_the_index_range_is_nan(product):
    lon, lat = pixel_to_lonlat(product, [-1.0, 9999.0], [0.0, 0.0])
    assert np.isnan(lon).all() and np.isnan(lat).all()


def test_mismatched_query_shapes_raise(product):
    with pytest.raises(ValueError, match="shape"):
        lonlat_to_pixel(product, [1.0, 2.0], [1.0])


def test_the_grid_beats_a_four_corner_homography_on_the_same_data(product):
    """The point of the module, stated as an executable claim.

    The synthetic ground model is non-projective by construction, so a
    homography through the four corners must miss the interior. The grid map
    must not.
    """
    cv2 = pytest.importorskip("cv2")
    ul, ur, lr, ll = product.corners()
    src = np.array([[lon, lat] for lat, lon in (ul, ur, lr, ll)], dtype=np.float32)
    height, width = 4037, 413
    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(src, dst)

    i, j = np.meshgrid(
        np.arange(product.shape[0]), np.arange(product.shape[1]), indexing="ij"
    )
    pts = np.stack(
        [product.lon.ravel(), product.lat.ravel(), np.ones(product.lat.size)], axis=1
    )
    projected = pts @ matrix.T
    projected = projected[:, :2] / projected[:, 2:3]
    homography_err = np.hypot(
        projected[:, 0] - product.pixels[j].ravel(),
        projected[:, 1] - product.scan_lines[i].ravel(),
    )

    found = lonlat_to_pixel(product, product.lat.ravel(), product.lon.ravel())
    grid_err = np.hypot(
        found.sample - product.pixels[j].ravel(),
        found.line - product.scan_lines[i].ravel(),
    )

    assert homography_err.max() > 10.0, "fixture is not non-projective enough to test"
    assert np.nanmax(grid_err) < 1e-6
    assert found.inside.all()


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def test_full_footprint_window_covers_the_whole_product(product):
    window = polygon_to_pixel_window(product, list(product.corners()))
    assert window == (0, 0, 4037, 413)


def test_interior_window_brackets_the_requested_region(product):
    i0, i1, j0, j1 = 10, 25, 1, 3
    poly = [
        (product.lat[i0, j0], product.lon[i0, j0]),
        (product.lat[i0, j1], product.lon[i0, j1]),
        (product.lat[i1, j1], product.lon[i1, j1]),
        (product.lat[i1, j0], product.lon[i1, j0]),
    ]
    row0, col0, height, width = polygon_to_pixel_window(product, poly)
    assert row0 <= product.scan_lines[i0]
    assert row0 + height >= product.scan_lines[i1]
    assert col0 <= product.pixels[j0]
    assert col0 + width >= product.pixels[j1]


def test_window_of_a_disjoint_polygon_is_none(product):
    assert polygon_to_pixel_window(product, [(0, 0), (0, 1), (1, 1), (1, 0)]) is None


def test_window_of_a_degenerate_ring_is_none(product):
    ul = product.corners()[0]
    assert polygon_to_pixel_window(product, [ul, ul]) is None


def test_closed_ring_is_accepted(product):
    ring = list(product.corners())
    assert polygon_to_pixel_window(product, ring + [ring[0]]) == \
        polygon_to_pixel_window(product, ring)


# ---------------------------------------------------------------------------
# Real products, when they happen to be extracted
# ---------------------------------------------------------------------------

REAL_ROOTS = (
    Path("data/raw"),
    Path("data/interim"),
)


def real_geometry_files():
    out = []
    for root in REAL_ROOTS:
        if root.exists():
            out.extend(find_geometry_files(root))
    return out


@pytest.mark.data
@pytest.mark.parametrize("paths", real_geometry_files() or [None])
def test_real_geometry_products_load_without_a_single_bad_row(paths):
    if paths is None:
        pytest.skip("no extracted *_g_grd_d18.csv under data/")
    csv_path, label_path = paths
    grid = read_geometry_grid(csv_path, label_path)

    assert grid.field_provenance is Provenance.VERIFIED
    assert grid.field_names == GEOMETRY_FIELD_NAMES
    assert grid.complete, grid.diagnostics.report()
    assert not grid.diagnostics.record_count_mismatch, grid.diagnostics.report()
    assert grid.scan_lines[0] == 0 and grid.pixels[0] == 0

    # Nodes must invert exactly, on the real geometry as on the synthetic one.
    step = max(1, grid.shape[0] // 50)
    i = np.arange(0, grid.shape[0], step)
    j = np.zeros_like(i) + grid.shape[1] // 2
    found = lonlat_to_pixel(grid, grid.lat[i, j], grid.lon[i, j])
    assert found.inside.all()
    assert np.allclose(found.line, grid.scan_lines[i], atol=1e-4)


def test_grid_is_frozen_and_reports_shape():
    grid = GeometryGrid(
        scan_lines=np.array([0, 1]),
        pixels=np.array([0, 1]),
        lat=np.zeros((2, 2)),
        lon=np.zeros((2, 2)),
    )
    assert grid.shape == (2, 2)
    with pytest.raises(AttributeError):
        grid.lines = 5  # type: ignore[misc]
    assert math.isclose(grid.lat.sum(), 0.0)
