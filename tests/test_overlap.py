"""Footprint overlap, its degenerate cases, and cropping.

The emphasis here is the failure taxonomy: every way a pair can fail to produce
a usable overlap must be classified and counted, never silently dropped.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from lunar_reg.constants import MOON_RADIUS_M
from lunar_reg.ingest.overlap import (
    FootprintPolygon,
    OverlapStatus,
    crop_to_overlap,
    find_overlapping_pairs,
    footprint_from_row,
    geographic_to_pixel_transform,
    intersect,
    polygon_area_m2,
    polygon_to_pixel_window,
    polygon_to_wkt,
)


def box(lat0, lat1, lon0, lon1, pid="p", sensor="OHRC", lines=1000, samples=800):
    """Footprint in UL, UR, LR, LL ring order."""
    return FootprintPolygon(
        corners=((lat1, lon0), (lat1, lon1), (lat0, lon1), (lat0, lon0)),
        product_id=pid, sensor=sensor, lines=lines, samples=samples,
    )


def analytic_area(lat0, lat1, lon0, lon1):
    return (
        MOON_RADIUS_M**2
        * math.radians(lon1 - lon0)
        * (math.sin(math.radians(lat1)) - math.sin(math.radians(lat0)))
    )


# --- area: the library trap this module exists to work around --------------


def test_area_matches_the_analytic_spherical_formula():
    ring = ((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0))
    assert polygon_area_m2(ring) == pytest.approx(analytic_area(0, 1, 0, 1), rel=0.01)


def test_area_is_correct_for_closed_rings():
    """Regression guard on a real pygeodesy trap.

    ``clipFHP4`` returns rings with the first vertex repeated at the end.
    ``sphericalNvector.areaOf`` is wrong by 53x-51,567x on such rings, with the
    error growing as the polygon shrinks. This module strips the duplicate and
    uses sphericalTrigonometry; if either safeguard is removed, this fails.
    """
    open_ring = ((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0))
    closed_ring = (*open_ring, open_ring[0])
    assert polygon_area_m2(closed_ring) == pytest.approx(polygon_area_m2(open_ring), rel=1e-9)


def test_thin_sliver_has_a_small_area_not_a_huge_one():
    """The sliver case that the n-vector implementation gets catastrophically wrong."""
    sliver = polygon_area_m2(((0.0, 0.0), (0.0, 10.0), (0.0001, 10.0), (0.0001, 0.0)))
    big = polygon_area_m2(((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)))
    assert sliver < big / 1000


def test_area_is_correct_for_longitudes_beyond_180():
    """Third pygeodesy trap: ``ST.LatLon`` raises above +/-180 longitude.

    That raise used to be caught and turned into an area of exactly 0, so a
    footprint using the 0..360 east-longitude convention -- which
    ``validate()`` accepts, and which polar sweeps make likely -- measured zero
    and looked like an empty overlap.
    """
    signed = ((0.0, 170.0), (0.0, -170.0), (1.0, -170.0), (1.0, 170.0))
    unsigned = ((0.0, 170.0), (0.0, 190.0), (1.0, 190.0), (1.0, 170.0))
    assert polygon_area_m2(unsigned) > 0.0
    assert polygon_area_m2(unsigned) == pytest.approx(polygon_area_m2(signed), rel=1e-9)


def test_area_of_a_polygon_around_the_pole_matches_the_analytic_cap():
    """A ring at constant colatitude has area ``2*pi*R^2*(1 - cos(colat))``.

    A 180-gon inscribed in that circle is short by ``1 - (n/2pi)sin(2pi/n)``,
    i.e. 0.02%, which is why the tolerance is not tighter.
    """
    for colat in (1.0, 3.0, 5.0):
        ring = cap_ring(colat, n=180)
        assert polygon_area_m2(ring) == pytest.approx(cap_area(colat), rel=1e-3)


def test_degenerate_rings_have_zero_area():
    assert polygon_area_m2(((0.0, 0.0), (1.0, 1.0))) == 0.0
    assert polygon_area_m2(()) == 0.0


# --- the overlap taxonomy --------------------------------------------------


def test_overlapping_footprints_produce_a_polygon():
    r = intersect(box(0, 10, 0, 10, "a"), box(5, 15, 5, 15, "b"))
    assert r.status is OverlapStatus.OK
    assert len(r.polygon) >= 3
    assert r.area_m2 == pytest.approx(analytic_area(5, 10, 5, 10), rel=0.02)


def test_overlap_fractions_are_reported_for_both_sides():
    r = intersect(box(0, 10, 0, 10, "a"), box(0, 20, 0, 20, "b"))
    assert r.source_fraction == pytest.approx(1.0, rel=0.02)
    assert 0.2 < r.reference_fraction < 0.3


def test_containment_gives_the_contained_footprint():
    r = intersect(box(0, 10, 0, 10, "outer"), box(2, 8, 2, 8, "inner"))
    assert r.status is OverlapStatus.OK
    assert r.area_m2 == pytest.approx(analytic_area(2, 8, 2, 8), rel=0.02)


def test_disjoint_is_classified_not_dropped():
    r = intersect(box(0, 10, 0, 10, "a"), box(50, 60, 50, 60, "b"))
    assert r.status is OverlapStatus.DISJOINT
    assert not r.status.is_suspicious, "plain non-overlap should not look like a bug"


def test_edge_touching_is_distinguished_from_disjoint():
    """clipFHP4 returns empty for both; conflating them would hide a real case."""
    r = intersect(box(0, 10, 0, 10, "a"), box(10, 20, 0, 10, "b"))
    assert r.status is OverlapStatus.TOUCHING_ONLY
    assert r.status.is_suspicious


def test_corner_touching_is_also_touching_only():
    assert intersect(box(0, 10, 0, 10), box(10, 20, 10, 20)).status is (
        OverlapStatus.TOUCHING_ONLY
    )


def test_sliver_overlap_is_flagged_degenerate():
    r = intersect(box(0, 10, 0, 10, "a"), box(9.99999, 20, 0, 10, "b"))
    assert r.status is OverlapStatus.DEGENERATE_SLIVER
    assert "aspect" in r.detail


def test_antimeridian_footprint_is_flagged():
    r = intersect(box(0, 10, -179, 179, "wrap"), box(0, 10, 0, 10, "b"))
    assert r.status is OverlapStatus.ANTIMERIDIAN


# --- polar footprints ------------------------------------------------------
#
# These used to be rejected outright, which threw away 100% of the real OHRC
# archive: every product downloaded so far sits at about -85 degrees. They are
# now clipped in a polar azimuthal-equidistant frame instead.


def cap_ring(colat_deg, pole_lat=-90.0, n=180, lon0=0.0, lon_span=360.0):
    """A polygon at constant angular distance from a pole.

    Sampled densely so the polygon approximates the true cap. Its spherical area
    is ``2*pi*R^2*(1 - cos(colat))``, which is what makes it a check with an
    answer known in advance rather than only a self-consistent one.
    """
    step = lon_span / n
    lats_lons = []
    for i in range(n):
        lon = lon0 + i * step
        lats_lons.append((pole_lat + colat_deg if pole_lat < 0 else pole_lat - colat_deg, lon))
    return tuple(lats_lons)


def cap_area(colat_deg):
    return 2 * math.pi * MOON_RADIUS_M**2 * (1 - math.cos(math.radians(colat_deg)))


def test_polar_pair_is_clipped_instead_of_rejected():
    r = intersect(box(84, 89, 0, 10, "polar"), box(85, 88, 2, 8, "b"))
    assert r.status is OverlapStatus.OK
    assert len(r.polygon) >= 3
    # The clip is a straight-edged quadrilateral in the polar plane, so its
    # edges cut just inside the parallels of the lat/lon rectangle; a couple of
    # percent below the rectangle's analytic area is the expected answer, not
    # agreement with it.
    assert 0.95 < r.area_m2 / analytic_area(85, 88, 2, 8) < 1.0


def test_polar_cap_overlap_is_right_where_lat_lon_is_hopeless():
    """The case a lat/lon clip cannot express at all.

    A ring at constant colatitude encircles the pole; in lat/lon it collapses to
    a horizontal line of zero area. In the polar frame it is a circle, and the
    intersection of two concentric caps is the smaller cap, whose area is known
    analytically.
    """
    inner = FootprintPolygon(corners=cap_ring(3.0), product_id="inner")
    outer = FootprintPolygon(corners=cap_ring(5.0), product_id="outer")

    assert polygon_area_m2(inner.corners) == pytest.approx(cap_area(3.0), rel=1e-3)

    r = intersect(inner, outer)
    assert r.status is OverlapStatus.OK
    assert r.area_m2 == pytest.approx(cap_area(3.0), rel=1e-3)


def test_polar_footprint_spanning_the_antimeridian_is_not_an_antimeridian_failure():
    """Near a pole a wide longitude span is ordinary, not evidence of a wrap.

    Both footprints here straddle 180 degrees a degree from the pole. The
    antimeridian guard would reject them; the polar frame has no antimeridian.
    """
    a = FootprintPolygon(corners=cap_ring(1.0, lon0=60.0, lon_span=240.0, n=60), product_id="a")
    b = FootprintPolygon(corners=cap_ring(1.0, lon0=105.0, lon_span=240.0, n=60), product_id="b")
    assert a.validate() is OverlapStatus.OK
    assert a.crosses_antimeridian, "the guard would have fired on this in lat/lon"

    r = intersect(a, b)
    assert r.status is OverlapStatus.OK
    assert r.area_m2 > 0


def pole_crossing_strip(half_width_m, half_length_m, bearing_deg, pole_lat=-90.0):
    """A rectangular strip centred exactly on a pole, built in the polar frame.

    The shape an OHRC pass straight over the pole makes. In lat/lon it is
    pathological: all four corners land on the *same* parallel, so a lat/lon
    polygon encloses no area at all, and its longitudes span the antimeridian.
    """
    from lunar_reg.ingest.overlap import _M_PER_ARC_DEG, PolarFrame

    frame = PolarFrame(pole_lat)
    t = math.radians(bearing_deg)
    corners = []
    for dx, dy in ((-half_width_m, -half_length_m), (half_width_m, -half_length_m),
                   (half_width_m, half_length_m), (-half_width_m, half_length_m)):
        x = (dx * math.cos(t) - dy * math.sin(t)) / _M_PER_ARC_DEG
        y = (dx * math.sin(t) + dy * math.cos(t)) / _M_PER_ARC_DEG
        corners.append(frame.to_sphere(y, x))
    return tuple(corners)


def test_strip_passing_over_the_pole_has_its_true_area():
    """3 km x 25 km over the pole is 75 km^2, however unhelpful its lat/lon is."""
    corners = pole_crossing_strip(1500.0, 12500.0, 0.0)
    strip = FootprintPolygon(corners=corners, product_id="over_pole")

    assert len(set(round(lat, 6) for lat in strip.lats)) == 1, (
        "all four corners are on one parallel -- the degenerate case"
    )
    assert strip.crosses_antimeridian, "and it wraps, which used to reject it too"
    assert strip.validate() is OverlapStatus.OK
    assert strip.area_m2() / 1e6 == pytest.approx(75.0, rel=1e-4)


def test_two_strips_crossing_at_the_pole_intersect_in_their_shared_square():
    """Two 3 km-wide strips crossing at right angles share a 3 km x 3 km square."""
    a = FootprintPolygon(corners=pole_crossing_strip(1500.0, 12500.0, 0.0), product_id="a")
    b = FootprintPolygon(corners=pole_crossing_strip(1500.0, 12500.0, 90.0), product_id="b")

    r = intersect(a, b)
    assert r.status is OverlapStatus.OK
    assert r.area_m2 / 1e6 == pytest.approx(9.0, rel=1e-4)


def test_east_longitude_convention_gives_the_same_answer():
    """A label may write longitude as 0..360; ``validate`` accepts it, so every
    stage downstream must agree with the signed form rather than measure zero."""
    signed = pole_crossing_strip(1500.0, 12500.0, 0.0)
    unsigned = tuple((lat, lon % 360.0) for lat, lon in signed)
    other = FootprintPolygon(corners=pole_crossing_strip(1500.0, 12500.0, 90.0), product_id="b")

    a = FootprintPolygon(corners=signed, product_id="signed")
    a360 = FootprintPolygon(corners=unsigned, product_id="unsigned")
    assert a360.area_m2() == pytest.approx(a.area_m2(), rel=1e-9)
    assert intersect(a360, other).area_m2 == pytest.approx(
        intersect(a, other).area_m2, rel=1e-9
    )


def test_a_wrapping_bounding_box_at_the_pole_is_refused_not_believed():
    """The trap on the other side of dropping the antimeridian guard.

    A strip over the pole has corners either side of the antimeridian, so its
    lat/lon bounding box is a cap wrapped most of the way round the pole --
    hundreds of times the real footprint. Corners are fine there; a box is not,
    and the box must say so rather than clip confidently.
    """
    # What `manifest.py` reduces a near-pole strip whose corners straddle the
    # antimeridian to: a box wrapped almost all the way round the pole.
    row = {"product_id": "over_pole", "sensor": "OHRC",
           "min_lat": -89.9, "max_lat": -89.0, "min_lon": -175.0, "max_lon": 175.0}

    boxed = footprint_from_row(row)
    assert boxed.bbox_derived
    assert boxed.validate() is OverlapStatus.POLAR_BBOX_UNUSABLE
    assert OverlapStatus.POLAR_BBOX_UNUSABLE.is_suspicious
    # And here is *why* it is refused rather than kept as a rough upper bound:
    # the ring is genuinely ambiguous. Spherical trigonometry reads the closing
    # edge as the 10-degree short way across the antimeridian; reading the box
    # as a lat/lon band takes the 350-degree long way. The two answers differ by
    # more than an order of magnitude and nothing in the ring says which is meant.
    short_way = boxed.area_m2()
    long_way = analytic_area(-89.9, -89.0, -175.0, 175.0)
    assert long_way / short_way > 10.0


def test_a_polar_bounding_box_that_does_not_wrap_is_still_usable():
    """Only the wrapping case is refused: the real OHRC products are boxes that
    do not wrap, and must keep working as an upper bound."""
    row = {"product_id": "ohrc", "sensor": "OHRC", "min_lat": -85.37,
           "max_lat": -84.55, "min_lon": 23.02, "max_lon": 27.72}
    boxed = footprint_from_row(row)
    assert boxed.bbox_derived and boxed.is_polar
    assert boxed.validate() is OverlapStatus.OK


def test_polar_and_equatorial_footprints_read_as_disjoint_not_as_a_polar_failure():
    """An honest non-overlap must not be dressed up as a geometry problem.

    This is the current real download: polar OHRC against mid-latitude TMC-2.
    """
    r = intersect(box(84, 89, 0, 10, "polar"), box(-10, 10, 0, 10, "equatorial"))
    assert r.status is OverlapStatus.DISJOINT
    assert not r.status.is_suspicious


def test_polar_pair_reaching_too_far_from_the_pole_is_reported_not_guessed():
    """Beyond the trusted colatitude the frame's error is unquantified, so it
    is refused with its own status rather than clipped anyway."""
    r = intersect(box(84, 89, 0, 10, "polar"), box(10, 85, 0, 10, "tall"))
    assert r.status is OverlapStatus.POLAR_EXTENT_UNSUPPORTED
    assert r.status.is_suspicious
    assert "deg from the north pole" in r.detail


def test_retired_polar_status_still_parses_for_old_result_tables():
    """Result tables written before the fix carry 'polar'; reading one must not
    raise, even though nothing produces the status any more."""
    assert OverlapStatus("polar") is OverlapStatus.POLAR


# --- the real OHRC products ------------------------------------------------

#: Corner coordinates read from the three complete real OHRC labels
#: (`ch2_ohr_ncp_20260103T*_d_img_d18.xml`, calibrated collection) with
#: `read_label`, and the footprint area each produces through
#: `footprint_from_row(...).area_m2()`. The areas are measured, not assumed; a
#: 3 km x 25 km OHRC strip is ~75 km^2, and an independent Monte-Carlo
#: integration on the sphere (uniform in lon and sin(lat), great-circle
#: point-in-polygon) agreed with each to within its 2-sigma noise of ~0.23 km^2.
REAL_OHRC = {
    "ch2_ohr_ncp_20260103T0609041371": (
        ((-85.323534, 27.723846), (-85.365795, 26.571730),
         (-84.552455, 24.029151), (-84.588687, 23.016449)),
        101074, 78.89,
    ),
    "ch2_ohr_ncp_20260103T1005176450": (
        ((-85.279005, 27.751481), (-85.325413, 26.628534),
         (-84.522148, 23.790313), (-84.562153, 22.794260)),
        101075, 78.96,
    ),
    "ch2_ohr_ncp_20260103T1203563771": (
        ((-85.280483, 27.939505), (-85.327140, 26.814357),
         (-84.529135, 23.792702), (-84.569067, 22.792277)),
        101073, 79.33,
    ),
}


def real_ohrc_footprint(product_id):
    """Build one real footprint through `footprint_from_row`, corners in label
    order (UL, UR, LL, LR -- which is *not* ring order; see
    `test_corner_numbering_is_not_ring_order`)."""
    corners, lines, _ = REAL_OHRC[product_id]
    row = {"product_id": product_id, "sensor": "OHRC", "lines": lines, "samples": 12000}
    for i, (lat, lon) in enumerate(corners, start=1):
        row[f"corner{i}_lat"], row[f"corner{i}_lon"] = lat, lon
    return footprint_from_row(row)


@pytest.mark.parametrize("product_id", sorted(REAL_OHRC))
def test_real_ohrc_footprints_are_usable_not_rejected(product_id):
    """The regression this whole polar path exists for: every real OHRC product
    was classified POLAR and discarded."""
    expected_km2 = REAL_OHRC[product_id][2]
    footprint = real_ohrc_footprint(product_id)

    assert footprint.is_polar, "these products really are at -85 degrees"
    assert footprint.validate() is OverlapStatus.OK
    assert footprint.area_m2() / 1e6 == pytest.approx(expected_km2, abs=0.05)


def test_real_ohrc_products_overlap_each_other():
    """Three passes over the same polar target; they should share most of their
    area. Measured 69.30 km^2 for this pair, cross-checked by Monte-Carlo
    integration at 69.30 +/- 0.16 km^2 (2 sigma)."""
    a = real_ohrc_footprint("ch2_ohr_ncp_20260103T0609041371")
    b = real_ohrc_footprint("ch2_ohr_ncp_20260103T1005176450")

    r = intersect(a, b)
    assert r.status is OverlapStatus.OK
    assert r.area_m2 / 1e6 == pytest.approx(69.30, abs=0.2)
    assert 0.8 < r.source_fraction < 1.0
    assert 0.8 < r.reference_fraction < 1.0


def test_real_polar_overlap_maps_to_a_pixel_window():
    """A polar overlap is only useful if it can be cropped, which needs the
    pixel fit to happen in the same frame the polygon was clipped in."""
    a = real_ohrc_footprint("ch2_ohr_ncp_20260103T0609041371")
    b = real_ohrc_footprint("ch2_ohr_ncp_20260103T1005176450")

    row_off, col_off, height, width = polygon_to_pixel_window(a, intersect(a, b).polygon)
    assert row_off >= 0 and col_off >= 0
    assert row_off + height <= a.lines and col_off + width <= a.samples
    # ~88% of the strip is shared, so the window must be most of the product.
    assert height * width > 0.5 * a.lines * a.samples


def test_polar_footprint_covers_its_own_product_in_pixels():
    """Off-by-one and frame-agreement guard, the polar twin of
    `test_full_coverage_window_is_the_whole_product`."""
    fp = real_ohrc_footprint("ch2_ohr_ncp_20260103T1203563771")
    assert polygon_to_pixel_window(fp, fp.corners) == (0, 0, fp.lines, fp.samples)


def test_non_finite_corner_is_invalid_not_a_crash():
    bad = FootprintPolygon(corners=((0.0, 0.0), (0.0, 1.0), (float("nan"), 1.0), (1.0, 0.0)))
    assert intersect(bad, box(0, 10, 0, 10)).status is OverlapStatus.INVALID_GEOMETRY


def test_out_of_range_latitude_is_invalid():
    bad = FootprintPolygon(corners=((0.0, 0.0), (0.0, 1.0), (95.0, 1.0), (1.0, 0.0)))
    assert intersect(bad, box(0, 10, 0, 10)).status is OverlapStatus.INVALID_GEOMETRY


def test_intersect_never_raises_on_adversarial_input():
    """Whatever comes in, the caller gets a classified result to count."""
    weird = [
        FootprintPolygon(corners=((0.0, 0.0),)),
        FootprintPolygon(corners=((0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0))),
        FootprintPolygon(corners=((-90.0, -180.0), (90.0, 180.0), (0.0, 0.0), (1.0, 1.0))),
    ]
    for a in weird:
        for b in weird:
            assert isinstance(intersect(a, b).status, OverlapStatus)


def test_wkt_is_lon_lat_and_closed():
    wkt = polygon_to_wkt(((10.0, 20.0), (10.0, 30.0), (15.0, 30.0)))
    assert wkt.startswith("POLYGON((")
    assert wkt.split("((")[1].split(",")[0].strip().startswith("20."), "lon must come first"
    coords = wkt.split("((")[1].removesuffix("))").split(",")
    assert coords[0].strip() == coords[-1].strip(), "ring must close"


def test_wkt_of_a_degenerate_ring_is_none():
    assert polygon_to_wkt(((0.0, 0.0), (1.0, 1.0))) is None


# --- manifest integration and diagnostics ----------------------------------


def _manifest(rows):
    import pandas as pd

    from lunar_reg.ingest.manifest import COLUMNS

    frame = pd.DataFrame(rows)
    for col in COLUMNS:
        if col not in frame.columns:
            frame[col] = None
    return frame


def test_footprint_from_bounding_box_columns():
    row = {"product_id": "x", "sensor": "OHRC", "min_lat": 0, "max_lat": 10,
           "min_lon": 0, "max_lon": 10, "lines": 100, "samples": 50}
    poly = footprint_from_row(row)
    assert poly is not None
    assert poly.bounds == (0.0, 10.0, 0.0, 10.0)
    assert (poly.lines, poly.samples) == (100, 50)


def test_footprint_prefers_explicit_corners_over_bbox():
    row = {"product_id": "x", "min_lat": 0, "max_lat": 10, "min_lon": 0, "max_lon": 10}
    for i, (lat, lon) in enumerate([(9, 1), (9, 8), (1, 1), (1, 8)], start=1):
        row[f"corner{i}_lat"], row[f"corner{i}_lon"] = lat, lon
    poly = footprint_from_row(row)
    assert poly.bounds == (1.0, 9.0, 1.0, 8.0), "corners should win over the bbox"


def test_corner_ring_order_avoids_a_bow_tie():
    """UL,UR,LL,LR traversed in index order self-intersects; UL,UR,LR,LL does not."""
    row = {"product_id": "x"}
    for i, (lat, lon) in enumerate([(9, 1), (9, 8), (1, 1), (1, 8)], start=1):
        row[f"corner{i}_lat"], row[f"corner{i}_lon"] = lat, lon
    poly = footprint_from_row(row)
    assert poly.corners == ((9.0, 1.0), (9.0, 8.0), (1.0, 8.0), (1.0, 1.0))
    assert poly.area_m2() == pytest.approx(analytic_area(1, 9, 1, 8), rel=0.02)


def test_row_without_any_geometry_returns_none():
    assert footprint_from_row({"product_id": "x", "sensor": "OHRC"}) is None


def test_nan_coordinates_are_treated_as_missing():
    row = {"product_id": "x", "min_lat": float("nan"), "max_lat": 10,
           "min_lon": 0, "max_lon": 10}
    assert footprint_from_row(row) is None


def test_inverted_bbox_is_rejected():
    row = {"product_id": "x", "min_lat": 10, "max_lat": 0, "min_lon": 0, "max_lon": 10}
    assert footprint_from_row(row) is None


def test_finds_pairs_and_ranks_by_overlap_area():
    manifest = _manifest([
        {"product_id": "ohrc_a", "sensor": "OHRC", "min_lat": 0, "max_lat": 10,
         "min_lon": 0, "max_lon": 10, "lines": 100, "samples": 100},
        {"product_id": "tmc_big", "sensor": "TMC2", "min_lat": 0, "max_lat": 10,
         "min_lon": 0, "max_lon": 10, "lines": 50, "samples": 50},
        {"product_id": "tmc_small", "sensor": "TMC2", "min_lat": 8, "max_lat": 12,
         "min_lon": 8, "max_lon": 12, "lines": 50, "samples": 50},
        {"product_id": "tmc_far", "sensor": "TMC2", "min_lat": 70, "max_lat": 75,
         "min_lon": 70, "max_lon": 75, "lines": 50, "samples": 50},
    ])
    pairs, diag = find_overlapping_pairs(manifest, "OHRC", "TMC2")

    assert list(pairs["reference_id"]) == ["tmc_big", "tmc_small"]
    assert pairs.iloc[0]["overlap_area_m2"] > pairs.iloc[1]["overlap_area_m2"]
    assert diag.n_pairs_considered == 3
    assert diag.counts[OverlapStatus.DISJOINT.value] == 1
    assert pairs.iloc[0]["polygon_wkt"].startswith("POLYGON((")


def test_diagnostics_surface_counts_and_a_sample_for_every_failure():
    """The explicit requirement: nothing degenerate may be dropped without a trace."""
    manifest = _manifest([
        {"product_id": "ohrc_a", "sensor": "OHRC", "min_lat": 0, "max_lat": 10,
         "min_lon": 0, "max_lon": 10},
        {"product_id": "ohrc_polar", "sensor": "OHRC", "min_lat": 84, "max_lat": 89,
         "min_lon": 0, "max_lon": 10},
        {"product_id": "tmc_touch", "sensor": "TMC2", "min_lat": 10, "max_lat": 20,
         "min_lon": 0, "max_lon": 10},
        {"product_id": "tmc_far", "sensor": "TMC2", "min_lat": 40, "max_lat": 45,
         "min_lon": 40, "max_lon": 45},
        # Overlaps ohrc_polar in latitude but runs down to 20 degrees, far
        # outside the range the polar frame is trusted over.
        {"product_id": "tmc_tall", "sensor": "TMC2", "min_lat": 20, "max_lat": 85,
         "min_lon": 0, "max_lon": 10},
    ])
    pairs, diag = find_overlapping_pairs(manifest, "OHRC", "TMC2")

    assert len(pairs) == 0
    assert diag.n_pairs_considered == 6
    assert diag.counts[OverlapStatus.TOUCHING_ONLY.value] == 1
    assert diag.counts[OverlapStatus.POLAR_EXTENT_UNSUPPORTED.value] == 1
    assert diag.counts[OverlapStatus.DISJOINT.value] == 4
    assert diag.n_suspicious == 2, (
        "touching and the unsupported polar extent are suspicious; disjoint is not"
    )

    report = diag.report()
    for token in ("touching_only", "polar_extent_unsupported", "sample:"):
        assert token in report
    assert "tmc_touch" in report or "tmc_tall" in report


def test_missing_footprint_is_reported_as_metadata_not_as_no_overlap():
    """Today's real state: geometry columns are unresolved.

    The report must not let that read as 'these products do not overlap'.
    """
    manifest = _manifest([
        {"product_id": "ohrc_a", "sensor": "OHRC"},
        {"product_id": "tmc_a", "sensor": "TMC2"},
    ])
    pairs, diag = find_overlapping_pairs(manifest, "OHRC", "TMC2")

    assert len(pairs) == 0
    assert diag.n_source_without_footprint == 1
    assert diag.n_reference_without_footprint == 1
    assert diag.counts[OverlapStatus.MISSING_FOOTPRINT.value] == 1

    report = diag.report()
    assert "metadata gap, not a geometry failure" in report
    assert "NOT evidence that products do not overlap" in report


def test_min_source_fraction_filters_pairs():
    manifest = _manifest([
        {"product_id": "ohrc_a", "sensor": "OHRC", "min_lat": 0, "max_lat": 10,
         "min_lon": 0, "max_lon": 10},
        {"product_id": "tmc_tiny", "sensor": "TMC2", "min_lat": 9, "max_lat": 10,
         "min_lon": 9, "max_lon": 10},
    ])
    assert len(find_overlapping_pairs(manifest, "OHRC", "TMC2")[0]) == 1
    assert len(find_overlapping_pairs(manifest, "OHRC", "TMC2", min_source_fraction=0.5)[0]) == 0


def test_empty_manifest_yields_empty_results_not_an_error():
    pairs, diag = find_overlapping_pairs(_manifest([]), "OHRC", "TMC2")
    assert len(pairs) == 0
    assert diag.n_pairs_considered == 0


# --- pixel mapping and cropping --------------------------------------------


def test_geographic_to_pixel_maps_corners_to_image_corners():
    poly = box(0, 10, 0, 10, lines=1000, samples=800)
    matrix = geographic_to_pixel_transform(poly)
    pts = np.array([[lon, lat, 1.0] for lat, lon in poly.corners]) @ matrix.T
    pixels = pts[:, :2] / pts[:, 2:3]
    expected = [[0, 0], [799, 0], [799, 999], [0, 999]]
    np.testing.assert_allclose(pixels, expected, atol=1e-3)


def test_pixel_transform_needs_pixel_dimensions():
    assert geographic_to_pixel_transform(
        FootprintPolygon(corners=box(0, 10, 0, 10).corners, lines=None, samples=None)
    ) is None


def test_polygon_maps_to_a_clipped_pixel_window():
    poly = box(0, 10, 0, 10, lines=1000, samples=800)
    window = polygon_to_pixel_window(poly, ((2.5, 2.5), (2.5, 7.5), (7.5, 7.5), (7.5, 2.5)))
    row_off, col_off, height, width = window
    assert 0 <= row_off < 1000 and 0 <= col_off < 800
    assert height == pytest.approx(500, abs=3)
    assert width == pytest.approx(400, abs=3)


def test_window_is_clipped_to_the_product_bounds():
    poly = box(0, 10, 0, 10, lines=100, samples=100)
    row_off, col_off, height, width = polygon_to_pixel_window(
        poly, ((-5.0, -5.0), (-5.0, 5.0), (5.0, 5.0), (5.0, -5.0))
    )
    assert row_off >= 0 and col_off >= 0
    assert row_off + height <= 100 and col_off + width <= 100


def test_polygon_entirely_outside_the_product_gives_no_window():
    poly = box(0, 10, 0, 10, lines=100, samples=100)
    assert polygon_to_pixel_window(
        poly, ((50.0, 50.0), (50.0, 60.0), (60.0, 60.0), (60.0, 50.0))
    ) is None


def test_cropping_a_degenerate_pair_raises_rather_than_writing_garbage(tmp_path):
    result = intersect(box(0, 10, 0, 10, "a"), box(50, 60, 50, 60, "b"))
    with pytest.raises(ValueError, match="cannot crop"):
        crop_to_overlap(result, tmp_path)


def test_crop_writes_both_sides(tmp_path):
    """End-to-end crop through a real PDS4 product on disk."""
    from tests.test_ingest_labels import _pds4_label

    def make(name, lines, samples):
        (tmp_path / f"{name}.img").write_bytes(
            np.arange(lines * samples, dtype="<u2").tobytes()
        )
        (tmp_path / f"{name}.xml").write_text(
            _pds4_label(
                lid=f"urn:test:{name}", file_name=f"{name}.img",
                axes=(("Line", lines), ("Sample", samples)),
            )
        )
        return str(tmp_path / f"{name}.xml")

    src_label = make("ohrc", 400, 300)
    ref_label = make("tmc", 200, 150)

    source = FootprintPolygon(
        corners=box(0, 10, 0, 10).corners, product_id="ohrc", sensor="OHRC",
        label_path=src_label, image_path=str(tmp_path / "ohrc.img"), lines=400, samples=300,
    )
    reference = FootprintPolygon(
        corners=box(5, 15, 5, 15).corners, product_id="tmc", sensor="TMC2",
        label_path=ref_label, image_path=str(tmp_path / "tmc.img"), lines=200, samples=150,
    )

    result = intersect(source, reference)
    assert result.ok

    summary = crop_to_overlap(result, tmp_path / "out")
    import rasterio

    for side in ("source", "reference"):
        entry = summary["sides"][side]
        assert "error" not in entry, entry.get("error")
        with rasterio.open(entry["output"]) as ds:
            assert ds.height == entry["height"] and ds.width == entry["width"]
            assert ds.height > 0 and ds.width > 0


def test_crop_reports_per_side_errors_without_failing_the_pair(tmp_path):
    """A side with no pixel dimensions is reported, not silently omitted."""
    source = FootprintPolygon(
        corners=box(0, 10, 0, 10).corners, product_id="a", lines=None, samples=None
    )
    reference = FootprintPolygon(
        corners=box(5, 15, 5, 15).corners, product_id="b", lines=None, samples=None
    )
    summary = crop_to_overlap(intersect(source, reference), tmp_path)
    assert set(summary["sides"]) == {"source", "reference"}
    assert all("error" in s for s in summary["sides"].values())


# --- regressions from the first live run -----------------------------------


def test_full_coverage_window_is_the_whole_product():
    """Off-by-one guard: a polygon covering the footprint must cover every pixel."""
    poly = box(0, 10, 0, 10, lines=800, samples=600)
    row_off, col_off, height, width = polygon_to_pixel_window(poly, poly.corners)
    assert (row_off, col_off) == (0, 0)
    assert (height, width) == (800, 600)


def test_crop_filenames_encode_the_pair_not_just_the_product(tmp_path):
    """A product overlapping two partners must not overwrite its own crop.

    First observed live: ohrc_A matched two TMC frames and the smaller crop
    silently replaced the larger one at the same path.
    """
    from tests.test_ingest_labels import _pds4_label

    (tmp_path / "ohrc.img").write_bytes(np.arange(800 * 600, dtype="<u2").tobytes())
    (tmp_path / "ohrc.xml").write_text(
        _pds4_label(lid="urn:t:ohrc", file_name="ohrc.img",
                    axes=(("Line", 800), ("Sample", 600)))
    )
    source = FootprintPolygon(
        corners=box(0, 2, 0, 2).corners, product_id="ohrc_A",
        label_path=str(tmp_path / "ohrc.xml"), image_path=str(tmp_path / "ohrc.img"),
        lines=800, samples=600,
    )
    partners = [
        FootprintPolygon(corners=box(0, 2, 0, 2).corners, product_id="tmc_full",
                         lines=300, samples=200),
        FootprintPolygon(corners=box(1, 2, 1, 2).corners, product_id="tmc_quarter",
                         lines=300, samples=200),
    ]

    outputs = []
    for partner in partners:
        summary = crop_to_overlap(intersect(source, partner), tmp_path / "out")
        outputs.append(summary["sides"]["source"]["output"])

    assert outputs[0] != outputs[1], "crops for different pairs must not collide"

    import rasterio

    with rasterio.open(outputs[0]) as full, rasterio.open(outputs[1]) as quarter:
        assert (full.height, full.width) == (800, 600)
        # The quarter overlap is 400x300 geometrically, but its edge falls at
        # pixel 299.5 and the window rounds outward to keep every touched pixel.
        assert quarter.height in (400, 401)
        assert quarter.width in (300, 301)
        assert quarter.height >= 400 and quarter.width >= 300, "must never under-cover"


def test_crop_output_is_a_readable_geotiff(tmp_path):
    """Guard on the GTiff profile: PDS4 block sizes are invalid without TILED."""
    from tests.test_ingest_labels import _pds4_label

    (tmp_path / "p.img").write_bytes(np.arange(200 * 150, dtype="<u2").tobytes())
    (tmp_path / "p.xml").write_text(
        _pds4_label(lid="urn:t:p", file_name="p.img", axes=(("Line", 200), ("Sample", 150)))
    )
    fp = FootprintPolygon(
        corners=box(0, 10, 0, 10).corners, product_id="p",
        label_path=str(tmp_path / "p.xml"), image_path=str(tmp_path / "p.img"),
        lines=200, samples=150,
    )
    other = FootprintPolygon(corners=box(5, 15, 5, 15).corners, product_id="q",
                             lines=100, samples=100)
    summary = crop_to_overlap(intersect(fp, other), tmp_path / "out")
    entry = summary["sides"]["source"]
    assert "error" not in entry, entry.get("error")

    import rasterio

    with rasterio.open(entry["output"]) as ds:
        assert ds.driver == "GTiff"
        assert ds.read(1).shape == (entry["height"], entry["width"])


def test_lid_with_colons_produces_a_safe_filename(tmp_path):
    from tests.test_ingest_labels import _pds4_label

    (tmp_path / "a.img").write_bytes(np.zeros(100 * 100, dtype="<u2").tobytes())
    (tmp_path / "a.xml").write_text(
        _pds4_label(lid="urn:isro:isda:ch2_ohr:x", file_name="a.img",
                    axes=(("Line", 100), ("Sample", 100)))
    )
    fp = FootprintPolygon(
        corners=box(0, 10, 0, 10).corners, product_id="urn:isro:isda:ch2_ohr:x",
        label_path=str(tmp_path / "a.xml"), image_path=str(tmp_path / "a.img"),
        lines=100, samples=100,
    )
    other = FootprintPolygon(corners=box(2, 8, 2, 8).corners,
                             product_id="urn:nasa:pds:lro/nac:y", lines=50, samples=50)
    out = crop_to_overlap(intersect(fp, other), tmp_path / "out")["sides"]["source"]["output"]
    name = Path(out).name
    assert ":" not in name and "/" not in name


def test_window_rounds_outward_never_inward():
    """The crop window must never lose a pixel of genuine overlap."""
    poly = box(0, 2, 0, 2, lines=800, samples=600)
    # Overlap edges land mid-pixel at 299.5 / 399.5.
    row_off, col_off, height, width = polygon_to_pixel_window(
        poly, ((1.0, 1.0), (1.0, 2.0), (2.0, 2.0), (2.0, 1.0))
    )
    assert height >= 400 and width >= 300
    assert height <= 401 and width <= 301, "slop must stay within one pixel per side"
