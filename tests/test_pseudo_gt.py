"""Tests for georeference-derived pseudo ground truth.

The load-bearing test here is :func:`test_validation_recovers_injected_error`.
Everything else checks plumbing; that one checks that the confidence machinery
reports a number that means what it claims to mean.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from lunar_reg.ingest.overlap import MOON_RADIUS_M, FootprintPolygon
from lunar_reg.ingest.pseudo_gt import (
    NOMINAL_GSD_M,
    TermSource,
    bridge_sensor,
    build_pseudo_gt,
    estimate_confidence,
    loop_closure_residual_m,
    point_in_ring,
    sample_grid_in_polygon,
    scale_ratio,
    validate_against_transform,
)

# A patch of equatorial mare, half a degree on a side.
LAT0, LAT1 = 0.0, 0.5
LON0, LON1 = 10.0, 10.5
RING = ((LAT1, LON0), (LAT1, LON1), (LAT0, LON1), (LAT0, LON0))

_M_PER_DEG_LAT = math.pi * MOON_RADIUS_M / 180.0


def _footprint(sensor: str, shift_m: float = 0.0) -> FootprintPolygon:
    """A footprint over RING, sized from the sensor's nominal GSD.

    ``shift_m`` displaces the recorded corners north by that many metres,
    standing in for a georeferencing error: the label claims the image sits
    somewhere it does not.
    """
    gsd = NOMINAL_GSD_M[sensor]
    height_m = (LAT1 - LAT0) * _M_PER_DEG_LAT
    width_m = (LON1 - LON0) * _M_PER_DEG_LAT * math.cos(math.radians((LAT0 + LAT1) / 2))
    d_lat = shift_m / _M_PER_DEG_LAT
    return FootprintPolygon(
        corners=tuple((lat + d_lat, lon) for lat, lon in RING),
        product_id=f"{sensor}_test",
        sensor=sensor,
        lines=int(height_m / gsd),
        samples=int(width_m / gsd),
    )


def test_point_in_ring():
    assert point_in_ring(0.25, 10.25, RING)
    assert not point_in_ring(0.25, 11.0, RING)
    assert not point_in_ring(-0.25, 10.25, RING)


def test_grid_is_inside_and_spaced():
    points = sample_grid_in_polygon(RING, spacing_m=2000.0)
    assert len(points) > 25
    assert all(point_in_ring(lat, lon, RING) for lat, lon in points)


def test_grid_spacing_controls_count():
    coarse = sample_grid_in_polygon(RING, spacing_m=4000.0)
    fine = sample_grid_in_polygon(RING, spacing_m=2000.0)
    # Halving the spacing quadruples the density, give or take edge effects.
    assert 3.0 < len(fine) / len(coarse) < 5.0


def test_scale_ratio_and_bridge():
    assert scale_ratio("IIRS", "OHRC") == pytest.approx(320.0)
    assert scale_ratio("TMC2", "TMC2") == pytest.approx(1.0)
    # 320x is unmatchable directly; TMC-2 splits it into 16x and 20x.
    assert bridge_sensor("IIRS", "OHRC") == "TMC2"
    # A ratio already inside the direct budget needs no bridge.
    assert bridge_sensor("OHRC", "LRO_NAC") is None


def test_confidence_refuses_a_total_while_terms_are_unknown():
    estimate = estimate_confidence("IIRS", "OHRC")
    assert estimate.total_sigma_m is None
    assert estimate.unknown_terms
    # The floor is still reported, and is the quantisation terms alone.
    expected = math.hypot(80.0 / math.sqrt(12), 0.25 / math.sqrt(12))
    assert estimate.lower_bound_sigma_m == pytest.approx(expected)
    assert "NOT ESTABLISHED" in estimate.report()


def test_confidence_totals_once_the_residual_is_measured():
    estimate = estimate_confidence("IIRS", "OHRC", measured_residual_m=120.0,
                                   n_validation_pairs=7)
    assert not estimate.unknown_terms
    assert estimate.total_sigma_m == pytest.approx(
        math.sqrt((80 / math.sqrt(12)) ** 2 + (0.25 / math.sqrt(12)) ** 2 + 120.0**2)
    )
    assert any(t.source is TermSource.MEASURED for t in estimate.terms)


def test_build_pseudo_gt_pairs_every_sample():
    source, reference = _footprint("IIRS"), _footprint("TMC2")
    gt = build_pseudo_gt(source, reference, RING, spacing_m=1500.0)
    assert gt is not None
    assert len(gt) == len(gt.latlon) > 20
    assert gt.src_pts.shape == gt.dst_pts.shape
    assert gt.scale_ratio == pytest.approx(16.0)
    # Every projected point lands inside its product.
    assert gt.src_pts[:, 0].min() >= 0 and gt.src_pts[:, 0].max() <= source.samples - 1
    assert gt.dst_pts[:, 1].min() >= 0 and gt.dst_pts[:, 1].max() <= reference.lines - 1


def test_match_result_marks_the_sigma_as_a_lower_bound():
    gt = build_pseudo_gt(_footprint("IIRS"), _footprint("TMC2"), RING, spacing_m=1500.0)
    result = gt.to_match_result()
    assert result.matcher.startswith("pseudo-gt")
    assert result.meta["sigma_m"] is None
    assert result.meta["sigma_is_lower_bound"] is True
    assert result.meta["unknown_terms"]


def _true_homography(source: FootprintPolygon, reference: FootprintPolygon):
    """Source-pixel -> reference-pixel map for two footprints over the same ground.

    Both cover RING, so the mapping is the pure scale a matcher would recover
    from the imagery, with no georeferencing involved.
    """
    sx = (reference.samples - 1) / (source.samples - 1)
    sy = (reference.lines - 1) / (source.lines - 1)
    return np.array([[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]])


def test_validation_is_near_zero_when_georeferencing_is_perfect():
    source, reference = _footprint("IIRS"), _footprint("TMC2")
    gt = build_pseudo_gt(source, reference, RING, spacing_m=1500.0)
    result = validate_against_transform(
        gt, _true_homography(source, reference), reference_gsd_m=NOMINAL_GSD_M["TMC2"]
    )
    # Sub-pixel at TMC-2 scale: the only residual is integer truncation of the
    # products' pixel dimensions.
    assert result.rmse_px < 1.0


@pytest.mark.parametrize("injected_m", [50.0, 200.0, 800.0])
def test_validation_recovers_injected_error(injected_m):
    """The measured residual must equal the georeferencing error that caused it.

    This is what licenses quoting the validation number as the accuracy of the
    pseudo ground truth. A displaced source label puts every correspondence off
    by that displacement; if the measurement did not recover it, the confidence
    figure would be decorative.
    """
    reference = _footprint("TMC2")
    truth = _footprint("IIRS")
    displaced = _footprint("IIRS", shift_m=injected_m)

    gt = build_pseudo_gt(displaced, reference, RING, spacing_m=1500.0)
    result = validate_against_transform(
        gt, _true_homography(truth, reference), reference_gsd_m=NOMINAL_GSD_M["TMC2"]
    )
    assert result.rmse_m == pytest.approx(injected_m, rel=0.05)


def test_loop_closure_is_tautologically_zero():
    """Documents the trap: this check cannot detect a georeferencing error.

    Both footprints are displaced by 5 km and the round trip still closes, which
    is exactly why loop closure must never be reported as a confidence measure.
    """
    footprints = [_footprint("IIRS", shift_m=5000.0), _footprint("TMC2", shift_m=5000.0)]
    assert loop_closure_residual_m(footprints, RING, spacing_m=2000.0) < 1.0
