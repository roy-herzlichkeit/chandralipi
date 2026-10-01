"""Footprint-overlap detection between manifests, and cropping to the shared region.

Follows the MoonMetaSync pattern: match products by corner coordinates on the
lunar sphere *before* any pixel work, so the matcher only ever sees pairs that
can actually correspond. Polygon clipping is done with pygeodesy's
Foster-Hormann-Popa clipper, driven with the lunar radius rather than an Earth
ellipsoid.

Nothing here silently drops a pair. Every rejection is classified into a
:class:`OverlapStatus`, counted, and given a retained sample -- see
:class:`OverlapDiagnostics`. A pair that produces a degenerate or empty polygon
is a *reported outcome*, not a skipped row.

Polar footprints
----------------
A lat/lon polygon degenerates at the pole: meridians converge, so a constant
distance east-west spans an unbounded longitude range, and a straight edge in
lat/lon is not a straight edge on the ground. Clipping there in lat/lon is
wrong, and OHRC's real products are polar -- every one downloaded so far sits at
about -85 degrees.

So a pair involving a polar footprint is clipped in a :class:`PolarFrame`
instead: an azimuthal-equidistant plane centred on the relevant pole, where the
pole is an ordinary interior point and longitude wrap does not exist. The
clipped ring is projected back to lat/lon and its area is still measured with
spherical trigonometry on the sphere, so the projection only ever decides
*which region* is shared, never how large it is.

The frame is measured in **degrees of arc** rather than metres, so that vertex
coordinates keep the same numeric magnitude as the lat/lon path and the
clipper's null-edge tolerance means the same thing in both.

Three library traps this module works around
--------------------------------------------
1. ``sphericalNvector.areaOf`` returns badly wrong values for a **closed** ring
   (first point repeated at the end) -- measured 53x too large for a 10-degree
   box and 51,567x too large for a thin sliver, with the error growing as the
   polygon shrinks. ``clipFHP4`` returns exactly such closed rings, so the
   obvious composition is silently wrong and makes slivers look enormous. This
   module strips the closing duplicate **and** uses
   ``sphericalTrigonometry.areaOf``, which is correct either way.
   Pinned by ``test_area_is_correct_for_closed_rings``.
2. ``ST.LatLon`` raises ``RangeError`` for a longitude outside +/-180, which
   this module used to convert into an area of exactly 0 m^2 -- silently, for a
   footprint whose only sin was using the 0..360 east-longitude convention a
   PDS label is entitled to. :func:`_wrap_lon` folds the range first.
   Pinned by ``test_area_is_correct_for_longitudes_beyond_180``.
3. ``clipFHP4`` returns an empty sequence -- not an exception -- for disjoint,
   edge-touching and corner-touching polygons alike. Those are distinguished
   here by an explicit adjacency check so "no overlap" and "touching only" are
   not conflated.

Trust boundary
--------------
This module consumes the ``min_lat``/``max_lat``/``min_lon``/``max_lon`` and
``cornerN_lat``/``cornerN_lon`` columns of a manifest. The eight corner fields
have since been confirmed against a real OHRC label (see
:mod:`lunar_reg.ingest.fieldmap`), so a row carrying them describes the real
rotated strip. **A manifest built by :mod:`lunar_reg.ingest.manifest` does not
carry those columns** -- only the bounding box derived from them -- so
:func:`footprint_from_row` falls back to the box, which near a pole is several
times the true footprint. That is an upper bound, not an error, but it is not
the 79 km^2 an OHRC strip actually covers; pass corner columns through if the
area matters.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from lunar_reg.constants import MOON_RADIUS_M

logger = logging.getLogger(__name__)

#: Latitude beyond which an axis-aligned lat/lon polygon stops describing a
#: footprint usefully -- meridians converge and longitude bounds lose meaning.
#: Above it a pair is clipped in a :class:`PolarFrame` rather than in lat/lon.
#: Below it meridian convergence over an OHRC- or TMC-2-sized footprint is a
#: fraction of a percent, so the cheaper lat/lon clip is kept.
POLAR_LATITUDE_DEG: float = 80.0

#: How far from its pole a polar pair may reach before the polar frame stops
#: being trustworthy, as an angular distance (90 - |lat| for the pole in use).
#: Straight edges in an azimuthal-equidistant plane are not great circles, and
#: the plane's transverse scale error is theta/sin(theta) -- 0.05% at 10 deg,
#: 1.2% at 30 deg, 4.7% at 60 deg. A partner reaching further than this is
#: reported as :attr:`OverlapStatus.POLAR_EXTENT_UNSUPPORTED` rather than
#: clipped with an error nobody has quantified. 60 deg is ~1800 km from the
#: pole, far beyond any real OHRC or TMC-2 footprint, so it should never fire
#: on a genuine polar pair.
POLAR_CLIP_MAX_COLATITUDE_DEG: float = 60.0

#: A longitude span wider than this implies the footprint wraps the antimeridian
#: (or that corner ordering is wrong). Either way the polygon is not trustworthy.
#: Applies only away from the poles: see :meth:`FootprintPolygon.validate`.
ANTIMERIDIAN_SPAN_DEG: float = 180.0

#: Overlap polygons below this area are treated as degenerate slivers rather
#: than usable regions. 1 km^2 is far below any useful OHRC/TMC-2 overlap.
MIN_OVERLAP_AREA_M2: float = 1.0e6

#: Aspect ratio beyond which an overlap is a sliver even if its area passes.
MAX_OVERLAP_ASPECT: float = 200.0


class OverlapStatus(str, Enum):
    """Why a candidate pair did or did not yield a usable overlap."""

    OK = "ok"
    #: Footprint columns did not resolve for this row -- a metadata gap, not a
    #: geometry failure. The corner fields themselves are verified against a
    #: real OHRC label, so this now points at the row, not at the field map.
    MISSING_FOOTPRINT = "missing_footprint"
    #: Clean non-overlap. Not an error.
    DISJOINT = "disjoint"
    #: Polygons touch at an edge or corner but enclose no area.
    TOUCHING_ONLY = "touching_only"
    #: Clipper returned fewer than three distinct points.
    DEGENERATE_EMPTY = "degenerate_empty"
    #: Non-zero but negligible area, or an extreme aspect ratio.
    DEGENERATE_SLIVER = "degenerate_sliver"
    #: Footprint crosses or appears to cross the antimeridian.
    ANTIMERIDIAN = "antimeridian"
    #: RETIRED, and never produced any more: polar footprints used to be
    #: rejected outright, which threw away 100% of the real OHRC archive. They
    #: are now clipped in a :class:`PolarFrame`. The member is kept so that
    #: result tables written before that change still parse through
    #: ``OverlapStatus(value)`` instead of raising.
    POLAR = "polar"
    #: A pair involving a polar footprint reaches further from that pole than
    #: :data:`POLAR_CLIP_MAX_COLATITUDE_DEG`, so the polar frame's straight-edge
    #: and scale assumptions no longer hold. Distinct from ``POLAR``: this is a
    #: pair that was routed to the polar path and could not be handled there,
    #: not a footprint refused for being polar at all.
    POLAR_EXTENT_UNSUPPORTED = "polar_extent_unsupported"
    #: The footprint is a lat/lon bounding box, it is polar, and its longitudes
    #: wrap -- so the box describes a cap most of the way round the pole rather
    #: than the product. The fix is corner columns, not a wider tolerance.
    POLAR_BBOX_UNUSABLE = "polar_bbox_unusable"
    #: A corner value was non-finite or out of range.
    INVALID_GEOMETRY = "invalid_geometry"
    #: The clipping library raised.
    CLIP_ERROR = "clip_error"

    @property
    def is_failure(self) -> bool:
        return self is not OverlapStatus.OK

    @property
    def is_suspicious(self) -> bool:
        """Whether this outcome suggests a bug or bad data, rather than honest non-overlap.

        ``DISJOINT`` is a normal result for most pairs; the rest warrant a look.
        """
        return self not in (OverlapStatus.OK, OverlapStatus.DISJOINT)


#: Metres per degree of arc on the lunar sphere. The polar frame's unit.
_M_PER_ARC_DEG: float = MOON_RADIUS_M * math.pi / 180.0


@lru_cache(maxsize=2)
def _equidistant(pole_lat: float):
    """Memoised pygeodesy azimuthal-equidistant projection centred on a pole.

    ``datum`` is not optional: pygeodesy defaults to WGS84 and would silently
    return Earth-sized eastings for lunar coordinates.
    """
    from pygeodesy.azimuthal import Equidistant

    from lunar_reg.constants import moon_datum

    return Equidistant(pole_lat, 0.0, datum=moon_datum())


@dataclass(frozen=True)
class PolarFrame:
    """An azimuthal-equidistant plane centred on one pole, in degrees of arc.

    Exists because clipping in lat/lon is wrong near a pole. In this frame the
    pole is an ordinary point, meridians do not converge, and a footprint that
    spans 300 degrees of longitude is an unremarkable small quadrilateral.

    Coordinates are ``(northing, easting)`` to match the ``(lat, lon)`` ordering
    the rest of this module uses, and are scaled to **degrees of arc** rather
    than metres: pygeodesy's clipper takes its null-edge tolerance in the same
    units as its input, so keeping polar and lat/lon coordinates at the same
    magnitude keeps that tolerance meaning the same thing on both paths.

    Equidistant rather than stereographic because radial distance from the pole
    is then exact, which makes the projected extents used for the sliver check
    true ground distances. Both are conformal enough over an OHRC footprint for
    the choice not to matter to the clip itself; areas are never taken from this
    plane, only from the sphere.
    """

    #: ``+90.0`` or ``-90.0``.
    pole_lat: float

    def to_plane(self, lat: float, lon: float) -> tuple[float, float]:
        # _wrap_lon for the same reason as in polygon_area_m2: pygeodesy's
        # Lon_ rejects anything outside +/-180, and a polar footprint is
        # exactly where a 0..360 longitude is likely to turn up.
        p = _equidistant(self.pole_lat).forward(lat, _wrap_lon(lon))
        return (p.y / _M_PER_ARC_DEG, p.x / _M_PER_ARC_DEG)

    def to_sphere(self, northing: float, easting: float) -> tuple[float, float]:
        p = _equidistant(self.pole_lat).reverse(
            easting * _M_PER_ARC_DEG, northing * _M_PER_ARC_DEG
        )
        return (float(p.lat), float(p.lon))

    def plane_ring(self, ring) -> tuple[tuple[float, float], ...]:
        return tuple(self.to_plane(lat, lon) for lat, lon in ring)

    def sphere_ring(self, ring) -> tuple[tuple[float, float], ...]:
        return tuple(self.to_sphere(n, e) for n, e in ring)

    def colatitude_deg(self, lat: float) -> float:
        """Angular distance of a latitude from this frame's pole, in degrees."""
        return abs(self.pole_lat - lat)


