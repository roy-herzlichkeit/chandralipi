"""Footprint geometry and overlap detection between products.

Follows the MoonMetaSync pattern: use each product's corner coordinates to find
geographically overlapping pairs *before* doing any pixel work, so the matcher
is only ever handed pairs that can actually correspond.

The one trap here is the datum. ``pygeodesy`` ships Earth ellipsoids and will
happily compute a WGS84 answer for lunar coordinates, which is wrong by a
factor of ~3.7 in ground distance. :func:`moon_datum` registers the lunar
sphere; pass its result to anything that converts degrees to metres.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from lunar_reg.constants import MOON_DATUM_NAME, MOON_FLATTENING, MOON_RADIUS_M

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def moon_datum():
    """Return (and memoise) a pygeodesy datum for the IAU mean-radius lunar sphere.

    Registered once per process; pygeodesy raises on duplicate registration, so
    the cache is load-bearing rather than a micro-optimisation.
    """
    from pygeodesy.datums import Datum, Datums, Transform
    from pygeodesy.ellipsoids import Ellipsoid

    existing = getattr(Datums, MOON_DATUM_NAME, None)
    if existing is not None:
        return existing

    ellipsoid = Ellipsoid(
        MOON_RADIUS_M,
        MOON_RADIUS_M * (1.0 - MOON_FLATTENING),
        name=MOON_DATUM_NAME,
    )
    return Datum(ellipsoid, transform=Transform(), name=MOON_DATUM_NAME)


@dataclass(frozen=True)
class Footprint:
    """Axis-aligned lat/lon extent of a product, in degrees."""

    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    product_id: str | None = None

    @classmethod
    def from_corners(cls, corners, product_id: str | None = None) -> Footprint:
        lats = [c[0] for c in corners]
        lons = [c[1] for c in corners]
        return cls(min(lats), max(lats), min(lons), max(lons), product_id)

    @property
    def area_deg2(self) -> float:
        return (self.max_lat - self.min_lat) * (self.max_lon - self.min_lon)

    def ground_extent_m(self) -> tuple[float, float]:
        """Approximate ``(north_south_m, east_west_m)`` extent on the lunar sphere."""
        from math import cos, radians

        mean_lat = radians((self.min_lat + self.max_lat) / 2.0)
        ns = radians(self.max_lat - self.min_lat) * MOON_RADIUS_M
        ew = radians(self.max_lon - self.min_lon) * MOON_RADIUS_M * cos(mean_lat)
        return ns, ew


def overlap(a: Footprint, b: Footprint) -> Footprint | None:
    """Intersect two footprints, or return ``None`` when they are disjoint.

    Note the polar caveat: OHRC's most interesting targets are near-polar, where
    longitude bounds wrap and an axis-aligned lat/lon box is a poor description
    of the true footprint. For polar pairs, reproject both footprints to a polar
    stereographic frame and intersect there instead of trusting this result.
    """
    min_lat = max(a.min_lat, b.min_lat)
    max_lat = min(a.max_lat, b.max_lat)
    min_lon = max(a.min_lon, b.min_lon)
    max_lon = min(a.max_lon, b.max_lon)
    if min_lat >= max_lat or min_lon >= max_lon:
        return None
    return Footprint(
        min_lat, max_lat, min_lon, max_lon, product_id=f"{a.product_id}^{b.product_id}"
    )


def overlap_fraction(a: Footprint, b: Footprint) -> float:
    """Fraction of ``a`` covered by ``b``, in the range ``[0, 1]``."""
    inter = overlap(a, b)
    if inter is None or a.area_deg2 == 0:
        return 0.0
    return inter.area_deg2 / a.area_deg2


def find_pairs(
    sources: list[Footprint],
    references: list[Footprint],
    min_fraction: float = 0.1,
) -> list[tuple[Footprint, Footprint, float]]:
    """All (source, reference) pairs overlapping by at least ``min_fraction``.

    Sorted by decreasing overlap so the most promising pairs are processed first.
    """
    pairs = []
    for s in sources:
        for r in references:
            frac = overlap_fraction(s, r)
            if frac >= min_fraction:
                pairs.append((s, r, frac))
    pairs.sort(key=lambda t: t[2], reverse=True)
    logger.info("found %d overlapping pairs (min_fraction=%.2f)", len(pairs), min_fraction)
    return pairs
