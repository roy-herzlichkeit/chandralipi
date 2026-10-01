"""Footprint overlap gates which pairs are worth matching at all."""

from __future__ import annotations

import pytest

from lunar_reg.constants import MOON_RADIUS_M, SENSORS
from lunar_reg.ingest.footprint import Footprint, find_pairs, overlap, overlap_fraction

A = Footprint(-10.0, 10.0, -10.0, 10.0, "A")
B = Footprint(0.0, 20.0, 0.0, 20.0, "B")
FAR = Footprint(60.0, 70.0, 60.0, 70.0, "FAR")


def test_overlapping_footprints_intersect():
    inter = overlap(A, B)
    assert inter is not None
    assert (inter.min_lat, inter.max_lat) == (0.0, 10.0)


def test_disjoint_footprints_return_none():
    assert overlap(A, FAR) is None


def test_overlap_fraction_is_a_quarter_here():
    assert overlap_fraction(A, B) == pytest.approx(0.25)


def test_find_pairs_sorts_by_decreasing_overlap():
    near = Footprint(-9.0, 9.0, -9.0, 9.0, "NEAR")
    pairs = find_pairs([A], [near, B, FAR], min_fraction=0.1)
    assert [p[1].product_id for p in pairs] == ["NEAR", "B"]


def test_find_pairs_applies_the_threshold():
    assert find_pairs([A], [FAR], min_fraction=0.1) == []


def test_ground_extent_uses_the_lunar_radius_not_earths():
    """The datum trap: a WGS84 answer here would be ~3.7x too large."""
    ns, _ = Footprint(0.0, 1.0, 0.0, 1.0).ground_extent_m()
    expected = MOON_RADIUS_M * 3.141592653589793 / 180.0
    assert ns == pytest.approx(expected, rel=1e-6)
    assert ns < 31_000  # one degree of latitude on Earth is ~111 km


def test_iirs_is_the_only_hyperspectral_sensor():
    assert [k for k, v in SENSORS.items() if v.bands > 1] == ["IIRS"]