@dataclass(frozen=True)
class FootprintPolygon:
    """A product's ground footprint as a lat/lon ring, plus its pixel size."""

    corners: tuple[tuple[float, float], ...]  # ((lat, lon), ...) in ring order
    product_id: str | None = None
    sensor: str | None = None
    label_path: str | None = None
    image_path: str | None = None
    lines: int | None = None
    samples: int | None = None
    #: True when the corners are a lat/lon bounding box rather than the
    #: product's real corners. Near a pole the difference is not cosmetic, so
    #: :meth:`validate` needs to know which it is holding.
    bbox_derived: bool = False

    @property
    def lats(self) -> tuple[float, ...]:
        return tuple(c[0] for c in self.corners)

    @property
    def lons(self) -> tuple[float, ...]:
        return tuple(c[1] for c in self.corners)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """``(min_lat, max_lat, min_lon, max_lon)``."""
        return (min(self.lats), max(self.lats), min(self.lons), max(self.lons))

    @property
    def is_polar(self) -> bool:
        return max(abs(v) for v in self.lats) >= POLAR_LATITUDE_DEG

    @property
    def crosses_antimeridian(self) -> bool:
        return (max(self.lons) - min(self.lons)) > ANTIMERIDIAN_SPAN_DEG

    def validate(self) -> OverlapStatus:
        """Classify this footprint before it is used in any clipping.

        A polar footprint is *valid*: :func:`intersect` routes it through a
        :class:`PolarFrame`. The antimeridian guard is deliberately not applied
        to one, because a wide longitude span near a pole is the normal case
        rather than evidence of a wrap -- a 3 km-wide strip passing within a
        degree of the pole sweeps most of the longitude circle legitimately, and
        the polar frame does not care where the antimeridian is. The cost is
        that a polar footprint with mis-ordered corners is no longer caught
        here; it shows up downstream as a degenerate or implausible area.

        The exception is a footprint that is only a *bounding box*. A wrapping
        box near a pole is not a wide footprint, it is a cap wrapped most of the
        way round the pole -- which is what a strip passing over the pole
        reduces to, since its corners land on both sides of the antimeridian.
        Clipping that would produce a confident answer for a region hundreds of
        times too large, so it gets its own status instead.
        """
        if len(self.corners) < 3:
            return OverlapStatus.INVALID_GEOMETRY
        for lat, lon in self.corners:
            if not (math.isfinite(lat) and math.isfinite(lon)):
                return OverlapStatus.INVALID_GEOMETRY
            if not (-90.0 <= lat <= 90.0) or not (-360.0 <= lon <= 360.0):
                return OverlapStatus.INVALID_GEOMETRY
        if self.crosses_antimeridian:
            if not self.is_polar:
                return OverlapStatus.ANTIMERIDIAN
            if self.bbox_derived:
                return OverlapStatus.POLAR_BBOX_UNUSABLE
        return OverlapStatus.OK

    def area_m2(self) -> float:
        return polygon_area_m2(self.corners)


def _strip_closing_duplicate(
    ring: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    """Drop a repeated first/last vertex.

    Load-bearing: see this module's docstring on ``areaOf`` and closed rings.
    """
    if len(ring) > 1 and ring[0] == ring[-1]:
        return ring[:-1]
    return ring


def _wrap_lon(lon: float) -> float:
    """Fold a longitude into ``[-180, 180)``.

    Load-bearing, and a third library trap: ``ST.LatLon`` raises ``RangeError``
    for a longitude outside +/-180, which :func:`polygon_area_m2` used to turn
    into an area of exactly 0. PDS labels are entitled to express east longitude
    as 0..360 -- :meth:`FootprintPolygon.validate` accepts that range -- so a
    perfectly good footprint could silently measure zero. Polar clipping makes
    that far more likely, because a footprint near the pole sweeps longitude
    freely.
    """
    return (lon + 180.0) % 360.0 - 180.0


def polygon_area_m2(ring, radius: float = MOON_RADIUS_M) -> float:
    """Spherical area of a lat/lon ring on the Moon, in square metres.

    Uses ``sphericalTrigonometry.areaOf``, which -- unlike the n-vector
    implementation -- is correct for both open and closed rings. The closing
    duplicate is stripped anyway so the input form cannot matter.

    Correct for a ring that encircles a pole or crosses the antimeridian: edges
    are great circles, so no lat/lon assumption is made about the interior.
    Verified against the analytic polar-cap area 2*pi*R^2*(1 - cos(colatitude)).
    """
    from pygeodesy import sphericalTrigonometry as ST

    ring = _strip_closing_duplicate(tuple(ring))
    if len(ring) < 3:
        return 0.0
    try:
        return float(
            ST.areaOf(
                [ST.LatLon(lat, _wrap_lon(lon)) for lat, lon in ring], radius=radius
            )
        )
    except Exception as exc:  # noqa: BLE001 - degenerate rings are reported, not raised
        # Not expected once longitudes are wrapped, so this is louder than the
        # debug line it used to be: a zero area here is indistinguishable
        # downstream from a genuinely empty overlap.
        logger.warning(
            "areaOf failed on a %d-point ring, reporting 0 m^2: %s", len(ring), exc
        )
        return 0.0


def _ring_extent_m(ring) -> tuple[float, float]:
    """Approximate ``(north_south_m, east_west_m)`` extent of a lat/lon ring."""
    ring = _strip_closing_duplicate(tuple(ring))
    if not ring:
        return (0.0, 0.0)
    lats = [c[0] for c in ring]
    lons = [c[1] for c in ring]
    mean_lat = math.radians(sum(lats) / len(lats))
    ns = math.radians(max(lats) - min(lats)) * MOON_RADIUS_M
    ew = math.radians(max(lons) - min(lons)) * MOON_RADIUS_M * math.cos(mean_lat)
    return (ns, ew)


def _plane_extent_m(ring) -> tuple[float, float]:
    """Ground extent of a ring already in :class:`PolarFrame` coordinates.

    Axis-aligned to the frame, which is oriented by the prime meridian rather
    than by the ring, so this is a bounding-box proxy exactly as the lat/lon
    version is -- but a proxy in true ground metres, which the lat/lon one stops
    being near a pole.
    """
    ring = _strip_closing_duplicate(tuple(ring))
    if not ring:
        return (0.0, 0.0)
    northings = [c[0] for c in ring]
    eastings = [c[1] for c in ring]
    return (
        (max(northings) - min(northings)) * _M_PER_ARC_DEG,
        (max(eastings) - min(eastings)) * _M_PER_ARC_DEG,
    )


@dataclass
class OverlapResult:
    """The outcome of intersecting two footprints. Never raises; always classified."""

    source: FootprintPolygon
    reference: FootprintPolygon
    status: OverlapStatus
    polygon: tuple[tuple[float, float], ...] = ()
    area_m2: float = 0.0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is OverlapStatus.OK

    @property
    def source_fraction(self) -> float:
        a = self.source.area_m2()
        return self.area_m2 / a if a > 0 else 0.0

    @property
    def reference_fraction(self) -> float:
        a = self.reference.area_m2()
        return self.area_m2 / a if a > 0 else 0.0

    @property
    def bounds(self) -> tuple[float, float, float, float] | None:
        if not self.polygon:
            return None
        lats = [c[0] for c in self.polygon]
        lons = [c[1] for c in self.polygon]
        return (min(lats), max(lats), min(lons), max(lons))

    def as_row(self) -> dict:
        b = self.bounds
        return {
            "source_id": self.source.product_id,
            "source_sensor": self.source.sensor,
            "source_image": self.source.image_path,
            "reference_id": self.reference.product_id,
            "reference_sensor": self.reference.sensor,
            "reference_image": self.reference.image_path,
            "status": self.status.value,
            "overlap_area_m2": self.area_m2,
            "overlap_area_km2": self.area_m2 / 1e6,
            "source_fraction": self.source_fraction,
            "reference_fraction": self.reference_fraction,
            "overlap_min_lat": b[0] if b else None,
            "overlap_max_lat": b[1] if b else None,
            "overlap_min_lon": b[2] if b else None,
            "overlap_max_lon": b[3] if b else None,
            "n_polygon_vertices": len(_strip_closing_duplicate(self.polygon)),
            "polygon_wkt": polygon_to_wkt(self.polygon),
            "detail": self.detail,
        }


def polygon_to_wkt(ring) -> str | None:
    """Serialise a lat/lon ring as WKT ``POLYGON`` in ``(lon lat)`` axis order.

    Longitude first, matching the OGC convention, so the value drops straight
    into QGIS or shapely without a coordinate flip.
    """
    ring = _strip_closing_duplicate(tuple(ring))
    if len(ring) < 3:
        return None
    closed = [*ring, ring[0]]
    coords = ", ".join(f"{lon:.9f} {lat:.9f}" for lat, lon in closed)
    return f"POLYGON(({coords}))"


def _ring_bounds(ring) -> tuple[float, float, float, float]:
    """``(min_a, max_a, min_b, max_b)`` of a ring of ``(a, b)`` pairs."""
    return (
        min(c[0] for c in ring), max(c[0] for c in ring),
        min(c[1] for c in ring), max(c[1] for c in ring),
    )


def _touching(a_ring, b_ring, eps: float = 1e-9) -> bool:
    """Whether two rings' bounding boxes abut without enclosing area.

    Takes rings rather than footprints so that a polar pair can be tested in its
    :class:`PolarFrame`, where a shared *longitude* edge means nothing: near a
    pole two footprints can share a meridian and still be far apart on the
    ground. Both coordinate systems are in degrees, so ``eps`` carries over.
    """
    a_min_a, a_max_a, a_min_b, a_max_b = _ring_bounds(a_ring)
    b_min_a, b_max_a, b_min_b, b_max_b = _ring_bounds(b_ring)
    gap_a = max(a_min_a, b_min_a) - min(a_max_a, b_max_a)
    gap_b = max(a_min_b, b_min_b) - min(a_max_b, b_max_b)
    return abs(gap_a) <= eps or abs(gap_b) <= eps


def _unit(lat: float, lon: float) -> tuple[float, float, float]:
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def _bounding_cap(ring) -> tuple[tuple[float, float, float], float]:
    """Smallest-ish spherical cap covering a ring: ``(centre_unit_vector, radius_deg)``.

    Not the minimal cap -- the centre is the normalised vertex mean, which is
    cheap and always valid, just occasionally a little wide. Wide is the safe
    direction here: this is only ever used to *prove* two footprints cannot
    meet, so an over-large cap costs a missed shortcut, never a wrong answer.
    """
    vs = [_unit(lat, lon) for lat, lon in ring]
    cx = sum(v[0] for v in vs)
    cy = sum(v[1] for v in vs)
    cz = sum(v[2] for v in vs)
    norm = math.sqrt(cx * cx + cy * cy + cz * cz)
    if norm <= 0.0:
        # Vertices cancel out (antipodal spread); no cap smaller than the sphere.
        return ((0.0, 0.0, 1.0), 180.0)
    centre = (cx / norm, cy / norm, cz / norm)
    return (centre, max(_angle_deg(centre, v) for v in vs))


def _angle_deg(u, v) -> float:
    """Angle between two unit vectors, in degrees."""
    dot = sum(a * b for a, b in zip(u, v, strict=True))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


def _cap_separation_deg(ring_a, ring_b) -> float:
    """Angular gap between two rings' bounding caps; positive means disjoint.

    A cap of radius below 90 degrees is convex, so every great-circle edge --
    and hence the whole footprint -- stays inside its own cap. Two caps that do
    not touch therefore contain footprints that cannot overlap, whatever the
    longitude bookkeeping says.
    """
    (ca, ra), (cb, rb) = _bounding_cap(ring_a), _bounding_cap(ring_b)
    return _angle_deg(ca, cb) - (ra + rb)


def _polar_frame_for(
    source: FootprintPolygon, reference: FootprintPolygon
) -> tuple[PolarFrame | None, OverlapStatus, str]:
    """Choose the polar frame for a pair, or say why the pair has none.

    Returns ``(frame, status, detail)``; ``frame`` is ``None`` unless ``status``
    is :attr:`OverlapStatus.OK`, and the status then explains the outcome the
    caller should report.

    Two footprints can only be handled in one polar frame, so the pair -- not
    each footprint -- decides the pole.

    Pairs that cannot possibly overlap are settled first, with a bounding-cap
    test that needs no projection. That matters for honesty rather than for
    speed: a polar OHRC strip against an equatorial TMC-2 frame -- exactly what
    the current download contains -- is a plain non-overlap, and must be
    reported ``DISJOINT`` rather than as a polar failure that reads like a bug.

    The obvious version of that test, comparing latitude ranges, is **wrong**
    near a pole and was tried first. A polygon's interior is not confined to its
    vertices' latitude band once the pole is involved: a strip passing directly
    over the pole has every vertex below 89 degrees and still covers 90, and a
    ring at constant colatitude has a one-point latitude band while enclosing a
    whole cap. Bounding caps have no such blind spot.
    """
    gap = _cap_separation_deg(source.corners, reference.corners)
    if gap > 0.0:
        return (
            None, OverlapStatus.DISJOINT,
            f"bounding caps are {gap:.3f} deg apart on the sphere",
        )

    # The pole is set by whichever vertex of the pair lies furthest north or
    # south; anything sitting near the *other* pole is then out of range below.
    extreme = max((*source.lats, *reference.lats), key=abs)
    frame = PolarFrame(90.0 if extreme >= 0.0 else -90.0)

    for name, poly in (("source", source), ("reference", reference)):
        colat = max(frame.colatitude_deg(lat) for lat in poly.lats)
        if colat > POLAR_CLIP_MAX_COLATITUDE_DEG:
            return (
                None, OverlapStatus.POLAR_EXTENT_UNSUPPORTED,
                f"{name} footprint {poly.product_id!r} reaches {colat:.1f} deg from "
                f"the {'north' if frame.pole_lat > 0 else 'south'} pole, beyond the "
                f"{POLAR_CLIP_MAX_COLATITUDE_DEG:.0f} deg the polar frame is trusted to",
            )
    return frame, OverlapStatus.OK, ""


def intersect(source: FootprintPolygon, reference: FootprintPolygon) -> OverlapResult:
    """Clip two footprints and classify the result.

    Near a pole the clip happens in a :class:`PolarFrame` rather than in
    lat/lon; the returned polygon is lat/lon either way, and its area is always
    measured on the sphere, so nothing downstream needs to know which path ran.

    Never raises. Degenerate outcomes come back as a status, so the caller can
    count them rather than discovering a silent gap later.
    """
    for name, poly in (("source", source), ("reference", reference)):
        status = poly.validate()
        if status is not OverlapStatus.OK:
            return OverlapResult(
                source, reference, status,
                detail=f"{name} footprint {poly.product_id!r}: {status.value}",
            )

    frame: PolarFrame | None = None
    if source.is_polar or reference.is_polar:
        frame, status, detail = _polar_frame_for(source, reference)
        if frame is None:
            return OverlapResult(source, reference, status, detail=detail)

    # The projection is inside the try for the same reason the clip is: this
    # function's contract is that it classifies rather than raises, and
    # pygeodesy raises on out-of-range coordinates.
    try:
        # The clipper is purely planar -- it never interprets its input as
        # spherical -- so feeding it frame coordinates in (northing, easting) is
        # the same operation it already performs on (lat, lon), in a plane that
        # behaves.
        source_ring = frame.plane_ring(source.corners) if frame else source.corners
        reference_ring = (
            frame.plane_ring(reference.corners) if frame else reference.corners
        )

        from pygeodesy.clipy import LatLon_, clipFHP4

        clipped = list(
            clipFHP4(
                [LatLon_(a, b) for a, b in source_ring],
                [LatLon_(a, b) for a, b in reference_ring],
                closed=True,
            )
        )
        clipped_ring = _strip_closing_duplicate(tuple((p.lat, p.lon) for p in clipped))
        ring = frame.sphere_ring(clipped_ring) if frame else clipped_ring
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        return OverlapResult(
            source, reference, OverlapStatus.CLIP_ERROR,
            detail=f"{type(exc).__name__}: {exc}",
        )

    if not clipped:
        # clipFHP4 gives an empty result for disjoint AND merely-touching
        # polygons; separate them so "touching" is not miscounted as "disjoint".
        status = (
            OverlapStatus.TOUCHING_ONLY
            if _touching(source_ring, reference_ring)
            else OverlapStatus.DISJOINT
        )
        return OverlapResult(source, reference, status, detail="clipper returned no vertices")

    if len(ring) < 3:
        return OverlapResult(
            source, reference, OverlapStatus.DEGENERATE_EMPTY,
            polygon=ring,
            detail=f"clipper returned {len(ring)} distinct vertices, need >= 3",
        )

    # Area always comes from the sphere, never from the plane: the projection
    # decides which region is shared, not how large it is.
    area = polygon_area_m2(ring)
    ns, ew = _plane_extent_m(clipped_ring) if frame else _ring_extent_m(ring)
    aspect = max(ns, ew) / min(ns, ew) if min(ns, ew) > 0 else float("inf")

    if area < MIN_OVERLAP_AREA_M2 or aspect > MAX_OVERLAP_ASPECT:
        return OverlapResult(
            source, reference, OverlapStatus.DEGENERATE_SLIVER,
            polygon=ring, area_m2=area,
            detail=f"area={area:.1f} m^2, aspect={aspect:.1f} "
                   f"(limits: area>={MIN_OVERLAP_AREA_M2:.0f}, aspect<={MAX_OVERLAP_ASPECT:.0f})",
        )

    return OverlapResult(source, reference, OverlapStatus.OK, polygon=ring, area_m2=area)


# ---------------------------------------------------------------------------
# Manifest integration
# ---------------------------------------------------------------------------

_CORNER_COLUMNS = tuple(f"corner{i}_{c}" for i in range(1, 5) for c in ("lat", "lon"))


def footprint_from_row(row: Any) -> FootprintPolygon | None:
    """Build a footprint from a manifest row, or ``None`` if it has no usable geometry.

    Prefers the four explicit corners in ring order. Falls back to the
    ``min_lat``/``max_lat``/``min_lon``/``max_lon`` bounding box, which loses any
    rotation of the real footprint -- a pushbroom strip at an angle becomes a
    larger axis-aligned box, so overlap area from the fallback is an upper bound.
    """
    def value(key):
        try:
            v = row[key]
        except (KeyError, IndexError, TypeError):
            return None
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    def text(key):
        """Row value as a plain str/int, normalising pandas NaN to None."""
        v = row.get(key)
        if v is None:
            return None
        # pandas fills absent values with NaN, which is not None but is falsy-ish.
        return None if isinstance(v, float) and math.isnan(v) else v

    def count(key):
        v = value(key)
        return int(v) if v is not None else None

    meta = {
        "product_id": text("product_id"),
        "sensor": text("sensor"),
        "label_path": text("label_path"),
        "image_path": text("image_path"),
        "lines": count("lines"),
        "samples": count("samples"),
    }

    corners = [(value(f"corner{i}_lat"), value(f"corner{i}_lon")) for i in range(1, 5)]
    if all(lat is not None and lon is not None for lat, lon in corners):
        # Ring order: corner1..4 are upper-left, upper-right, lower-left,
        # lower-right in the field map, so traverse 1,2,4,3 to avoid a bow-tie.
        # Corner naming VERIFIED against a real OHRC label (fieldmap.py):
        # corner3 really is lower-LEFT, so 1,2,3,4 would be a bow-tie.
        ordered = (corners[0], corners[1], corners[3], corners[2])
        return FootprintPolygon(corners=tuple(ordered), **meta)

    min_lat, max_lat = value("min_lat"), value("max_lat")
    min_lon, max_lon = value("min_lon"), value("max_lon")
    if None in (min_lat, max_lat, min_lon, max_lon):
        return None
    if max_lat <= min_lat or max_lon <= min_lon:
        return None
    return FootprintPolygon(
        corners=(
            (min_lat, min_lon), (min_lat, max_lon),
            (max_lat, max_lon), (max_lat, min_lon),
        ),
        bbox_derived=True,
        **meta,
    )


@dataclass
class OverlapDiagnostics:
    """Counts and retained samples for every outcome.

    Exists because a silently-skipped pair is indistinguishable from a pair that
    genuinely does not overlap. :meth:`report` is meant to be printed on every
    run, not only on failure.
    """

    counts: Counter = field(default_factory=Counter)
    samples: dict[str, str] = field(default_factory=dict)
    n_source: int = 0
    n_reference: int = 0
    n_pairs_considered: int = 0
    n_source_without_footprint: int = 0
    n_reference_without_footprint: int = 0

    def record(self, result: OverlapResult) -> None:
        key = result.status.value
        self.counts[key] += 1
        if key not in self.samples:
            self.samples[key] = (
                f"{result.source.product_id} x {result.reference.product_id}"
                + (f" -- {result.detail}" if result.detail else "")
            )

    def record_missing(self, status: OverlapStatus, detail: str) -> None:
        self.counts[status.value] += 1
        self.samples.setdefault(status.value, detail)

    @property
    def n_ok(self) -> int:
        return self.counts[OverlapStatus.OK.value]

    @property
    def n_suspicious(self) -> int:
        return sum(
            n for k, n in self.counts.items()
            if OverlapStatus(k).is_suspicious
        )

    def report(self) -> str:
        lines = [
            f"considered {self.n_pairs_considered} pair(s) "
            f"from {self.n_source} source x {self.n_reference} reference product(s)",
        ]
        if self.n_source_without_footprint or self.n_reference_without_footprint:
            lines.append(
                f"products with no usable footprint: "
                f"{self.n_source_without_footprint} source, "
                f"{self.n_reference_without_footprint} reference"
            )
        lines.append("")
        lines.append("outcomes:")
        for status in OverlapStatus:
            n = self.counts.get(status.value, 0)
            if not n:
                continue
            marker = "  " if status in (OverlapStatus.OK, OverlapStatus.DISJOINT) else "! "
            lines.append(f"{marker}{status.value:20s} {n:6d}")
            if status.is_suspicious:
                lines.append(f"      sample: {self.samples.get(status.value, '(none)')}")

        if self.counts.get(OverlapStatus.MISSING_FOOTPRINT.value):
            lines += [
                "",
                "NOTE: missing_footprint means the manifest has no corner or bounding-box",
                "      coordinates -- a metadata gap, not a geometry failure. All eight",
                "      corner fields are verified against a real OHRC label, so this is a",
                "      gap in these rows rather than in the field mapping; check the label",
                "      itself with `lunar-reg probe-label`.",
                "      This is NOT evidence that products do not overlap.",
            ]
        if self.n_ok == 0 and self.n_pairs_considered:
            lines += ["", "no usable overlaps found -- see the outcome breakdown above before"
                      " concluding the data is at fault"]
        return "\n".join(lines)


def find_overlapping_pairs(
    manifest,
    source_sensor: str = "OHRC",
    reference_sensor: str = "TMC2",
    min_source_fraction: float = 0.0,
):
    """Intersect every source/reference footprint pair in a manifest.

    Returns ``(pairs_dataframe, diagnostics)``. The DataFrame holds only pairs
    with :attr:`OverlapStatus.OK` that clear ``min_source_fraction``, sorted by
    decreasing overlap area. Everything else is in ``diagnostics``, counted and
    sampled -- nothing is dropped without a trace.
    """
    import pandas as pd

    diagnostics = OverlapDiagnostics()

    sources = manifest[manifest["sensor"] == source_sensor]
    references = manifest[manifest["sensor"] == reference_sensor]
    diagnostics.n_source = len(sources)
    diagnostics.n_reference = len(references)

    source_polys, reference_polys = [], []
    for _, row in sources.iterrows():
        poly = footprint_from_row(row)
        if poly is None:
            diagnostics.n_source_without_footprint += 1
        else:
            source_polys.append(poly)
    for _, row in references.iterrows():
        poly = footprint_from_row(row)
        if poly is None:
            diagnostics.n_reference_without_footprint += 1
        else:
            reference_polys.append(poly)

    missing = diagnostics.n_source_without_footprint + diagnostics.n_reference_without_footprint
    if missing:
        diagnostics.record_missing(
            OverlapStatus.MISSING_FOOTPRINT,
            f"{missing} product(s) carry no corner or bounding-box coordinates; "
            f"first source without one: "
            f"{sources.iloc[0]['product_id'] if len(sources) else '(none)'}",
        )

    rows = []
    for source in source_polys:
        for reference in reference_polys:
            diagnostics.n_pairs_considered += 1
            result = intersect(source, reference)
            diagnostics.record(result)
            if result.ok and result.source_fraction >= min_source_fraction:
                rows.append(result.as_row())

    frame = pd.DataFrame(rows)
    if len(frame):
        frame = frame.sort_values("overlap_area_m2", ascending=False).reset_index(drop=True)

    logger.info(
        "overlap scan: %d usable pair(s), %d suspicious outcome(s)",
        len(frame), diagnostics.n_suspicious,
    )
    if diagnostics.n_suspicious:
        # One concise line here; the full report is the caller's to print, so it
        # is not emitted twice when the CLI prints it too.
        logger.warning(
            "%d non-trivial outcome(s): %s -- call diagnostics.report() for detail",
            diagnostics.n_suspicious,
            ", ".join(
                f"{k}={n}" for k, n in sorted(diagnostics.counts.items())
                if OverlapStatus(k).is_suspicious
            ),
        )
    return frame, diagnostics


# ---------------------------------------------------------------------------
# Cropping to the shared region
# ---------------------------------------------------------------------------


def footprint_frame(footprint: FootprintPolygon) -> PolarFrame | None:
    """The plane a footprint's ground geometry should be handled in.

    ``None`` means lat/lon is good enough. Derived from the footprint alone so
    that :func:`geographic_to_pixel_transform` and
    :func:`polygon_to_pixel_window` cannot disagree about which plane a set of
    pixel coordinates was fitted in.
    """
    if not footprint.is_polar:
        return None
    return PolarFrame(90.0 if max(footprint.lats, key=abs) >= 0.0 else -90.0)


def geographic_to_pixel_transform(footprint: FootprintPolygon):
    """Build a lat/lon -> pixel transform from a footprint's four corners.

    ASSUMPTION, and a real limitation: this fits a homography from the four
    corner coordinates to the four image corners, i.e. it assumes the mapping
    between ground and pixel space is well approximated by a projective
    transform over the whole product. For a short TMC-2 frame that is
    reasonable. For a 90,000-line OHRC pushbroom strip over a curved body it is
    an approximation whose error grows away from the corners.

    It also depends on the corner *ordering* in the field map. That ordering is
    now verified against a real OHRC label -- corner3 is lower-**left**, so the
    ring is traversed 1, 2, 4, 3 -- but only for OHRC. A product from another
    instrument that numbers its corners differently would silently produce a
    mirrored or rotated crop, so treat a first crop from a new sensor as a
    visual check rather than as a measurement.

    For a polar footprint the fit is done in that footprint's
    :class:`PolarFrame` instead of in lat/lon. A homography can absorb a fair
    amount of distortion, but not meridian convergence: at -85 degrees a degree
    of longitude is a twelfth of a degree of latitude on the ground, and the
    ratio changes across the footprint, so a lat/lon fit skews the crop window.

    Returns a 3x3 ``numpy`` array, or ``None`` when the footprint or the pixel
    dimensions are unusable.
    """
    import cv2
    import numpy as np

    if footprint.lines is None or footprint.samples is None:
        return None
    if len(footprint.corners) < 4:
        return None

    height, width = int(footprint.lines), int(footprint.samples)
    if height <= 0 or width <= 0:
        return None

    # Ring order from footprint_from_row is UL, UR, LR, LL.
    frame = footprint_frame(footprint)
    corners = (
        frame.plane_ring(footprint.corners[:4]) if frame else footprint.corners[:4]
    )
    src = np.array([[b, a] for a, b in corners], dtype=np.float32)
    dst = np.array(
        [[0.0, 0.0], [width - 1.0, 0.0], [width - 1.0, height - 1.0], [0.0, height - 1.0]],
        dtype=np.float32,
    )
    return cv2.getPerspectiveTransform(src, dst)


def polygon_to_pixel_window(footprint: FootprintPolygon, polygon):
    """Pixel-space bounding window of a lat/lon polygon within a product.

    Returns ``(row_off, col_off, height, width)`` clipped to the product, or
    ``None`` if the polygon maps entirely outside it.

    The window is **conservative**: it covers every pixel the polygon touches,
    so an edge falling mid-pixel rounds outward. A window may therefore be up to
    one pixel larger per side than the exact geometric extent. That direction is
    deliberate -- a crop that silently drops a row of genuine overlap is worse
    than one carrying a pixel of slop.
    """
    import numpy as np

    matrix = geographic_to_pixel_transform(footprint)
    if matrix is None:
        return None

    # Must use the same plane the matrix was fitted in, hence footprint_frame
    # rather than any decision taken per pair.
    frame = footprint_frame(footprint)
    ring = _strip_closing_duplicate(tuple(polygon))
    if frame is not None:
        ring = frame.plane_ring(ring)
    pts = np.array([[b, a] for a, b in ring], dtype=np.float64)
    homogeneous = np.hstack([pts, np.ones((len(pts), 1))]) @ matrix.T
    denom = homogeneous[:, 2:3]
    if not np.all(np.isfinite(denom)) or np.any(np.abs(denom) < 1e-12):
        return None
    pixels = homogeneous[:, :2] / denom

    # Corners map to pixel *centres* (0 .. width-1), so the exclusive stop bound
    # is one past the last covered pixel. Without the +1 a polygon covering the
    # whole product yields a window one row and one column short.
    col0 = int(math.floor(pixels[:, 0].min()))
    col1 = int(math.floor(pixels[:, 0].max())) + 1
    row0 = int(math.floor(pixels[:, 1].min()))
    row1 = int(math.floor(pixels[:, 1].max())) + 1

    col0 = max(0, min(col0, int(footprint.samples)))
    col1 = max(0, min(col1, int(footprint.samples)))
    row0 = max(0, min(row0, int(footprint.lines)))
    row1 = max(0, min(row1, int(footprint.lines)))

    if col1 <= col0 or row1 <= row0:
        return None
    return (row0, col0, row1 - row0, col1 - col0)


def _safe_stem(text: str | None, fallback: str) -> str:
    """Filesystem-safe stem from a product id (PDS4 LIDs contain ':' and '/')."""
    if not text:
        return fallback
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(text))[-60:]


def crop_to_overlap(
    result: OverlapResult,
    output_dir: str | Path,
    suffix: str = "_overlap.tif",
) -> dict[str, Any]:
    """Crop both products of an overlapping pair to the shared region.

    Uses a windowed read, so an OHRC strip is never fully loaded -- only the
    overlap window comes off disk. Writes one GeoTIFF per side.

    Returns a summary dict including the pixel window used for each side and any
    reason a side could not be cropped. Raises :class:`ValueError` if called on
    a result that is not :attr:`OverlapStatus.OK`, since cropping to a
    degenerate polygon is never meaningful.
    """
    import rasterio
    from rasterio.windows import Window

    from lunar_reg.ingest.pds4 import open_product

    if not result.ok:
        raise ValueError(
            f"cannot crop a pair with status {result.status.value!r}; "
            f"only OK overlaps have a usable polygon ({result.detail})"
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"status": result.status.value, "sides": {}}

    for side, footprint in (("source", result.source), ("reference", result.reference)):
        entry: dict[str, Any] = {"product_id": footprint.product_id}
        window_spec = polygon_to_pixel_window(footprint, result.polygon)
        if window_spec is None:
            entry["error"] = (
                "overlap polygon does not map to a usable pixel window "
                "(missing pixel dimensions, or the polygon falls outside the product)"
            )
            summary["sides"][side] = entry
            logger.warning("%s %s: %s", side, footprint.product_id, entry["error"])
            continue

        row_off, col_off, height, width = window_spec
        entry.update(row_off=row_off, col_off=col_off, height=height, width=width)

        source_path = footprint.label_path or footprint.image_path
        if not source_path:
            entry["error"] = "no label or image path recorded in the manifest"
            summary["sides"][side] = entry
            continue

        # The pair id is part of the name: a product that overlaps several
        # partners produces one crop per pair, and without this the second
        # crop silently overwrites the first with a different region.
        own = _safe_stem(
            footprint.product_id, Path(str(footprint.image_path or source_path)).stem
        )
        partner = _safe_stem(
            (result.reference if side == "source" else result.source).product_id, "partner"
        )
        out_path = output_dir / f"{own}__vs__{partner}{suffix}"
        try:
            with open_product(source_path) as dataset:
                window = Window(col_off, row_off, width, height)
                data = dataset.read(1, window=window)
                profile = dataset.profile.copy()
                profile.update(
                    driver="GTiff", height=height, width=width, count=1,
                    dtype=data.dtype, compress="deflate",
                )
                profile.pop("nodata", None)
                # A PDS4 profile carries blockxsize/blockysize but not tiled;
                # GTiff rejects block sizes unless TILED=YES, so drop them for
                # the small strip-organised outputs a crop produces.
                profile.pop("blockxsize", None)
                profile.pop("blockysize", None)
                profile["tiled"] = False
                with rasterio.open(out_path, "w", **profile) as out:
                    out.write(data, 1)
            entry["output"] = str(out_path)
        except Exception as exc:  # noqa: BLE001 - reported per side, not fatal for the pair
            entry["error"] = f"{type(exc).__name__}: {exc}"
            logger.warning("could not crop %s: %s", source_path, exc)

        summary["sides"][side] = entry

    return summary


def find_cross_sensor_pairs(
    manifest,
    sensors: tuple[str, ...] = ("OHRC", "TMC2", "IIRS", "LRO_NAC"),
    min_source_fraction: float = 0.0,
):
    """Scan every unordered sensor combination, not just OHRC against TMC-2.

    Stage 2 handled one pair of sensors because that was the only pair in play.
    Bringing IIRS in changes the shape of the problem: IIRS at 80 m/px against
    OHRC at 0.25 m/px is a ratio of roughly 320, which no feature matcher
    bridges directly. So the scan now also reports, per pair, the nominal scale
    ratio and -- where the ratio is too wide -- which intermediate sensor to
    chain through instead.

    Returns ``(pairs_dataframe, diagnostics_by_sensor_pair)``. Each pair of
    sensors keeps its own :class:`OverlapDiagnostics`, because "no IIRS
    footprints resolved" and "no OHRC/TMC-2 pairs overlapped" are different
    problems and must not be added together into one count.
    """
    import pandas as pd

    from lunar_reg.ingest.pseudo_gt import (
        MAX_DIRECT_SCALE_RATIO,
        bridge_sensor,
        scale_ratio,
    )

    present = [s for s in sensors if (manifest["sensor"] == s).any()]
    absent = [s for s in sensors if s not in present]
    if absent:
        logger.warning(
            "no products in the manifest for sensor(s): %s -- those combinations "
            "are not scanned, which is a data gap rather than an absence of overlap",
            ", ".join(absent),
        )

    frames, diagnostics = [], {}
    for i, source_sensor in enumerate(present):
        for reference_sensor in present[i + 1:]:
            frame, diag = find_overlapping_pairs(
                manifest, source_sensor, reference_sensor, min_source_fraction
            )
            key = f"{source_sensor}x{reference_sensor}"
            diagnostics[key] = diag
            if not len(frame):
                continue
            ratio = scale_ratio(source_sensor, reference_sensor)
            frame = frame.assign(
                source_sensor=source_sensor,
                reference_sensor=reference_sensor,
                scale_ratio=ratio,
                direct_match_feasible=(
                    None if ratio is None else ratio <= MAX_DIRECT_SCALE_RATIO
                ),
                bridge_via=bridge_sensor(source_sensor, reference_sensor),
            )
            frames.append(frame)

    if not frames:
        return pd.DataFrame(), diagnostics

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("overlap_area_m2", ascending=False).reset_index(drop=True)

    infeasible = combined[combined["direct_match_feasible"] == False]  # noqa: E712
    if len(infeasible):
        logger.warning(
            "%d of %d overlapping pair(s) exceed the direct-match scale ratio of "
            "%.0fx and must be chained through an intermediate sensor; widest is "
            "%s at %.0fx",
            len(infeasible), len(combined), MAX_DIRECT_SCALE_RATIO,
            f"{infeasible.iloc[0]['source_sensor']}x{infeasible.iloc[0]['reference_sensor']}",
            infeasible["scale_ratio"].max(),
        )
    return combined, diagnostics
